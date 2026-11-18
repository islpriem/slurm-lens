"""Command line: migrate the database, collect snapshots, check them, serve the web frontend."""

import logging
from datetime import UTC, datetime
from pathlib import Path

import click
import uvicorn
from sqlalchemy import func, select

from .api import create_app
from .client import token_expiry
from .collector import MARGIN, Collector, history_windows
from .config import Config
from .models import HistoryWindow, JobRecord, Snapshot
from .store import Store


@click.group()
@click.option(
    "--config",
    "path",
    envvar="SLURM_LENS_CONFIG",
    default="/etc/slurm-lens/slurm-lens.ini",
    show_default=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.pass_context
def main(context: click.Context, path: Path):
    """Collect Slurm scheduling data into PostgreSQL."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = Config.load(path)
    context.obj = config, Store(config.database())


@main.command()
@click.pass_obj
def migrate(obj):
    """Bring the database schema up to date."""
    _, store = obj
    store.migrate()


@main.command()
@click.option("--once", is_flag=True, help="Collect one snapshot and stop.")
@click.pass_obj
def collect(obj, once: bool):
    """Migrate, then collect a snapshot every interval."""
    config, store = obj
    store.migrate()
    collector = Collector(config, store)
    collector.abort_unfinished()
    if once:
        collector.run()
    else:
        collector.forever()


@main.command()
@click.pass_obj
def status(obj):
    """Show what was collected; exit code 1 if no snapshot succeeded recently."""
    config, store = obj
    now = datetime.now(UTC)
    with store.session() as session:
        last, last_ok = Snapshot.latest(session), Snapshot.latest(session, "ok")
        healthy = Snapshot.healthy(session, config.interval, now)
        complete = set(
            session.scalars(select(HistoryWindow.start_time).where(HistoryWindow.complete))
        )
        records = session.scalar(select(func.count()).select_from(JobRecord))
    if last is None:
        raise click.ClickException("no snapshot yet")
    windows = history_windows(config.history_start, now, config.window, complete, 10**6)
    missing = [w for w in windows if w + config.window + MARGIN <= now]
    click.echo(f"last snapshot    {last.taken_at:%Y-%m-%d %H:%M} {last.status} {last.error or ''}")
    click.echo(f"last ok snapshot {f'{last_ok.taken_at:%Y-%m-%d %H:%M}' if last_ok else 'none'}")
    click.echo(f"history windows  {len(complete)} complete, {len(missing)} missing, {records} jobs")
    try:
        click.echo(f"token expires    {token_expiry(config.token()) or 'unknown'}")
    except (OSError, KeyError):
        click.echo("token            missing")
    if not healthy:
        raise SystemExit(1)


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True)
@click.option("--web", type=click.Path(exists=True, file_okay=False, path_type=Path),
              help="Built frontend to serve next to the API.")  # fmt: skip
@click.pass_obj
def serve(obj, host: str, port: int, web: Path | None):
    """Serve the API for the web frontend."""
    config, store = obj
    uvicorn.run(create_app(config, store, web), host=host, port=port)
