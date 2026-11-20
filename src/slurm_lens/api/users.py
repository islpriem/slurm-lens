"""Users and accounts: who allocates the GPUs, who waits, how fairshare treats them."""

from collections import Counter
from itertools import accumulate
from operator import itemgetter

from fastapi import APIRouter
from sqlalchemy import Integer, func, select

from ..models import FairshareSnapshot, Job, JobRecord, JobSnapshot, Snapshot
from .query import allocated, model_colors, quantiles, started
from .scope import Scope, ScopeDep
from .view import GRAY, PALETTE, Chart, Table, Tile, View, ranking, series, top

router = APIRouter()


@router.get("")
def view(scope: ScopeDep) -> View:
    users = Users(scope)
    return View(users.tiles(), [users.over_time(), users.accounts(), users.models(), users.table()])


class Users:
    """GPU hours per hour, user, account and model, with the names the scope asks for."""

    def __init__(self, scope: Scope):
        self.scope = scope
        self.hours = Counter()  # by hour and user
        self.used = Counter()  # by user, account and model
        columns = JobRecord.user_name, JobRecord.account, JobRecord.gpu_model
        for (hour, user, account, model), gpus in allocated(scope, *columns).items():
            user, account = scope.user(user), scope.account(account)
            self.hours[hour, user] += gpus
            self.used[user, account, model] += gpus
        self.users = self.total(0)
        # the users with an own color in the charts
        self.top = [user for user, _ in self.users.most_common(len(PALETTE) - 1)]
        snapshot = Snapshot.latest(scope.session, "ok")
        tasks = func.sum(JobSnapshot.array_tasks).cast(Integer)
        query = (
            select(Job.user_name, tasks)
            .join(Job)
            .where(
                JobSnapshot.snapshot_id == (snapshot and snapshot.id),
                JobSnapshot.state == "PENDING",
            )
        )
        self.pending = {scope.user(user): n for user, n in scope.session.execute(
            query.group_by(Job.user_name))}  # fmt: skip
        competing = query.where(JobSnapshot.reason.in_(["Resources", "Priority"]))
        self.waiting = {scope.user(user) for user, _ in scope.session.execute(
            competing.group_by(Job.user_name))}  # fmt: skip

    def total(self, *parts: int) -> Counter:
        """GPU hours by the given parts of (user, account, model), e.g. total(0) per user."""
        key, result = itemgetter(*parts), Counter()
        for keys, gpus in self.used.items():
            result[key(keys)] += gpus
        return result

    def tiles(self) -> list[Tile]:
        names = func.count(JobRecord.user_name.distinct()), func.count(JobRecord.account.distinct())
        query = select(*names).where(started(self.scope))
        users, accounts = self.scope.session.execute(query).one()
        hours = [h for _, h in self.users.most_common()]
        total = sum(hours) or 1
        # the fewest users that together have half of the GPU hours
        half = next((i for i, h in enumerate(accumulate(hours), 1) if h >= total / 2), 0)
        largest = self.top[0] if self.top else "nobody"
        return [
            Tile("Active users", users, f"in {accounts} accounts"),
            Tile("Users with GPUs", len(self.users), f"{len(self.waiting)} wait for GPUs now"),
            Tile("Largest user", f"{100 * (hours or [0])[0] / total:.0f} %",
                 f"of the GPU hours went to {largest}"),
            Tile("Half of the GPU hours", f"{half} users", f"of {len(self.users)} with GPUs"),
        ]  # fmt: skip

    def over_time(self) -> Chart:
        others = Counter()
        for (hour, user), gpus in self.hours.items():
            if user not in self.top:
                others[hour] += gpus
        values = {user: [self.hours[h, user] for h in self.scope.hours] for user in self.top}
        values["others"] = [others[h] for h in self.scope.hours]
        note = f"The {len(self.top)} users with the most GPU hours, everybody else in gray."
        return Chart("Allocated GPUs per user", "area", self.scope.hours,
                     series(values, {"others": GRAY}), unit=" GPUs", note=note, stacked=True,
                     wide=True)  # fmt: skip

    def accounts(self) -> Chart:
        accounts = top(self.total(1), 9)
        return ranking("GPU hours per account", accounts, {"others": GRAY}, unit=" h")

    def models(self) -> Chart:
        """The models of the users with the most GPU hours."""
        x = [user for user, _ in self.users.most_common(10)]
        colors = model_colors(self.total(2))
        hours = Counter()
        for (user, model), gpus in self.total(0, 2).items():
            hours[user, model if model in colors else "other"] += gpus
        values = {model: [hours[user, model] for user in x] for model in colors}
        return Chart("GPU hours per user and model", "bar", x, series(values, colors), unit=" h",
                     stacked=True, horizontal=True)  # fmt: skip

    def table(self) -> Table:
        """Every user with GPU hours, in their account with the most."""
        session, user = self.scope.session, self.scope.user
        query = select(
            JobRecord.user_name,
            func.count(),
            func.count().filter(JobRecord.gpus > 0),
            quantiles(JobRecord.wait_s, 0.5),
        ).where(started(self.scope))
        jobs = {
            user(name): (count, gpu_jobs, wait[0] / 3600)
            for name, count, gpu_jobs, wait in session.execute(query.group_by(JobRecord.user_name))
        }
        latest = select(func.max(FairshareSnapshot.snapshot_id)).scalar_subquery()
        query = select(FairshareSnapshot).where(
            FairshareSnapshot.snapshot_id == latest, FairshareSnapshot.type == "USER"
        )
        factors = {
            (user(s.name), self.scope.account(s.parent)): s.fairshare_factor
            for s in session.scalars(query)
        }
        accounts, total = self.total(0, 1), self.users.total() or 1
        rows = []
        for name, hours in self.users.most_common():
            account = max((a for u, a in accounts if u == name), key=lambda a: accounts[name, a])
            rows.append([
                name, account, hours, 100 * hours / total, *jobs.get(name, (0, 0, None)),
                factors.get((name, account)), self.pending.get(name, 0),
            ])  # fmt: skip
        columns = ["User", "Account", "GPU hours", "GPU hours (%)", "Jobs started", "GPU jobs",
                   "Median wait (h)", "Fairshare factor", "Pending tasks now"]  # fmt: skip
        return Table("Users with GPU hours", columns, rows)
