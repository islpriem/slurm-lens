import json
from pathlib import Path

DATA = Path(__file__).with_name("data")


def payload(name: str) -> dict:
    """A synthetic slurmrestd response from tests/data."""
    return json.loads((DATA / f"{name}.json").read_text())
