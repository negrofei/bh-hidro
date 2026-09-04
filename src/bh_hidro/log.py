"""Process logging. Named log.py so it does not shadow the stdlib logging module."""

import logging
from pathlib import Path


def setup_logging(log_dir: Path, name: str = "bh_hidro", level: str = "INFO") -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    numeric = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    file_handler = logging.FileHandler(log_dir / f"{name}.log")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger
