from datetime import UTC, datetime

from conftest import payload

from slurm_lens import slurm

NOW = datetime(2026, 10, 26, 14, 30, tzinfo=UTC)


def jobs():
    return {j["job_id"]: j for j in payload("jobs")["jobs"]}


def test_running_job_has_allocation_with_physical_gpus():
    running = next(j for j in jobs().values() if j["job_state"] == ["RUNNING"])
    rows = slurm.queue_rows(running, snapshot_id=1, now=NOW)
    assert rows.snapshot["state"] == "RUNNING"
    assert rows.job["req_gpus"] > 0
    allocation = rows.allocations[0]
    assert allocation["gpu_idx"] and len(allocation["gpu_idx"]) == rows.job["req_gpus"]
    assert allocation["node"] in running["nodes"]


def test_pending_job_keeps_the_backfill_plan():
    planned = next(j for j in jobs().values() if j["scheduled_nodes"])
    rows = slurm.queue_rows(planned, snapshot_id=1, now=NOW)
    assert rows.snapshot["scheduled_nodes"] == planned["scheduled_nodes"]
    assert rows.snapshot["start_time"] > NOW
    assert rows.allocations == []


def test_pending_array_counts_its_tasks():
    array = next(j for j in jobs().values() if j["array_task_string"])
    assert slurm.queue_rows(array, snapshot_id=1, now=NOW).snapshot["array_tasks"] > 1


def test_raw_job_has_no_personal_fields():
    raw = slurm.queue_rows(next(iter(jobs().values())), snapshot_id=1, now=NOW).job["raw"]
    assert not slurm.PERSONAL & raw.keys()
    assert "user_name" in raw


def test_node_splits_state_from_static_configuration():
    node = next(n for n in payload("nodes")["nodes"] if n["gres"])
    state, static = slurm.node_rows(node, snapshot_id=1)
    assert state["gpus_used"] == len(state["gpu_idx_used"])
    assert "alloc_cpus" not in static and static["gres"] == node["gres"]


def test_diag_drops_lists_with_user_names():
    diag = slurm.diag(payload("diag")["statistics"] | {"rpcs_by_user": [{"user": "x"}]})
    assert "rpcs_by_user" not in diag and diag["jobs_running"] >= 0
