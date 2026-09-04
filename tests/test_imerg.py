from datetime import date, datetime, timedelta

import pandas as pd

from bh_hidro.ingest.imerg.dates import best_origin_by_date, clip_imerg, needs_next_month_listing
from bh_hidro.ingest.imerg.origins import ORIGIN, better_or_equal_already
from bh_hidro.ingest.imerg.pluvio import EXPECTED_3HR, filter_trihorario, pluviometric_slots, timestamp_from_name


def test_pluviometric_slots_are_eight():
    slots = pluviometric_slots(date(2026, 9, 3))
    assert len(slots) == EXPECTED_3HR
    assert slots[0] == datetime(2026, 9, 3, 15)
    assert slots[-1] == datetime(2026, 9, 4, 12)


def test_timestamp_from_end_label_plus_one_second():
    name = "3B-HHR-L.MS.MRG.3IMERG.20260903-S120000-E145959.0720.V07B.3hr.tif"
    assert timestamp_from_name(name) == datetime(2026, 9, 3, 15, 0, 0)


def test_filter_trihorario_keeps_pluviometric_day():
    fecha = date(2026, 9, 3)
    files = [
        "3B-HHR-L.MS.MRG.3IMERG.20260903-S120000-E145959.0720.V07B.3hr.tif",
        "3B-HHR-L.MS.MRG.3IMERG.20260903-S150000-E175959.0900.V07B.3hr.tif",
        "3B-HHR-L.MS.MRG.3IMERG.20260903-S180000-E205959.1080.V07B.3hr.tif",
        "3B-HHR-L.MS.MRG.3IMERG.20260903-S210000-E235959.1260.V07B.3hr.tif",
        "3B-HHR-L.MS.MRG.3IMERG.20260904-S000000-E025959.0000.V07B.3hr.tif",
        "3B-HHR-L.MS.MRG.3IMERG.20260904-S030000-E055959.0180.V07B.3hr.tif",
        "3B-HHR-L.MS.MRG.3IMERG.20260904-S060000-E085959.0360.V07B.3hr.tif",
        "3B-HHR-L.MS.MRG.3IMERG.20260904-S090000-E115959.0540.V07B.3hr.tif",
        "3B-HHR-E.MS.MRG.3IMERG.20260903-S120000-E145959.0720.V07B.3hr.tif",
        "3B-HHR-L.MS.MRG.3IMERG.20260903-S090000-E115959.0540.V07B.3hr.tif",
    ]
    got = filter_trihorario(fecha, files, "late")
    assert len(got) == 8
    assert all("3B-HHR-L" in name for name in got)
    assert files[-1] not in got


def test_priority_skips_worse_or_equal_origin():
    assert better_or_equal_already(None, ORIGIN["late"]) is False
    assert better_or_equal_already(ORIGIN["late"], ORIGIN["late"]) is True
    assert better_or_equal_already(ORIGIN["late"], ORIGIN["early"]) is True
    assert better_or_equal_already(ORIGIN["early"], ORIGIN["late"]) is False
    assert better_or_equal_already(ORIGIN["ImergCalib"], ORIGIN["late"]) is True


def test_clip_imerg_stops_at_yesterday():
    got = clip_imerg(date(2026, 8, 28), date(2026, 9, 5), today=date(2026, 9, 4))
    assert got[0] == date(2026, 8, 28)
    assert got[-1] == date(2026, 9, 3)


def test_clip_imerg_empty_if_all_future():
    assert clip_imerg(date(2026, 9, 4), date(2026, 9, 6), today=date(2026, 9, 4)) == []


def test_best_origin_keeps_lowest_id():
    loaded = pd.DataFrame(
        {
            "fecha": [date(2026, 9, 1), date(2026, 9, 1), date(2026, 9, 2)],
            "id_origen": [4, 3, 4],
        }
    )
    got = best_origin_by_date(loaded)
    assert got[date(2026, 9, 1)] == 3
    assert got[date(2026, 9, 2)] == 4


def test_month_boundary_needs_next_listing():
    assert needs_next_month_listing(date(2026, 8, 31)) is True
    assert needs_next_month_listing(date(2026, 8, 30)) is False
    assert needs_next_month_listing(date(2026, 12, 31)) is True
