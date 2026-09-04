"""Precipitation and ETP by source priority. 0p1 only: IMERG → ERALand → WRF."""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from bh_hidro.db.models.atmospheric import DatoERALand, Imerg0p1, WRF0p1

logger = logging.getLogger(__name__)

PRECIP_PRIORITY = ("Imerg0p1", "DatoERALand", "WRF0p1")
ETP_PRIORITY = ("DatoERALand", "WRF0p1")

_MODELS = {
    "Imerg0p1": Imerg0p1,
    "DatoERALand": DatoERALand,
    "WRF0p1": WRF0p1,
}


def parse_priority(raw: str | None, default: tuple[str, ...]) -> list[str]:
    if not raw:
        return list(default)
    names = [name.strip() for name in raw.split(",") if name.strip()]
    return [name for name in names if name in _MODELS] or list(default)


async def get_precip(
    fecha: date,
    id_provincia: int,
    priority: list[str] | None = None,
) -> tuple[pd.DataFrame, str]:
    for name in priority or PRECIP_PRIORITY:
        model = _MODELS[name]
        if not await model.exists_fecha_province(fecha, id_provincia):
            continue
        if name == "Imerg0p1":
            return await _imerg_precip(fecha, id_provincia), name
        df = await model.by_fecha_province(fecha, id_provincia, columns=["id_nodo", "tp"])
        if df.empty:
            continue
        df["tp"] = df["tp"].astype(float).clip(lower=0)
        return df[["id_nodo", "tp"]], name
    raise ValueError(f"No precipitation data available for {fecha}")


async def get_etp(
    fecha: date,
    id_provincia: int,
    priority: list[str] | None = None,
) -> tuple[pd.DataFrame, str]:
    for name in priority or ETP_PRIORITY:
        model = _MODELS[name]
        if not await model.exists_fecha_province(fecha, id_provincia):
            continue
        df = await model.by_fecha_province(fecha, id_provincia, columns=["id_nodo", "etp"])
        if df.empty:
            continue
        df["etp"] = df["etp"].astype(float)
        return df[["id_nodo", "etp"]], name
    raise ValueError(f"No ETP data available for {fecha}")


async def _imerg_precip(fecha: date, id_provincia: int) -> pd.DataFrame:
    nodes = await Imerg0p1.association().read_by_provincias(id_provincia)
    raw = await Imerg0p1.by_fecha_province(fecha, id_provincia, columns=["id_nodo", "precip"])
    merged = nodes[["id_nodo"]].merge(raw, on="id_nodo", how="left")
    merged["tp"] = merged["precip"].fillna(0).astype(float).clip(lower=0)
    return merged[["id_nodo", "tp"]]
