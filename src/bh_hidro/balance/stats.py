"""Department agua_util categories. Same bins as prod visualization enums."""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from bh_hidro.db.models.balance import EstadisticasDepartamento0p1

logger = logging.getLogger(__name__)

AGUA_UTIL_LEVELS = [0, 0.25, 0.5, 0.75, 0.95, 1]
AGUA_UTIL_LABELS = ["Escasas", "Regulares", "Adecuadas", "Óptimas", "Excesivas", "Muy excesivas"]
CATEGORY_COLUMNS = {
    "Sequía": "prop_sequia",
    "Escasas": "prop_escasas",
    "Regulares": "prop_regulares",
    "Adecuadas": "prop_adecuadas",
    "Óptimas": "prop_optimas",
    "Excesivas": "prop_excesivas",
    "Muy excesivas": "prop_muy_excesivas",
}


def categorize_agua_util(values: pd.Series) -> pd.Series:
    bins = [-float("inf")] + AGUA_UTIL_LEVELS + [float("inf")]
    labels = ["Sequía"] + AGUA_UTIL_LABELS
    cats = pd.cut(values, bins=bins, labels=labels, right=True, include_lowest=True)
    cats = cats.astype(object)
    cats[values >= 1] = "Muy excesivas"
    return cats


def stats_from_balance(df: pd.DataFrame, fecha: date, id_cultivo_general: int) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    if "area_formita" not in work.columns:
        work["area_formita"] = 1.0
    work["area_formita"] = work["area_formita"].fillna(0)
    grouped = work.groupby(["id_departamento", "id_provincia"], dropna=False)

    def _agg(g: pd.DataFrame) -> pd.Series:
        area = g["area_formita"]
        total = area.sum()
        mean = (g["agua_util"] * area).sum() / total if total else float("nan")
        return pd.Series(
            {
                "agua_util_mean": mean,
                "agua_util_min": g["agua_util"].min(),
                "agua_util_max": g["agua_util"].max(),
            }
        )

    stats = grouped.apply(_agg, include_groups=False).reset_index()
    work["category"] = categorize_agua_util(work["agua_util"].astype(float))
    totals = work.groupby(["id_departamento", "id_provincia"])["area_formita"].sum()
    cat_area = (
        work.groupby(["id_departamento", "id_provincia", "category"], observed=True)["area_formita"]
        .sum()
        .unstack(fill_value=0)
    )
    props = cat_area.div(totals, axis=0).round(4).reset_index()
    stats = stats.merge(props, on=["id_departamento", "id_provincia"], how="left")
    for label, column in CATEGORY_COLUMNS.items():
        if label in stats.columns:
            stats[column] = stats[label]
        elif column not in stats.columns:
            stats[column] = 0.0
    stats["fecha"] = fecha
    stats["id_cultivo_general"] = id_cultivo_general
    keep = [
        "id_provincia",
        "id_departamento",
        "id_cultivo_general",
        "fecha",
        "agua_util_mean",
        "agua_util_min",
        "agua_util_max",
        *CATEGORY_COLUMNS.values(),
    ]
    return stats[[c for c in keep if c in stats.columns]]


async def upsert_stats(df: pd.DataFrame, chunk: int = 5000) -> int:
    if df is None or df.empty:
        return 0
    await EstadisticasDepartamento0p1.upsert_df(df, chunk_size=chunk)
    return len(df)
