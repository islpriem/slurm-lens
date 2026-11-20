"""Timeline: one row per GPU, what ran on it and what the scheduler plans, as at any snapshot."""

from bisect import bisect, insort
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import accumulate

from fastapi import APIRouter, HTTPException
from sqlalchemy import and_, or_, select

from ..models import (
    Job,
    JobAllocation,
    JobRecord,
    JobRecordNode,
    JobSnapshot,
    NodeSnapshot,
    Snapshot,
)
from ..parse import hostlist
from .jobs import STARTED
from .nodes import state
from .query import COUNTED, gpu_nodes, label, nodes
from .scope import Scope, ScopeDep
from .view import PALETTE, duration

# what a bar shows: the job ran; it runs at the snapshot, up to its time limit; it is planned
RAN, RUNNING, PLANNED = 0, 1, 2

router = APIRouter()


@dataclass
class GpuNode:
    name: str
    model: str
    gpus: int
    partitions: list[str]
    state: str | None  # at the snapshot


@dataclass
class Gantt:
    at: datetime  # the snapshot that is now
    start: datetime
    end: datetime
    snapshots: list[datetime]  # of the period, to go back to
    nodes: list[GpuNode]  # their GPUs are the rows, in this order
    jobs: list[tuple[int, str, str]]  # job id, user and account
    bars: list[tuple[int, int, int, int, int]]  # job, row, start and end in ms, what it shows
    colors: dict[str, dict[str, str]]  # per user and per account; the others are gray


@dataclass
class Section:
    title: str
    rows: list[tuple[str, datetime | int | float | str | None]]

    def __post_init__(self):
        self.rows = [(name, value) for name, value in self.rows if value not in (None, "")]


@dataclass
class Details:
    title: str
    sections: list[Section]


@router.get("")
def view(scope: ScopeDep, at: datetime | None = None, ahead: int = 48) -> Gantt:
    return Timeline(scope, at, timedelta(hours=ahead)).gantt()


@router.get("/jobs/{job_id}")
def details(job_id: int, scope: ScopeDep, at: datetime | None = None) -> Details:
    return Timeline(scope, at).details(job_id)


@dataclass
class Piece:
    """A job on one node, before it gets its GPUs."""

    job: int  # index in the jobs of the timeline
    node: str
    gpus: int
    start: datetime
    end: datetime
    planned: bool = False
    fixed: list[int] = field(default_factory=list)  # its physical GPUs, if a snapshot saw them


class Slots:
    """The GPUs of a node and when they are taken."""

    def __init__(self, gpus: int):
        self.taken = [[] for _ in range(gpus)]  # sorted (start, end) per GPU

    def free(self, gpu: int, start: datetime, end: datetime) -> bool:
        taken = self.taken[gpu]
        i = bisect(taken, (start,))
        return (not i or taken[i - 1][1] <= start) and (i == len(taken) or taken[i][0] >= end)

    def place(self, piece: Piece) -> list[int]:
        """The GPUs a snapshot saw, otherwise the lowest that are free; accounting has no index."""
        gpus = [g for g in piece.fixed if g < len(self.taken)] or [
            g for g in range(len(self.taken)) if self.free(g, piece.start, piece.end)
        ][: piece.gpus]
        for gpu in gpus:
            insort(self.taken[gpu], (piece.start, piece.end))
        return gpus


