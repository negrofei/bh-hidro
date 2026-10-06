"""Operative date windows for ERALand, WRF and GFS. No I/O."""

from __future__ import annotations

from datetime import date, timedelta


LAG_REANALYSIS = timedelta(days=7)
WRF_MAX_FCST = timedelta(hours=72)
WRF_START = date(2022, 1, 1)
GFS_MAX_FCST = timedelta(hours=384)
GFS_LOOKBACK = timedelta(days=9)


def daterange(start: date, end: date) -> list[date]:
    if start > end:
        return []
    days = (end - start).days
    return [start + timedelta(days=i) for i in range(days + 1)]


def operative_window(
    today: date,
    days_back: int,
    days_forward: int,
) -> tuple[date, date]:
    return today - timedelta(days=days_back), today + timedelta(days=days_forward)


def clip_eraland(start: date, end: date, today: date, lag: timedelta = LAG_REANALYSIS) -> tuple[date, date]:
    """Keep the requested window; never pull days the caller did not ask for.

    ERALand only exists up to today-lag. If the whole request is after that,
    return an empty range (start > end) instead of snapping back to the last day.
    """
    last = today - lag
    if start > last:
        return start, start - timedelta(days=1)
    if end > last:
        end = last
    return start, end


def support_dates(targets: list[date]) -> list[date]:
    """ERALand precip is pluviometric 12–12, so each target needs D+1 hourly GRIB."""
    needed = {d + timedelta(days=1) for d in targets}
    return sorted(needed - set(targets))


def wrf_dates(
    start: date,
    end: date,
    today: date,
    already: set[date] | None = None,
    lag: timedelta = LAG_REANALYSIS,
    max_fcst: timedelta = WRF_MAX_FCST,
    wrf_start: date = WRF_START,
) -> list[date]:
    """Dates after the last reanalysis, through +72 h, not already in wrf0p1."""
    already = already or set()
    window = [d for d in daterange(start, end) if d >= wrf_start]
    if not window:
        return []

    last_rean = today - lag
    horizon = today + max_fcst

    if last_rean in window:
        candidates = window[window.index(last_rean) + 1 :]
    elif last_rean >= min(window):
        candidates = []
    else:
        candidates = window

    candidates = [d for d in candidates if d <= horizon]
    return [d for d in candidates if d not in already]


def gfs_dates(
    start: date,
    end: date,
    today: date,
    already: set[date] | None = None,
    lag: timedelta = LAG_REANALYSIS,
    max_fcst: timedelta = GFS_MAX_FCST,
    lookback: timedelta = GFS_LOOKBACK,
) -> list[date]:
    """Dates after the last reanalysis through GFS horizon, not already in gfs0p1."""
    already = already or set()
    window = daterange(start, end)
    if not window:
        return []

    last_rean = today - lag
    earliest = today - lookback
    horizon = today + max_fcst

    if last_rean in window:
        candidates = window[window.index(last_rean) + 1 :]
    elif last_rean >= min(window):
        candidates = []
    else:
        candidates = window

    candidates = [d for d in candidates if earliest <= d <= horizon]
    return [d for d in candidates if d not in already]
