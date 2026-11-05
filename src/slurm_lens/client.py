"""Read-only HTTP access to slurmrestd."""

import time
from dataclasses import dataclass, field

import httpx


class Unavailable(Exception):
    """slurmrestd cannot be used right now, so a whole run is pointless."""


class TokenError(Unavailable):
    """Slurm rejected the token."""


@dataclass(frozen=True)
class Reply:
    status: int
    data: dict = field(default_factory=dict)
    seconds: float = 0.0
    error: str | None = None


class SlurmClient:
    """GET-only client that refuses every path outside the allowlist."""

    def __init__(self, url, token, allowed, pause=2.0, retries=2, transport=None):
        self.allowed = allowed
        self.pause = pause  # slurmrestd has little memory, so requests are spaced out
        self.retries = retries
        self.http = httpx.Client(
            base_url=url, headers={"X-SLURM-USER-TOKEN": token}, timeout=300, transport=transport
        )

    def get(self, path: str, **params) -> Reply:
        if path not in self.allowed:
            raise ValueError(f"{path} is not on the allowlist")
        reply = failure = None
        for attempt in range(self.retries + 1):
            time.sleep(self.pause * 2**attempt)
            # no response or no JSON means the proxy or the connection failed, worth another try
            try:
                reply = self._get(path, params)
            except httpx.TransportError as error:
                failure = error
                continue
            if reply.data:
                return reply
        if reply is None:
            raise Unavailable(f"no answer from {path}: {failure!r}")
        return reply

    def _get(self, path: str, params: dict) -> Reply:
        started = time.monotonic()
        response = self.http.get(path, params=params)
        seconds = time.monotonic() - started
        if response.status_code in (401, 403):
            raise TokenError(f"slurmrestd answered {response.status_code}, the token is invalid")
        try:
            data = response.json()
        except ValueError:
            return Reply(response.status_code, seconds=seconds, error=response.text[:200])
        errors = "; ".join(e.get("description", "") for e in data.get("errors", []))
        return Reply(response.status_code, data, seconds, errors or None)
