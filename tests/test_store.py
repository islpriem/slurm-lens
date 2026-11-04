from datetime import UTC, datetime, timedelta

from alembic import command
from sqlalchemy import select

from slurm_lens.models import ConfigVersion, HistoryWindow
from slurm_lens.store import alembic_config

T0 = datetime(2026, 11, 1, tzinfo=UTC)


def test_migrations_match_the_models(store):
    with store.engine.connect() as connection:
        command.check(alembic_config(connection))  # raises if a migration is missing


WINDOW = {"start_time": T0, "end_time": T0 + timedelta(hours=4), "fetched_at": T0, "items": 1}


def test_upsert_updates_the_given_columns(session):
    update = ["fetched_at", "items", "complete"]
    HistoryWindow.upsert(session, [{**WINDOW, "complete": False}], update)
    HistoryWindow.upsert(session, [{**WINDOW, "items": 5, "complete": True}], update)
    window = session.scalars(select(HistoryWindow)).one()
    assert (window.items, window.complete) == (5, True)


def test_upsert_without_update_keeps_the_first_row(session):
    HistoryWindow.upsert(session, [{**WINDOW, "complete": False}])
    HistoryWindow.upsert(session, [{**WINDOW, "items": 5, "complete": True}])
    assert session.scalars(select(HistoryWindow.items)).one() == 1


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
