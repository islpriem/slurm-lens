import re
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from test_collector import NOW, config, slurm_api

from slurm_lens.api import MODULES, create_app
from slurm_lens.api.timeline import PLANNED, RUNNING
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
    for module in MODULES.keys() - {"timeline"}:
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


def test_check_for_monitoring(store, session, monkeypatch):
    api = client(store)
    assert api.get("/api/health/check").status_code == 503
    monkeypatch.setenv("SLURM_JWT", "token")
    Collector(config(), store, transport=slurm_api()).run()
    check = api.get("/api/health/check")
    assert check.status_code == 200 and check.json()["healthy"]


def test_frontend_routes_in_the_browser(store, session, tmp_path):
    (tmp_path / "200.html").write_text("app")
    (tmp_path / "favicon.ico").write_text("icon")
    api = TestClient(create_app(config(), store, tmp_path))
    assert [api.get(path).text for path in ("/", "/gpus", "/favicon.ico")] == ["app", "app", "icon"]
    assert api.get("/api/unknown").status_code == 404


def test_timeline_with_details(store, session, monkeypatch):
    # while the job of the test data runs
    monkeypatch.setenv("SLURM_JWT", "token")
    Collector(config(), store, transport=slurm_api()).run(datetime(2026, 10, 25, 10, tzinfo=UTC))
    api = client(store)
    gantt = api.get("/api/timeline", params={"ahead": 24 * 30}).json()
    rows = sum(node["gpus"] for node in gantt["nodes"])
    # the test data has no accounting before the snapshot, so nothing ran yet
    assert {bar[4] for bar in gantt["bars"]} == {RUNNING, PLANNED}
    assert all(0 <= bar[1] < rows and bar[2] < bar[3] for bar in gantt["bars"])
    job = gantt["jobs"][gantt["bars"][0][0]][0]
    details = api.get(f"/api/timeline/jobs/{job}").json()
    assert details["title"] == f"Job {job}" and details["sections"]
    assert api.get("/api/timeline/jobs/1").status_code == 404
