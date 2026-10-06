from datetime import date, timedelta

import pandas as pd
import xarray as xr

from bh_hidro.domain import ARG_PAR_URU, cds_area
from bh_hidro.ingest.download.daily import concat_netcdf
from bh_hidro.ingest.download.nomads_gfs import forecast_hours as gfs_forecast_hours
from bh_hidro.ingest.download.nomads_gfs import init_cycle as gfs_init_cycle
from bh_hidro.ingest.download.nomads_gfs import local_grib_name, remote_flux_url
from bh_hidro.ingest.download.s3_wrf import forecast_hours, init_cycle, remote_keys
from bh_hidro.ingest.download.windows import (
    clip_eraland,
    daterange,
    gfs_dates,
    operative_window,
    support_dates,
    wrf_dates,
)


def test_operative_window():
    start, end = operative_window(date(2026, 9, 4), days_back=7, days_forward=1)
    assert start == date(2026, 8, 28)
    assert end == date(2026, 9, 5)


def test_clip_eraland_lag():
    start, end = clip_eraland(date(2026, 8, 20), date(2026, 9, 5), today=date(2026, 9, 4))
    assert start == date(2026, 8, 20)
    assert end == date(2026, 8, 28)


def test_clip_eraland_does_not_snap_future_request_backward():
    start, end = clip_eraland(date(2026, 9, 3), date(2026, 9, 5), today=date(2026, 9, 4))
    assert start > end
    assert daterange(start, end) == []


def test_support_dates_are_next_day_only():
    targets = [date(2026, 8, 20), date(2026, 8, 21)]
    assert support_dates(targets) == [date(2026, 8, 22)]


def test_daterange_inclusive():
    assert daterange(date(2026, 1, 1), date(2026, 1, 3)) == [
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 3),
    ]


def test_wrf_fills_after_reanalysis():
    today = date(2026, 9, 4)
    start, end = date(2026, 8, 20), date(2026, 9, 7)
    got = wrf_dates(start, end, today, already=set())
    assert date(2026, 8, 28) not in got
    assert date(2026, 8, 29) in got
    assert max(got) == today + timedelta(hours=72)


def test_wrf_skips_already_loaded():
    today = date(2026, 9, 4)
    got = wrf_dates(date(2026, 8, 20), date(2026, 9, 7), today, already={date(2026, 8, 29)})
    assert date(2026, 8, 29) not in got


def test_cds_area_order():
    assert cds_area(ARG_PAR_URU) == [-19.0, -73.75, -56.0, -52.75]


def test_wrf_s3_keys_for_valid_day():
    hours = list(forecast_hours(date(2026, 9, 4), date(2026, 9, 4)))
    assert hours[0] == 1 and hours[-1] == 24
    hourly, daily = remote_keys(date(2026, 9, 4), date(2026, 9, 4))
    assert hourly[0].endswith("WRFDETAR_01H_20260904_12_001.nc")
    assert daily.endswith("WRFDETAR_24H_20260904_12_001.nc")


def test_wrf_past_valid_uses_that_days_cycle():
    today = date(2026, 9, 4)
    valid = date(2026, 9, 2)
    init = init_cycle(valid, today)
    assert init == valid
    hours = list(forecast_hours(valid, init))
    assert hours[0] == 1 and hours[-1] == 24
    hourly, daily = remote_keys(valid, init)
    assert "2026/09/02/12/" in hourly[0]
    assert hourly[0].endswith("WRFDETAR_01H_20260902_12_001.nc")
    assert daily.endswith("WRFDETAR_24H_20260902_12_001.nc")
    assert "_-" not in hourly[0]


def test_wrf_future_valid_uses_today_looking_forward():
    today = date(2026, 9, 4)
    valid = date(2026, 9, 6)
    init = init_cycle(valid, today)
    assert init == today
    hours = list(forecast_hours(valid, init))
    assert hours[0] == 49 and hours[-1] == 72
    hourly, daily = remote_keys(valid, init)
    assert "2026/09/04/12/" in hourly[0]
    assert hourly[0].endswith("WRFDETAR_01H_20260904_12_049.nc")
    assert daily.endswith("WRFDETAR_24H_20260904_12_003.nc")


def test_wrf_refuses_init_after_valid():
    import pytest

    with pytest.raises(ValueError, match="look forward"):
        forecast_hours(date(2026, 9, 2), date(2026, 9, 4))


def test_concat_netcdf_loads_without_dask(tmp_path):
    times = pd.date_range("2000-01-01", periods=2, freq="h")
    first = xr.Dataset({"tp": ("time", [0.1])}, coords={"time": times[:1]})
    second = xr.Dataset({"tp": ("time", [0.2])}, coords={"time": times[1:]})
    a = tmp_path / "a.nc"
    b = tmp_path / "b.nc"
    first.to_netcdf(a)
    second.to_netcdf(b)
    got = concat_netcdf([a, b])
    assert list(got.tp.values) == [0.1, 0.2]
    assert len(got.time) == 2


def test_gfs_fills_after_reanalysis_beyond_wrf():
    today = date(2026, 9, 4)
    got = gfs_dates(date(2026, 8, 20), date(2026, 9, 20), today, already=set())
    assert date(2026, 8, 28) not in got
    assert date(2026, 8, 29) in got
    assert max(got) == today + timedelta(hours=384)


def test_gfs_skips_already_loaded():
    today = date(2026, 9, 4)
    got = gfs_dates(date(2026, 8, 20), date(2026, 9, 20), today, already={date(2026, 8, 29)})
    assert date(2026, 8, 29) not in got


def test_gfs_nomads_paths_and_hours():
    today = date(2026, 9, 4)
    valid = date(2026, 9, 6)
    init = gfs_init_cycle(valid, today)
    assert init == today
    hours = gfs_forecast_hours(valid, init)
    assert hours[0] == 49 and hours[-1] == 72
    assert local_grib_name(init, 49) == "gfs.20260904.sfluxgrbf049.grib2"
    url = remote_flux_url(init, 49)
    assert "gfs.20260904/12/atmos/gfs.t12z.sfluxgrbf049.grib2" in url


def test_gfs_idx_range_merge():
    from bh_hidro.ingest.download.nomads_gfs import _merge_ranges, _parse_idx

    raw = "\n".join(
        [
            "1:0:d=2026090412:UGRD:10 m above ground:1 hour fcst:",
            "2:100:d=2026090412:VGRD:10 m above ground:1 hour fcst:",
            "3:250:d=2026090412:TMP:2 m above ground:1 hour fcst:",
        ]
    )
    lines = _parse_idx(raw)
    assert lines[0].endswith(":range=0-99")
    assert lines[1].endswith(":range=100-249")
    assert lines[2].endswith(":range=250-")
    matched = [ln for ln in lines if "UGRD" in ln or "VGRD" in ln]
    assert _merge_ranges(matched) == "0-249"
