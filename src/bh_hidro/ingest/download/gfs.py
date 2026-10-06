"""GFS: NOMADS sflux → land grid → daily → gfs0p1. Fills after WRF / beyond WRF horizon."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import xarray as xr

from bh_hidro.domain import ARG_PAR_URU, cds_area
from bh_hidro.ingest.download.daily import (
    _squeeze_height,
    concat_netcdf,
    gfs_add_dewpoint,
    gfs_add_radiation,
    gfs_etp,
    gfs_hourly_precip,
    gfs_lon180,
    gfs_temp_to,
    hourly_to_daily,
)
from bh_hidro.ingest.download.ini import DownloadIni
from bh_hidro.ingest.download.nomads_gfs import (
    download_valid_day,
    forecast_hours,
    local_grib_name,
)
from bh_hidro.ingest.download.remap import LAND_GRID
from bh_hidro.ingest.download.to_db import upsert_gfs
from bh_hidro.ingest.download.windows import gfs_dates
from bh_hidro.ingest.pool import CDO_LOCK

logger = logging.getLogger(__name__)

VAR_GRIB2NC = {
    "10u": "u10",
    "10v": "v10",
    "2t": "t2m",
    "2sh": "sh2m",
    "lat": "latitude",
    "lon": "longitude",
}


def daily_out(down_dir: Path, fecha: date) -> Path:
    return down_dir / f"gfs_land_{fecha.strftime('%Y%m%d')}_daily.nc"


def land_nc_name(grib: Path) -> Path:
    return grib.with_name(f"land_{grib.stem}.nc")


def grib_to_land_nc(src: Path, dest: Path) -> Path:
    """GRIB → NetCDF, crop domain, rename, remapbil onto ReticulaLand."""
    if dest.is_file() and dest.stat().st_size > 0:
        logger.info("%s already remapped", dest.name)
        return dest
    if not LAND_GRID.is_file():
        raise FileNotFoundError(LAND_GRID)
    if not src.is_file():
        raise FileNotFoundError(src)

    from cdo import Cdo

    latmax, lonmin, latmin, lonmax = cds_area(ARG_PAR_URU)
    nc = dest.with_suffix(".tmp.nc")
    box = dest.with_suffix(".box.nc")
    renamed = dest.with_suffix(".renamed.nc")
    with CDO_LOCK:
        cdo = Cdo()
        cdo.copy(input=str(src), output=str(nc), options="-f nc")
        cdo.sellonlatbox(f"{lonmin},{lonmax},{latmin},{latmax}", input=str(nc), output=str(box))
        nc.unlink(missing_ok=True)
        cdo.chname(
            ",".join(f"{k},{v}" for k, v in VAR_GRIB2NC.items()),
            input=str(box),
            output=str(renamed),
        )
        box.unlink(missing_ok=True)
        cdo.remapbil(str(LAND_GRID), input=str(renamed), output=str(dest))
        renamed.unlink(missing_ok=True)
    logger.info("remapped %s", dest.name)
    return dest


def assemble_daily(down_dir: Path, valid: date, init: date) -> Path:
    out = daily_out(down_dir, valid)
    if out.is_file():
        return out

    hours = forecast_hours(valid, init)
    hourly = [land_nc_name(down_dir / local_grib_name(init, h)) for h in hours]
    missing = [p for p in hourly if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"missing remapped GFS files for {valid}: {missing[0].name}")

    raw = concat_netcdf(hourly)
    try:
        if "valid_time" in raw.dims or "valid_time" in raw.coords:
            raw = raw.rename({"valid_time": "time"})
        data = gfs_lon180(raw)
        data["t2m"] = gfs_temp_to(data["t2m"], "K")
        data = gfs_add_dewpoint(data)
        data["d2m"] = gfs_temp_to(data["d2m"], "K")
        data = gfs_add_radiation(data)
        data = gfs_hourly_precip(data)

        start = datetime(valid.year, valid.month, valid.day, 12)
        pluvio = data.sel(time=slice(start, start + timedelta(hours=24)))
        means = hourly_to_daily(pluvio, {"u10", "v10", "sp"}, "mean")
        sums = hourly_to_daily(pluvio, {"Rn", "G", "tp"}, "sum")
        mins = hourly_to_daily(pluvio, {"t2m", "d2m"}, "min")
        maxs = hourly_to_daily(pluvio, {"t2m", "d2m"}, "max")
        merged = xr.merge([means, sums, mins, maxs])
        if "time" in merged.dims and merged.sizes.get("time", 1) == 1:
            merged = merged.isel(time=0)

        for name in ("u10", "v10", "t2m_min", "d2m_min", "t2m_max", "d2m_max", "sp", "Rn", "G", "tp"):
            if name in merged:
                merged[name] = _squeeze_height(merged[name])

        merged["etp"] = gfs_etp(merged)
        for var in ("tp", "etp"):
            if var in merged:
                merged[var] = merged[var].clip(min=0)
        day_prono = (valid - init).days
        slim = merged[["tp", "etp", "t2m_min", "t2m_max"]]
        if "time" not in slim.dims:
            slim = slim.expand_dims(time=[np_datetime(valid)])
        slim.attrs["day_prono"] = day_prono
        for old, new in (("latitude", "lat"), ("longitude", "lon")):
            if old in slim.coords or old in slim.dims:
                slim = slim.rename({old: new})
        slim.to_netcdf(out)
        return out
    finally:
        raw.close()


def np_datetime(d: date):
    import numpy as np

    return np.datetime64(d.isoformat())


async def dates_missing(
    cfg: DownloadIni,
    today: date,
    exclude: list[date] | None = None,
    extra: list[date] | None = None,
) -> list[date]:
    try:
        from bh_hidro.db.models.atmospheric import GFS0p1
        from bh_hidro.db.models.geographic import Provincia

        ids = await Provincia.ids_by_names(cfg.provinces)
        loaded = set(await GFS0p1.dates_for_provinces(ids))
    except Exception as exc:
        logger.warning("Could not read GFS dates from MySQL (%s); assuming empty", exc)
        loaded = set()
    wanted = gfs_dates(cfg.start, cfg.end, today, already=loaded)
    extra = extra or []
    exclude = set(exclude or [])
    return sorted((set(wanted) | set(extra)) - loaded - exclude)


async def run_gfs(
    cfg: DownloadIni,
    today: date | None = None,
    exclude: list[date] | None = None,
    extra: list[date] | None = None,
    dry_run: bool = False,
) -> dict[date, str]:
    today = today or date.today()
    targets = await dates_missing(cfg, today, exclude=exclude, extra=extra)
    logger.info("GFS targets=%s", targets)
    if dry_run:
        return {d: "dry-run" for d in targets}
    if not targets:
        logger.info("GFS up to date")
        return {}

    status: dict[date, str] = {}
    for valid in targets:
        try:
            init = download_valid_day(
                valid,
                cfg.down_dir,
                as_of=today,
                workers=cfg.fetch_workers,
                max_tries=cfg.max_tries,
            )
            for hour in forecast_hours(valid, init):
                grib = cfg.down_dir / local_grib_name(init, hour)
                grib_to_land_nc(grib, land_nc_name(grib))
            daily = assemble_daily(cfg.down_dir, valid, init)
            with xr.open_dataset(daily) as ds:
                ds.attrs["model"] = "GFS"
                await upsert_gfs(ds, chunk=cfg.chunk_size, today=today)
            if cfg.erase:
                for hour in forecast_hours(valid, init):
                    grib = cfg.down_dir / local_grib_name(init, hour)
                    grib.unlink(missing_ok=True)
            status[valid] = "Listo"
        except Exception as exc:
            logger.error("GFS %s: %s", valid, exc)
            status[valid] = "ERROR"
    return status
