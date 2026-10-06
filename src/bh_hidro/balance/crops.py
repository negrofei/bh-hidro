"""Load crop / soil / formita frames for the 0p1 merge balance."""

from __future__ import annotations

import json
import logging
import re

import pandas as pd

from bh_hidro.balance.engine import NON_AGRICULTURAL_SOIL
from bh_hidro.db.models.agricultural import CultivoGeneral, EtapaFenologica, RelEtapaPatron, Suelo, TipoCultivo
from bh_hidro.db.models.formitas import FormitasMerge0p1
from bh_hidro.db.models.grids import PatronKcXNodoLand

logger = logging.getLogger(__name__)


def _geom_area(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 1.0
    from shapely import wkb

    payload = bytes(value.data) if hasattr(value, "data") else bytes(value)
    return float(wkb.loads(payload).area)


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [parsed]
        except json.JSONDecodeError:
            return [value]
    return [value]


async def crop_ids(codes: list[str]) -> pd.DataFrame:
    table = await CultivoGeneral.read_all()
    if codes == ["all"]:
        return table
    return table[table["codigo"].isin(codes)]


async def tipos_from_cultivo_general(id_cultivo_general: int) -> list[int]:
    logger.debug("Getting crop types for crop %s", id_cultivo_general)
    cultivo = await CultivoGeneral.select_where(id_cultivo_general=id_cultivo_general)
    prefix = cultivo["codigo"].iloc[0]
    tipos = await TipoCultivo.read_all()
    if prefix == "P-CN":
        pradera, campo_natural = prefix.split("-")
        ids = pd.concat(
            [
                tipos[tipos["codigo"].str.contains(pradera, regex=False)]["id_tipo_cultivo"],
                tipos[tipos["codigo"].str.contains(campo_natural, regex=False)]["id_tipo_cultivo"],
            ]
        )
        return ids.tolist()
    if "ROT" in prefix:
        logger.debug("Rotational crop for %s", id_cultivo_general)
        rotaciones = re.findall(r"\((.*?)\)", prefix.split("-")[2])
        parts = [
            tipos[tipos["codigo"].str.contains("(" + rotacion + ")", regex=False)]["id_tipo_cultivo"]
            for rotacion in rotaciones
        ]
        return pd.concat(parts).tolist()
    return tipos[tipos["codigo"].str.contains(prefix, regex=False)]["id_tipo_cultivo"].tolist()


async def fenologia(id_tipos: list[int]) -> pd.DataFrame:
    df = await EtapaFenologica.read_all()
    return df[df["id_tipo_cultivo"].isin(id_tipos)]


async def nombres_tipo(id_tipos: list) -> dict[int, str]:
    cults = await TipoCultivo.read_all()
    names: dict[int, str] = {}
    for item in id_tipos:
        values = item if isinstance(item, (list, tuple)) else [item]
        for tipo_id in values:
            row = cults[cults["id_tipo_cultivo"] == tipo_id]
            if not row.empty:
                names[int(tipo_id)] = row.nombre.item()
    return names


async def formitas_for_province(id_provincia: int, suelo: pd.DataFrame) -> pd.DataFrame:
    df = await FormitasMerge0p1.read_by_provincias(id_provincia)
    if "shape_formita" in df.columns:
        df["area_formita"] = df["shape_formita"].apply(_geom_area)
        df = df.drop(columns=["shape_formita"])
    else:
        df["area_formita"] = 1.0
    df = df[df.id_suelo != NON_AGRICULTURAL_SOIL]
    empty_cc = suelo[suelo["capacidad_campo"].isnull()]["id_suelo"]
    if not empty_cc.empty:
        df = df[~df.id_suelo.isin(empty_cc)]
    return df


async def base_frame(id_cultivo_general: int, id_provincia: int) -> pd.DataFrame:
    suelo = await Suelo.read_all()
    formitas = await formitas_for_province(id_provincia, suelo)
    if formitas.empty:
        return formitas
    patrones = await PatronKcXNodoLand.for_cultivo_general(id_cultivo_general)
    if patrones.empty:
        return patrones
    for col in ("id_patronkcnodo", "lat_nodo", "lon_nodo"):
        if col in patrones.columns:
            patrones = patrones.drop(columns=[col])
    merged = formitas.merge(patrones, on="id_nodo")
    merged["id_tipo_cultivo"] = merged["id_tipo_cultivo"].apply(lambda x: tuple(_as_list(x)))
    merged["id_patron"] = merged["id_patron"].apply(lambda x: tuple(_as_list(x)))
    merged["id_cultivo_general"] = id_cultivo_general
    merged = merged.merge(suelo, on="id_suelo", how="left")
    if "tipo_suelo" in merged.columns:
        merged = merged.drop(columns=["tipo_suelo"])
    out = merged.drop_duplicates(
        ["id_formita", "id_provincia", "id_departamento", "id_suelo", "id_nodo", "id_cultivo_general"]
    )
    logger.info(
        "Created base dataframe with %s records for crop=%s provincia=%s",
        len(out),
        id_cultivo_general,
        id_provincia,
    )
    return out


async def rel_etapa_patron() -> pd.DataFrame:
    return await RelEtapaPatron.read_all()
