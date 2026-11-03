import json
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from slurm_lens.models import Base
from slurm_lens.store import Store

DATA = Path(__file__).with_name("data")
URL = make_url(
    os.environ.get(
        "SLURM_LENS_TEST_DATABASE",
        "postgresql+psycopg://slurm_lens:slurm_lens@localhost:5432/slurm_lens_test",
    )
)


def payload(name: str) -> dict:
    """A synthetic slurmrestd response from tests/data."""
    return json.loads((DATA / f"{name}.json").read_text())


@pytest.fixture(scope="session")
def store():
    # a fresh database per test run, so every run starts empty
    admin = create_engine(URL.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{URL.database}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{URL.database}"'))
    admin.dispose()
    store = Store(URL)
    store.create()
    yield store
    store.engine.dispose()


@pytest.fixture
def session(store):
    with store.session() as session:
        yield session
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with store.engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} CASCADE"))
