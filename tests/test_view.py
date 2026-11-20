from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest

from slurm_lens.api.nodes import state
from slurm_lens.api.queue import reason
from slurm_lens.api.timeline import Piece, Slots
from slurm_lens.api.users import concentration
from slurm_lens.api.view import box, duration, grouped, percent, pie, top


def test_box_has_five_quantiles():
    assert box(list(range(101))) == [5, 25, 50, 75, 95]
    assert box([3]) is None


def test_top_sums_up_the_rest():
    assert top(Counter(a=5, b=3, c=1, d=1), 2) == {"a": 5, "b": 3, "others": 2}
    assert top(Counter(a=5), 2) == {"a": 5}


def test_grouped_keeps_one_series_per_group():
    models = {"gx01": "h100", "gx02": "a100", "gx03": "h100"}
    values = grouped(list(models), {"gx01": 1, "gx02": 2, "gx03": 3}, models)
    assert values == {"h100": [1, None, 3], "a100": [None, 2, None]}


def test_pie_leaves_out_empty_slices():
    assert [s.name for s in pie("states", {"ok": 3, "failed": 0}).series] == ["ok"]


def test_percent_and_duration():
    assert percent([1, 3]) == [25, 75] and percent([0, 0]) == [0, 0]
    durations = [duration(s) for s in (59, 3600, 3 * 3600 + 1200, 50 * 3600)]
    assert durations == ["59 s", "1 h", "3 h 20 min", "2 days 2 h"]


def test_groups_of_slurm_states_and_reasons():
    assert [state(s) for s in ("MIXED,PLANNED", "IDLE,DRAIN", "ALLOCATED", "FUTURE")] == [
        "mixed", "unavailable", "allocated", "other",
    ]  # fmt: skip
    reasons = ["Priority", "DependencyNeverSatisfied", "JobHeldUser", "QOSMaxMemoryPerUser",
               "ReqNodeNotAvail", None]  # fmt: skip
    assert [reason(r) for r in reasons] == [
        "competing", "dependency", "held", "limit", "nodes unavailable", "other",
    ]  # fmt: skip


def test_concentration_of_the_largest():
    shares = concentration([3, 1])
    assert (shares[0], shares[50], shares[100]) == (0, 75, 100)
    assert concentration([2, 2, 2, 2]) == pytest.approx(list(range(101)))


def test_slots_keep_known_gpus_and_fill_the_lowest_free():
    slots, start = Slots(4), datetime(2026, 11, 20, tzinfo=UTC)
    hour = timedelta(hours=1)
    assert slots.place(Piece(0, "gx01", 2, start, start + 2 * hour, fixed=[1, 2])) == [1, 2]
    assert slots.place(Piece(1, "gx01", 2, start + hour, start + 3 * hour)) == [0, 3]
    assert slots.place(Piece(2, "gx01", 1, start + 2 * hour, start + 4 * hour)) == [1]
