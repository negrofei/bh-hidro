"""Parse balance.ini."""

from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from bh_hidro.balance.sources import ETP_PRIORITY, PRECIP_PRIORITY, parse_priority
from bh_hidro.config import Settings, get_settings
from bh_hidro.ingest.download.windows import operative_window


@dataclass
class BalanceIni:
    path: Path
    provinces: list[str]
    crops: list[str]
    operativo: bool
    start: date
    end: date
    chunk_size: int
    paralelo: bool
    workers: int
    raise_if_data_gap: bool
    first_day: date
    precip_priority: list[str]
    etp_priority: list[str]

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
    ) -> BalanceIni:
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

        crops_raw = parser.get("cultivo", "tipo_cultivo", fallback="all")
        crops = [c.strip() for c in crops_raw.split("|") if c.strip()] if crops_raw != "all" else ["all"]
        return cls(
            path=path,
            provinces=[p.strip() for p in parser.get("region", "provincias").split("|") if p.strip()],
            crops=crops,
            operativo=operativo,
            start=start,
            end=end,
            chunk_size=parser.getint("run", "chunks_formi", fallback=10000),
            paralelo=parser.getboolean("run", "paralelo", fallback=True),
            workers=parser.getint("run", "workers", fallback=7),
            # True (default): refuse days without yesterday. False: continue from last loaded.
            raise_if_data_gap=parser.getboolean("run", "raise_if_data_gap", fallback=True),
            first_day=settings.first_day,
            precip_priority=parse_priority(
                parser.get("data_providers", "precipitation_priority_0p1", fallback=None),
                PRECIP_PRIORITY,
            ),
            etp_priority=parse_priority(
                parser.get("data_providers", "etp_priority_0p1", fallback=None),
                ETP_PRIORITY,
            ),
        )
