"""HTTP API for the web frontend. Every module is a router under /api/<module>."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ..config import Config
from ..store import Store
from . import gpus, health, jobs, nodes, queue, users

MODULES = {
    "gpus": gpus,
    "nodes": nodes,
    "queue": queue,
    "jobs": jobs,
    "users": users,
    "health": health,
}


def create_app(config: Config, store: Store, web: Path | None = None) -> FastAPI:
    app = FastAPI(title="slurm-lens")
    app.state.config, app.state.store = config, store
    for name, module in MODULES.items():
        app.include_router(module.router, prefix=f"/api/{name}", tags=[name])
    if web:
        # the built frontend; it routes with #/..., so index.html is the only page
        app.mount("/", StaticFiles(directory=web, html=True))
    return app
