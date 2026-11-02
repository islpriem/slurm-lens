from datetime import timedelta

import pytest

from slurm_lens.config import Config

INI = """
[slurm]
url = https://slurm.example.org
token_file = {token}

[database]
url = postgresql+psycopg://lens@db:5432/lens  ; password comes from the environment

[collector]
interval_minutes = 5
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
    assert config.interval == timedelta(minutes=5)


def test_token_is_read_from_the_file_each_time(config):
    assert config.token() == "secret"
    config.token_file.write_text("rotated")
    assert config.token() == "rotated"


def test_token_from_environment_without_token_file(tmp_path, monkeypatch):
    path = tmp_path / "slurm-lens.ini"
    path.write_text(INI.replace("token_file = {token}\n", ""))
    monkeypatch.setenv("SLURM_JWT", "from-env")
    assert Config.load(path).token() == "from-env"
