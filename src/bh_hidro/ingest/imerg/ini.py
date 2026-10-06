"""Parse reports.ini for the IMERG step."""

from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from bh_hidro.config import Settings, get_settings, host_path
from bh_hidro.ingest.download.windows import operative_window


@dataclass
class ImergIni:
    path: Path
    down_dir: Path
    operativo: bool
    late: bool
    early: bool
    calib: bool
    overwrite: bool
    start: date
    end: date
    chunk_size: int
    paralelo: bool
    workers: int

    @property
    def fetch_workers(self) -> int:
        from bh_hidro.ingest.pool import fetch_workers

        return fetch_workers(self.paralelo, self.workers)

    @classmethod
    def load(
        cls,
        path: Path,
        settings: Settings | None = None,
        start: date | None = None,
        end: date | None = None,
        today: date | None = None,
    ) -> ImergIni:
        settings = settings or get_settings()
        parser = ConfigParser()
        if not path.is_file():
            raise FileNotFoundError(path)
        parser.read(path)
        operativo = parser.getboolean("run", "operativo", fallback=True)
        if start is None or end is None:
            if operativo:
                win = operative_window(
                    today or date.today(),
                    settings.delta_days_back,
                    settings.delta_days_forward,
                )
                start = start or win[0]
                end = end or win[1]
            else:
                start = start or datetime.strptime(parser.get("fechas", "fechaini"), "%Y%m%d").date()
                end = end or datetime.strptime(parser.get("fechas", "fechafin"), "%Y%m%d").date()

        down_dir = host_path(Path(parser.get("directorios", "down_dir", fallback=str(settings.down_dir))))
        down_dir.mkdir(parents=True, exist_ok=True)

        return cls(
            path=path,
            down_dir=down_dir,
            operativo=operativo,
            late=parser.getboolean("imerg", "imerg_late", fallback=True),
            early=parser.getboolean("imerg", "imerg_early", fallback=True),
            calib=parser.getboolean("imerg", "imerg_calib", fallback=False),
            overwrite=parser.getboolean("imerg", "overwrite", fallback=False),
            start=start,
            end=end,
            chunk_size=parser.getint("database", "chunk_size", fallback=5000),
            paralelo=parser.getboolean("run", "paralelo", fallback=True),
            workers=parser.getint("run", "workers", fallback=4),
        )
