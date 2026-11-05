"""Database schema. Times are UTC, memory is in MB, time limits in minutes, durations in seconds."""

from datetime import datetime
from typing import Any

from sqlalchemy import ARRAY, BigInteger, DateTime, ForeignKey, Index, Integer, or_, select, text
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

REMOVED = object()


class Base(DeclarativeBase):
    type_annotation_map = {
        int: BigInteger,
        datetime: DateTime(timezone=True),
        dict: JSONB,
        Any: JSONB,
        list[int]: ARRAY(Integer),
    }

    @classmethod
    def upsert(cls, session: Session, rows: list[dict], update=()) -> None:
        """Bulk insert; on a key conflict update the given columns or keep the existing row."""
        if not rows:
            return
        statement = insert(cls)
        keys = [column.name for column in cls.__table__.primary_key]
        if update:
            changes = {column: statement.excluded[column] for column in update}
            statement = statement.on_conflict_do_update(index_elements=keys, set_=changes)
        else:
            statement = statement.on_conflict_do_nothing(index_elements=keys)
        session.execute(statement, rows)

    @classmethod
    def columns(cls, *exclude: str) -> list[str]:
        """Names of the non-key columns, e.g. for upsert()."""
        return [
            c.name for c in cls.__table__.columns if not c.primary_key and c.name not in exclude
        ]


class Snapshot(Base):
    """One collector run; the live state below refers to it."""

    __tablename__ = "snapshot"
    id: Mapped[int] = mapped_column(primary_key=True)
    taken_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(default="running")  # running, ok, partial, failed, aborted
    error: Mapped[str | None]
    diag: Mapped[dict | None]  # sdiag statistics


class ApiCall(Base):
    """Every request to slurmrestd, to see what was fetched and what failed."""

    __tablename__ = "api_call"
    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshot.id"), index=True)
    path: Mapped[str]
    params: Mapped[dict]
    status: Mapped[int | None]  # None if no response arrived
    seconds: Mapped[float]
    items: Mapped[int | None]
    error: Mapped[str | None]


class ConfigVersion(Base):
    """Slowly changing configuration (slurm.conf, partitions, nodes, QOS, ...) with validity."""

    __tablename__ = "config_version"
    kind: Mapped[str] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(primary_key=True)
    valid_from: Mapped[datetime] = mapped_column(primary_key=True)
    valid_to: Mapped[datetime | None]
    value: Mapped[Any]
    __table_args__ = (
        Index(
            "config_version_open",
            "kind",
            "key",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    @classmethod
    def record(cls, session: Session, kind: str, values: dict[str, Any], now: datetime) -> int:
        """Close changed or removed keys, open new versions; returns the number of changed keys."""
        query = select(cls).where(cls.kind == kind, cls.valid_to.is_(None))
        current = {version.key: version for version in session.scalars(query)}
        changed = [v for key, v in current.items() if values.get(key, REMOVED) != v.value]
        for version in changed:
            version.valid_to = now
        session.flush()  # close first, only one open version per key is allowed
        opened = [key for key in values if key not in current or current[key] in changed]
        session.add_all(
            cls(kind=kind, key=key, value=values[key], valid_from=now) for key in opened
        )
        return len({v.key for v in changed} | set(opened))

    @classmethod
    def at(cls, session: Session, kind: str, time: datetime) -> dict[str, Any]:
        """The configuration of one kind as it was at the given time."""
        valid = or_(cls.valid_to.is_(None), cls.valid_to > time)
        query = select(cls).where(cls.kind == kind, cls.valid_from <= time, valid)
        return {version.key: version.value for version in session.scalars(query)}


class Job(Base):
    """What a job in the live queue asks for; stored once, updated if the request changes."""

    __tablename__ = "job"
    job_id: Mapped[int] = mapped_column(primary_key=True)
    user_name: Mapped[str]
    account: Mapped[str]
    partition: Mapped[str]  # comma separated if submitted to several partitions
    qos: Mapped[str]
    submit_time: Mapped[datetime | None]
    time_limit_min: Mapped[int | None]
    tres_req: Mapped[dict]
    req_gpus: Mapped[int | None]
    req_gpu_model: Mapped[str | None]  # None if any model is fine
    constraints: Mapped[str | None]
    dependency: Mapped[str | None]
    array_job_id: Mapped[int | None]
    array_task_id: Mapped[int | None]
    first_seen: Mapped[datetime]
    raw: Mapped[dict]  # the job as slurmrestd returned it, without personal fields


class JobSnapshot(Base):
    """What changes for a queued job from one snapshot to the next."""

    __tablename__ = "job_snapshot"
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshot.id"), primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job.job_id"), primary_key=True, index=True)
    state: Mapped[str]
    reason: Mapped[str | None]
    priority: Mapped[int | None]
    partition_priority: Mapped[dict | None]  # priority per partition for multi-partition jobs
    eligible_time: Mapped[datetime | None]
    accrue_time: Mapped[datetime | None]
    start_time: Mapped[datetime | None]  # pending: start planned by the backfill scheduler
    end_time: Mapped[datetime | None]  # running: start + time limit
    nodes: Mapped[str | None]
    scheduled_nodes: Mapped[str | None]  # pending: nodes planned by the backfill scheduler
    array_tasks: Mapped[int]  # pending array records stand for several tasks


