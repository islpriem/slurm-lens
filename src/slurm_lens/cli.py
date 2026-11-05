"""Command line: migrate the database, collect snapshots, check that collecting works."""

import logging
from datetime import UTC, datetime
from pathlib import Path

import click
from sqlalchemy import func, select

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
        last = session.scalars(select(Snapshot).order_by(Snapshot.id.desc()).limit(1)).first()
        last_ok = session.scalar(select(func.max(Snapshot.taken_at)).where(Snapshot.status == "ok"))
        complete = set(
            session.scalars(select(HistoryWindow.start_time).where(HistoryWindow.complete))
        )
        records = session.scalar(select(func.count()).select_from(JobRecord))
    if last is None:
        raise click.ClickException("no snapshot yet")
    windows = history_windows(config.history_start, now, config.window, complete, 10**6)
    missing = [w for w in windows if w + config.window + MARGIN <= now]
    click.echo(f"last snapshot    {last.taken_at:%Y-%m-%d %H:%M} {last.status} {last.error or ''}")
    click.echo(f"last ok snapshot {last_ok:%Y-%m-%d %H:%M}" if last_ok else "last ok snapshot none")
    click.echo(f"history windows  {len(complete)} complete, {len(missing)} missing, {records} jobs")
    if not last_ok or now - last_ok > 3 * config.interval:
        raise SystemExit(1)
