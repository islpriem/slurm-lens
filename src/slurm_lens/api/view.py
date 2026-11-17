"""What a module shows: computed here, the frontend only scales the axes and draws."""

from dataclasses import dataclass, field
from datetime import datetime
from itertools import cycle
from typing import Literal

# categorical colors in a fixed order, the same as in the notebooks
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]
GRAY = "#bdbcb6"
STATUS = {"ok": "#1baf7a", "partial": "#eda100", "failed": "#d03b3b", "aborted": GRAY}


@dataclass
class Series:
    name: str
    color: str
    y: list[float | None]  # one value per x, None where there is none

    def __post_init__(self):
        self.y = [y if y is None else round(y, 2) for y in self.y]


@dataclass
class Chart:
    title: str
    kind: Literal["line", "dot", "bar"]
    x: list[datetime] | list[str]  # times, or the categories of a bar chart
    series: list[Series]
    y_max: float | None = None
    log: bool = False
    wide: bool = False  # over the whole width of the page


@dataclass
class Tile:
    title: str
    value: datetime | int | None
    note: str = ""


@dataclass
class View:
    tiles: list[Tile] = field(default_factory=list)
    charts: list[Chart] = field(default_factory=list)


def series(values: dict[str, list], colors: dict[str, str] | None = None) -> list[Series]:
    """Series in the order of the dict; names without a fixed color get the palette in order."""
    colors, palette = colors or {}, cycle(PALETTE)
    return [Series(name, colors.get(name) or next(palette), y) for name, y in values.items()]


def percent(values: list[float]) -> list[float]:
    total = sum(values) or 1
    return [100 * value / total for value in values]
