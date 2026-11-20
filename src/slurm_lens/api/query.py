"""Building blocks the views share: the nodes, sizes and states of jobs, GPUs per hour."""

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Float, case, func, or_, select, true, type_coerce
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.orm import Session

from ..models import ConfigVersion, JobRecord, JobRecordNode
from ..parse import gres
from .scope import HOUR, Scope
from .view import GRAY, PALETTE, RED

GPUS = func.coalesce(JobRecord.gpus, 0)
GPU_HOURS = (func.sum(GPUS * JobRecord.elapsed_s) / 3600).cast(Float)
SIZES = ["CPU only", "1 GPU", "2-4 GPUs", "5-8 GPUs", "> 8 GPUs"]
SIZE = case(
    (GPUS == 0, SIZES[0]),
    (GPUS == 1, SIZES[1]),
    (GPUS <= 4, SIZES[2]),
    (GPUS <= 8, SIZES[3]),
    else_=SIZES[4],
)
# final states and their colors
FINAL = {
    "COMPLETED": PALETTE[2],
    "FAILED": RED,
    "CANCELLED": GRAY,
    "TIMEOUT": PALETTE[3],
    "OUT_OF_MEMORY": PALETTE[4],
}
BOX = (0.05, 0.25, 0.5, 0.75, 0.95)  # quantiles of a box plot
# resized jobs keep their old allocation as a separate record, it is left out everywhere
COUNTED = JobRecord.state.not_like("%RESIZING%")


@dataclass
class Node:
    name: str
    model: str | None
    gpus: int
    cpus: int
    memory_mb: int
    partitions: list[str]

    def size(self, column) -> int:
        """How much of the resource that a JobRecord column counts the node has."""
        return {"gpus": self.gpus, "cpus": self.cpus, "memory_mb": self.memory_mb}[column.key]


def nodes(session: Session) -> list[Node]:
    """The nodes as they are configured now."""
    config = ConfigVersion.at(session, "node", datetime.now(UTC))
    result = []
    for name, n in sorted(config.items()):
        gpus = [(model, count) for kind, model, count, _ in gres(n["gres"]) if kind == "gpu"]
        model, count = gpus[0] if gpus else (None, 0)
        result.append(Node(name, model, count, n["cpus"], n["real_memory"], n["partitions"]))
    return result


def capacity(nodes: list[Node]) -> Counter:
    """GPUs per model."""
    result = Counter()
    for node in nodes:
        if node.gpus:
            result[node.model] += node.gpus
    return result


def gpu_nodes(nodes: list[Node]) -> list[Node]:
    """The nodes with GPUs, by model (the one with the most GPUs first) and name."""
    models = [model for model, _ in capacity(nodes).most_common()]
    return sorted((n for n in nodes if n.gpus), key=lambda n: (models.index(n.model), n.name))


def model_colors(capacity: Counter) -> dict[str, str]:
    """The models with the most GPUs get the palette in order, the others are drawn gray."""
    models = [model for model, _ in capacity.most_common()]
    return dict(zip(models, PALETTE, strict=False)) | {"other": GRAY}


def label(value: str) -> str:
    """'OUT_OF_MEMORY' -> 'out of memory'"""
    return value.lower().replace("_", " ")


def quantiles(column, *q: float):
    """The given quantiles of a column as a list, e.g. BOX for a box plot."""
    # as Float, SQLAlchemy would convert the list as a whole for a Numeric column
    return func.percentile_cont(array(q)).within_group(type_coerce(column, Float))


def started(scope: Scope):
    """Jobs that started in the history period."""
    start, end = scope.history
    return (JobRecord.start_time >= start) & (JobRecord.start_time < end) & COUNTED


def allocated(scope: Scope, *by, resource=JobRecord.gpus) -> dict[tuple, float]:
    """GPUs (or another resource) allocated on average in every hour of the history period.

    Keys are the hour followed by the values of `by`. With JobRecordNode.node in `by` the
    resources of a job are split evenly over its nodes.
    """
    per_node = any(column is JobRecordNode.node for column in by)
    start, end = scope.history
    begin = func.greatest(JobRecord.start_time, start)
    until = func.least(func.coalesce(JobRecord.end_time, end), end)
    # one row per job and hour it overlaps, weighted with the overlap
    hours = func.generate_series(func.date_trunc("hour", begin), until, HOUR)
    hour = hours.table_valued("hour").render_derived().lateral()
    overlap = func.least(until, hour.c.hour + HOUR) - func.greatest(begin, hour.c.hour)
    used = resource * func.extract("epoch", overlap) / 3600
    query = (
        select(hour.c.hour, *by, func.sum(used / JobRecord.node_count if per_node else used))
        .select_from(JobRecord)
        .join(hour, true())
        .where(resource > 0, JobRecord.node_count > 0, COUNTED, JobRecord.start_time < end)
        .where(or_(JobRecord.end_time.is_(None), JobRecord.end_time > start))
        .group_by(hour.c.hour, *by)
    )
    if per_node:
        query = query.join(JobRecordNode)
    return {tuple(row[:-1]): float(row[-1]) for row in scope.session.execute(query)}


def total(values: dict[tuple, float], key: int = 1) -> Counter:
    """Sums over all hours, by the value at the given position of the keys."""
    result = Counter()
    for keys, value in values.items():
        result[keys[key]] += value
    return result
