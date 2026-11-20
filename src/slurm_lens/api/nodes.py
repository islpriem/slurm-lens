"""Nodes: their state, and how much of their GPUs, CPUs and memory is allocated."""

from collections import Counter
from statistics import mean

from fastapi import APIRouter
from sqlalchemy import select

from ..models import JobRecord, JobRecordNode, NodeSnapshot, Snapshot
from .query import allocated, capacity, nodes
from .scope import Scope, ScopeDep
from .view import GRAY, PALETTE, RED, Chart, Table, Tile, View, box, box_note, pie, series

STATES = {"allocated": PALETTE[0], "mixed": PALETTE[3], "idle": PALETTE[2], "unavailable": RED}
RESOURCES = {"GPUs": JobRecord.gpus, "CPUs": JobRecord.cpus, "memory": JobRecord.memory_mb}

router = APIRouter()


@router.get("")
def view(scope: ScopeDep) -> View:
    cluster = Cluster(scope)
    panels = [cluster.states(), cluster.over_time(), cluster.allocation(), cluster.table()]
    return View(cluster.tiles(), panels)


def state(value: str) -> str:
    """A few groups of the compound Slurm states, e.g. 'MIXED,PLANNED' is mixed."""
    if any(flag in value for flag in ("DOWN", "DRAIN", "FAIL", "NOT_RESPONDING")):
        return "unavailable"
    first = value.split(",")[0].lower()
    return first if first in STATES else "other"


class Cluster:
    """The nodes as configured now, their latest state and the allocated share per hour."""

    def __init__(self, scope: Scope):
        self.scope = scope
        self.nodes = nodes(scope.session)
        # GPU nodes by model, the model with the most GPUs first
        models = [model for model, _ in capacity(self.nodes).most_common()]
        gpu_nodes = [node for node in self.nodes if node.gpus]
        self.gpu_nodes = sorted(gpu_nodes, key=lambda node: (models.index(node.model), node.name))
        latest = Snapshot.latest(scope.session, "ok")
        query = select(NodeSnapshot).where(NodeSnapshot.snapshot_id == (latest and latest.id))
        self.latest = {node.node: node for node in scope.session.scalars(query)}
        # allocated share of every node per resource and hour
        self.shares = {}
        for name, column in RESOURCES.items():
            used = allocated(scope, JobRecordNode.node, resource=column)
            self.shares[name] = {
                node.name: [100 * used.get((h, node.name), 0) / node.size(column)
                            for h in scope.hours]
                for node in self.nodes
                if node.size(column)
            }  # fmt: skip

    def average(self, resource: str, nodes=None) -> float:
        """Allocated share of the given nodes (all by default) over the whole period."""
        sizes = {node.name: node.size(RESOURCES[resource]) for node in nodes or self.nodes}
        shares = self.shares[resource]
        used = sum(mean(shares[name]) * size for name, size in sizes.items() if name in shares)
        return used / (sum(sizes.values()) or 1)

    def now(self, allocated: str, resource: str) -> float:
        """Allocated share of all nodes in the latest snapshot."""
        used = sum(getattr(node, allocated) for node in self.latest.values())
        return 100 * used / (sum(node.size(RESOURCES[resource]) for node in self.nodes) or 1)

    def tiles(self) -> list[Tile]:
        down = [name for name, node in self.latest.items() if state(node.state) == "unavailable"]
        return [
            Tile("Nodes", len(self.nodes), f"{len(self.gpu_nodes)} with GPUs"),
            Tile("Unavailable now", len(down), ", ".join(down), "warn" if down else "ok"),
            Tile("CPUs allocated", f"{self.average('CPUs'):.0f} %",
                 f"{self.now('alloc_cpus', 'CPUs'):.0f} % now"),
            Tile("Memory allocated", f"{self.average('memory'):.0f} %",
                 f"{self.now('alloc_memory_mb', 'memory'):.0f} % now"),
        ]  # fmt: skip

    def states(self) -> Chart:
        counts = Counter(state(node.state) for node in self.latest.values())
        colors = STATES | {"other": GRAY}
        return pie("Node states now", {s: counts[s] for s in colors}, colors)

    def over_time(self) -> Chart:
        """Nodes per state in every snapshot of the period."""
        period = Snapshot.taken_at.between(self.scope.start, self.scope.end)
        query = select(Snapshot.taken_at, NodeSnapshot.state).join(NodeSnapshot)
        rows = self.scope.session.execute(
            query.where(Snapshot.status == "ok", period).order_by(Snapshot.id)
        )
        counts = {}
        for taken_at, value in rows:
            counts.setdefault(taken_at, Counter())[state(value)] += 1
        values = {s: [c[s] for c in counts.values()] for s in STATES}
        unavailable = [c["unavailable"] for c in counts.values()] or [0]
        return Chart("Nodes per state", "area", list(counts), series(values, STATES),
                     unit=" nodes", note="From the snapshots of the collector.",
                     stats={"unavailable on average": f"{mean(unavailable):.1f}"},
                     stacked=True)  # fmt: skip

    def allocation(self) -> Chart:
        """GPUs can stay idle when the CPUs or the memory of their node are taken."""
        x = [f"{node.name} · {node.model}" for node in self.gpu_nodes]
        values = {
            resource: [box(self.shares[resource][node.name]) for node in self.gpu_nodes]
            for resource in RESOURCES
        }
        stats = {r: f"{self.average(r, self.gpu_nodes):.0f} %" for r in RESOURCES}
        return Chart("Allocation of the GPU nodes", "box", x, series(values), unit=" %",
                     note=box_note("hours"), stats=stats, y_max=100, wide=True)  # fmt: skip

    def table(self) -> Table:
        rows = [
            [node.name, f"{node.gpus} × {node.model}" if node.gpus else None, node.cpus,
             round(node.memory_mb / 1024),
             state(self.latest[node.name].state) if node.name in self.latest else None,
             *(mean(self.shares[r][node.name]) if node.name in self.shares[r] else None
               for r in RESOURCES)]
            for node in self.nodes
        ]  # fmt: skip
        columns = ["Node", "GPUs", "CPUs", "Memory (GB)", "State now", "GPUs allocated (%)",
                   "CPUs allocated (%)", "Memory allocated (%)"]  # fmt: skip
        return Table("Nodes", columns, rows)
