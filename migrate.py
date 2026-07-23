import os
from pathlib import Path

from alembic import command
from alembic.config import Config

BASE_DIR = Path(__file__).resolve().parent


def upgrade_database() -> None:
    config = Config(str(BASE_DIR / "alembic.ini"))
    config.set_main_option(
        "sqlalchemy.url",
        os.getenv("DATABASE_URL", "sqlite:///./predict_withfun.db").replace(
            "%",
            "%%",
        ),
    )
    command.upgrade(config, "head")


if __name__ == "__main__":
    upgrade_database()
