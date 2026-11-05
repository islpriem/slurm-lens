from datetime import UTC, datetime, timedelta

import pytest
from click.testing import CliRunner
from conftest import URL
from test_collector import config, slurm_api

from slurm_lens.cli import main
from slurm_lens.collector import Collector


@pytest.fixture
def ini(tmp_path):
    path = tmp_path / "slurm-lens.ini"
    start = (datetime.now(UTC) - timedelta(days=1)).date()
    path.write_text(f"""
[slurm]
url = https://slurm.test

[database]
url = {URL.render_as_string(hide_password=False)}

[collector]

[history]
start = {start}
""")
    return path


def status(ini):
    return CliRunner().invoke(main, ["--config", str(ini), "status"])


def test_status_fails_without_snapshots(ini, session):
    result = status(ini)
    assert result.exit_code == 1 and "no snapshot" in result.output


def test_status_after_a_run(ini, store, session, monkeypatch):
    monkeypatch.setenv("SLURM_JWT", "token")
    Collector(config(history_start=datetime.now(UTC) - timedelta(days=1)), store, slurm_api()).run()
    result = status(ini)
    assert result.exit_code == 0, result.output
    assert "last snapshot" in result.output and "ok" in result.output
    assert "history windows" in result.output
