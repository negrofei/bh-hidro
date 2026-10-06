"""Parse output.ini."""

from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from bh_hidro.config import Settings, get_settings, host_path
from bh_hidro.ingest.download.windows import operative_window


@dataclass
class OutputIni:
    path: Path
    out_dir: Path
    tiles_dir: Path
    provinces: list[str]
    crops: list[str]
    variable: str
    operativo: bool
    geojson: bool
    start: date
    end: date
    min_zoom: int
    max_zoom: int

    @classmethod
    def load(
        cls,
        path: Path,
        settings: Settings | None = None,
        start: date | None = None,
        end: date | None = None,
        today: date | None = None,
    ) -> OutputIni:
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
                    settings.delta_days_back_output,
                    settings.delta_days_forward_output,
                )
                start = start or win[0]
                end = end or win[1]
            else:
                start = start or datetime.strptime(parser.get("fechas", "fechaini"), "%Y%m%d").date()
                end = end or datetime.strptime(parser.get("fechas", "fechafin"), "%Y%m%d").date()
        out_dir = host_path(Path(parser.get("directorios", "out_dir", fallback=str(settings.out_dir))))
        out_dir.mkdir(parents=True, exist_ok=True)
        tiles_dir = out_dir / "tmp"
        tiles_dir.mkdir(parents=True, exist_ok=True)
        crops_raw = parser.get("balance_hidrico", "cultivos", fallback="all")
        return cls(
            path=path,
            out_dir=out_dir,
            tiles_dir=tiles_dir,
            provinces=[p.strip() for p in parser.get("salida", "provincias").split("|") if p.strip()],
            crops=[c.strip() for c in crops_raw.split("|") if c.strip()],
            variable=parser.get("balance_hidrico", "variable_balance", fallback="agua_util"),
            operativo=operativo,
            geojson=parser.getboolean("salida", "geojson", fallback=True),
            start=start,
            end=end,
            min_zoom=5,
            max_zoom=9,
        )
