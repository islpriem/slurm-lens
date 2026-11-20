"""What a request asks for: a period, and whether users and accounts get pseudonyms."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import cached_property
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Config
from ..models import HistoryWindow, JobRecord

HOUR = timedelta(hours=1)
BEGINNING = datetime(2000, 1, 1, tzinfo=UTC)


def full_hour(time: datetime, up: bool = False) -> datetime:
    down = time.replace(minute=0, second=0, microsecond=0)
    return down + HOUR if up and down < time else down


def session(request: Request) -> Iterator[Session]:
    with request.app.state.store.session() as session:
        yield session


def config(request: Request) -> Config:
    return request.app.state.config


SessionDep = Annotated[Session, Depends(session)]
ConfigDep = Annotated[Config, Depends(config)]


@dataclass
class Scope:
    """The period a view covers, and how it names users and accounts.

    Pseudonyms are ranked by GPU hours over the whole history: U1 is the user with the most,
    A1 the account. So they stay the same for every period.
    """

    session: Session
    start: datetime
    end: datetime
    pseudonyms: bool
    zone: str  # of the reader, for days and hours of the day

    def local(self, time: datetime) -> datetime:
        return time.astimezone(ZoneInfo(self.zone))

    def day(self, column):
        """Midnight of the day of a time column, in the time zone of the reader."""
        return func.date_trunc("day", column, self.zone)

    @cached_property
    def history(self) -> tuple[datetime, datetime]:
        """The part of the period that the accounting history covers without gaps."""
        covered = HistoryWindow.covered(self.session)
        if not covered:
            raise HTTPException(404, "no accounting history yet")
        # full hours only, so that the first and the last hour are not half empty
        start = full_hour(max(self.start, covered[0]), up=True)
        end = full_hour(min(self.end, covered[1]))
        if start >= end:
            raise HTTPException(404, "no accounting history in this period")
        return start, end

    @cached_property
    def hours(self) -> list[datetime]:
        """Every hour of the history period."""
        start, end = self.history
        return [start + i * HOUR for i in range((end - start) // HOUR)]

    def user(self, name: str) -> str:
        return self._name(name, self._users, "U")

    def account(self, name: str) -> str:
        return self._name(name, self._accounts, "A")

    def _name(self, name: str, ranking: dict[str, str], prefix: str) -> str:
        if not self.pseudonyms:
            return name
        # a user who has not run a job yet is added at the end
        return ranking.setdefault(name, f"{prefix}{len(ranking) + 1}")

    @cached_property
    def _users(self) -> dict[str, str]:
        return self._rank(JobRecord.user_name, "U")

    @cached_property
    def _accounts(self) -> dict[str, str]:
        return self._rank(JobRecord.account, "A")

    def _rank(self, column, prefix: str) -> dict[str, str]:
        usage = func.sum(func.coalesce(JobRecord.gpus, 0) * JobRecord.elapsed_s)
        names = self.session.scalars(select(column).group_by(column).order_by(usage.desc(), column))
        return {name: f"{prefix}{i}" for i, name in enumerate(names, 1)}


def scope(
    session: SessionDep,
    start: datetime | None = None,
    end: datetime | None = None,
    pseudonyms: bool = True,
    zone: str = "UTC",
) -> Scope:
    """Everything up to now if no period is given."""
    try:
        ZoneInfo(zone)
    except (ValueError, ZoneInfoNotFoundError):
        raise HTTPException(422, f"unknown time zone {zone}") from None
    end = end.astimezone(UTC) if end else datetime.now(UTC)
    return Scope(session, start.astimezone(UTC) if start else BEGINNING, end, pseudonyms, zone)


ScopeDep = Annotated[Scope, Depends(scope)]
