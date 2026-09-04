"""CDO remap onto the 0.1° land grid."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

LAND_GRID = Path(__file__).with_name("ReticulaLand.grid")


def remap_to_land(src: Path, dest: Path, method: str = "remapdis") -> Path:
    if dest.is_file() and dest.stat().st_size > 0:
        logger.info("%s already remapped", dest.name)
        return dest
    if not LAND_GRID.is_file():
        raise FileNotFoundError(LAND_GRID)

    from cdo import Cdo

    cdo = Cdo()
    tmp = dest.with_stem(dest.stem + "_gridfix")
    griddes = [line.replace("gridtype  = generic", "gridtype  = latlon") for line in cdo.griddes(input=str(src))]
    gridfile = dest.parent / "tmp_griddes.txt"
    gridfile.write_text("\n".join(line.rstrip() for line in griddes) + "\n")
    getattr(cdo, "remapdis")(str(gridfile), input=str(src), output=str(tmp))
    remap = getattr(cdo, method)
    remap(str(LAND_GRID), input=str(tmp), output=str(dest))
    tmp.unlink(missing_ok=True)
    gridfile.unlink(missing_ok=True)
    logger.info("remapped %s", dest.name)
    return dest


def remap_bil_to_land(src: Path, dest: Path) -> Path:
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    if not LAND_GRID.is_file():
        raise FileNotFoundError(LAND_GRID)
    from cdo import Cdo

    Cdo().remapbil(str(LAND_GRID), input=str(src), output=str(dest))
    return dest
