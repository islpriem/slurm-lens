"""Command line: migrate the database and collect snapshots."""

import logging
from pathlib import Path

import click

from .collector import Collector
from .config import Config
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
