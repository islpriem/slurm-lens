"""Queue: what is pending and why, how long jobs wait, when they are submitted."""

from collections import Counter
from datetime import UTC, datetime
from statistics import mean

from fastapi import APIRouter
from sqlalchemy import func, select

from ..models import Job, JobRecord, JobSnapshot, NodeSnapshot, Snapshot
from .nodes import state
from .query import nodes, quantiles, started
from .scope import Scope, ScopeDep
from .view import GRAY, PALETTE, Chart, Table, Tile, View, duration, ranking, series

# why a job is pending; competing means it waits for resources or its priority
REASONS = {
    "competing": PALETTE[0],
    "dependency": PALETTE[1],
    "held": PALETTE[4],
    "limit": PALETTE[3],
    "nodes unavailable": PALETTE[6],
    "other": GRAY,
}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

router = APIRouter()


@router.get("")
def view(scope: ScopeDep) -> View:
    queue = Queue(scope)
    return View(queue.tiles(), [
        queue.over_time(), queue.reasons(), queue.demand(), queue.submissions(), queue.waits(),
        queue.users(),
    ])  # fmt: skip


def reason(value: str | None) -> str:
    """The group of a Slurm pending reason."""
    value = value or ""
    if value in ("Resources", "Priority"):
        return "competing"
    if value.startswith("Dependency"):
        return "dependency"
    if value.startswith("JobHeld"):
        return "held"
    if "Limit" in value or value.startswith(("QOS", "Assoc")):
        return "limit"
    if value == "ReqNodeNotAvail":
        return "nodes unavailable"
    return "other"


