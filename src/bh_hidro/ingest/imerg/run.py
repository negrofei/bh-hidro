"""Sequential IMERG Late then Early onto the land grid. Calib is weekly FTP."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import xarray as xr

from bh_hidro.config import Settings, get_settings
from bh_hidro.ingest.imerg.dates import best_origin_by_date, clip_imerg
from bh_hidro.ingest.imerg.ini import ImergIni
from bh_hidro.ingest.imerg.origins import DAILY_ORDER, ORIGIN, better_or_equal_already
from bh_hidro.ingest.imerg.pluvio import EXPECTED_3HR, filter_trihorario
from bh_hidro.ingest.imerg.remap import CALIB_GRID

logger = logging.getLogger(__name__)


def daily_nc(down_dir: Path, fecha: date, latency: str) -> Path:
    return down_dir / f"imerg_daily_{fecha.strftime('%Y%m%d')}_{latency}_from3hr.nc"


def land_nc(down_dir: Path, fecha: date, latency: str) -> Path:
    suffix = "0p1" if latency == "calib" else "from3hr_0p1"
    return down_dir / f"imerg_daily_{fecha.strftime('%Y%m%d')}_{latency}_{suffix}.nc"


def calib_raw_nc(down_dir: Path, fecha: date) -> Path:
    return down_dir / f"imerg_daily_{fecha.strftime('%Y%m%d')}_calib.nc"


def enabled_latencies(cfg: ImergIni) -> list[str]:
    flags = {"late": cfg.late, "early": cfg.early}
    return [name for name in DAILY_ORDER if flags[name]]


async def loaded_origins(start: date, end: date) -> dict[date, int]:
    try:
        from bh_hidro.db.models.atmospheric import Imerg0p1

        df = await Imerg0p1.dates_loaded(start.isoformat(), end.isoformat())
        return best_origin_by_date(df)
    except Exception as exc:
        logger.warning("Could not read imerg0p1 dates from MySQL (%s); assuming empty", exc)
        return {}


def ingest_one(cfg: ImergIni, fecha: date, latency: str, settings: Settings) -> None:
    from bh_hidro.ingest.imerg.geotiff import tifs_to_daily
    from bh_hidro.ingest.imerg.http import download_files, list_remote
    from bh_hidro.ingest.imerg.remap import remap_imerg_to_land

    remotes = list_remote(latency, fecha, settings=settings)
    wanted = filter_trihorario(fecha, remotes, latency)
    if len(wanted) != EXPECTED_3HR:
        raise FileNotFoundError(f"{latency} {fecha}: {len(wanted)}/{EXPECTED_3HR} 3h files")

    tifs = download_files(wanted, latency, cfg.down_dir, overwrite=cfg.overwrite, settings=settings)
    raw = daily_nc(cfg.down_dir, fecha, latency)
    if not raw.is_file() or cfg.overwrite:
        daily = tifs_to_daily(tifs, fecha, latency)
        daily.to_netcdf(raw)
    dest = land_nc(cfg.down_dir, fecha, latency)
    remap_imerg_to_land(raw, dest, overwrite=cfg.overwrite)


def ingest_calib_one(cfg: ImergIni, fecha: date, settings: Settings, available: set[str]) -> None:
    from bh_hidro.ingest.imerg.ftp import download_ajuste, filename
    from bh_hidro.ingest.imerg.geotiff import calib_tif_to_daily
    from bh_hidro.ingest.imerg.remap import remap_imerg_to_land

    if filename(fecha) not in available:
        raise FileNotFoundError(f"calib {fecha}: {filename(fecha)} not on FTP")
    tif = download_ajuste(fecha, cfg.down_dir, overwrite=cfg.overwrite, settings=settings)
    raw = calib_raw_nc(cfg.down_dir, fecha)
    if not raw.is_file() or cfg.overwrite:
        daily = calib_tif_to_daily(tif, fecha)
        daily.to_netcdf(raw)
    dest = land_nc(cfg.down_dir, fecha, "calib")
    remap_imerg_to_land(raw, dest, overwrite=cfg.overwrite, grid=CALIB_GRID)


async def upsert_one(cfg: ImergIni, fecha: date, latency: str) -> int:
    from bh_hidro.ingest.download.to_db import upsert_imerg0p1

    dest = land_nc(cfg.down_dir, fecha, latency)
    with xr.open_dataset(dest) as ds:
        return await upsert_imerg0p1(ds.load(), ORIGIN[latency], chunk=cfg.chunk_size)


def _reports_path(settings: Settings, calib: bool) -> Path:
    if calib and settings.reports_weekly_config.is_file():
        return settings.reports_weekly_config
    return settings.reports_config


async def run_imerg_calib(
    cfg: ImergIni,
    settings: Settings,
    dry_run: bool,
    today: date,
) -> dict[str, dict[date, str]]:
    from bh_hidro.ingest.imerg.ftp import filename, list_remote

    wanted = clip_imerg(cfg.start, cfg.end, today)
    already = await loaded_origins(cfg.start, cfg.end) if wanted else {}
    origin = ORIGIN["ImergCalib"]
    logger.info("IMERG Calib dates=%s", wanted)
    available: set[str] = set()
    if wanted and not dry_run:
        available = list_remote(settings)
    out: dict[str, dict[date, str]] = {"calib": {}}
    for fecha in wanted:
        if better_or_equal_already(already.get(fecha), origin):
            out["calib"][fecha] = "skip"
            continue
        if dry_run:
            out["calib"][fecha] = "dry-run"
            continue
        if filename(fecha) not in available:
            out["calib"][fecha] = "missing"
            continue
        try:
            ingest_calib_one(cfg, fecha, settings, available)
            rows = await upsert_one(cfg, fecha, "calib")
            out["calib"][fecha] = f"ok:{rows}"
        except FileNotFoundError as exc:
            logger.warning("IMERG calib %s missing: %s", fecha, exc)
            out["calib"][fecha] = "missing"
        except Exception as exc:
            logger.error("IMERG calib %s failed: %s", fecha, exc)
            out["calib"][fecha] = "ERROR"
    return out


async def run_imerg(
    settings: Settings | None = None,
    start: date | None = None,
    end: date | None = None,
    dry_run: bool = False,
    today: date | None = None,
    calib: bool = False,
) -> dict[str, dict[date, str]]:
    settings = settings or get_settings()
    today = today or date.today()
    cfg = ImergIni.load(
        _reports_path(settings, calib),
        settings=settings,
        start=start,
        end=end,
        today=today,
    )
    if calib or (cfg.calib and not cfg.late and not cfg.early):
        return await run_imerg_calib(cfg, settings, dry_run, today)

    wanted = clip_imerg(cfg.start, cfg.end, today)
    already = await loaded_origins(cfg.start, cfg.end) if wanted else {}
    latencies = enabled_latencies(cfg)
    logger.info("IMERG dates=%s latencies=%s calib=%s", wanted, latencies, cfg.calib)
    if cfg.calib:
        logger.info("IMERG Calib is weekly; skipped in the daily run")

    out: dict[str, dict[date, str]] = {name: {} for name in latencies}
    done: set[date] = set()
    for latency in latencies:
        origin = ORIGIN[latency]
        for fecha in wanted:
            if fecha in done:
                continue
            if better_or_equal_already(already.get(fecha), origin):
                out[latency][fecha] = "skip"
                continue
            if dry_run:
                out[latency][fecha] = "dry-run"
                done.add(fecha)
                continue
            try:
                ingest_one(cfg, fecha, latency, settings)
                rows = await upsert_one(cfg, fecha, latency)
                out[latency][fecha] = f"ok:{rows}"
                done.add(fecha)
            except Exception as exc:
                logger.error("IMERG %s %s failed: %s", latency, fecha, exc)
                out[latency][fecha] = "ERROR"
    return out
