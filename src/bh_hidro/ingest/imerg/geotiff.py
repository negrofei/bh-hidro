"""GeoTIFF 3 h → daily 12–12 (mm)."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import numpy as np
import xarray as xr

from bh_hidro.domain import ARG_PAR_URU
from bh_hidro.ingest.imerg.pluvio import timestamp_from_name

logger = logging.getLogger(__name__)


def read_geotiff(path: Path, bounds: list[float] | None = None) -> xr.DataArray:
    import rioxarray

    lonmin, lonmax, latmin, latmax = bounds or ARG_PAR_URU
    da = rioxarray.open_rasterio(path)
    da = da.assign_coords(time=timestamp_from_name(path.name))
    da = da.squeeze("band").rename("precip").rename({"x": "lon", "y": "lat"})
    if (np.diff(da.lat.values) < 0).all():
        da = da.sortby("lat")
    da = da.sel(lon=slice(lonmin, lonmax), lat=slice(latmin, latmax))
    return da


def daily_scale(latency: str) -> float:
    """Late/Early GeoTIFFs are 0.1 mm. Calib FTP Ajuste_*.tif is already mm."""
    return 1.0 if latency == "calib" else 0.1


def tifs_to_daily(files: list[Path], fecha: date, latency: str) -> xr.DataArray:
    arrays = [read_geotiff(Path(f)) for f in files]
    dataset = xr.concat(arrays, dim="time").sortby("time")
    daily = dataset.resample(time="24h", origin="start").sum()
    daily = daily * daily_scale(latency)
    daily["lon"] = daily.lon.round(2)
    daily["lat"] = daily.lat.round(2)
    daily.attrs.update({"units": "mm", "latency": latency, "fecha": fecha.isoformat()})
    for name in ("band", "spatial_ref"):
        if name in daily.coords or name in getattr(daily, "variables", {}):
            daily = daily.drop_vars(name)
    return daily


def calib_tif_to_daily(path: Path, fecha: date, bounds: list[float] | None = None) -> xr.DataArray:
    import pandas as pd
    import rioxarray

    lonmin, lonmax, latmin, latmax = bounds or ARG_PAR_URU
    da = rioxarray.open_rasterio(path)
    da = da.squeeze("band").rename("precip").rename({"x": "lon", "y": "lat"})
    if (np.diff(da.lat.values) < 0).all():
        da = da.sortby("lat")
    da = da.sel(lon=slice(lonmin, lonmax), lat=slice(latmin, latmax))
    da = da.expand_dims(time=[pd.Timestamp(fecha)])
    da["lon"] = da.lon.round(2)
    da["lat"] = da.lat.round(2)
    da = da.where(da >= 1e-2, 0)
    da.attrs.update({"units": "mm", "latency": "calib", "fecha": fecha.isoformat()})
    for name in ("band", "spatial_ref"):
        if name in da.coords or name in getattr(da, "variables", {}):
            da = da.drop_vars(name)
    return da
