"""Async session helper."""

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bh_hidro.db.connection import engine_to_database


@asynccontextmanager
async def get_session():
    engine = await engine_to_database()
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
