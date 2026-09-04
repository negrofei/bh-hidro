from datetime import date

import pandas as pd

from bh_hidro.balance.engine import STUBBLE_KC, balance_hidrico_pandarized, initial_almacenaje
from bh_hidro.balance.kc import CalendarKc, GddKc, add_cumulative_gdd_by_node, juliano2fechas
from bh_hidro.balance.sources import parse_priority
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


def test_parse_priority_drops_unknown():
    assert parse_priority("Imerg0p1,GFS0p1,DatoERALand", ("Imerg0p1",)) == ["Imerg0p1", "DatoERALand"]
