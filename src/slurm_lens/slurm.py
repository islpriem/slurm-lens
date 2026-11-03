"""The slurmrestd endpoints we read and how their responses become database rows."""

from typing import Any, NamedTuple

from .parse import array_size, gres, index_range, join, num, stamp, tres

VERSION = "v0.0.45"
PATHS = {
    "jobs": f"/slurm/{VERSION}/jobs/",
    "diag": f"/slurm/{VERSION}/diag/",
    "nodes": f"/slurm/{VERSION}/nodes/",
    "conf": f"/slurm/{VERSION}/conf",
    "partitions": f"/slurm/{VERSION}/partitions/",
    "reservations": f"/slurm/{VERSION}/reservations/",
    "shares": f"/slurm/{VERSION}/shares",
    "qos": f"/slurmdb/{VERSION}/qos/",
    "tres": f"/slurmdb/{VERSION}/tres/",
    "associations": f"/slurmdb/{VERSION}/associations/",
}
ALLOWED = frozenset(PATHS.values())

# free text about the user's work; not needed and not stored
PERSONAL = frozenset(
    [
        "name",
        "command",
        "submit_line",
        "comment",
        "admin_comment",
        "system_comment",
        "current_working_directory",
        "standard_input",
        "standard_output",
        "standard_error",
        "stdin_expanded",
        "stdout_expanded",
        "stderr_expanded",
        "mail_user",
        "mail_type",
        "container",
        "container_id",
        "extra",
    ]
)

# static part of a node, versioned in config_version; the rest changes every snapshot
NODE_STATIC = [
    "architecture",
    "cpus",
    "sockets",
    "cores",
    "threads",
    "real_memory",
    "specialized_memory",
    "specialized_cores",
    "features",
    "active_features",
    "gres",
    "partitions",
    "weight",
    "tres",
    "version",
]

# kinds of configuration: endpoint, list in its response, field that names an item
CONFIG = {
    "partition": ("partitions", "partitions", "name"),
    "reservation": ("reservations", "reservations", "name"),
    "qos": ("qos", "qos", "name"),
    "tres": ("tres", "TRES", "id"),
    "association": ("associations", "associations", "id"),
}


class QueueRows(NamedTuple):
    job: dict
    snapshot: dict
    allocations: list[dict]


def gpu_model(counts: dict[str, int]) -> str | None:
    return next((k.split(":", 1)[1] for k in counts if k.startswith("gres/gpu:")), None)


def queue_rows(j: dict, snapshot_id: int, now) -> QueueRows:
    """A job of the live queue: its request, its current state and where it runs."""
    requested = tres(j["tres_req_str"])
    job = {
        "job_id": j["job_id"],
        "user_name": j["user_name"],
        "account": j["account"],
        "partition": j["partition"],
        "qos": j["qos"],
        "submit_time": stamp(j["submit_time"]),
        "time_limit_min": num(j["time_limit"]),
        "tres_req": requested,
        "req_gpus": requested.get("gres/gpu"),
        "req_gpu_model": gpu_model(requested),
        "constraints": j["features"] or None,
        "dependency": j["dependency"] or None,
        "array_job_id": num(j["array_job_id"]) or None,
        "array_task_id": num(j["array_task_id"]),
        "first_seen": now,
        "raw": {key: value for key, value in j.items() if key not in PERSONAL},
    }
    snapshot = {
        "snapshot_id": snapshot_id,
        "job_id": j["job_id"],
        "state": join(j["job_state"]),
        "reason": j["state_reason"],
        "priority": num(j["priority"]),
        "partition_priority": {p["partition"]: p["priority"] for p in j["priority_by_partition"]}
        or None,
        **{
            key: stamp(j[key]) for key in ("eligible_time", "accrue_time", "start_time", "end_time")
        },
        "nodes": j["nodes"] or None,
        "scheduled_nodes": j["scheduled_nodes"] or None,
        "array_tasks": array_size(j["array_task_string"]),
    }
    return QueueRows(job, snapshot, _allocations(j, now))


def _allocations(j: dict, now) -> list[dict]:
    if not j["job_resources"]:
        return []
    nodes = j["job_resources"]["nodes"]["allocation"]
    # gres_detail has one entry per allocated node, in the same order
    details = j["gres_detail"] + [""] * len(nodes)
    rows = []
    for node, detail in zip(nodes, details, strict=False):
        gpus = [(model, index_range(idx)) for name, model, _, idx in gres(detail) if name == "gpu"]
        rows.append({
            "job_id": j["job_id"],
            "node": node["name"],
            "cpus": node["cpus"]["count"],
            "memory_mb": node["memory"]["allocated"],
            "gpu_model": gpus[0][0] if gpus else None,
            "gpu_idx": [i for _, indices in gpus for i in indices],
            "first_seen": now,
        })  # fmt: skip
    return rows


def node_rows(n: dict, snapshot_id: int) -> tuple[dict, dict]:
    """A node's state in this snapshot and its static configuration."""
    gpus = [
        (count, index_range(idx)) for name, _, count, idx in gres(n["gres_used"]) if name == "gpu"
    ]
    state = {
        "snapshot_id": snapshot_id,
        "node": n["name"],
        "state": join(n["state"]),
        "reason": n["reason"] or None,
        "alloc_cpus": n["alloc_cpus"],
        "alloc_memory_mb": n["alloc_memory"],
        "free_memory_mb": num(n["free_mem"]),
        "cpu_load": num(n["cpu_load"]),
        "gpus_used": sum(count for count, _ in gpus),
        "gpu_idx_used": [i for _, indices in gpus for i in indices],
    }
    return state, {key: n[key] for key in NODE_STATIC}


def config_items(kind: str, data: dict) -> dict[str, Any]:
    """Items of one kind of configuration, keyed by their name."""
    _, key, name = CONFIG[kind]
    # associations carry usage counters, which are not configuration
    return {
        str(item[name]): {k: v for k, v in item.items() if k != "accounting"} for item in data[key]
    }


def share_row(s: dict, snapshot_id: int) -> dict:
    return {
        "snapshot_id": snapshot_id,
        "assoc_id": s["id"],
        "type": join(s["type"]),
        "name": s["name"],
        "parent": s["parent"] or None,
        "shares": num(s["shares"]),
        "shares_normalized": num(s["shares_normalized"]),
        "usage_raw": s["usage"],
        "effective_usage": num(s["effective_usage"]),
        "fairshare_factor": num(s["fairshare"]["factor"]),
        "fairshare_level": num(s["fairshare"]["level"]),
        "tres_usage": {t["name"]: num(t["value"]) for t in s["tres"]["usage"] if num(t["value"])},
    }


def diag(statistics: dict) -> dict:
    """Scalar scheduler statistics; the lists (RPCs per user, ...) are left out."""
    values = {key: num(value) for key, value in statistics.items()}
    return {key: value for key, value in values.items() if not isinstance(value, list | dict)}
