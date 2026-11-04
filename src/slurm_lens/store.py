"""Database connection and migrations."""

from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import Connection, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

MIGRATIONS = Path(__file__).with_name("migrations")


def alembic_config(connection: Connection) -> AlembicConfig:
    """Alembic settings in code, so no alembic.ini is needed."""
    config = AlembicConfig()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.attributes["connection"] = connection
    return config


class Store:
    """Engine, sessions and schema migrations for one database."""

    def __init__(self, url: URL | str):
        self.engine = create_engine(url)
        self.session = sessionmaker(self.engine)

    def migrate(self) -> None:
        with self.engine.begin() as connection:
            command.upgrade(alembic_config(connection), "head")

    def revision(self, message: str) -> None:
        """Generate the next migration from the difference between models and database."""
        number = len(list((MIGRATIONS / "versions").glob("*.py"))) + 1
        with self.engine.begin() as connection:
            config = alembic_config(connection)
            command.revision(config, message, autogenerate=True, rev_id=f"{number:04d}")
