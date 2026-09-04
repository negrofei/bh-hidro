"""Sequential IMERG Late then Early onto the land grid. No 0.25°, no threads."""

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

logger = logging.getLogger(__name__)


def daily_nc(down_dir: Path, fecha: date, latency: str) -> Path:
    return down_dir / f"imerg_daily_{fecha.strftime('%Y%m%d')}_{latency}_from3hr.nc"


def land_nc(down_dir: Path, fecha: date, latency: str) -> Path:
    return down_dir / f"imerg_daily_{fecha.strftime('%Y%m%d')}_{latency}_from3hr_0p1.nc"


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


async def upsert_one(cfg: ImergIni, fecha: date, latency: str) -> int:
    from bh_hidro.ingest.download.to_db import upsert_imerg0p1

    dest = land_nc(cfg.down_dir, fecha, latency)
    with xr.open_dataset(dest) as ds:
        return await upsert_imerg0p1(ds.load(), ORIGIN[latency], chunk=cfg.chunk_size)


async def run_imerg(
    settings: Settings | None = None,
    start: date | None = None,
    end: date | None = None,
    dry_run: bool = False,
    today: date | None = None,
) -> dict[str, dict[date, str]]:
    settings = settings or get_settings()
    today = today or date.today()
    cfg = ImergIni.load(settings.reports_config, settings=settings, start=start, end=end, today=today)
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
