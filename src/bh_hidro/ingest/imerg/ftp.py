"""SMN FTP for weekly IMERG Calib (Ajuste_YYYYMMDD.tif)."""

from __future__ import annotations

import logging
from datetime import date
from ftplib import FTP, all_errors
from pathlib import Path

from bh_hidro.config import Settings, get_settings

logger = logging.getLogger(__name__)

DATA_PATH = "/SQPE-OBS/datos"
FILE_PATTERN = "Ajuste_{ymd}.tif"


def filename(fecha: date) -> str:
    return FILE_PATTERN.format(ymd=fecha.strftime("%Y%m%d"))


def credentials(settings: Settings | None = None) -> tuple[str, str, str]:
    settings = settings or get_settings()
    host = settings.imerg_ftp_host
    user = settings.imerg_ftp_user
    password = settings.imerg_ftp_password
    if not host or not user or not password:
        raise FileNotFoundError(
            "Set IMERG_FTP_HOST, IMERG_FTP_USER and IMERG_FTP_PASSWORD for Calib."
        )
    return host, user, password


def list_remote(settings: Settings | None = None) -> set[str]:
    host, user, password = credentials(settings)
    ftp = FTP()
    try:
        ftp.connect(host, 21, timeout=60)
        ftp.login(user=user, passwd=password)
        ftp.cwd(DATA_PATH)
        names = ftp.nlst()
    except all_errors as exc:
        logger.error("IMERG Calib FTP list failed: %s", exc)
        raise
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()
    return {name for name in names if name.startswith("Ajuste_") and name.endswith(".tif")}


def download_ajuste(
    fecha: date,
    outdir: Path,
    overwrite: bool = False,
    settings: Settings | None = None,
) -> Path:
    dest = outdir / filename(fecha)
    if dest.is_file() and dest.stat().st_size > 0 and not overwrite:
        logger.info("%s already downloaded", dest.name)
        return dest
    host, user, password = credentials(settings)
    remote = f"{DATA_PATH}/{filename(fecha)}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    ftp = FTP()
    try:
        ftp.connect(host, 21, timeout=60)
        ftp.login(user=user, passwd=password)
        with dest.open("wb") as handle:
            ftp.retrbinary(f"RETR {remote}", handle.write)
    except all_errors as exc:
        dest.unlink(missing_ok=True)
        raise FileNotFoundError(f"IMERG Calib {filename(fecha)}: {exc}") from exc
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()
    if not dest.is_file() or dest.stat().st_size == 0:
        raise FileNotFoundError(f"IMERG Calib download empty: {dest}")
    logger.info("downloaded %s", dest.name)
    return dest
