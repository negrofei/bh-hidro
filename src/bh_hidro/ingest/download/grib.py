"""GRIB → NetCDF via CDO, then rename GRIB short names."""

from __future__ import annotations

import logging
from pathlib import Path

from bh_hidro.ingest.pool import CDO_LOCK

logger = logging.getLogger(__name__)

GRIB_TO_NC = {
    "10u": "u10",
    "10v": "v10",
    "2t": "t2m",
    "2d": "d2m",
    "lat": "latitude",
    "lon": "longitude",
}


class GribError(Exception):
    pass


def grib_to_netcdf(grib_file: Path) -> Path:
    outfile = grib_file.with_suffix(".nc")
    if outfile.is_file() and outfile.stat().st_size > 0:
        logger.info("%s already converted", outfile.name)
        return outfile
    if not grib_file.is_file() or grib_file.stat().st_size == 0:
        raise GribError(f"missing or empty GRIB: {grib_file}")

    from cdo import Cdo

    with CDO_LOCK:
        cdo = Cdo()
        renamed = outfile.with_name(outfile.stem + "_renamed.nc")
        cdo.copy(input=str(grib_file), output=str(outfile), options="-f nc")
        pairs = ",".join(f"{k},{v}" for k, v in GRIB_TO_NC.items())
        cdo.chname(pairs, input=str(outfile), output=str(renamed))
        outfile.unlink()
        renamed.rename(outfile)
    logger.info("converted %s", outfile.name)
    return outfile
