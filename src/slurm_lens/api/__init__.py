"""HTTP API for the web frontend. Every module is a router under /api/<module>."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from ..config import Config
from ..store import Store
from . import gpus, health, jobs, nodes, queue, timeline, users

MODULES = {
    "gpus": gpus,
    "nodes": nodes,
    "queue": queue,
    "jobs": jobs,
    "users": users,
    "timeline": timeline,
    "health": health,
}


class Frontend(StaticFiles):
    """The built frontend. It routes in the browser, so other paths get its fallback page."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404 or path.startswith("api/"):
                raise
            return await super().get_response("200.html", scope)


def create_app(config: Config, store: Store, web: Path | None = None) -> FastAPI:
    app = FastAPI(title="SlurmLens")
    app.state.config, app.state.store = config, store
    app.add_middleware(GZipMiddleware)
    for name, module in MODULES.items():
        app.include_router(module.router, prefix=f"/api/{name}", tags=[name])
    if web:
        app.mount("/", Frontend(directory=web))
    return app
