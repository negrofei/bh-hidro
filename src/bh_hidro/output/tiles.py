"""tippecanoe GeoJSON → MBTiles. PNG is not part of the cron."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def tippecanoe_available() -> bool:
    return shutil.which("tippecanoe") is not None


def geojson_to_mbtiles(geojson: Path, dest_dir: Path, min_zoom: int = 5, max_zoom: int = 9) -> Path | None:
    if not geojson.is_file():
        raise FileNotFoundError(geojson)
    if not tippecanoe_available():
        logger.warning("tippecanoe not on PATH; skipping tiles for %s", geojson.name)
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    mbtiles = dest_dir / geojson.with_suffix(".mbtiles").name
    cmd = [
        "tippecanoe",
        "-o",
        str(mbtiles),
        str(geojson),
        f"--minimum-zoom={min_zoom}",
        f"--maximum-zoom={max_zoom}",
        "--force",
    ]
    logger.info("%s", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return mbtiles
