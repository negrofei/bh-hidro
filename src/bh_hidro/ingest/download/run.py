"""Sequential ERALand then WRF. No thread circus, no ERA5/GFS."""

from __future__ import annotations

import logging
from datetime import date

from bh_hidro.config import Settings, get_settings
from bh_hidro.ingest.download.eraland import run_eraland
from bh_hidro.ingest.download.ini import DownloadIni
from bh_hidro.ingest.download.wrf import run_wrf

logger = logging.getLogger(__name__)


async def run_download(
    settings: Settings | None = None,
    start: date | None = None,
    end: date | None = None,
    dry_run: bool = False,
    today: date | None = None,
) -> dict[str, dict[date, str]]:
    settings = settings or get_settings()
    cfg = DownloadIni.load(settings.download_config, settings=settings, start=start, end=end, today=today)
    today = today or date.today()
    out: dict[str, dict[date, str]] = {}
    eraland_errors: list[date] = []
    if cfg.eraland:
        out["eraland"] = await run_eraland(cfg, today=today, dry_run=dry_run)
        eraland_errors = [d for d, status in out["eraland"].items() if status == "ERROR"]
    if cfg.wrf:
        extra = eraland_errors if cfg.eraland else []
        out["wrf"] = await run_wrf(cfg, today=today, extra=extra, dry_run=dry_run)
    return out
