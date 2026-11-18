"""General statistics about the cluster, from the accounting history and the snapshots."""

from collections import Counter
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import Float, case, func, or_, select
from sqlalchemy.orm import Session

from ..config import Config
from ..models import ConfigVersion, HistoryWindow, JobRecord, JobSnapshot, Snapshot
from ..parse import gres
from ..store import Store
from .view import GRAY, PALETTE, Chart, Series, View, percent, series

HOUR = timedelta(hours=1)
FINAL = ["COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY"]

gpus = func.coalesce(JobRecord.gpus, 0)
gpu_hours = (func.sum(gpus * JobRecord.elapsed_s) / 3600).cast(Float).label("gpu_hours")
size = case(
    (gpus == 0, "CPU only"),
    (gpus == 1, "1 GPU"),
    (gpus <= 4, "2-4 GPUs"),
    (gpus <= 8, "5-8 GPUs"),
    else_="> 8 GPUs",
).label("size")
# resized jobs keep their old allocation as a separate record, it is left out everywhere
counted = JobRecord.state.not_like("%RESIZING%")


def router(config: Config, store: Store) -> APIRouter:
    api = APIRouter()

    @api.get("")
    def view(days: int = 30, hours: int = 24) -> View:
        """Allocation of the last two weeks, jobs of the last days, queue of the last hours."""
        with store.session() as session:
            covered = HistoryWindow.covered(session)
            if not covered:
                raise HTTPException(404, "no accounting history yet")
            start, end = covered
            period = max(start, end - timedelta(days=days)), end, f"last {days} days"
            charts = [
                allocation(session, max(start, end - timedelta(days=14)), end),
                *sizes(session, *period),
                states(session, *period),
                queue(session, hours),
            ]
        return View(charts=charts)

    return api


def capacity(session: Session) -> Counter:
    """GPUs per model as the nodes are configured now."""
    total = Counter()
    for node in ConfigVersion.at(session, "node", datetime.now(UTC)).values():
        for name, model, count, _ in gres(node["gres"]):
            if name == "gpu":
                total[model] += count
    return total


def allocation(session: Session, start: datetime, end: datetime) -> Chart:
    """Allocated share of the four GPU models with the most GPUs, every hour."""
    first = start.replace(minute=0, second=0, microsecond=0)
    hours = func.generate_series(first, end, HOUR).table_valued("hour").render_derived()
    # ran(first, end) is implied, but lets the database skip all other jobs early
    jobs = ran(hours.c.hour, hours.c.hour) & ran(first, end) & counted & (JobRecord.gpus > 0)
    query = (
        select(hours.c.hour, JobRecord.gpu_model, func.sum(JobRecord.gpus).cast(Float))
        .select_from(hours)
        .outerjoin(JobRecord, jobs)
        .group_by(hours.c.hour, JobRecord.gpu_model)
    )
    used = {(hour, model): gpus for hour, model, gpus in session.execute(query)}
    x = sorted({hour for hour, _ in used})
    values = {
        model: [100 * used.get((hour, model), 0) / total for hour in x]
        for model, total in capacity(session).most_common(4)
    }
    return Chart("Allocated GPUs per model (%)", "line", x, series(values), y_max=100, wide=True)


def ran(start, end):
    """Jobs that ran at some time from start to end, or at start if both are the same."""
    return (JobRecord.start_time <= end) & or_(
        JobRecord.end_time.is_(None), JobRecord.end_time > start
    )


def started(start: datetime, end: datetime):
    return (JobRecord.start_time >= start) & (JobRecord.start_time < end) & counted


def shares(rows) -> list[Series]:
    """Share of the jobs and of the GPU hours in every row."""
    values = {
        "jobs": percent([r.jobs for r in rows]),
        "GPU hours": percent([r.gpu_hours for r in rows]),
    }
    return series(values, {"jobs": GRAY})


def sizes(session: Session, start: datetime, end: datetime, period: str) -> list[Chart]:
    wait = (func.percentile_cont(0.5).within_group(JobRecord.wait_s) / 60).label("wait")
    query = select(size, func.count().label("jobs"), gpu_hours, wait).where(started(start, end))
    rows = session.execute(query.group_by(size).order_by(func.min(gpus))).all()
    x = [r.size for r in rows]
    waits = series({"wait": [r.wait for r in rows]}, {"wait": PALETTE[1]})
    return [
        Chart(f"Jobs and GPU hours per job size, {period} (%)", "bar", x, shares(rows)),
        Chart(f"Median wait per job size, {period} (minutes)", "bar", x, waits),
    ]


def states(session: Session, start: datetime, end: datetime, period: str) -> Chart:
    query = (
        select(JobRecord.state, func.count().label("jobs"), gpu_hours)
        .where(started(start, end), JobRecord.state.in_(FINAL))
        .group_by(JobRecord.state)
        .order_by(func.count().desc())
    )
    rows = session.execute(query).all()
    x = [r.state.lower().replace("_", " ") for r in rows]
    return Chart(f"Jobs and GPU hours per final state, {period} (%)", "bar", x, shares(rows))


def queue(session: Session, hours: int) -> Chart:
    """Pending tasks in the last hours of snapshots, all of them and those competing."""
    last_ok = Snapshot.latest(session, "ok")
    since = (last_ok.taken_at if last_ok else datetime.now(UTC)) - hours * HOUR
    tasks = func.sum(JobSnapshot.array_tasks)
    competing = tasks.filter(JobSnapshot.reason.in_(["Priority", "Resources"]))
    query = (
        select(Snapshot.taken_at, tasks.label("all"), competing.label("competing"))
        .join(JobSnapshot)
        .where(Snapshot.status == "ok", Snapshot.taken_at > since, JobSnapshot.state == "PENDING")
        .group_by(Snapshot.id)
        .order_by(Snapshot.id)
    )
    rows = session.execute(query).all()
    # a log axis cannot show 0
    values = {
        "all": [r.all or None for r in rows],
        "competing": [r.competing or None for r in rows],
    }
    title = f"Pending tasks in the queue, last {hours} hours"
    return Chart(title, "line", [r.taken_at for r in rows], series(values, {"all": GRAY}), log=True)
