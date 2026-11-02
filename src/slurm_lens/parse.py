"""Small helpers that turn slurmrestd values into plain Python values."""

import re
from datetime import UTC, datetime

MB_PER_UNIT = {"K": 1 / 1024, "M": 1, "G": 1024, "T": 1024**2}
GRES = re.compile(r"(\w+)(?::([\w-]+))?:(\d+)(?:\((S|IDX):([^)]*)\))?")
HOSTS = re.compile(r"([^,\[]+)(?:\[([^\]]+)\])?")


def num(value):
    """Unwrap a {set, infinite, number} struct; unset and infinite become None."""
    if isinstance(value, dict) and "number" in value:
        return value["number"] if value["set"] and not value["infinite"] else None
    return value


def stamp(value) -> datetime | None:
    """Unix timestamp as UTC datetime, where 0 means 'not set'."""
    seconds = num(value)
    return datetime.fromtimestamp(seconds, UTC) if seconds else None


def join(values) -> str | None:
    return ",".join(values or []) or None


def tres(text: str) -> dict[str, int]:
    """'cpu=4,mem=16G,gres/gpu:a100=1' -> {'cpu': 4, 'mem': 16384, 'gres/gpu:a100': 1}"""
    result = {}
    for key, value in (item.split("=", 1) for item in (text or "").split(",") if item):
        factor = MB_PER_UNIT.get(value[-1])
        result[key] = round(float(value[:-1]) * factor) if factor else round(float(value))
    return result


def tres_list(items: list[dict]) -> dict[str, int]:
    """Accounting TRES list -> same dict format as tres()."""
    return {f"{t['type']}/{t['name']}" if t["name"] else t["type"]: t["count"] for t in items}


def gres(text: str) -> list[tuple[str, str | None, int, str | None]]:
    """'gpu:a100:3(IDX:0-1,4)' -> [('gpu', 'a100', 3, '0-1,4')], only IDX lists are kept."""
    return [
        (name, model or None, int(count), idx if kind == "IDX" and idx != "N/A" else None)
        for name, model, count, kind, idx in GRES.findall(text or "")
    ]


def _expand(ranges: str) -> list[str]:
    """'07-08,14' -> ['07', '08', '14'], keeping the zero padding; '0-9:3' uses a step."""
    result = []
    for part in ranges.split(","):
        low, _, high = part.partition("-")
        high, _, step = high.partition(":")
        stop = int(high or low) + 1
        result += [f"{i:0{len(low)}d}" for i in range(int(low), stop, int(step or 1))]
    return result


def index_range(text: str | None) -> list[int]:
    return [int(i) for i in _expand(text)] if text else []


def hostlist(text: str | None) -> list[str]:
    """'gx[07-08],gx13v1' -> ['gx07', 'gx08', 'gx13v1']"""
    if not text or text == "None assigned":
        return []
    return [
        prefix + suffix
        for prefix, ranges in HOSTS.findall(text)
        for suffix in (_expand(ranges) if ranges else [""])
    ]


def array_size(text: str) -> int:
    """Number of tasks in an array spec like '0-47%4'."""
    return len(_expand(text.split("%")[0])) if text else 1
