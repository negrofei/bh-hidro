"""Create bh_hidro schema and copy reference tables from the running prod MySQL.

Does not copy operative series (ERALand, WRF, IMERG, balance). Does not drop fdc_database.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from bh_hidro.config import Settings, get_settings
from bh_hidro.db.base import Base
from bh_hidro.db import models as _models  # noqa: F401
from bh_hidro.db.models.grids import OrigenImerg
from bh_hidro.db.tables import REFERENCE_TABLES

logger = logging.getLogger(__name__)


@dataclass
class CopyResult:
    created: bool
    copied: dict[str, int]
    skipped: dict[str, int]


def _ident(name: str) -> str:
    return "`" + name.replace("`", "") + "`"


async def _scalar(engine, sql: str, **params):
    async with engine.connect() as conn:
        return await conn.scalar(text(sql), params)


async def _execute_as(url: str, statements: list[str]) -> None:
    engine = create_async_engine(url, poolclass=NullPool, pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            for sql in statements:
                await conn.execute(text(sql))
    finally:
        await engine.dispose()


async def ensure_database(settings: Settings) -> None:
    db = _ident(settings.database_name)
    create_sql = (
        f"CREATE DATABASE IF NOT EXISTS {db} "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    grant_sql = (
        f"GRANT ALL PRIVILEGES ON {db}.* TO "
        f"'{settings.database_user}'@'%'"
    )
    try:
        await _execute_as(settings.database_url(database="mysql"), [create_sql])
        return
    except Exception as exc:
        logger.warning(
            "CREATE DATABASE as %s failed (%s)", settings.database_user, exc
        )
    if not settings.mysql_root_password:
        raise RuntimeError(
            "No pude crear la base. Corré scripts/ensure_database.sh en el host "
            f"(container {settings.mysql_container}) o exportá MYSQL_ROOT_PASSWORD."
        )
    await _execute_as(
        settings.admin_url(user="root", password=settings.mysql_root_password),
        [create_sql, grant_sql, "FLUSH PRIVILEGES"],
    )


async def create_schema(settings: Settings) -> None:
    engine = create_async_engine(settings.database_url(), poolclass=NullPool, pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


async def _table_count(engine, database: str, table: str) -> int | None:
    try:
        return int(
            await _scalar(
                engine,
                f"SELECT COUNT(*) FROM {_ident(database)}.{_ident(table)}",
            )
            or 0
        )
    except Exception:
        return None


def _refuse_bad_copy(settings: Settings) -> None:
    if not settings.same_mysql_instance():
        raise ValueError(
            "Bootstrap --from-mysql copia en la misma instancia MySQL. "
            f"source={settings.source_database_host or settings.database_host}:"
            f"{settings.source_port} dest={settings.database_host}:{settings.database_port}"
        )
    if settings.source_database_name == settings.database_name:
        raise ValueError(
            f"source and dest database are both {settings.database_name}; refusing to copy onto itself"
        )


async def copy_reference_tables(
    settings: Settings,
    force: bool = False,
    dry_run: bool = False,
) -> CopyResult:
    _refuse_bad_copy(settings)

    # Connect to the source schema so dry-run works before bh_hidro exists.
    engine = create_async_engine(
        settings.database_url(database=settings.source_database_name),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    copied: dict[str, int] = {}
    skipped: dict[str, int] = {}
    try:
        for table in REFERENCE_TABLES:
            if table not in Base.metadata.tables:
                logger.warning("ORM has no table %s, skipping", table)
                continue
            src_n = await _table_count(engine, settings.source_database_name, table)
            dst_n = await _table_count(engine, settings.database_name, table)
            if src_n is None:
                logger.warning("Source table %s.%s missing", settings.source_database_name, table)
                skipped[table] = -1
                continue
            if dst_n and dst_n > 0 and not force:
                skipped[table] = dst_n
                continue
            columns = [c.name for c in Base.metadata.tables[table].columns]
            col_sql = ", ".join(_ident(c) for c in columns)
            if dry_run:
                copied[table] = src_n
                continue
            async with engine.begin() as conn:
                await conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
                if force and dst_n:
                    await conn.execute(
                        text(f"TRUNCATE TABLE {_ident(settings.database_name)}.{_ident(table)}")
                    )
                await conn.execute(
                    text(
                        f"INSERT INTO {_ident(settings.database_name)}.{_ident(table)} ({col_sql}) "
                        f"SELECT {col_sql} FROM {_ident(settings.source_database_name)}.{_ident(table)}"
                    )
                )
                await conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            copied[table] = src_n
            logger.info("copied %s (%s rows)", table, src_n)
    finally:
        await engine.dispose()
    return CopyResult(created=True, copied=copied, skipped=skipped)


async def seed_origen_imerg(settings: Settings) -> int:
    from bh_hidro.db.connection import dispose_engine, engine_to_database

    await dispose_engine()
    await engine_to_database(settings)
    existing = await OrigenImerg.read_all()
    if not existing.empty:
        await dispose_engine()
        return 0
    await OrigenImerg.upsert_df(pd.DataFrame(OrigenImerg.SEED))
    await dispose_engine()
    return len(OrigenImerg.SEED)


async def run_bootstrap(
    settings: Settings | None = None,
    from_mysql: bool = True,
    create: bool = True,
    force: bool = False,
    dry_run: bool = False,
) -> CopyResult:
    settings = settings or get_settings()
    if from_mysql:
        _refuse_bad_copy(settings)
    if create and not dry_run:
        await ensure_database(settings)
        await create_schema(settings)
    if from_mysql:
        result = await copy_reference_tables(settings, force=force, dry_run=dry_run)
    else:
        result = CopyResult(created=create, copied={}, skipped={})
    if not dry_run:
        await seed_origen_imerg(settings)
    return result
