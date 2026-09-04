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
        text = re.sub("HHH", f"{hour:03d}", text)
    return text


def forecast_hours(valid: date, init: date) -> range:
    fcst = (valid - init).days
    return range(1 + fcst * 24, (fcst + 1) * 24 + 1)


def remote_keys(valid: date, init: date) -> tuple[list[str], str]:
    hours = forecast_hours(valid, init)
    if max(hours) > 72:
        raise ValueError(f"WRF cycle {init} cannot reach {valid} (need {max(hours)} h)")
    parent = _sub(REMOTE_PARENT, init)
    hourly = [f"{parent}/{_sub(HOURLY_TMPL, init, h)}" for h in hours]
    daily = f"{parent}/{_sub(DAILY_TMPL, init, (valid - init).days + 1)}"
    return hourly, daily


def _client():
    from boto3.session import Session
    from botocore import UNSIGNED
    from botocore.client import Config

    return Session().client("s3", config=Config(signature_version=UNSIGNED, max_pool_connections=50))


def download_object(s3, key: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 0:
        logger.debug("skip existing %s", dest.name)
        return
    logger.info("S3 get s3://%s/%s", BUCKET, key)
    s3.download_file(BUCKET, key, str(dest))


def download_valid_day(valid: date, down_dir: Path, init: date | None = None, max_back: int = 10) -> date:
    """Download hourly + 24H files. Walk back init date if the cycle is missing."""
    init = init or date.today()
    s3 = _client()
    for _ in range(max_back):
        try:
            hourly, daily = remote_keys(valid, init)
        except ValueError:
            init = init - timedelta(days=1)
            continue
        try:
            for key in hourly:
                download_object(s3, key, down_dir / Path(key).name)
            download_object(s3, daily, down_dir / Path(daily).name)
            return init
        except Exception as exc:
            logger.warning("WRF %s from %s failed (%s), trying previous cycle", valid, init, exc)
            init = init - timedelta(days=1)
    raise RuntimeError(f"Could not download WRF for {valid}")
