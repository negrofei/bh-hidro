"""Create / drop mapped tables. Use against an empty DB, not production."""

from bh_hidro.db.base import Base
from bh_hidro.db.connection import engine_to_database
from bh_hidro.db import models as _models  # noqa: F401  — register mappers


async def create_schema() -> None:
    engine = await engine_to_database()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_schema() -> None:
    engine = await engine_to_database()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
