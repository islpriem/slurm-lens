"""Read-only HTTP access to slurmrestd."""

import time
from dataclasses import dataclass, field

import httpx


@dataclass(frozen=True)
class Reply:
    status: int
    data: dict = field(default_factory=dict)
    seconds: float = 0.0
    error: str | None = None


class SlurmClient:
    """GET-only client that refuses every path outside the allowlist."""

    def __init__(self, url, token, allowed, transport=None):
        self.allowed = allowed
        self.http = httpx.Client(
            base_url=url, headers={"X-SLURM-USER-TOKEN": token}, timeout=300, transport=transport
        )

    def get(self, path: str, **params) -> Reply:
        if path not in self.allowed:
            raise ValueError(f"{path} is not on the allowlist")
        started = time.monotonic()
        response = self.http.get(path, params=params)
        seconds = time.monotonic() - started
        try:
            data = response.json()
        except ValueError:
            return Reply(response.status_code, seconds=seconds, error=response.text[:200])
        errors = "; ".join(e.get("description", "") for e in data.get("errors", []))
        return Reply(response.status_code, data, seconds, errors or None)
