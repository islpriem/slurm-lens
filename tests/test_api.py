from fastapi.testclient import TestClient
from test_collector import NOW, config, slurm_api

from slurm_lens.api import create_app
from slurm_lens.collector import Collector


def client(store) -> TestClient:
    return TestClient(create_app(config(), store))


def test_health_without_data(store, session):
    api = client(store)
    assert api.get("/api/health").json()["tiles"][0]["note"] == "no run yet"
    status = api.get("/api/health/status").json()
    assert status["synced_at"] is None and not status["healthy"]


def test_statistics_need_a_history(store, session):
    assert client(store).get("/api/stats").status_code == 404


def test_views_after_a_run(store, session, monkeypatch):
    monkeypatch.setenv("SLURM_JWT", "token")
    Collector(config(), store, transport=slurm_api()).run(NOW)
    api = client(store)
    assert api.get("/api/health/status").json()["synced_at"].startswith("2026-11-05")
    for module in ["health", "stats"]:
        charts = api.get(f"/api/{module}").json()["charts"]
        assert charts and all(len(s["y"]) == len(c["x"]) for c in charts for s in c["series"])
