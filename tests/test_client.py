import httpx
import pytest

from slurm_lens.client import SlurmClient

PATH = "/slurm/v0.0.45/ping/"


def client(handler, **kwargs) -> SlurmClient:
    return SlurmClient(
        "https://slurm.test",
        "token",
        {PATH},
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


def test_slurm_errors_in_json_are_returned():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(500, json={"errors": [{"description": "broken"}]})

    reply = client(handler).get(PATH)
    assert (len(calls), reply.status, reply.error) == (1, 500, "broken")
