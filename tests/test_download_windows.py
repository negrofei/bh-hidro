from datetime import date, timedelta

from bh_hidro.domain import ARG_PAR_URU, cds_area
from bh_hidro.ingest.download.s3_wrf import forecast_hours, remote_keys
from bh_hidro.ingest.download.windows import (
    clip_eraland,
    daterange,
    operative_window,
    support_dates,
    wrf_dates,
)


def test_operative_window():
    start, end = operative_window(date(2026, 9, 4), days_back=7, days_forward=1)
    assert start == date(2026, 8, 28)
    assert end == date(2026, 9, 5)


def test_clip_eraland_lag():
    start, end = clip_eraland(date(2026, 8, 28), date(2026, 9, 5), today=date(2026, 9, 4))
    assert end == date(2026, 8, 28)


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
