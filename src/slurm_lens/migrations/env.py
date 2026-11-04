"""Alembic environment; the connection comes from slurm_lens.store.alembic_config()."""

from alembic import context

from slurm_lens.models import Base

context.configure(connection=context.config.attributes["connection"], target_metadata=Base.metadata)
with context.begin_transaction():
    context.run_migrations()
