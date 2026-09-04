"""Parse download.ini plus Settings paths."""

from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from bh_hidro.config import Settings, get_settings
from bh_hidro.ingest.download.windows import operative_window


@dataclass
class DownloadIni:
    path: Path
    parser: ConfigParser
    down_dir: Path
    log_dir: Path
    operativo: bool
    eraland: bool
    wrf: bool
    provinces: list[str]
    start: date
    end: date
    max_tries: int
    chunk_size: int
    erase: bool

    @classmethod
    def load(
        cls,
        path: Path,
        settings: Settings | None = None,
        start: date | None = None,
        end: date | None = None,
        today: date | None = None,
    ) -> DownloadIni:
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

        provinces = [p.strip() for p in parser.get("region", "provincias").split("|") if p.strip()]
        down_dir = Path(parser.get("directorios", "down_dir", fallback=str(settings.down_dir)))
        log_dir = Path(parser.get("directorios", "log_dir", fallback=str(settings.log_dir)))
        try:
            down_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            down_dir = Path(settings.down_dir)
            down_dir.mkdir(parents=True, exist_ok=True)
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            log_dir = Path(settings.log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)

        return cls(
            path=path,
            parser=parser,
            down_dir=down_dir,
            log_dir=log_dir,
            operativo=operativo,
            eraland=parser.getboolean("productos", "eraland", fallback=True),
            wrf=parser.getboolean("productos", "wrf", fallback=True),
            provinces=provinces,
            start=start,
            end=end,
            max_tries=parser.getint("run", "max_tries", fallback=1),
            chunk_size=parser.getint("run", "database_chunk_size", fallback=10000),
            erase=parser.getboolean("run", "erase", fallback=True),
        )
