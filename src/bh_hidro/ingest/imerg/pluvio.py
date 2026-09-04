"""Pluviometric 12–12 file filter for IMERG 3-hourly GeoTIFFs."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path

EXPECTED_3HR = 8


def timestamp_from_name(file: str) -> datetime:
    day = datetime.strptime(re.search(r"\d{8}", file).group(), "%Y%m%d").date()
    clock = datetime.strptime(re.search(r"E\d{6}", file).group()[1:], "%H%M%S")
    stamp = datetime(day.year, day.month, day.day, clock.hour, clock.minute, clock.second)
    return stamp + timedelta(seconds=1)


def pluviometric_slots(fecha: date, step: timedelta = timedelta(hours=3)) -> list[datetime]:
    start = datetime(fecha.year, fecha.month, fecha.day, 12)
    end = start + timedelta(days=1)
    n = int((end - start) / step)
    return [start + step * i for i in range(1, n + 1)]


def filter_trihorario(fecha: date, files: list[str | Path], latency: str) -> list[str]:
    letter = "E" if latency == "early" else "L"
    nxt = fecha + timedelta(days=1)
    pattern = rf"3B-HHR-{letter}.+(?:{fecha.strftime('%Y%m%d')}|{nxt.strftime('%Y%m%d')}).+\.3hr\.tif"
    names = [str(f) for f in files]
    matches = sorted(f for f in names if re.search(pattern, f))
    slots = set(pluviometric_slots(fecha))
    return [f for f in matches if timestamp_from_name(f) in slots]