class JobAllocation(Base):
    """Where a running job runs, including the physical GPUs, which accounting does not keep."""

    __tablename__ = "job_allocation"
    job_id: Mapped[int] = mapped_column(ForeignKey("job.job_id"), primary_key=True)
    node: Mapped[str] = mapped_column(primary_key=True)
    cpus: Mapped[int]
    memory_mb: Mapped[int]
    gpu_model: Mapped[str | None]
    gpu_idx: Mapped[list[int]]
    first_seen: Mapped[datetime]


class NodeSnapshot(Base):
    """State and allocation of a node in one snapshot; the static part is in config_version."""

    __tablename__ = "node_snapshot"
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshot.id"), primary_key=True)
    node: Mapped[str] = mapped_column(primary_key=True)
    state: Mapped[str]
    reason: Mapped[str | None]
    alloc_cpus: Mapped[int]
    alloc_memory_mb: Mapped[int]
    free_memory_mb: Mapped[int | None]
    cpu_load: Mapped[int | None]
    gpus_used: Mapped[int]
    gpu_idx_used: Mapped[list[int]]


class FairshareSnapshot(Base):
    """The fairshare tree (sshare) of one snapshot."""

    __tablename__ = "fairshare_snapshot"
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshot.id"), primary_key=True)
    assoc_id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str]  # USER or ASSOCIATION (account)
    name: Mapped[str]
    parent: Mapped[str | None]
    shares: Mapped[int | None]
    shares_normalized: Mapped[float | None]
    usage_raw: Mapped[int]  # decayed usage
    effective_usage: Mapped[float | None]
    fairshare_factor: Mapped[float | None]
    fairshare_level: Mapped[float | None]
    tres_usage: Mapped[dict]  # decayed usage per TRES, non-zero only


class HistoryWindow(Base):
    """A time window of the accounting history; complete once fetched after it ended."""

    __tablename__ = "history_window"
    start_time: Mapped[datetime] = mapped_column(primary_key=True)
    end_time: Mapped[datetime]
    fetched_at: Mapped[datetime]
    items: Mapped[int]
    complete: Mapped[bool]


class JobRecord(Base):
    """A job from accounting (sacct); a requeued job gets a new record."""

    __tablename__ = "job_record"
    sluid: Mapped[str] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(index=True)
    array_job_id: Mapped[int | None]
    array_task_id: Mapped[int | None]
    user_name: Mapped[str]
    account: Mapped[str]
    partition: Mapped[str]
    qos: Mapped[str]
    state: Mapped[str]
    reason: Mapped[str | None]
    exit_code: Mapped[int | None]
    submit_time: Mapped[datetime | None]
    eligible_time: Mapped[datetime | None]
    start_time: Mapped[datetime | None] = mapped_column(index=True)
    end_time: Mapped[datetime | None]
    elapsed_s: Mapped[int]
    wait_s: Mapped[int | None]  # eligible until start
    suspended_s: Mapped[int]
    time_limit_min: Mapped[int | None]
    priority: Mapped[int | None]
    node_count: Mapped[int]
    cpus: Mapped[int | None]
    memory_mb: Mapped[int | None]
    gpus: Mapped[int | None]
    gpu_model: Mapped[str | None]
    billing: Mapped[int | None]
    tres_req: Mapped[dict]
    tres_alloc: Mapped[dict]
    constraints: Mapped[str | None]
    started_on: Mapped[str | None]  # SCHEDULE (main scheduler), BACKFILL or SUBMIT
    flags: Mapped[str | None]
    restart_cnt: Mapped[int]


class JobRecordNode(Base):
    """Nodes a job from accounting ran on."""

    __tablename__ = "job_record_node"
    sluid: Mapped[str] = mapped_column(ForeignKey("job_record.sluid"), primary_key=True)
    node: Mapped[str] = mapped_column(primary_key=True, index=True)
