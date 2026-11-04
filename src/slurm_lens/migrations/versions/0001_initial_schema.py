"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-04 23:51:24.389853
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "config_version",
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("kind", "key", "valid_from"),
    )
    op.create_index(
        "config_version_open",
        "config_version",
        ["kind", "key"],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL"),
    )
    op.create_table(
        "history_window",
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("items", sa.BigInteger(), nullable=False),
        sa.Column("complete", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("start_time"),
    )
    op.create_table(
        "job",
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("user_name", sa.String(), nullable=False),
        sa.Column("account", sa.String(), nullable=False),
        sa.Column("partition", sa.String(), nullable=False),
        sa.Column("qos", sa.String(), nullable=False),
        sa.Column("submit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_limit_min", sa.BigInteger(), nullable=True),
        sa.Column("tres_req", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("req_gpus", sa.BigInteger(), nullable=True),
        sa.Column("req_gpu_model", sa.String(), nullable=True),
        sa.Column("constraints", sa.String(), nullable=True),
        sa.Column("dependency", sa.String(), nullable=True),
        sa.Column("array_job_id", sa.BigInteger(), nullable=True),
        sa.Column("array_task_id", sa.BigInteger(), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_table(
        "job_record",
        sa.Column("sluid", sa.String(), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("array_job_id", sa.BigInteger(), nullable=True),
        sa.Column("array_task_id", sa.BigInteger(), nullable=True),
        sa.Column("user_name", sa.String(), nullable=False),
        sa.Column("account", sa.String(), nullable=False),
        sa.Column("partition", sa.String(), nullable=False),
        sa.Column("qos", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("exit_code", sa.BigInteger(), nullable=True),
        sa.Column("submit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eligible_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("elapsed_s", sa.BigInteger(), nullable=False),
        sa.Column("wait_s", sa.BigInteger(), nullable=True),
        sa.Column("suspended_s", sa.BigInteger(), nullable=False),
        sa.Column("time_limit_min", sa.BigInteger(), nullable=True),
        sa.Column("priority", sa.BigInteger(), nullable=True),
        sa.Column("node_count", sa.BigInteger(), nullable=False),
        sa.Column("cpus", sa.BigInteger(), nullable=True),
        sa.Column("memory_mb", sa.BigInteger(), nullable=True),
        sa.Column("gpus", sa.BigInteger(), nullable=True),
        sa.Column("gpu_model", sa.String(), nullable=True),
        sa.Column("billing", sa.BigInteger(), nullable=True),
        sa.Column("tres_req", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tres_alloc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("constraints", sa.String(), nullable=True),
        sa.Column("started_on", sa.String(), nullable=True),
        sa.Column("flags", sa.String(), nullable=True),
        sa.Column("restart_cnt", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("sluid"),
    )
    op.create_index(op.f("ix_job_record_job_id"), "job_record", ["job_id"], unique=False)
    op.create_index(op.f("ix_job_record_start_time"), "job_record", ["start_time"], unique=False)
    op.create_table(
        "snapshot",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("diag", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "api_call",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.BigInteger(), nullable=True),
        sa.Column("seconds", sa.Double(), nullable=False),
        sa.Column("items", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["snapshot.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_api_call_snapshot_id"), "api_call", ["snapshot_id"], unique=False)
    op.create_table(
        "fairshare_snapshot",
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("assoc_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("parent", sa.String(), nullable=True),
        sa.Column("shares", sa.BigInteger(), nullable=True),
        sa.Column("shares_normalized", sa.Double(), nullable=True),
        sa.Column("usage_raw", sa.BigInteger(), nullable=False),
        sa.Column("effective_usage", sa.Double(), nullable=True),
        sa.Column("fairshare_factor", sa.Double(), nullable=True),
        sa.Column("fairshare_level", sa.Double(), nullable=True),
        sa.Column("tres_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["snapshot.id"],
        ),
        sa.PrimaryKeyConstraint("snapshot_id", "assoc_id"),
    )
    op.create_table(
        "job_allocation",
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("node", sa.String(), nullable=False),
        sa.Column("cpus", sa.BigInteger(), nullable=False),
        sa.Column("memory_mb", sa.BigInteger(), nullable=False),
        sa.Column("gpu_model", sa.String(), nullable=True),
        sa.Column("gpu_idx", sa.ARRAY(sa.Integer()), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job.job_id"],
        ),
        sa.PrimaryKeyConstraint("job_id", "node"),
    )
    op.create_table(
        "job_record_node",
        sa.Column("sluid", sa.String(), nullable=False),
        sa.Column("node", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["sluid"],
            ["job_record.sluid"],
        ),
        sa.PrimaryKeyConstraint("sluid", "node"),
    )
    op.create_index(op.f("ix_job_record_node_node"), "job_record_node", ["node"], unique=False)
    op.create_table(
        "job_snapshot",
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("priority", sa.BigInteger(), nullable=True),
        sa.Column("partition_priority", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("eligible_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accrue_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nodes", sa.String(), nullable=True),
        sa.Column("scheduled_nodes", sa.String(), nullable=True),
        sa.Column("array_tasks", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job.job_id"],
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["snapshot.id"],
        ),
        sa.PrimaryKeyConstraint("snapshot_id", "job_id"),
    )
    op.create_index(op.f("ix_job_snapshot_job_id"), "job_snapshot", ["job_id"], unique=False)
    op.create_table(
        "node_snapshot",
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("node", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("alloc_cpus", sa.BigInteger(), nullable=False),
        sa.Column("alloc_memory_mb", sa.BigInteger(), nullable=False),
        sa.Column("free_memory_mb", sa.BigInteger(), nullable=True),
        sa.Column("cpu_load", sa.BigInteger(), nullable=True),
        sa.Column("gpus_used", sa.BigInteger(), nullable=False),
        sa.Column("gpu_idx_used", sa.ARRAY(sa.Integer()), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["snapshot.id"],
        ),
        sa.PrimaryKeyConstraint("snapshot_id", "node"),
    )


def downgrade() -> None:
    op.drop_table("node_snapshot")
    op.drop_index(op.f("ix_job_snapshot_job_id"), table_name="job_snapshot")
    op.drop_table("job_snapshot")
    op.drop_index(op.f("ix_job_record_node_node"), table_name="job_record_node")
    op.drop_table("job_record_node")
    op.drop_table("job_allocation")
    op.drop_table("fairshare_snapshot")
    op.drop_index(op.f("ix_api_call_snapshot_id"), table_name="api_call")
    op.drop_table("api_call")
    op.drop_table("snapshot")
    op.drop_index(op.f("ix_job_record_start_time"), table_name="job_record")
    op.drop_index(op.f("ix_job_record_job_id"), table_name="job_record")
    op.drop_table("job_record")
    op.drop_table("job")
    op.drop_table("history_window")
    op.drop_index(
        "config_version_open",
        table_name="config_version",
        postgresql_where=sa.text("valid_to IS NULL"),
    )
    op.drop_table("config_version")
