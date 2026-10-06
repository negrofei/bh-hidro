"""Precipitation and ETP by source priority. 0p1: IMERG → ERALand → WRF → GFS."""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from bh_hidro.db.models.atmospheric import DatoERALand, GFS0p1, Imerg0p1, WRF0p1

logger = logging.getLogger(__name__)

PRECIP_PRIORITY = ("Imerg0p1", "DatoERALand", "WRF0p1", "GFS0p1")
ETP_PRIORITY = ("DatoERALand", "WRF0p1", "GFS0p1")

_MODELS = {
    "Imerg0p1": Imerg0p1,
    "DatoERALand": DatoERALand,
    "WRF0p1": WRF0p1,
    "GFS0p1": GFS0p1,
}

_PRECIP_COLUMN = {
    "Imerg0p1": "precip",
    "DatoERALand": "tp",
    "WRF0p1": "tp",
    "GFS0p1": "tp",
}


def parse_priority(raw: str | None, default: tuple[str, ...]) -> list[str]:
    if not raw:
        return list(default)
    names = [name.strip() for name in raw.split(",") if name.strip()]
    return [name for name in names if name in _MODELS] or list(default)


def complete_precip_nodes(nodes: pd.DataFrame, raw: pd.DataFrame, value_col: str = "tp") -> pd.DataFrame:
    """Every province node must appear; missing precipitation is 0 (it matters for the bucket)."""
    work = raw.rename(columns={value_col: "tp"}) if value_col != "tp" else raw
    merged = nodes[["id_nodo"]].drop_duplicates().merge(work[["id_nodo", "tp"]], on="id_nodo", how="left")
    filled = int(merged["tp"].isna().sum())
    if filled:
        logger.debug("Filled %s province nodes with tp=0", filled)
    merged["tp"] = merged["tp"].fillna(0).astype(float).clip(lower=0)
    return merged[["id_nodo", "tp"]]


async def get_precip(
    fecha: date,
    id_provincia: int,
    priority: list[str] | None = None,
) -> tuple[pd.DataFrame, str]:
    nodes = await DatoERALand.association().read_by_provincias(id_provincia)
    for name in priority or PRECIP_PRIORITY:
        model = _MODELS[name]
        if not await model.exists_fecha_province(fecha, id_provincia):
            logger.debug("No %s precip for %s provincia=%s", name, fecha, id_provincia)
            continue
        logger.debug("Found %s precip for %s provincia=%s", name, fecha, id_provincia)
        value_col = _PRECIP_COLUMN[name]
        raw = await model.by_fecha_province(fecha, id_provincia, columns=["id_nodo", value_col])
        if raw.empty:
            continue
        return complete_precip_nodes(nodes, raw, value_col), name
    raise ValueError(f"No precipitation data available for {fecha}")


async def get_etp(
    fecha: date,
    id_provincia: int,
    priority: list[str] | None = None,
) -> tuple[pd.DataFrame, str]:
    """Merge ETP sources node-wise (best coverage). Never invent ETP=0."""
    nodes = await DatoERALand.association().read_by_provincias(id_provincia)
    out = nodes[["id_nodo"]].drop_duplicates().copy()
    out["etp"] = pd.NA
    used: list[str] = []
    for name in priority or ETP_PRIORITY:
        model = _MODELS[name]
        if not await model.exists_fecha_province(fecha, id_provincia):
            logger.debug("No %s ETP for %s provincia=%s", name, fecha, id_provincia)
            continue
        raw = await model.by_fecha_province(fecha, id_provincia, columns=["id_nodo", "etp"])
        if raw.empty:
            continue
        missing = out["etp"].isna()
        if not missing.any():
            break
        patch = out.loc[missing, ["id_nodo"]].merge(raw, on="id_nodo", how="left")
        out.loc[missing, "etp"] = patch["etp"].astype(float).to_numpy()
        used.append(name)
        logger.debug("Found %s ETP for %s provincia=%s", name, fecha, id_provincia)
    if not used or out["etp"].isna().all():
        raise ValueError(f"No ETP data available for {fecha}")
    still = int(out["etp"].isna().sum())
    if still:
        logger.warning("ETP still missing for %s nodes on %s after %s", still, fecha, used)
    out = out.dropna(subset=["etp"])
    out["etp"] = out["etp"].astype(float)
    label = "+".join(used) if len(used) > 1 else used[0]
    return out[["id_nodo", "etp"]], label
