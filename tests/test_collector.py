from datetime import UTC, datetime, timedelta

import httpx
import pytest
from conftest import payload
from sqlalchemy import func, select

from slurm_lens.collector import Collector, history_windows
from slurm_lens.config import Config
from slurm_lens.models import (
    ApiCall,
    ConfigVersion,
    FairshareSnapshot,
    HistoryWindow,
    JobAllocation,
    JobRecord,
    JobSnapshot,
    NodeSnapshot,
    Snapshot,
)
from slurm_lens.slurm import PATHS

NOW = datetime(2026, 11, 5, 10, 0, tzinfo=UTC)
HOUR = timedelta(hours=1)


def history_windows_at(now, complete=(), backfill=2):
    start = datetime(2026, 11, 4, tzinfo=UTC)
    return history_windows(start, now, 4 * HOUR, set(complete), backfill)


def test_history_windows_fetch_recent_ones_and_backfill_the_oldest_first():
    windows = history_windows_at(NOW)
    # 4.11. 00:00 and 04:00 are the oldest missing windows, 5.11. 08:00 is still running
    assert [(w.day, w.hour) for w in windows] == [(4, 0), (4, 4), (5, 8)]


def test_complete_windows_are_never_fetched_again():
    day = datetime(2026, 11, 4, tzinfo=UTC)
    complete = [day + 4 * HOUR * i for i in range(6)]
    assert [(w.day, w.hour) for w in history_windows_at(NOW, complete)] == [(5, 0), (5, 4), (5, 8)]


def config(**changes):
    values = dict(
        slurm_url="https://slurm.test",
        token_file=None,
        pause=0,
        database_url="",
        interval=timedelta(minutes=5),
        fairshare_interval=HOUR,
        history_start=NOW - timedelta(days=1),
        window=4 * HOUR,
        max_backfill_windows=2,
    )
    return Config(**(values | changes))


ROUTES = {path: name for name, path in PATHS.items()}


def slurm_api(failing=(), status=502):
    def handler(request):
        name = ROUTES[request.url.path]
        if name in failing and status is None:
            raise httpx.ConnectError("name not known")
        if name in failing:
            return httpx.Response(status, text="Bad Gateway")
        return httpx.Response(200, json=payload(name))

    return httpx.MockTransport(handler)


@pytest.fixture
def collect(store, session, monkeypatch):
    monkeypatch.setenv("SLURM_JWT", "token")

    def run(now=NOW, **api):
        Collector(config(), store, transport=slurm_api(**api)).run(now)
        session.expire_all()

    return run


def count(session, model, *where):
    return session.scalar(select(func.count()).select_from(model).where(*where))


def test_run_stores_queue_nodes_configuration_fairshare_and_history(collect, session):
    collect()
    snapshot = session.scalars(select(Snapshot)).one()
    assert (snapshot.status, snapshot.error) == ("ok", None)
    assert snapshot.diag["jobs_running"] >= 0
    assert count(session, JobSnapshot) == len(payload("jobs")["jobs"])
    assert count(session, JobAllocation) >= 1
    assert count(session, NodeSnapshot) == len(payload("nodes")["nodes"])
    assert count(session, FairshareSnapshot) == len(payload("shares")["shares"]["shares"])
    kinds = set(session.scalars(select(ConfigVersion.kind).distinct()))
    assert kinds == {"slurm_conf", "node", "partition", "reservation", "qos", "tres", "association"}
    assert count(session, JobRecord) == len(payload("history")["jobs"])
    assert count(session, HistoryWindow) == 2 + 1  # backfill limit plus the running window


def test_second_run_adds_a_snapshot_but_no_new_versions(collect, session):
    collect()
    versions = count(session, ConfigVersion)
    collect(NOW + timedelta(minutes=5))
    assert count(session, Snapshot) == 2
    assert count(session, JobSnapshot) == 2 * len(payload("jobs")["jobs"])
    assert count(session, ConfigVersion) == versions
    assert count(session, FairshareSnapshot) == len(payload("shares")["shares"]["shares"])  # hourly


def test_a_failing_endpoint_does_not_stop_the_run(collect, session):
    collect(failing={"nodes"})
    snapshot = session.scalars(select(Snapshot)).one()
    assert snapshot.status == "partial" and "nodes" in snapshot.error
    assert count(session, NodeSnapshot) == 0
    assert count(session, JobSnapshot) > 0
    assert count(session, ApiCall, ApiCall.status == 502) == 1


def test_a_rejected_token_fails_the_run(collect, session):
    collect(failing=set(PATHS), status=401)
    snapshot = session.scalars(select(Snapshot)).one()
    assert snapshot.status == "failed" and "token" in snapshot.error


def test_an_unreachable_api_stops_the_run_early(collect, session):
    collect(failing=set(PATHS), status=None)
    snapshot = session.scalars(select(Snapshot)).one()
    assert snapshot.status == "failed" and "no answer" in snapshot.error
    assert count(session, ApiCall) == 0  # nothing was answered, the run stopped at the first step
