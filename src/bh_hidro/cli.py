"""CLI. Operative pipeline: download → imerg → balance → output."""

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
    download = sub.add_parser("download", help="Descarga ERALand / WRF")
    download.add_argument("--dry-run", action="store_true")
    download.add_argument("--start-date", help="YYYYMMDD")
    download.add_argument("--end-date", help="YYYYMMDD")
    imerg = sub.add_parser("imerg", help="Precipitación IMERG Late/Early 0p1")
    imerg.add_argument("--dry-run", action="store_true")
    imerg.add_argument("--start-date", help="YYYYMMDD")
    imerg.add_argument("--end-date", help="YYYYMMDD")
    balance = sub.add_parser("balance", help="Cálculo de balance 0p1")
    balance.add_argument("--dry-run", action="store_true")
    balance.add_argument("--start-date", help="YYYYMMDD")
    balance.add_argument("--end-date", help="YYYYMMDD")
    output = sub.add_parser("output", help="GeoJSON / tiles")
    output.add_argument("--dry-run", action="store_true")
    output.add_argument("--start-date", help="YYYYMMDD")
    output.add_argument("--end-date", help="YYYYMMDD")
    run = sub.add_parser("run", help="Pipeline completo")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--start-date", help="YYYYMMDD")
    run.add_argument("--end-date", help="YYYYMMDD")

    args = parser.parse_args(argv)
    settings = get_settings()
    logger = setup_logging(settings.log_dir, level=args.logmode)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "status":
        return _cmd_status(logger, settings)

    if args.command == "download":
        return _cmd_download(args, settings)

    if args.command == "imerg":
        return _cmd_imerg(args, settings)

    if args.command == "balance":
        return _cmd_balance(args, settings)

    if args.command == "output":
        return _cmd_output(args, settings)

    if args.command == "run":
        return _cmd_run(args, settings)

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


def _parse_ymd(value: str | None):
    if not value:
        return None
    from datetime import datetime

    return datetime.strptime(value, "%Y%m%d").date()


def _cmd_download(args, settings) -> int:
    import asyncio

    from bh_hidro.ingest.download import run_download

    start = _parse_ymd(args.start_date)
    end = _parse_ymd(args.end_date)
    results = asyncio.run(
        run_download(settings=settings, start=start, end=end, dry_run=args.dry_run)
    )
    for product, dates in results.items():
        print(f"{product}: {len(dates)} dates")
        for fecha, status in sorted(dates.items()):
            print(f"  {fecha} {status}")
    if any(status == "ERROR" for dates in results.values() for status in dates.values()):
        return 1
    return 0


def _cmd_imerg(args, settings) -> int:
    import asyncio

    from bh_hidro.ingest.imerg import run_imerg

    start = _parse_ymd(args.start_date)
    end = _parse_ymd(args.end_date)
    results = asyncio.run(
        run_imerg(settings=settings, start=start, end=end, dry_run=args.dry_run)
    )
    for product, dates in results.items():
        print(f"{product}: {len(dates)} dates")
        for fecha, status in sorted(dates.items()):
            print(f"  {fecha} {status}")
    if any(status == "ERROR" for dates in results.values() for status in dates.values()):
        return 1
    return 0


def _print_results(results: dict) -> int:
    for product, dates in results.items():
        print(f"{product}: {len(dates)} dates")
        for fecha, status in sorted(dates.items()):
            print(f"  {fecha} {status}")
    if any(status == "ERROR" for dates in results.values() for status in dates.values()):
        return 1
    return 0


def _cmd_balance(args, settings) -> int:
    import asyncio

    from bh_hidro.balance import run_balance

    start = _parse_ymd(args.start_date)
    end = _parse_ymd(args.end_date)
    results = asyncio.run(
        run_balance(settings=settings, start=start, end=end, dry_run=args.dry_run)
    )
    return _print_results(results)


def _cmd_output(args, settings) -> int:
    import asyncio

    from bh_hidro.output import run_output

    start = _parse_ymd(args.start_date)
    end = _parse_ymd(args.end_date)
    results = asyncio.run(
        run_output(settings=settings, start=start, end=end, dry_run=args.dry_run)
    )
    return _print_results(results)


def _cmd_run(args, settings) -> int:
    codes = [
        _cmd_download(args, settings),
        _cmd_imerg(args, settings),
        _cmd_balance(args, settings),
        _cmd_output(args, settings),
    ]
    if 1 in codes:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
