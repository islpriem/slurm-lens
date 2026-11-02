from datetime import UTC, datetime

from slurm_lens.parse import (
    join,
    num,
    stamp,
    tres,
    tres_list,
)


def test_num():
    assert num({"set": True, "infinite": False, "number": 5}) == 5
    assert num({"set": False, "infinite": False, "number": 0}) is None
    assert num({"set": True, "infinite": True, "number": 0}) is None
    assert num(7) == 7


def test_stamp():
    assert stamp({"set": True, "infinite": False, "number": 1792948150}) == datetime(
        2026, 10, 25, 17, 9, 10, tzinfo=UTC
    )
    assert stamp(0) is None


def test_join():
    assert join(["MIXED", "PLANNED"]) == "MIXED,PLANNED"
    assert join([]) is None


def test_tres():
    assert tres("cpu=96,mem=512G,node=1,gres/gpu:h100=8") == {
        "cpu": 96, "mem": 524288, "node": 1, "gres/gpu:h100": 8
    }  # fmt: skip
    assert tres("mem=190474M") == {"mem": 190474}
    assert tres("") == {}


def test_tres_list():
    items = [
        {"type": "gres", "name": "gpu:h100", "count": 8},
        {"type": "mem", "name": "", "count": 1},
    ]
    assert tres_list(items) == {"gres/gpu:h100": 8, "mem": 1}
