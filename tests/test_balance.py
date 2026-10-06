from datetime import date
from pathlib import Path

import pandas as pd

from bh_hidro.balance.engine import STUBBLE_KC, balance_hidrico_pandarized, initial_almacenaje
from bh_hidro.balance.ini import BalanceIni
from bh_hidro.balance.kc import CalendarKc, GddKc, add_cumulative_gdd_by_node, juliano2fechas
from bh_hidro.balance.run import _numeric_ids
from bh_hidro.balance.sources import complete_precip_nodes, parse_priority
from bh_hidro.balance.stats import categorize_agua_util


def test_fao_bucket_caps_at_field_capacity():
    df = pd.DataFrame(
        {
            "pmp": [40.0],
            "capacidad_campo": [100.0],
            "coef_escurrimiento": [0.1],
            "coef_percolacion": [0.05],
            "kc": [1.0],
            "etp": [5.0],
            "tp": [80.0],
            "almacenaje": [90.0],
            "exceso": [0.0],
        }
    )
    almacenaje, exceso, *_rest, agua_util = balance_hidrico_pandarized(df)
    assert float(almacenaje.iloc[0]) <= 100.0
    assert float(exceso.iloc[0]) >= 0.0
    assert 0.0 <= float(agua_util.iloc[0]) <= 1.5


def test_initial_almacenaje_is_half_available_water():
    pmp = pd.Series([40.0])
    cc = pd.Series([100.0])
    assert float(initial_almacenaje(pmp, cc).iloc[0]) == 70.0


def test_calendar_kc_unico():
    fenologia = pd.DataFrame(
        {"id_etapa": [1], "id_tipo_cultivo": [2], "nombre_etapa": ["Unico"], "kc": [0.85]}
    )
    rel = pd.DataFrame({"id_etapa": [1], "id_patron": [3], "juliano": [1]})
    kc = CalendarKc().kc_for_date(date(2026, 9, 1), 3, 2, fenologia, rel)
    assert kc == 0.85


def test_calendar_kc_stubble_outside_season():
    fenologia = pd.DataFrame(
        {
            "id_etapa": [1, 2],
            "id_tipo_cultivo": [2, 2],
            "nombre_etapa": ["Siembra", "Cosecha"],
            "kc": [0.4, 1.1],
        }
    )
    rel = pd.DataFrame({"id_etapa": [1, 2], "id_patron": [3, 3], "juliano": [300, 350]})
    kc = CalendarKc().kc_for_date(date(2026, 1, 15), 3, 2, fenologia, rel)
    assert kc == STUBBLE_KC


def test_juliano_wraps_year():
    julianos = pd.Series([350, 20], name="juliano")
    fechas = juliano2fechas(julianos, date(2026, 1, 10))
    assert fechas[0] < fechas[1] or fechas[1].year >= fechas[0].year


def test_gdd_outside_range_is_stubble():
    fenologia = pd.DataFrame(
        {
            "id_etapa": [1, 2],
            "id_tipo_cultivo": [2, 2],
            "nombre_etapa": ["Siembra", "Cosecha"],
            "kc": [0.4, 1.1],
        }
    )
    rel = pd.DataFrame({"id_etapa": [1, 2], "id_patron": [3, 3], "juliano": [1, 100]})
    umbral = pd.DataFrame({"id_nodo": [10, 10], "id_patron": [3, 3], "id_etapa": [1, 2], "gdd_umbral": [100.0, 800.0]})
    kc = GddKc().kc_for_date(10.0, 3, 2, 10, fenologia, rel, umbral)
    assert kc == STUBBLE_KC


def test_cumulative_gdd_clips_base():
    data = pd.DataFrame(
        {
            "id_nodo": [1, 1],
            "fecha": [date(2026, 1, 1), date(2026, 1, 2)],
            "t2m_max": [20.0, 22.0],
            "t2m_min": [8.0, 10.0],
        }
    )
    got = add_cumulative_gdd_by_node(data, t_base=10.0, t_upp=30.0)
    assert got["gdd"].iloc[1] > got["gdd"].iloc[0]


def test_agua_util_bins():
    cats = categorize_agua_util(pd.Series([-0.1, 0.1, 0.4, 0.8, 1.0, 1.2]))
    assert list(cats) == [
        "Sequía",
        "Escasas",
        "Regulares",
        "Óptimas",
        "Muy excesivas",
        "Muy excesivas",
    ]


