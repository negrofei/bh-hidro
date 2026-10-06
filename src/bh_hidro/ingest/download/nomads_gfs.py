"""NOMADS GFS 0.25° sflux: inventory + HTTP byte-range download. No Perl."""

from __future__ import annotations

import logging
import re
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

from bh_hidro.ingest.pool import map_threads

logger = logging.getLogger(__name__)

HOST = "nomads.ncep.noaa.gov"
CYCLE = "12"
AVAILABLE_HOURS = list(range(1, 121)) + list(range(123, 387, 3))
MAX_FCST_HOUR = 384
MIN_SIZE = 10_000_000

FLUX_VARS = (
    ":UGRD:10 m above ground:",
    ":VGRD:10 m above ground:",
    ":DPT:2 m above ground:",
    ":TMP:2 m above ground:",
    ":SPFH:2 m above ground:",
    ":USWRF:surface:{h} hour fcst:",
    ":ULWRF:surface:{h} hour fcst:",
    ":DSWRF:surface:{h} hour fcst:",
    ":DLWRF:surface:{h} hour fcst:",
    ":PRES:surface:",
    ":PRATE:surface:",
)


def init_cycle(valid: date, as_of: date | None = None) -> date:
    as_of = as_of or date.today()
    return as_of if valid > as_of else valid


def forecast_hours(valid: date, init: date) -> list[int]:
    if init > valid:
        raise ValueError(f"GFS init {init} cannot look forward from valid {valid}")
    fcst = (valid - init).days
    wanted = list(range(1 + fcst * 24, (fcst + 1) * 24 + 1))
    if max(wanted) > MAX_FCST_HOUR:
        raise ValueError(f"GFS horizon {MAX_FCST_HOUR}h too short for {valid} from {init}")
    available = set(AVAILABLE_HOURS)
    if all(h in available for h in wanted):
        return wanted
    return [h for h in wanted if h in available]


def local_grib_name(init: date, hour: int) -> str:
    return f"gfs.{init.strftime('%Y%m%d')}.sfluxgrbf{hour:03d}.grib2"


def remote_flux_url(init: date, hour: int) -> str:
    ymd = init.strftime("%Y%m%d")
    path = f"/pub/data/nccf/com/gfs/prod/gfs.{ymd}/{CYCLE}/atmos/gfs.t{CYCLE}z.sfluxgrbf{hour:03d}.grib2"
    return f"https://{HOST}{path}"


def _parse_idx(text: str) -> list[str]:
    """Turn a wgrib2 .idx into lines with :range=from-to."""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    if any(":range=" in ln for ln in lines):
        return lines

    starts: list[tuple[int, str]] = []
    for line in lines:
        parts = line.split(":", 2)
        if len(parts) < 2 or not parts[1].isdigit():
            raise ValueError(f"bad GFS idx line: {line[:80]}")
        starts.append((int(parts[1]), line))

    out: list[str] = []
    for i, (start, line) in enumerate(starts):
        if i + 1 < len(starts):
            end = starts[i + 1][0] - 1
            out.append(f"{line}:range={start}-{end}")
        else:
            out.append(f"{line}:range={start}-")
    return out


def _merge_ranges(matched: list[str]) -> str:
    last_from = ""
    last_to: int | str = -100
    chunks: list[str] = []
    for line in matched:
        m = re.search(r":range=([0-9]*)-([0-9]*)", line)
        if not m:
            m_open = re.search(r":range=([0-9]*)-$", line)
            if not m_open:
                continue
            frm, to = m_open.group(1), ""
        else:
            frm, to = m.group(1), m.group(2)
        if (
            last_from != ""
            and isinstance(last_to, int)
            and last_to != -100
            and frm.isdigit()
            and last_to + 1 == int(frm)
        ):
            last_to = int(to) if to != "" else ""
            continue
        if last_from != "":
            chunks.append(f"{last_from}-{last_to}" if last_to != "" else f"{last_from}-")
        last_from = frm
        last_to = int(to) if to != "" else ""
    if last_from != "":
        chunks.append(f"{last_from}-{last_to}" if last_to != "" else f"{last_from}-")
    return ",".join(chunks)


def _var_patterns(hour: int) -> str:
    return "|".join(v.format(h=hour) for v in FLUX_VARS)


def download_flux_hour(init: date, hour: int, dest: Path, max_tries: int = 1, sleep_s: int = 60) -> Path:
    """Download one sflux GRIB subset via HTTP Range."""
    if dest.is_file() and dest.stat().st_size >= MIN_SIZE:
        logger.info("GFS already on disk %s", dest.name)
        return dest

    url = remote_flux_url(init, hour)
    idx_url = f"{url}.idx"
    pattern = _var_patterns(hour)
    last_err: Exception | None = None
    for attempt in range(max(1, max_tries)):
        if attempt:
            import time

            wait = sleep_s * attempt
            logger.warning("retry %s %s after %ss", attempt, dest.name, wait)
            time.sleep(wait)
        try:
            inv = subprocess.run(
                ["curl", "-f", "-s", "-k", idx_url],
                check=True,
                capture_output=True,
                text=True,
            )
            lines = _parse_idx(inv.stdout)
            matched = [ln for ln in lines if re.search(pattern, ln)]
            if not matched:
                raise FileNotFoundError(f"no inventory matches for {dest.name}")
            ranges = _merge_ranges(matched)
            if not ranges:
                raise FileNotFoundError(f"empty byte range for {dest.name}")
            tmp = dest.with_suffix(dest.suffix + ".tmp")
            subprocess.run(
                ["curl", "-f", "-s", "-k", "-r", ranges, url, "-o", str(tmp)],
                check=True,
                capture_output=True,
                text=True,
            )
            tmp.rename(dest)
            if dest.stat().st_size < 1000:
                dest.unlink(missing_ok=True)
                raise RuntimeError(f"tiny GFS download {dest.name}")
            logger.info("downloaded %s (%s bytes)", dest.name, dest.stat().st_size)
            return dest
        except Exception as exc:
            last_err = exc
            logger.error("GFS download %s: %s", dest.name, exc)
            dest.unlink(missing_ok=True)
    raise RuntimeError(f"GFS download failed {dest.name}: {last_err}")


def download_valid_day(
    valid: date,
    down_dir: Path,
    as_of: date | None = None,
    workers: int = 4,
    max_tries: int = 1,
) -> date:
    """Download all sflux hours for one pluviometric valid day. Returns init cycle date."""
    as_of = as_of or date.today()
    init = init_cycle(valid, as_of)
    hours = forecast_hours(valid, init)
    down_dir.mkdir(parents=True, exist_ok=True)

    def one(hour: int) -> Path:
        return download_flux_hour(init, hour, down_dir / local_grib_name(init, hour), max_tries=max_tries)

    rows = map_threads(one, hours, workers, desc="gfs-nomads")
    errors = [err for _h, _p, err in rows if err is not None]
    if errors:
        raise errors[0]
    return init


def available_init_window(now: datetime | None = None) -> tuple[date, date]:
    """GFS on NOMADS ~3 h after cycle; keep ~9 days of history."""
    now = now or datetime.now()
    lo = (now - timedelta(days=9)).date()
    hi = now.date() if now.hour > 15 else (now - timedelta(days=1)).date()
    return lo, hi
