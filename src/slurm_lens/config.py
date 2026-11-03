"""Settings from the INI file. Secrets come from a file or the environment, never from the INI."""

import os
from configparser import ConfigParser
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from sqlalchemy.engine import URL, make_url


@dataclass(frozen=True)
class Config:
    slurm_url: str
    token_file: Path | None
    database_url: str
    interval: timedelta

    @classmethod
    def load(cls, path: Path) -> "Config":
        ini = ConfigParser(inline_comment_prefixes=(";",))
        with open(path) as f:
            ini.read_file(f)
        slurm, collector = ini["slurm"], ini["collector"]
        token_file = slurm.get("token_file")
        return cls(
            slurm_url=slurm["url"],
            token_file=Path(token_file) if token_file else None,
            database_url=ini["database"]["url"],
            interval=timedelta(minutes=collector.getfloat("interval_minutes", 5)),
        )

    def token(self) -> str:
        """The Slurm JWT, read on every call so a new token works without a restart."""
        if self.token_file:
            return self.token_file.read_text().strip()
        return os.environ["SLURM_JWT"]

    def database(self) -> URL:
        """Database URL; containers may override the host, the password is never in the INI."""
        url = make_url(os.environ.get("SLURM_LENS_DATABASE_URL", self.database_url))
        password = os.environ.get("SLURM_LENS_DB_PASSWORD")
        return url.set(password=password) if password else url
