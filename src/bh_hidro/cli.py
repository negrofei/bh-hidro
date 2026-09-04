"""CLI. Pipeline commands are stubs until each module is transferred."""

from __future__ import annotations

import argparse
import sys

from bh_hidro import __version__
from bh_hidro.config import get_settings
from bh_hidro.log import setup_logging

_NOT_READY = "Módulo aún no transferido desde bhERA5."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bh-hidro",
        description="Balance hídrico: ingest, cálculo y salidas.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--logmode",
        choices=["debug", "info", "warning", "error"],
        default="info",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Mostrar config e intentar ping a MySQL")
    sub.add_parser("download", help="Descarga ERALand / WRF")
    sub.add_parser("imerg", help="Precipitación IMERG")
    sub.add_parser("balance", help="Cálculo de balance 0p1")
    sub.add_parser("output", help="GeoJSON / tiles")
    sub.add_parser("run", help="Pipeline completo (cuando existan los módulos)")

    args = parser.parse_args(argv)
    settings = get_settings()
    logger = setup_logging(settings.log_dir, level=args.logmode)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "status":
        return _cmd_status(logger, settings)

    logger.info("%s: %s", args.command, _NOT_READY)
    print(_NOT_READY, file=sys.stderr)
    return 2


def _cmd_status(logger, settings) -> int:
    from bh_hidro.db.base import Base
    from bh_hidro.db import models as _models  # noqa: F401

    logger.info("host=%s db=%s", settings.database_host, settings.database_name)
    print(f"database: {settings.database_user}@{settings.database_host}:{settings.database_port}/{settings.database_name}")
    print(f"log_dir:  {settings.log_dir}")
    print(f"down_dir: {settings.down_dir}")
    print(f"out_dir:  {settings.out_dir}")
    print(f"models:   {len(Base.metadata.tables)} tables")
    try:
        import asyncio

        asyncio.run(_ping_mysql(settings))
        print("mysql: ok")
    except Exception as exc:
        print(f"mysql: unreachable ({exc})")
    return 0


async def _ping_mysql(settings) -> None:
    from sqlalchemy import text

    from bh_hidro.db.connection import dispose_engine, engine_to_database

    engine = await engine_to_database(settings)
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    await dispose_engine()


if __name__ == "__main__":
    raise SystemExit(main())