class Queue:
    """The pending jobs and the free GPUs of the latest snapshot."""

    def __init__(self, scope: Scope):
        self.scope = scope
        latest = Snapshot.latest(scope.session, "ok")
        self.taken_at = latest.taken_at if latest else datetime.now(UTC)
        snapshot = latest and latest.id
        columns = [JobSnapshot.reason, JobSnapshot.array_tasks, JobSnapshot.eligible_time,
                   Job.user_name, Job.submit_time, Job.req_gpus, Job.partition]  # fmt: skip
        query = (
            select(*columns)
            .join(Job)
            .where(JobSnapshot.snapshot_id == snapshot, JobSnapshot.state == "PENDING")
        )
        self.pending = scope.session.execute(query).all()
        self.competing = [job for job in self.pending if reason(job.reason) == "competing"]
        # free GPUs per available node
        self.nodes = {node.name: node for node in nodes(scope.session) if node.gpus}
        query = select(NodeSnapshot).where(
            NodeSnapshot.snapshot_id == snapshot, NodeSnapshot.node.in_(self.nodes)
        )
        self.free = {
            n.node: self.nodes[n.node].gpus - n.gpus_used
            for n in scope.session.scalars(query)
            if state(n.state) != "unavailable"
        }

    def wanted(self, jobs) -> int:
        return sum((job.req_gpus or 0) * job.array_tasks for job in jobs)

    def tiles(self) -> list[Tile]:
        tasks = sum(job.array_tasks for job in self.pending)
        competing = sum(job.array_tasks for job in self.competing)
        query = select(quantiles(JobRecord.wait_s, 0.5, 0.9)).where(
            started(self.scope), JobRecord.gpus > 0
        )
        median, p90 = self.scope.session.scalar(query) or (None, None)
        start, end = self.scope.history
        submitted = (JobRecord.submit_time >= start) & (JobRecord.submit_time < end)
        submissions = self.scope.session.scalar(select(func.count()).where(submitted))
        days = max(1, (end - start).total_seconds() / 86400)
        return [
            Tile("Pending now", len(self.pending), f"{tasks:,} tasks with the array tasks"),
            Tile("Waiting for resources now", competing,
                 f"tasks for {self.wanted(self.competing)} GPUs, {sum(self.free.values())} free"),
            Tile("Median wait of GPU jobs", duration(median), f"90th percentile {duration(p90)}"),
            Tile("Jobs submitted", submissions, f"{submissions / days:,.0f} a day"),
        ]  # fmt: skip

    def over_time(self) -> Chart:
        """Pending tasks per reason in every snapshot of the period."""
        period = Snapshot.taken_at.between(self.scope.start, self.scope.end)
        query = (
            select(Snapshot.taken_at, JobSnapshot.reason, func.sum(JobSnapshot.array_tasks))
            .join(JobSnapshot)
            .where(Snapshot.status == "ok", period, JobSnapshot.state == "PENDING")
            .group_by(Snapshot.id, JobSnapshot.reason)
            .order_by(Snapshot.id)
        )
        counts = {}
        for taken_at, value, tasks in self.scope.session.execute(query):
            counts.setdefault(taken_at, Counter())[reason(value)] += tasks
        values = {r: [c[r] for c in counts.values()] for r in REASONS}
        totals = [c.total() for c in counts.values()] or [0]
        stats = {
            "pending on average": f"{mean(totals):,.0f}",
            "competing on average": f"{mean(values['competing'] or [0]):,.0f}",
            "most": f"{max(totals):,}",
        }
        return Chart("Pending tasks per reason", "area", list(counts), series(values, REASONS),
                     unit=" tasks", note="From the snapshots; an array counts with every task.",
                     stats=stats, stacked=True, wide=True)  # fmt: skip

    def reasons(self) -> Chart:
        tasks = Counter()
        for job in self.pending:
            tasks[reason(job.reason)] += job.array_tasks
        values = {r: tasks[r] for r, _ in tasks.most_common()}
        return ranking("Why tasks are pending now", values, REASONS, unit=" tasks")

    def demand(self) -> Chart:
        """GPUs that competing jobs ask for; jobs and nodes in several partitions count in each."""
        wanted, free = Counter(), Counter()
        for job in self.competing:
            for partition in job.partition.split(","):
                wanted[partition] += self.wanted([job])
        for node, gpus in self.free.items():
            for partition in self.nodes[node].partitions:
                free[partition] += gpus
        x = [p for p, _ in (wanted + free).most_common() if p != "admin"]
        values = {"wanted": [wanted[p] for p in x], "free": [free[p] for p in x]}
        colors = {"wanted": PALETTE[1], "free": PALETTE[2]}
        return Chart("GPUs wanted and free per partition now", "bar", x, series(values, colors),
                     unit=" GPUs", note="Jobs for several partitions count in each of them.",
                     horizontal=True)  # fmt: skip

    def submissions(self) -> Chart:
        """Jobs submitted per weekday and hour of the reader; an array counts once."""
        start, end = self.scope.history
        local = func.timezone(self.scope.zone, JobRecord.submit_time)
        day, hour = func.extract("isodow", local), func.extract("hour", local)
        submission = func.coalesce(JobRecord.array_job_id, JobRecord.job_id).distinct()
        query = (
            select(day, hour, func.count(submission))
            .where(JobRecord.submit_time >= start, JobRecord.submit_time < end)
            .group_by(day, hour)
        )
        weeks = max(1, (end - start).total_seconds() / (7 * 86400))
        counts = {(int(d), int(h)): n / weeks for d, h, n in self.scope.session.execute(query)}
        hours = range(24)
        values = {d: [counts.get((i, h), 0) for h in hours] for i, d in enumerate(WEEKDAYS, 1)}
        busiest = max(counts, key=counts.get, default=(1, 0))
        stats = {"busiest hour": f"{WEEKDAYS[busiest[0] - 1]} {busiest[1]:02}:00"}
        return Chart("Submissions per weekday and hour", "heatmap", [f"{h:02}" for h in hours],
                     series(values, dict.fromkeys(WEEKDAYS, PALETTE[0])), unit=" a week",
                     note="Average per week; an array counts once.", stats=stats,
                     wide=True)  # fmt: skip

    def waits(self) -> Chart:
        """Median and 90th percentile of the wait of the GPU jobs started on a day."""
        day = self.scope.day(JobRecord.start_time)
        query = (
            select(day, quantiles(JobRecord.wait_s, 0.5, 0.9))
            .where(started(self.scope), JobRecord.gpus > 0)
            .group_by(day)
            .order_by(day)
        )
        rows = self.scope.session.execute(query).all()
        values = {
            "median": [q[0] / 3600 for _, q in rows],
            "90th percentile": [q[1] / 3600 for _, q in rows],
        }
        return Chart("Wait of the GPU jobs per day", "line", [d for d, _ in rows], series(values),
                     unit=" h", note="From eligible until start.", wide=True)  # fmt: skip

    def users(self) -> Table:
        """Users with pending jobs now; an array counts once as job."""
        users = {}
        for job in self.pending:
            users.setdefault(self.scope.user(job.user_name), []).append(job)
        rows = []
        for user, jobs in users.items():
            reasons = Counter()
            for job in jobs:
                reasons[reason(job.reason)] += job.array_tasks
            since = min(job.eligible_time or job.submit_time or self.taken_at for job in jobs)
            competing = [job for job in jobs if reason(job.reason) == "competing"]
            rows.append([
                user, len(jobs), reasons.total(), reasons["competing"], self.wanted(competing),
                reasons.most_common(1)[0][0], (self.taken_at - since).total_seconds() / 3600,
            ])  # fmt: skip
        rows.sort(key=lambda row: -row[2])
        columns = ["User", "Pending jobs", "Tasks", "Competing tasks", "GPUs wanted",
                   "Main reason", "Longest wait (h)"]  # fmt: skip
        return Table("Users with pending jobs now", columns, rows)
