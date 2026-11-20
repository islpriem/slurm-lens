"""GPUs: how much of every model is allocated, over time and per hour."""

from statistics import mean

from fastapi import APIRouter
from sqlalchemy import func, select

from ..models import JobRecord
from .query import allocated, capacity, model_colors, nodes, quantiles, started, total
from .scope import Scope, ScopeDep
from .view import GRAY, Chart, Table, Tile, View, box, box_note, grouped, ranking, series, top

router = APIRouter()


@router.get("")
def view(scope: ScopeDep) -> View:
    gpus = Gpus(scope)
    panels = [gpus.over_time(), gpus.allocation(), gpus.partitions(), gpus.table()]
    return View(gpus.tiles(), panels)


class Gpus:
    """GPUs allocated per model and hour, compared with the GPUs the nodes have now."""

    def __init__(self, scope: Scope):
        self.scope = scope
        self.nodes = [node for node in nodes(scope.session) if node.gpus]
        self.capacity = capacity(self.nodes)
        self.models = [model for model, _ in self.capacity.most_common()]
        self.colors = model_colors(self.capacity)
        used = allocated(scope, JobRecord.gpu_model)
        self.hourly = {m: [used.get((hour, m), 0) for hour in scope.hours] for m in self.models}
        self.total = [sum(gpus) for gpus in zip(*self.hourly.values(), strict=True)]
        self.shares = {m: [100 * g / self.capacity[m] for g in self.hourly[m]] for m in self.models}

    def tiles(self) -> list[Tile]:
        gpus, hours = self.capacity.total(), len(self.scope.hours)
        share = [100 * used / gpus for used in self.total]
        busiest = max(self.models, key=lambda model: mean(self.shares[model]))
        return [
            Tile("GPUs", gpus, f"{len(self.models)} models on {len(self.nodes)} nodes"),
            Tile("Allocated on average", f"{mean(share):.0f} %",
                 f"between {min(share):.0f} and {max(share):.0f} % per hour"),
            Tile("Idle GPU hours", round(gpus * hours - sum(self.total)), f"of {gpus * hours:,}"),
            Tile("Busiest model", busiest, f"{mean(self.shares[busiest]):.0f} % allocated"),
        ]  # fmt: skip

    def over_time(self) -> Chart:
        """The models with an own color, the others together."""
        values = {model: self.hourly[model] for model in self.models if model in self.colors}
        rest = [self.hourly[model] for model in self.models if model not in self.colors]
        if rest:
            values["other"] = [sum(gpus) for gpus in zip(*rest, strict=True)]
        stats = {
            "average": f"{mean(self.total):.0f}",
            "lowest hour": f"{min(self.total):.0f}",
            "highest hour": f"{max(self.total):.0f}",
            "GPUs": f"{self.capacity.total()}",
        }
        return Chart("Allocated GPUs per model", "area", self.scope.hours,
                     series(values, self.colors), unit=" GPUs", note="Average of every hour.",
                     stats=stats, y_max=self.capacity.total(), stacked=True,
                     wide=True)  # fmt: skip

    def allocation(self) -> Chart:
        boxes = {model: box(self.shares[model]) for model in self.models}
        groups = {model: model if model in self.colors else "other" for model in self.models}
        values = series(grouped(self.models, boxes, groups), self.colors)
        return Chart("Allocated share per model", "box", self.models, values, unit=" %",
                     note=box_note("hours"), y_max=100)  # fmt: skip

    def partitions(self) -> Chart:
        hours = top(total(allocated(self.scope, JobRecord.partition)), 7)
        return ranking("GPU hours per partition", hours, {"others": GRAY}, unit=" h")

    def table(self) -> Table:
        query = (
            select(JobRecord.gpu_model, func.count(), quantiles(JobRecord.wait_s, 0.5))
            .where(started(self.scope), JobRecord.gpus > 0)
            .group_by(JobRecord.gpu_model)
        )
        jobs = {m: (n, wait[0] / 3600) for m, n, wait in self.scope.session.execute(query)}
        hours = len(self.scope.hours)
        rows = [
            [model, self.capacity[model], sum(n.model == model for n in self.nodes),
             mean(self.shares[model]), sum(self.hourly[model]),
             self.capacity[model] * hours - sum(self.hourly[model]), *jobs.get(model, (0, None))]
            for model in self.models
        ]  # fmt: skip
        columns = ["Model", "GPUs", "Nodes", "Allocated (%)", "GPU hours used", "Idle GPU hours",
                   "GPU jobs started", "Median wait (h)"]  # fmt: skip
        return Table("Models", columns, rows)