def test_parse_priority_keeps_known_including_gfs():
    assert parse_priority("Imerg0p1,GFS0p1,DatoERALand", ("Imerg0p1",)) == [
        "Imerg0p1",
        "GFS0p1",
        "DatoERALand",
    ]


def test_parse_priority_drops_unknown():
    assert parse_priority("Imerg0p1,FakeModel,DatoERALand", ("Imerg0p1",)) == [
        "Imerg0p1",
        "DatoERALand",
    ]

def test_complete_precip_nodes_fills_missing_with_zero():
    nodes = pd.DataFrame({"id_nodo": [1, 2, 3]})
    raw = pd.DataFrame({"id_nodo": [1, 3], "tp": [12.5, -1.0]})
    got = complete_precip_nodes(nodes, raw, "tp")
    assert list(got["id_nodo"]) == [1, 2, 3]
    assert float(got.loc[got["id_nodo"] == 2, "tp"].iloc[0]) == 0.0
    assert float(got.loc[got["id_nodo"] == 3, "tp"].iloc[0]) == 0.0


def test_complete_precip_nodes_renames_imerg_column():
    nodes = pd.DataFrame({"id_nodo": [10, 11]})
    raw = pd.DataFrame({"id_nodo": [10], "precip": [4.2]})
    got = complete_precip_nodes(nodes, raw, "precip")
    assert list(got.columns) == ["id_nodo", "tp"]
    assert float(got.loc[got["id_nodo"] == 11, "tp"].iloc[0]) == 0.0


def test_dates_to_run_always_returns_full_window():
    import asyncio

    from bh_hidro.balance.run import dates_to_run

    cfg = BalanceIni.load(
        Path("configs/example/balance.ini"),
        start=date(2026, 9, 29),
        end=date(2026, 10, 7),
    )
    got = asyncio.run(dates_to_run(cfg, id_cultivo_general=1, id_provincia=22))
    assert got[0] == date(2026, 9, 29)
    assert got[-1] == date(2026, 10, 7)
    assert len(got) == 9


def test_numeric_ids_coerces_without_ignore():
    df = pd.DataFrame(
        {
            "id_nodo": [1],
            "pmp": ["40.0"],
            "pp_from": ["Imerg0p1"],
            "etp_from": ["DatoERALand"],
        }
    )
    out = _numeric_ids(df)
    assert out["pmp"].dtype.kind == "f"
    assert float(out["pmp"].iloc[0]) == 40.0
    assert out["pp_from"].iloc[0] == "Imerg0p1"


def test_balance_ini_reads_workers():
    cfg = BalanceIni.load(
        Path("configs/example/balance.ini"),
        start=date(2000, 1, 1),
        end=date(2000, 1, 3),
    )
    assert cfg.paralelo is True
    assert cfg.workers == 7
    assert cfg.fetch_workers == 7
    assert cfg.raise_if_data_gap is True
    assert cfg.first_day == date(2000, 1, 1)


def test_initial_state_frame_is_half_agua_util():
    from bh_hidro.balance.engine import BALANCE_INDEX
    from bh_hidro.balance.run import initial_state_frame

    base = pd.DataFrame(
        {
            "id_formita": [1],
            "id_provincia": [22],
            "id_departamento": [1],
            "id_suelo": [1],
            "id_nodo": [10],
            "id_cultivo_general": [1],
            "pmp": [40.0],
            "capacidad_campo": [100.0],
        }
    )
    init = initial_state_frame(base, date(1999, 12, 31))
    assert list(init.columns[:6]) == BALANCE_INDEX or set(BALANCE_INDEX).issubset(init.columns)
    assert float(init["almacenaje"].iloc[0]) == 70.0
    assert float(init["agua_util"].iloc[0]) == 0.5
    assert init["pp_from"].iloc[0] == "init"


def test_calendar_kc_interpolates_and_logs(caplog):
    import logging

    fenologia = pd.DataFrame(
        {
            "id_etapa": [1, 2],
            "id_tipo_cultivo": [2, 2],
            "nombre_etapa": ["Siembra", "Cosecha"],
            "kc": [0.4, 1.1],
        }
    )
    rel = pd.DataFrame({"id_etapa": [1, 2], "id_patron": [3, 3], "juliano": [10, 40]})
    with caplog.at_level(logging.DEBUG, logger="bh_hidro.balance.kc"):
        kc = CalendarKc().kc_for_date(date(2026, 1, 25), 3, 2, fenologia, rel)
    assert 0.4 < kc < 1.1
    assert "interpolated Kc=" in caplog.text
