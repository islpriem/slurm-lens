"""What a module shows: computed here, the frontend only scales the axes and draws."""

import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from itertools import cycle
from typing import Literal

# categorical colors in a fixed order, the same as in the notebooks
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]
GRAY = "#bdbcb6"
RED = "#d03b3b"
STATUS = {"ok": PALETTE[2], "partial": PALETTE[3], "failed": RED, "aborted": GRAY}


Value = float | list[float] | None  # a number, or for box plots low, q1, median, q3 and high


@dataclass
class Series:
    name: str
    color: str
    y: list[Value]  # one value per x, None where there is none

    def __post_init__(self):
        self.y = [rounded(y) for y in self.y]


def rounded(y):
    """Floats with two decimals (also from ints and Decimals), lists element by element."""
    if isinstance(y, list):
        return [rounded(v) for v in y]
    return None if y is None else round(float(y), 2)


@dataclass
class Chart:
    """Lines and areas have times or numbers as x, the others categories; pies one value each."""

    title: str
    kind: Literal["line", "area", "dot", "bar", "pie", "box", "heatmap", "ranking"]
    x: list[datetime] | list[float] | list[str]
    series: list[Series]
    unit: str = ""  # after every value, e.g. " %"
    x_unit: str = ""  # after every x that is a number
    note: str = ""  # how to read the chart
    stats: dict[str, str] = field(default_factory=dict)  # key figures next to the chart
    y_max: float | None = None
    stacked: bool = False
    horizontal: bool = False
    wide: bool = False  # over the whole width of the page


@dataclass
class Table:
    title: str
    columns: list[str]
    rows: list[list[datetime | int | float | str | None]]
    kind: Literal["table"] = "table"
    wide: bool = True

    def __post_init__(self):
        self.rows = [
            [rounded(v) if isinstance(v, Decimal | float) else v for v in r] for r in self.rows
        ]


@dataclass
class Tile:
    title: str
    value: datetime | int | float | str | None
    note: str = ""
    status: Literal["ok", "warn", "fail"] | None = None


@dataclass
class View:
    tiles: list[Tile] = field(default_factory=list)
    panels: list[Chart | Table] = field(default_factory=list)


def series(values: dict[str, list], colors: dict[str, str] | None = None) -> list[Series]:
    """Series in the order of the dict; names without a fixed color get the palette in order."""
    colors, palette = colors or {}, cycle(PALETTE)
    return [Series(name, colors.get(name) or next(palette), y) for name, y in values.items()]


def pie(title: str, counts: dict[str, float], colors: dict[str, str] | None = None) -> Chart:
    """One slice per entry in the order of the dict, empty ones left out."""
    return Chart(title, "pie", [], series({k: [v] for k, v in counts.items() if v}, colors))


def ranking(title: str, values: dict[str, float], colors=None, **options) -> Chart:
    """A list of bars with their share, in the order of the dict; one color unless given."""
    x = list(values)
    colors = dict.fromkeys(x, PALETTE[0]) | (colors or {})
    return Chart(title, "ranking", x, series(grouped(x, values), colors), **options)


def top(counts: Counter, n: int, rest: str = "others") -> dict[str, float]:
    """The n largest entries and the sum of all others."""
    largest = dict(counts.most_common(n))
    others = sum(counts.values()) - sum(largest.values())
    return largest | ({rest: others} if others else {})


def percent(values: list[float]) -> list[float]:
    total = sum(values) or 1
    return [100 * value / total for value in values]


def box(values: list[float]) -> list[float] | None:
    """5th, 25th, 50th, 75th and 95th percentile."""
    if len(values) < 2:
        return None
    q = statistics.quantiles(values, n=20, method="inclusive")
    return [q[0], q[4], q[9], q[14], q[18]]


def duration(seconds: float | None) -> str:
    """'40 s', '45 min', '3 h 20 min', '4 days 2 h'"""
    if seconds is None:
        return "–"
    if seconds < 60:
        return f"{seconds:.0f} s"
    hours, minutes = divmod(round(seconds / 60), 60)
    days, hours = divmod(hours, 24) if hours >= 48 else (0, hours)
    parts = (days, "days"), (hours, "h"), (0 if days else minutes, "min")
    return " ".join(f"{n} {unit}" for n, unit in parts if n)


def box_note(of: str) -> str:
    """How to read a box plot over the given things."""
    return f"Middle half, median and 5th to 95th percentile of the {of}."


def grouped(x: list[str], values: dict[str, Value], group: dict[str, str] | None = None) -> dict:
    """Values per x as one series per group (every x on its own by default), None at the x of
    other groups: so that each group keeps its color."""
    group = group or {category: category for category in x}
    groups = dict.fromkeys(group[category] for category in x)
    return {g: [values[c] if group[c] == g else None for c in x] for g in groups}
