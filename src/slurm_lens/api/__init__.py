"""HTTP API for the web frontend. Every module is a router under /api/<module>."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ..config import Config
from ..store import Store
from . import health, stats

MODULES = {"health": health, "stats": stats}


def create_app(config: Config, store: Store, web: Path | None = None) -> FastAPI:
    app = FastAPI(title="slurm-lens")
    for name, module in MODULES.items():
        app.include_router(module.router(config, store), prefix=f"/api/{name}", tags=[name])
    if web:
        # the built frontend; it routes with #/..., so index.html is the only page
        app.mount("/", StaticFiles(directory=web, html=True))
    return app
