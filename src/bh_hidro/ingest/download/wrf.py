"""WRF: S3 → land grid → daily → wrf0p1. Fills after last ERALand reanalysis."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import xarray as xr

from bh_hidro.ingest.download.daily import (
    hourly_to_daily,
    wrf_add_radiation,
    wrf_add_vapor,
    wrf_etp,
)
from bh_hidro.ingest.download.ini import DownloadIni
from bh_hidro.ingest.download.remap import remap_bil_to_land
from bh_hidro.ingest.download.s3_wrf import download_valid_day, remote_keys
from bh_hidro.ingest.download.to_db import upsert_wrf
from bh_hidro.ingest.download.windows import wrf_dates

logger = logging.getLogger(__name__)


def daily_out(down_dir: Path, fecha: date) -> Path:
    return down_dir / f"wrf_land_{fecha.strftime('%Y%m%d')}_daily.nc"


def _interp_name(raw: Path) -> Path:
    return raw.with_name(f"land_{raw.stem}_interp.nc")


def assemble_daily(down_dir: Path, valid: date, init: date) -> Path:
    out = daily_out(down_dir, valid)
    if out.is_file():
        return out
    hourly_keys, daily_key = remote_keys(valid, init)
    hourly = [_interp_name(down_dir / Path(k).name) for k in hourly_keys]
    daily24 = _interp_name(down_dir / Path(daily_key).name)
    if not all(p.is_file() for p in hourly) or not daily24.is_file():
        raise FileNotFoundError(f"missing interpolated WRF files for {valid}")

    with xr.open_mfdataset([str(p) for p in hourly]) as raw:
        data = wrf_add_vapor(wrf_add_radiation(raw))
        means = hourly_to_daily(data, {"magViento10", "PSFC", "T2", "HR2", "pres_vap_real"}, "mean").isel(time=0)
        sums = hourly_to_daily(data, {"Rn", "G"}, "sum").isel(time=0)
        mins = hourly_to_daily(data, {"T2"}, "min").isel(time=0)
        maxs = hourly_to_daily(data, {"T2"}, "max").isel(time=0)
        pp = data["PP"][-1, ...]

    with xr.open_dataset(daily24) as t00:
        mins["Tmin"] = xr.DataArray(
            t00["Tmin"].isel(time=0).values, coords=mins.coords, attrs={"units": t00["Tmin"].units}
        )
        tmax_src = t00["Tmax"] if "Tmax" in t00.variables else None
        tmax = t00["Tmax"].isel(time=0).values if tmax_src is not None else maxs["T2_max"].values
        tmax_units = t00["Tmax"].units if tmax_src is not None else t00["Tmin"].units
        maxs["Tmax"] = xr.DataArray(tmax, coords=maxs.coords, attrs={"units": tmax_units})

    sums["tp"] = xr.DataArray(pp.values, coords=sums.coords, attrs={"units": getattr(pp, "units", "mm")})
    merged = xr.merge([means, sums, mins, maxs])
    merged = merged.drop_vars([v for v in ("T2", "T2_max", "T2_min") if v in merged])
    for old, new in (("latitude", "lat"), ("longitude", "lon")):
        if old in merged.coords or old in merged.dims:
            merged = merged.rename({old: new})
    merged["etp"] = wrf_etp(merged)
    merged.attrs["day_prono"] = (valid - init).days
    slim = merged[["tp", "etp"]]
    slim["day_prono"] = (valid - init).days
    slim.to_netcdf(out)
    return out


async def dates_missing(cfg: DownloadIni, today: date, extra: list[date] | None = None) -> list[date]:
    try:
        from bh_hidro.db.models.atmospheric import WRF0p1
        from bh_hidro.db.models.geographic import Provincia

        ids = await Provincia.ids_by_names(cfg.provinces)
        loaded = set(await WRF0p1.dates_for_provinces(ids, day_prono=0))
    except Exception as exc:
        logger.warning("Could not read WRF dates from MySQL (%s); assuming empty", exc)
        loaded = set()
    wanted = wrf_dates(cfg.start, cfg.end, today, already=loaded)
    extra = extra or []
    return sorted(set(wanted) | set(extra) - loaded)


async def run_wrf(
    cfg: DownloadIni,
    today: date | None = None,
    extra: list[date] | None = None,
    dry_run: bool = False,
) -> dict[date, str]:
    today = today or date.today()
    targets = await dates_missing(cfg, today, extra)
    logger.info("WRF targets=%s", targets)
    if dry_run:
        return {d: "dry-run" for d in targets}
    if not targets:
        logger.info("WRF up to date")
        return {}

    status: dict[date, str] = {}
    for valid in targets:
        try:
            init = download_valid_day(valid, cfg.down_dir, init=today)
            hourly_keys, daily_key = remote_keys(valid, init)
            for key in [*hourly_keys, daily_key]:
                raw = cfg.down_dir / Path(key).name
                remap_bil_to_land(raw, _interp_name(raw))
            daily = assemble_daily(cfg.down_dir, valid, init)
            with xr.open_dataset(daily) as ds:
                ds.attrs["model"] = "WRF"
                await upsert_wrf(ds, chunk=cfg.chunk_size, today=today)
            status[valid] = "Listo"
        except Exception as exc:
            logger.error("WRF %s: %s", valid, exc)
            status[valid] = "ERROR"
    return status
