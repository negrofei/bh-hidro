"""CDO: native IMERG grid, then land 0.1°."""

from __future__ import annotations

import logging
from pathlib import Path

from bh_hidro.ingest.download.remap import LAND_GRID

logger = logging.getLogger(__name__)

IMERG_GRID = Path(__file__).with_name("imergDataGrid.txt")


def remap_imerg_to_land(src: Path, dest: Path, overwrite: bool = False) -> Path:
    if dest.is_file() and dest.stat().st_size > 0 and not overwrite:
        logger.info("%s already remapped", dest.name)
        return dest
    if not IMERG_GRID.is_file():
        raise FileNotFoundError(IMERG_GRID)
    if not LAND_GRID.is_file():
        raise FileNotFoundError(LAND_GRID)
    if not src.is_file():
        raise FileNotFoundError(src)

    from cdo import Cdo

    cdo = Cdo()
    tmp = dest.with_stem(f"tmp_imerg_{src.stem}")
    try:
        cdo.remapdis(str(IMERG_GRID), input=str(src), output=str(tmp))
        if not tmp.is_file() or tmp.stat().st_size < 1024:
            raise RuntimeError(f"IMERG grid remap produced empty file: {tmp}")
        if dest.is_file():
            dest.unlink()
        cdo.remapdis(str(LAND_GRID), input=str(tmp), output=str(dest))
    finally:
        tmp.unlink(missing_ok=True)
    if not dest.is_file() or dest.stat().st_size < 1024:
        raise RuntimeError(f"land remap produced empty file: {dest}")
    logger.info("remapped %s", dest.name)
    return dest
