from datetime import UTC, datetime, timedelta

import httpx
import pytest
from conftest import payload
from sqlalchemy import func, select

from slurm_lens.collector import Collector
from slurm_lens.config import Config
from slurm_lens.models import (
    ApiCall,
    ConfigVersion,
    FairshareSnapshot,
    JobAllocation,
    JobSnapshot,
    NodeSnapshot,
    Snapshot,
)
from slurm_lens.slurm import PATHS

NOW = datetime(2026, 11, 5, 10, 0, tzinfo=UTC)
HOUR = timedelta(hours=1)


def config(**changes):
    values = dict(
        slurm_url="https://slurm.test",
        token_file=None,
        database_url="",
        interval=timedelta(minutes=5),
        fairshare_interval=HOUR,
    )
    return Config(**(values | changes))


ROUTES = {path: name for name, path in PATHS.items()}


def slurm_api(failing=(), status=502):
    def handler(request):
        name = ROUTES[request.url.path]
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


def test_run_stores_queue_nodes_configuration_and_fairshare(collect, session):
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
