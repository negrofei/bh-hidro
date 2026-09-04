"""Async MySQL engine. Models arrive with the schemas transfer."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from bh_hidro.config import Settings, get_settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None


class DatabaseConfig:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    @property
    def url(self) -> str:
        return self.settings.database_url()


async def engine_to_database(settings: Settings | None = None) -> AsyncEngine:
    global _engine
    if _engine is None:
        cfg = DatabaseConfig(settings)
        logger.info("Creating MySQL engine for %s", cfg.settings.database_host)
        _engine = create_async_engine(
            cfg.url,
            poolclass=NullPool,
            pool_pre_ping=True,
        )
    return _engine


async def dispose_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
