"""Health: does the collector run, do its requests succeed, is the history complete?"""

from collections import Counter
from datetime import UTC, datetime, timedelta
from functools import cached_property
from statistics import median

from fastapi import APIRouter, Response
from sqlalchemy import Integer, func, select

from .. import slurm
from ..client import token_expiry
from ..collector import missing_windows
from ..config import Config
from ..models import ApiCall, HistoryWindow, JobRecord, Snapshot
from .query import quantiles
from .scope import ConfigDep, Scope, ScopeDep, SessionDep
from .view import STATUS, Chart, Table, Tile, View, duration, series

DAY = timedelta(days=1)

router = APIRouter()


@router.get("")
def view(scope: ScopeDep, config: ConfigDep) -> View:
    health = Health(scope, config)
    tiles = [health.collector(), health.history(), health.token(), health.collected()]
    return View(tiles, [
        health.durations(), health.fetched(), health.coverage(), health.requests(), health.table(),
    ])  # fmt: skip


@router.get("/check", responses={503: {"description": "The collector or its token need a look"}})
def check(scope: ScopeDep, config: ConfigDep, response: Response) -> dict:
    """For uptime monitoring: 200 while everything works, 503 if something has failed."""
    health = Health(scope, config)
    checks = [health.collector(), health.history(), health.token()]
    healthy = all(check.status != "fail" for check in checks)
    response.status_code = 200 if healthy else 503
    return {"healthy": healthy} | {
        check.title: {"status": check.status, "value": check.value, "note": check.note}
        for check in checks
    }


@router.get("/status")
def status(session: SessionDep, config: ConfigDep) -> dict:
    """For every view: when it was generated, when the collector last succeeded, is it healthy?"""
    now = datetime.now(UTC)
    last_ok = Snapshot.latest(session, "ok")
    healthy = Snapshot.healthy(session, config.interval, now)
    return {"generated_at": now, "synced_at": last_ok and last_ok.taken_at, "healthy": healthy}


def ago(time: datetime | None) -> str:
    return f"{duration((datetime.now(UTC) - time).total_seconds())} ago" if time else "never"


def seconds(run: Snapshot) -> float | None:
    return (run.finished_at - run.taken_at).total_seconds() if run.finished_at else None


