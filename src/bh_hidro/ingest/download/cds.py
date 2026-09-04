"""CDS ERA5-Land hourly GRIB."""

from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path

from bh_hidro.domain import cds_area

logger = logging.getLogger(__name__)

ERLAND_VARS = [
    "2m_dewpoint_temperature",
    "2m_temperature",
    "surface_net_solar_radiation",
    "surface_net_thermal_radiation",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "surface_pressure",
    "total_precipitation",
    "potential_evaporation",
]

HOURS = [f"{h:02d}:00" for h in range(24)]


def grib_path(down_dir: Path, fecha: date) -> Path:
    return down_dir / f"eraland_{fecha.strftime('%Y%m%d')}.grib"


def download_eraland_grib(fecha: date, outfile: Path, area: list[float] | None = None) -> Path:
    if outfile.is_file() and outfile.stat().st_size > 0:
        logger.info("%s already exists", outfile.name)
        return outfile

    import cdsapi

    rc = os.getenv("CDSAPI_RC")
    if rc and not Path(rc).is_file():
        raise FileNotFoundError(f"CDSAPI_RC not found: {rc}")

    client = cdsapi.Client()
    params = {
        "product_type": ["reanalysis"],
        "data_format": "grib",
        "download_format": "unarchived",
        "variable": ERLAND_VARS,
        "area": area or cds_area(),
        "year": [fecha.strftime("%Y")],
        "month": [fecha.strftime("%m")],
        "day": [fecha.strftime("%d")],
        "time": HOURS,
    }
    logger.info("CDS retrieve reanalysis-era5-land for %s", fecha)
    client.retrieve("reanalysis-era5-land", params).download(target=str(outfile))
    return outfile
