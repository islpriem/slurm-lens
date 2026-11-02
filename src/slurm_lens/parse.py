"""Small helpers that turn slurmrestd values into plain Python values."""

from datetime import UTC, datetime

MB_PER_UNIT = {"K": 1 / 1024, "M": 1, "G": 1024, "T": 1024**2}


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
