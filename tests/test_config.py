from datetime import UTC, datetime, timedelta

import pytest

from slurm_lens.config import Config

INI = """
[slurm]
url = https://slurm.example.org
token_file = {token}
pause_seconds = 0.5

[database]
url = postgresql+psycopg://lens@db:5432/lens  ; password comes from the environment

[collector]
interval_minutes = 5
fairshare_minutes = 60

[history]
start = 2026-10-01
window_hours = 4
max_backfill_windows = 6
"""


@pytest.fixture
def config(tmp_path):
    token = tmp_path / "token"
    token.write_text("secret\n")
    path = tmp_path / "slurm-lens.ini"
    path.write_text(INI.format(token=token))
    return Config.load(path)


def test_load(config):
    assert config.slurm_url == "https://slurm.example.org"
    assert config.pause == 0.5
    assert config.interval == timedelta(minutes=5)
    assert config.fairshare_interval == timedelta(hours=1)
    assert config.history_start == datetime(2026, 10, 1, tzinfo=UTC)
    assert config.window == timedelta(hours=4)
    assert config.max_backfill_windows == 6


def test_token_is_read_from_the_file_each_time(config):
    assert config.token() == "secret"
    config.token_file.write_text("rotated")
    assert config.token() == "rotated"


def test_token_from_environment_without_token_file(tmp_path, monkeypatch):
    path = tmp_path / "slurm-lens.ini"
    path.write_text(INI.replace("token_file = {token}\n", ""))
    monkeypatch.setenv("SLURM_JWT", "from-env")
    assert Config.load(path).token() == "from-env"


def test_database_password_from_environment(config, monkeypatch):
    monkeypatch.setenv("SLURM_LENS_DB_PASSWORD", "pw")
    assert config.database().password == "pw"
    assert config.database().host == "db"


def test_database_url_can_be_overridden(config, monkeypatch):
    monkeypatch.setenv("SLURM_LENS_DATABASE_URL", "postgresql+psycopg://lens@localhost/lens")
    assert config.database().host == "localhost"
