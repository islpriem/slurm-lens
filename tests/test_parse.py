from datetime import UTC, datetime

from slurm_lens.parse import (
    array_size,
    gres,
    hostlist,
    index_range,
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


def test_gres():
    assert gres("gpu:h100:8(S:0-1)") == [("gpu", "h100", 8, None)]
    assert gres("gpu:a100:3(IDX:0-1,4)") == [("gpu", "a100", 3, "0-1,4")]
    assert gres("gpu:gh200:0(IDX:N/A)") == [("gpu", "gh200", 0, None)]
    assert gres("gpu:2080_ti:8(S:0),gpu:4") == [("gpu", "2080_ti", 8, None), ("gpu", None, 4, None)]
    assert gres("") == []


def test_ranges():
    assert index_range("0-1,4") == [0, 1, 4]
    assert index_range(None) == []
    assert hostlist("gx[07-08,14],gx13v1") == ["gx07", "gx08", "gx14", "gx13v1"]
    assert hostlist("None assigned") == []
    assert array_size("0-47%4") == 48
    assert array_size("1,3,5-7") == 5
    assert array_size("2-47:5%2") == 10
    assert array_size("") == 1
