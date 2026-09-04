"""NASA PPS HTTP listing and GeoTIFF download."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

from bh_hidro.config import Settings, get_settings
from bh_hidro.ingest.imerg.dates import needs_next_month_listing

logger = logging.getLogger(__name__)

SERVERS = {
    "early": "https://jsimpsonhttps.pps.eosdis.nasa.gov",
    "late": "https://jsimpsonhttps.pps.eosdis.nasa.gov",
    "final": "https://arthurhouhttps.pps.eosdis.nasa.gov",
}
PATHS = {
    "early": "/imerg/gis/early/YYYY/MM",
    "late": "/imerg/gis/YYYY/MM",
    "final": "/gpmdata/YYYY/MM/DD/gis",
}


def credentials(settings: Settings | None = None) -> tuple[str, str]:
    settings = settings or get_settings()
    user = settings.imerg_user
    password = settings.imerg_password
    if not user or not password:
        raise FileNotFoundError("Set IMERG_USER and IMERG_PASSWORD (NASA PPS email for both).")
    return user, password


def _path(latency: str, fecha: date) -> str:
    path = PATHS[latency]
    return (
        path.replace("YYYY", f"{fecha.year}")
        .replace("MM", f"{fecha.month:02d}")
        .replace("DD", f"{fecha.day:02d}")
    )


def _session(settings: Settings | None = None):
    import requests

    user, password = credentials(settings)
    session = requests.Session()
    session.auth = (user, password)
    return session


def list_files(latency: str, fecha: date, settings: Settings | None = None) -> list[str]:
    from bs4 import BeautifulSoup

    session = _session(settings)
    path = _path(latency, fecha)
    url = f"{SERVERS[latency]}{path}"
    logger.info("IMERG list %s", url)
    try:
        response = session.get(url, timeout=60)
        response.raise_for_status()
    except Exception as exc:
        logger.error("IMERG list failed %s: %s", url, exc)
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    hrefs = [a.get("href") for a in soup.find_all("a") if a.get("href")]
    return [f"{path}/{name}" for name in hrefs if name and not name.endswith("/")]


def list_remote(latency: str, fecha: date, settings: Settings | None = None) -> list[str]:
    files = list_files(latency, fecha, settings=settings)
    if needs_next_month_listing(fecha):
        files += list_files(latency, fecha + timedelta(days=1), settings=settings)
    return files


def download_files(
    remote_paths: list[str],
    latency: str,
    outdir: Path,
    overwrite: bool = False,
    settings: Settings | None = None,
) -> list[Path]:
    session = _session(settings)
    saved: list[Path] = []
    for remote in remote_paths:
        dest = outdir / Path(remote).name
        if dest.is_file() and not overwrite:
            saved.append(dest)
            continue
        url = f"{SERVERS[latency]}/{remote.lstrip('/')}"
        logger.info("IMERG get %s", url)
        response = session.get(url, stream=True, timeout=120)
        response.raise_for_status()
        with dest.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=8192):
                handle.write(chunk)
        saved.append(dest)
    return saved
