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


def tifs_to_daily(files: list[Path], fecha: date, latency: str) -> xr.DataArray:
    arrays = [read_geotiff(Path(f)) for f in files]
    dataset = xr.concat(arrays, dim="time").sortby("time")
    daily = dataset.resample(time="24h", origin="start").sum()
    daily = daily / 10  # early/late stored as 0.1 mm
    daily["lon"] = daily.lon.round(2)
    daily["lat"] = daily.lat.round(2)
    daily.attrs.update({"units": "mm", "latency": latency, "fecha": fecha.isoformat()})
    for name in ("band", "spatial_ref"):
        if name in daily.coords or name in getattr(daily, "variables", {}):
            daily = daily.drop_vars(name)
    return daily
