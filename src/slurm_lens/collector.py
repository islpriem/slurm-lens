"""Periodic collection: live queue, configuration, fairshare and the accounting history."""

import logging
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from . import slurm
from .client import SlurmClient, Unavailable, token_expiry
from .config import Config
from .models import (
    ApiCall,
    ConfigVersion,
    FairshareSnapshot,
    HistoryWindow,
    Job,
    JobAllocation,
    JobRecord,
    JobRecordNode,
    JobSnapshot,
    NodeSnapshot,
    Snapshot,
)
from .parse import num
from .store import Store

log = logging.getLogger(__name__)

# accounting may receive a job's final state a little after the job ended
MARGIN = timedelta(hours=1)


def history_windows(start, now, size, complete, backfill) -> list[datetime]:
    """Window starts to fetch: the oldest incomplete ones (at most `backfill`), then recent ones.

    A window is complete once it was fetched after its end plus MARGIN; recent windows can still
    change and are fetched on every run.
    """
    seconds = size.total_seconds()
    first = datetime.fromtimestamp(start.timestamp() // seconds * seconds, UTC)
    starts = [first + i * size for i in range(int((now - first) / size) + 1)]
    recent = [w for w in starts if w + size + MARGIN > now]
    older = [w for w in starts if w not in complete and w not in recent]
    return older[:backfill] + recent


class Collector:
    """Collects one snapshot per run; every step has its own transaction and may fail alone."""

    def __init__(self, config: Config, store: Store, transport=None):
        self.config = config
        self.store = store
        self.transport = transport  # tests replace the network here

    def abort_unfinished(self) -> None:
        """Mark snapshots of a run that was killed, e.g. by a restart of the container."""
        with self.store.session.begin() as session:
            query = update(Snapshot).where(Snapshot.status == "running")
            session.execute(query.values(status="aborted"))

    def forever(self) -> None:
        while True:
            started = time.monotonic()
            self.run()
            time.sleep(max(0.0, self.config.interval.total_seconds() - time.monotonic() + started))

    def run(self, now: datetime | None = None) -> None:
        self.now = now or datetime.now(UTC)
        with self.store.session.begin() as session:
            snapshot = Snapshot(taken_at=self.now)
            session.add(snapshot)
            session.flush()
            self.snapshot_id = snapshot.id
        steps = [self.queue, self.nodes, self.slurm_config, self.accounting_config, self.fairshare]
        steps.append(self.history)
        errors = []
        try:
            self.client = self._client()
            for step in steps:
                try:
                    step()
                except Unavailable:
                    raise
                except Exception as error:
                    log.exception("step %s failed", step.__name__)
                    errors.append(f"{step.__name__}: {error}")
        except (Unavailable, OSError, KeyError) as error:  # no answer or no usable token
            log.error("run failed: %s", error)
            errors = [str(error)] * len(steps)
        status = "ok" if not errors else "failed" if len(errors) == len(steps) else "partial"
        with self.store.session.begin() as session:
            snapshot = session.get(Snapshot, self.snapshot_id)
            snapshot.status, snapshot.error = status, "; ".join(dict.fromkeys(errors)) or None
            snapshot.finished_at = datetime.now(UTC)
        log.info("snapshot %s: %s", self.snapshot_id, status)

    def _client(self) -> SlurmClient:
        token = self.config.token()
        expiry = token_expiry(token)
        if expiry and expiry - self.now < timedelta(days=1):
            log.warning("the Slurm token expires at %s", expiry)
        return SlurmClient(
            self.config.slurm_url, token, slurm.ALLOWED, self.config.pause, transport=self.transport
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

    def slurm_config(self) -> None:
        conf = {key: num(value) for key, value in self.fetch("conf")["slurm_conf"].items()}
        self._record({"slurm_conf": conf} | self._config_items("partition", "reservation"))

    def accounting_config(self) -> None:
        self._record(self._config_items("qos", "tres", "association"))

    def _config_items(self, *kinds: str) -> dict[str, dict]:
        return {kind: slurm.config_items(kind, self.fetch(slurm.CONFIG[kind][0])) for kind in kinds}

    def _record(self, kinds: dict[str, dict]) -> None:
        # everything is fetched before anything is written, a failed request changes nothing
        with self.store.session.begin() as session:
            for kind, values in kinds.items():
                if changed := ConfigVersion.record(session, kind, values, self.now):
                    log.info("%s: %d changes", kind, changed)

    def fairshare(self) -> None:
        with self.store.session() as session:
            last = session.scalar(
                select(Snapshot.taken_at).where(
                    Snapshot.id == select(func.max(FairshareSnapshot.snapshot_id)).scalar_subquery()
                )
            )
        if last and self.now - last < self.config.fairshare_interval:
            return
        shares = self.fetch("shares")["shares"]["shares"]
        with self.store.session.begin() as session:
            FairshareSnapshot.upsert(
                session, [slurm.share_row(s, self.snapshot_id) for s in shares]
            )

    def history(self) -> None:
        with self.store.session() as session:
            query = select(HistoryWindow.start_time).where(HistoryWindow.complete)
            complete = set(session.scalars(query))
        config = self.config
        starts = history_windows(
            config.history_start, self.now, config.window, complete, config.max_backfill_windows
        )
        for start in starts:
            end = start + config.window
            data = self.fetch(
                "history",
                start_time=int(start.timestamp()),
                end_time=int(end.timestamp()),
                skip_steps="true",
                disable_truncate_usage_time="true",  # otherwise start and end are cut to the window
            )
            rows = [slurm.record_rows(r) for r in data["jobs"]]
            records = {record["sluid"]: record for record, _ in rows}
            window = {
                "start_time": start,
                "end_time": end,
                "fetched_at": self.now,
                "items": len(records),
                "complete": self.now >= end + MARGIN,
            }
            # each window is its own transaction, so an outage only loses the windows after it
            with self.store.session.begin() as session:
                JobRecord.upsert(session, list(records.values()), update=JobRecord.columns())
                JobRecordNode.upsert(session, [n for _, nodes in rows for n in nodes])
                HistoryWindow.upsert(session, [window], update=HistoryWindow.columns())
