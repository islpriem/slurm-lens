from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from slurm_lens.models import ConfigVersion, Snapshot

T0 = datetime(2026, 11, 1, tzinfo=UTC)


ROW = {"id": 1, "taken_at": T0}


def test_upsert_updates_the_given_columns(session):
    Snapshot.upsert(session, [{**ROW, "status": "running"}], ["status"])
    Snapshot.upsert(session, [{**ROW, "status": "ok"}], ["status"])
    assert session.scalars(select(Snapshot.status)).one() == "ok"


def test_upsert_without_update_keeps_the_first_row(session):
    Snapshot.upsert(session, [{**ROW, "status": "running"}])
    Snapshot.upsert(session, [{**ROW, "status": "ok"}])
    assert session.scalars(select(Snapshot.status)).one() == "running"


def test_config_versions_change_only_when_values_change(session):
    assert (
        ConfigVersion.record(
            session, "qos", {"normal": {"priority": 100}, "high": {"priority": 200}}, T0
        )
        == 2
    )
    later = T0 + timedelta(hours=1)
    assert (
        ConfigVersion.record(
            session, "qos", {"normal": {"priority": 100}, "high": {"priority": 200}}, later
        )
        == 0
    )
    latest = T0 + timedelta(hours=2)
    assert ConfigVersion.record(session, "qos", {"normal": {"priority": 150}}, latest) == 2

    assert ConfigVersion.at(session, "qos", later) == {
        "normal": {"priority": 100},
        "high": {"priority": 200},
    }
    assert ConfigVersion.at(session, "qos", latest) == {"normal": {"priority": 150}}
    assert ConfigVersion.at(session, "qos", T0 - timedelta(seconds=1)) == {}


def test_config_versions_keep_scalars(session):
    ConfigVersion.record(
        session, "slurm_conf", {"PriorityWeightAge": 10000, "SchedulerType": "backfill"}, T0
    )
    assert ConfigVersion.at(session, "slurm_conf", T0)["PriorityWeightAge"] == 10000
