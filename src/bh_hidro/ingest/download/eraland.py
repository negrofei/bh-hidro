"""ERALand: CDS → GRIB → daily 12–12 → land grid → datos_eraland."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

import xarray as xr

from bh_hidro.ingest.download.cds import download_eraland_grib, grib_path
from bh_hidro.ingest.download.daily import eraland_daily_from_hourly
from bh_hidro.ingest.download.grib import grib_to_netcdf
from bh_hidro.ingest.download.ini import DownloadIni
from bh_hidro.ingest.download.remap import remap_to_land
from bh_hidro.ingest.download.to_db import upsert_eraland
from bh_hidro.ingest.download.windows import clip_eraland, daterange, support_dates

logger = logging.getLogger(__name__)


def daily_path(down_dir: Path, fecha: date) -> Path:
    return down_dir / f"eraland_{fecha.strftime('%Y%m%d')}_daily.nc"


def nc_path(down_dir: Path, fecha: date) -> Path:
    return down_dir / f"eraland_{fecha.strftime('%Y%m%d')}.nc"


async def dates_missing(cfg: DownloadIni, today: date) -> tuple[list[date], list[date]]:
    start, end = clip_eraland(cfg.start, cfg.end, today)
    wanted = set(daterange(start, end))
    try:
        from bh_hidro.db.models.atmospheric import DatoERALand
        from bh_hidro.db.models.geographic import Provincia

        ids = await Provincia.ids_by_names(cfg.provinces)
        loaded = set(await DatoERALand.dates_for_provinces(ids))
    except Exception as exc:
        logger.warning("Could not read ERALand dates from MySQL (%s); assuming empty", exc)
        loaded = set()
    targets = sorted(wanted - loaded)
    return targets, support_dates(targets)


def fetch_and_convert(down_dir: Path, fecha: date) -> Path:
    grib = download_eraland_grib(fecha, grib_path(down_dir, fecha))
    return grib_to_netcdf(grib)


def build_daily(down_dir: Path, fecha: date) -> Path:
    out = daily_path(down_dir, fecha)
    if out.is_file():
        return out
    hourly = [nc_path(down_dir, fecha), nc_path(down_dir, fecha + timedelta(days=1))]
    missing = [p for p in hourly if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"ERALand daily {fecha} needs {missing}")
    tmp = out.with_stem(f"tmp_{fecha}")
    ds = eraland_daily_from_hourly(hourly, fecha)
    ds.to_netcdf(tmp)
    ds.close()
    return remap_to_land(tmp, out)


async def run_eraland(cfg: DownloadIni, today: date | None = None, dry_run: bool = False) -> dict[date, str]:
    today = today or date.today()
    targets, extra = await dates_missing(cfg, today)
    all_dates = sorted(set(targets) | set(extra))
    logger.info("ERALand targets=%s support=%s", targets, extra)
    if dry_run:
        return {d: "dry-run" for d in all_dates}
    if not all_dates:
        logger.info("ERALand up to date")
        return {}

    status: dict[date, str] = {}
    for fecha in all_dates:
        try:
            fetch_and_convert(cfg.down_dir, fecha)
            status[fecha] = "downloaded"
        except Exception as exc:
            logger.error("ERALand fetch %s: %s", fecha, exc)
            status[fecha] = "ERROR"

    ok: list[date] = []
    for fecha in targets:
        if status.get(fecha) == "ERROR" or status.get(fecha + timedelta(days=1)) == "ERROR":
            status[fecha] = "ERROR"
            continue
        try:
            daily = build_daily(cfg.down_dir, fecha)
            with xr.open_dataset(daily) as ds:
                ds.attrs["model"] = "ERALand"
                await upsert_eraland(ds, chunk=cfg.chunk_size)
            status[fecha] = "Listo"
            ok.append(fecha)
        except Exception as exc:
            logger.error("ERALand daily %s: %s", fecha, exc)
            status[fecha] = "ERROR"
    logger.info("ERALand loaded %s dates", len(ok))
    return status
