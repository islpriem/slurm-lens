import re

from fastapi.testclient import TestClient
from test_collector import NOW, config, slurm_api

from slurm_lens.api import MODULES, create_app
from slurm_lens.collector import Collector


def client(store) -> TestClient:
    return TestClient(create_app(config(), store))


def collected(store, monkeypatch) -> TestClient:
    monkeypatch.setenv("SLURM_JWT", "token")
    Collector(config(), store, transport=slurm_api()).run(NOW)
    return client(store)


def test_health_without_data(store, session):
    api = client(store)
    assert api.get("/api/health").json()["tiles"][0]["value"] == "unhealthy"
    status = api.get("/api/health/status").json()
    assert status["synced_at"] is None and not status["healthy"]


def test_statistics_need_a_history(store, session):
    assert client(store).get("/api/gpus").status_code == 404


def test_every_module_after_a_run(store, session, monkeypatch):
    api = collected(store, monkeypatch)
    for module in MODULES:
        view = api.get(f"/api/{module}").json()
        charts = [p for p in view["panels"] if p["kind"] not in ("pie", "table")]
        assert view["tiles"] and charts, module
        assert all(len(s["y"]) == len(c["x"]) for c in charts for s in c["series"]), module


def test_pseudonyms(store, session, monkeypatch):
    api = collected(store, monkeypatch)
    names = {}
    for pseudonyms in (True, False):
        view = api.get("/api/queue", params={"pseudonyms": pseudonyms}).json()
        [users] = [p for p in view["panels"] if p["title"] == "Users with pending jobs now"]
        names[pseudonyms] = [row[0] for row in users["rows"]]
    assert names[True] and all(re.fullmatch(r"U\d+", name) for name in names[True])
    assert names[False] and not set(names[False]) & set(names[True])


def test_time_zone(store, session, monkeypatch):
    api = collected(store, monkeypatch)
    assert api.get("/api/queue", params={"zone": "Europe/Berlin"}).status_code == 200
    assert api.get("/api/queue", params={"zone": "Mars/Base"}).status_code == 422


def test_period(store, session, monkeypatch):
    api = collected(store, monkeypatch)
    later = {"start": NOW.isoformat()}
    assert api.get("/api/jobs", params=later).status_code == 404
    hours = api.get("/api/gpus").json()["panels"][0]["x"]
    assert hours and all(hour.endswith(":00:00Z") for hour in hours)
