"""SMN WRF on unsigned S3 (smn-ar-wrf)."""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

BUCKET = "smn-ar-wrf"
CYCLE = "12"
REMOTE_PARENT = "DATA/WRF/DET/YYYY/mm/dd/CC"
HOURLY_TMPL = "WRFDETAR_01H_YYYYmmdd_CC_HHH.nc"
DAILY_TMPL = "WRFDETAR_24H_YYYYmmdd_CC_HHH.nc"


def _sub(template: str, when: date, hour: int | None = None) -> str:
    text = (
        template.replace("YYYY", when.strftime("%Y"))
        .replace("mm", when.strftime("%m"))
        .replace("dd", when.strftime("%d"))
        .replace("CC", CYCLE)
        .replace("YYYYmmdd", when.strftime("%Y%m%d"))
    )
    if hour is not None:
        if hour < 1:
            raise ValueError(f"WRF forecast hour must be >= 1, got {hour}")
        text = re.sub("HHH", f"{hour:03d}", text)
    return text


def init_cycle(valid: date, as_of: date) -> date:
    """Cycle that forecasts onto valid. Never an init after the valid date."""
    return as_of if valid > as_of else valid


def forecast_hours(valid: date, init: date) -> range:
    if init > valid:
        raise ValueError(f"WRF init {init} is after valid {valid}; forecasts only look forward")
    fcst = (valid - init).days
    hours = range(1 + fcst * 24, (fcst + 1) * 24 + 1)
    if min(hours) < 1 or max(hours) > 72:
        raise ValueError(f"WRF cycle {init} cannot reach {valid} (hours {min(hours)}-{max(hours)})")
    return hours


def remote_keys(valid: date, init: date) -> tuple[list[str], str]:
    hours = forecast_hours(valid, init)
    parent = _sub(REMOTE_PARENT, init)
    hourly = [f"{parent}/{_sub(HOURLY_TMPL, init, h)}" for h in hours]
    daily = f"{parent}/{_sub(DAILY_TMPL, init, (valid - init).days + 1)}"
    return hourly, daily


def _client():
    from boto3.session import Session
    from botocore import UNSIGNED
    from botocore.client import Config

    return Session().client("s3", config=Config(signature_version=UNSIGNED, max_pool_connections=200))


def download_object(s3, key: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 0:
        logger.debug("skip existing %s", dest.name)
        return
    logger.info("S3 get s3://%s/%s", BUCKET, key)
    s3.download_file(BUCKET, key, str(dest))


def download_keys(s3, keys: list[str], down_dir: Path, workers: int) -> None:
    from bh_hidro.ingest.pool import first_error, map_threads

    def one(key: str) -> str:
        download_object(s3, key, down_dir / Path(key).name)
        return key

    err = first_error(map_threads(one, keys, workers, desc="WRF-S3"))
    if err is not None:
        raise err


def download_valid_day(
    valid: date,
    down_dir: Path,
    as_of: date | None = None,
    max_back: int = 3,
    workers: int = 4,
) -> date:
    """Download the cycle that forecasts onto valid, then earlier inits if that run is missing."""
    as_of = as_of or date.today()
    init = init_cycle(valid, as_of)
    s3 = _client()
    last_error: Exception | None = None
    for _ in range(max_back):
        try:
            hourly, daily = remote_keys(valid, init)
        except ValueError as exc:
            raise RuntimeError(f"Could not download WRF for {valid}") from (last_error or exc)
        try:
            download_keys(s3, [*hourly, daily], down_dir, workers)
            return init
        except Exception as exc:
            last_error = exc
            logger.warning(
                "WRF %s from cycle %s failed (%s), trying previous init (still forecasting onto %s)",
                valid,
                init,
                exc,
                valid,
            )
            init = init - timedelta(days=1)
    raise RuntimeError(f"Could not download WRF for {valid}") from last_error
