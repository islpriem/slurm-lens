from datetime import UTC, datetime

from sqlalchemy import select

from slurm_lens.models import Snapshot

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
