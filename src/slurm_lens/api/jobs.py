"""Jobs: how large they are, how they start and end, how long they wait and run."""

from collections import Counter
from statistics import mean

from fastapi import APIRouter
from sqlalchemy import case, func, select

from ..models import JobRecord
from .query import BOX, FINAL, GPU_HOURS, SIZE, SIZES, label, quantiles, started
from .scope import Scope, ScopeDep
from .view import (
    PALETTE,
    Chart,
    Table,
    Tile,
    View,
    box_note,
    duration,
    grouped,
    percent,
    pie,
    series,
)

STARTED = {"SCHEDULE": "main scheduler", "BACKFILL": "backfill", "SUBMIT": "at submit"}
# classes of durations by their upper limit in seconds
DURATIONS = {
    "≤ 10 min": 600,
    "≤ 1 h": 3600,
    "≤ 4 h": 4 * 3600,
    "≤ 12 h": 12 * 3600,
    "≤ 1 day": 24 * 3600,
    "≤ 2 days": 48 * 3600,
    "≤ 1 week": 7 * 24 * 3600,
}
LONGER = "> 1 week"
LIMIT = JobRecord.time_limit_min * 60
FINISHED = JobRecord.state.in_(FINAL)

router = APIRouter()


@router.get("")
def view(scope: ScopeDep) -> View:
    jobs = Jobs(scope)
    return View(jobs.tiles(), [
        jobs.per_day(), jobs.sizes(), jobs.waits(), jobs.starts_per_size(), jobs.starts(),
        jobs.limit_used(), jobs.durations(), jobs.states(),
    ])  # fmt: skip


def duration_class(seconds):
    return case(*((seconds <= limit, name) for name, limit in DURATIONS.items()), else_=LONGER)