class Timeline:
    """The jobs of the GPU nodes in a period, as the snapshot at its end saw them."""

    def __init__(self, scope: Scope, at: datetime | None = None, ahead: timedelta = timedelta()):
        self.scope, session = scope, scope.session
        until = min(at.astimezone(UTC) if at else scope.end, scope.end)
        query = select(Snapshot).where(Snapshot.status == "ok", Snapshot.taken_at <= until)
        self.snapshot = session.scalars(query.order_by(Snapshot.id.desc()).limit(1)).first()
        self.at = self.snapshot.taken_at if self.snapshot else until
        self.snapshot_id = self.snapshot and self.snapshot.id
        history = session.scalar(select(JobRecord.start_time).order_by(JobRecord.start_time))
        self.start, self.end = max(scope.start, history or self.at), self.at + ahead
        self.nodes = gpu_nodes(nodes(session))
        self.index, self.jobs = {}, []

    def job(self, job_id: int, user: str, account: str) -> int:
        """The index of a job in the list the bars refer to."""
        if job_id not in self.index:
            self.index[job_id] = len(self.jobs)
            self.jobs.append((job_id, self.scope.user(user), self.scope.account(account)))
        return self.index[job_id]

    def queued(self, *where):
        """GPU jobs of the snapshot, with the job they belong to."""
        query = (
            select(JobSnapshot, Job)
            .join(Job)
            .where(JobSnapshot.snapshot_id == self.snapshot_id, Job.req_gpus > 0, *where)
        )
        return self.scope.session.execute(query).all()

    def pieces(self) -> list[Piece]:
        names = {node.name for node in self.nodes}
        running = {s.job_id: (s, job) for s, job in self.queued(JobSnapshot.state == "RUNNING")}
        pieces = []
        # what accounting knows; jobs running at the snapshot last until it expects them to end
        allocation = and_(
            JobAllocation.job_id == JobRecord.job_id, JobAllocation.node == JobRecordNode.node
        )
        record = (
            JobRecord.job_id, JobRecord.user_name, JobRecord.account, JobRecord.start_time,
            JobRecord.end_time, JobRecord.time_limit_min, JobRecord.gpus, JobRecord.node_count,
        )  # fmt: skip
        query = (
            select(*record, JobRecordNode.node, JobAllocation.gpu_idx)
            .select_from(JobRecord)
            .join(JobRecordNode)
            .outerjoin(JobAllocation, allocation)
            .where(JobRecord.gpus > 0, COUNTED, JobRecordNode.node.in_(names))
            .where(JobRecord.start_time < self.at)
            .where(or_(JobRecord.end_time.is_(None), JobRecord.end_time > self.start))
        )
        for record in self.scope.session.execute(query):
            end = record.end_time
            if not end or end > self.at:
                limit = timedelta(minutes=record.time_limit_min or 0)
                queued = running.get(record.job_id)
                end = queued[0].end_time if queued else max(record.start_time + limit, self.at)
            job = self.job(record.job_id, record.user_name, record.account)
            gpus = max(1, record.gpus // max(1, record.node_count))
            fixed = record.gpu_idx or []
            pieces.append(Piece(job, record.node, gpus, record.start_time, end, fixed=fixed))
        # running jobs that accounting does not have yet
        seen = {self.jobs[piece.job][0] for piece in pieces}
        query = select(JobAllocation).where(
            JobAllocation.job_id.in_(set(running) - seen), JobAllocation.node.in_(names)
        )
        for allocation in self.scope.session.scalars(query):
            queued, job = running[allocation.job_id]
            index = self.job(job.job_id, job.user_name, job.account)
            pieces.append(Piece(index, allocation.node, len(allocation.gpu_idx), queued.start_time,
                                queued.end_time, fixed=allocation.gpu_idx))  # fmt: skip
        # pending jobs where and when the backfill scheduler plans to start them
        planned = JobSnapshot.state == "PENDING", JobSnapshot.start_time < self.end
        for queued, job in self.queued(*planned):
            hosts = [host for host in hostlist(queued.scheduled_nodes) if host in names]
            if not hosts or not job.time_limit_min:
                continue
            end = queued.start_time + timedelta(minutes=job.time_limit_min)
            index = self.job(job.job_id, job.user_name, job.account)
            gpus = max(1, job.req_gpus // len(hosts))
            pieces += [Piece(index, host, gpus, queued.start_time, end, True) for host in hosts]
        return pieces

    def ms(self, time: datetime) -> int:
        """Milliseconds since 1970, within the period."""
        return int(max(self.start, min(time, self.end)).timestamp() * 1000)

    def bars(self) -> list[tuple[int, int, int, int, int]]:
        slots = {node.name: Slots(node.gpus) for node in self.nodes}
        first = dict(zip(slots, accumulate((n.gpus for n in self.nodes), initial=0), strict=False))
        bars = []
        # the GPUs a snapshot saw first, the others fill the gaps in the order they started
        for piece in sorted(self.pieces(), key=lambda p: (not p.fixed, p.start)):
            if piece.planned:
                parts = [(piece.start, piece.end, PLANNED)]
            else:
                parts = [(piece.start, min(piece.end, self.at), RAN),
                         (max(piece.start, self.at), piece.end, RUNNING)]  # fmt: skip
            for gpu in slots[piece.node].place(piece):
                bars += [
                    (piece.job, first[piece.node] + gpu, self.ms(start), self.ms(end), kind)
                    for start, end, kind in parts
                    if self.ms(start) < self.ms(end)
                ]
        return bars

    def gantt(self) -> Gantt:
        bars = self.bars()
        period = Snapshot.taken_at.between(self.scope.start, self.scope.end)
        query = select(Snapshot.taken_at).where(Snapshot.status == "ok", period)
        snapshots = list(self.scope.session.scalars(query.order_by(Snapshot.id)))
        query = select(NodeSnapshot).where(NodeSnapshot.snapshot_id == self.snapshot_id)
        states = {node.node: state(node.state) for node in self.scope.session.scalars(query)}
        gpu_nodes = [
            GpuNode(n.name, n.model, n.gpus, n.partitions, states.get(n.name)) for n in self.nodes
        ]
        # the users and accounts with the most GPU time in the period get an own color
        colors = {}
        for key, name in ((1, "user"), (2, "account")):
            used = Counter()
            for job, _, start, end, _ in bars:
                used[self.jobs[job][key]] += end - start
            colors[name] = dict(zip((n for n, _ in used.most_common()), PALETTE, strict=False))
        return Gantt(self.at, self.start, self.end, snapshots, gpu_nodes, self.jobs, bars, colors)

    def details(self, job_id: int) -> Details:
        """What a job asked for, what the scheduler thought at the snapshot and how it ran."""
        session = self.scope.session
        job = session.get(Job, job_id)
        query = select(JobRecord).where(JobRecord.job_id == job_id)
        record = session.scalars(query.order_by(JobRecord.start_time.desc().nulls_last())).first()
        if not job and not record:
            raise HTTPException(404, f"job {job_id} is unknown")
        queued = self.snapshot and session.get(JobSnapshot, (self.snapshot_id, job_id))
        sections = [self.request(job or record, job)]
        if queued:
            sections.append(self.scheduled(queued))
        if record:
            sections.append(self.run(record))
        return Details(f"Job {job_id}", sections)

    def request(self, known: Job | JobRecord, job: Job | None) -> Section:
        """From the queue if a snapshot saw the job, otherwise from accounting."""
        tres = known.tres_req or {}
        model = job.req_gpu_model if job else known.gpu_model
        gpus = tres.get("gres/gpu")
        array = known.array_task_id is not None and f"{known.array_job_id}_{known.array_task_id}"
        limit = known.time_limit_min and duration(known.time_limit_min * 60)
        return Section("Request", [
            ("User", self.scope.user(known.user_name)),
            ("Account", self.scope.account(known.account)),
            ("Partition", known.partition),
            ("QOS", known.qos),
            ("GPUs", f"{gpus} × {model}" if gpus and model else gpus),
            ("CPUs", tres.get("cpu")),
            ("Memory", f"{tres['mem'] / 1024:.0f} GB" if "mem" in tres else None),
            ("Time limit", limit),
            ("Features", known.constraints),
            ("Submitted", known.submit_time),
            ("Depends on", job and job.dependency),
            ("Array task", array or None),
        ])  # fmt: skip

    def scheduled(self, queued: JobSnapshot) -> Section:
        running = queued.state == "RUNNING"
        return Section(f"Scheduler at {self.scope.local(self.at):%d %b %H:%M}", [
            ("State", label(queued.state)),
            ("Reason", None if running else queued.reason),
            ("Priority", queued.priority),
            ("Eligible since", queued.eligible_time),
            ("Started" if running else "Planned start", queued.start_time),
            ("Expected end", queued.end_time),
            ("Nodes", queued.nodes if running else queued.scheduled_nodes),
            ("Tasks waiting", queued.array_tasks if queued.array_tasks > 1 else None),
        ])  # fmt: skip

    def run(self, record: JobRecord) -> Section:
        """What accounting knows about the run, so far if it still runs."""
        limit = (record.time_limit_min or 0) * 60
        query = select(JobRecordNode.node).where(JobRecordNode.sluid == record.sluid)
        used = limit and f"{100 * record.elapsed_s / limit:.0f} % of {duration(limit)}"
        return Section("Run", [
            ("State", label(record.state)),
            ("Started", record.start_time),
            ("Ended", record.end_time),
            ("Waited", duration(record.wait_s) if record.wait_s is not None else None),
            ("Runtime", duration(record.elapsed_s)),
            ("Time limit used", used or None),
            ("Started by", STARTED.get(record.started_on)),
            ("Nodes", ", ".join(self.scope.session.scalars(query))),
            ("GPUs", record.gpus),
            ("Exit code", record.exit_code),
        ])  # fmt: skip
