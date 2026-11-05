import base64
import json
from datetime import UTC, datetime

import httpx
import pytest

from slurm_lens.client import SlurmClient, TokenError, Unavailable, token_expiry

PATH = "/slurm/v0.0.45/ping/"


def client(handler, **kwargs) -> SlurmClient:
    return SlurmClient(
        "https://slurm.test",
        "token",
        {PATH},
        pause=0,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def test_get_sends_the_token_and_returns_json():
    def handler(request):
        assert request.method == "GET"
        assert request.headers["X-SLURM-USER-TOKEN"] == "token"
        assert request.url.params["flags"] == "DETAIL"
        return httpx.Response(200, json={"pings": []})

    reply = client(handler).get(PATH, flags="DETAIL")
    assert (reply.status, reply.data, reply.error) == (200, {"pings": []}, None)


def test_refuses_paths_outside_the_allowlist():
    with pytest.raises(ValueError):
        client(lambda request: httpx.Response(200)).get("/slurm/v0.0.45/reconfigure/")


def test_has_no_way_to_change_the_cluster():
    slurm = client(lambda request: httpx.Response(200))
    assert not any(hasattr(slurm, name) for name in ("post", "put", "delete", "request"))


def test_retries_proxy_errors_without_json():
    answers = iter([httpx.Response(502, text="Bad Gateway"), httpx.Response(200, json={"ok": 1})])
    reply = client(lambda request: next(answers)).get(PATH)
    assert reply.data == {"ok": 1}


def test_gives_up_after_the_retries():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ConnectTimeout("timeout")

    with pytest.raises(Unavailable, match="timeout"):
        client(handler, retries=2).get(PATH)
    assert len(calls) == 3


def test_a_proxy_error_after_the_retries_is_returned():
    reply = client(lambda request: httpx.Response(502, text="Bad Gateway")).get(PATH)
    assert (reply.status, reply.error) == (502, "Bad Gateway")


def test_slurm_errors_in_json_are_returned_not_retried():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(500, json={"errors": [{"description": "broken"}]})

    reply = client(handler).get(PATH)
    assert (len(calls), reply.status, reply.error) == (1, 500, "broken")


def test_rejected_token_raises():
    with pytest.raises(TokenError):
        client(lambda request: httpx.Response(401)).get(PATH)


def test_token_expiry():
    payload = (
        base64.urlsafe_b64encode(json.dumps({"exp": 1792983282}).encode()).decode().rstrip("=")
    )
    assert token_expiry(f"header.{payload}.signature") == datetime(
        2026, 10, 26, 2, 54, 42, tzinfo=UTC
    )
    assert token_expiry("not a jwt") is None
