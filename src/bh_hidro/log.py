"""Process logging. Named log.py so it does not shadow the stdlib logging module."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)s [%(processName)s %(name)s] %(message)s"
_NOISY = ("aiomysql", "asyncio", "sqlalchemy.engine")

STEP_LOG_NAMES = {
    "download": "descarga",
    "imerg": "reportes",
    "balance": "balance",
    "output": "output",
    "run": "run",
    "bootstrap": "bootstrap",
    "status": "status",
}


def _numeric_level(level: str) -> int:
    return getattr(logging, level.upper(), logging.INFO)


def _quiet_libraries() -> None:
    for name in _NOISY:
        logging.getLogger(name).setLevel(logging.WARNING)


def _ensure_log_dir(log_dir: Path) -> Path:
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def setup_logging(
    log_dir: Path,
    name: str = "bh_hidro",
    level: str = "INFO",
    logbasename: str | None = None,
) -> logging.Logger:
    """One file per pipeline step, e.g. descarga_20260908_1220.log."""
    log_dir = _ensure_log_dir(log_dir)
    numeric = _numeric_level(level)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    basename = logbasename or name
    logfile = log_dir / f"{basename}_{stamp}.log"

    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.setLevel(numeric)
    logger.propagate = False
    _quiet_libraries()

    formatter = logging.Formatter(_FORMAT)
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)
    file_handler = logging.FileHandler(logfile)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.info("logging to %s", logfile)
    return logger


def setup_process_logging(log_dir: Path, level: str, process_name: str) -> logging.Logger:
    """Own file + stderr for a balance worker. Call only in the child."""
    log_dir = _ensure_log_dir(log_dir)
    numeric = _numeric_level(level)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    logfile = log_dir / f"process_{process_name}_{stamp}.log"
    formatter = logging.Formatter(_FORMAT)

    root = logging.getLogger()
    root.setLevel(numeric)
    root.handlers.clear()
    file_handler = logging.FileHandler(logfile)
    file_handler.setFormatter(formatter)
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    root.addHandler(file_handler)
    root.addHandler(stream)

    package = logging.getLogger("bh_hidro")
    package.setLevel(numeric)
    package.handlers.clear()
    package.propagate = True
    _quiet_libraries()
    package.info("process logging to %s", logfile)
    return package
