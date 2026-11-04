"""Settings from the INI file. Secrets come from a file or the environment, never from the INI."""

import os
from configparser import ConfigParser
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.engine import URL, make_url


@dataclass(frozen=True)
class Config:
    slurm_url: str
    token_file: Path | None
    pause: float
    database_url: str
    interval: timedelta
    fairshare_interval: timedelta
    history_start: datetime
    window: timedelta
    max_backfill_windows: int

    @classmethod
    def load(cls, path: Path) -> "Config":
        ini = ConfigParser(inline_comment_prefixes=(";",))
        with open(path) as f:
            ini.read_file(f)
        slurm, collector, history = ini["slurm"], ini["collector"], ini["history"]
        token_file = slurm.get("token_file")
        return cls(
            slurm_url=slurm["url"],
            token_file=Path(token_file) if token_file else None,
            pause=slurm.getfloat("pause_seconds", 2.0),
            database_url=ini["database"]["url"],
            interval=timedelta(minutes=collector.getfloat("interval_minutes", 5)),
            fairshare_interval=timedelta(minutes=collector.getfloat("fairshare_minutes", 60)),
            history_start=datetime.fromisoformat(history["start"]).replace(tzinfo=UTC),
            window=timedelta(hours=history.getfloat("window_hours", 4)),
            max_backfill_windows=history.getint("max_backfill_windows", 6),
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