class Health:
    """The collector runs of the period with their requests, and the state of the history."""

    def __init__(self, scope: Scope, config: Config):
        self.scope, self.config, self.now = scope, config, datetime.now(UTC)

    @cached_property
    def runs(self) -> list:
        items = func.sum(ApiCall.items)
        calls = (
            select(
                ApiCall.snapshot_id,
                func.count().label("calls"),
                func.count().filter(ApiCall.status.is_distinct_from(200)).label("failed"),
                items.filter(ApiCall.path == slurm.PATHS["jobs"]).cast(Integer).label("queue"),
                items.filter(ApiCall.path == slurm.PATHS["history"]).cast(Integer).label("history"),
            )
            .group_by(ApiCall.snapshot_id)
            .subquery()
        )
        query = (
            select(Snapshot, calls.c.calls, calls.c.failed, calls.c.queue, calls.c.history)
            .outerjoin(calls, calls.c.snapshot_id == Snapshot.id)
            .where(Snapshot.taken_at.between(self.scope.start, self.scope.end))
            .order_by(Snapshot.id)
        )
        return self.scope.session.execute(query).all()

    def collector(self) -> Tile:
        session = self.scope.session
        last_ok = Snapshot.latest(session, "ok")
        note = f"last ok run {ago(last_ok and last_ok.taken_at)}"
        if Snapshot.healthy(session, self.config.interval, self.now):
            return Tile("Collector", "healthy", note, "ok")
        return Tile("Collector", "unhealthy", note, "fail")

    def history(self) -> Tile:
        session = self.scope.session
        query = select(HistoryWindow.start_time).where(HistoryWindow.complete)
        missing = missing_windows(self.config, set(session.scalars(query)), self.now)
        _, end = HistoryWindow.covered(session) or (None, None)
        if missing:
            windows = f"{len(missing)} window{'s' if len(missing) > 1 else ''} missing"
            return Tile("Accounting history", windows, f"no gaps up to {ago(end)}", "warn")
        return Tile("Accounting history", "complete", f"up to {ago(end)}", "ok")

    def token(self) -> Tile:
        try:
            expiry = token_expiry(self.config.token())
        except (OSError, KeyError):
            return Tile("Slurm token", "unknown", "not readable here")
        if expiry is None:
            return Tile("Slurm token", "unknown", "no expiry in the token")
        left = (expiry - self.now).total_seconds()
        days = left / DAY.total_seconds()
        status = "fail" if days < 1 else "warn" if days < 7 else "ok"
        return Tile("Slurm token", expiry, f"valid for {duration(max(0, left))}", status)

    def collected(self) -> Tile:
        session = self.scope.session
        jobs = session.scalar(select(func.count()).select_from(JobRecord))
        snapshots = session.scalar(select(func.count()).select_from(Snapshot))
        return Tile("Jobs collected", jobs, f"and {snapshots:,} snapshots")

    def durations(self) -> Chart:
        """Minutes every finished run took, one series per status."""
        runs = [run.Snapshot for run in self.runs if run.Snapshot.finished_at]
        statuses = [status for status in STATUS if any(r.status == status for r in runs)]
        minutes = {s: [seconds(r) / 60 if r.status == s else None for r in runs] for s in statuses}
        took = [seconds(run) for run in runs] or [0]
        stats = {
            "runs": f"{len(runs):,}",
            "not ok": f"{sum(run.status != 'ok' for run in runs):,}",
            "median": duration(median(took)),
            "longest": duration(max(took)),
        }
        return Chart("Duration of the collector runs", "dot", [r.taken_at for r in runs],
                     series(minutes, STATUS), unit=" min", stats=stats, wide=True)  # fmt: skip

    def fetched(self) -> Chart:
        values = {
            "live queue": [run.queue for run in self.runs],
            "accounting": [run.history for run in self.runs],
        }
        x = [run.Snapshot.taken_at for run in self.runs]
        return Chart("Jobs fetched per run", "line", x, series(values))

    def coverage(self) -> Chart:
        """Share of every day of the period that complete accounting windows cover."""
        first = self.scope.start.replace(hour=0, minute=0, second=0, microsecond=0)
        query = select(HistoryWindow.start_time, HistoryWindow.end_time).where(
            HistoryWindow.complete, HistoryWindow.start_time.between(first, self.scope.end)
        )
        covered = Counter()
        for start, end in self.scope.session.execute(query):
            covered[start.date()] += (end - start) / DAY
        first, today = min(covered, default=self.now.date()), self.now.date()
        days = [first + i * DAY for i in range((today - first).days + 1)]
        values = {"covered": [min(100, 100 * covered[day]) for day in days]}
        return Chart("Accounting history covered per day", "bar", [f"{d:%d %b}" for d in days],
                     series(values), unit=" %", y_max=100)  # fmt: skip

    def requests(self) -> Table:
        """The requests of the period to slurmrestd, per endpoint."""
        names = {path: name for name, path in slurm.PATHS.items()}
        failed = func.count().filter(ApiCall.status.is_distinct_from(200))
        query = (
            select(ApiCall.path, func.count(), failed, quantiles(ApiCall.seconds, 0.5),
                   func.max(ApiCall.seconds))
            .join(Snapshot)
            .where(Snapshot.taken_at.between(self.scope.start, self.scope.end))
            .group_by(ApiCall.path)
            .order_by(func.count().desc())
        )  # fmt: skip
        rows = [
            [names.get(path, path), path, n, bad, median[0], longest]
            for path, n, bad, median, longest in self.scope.session.execute(query)
        ]
        columns = ["Endpoint", "Path", "Requests", "Failed", "Median (s)", "Longest (s)"]
        return Table("Requests to slurmrestd", columns, rows)

    def table(self) -> Table:
        rows = [
            [run.taken_at, run.status, seconds(run), calls, failed, queue, history, run.error]
            for run, calls, failed, queue, history in reversed(self.runs[-15:])
        ]
        columns = ["Started", "Status", "Seconds", "Requests", "Failed", "Queue jobs",
                   "Accounting jobs", "Error"]  # fmt: skip
        return Table("Latest runs", columns, rows)
