"""Database schema. Times are UTC, memory is in MB, time limits in minutes, durations in seconds."""

from datetime import datetime
from typing import Any

from sqlalchemy import ARRAY, BigInteger, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {
        int: BigInteger,
        datetime: DateTime(timezone=True),
        dict: JSONB,
        Any: JSONB,
        list[int]: ARRAY(Integer),
    }


class Snapshot(Base):
    """One collector run; the live state below refers to it."""

    __tablename__ = "snapshot"
    id: Mapped[int] = mapped_column(primary_key=True)
    taken_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(default="running")  # running, ok, partial or failed
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
