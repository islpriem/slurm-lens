"""Periodic collection of the live queue and the nodes."""

import logging
from datetime import UTC, datetime

from . import slurm
from .client import SlurmClient
from .config import Config
from .models import (
    ApiCall,
    ConfigVersion,
    Job,
    JobAllocation,
    JobSnapshot,
    NodeSnapshot,
    Snapshot,
)
from .store import Store

log = logging.getLogger(__name__)


class Collector:
    """Collects one snapshot per run; every step has its own transaction and may fail alone."""

    def __init__(self, config: Config, store: Store, transport=None):
        self.config = config
        self.store = store
        self.transport = transport  # tests replace the network here

    def run(self, now: datetime | None = None) -> None:
        self.now = now or datetime.now(UTC)
        with self.store.session.begin() as session:
            snapshot = Snapshot(taken_at=self.now)
            session.add(snapshot)
            session.flush()
            self.snapshot_id = snapshot.id
        steps = [self.queue, self.nodes]
        errors = []
        self.client = self._client()
        for step in steps:
            try:
                step()
            except Exception as error:
                log.exception("step %s failed", step.__name__)
                errors.append(f"{step.__name__}: {error}")
        status = "ok" if not errors else "failed" if len(errors) == len(steps) else "partial"
        with self.store.session.begin() as session:
            snapshot = session.get(Snapshot, self.snapshot_id)
            snapshot.status, snapshot.error = status, "; ".join(dict.fromkeys(errors)) or None
            snapshot.finished_at = datetime.now(UTC)
        log.info("snapshot %s: %s", self.snapshot_id, status)

    def _client(self) -> SlurmClient:
        return SlurmClient(
            self.config.slurm_url,
            self.config.token(),
            slurm.ALLOWED,
            transport=self.transport,
        )

    def fetch(self, name: str, **params) -> dict:
        """GET one endpoint and log the call; raises if no usable answer came back."""
        reply = self.client.get(slurm.PATHS[name], **params)
        items = next((len(v) for v in reply.data.values() if isinstance(v, list | dict)), None)
        with self.store.session.begin() as session:
            session.add(ApiCall(
                snapshot_id=self.snapshot_id, path=slurm.PATHS[name], params=params,
                status=reply.status, seconds=reply.seconds, items=items, error=reply.error,
            ))  # fmt: skip
        if reply.status != 200:
            raise RuntimeError(f"{name} answered {reply.status}: {reply.error}")
        return reply.data

    def queue(self) -> None:
        jobs = self.fetch("jobs")["jobs"]
        statistics = self.fetch("diag")["statistics"]
        rows = [slurm.queue_rows(j, self.snapshot_id, self.now) for j in jobs]
        with self.store.session.begin() as session:
            # the request of a job can change (scontrol update), its first sighting not
            Job.upsert(session, [r.job for r in rows], update=Job.columns("first_seen", "raw"))
            JobSnapshot.upsert(session, [r.snapshot for r in rows])
            JobAllocation.upsert(session, [a for r in rows for a in r.allocations])
            session.get(Snapshot, self.snapshot_id).diag = slurm.diag(statistics)

    def nodes(self) -> None:
        rows = [slurm.node_rows(n, self.snapshot_id) for n in self.fetch("nodes")["nodes"]]
        with self.store.session.begin() as session:
            NodeSnapshot.upsert(session, [state for state, _ in rows])
            static = {state["node"]: config for state, config in rows}
            ConfigVersion.record(session, "node", static, self.now)