class Jobs:
    """The jobs that started in the period."""

    def __init__(self, scope: Scope):
        self.scope = scope

    def rows(self, *columns, where=True, by=()) -> list:
        query = select(*by, *columns).where(started(self.scope), where).group_by(*by)
        return self.scope.session.execute(query).all()

    def by(self, column, keys: list, *columns, where=True) -> list:
        """One row per key of the column that has jobs, in the order of the keys."""
        rows = {row[0]: row for row in self.rows(*columns, where=where, by=(column,))}
        return [rows[key] for key in keys if key in rows]

    def tiles(self) -> list[Tile]:
        [(jobs, gpu_jobs, backfill)] = self.rows(
            func.count(),
            func.count().filter(JobRecord.gpus > 0),
            func.count().filter(JobRecord.started_on == "BACKFILL"),
        )
        states = dict(self.rows(func.count(), where=FINISHED, by=(JobRecord.state,)))
        finished = sum(states.values()) or 1
        share = {state: 100 * states.get(state, 0) / finished for state in FINAL}
        used = quantiles(JobRecord.elapsed_s, 0.5), quantiles(JobRecord.elapsed_s / LIMIT, 0.5)
        [(runtime, limit_used)] = self.rows(*used, where=FINISHED & (LIMIT > 0))
        return [
            Tile("Jobs started", jobs, f"{gpu_jobs:,} of them with GPUs"),
            Tile("Completed", f"{share['COMPLETED']:.0f} %",
                 f"{share['FAILED']:.0f} % failed, {share['TIMEOUT']:.0f} % timed out"),
            Tile("Median runtime", duration(runtime and runtime[0]),
                 f"{100 * limit_used[0]:.0f} % of the time limit" if limit_used else ""),
            Tile("Started by backfill", f"{100 * backfill / (jobs or 1):.0f} %",
                 "the others by the main loop"),
        ]  # fmt: skip

    def per_day(self) -> Chart:
        day = self.scope.day(JobRecord.start_time)
        counts = {(d, size): n for d, size, n in self.rows(func.count(), by=(day, SIZE))}
        days = sorted({d for d, _ in counts})
        values = {size: [counts.get((d, size), 0) for d in days] for size in SIZES[1:]}
        per_day = [sum(day) for day in zip(*values.values(), strict=True)] or [0]
        busiest = days[per_day.index(max(per_day))] if days else None
        stats = {"per day": f"{mean(per_day):,.0f}", "most": f"{max(per_day):,}"}
        if busiest:
            stats["busiest day"] = f"{self.scope.local(busiest):%a %d %b}"
        x = [f"{self.scope.local(d):%d %b}" for d in days]
        return Chart("GPU jobs started per day", "bar", x, series(values), unit=" jobs",
                     stats=stats, stacked=True, wide=True)  # fmt: skip

    def sizes(self) -> Table:
        rows = self.by(
            SIZE, SIZES,
            func.count(),
            GPU_HOURS,
            quantiles(JobRecord.wait_s, 0.5),
            quantiles(JobRecord.elapsed_s, 0.5),
            func.count().filter(JobRecord.started_on == "BACKFILL"),
        )  # fmt: skip
        jobs, hours = percent([r[1] for r in rows]), percent([r[2] for r in rows])
        rows = [
            [size, n, jobs[i], gpu_hours, hours[i], wait[0] / 3600, runtime[0] / 3600,
             100 * backfill / n]
            for i, (size, n, gpu_hours, wait, runtime, backfill) in enumerate(rows)
        ]  # fmt: skip
        columns = ["Size", "Jobs", "Jobs (%)", "GPU hours", "GPU hours (%)", "Median wait (h)",
                   "Median runtime (h)", "Backfill (%)"]  # fmt: skip
        return Table("Job sizes", columns, rows)

    def waits(self) -> Chart:
        rows = self.by(SIZE, SIZES, quantiles(JobRecord.wait_s, *BOX))
        boxes = {size: [q / 3600 for q in quantile] for size, quantile in rows}
        x = list(boxes)
        values = series(grouped(x, boxes))
        return Chart("Wait per job size", "box", x, values, unit=" h", note=box_note("jobs"))

    def starts(self) -> Chart:
        counts = dict(self.rows(func.count(), by=(JobRecord.started_on,)))
        return pie("How jobs started", {name: counts.get(key, 0) for key, name in STARTED.items()})

    def starts_per_size(self) -> Chart:
        counts, totals = Counter(), Counter()
        for size, how, n in self.rows(func.count(), by=(SIZE, JobRecord.started_on)):
            counts[size, how] += n
            totals[size] += n
        x = [size for size in SIZES if totals[size]]
        shares = {name: [100 * counts[size, key] / totals[size] for size in x]
                  for key, name in STARTED.items()}  # fmt: skip
        values = {name: share for name, share in shares.items() if any(share)}
        return Chart("How jobs started per job size", "bar", x, series(values), unit=" %",
                     y_max=100, stacked=True, horizontal=True)  # fmt: skip

    def durations(self) -> Chart:
        """The backfill scheduler plans with the time limits, so they matter."""
        seconds = {"time limit": LIMIT, "runtime": JobRecord.elapsed_s}
        x, values = [*DURATIONS, LONGER], {}
        for name, column in seconds.items():
            counts = dict(self.rows(func.count(), where=FINISHED, by=(duration_class(column),)))
            values[name] = percent([counts.get(c, 0) for c in x])
        [(limit, runtime)] = self.rows(
            quantiles(LIMIT, 0.5), quantiles(JobRecord.elapsed_s, 0.5), where=FINISHED
        )
        stats = {
            "median time limit": duration(limit and limit[0]),
            "median runtime": duration(runtime and runtime[0]),
        }
        colors = {"time limit": PALETTE[1], "runtime": PALETTE[0]}
        return Chart("Time limit and runtime of finished jobs", "bar", x, series(values, colors),
                     unit=" %", stats=stats, wide=True)  # fmt: skip

    def limit_used(self) -> Chart:
        used = 100 * JobRecord.elapsed_s / LIMIT
        rows = self.by(JobRecord.state, list(FINAL), quantiles(used, *BOX), where=LIMIT > 0)
        boxes = {label(state): quantile for state, quantile in rows}
        colors = {label(state): color for state, color in FINAL.items()}
        x = list(boxes)
        values = series(grouped(x, boxes), colors)
        title = "Time limit used per final state"
        return Chart(title, "box", x, values, unit=" %", note=box_note("jobs"))

    def states(self) -> Table:
        rows = self.by(JobRecord.state, list(FINAL), func.count(), GPU_HOURS)
        jobs, hours = percent([r[1] for r in rows]), percent([r[2] for r in rows])
        rows = [[label(s), n, jobs[i], h, hours[i]] for i, (s, n, h) in enumerate(rows)]
        columns = ["Final state", "Jobs", "Jobs (%)", "GPU hours", "GPU hours (%)"]
        return Table("Final states", columns, rows)
