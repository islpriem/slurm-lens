"""Database connection."""

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from .models import Base


class Store:
    """Engine and sessions for one database."""

    def __init__(self, url: URL | str):
        self.engine = create_engine(url)
        self.session = sessionmaker(self.engine)

    def create(self) -> None:
        Base.metadata.create_all(self.engine)
