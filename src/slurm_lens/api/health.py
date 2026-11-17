"""Health: does the collector run, do its requests succeed, is the history complete?"""

from collections import Counter
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from sqlalchemy import func, select

from ..config import Config
from ..models import HistoryWindow, JobRecord, Snapshot
from ..store import Store
from .view import STATUS, Chart, Tile, View, series

DAY, MINUTE = timedelta(days=1), timedelta(minutes=1)


def router(config: Config, store: Store) -> APIRouter:
    api = APIRouter()

    @api.get("")
    def view(runs: int = 300) -> View:
        with store.session() as session:
            last, last_ok = Snapshot.latest(session), Snapshot.latest(session, "ok")
            snapshots = session.scalars(select(Snapshot).order_by(Snapshot.id.desc()).limit(runs))
            snapshots = list(snapshots)[::-1]
            query = select(HistoryWindow.start_time, HistoryWindow.end_time)
            windows = session.execute(query.where(HistoryWindow.complete)).all()
            start, end = HistoryWindow.covered(session) or (None, None)
            jobs = session.scalar(select(func.count()).select_from(JobRecord))
        tiles = [
            Tile("Last run", last and last.taken_at, last.status if last else "no run yet"),
            Tile("Last successful run", last_ok and last_ok.taken_at),
            Tile("History without gaps", end, f"since {start:%d %b %Y}" if start else ""),
            Tile("Jobs in the history", jobs, f"{len(windows)} complete windows"),
        ]
        return View(tiles, [durations(snapshots), coverage(windows)])

    @api.get("/status")
    def status() -> dict:
        """For the header of every view: when it was generated, is the collector healthy?"""
        now = datetime.now(UTC)
        with store.session() as session:
            last_ok = Snapshot.latest(session, "ok")
            healthy = Snapshot.healthy(session, config.interval, now)
        return {"generated_at": now, "synced_at": last_ok and last_ok.taken_at, "healthy": healthy}

    return api


def durations(snapshots: list[Snapshot]) -> Chart:
    """Minutes every finished run took, one series per status."""
    finished = [s for s in snapshots if s.finished_at]
    minutes = {
        status: [
            (s.finished_at - s.taken_at) / MINUTE if s.status == status else None for s in finished
        ]
        for status in STATUS
        if any(s.status == status for s in finished)
    }
    x = [s.taken_at for s in finished]
    title = "Duration of the collector runs (minutes)"
    return Chart(title, "dot", x, series(minutes, STATUS), wide=True)


def coverage(windows: list[tuple[datetime, datetime]]) -> Chart:
    """Share of every day that complete accounting windows cover, up to today."""
    covered = Counter()
    for start, end in windows:
        covered[start.date()] += (end - start) / DAY
    today = datetime.now(UTC).date()
    first = min(covered, default=today)
    days = [first + i * DAY for i in range((today - first).days + 1)]
    values = {"covered": [min(100, 100 * covered[day]) for day in days]}
    title = "Accounting history covered per day (%)"
    return Chart(title, "bar", [f"{d:%d %b}" for d in days], series(values), y_max=100, wide=True)
