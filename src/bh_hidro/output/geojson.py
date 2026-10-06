"""Join formitas geometry with daily agua_util and write GeoJSON."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from bh_hidro.db.models.balance import BalanceHidricoMerge0p1
from bh_hidro.db.models.formitas import FormitasMerge0p1

logger = logging.getLogger(__name__)


def _to_geojson_geom(value):
    from shapely import to_geojson, wkb

    payload = bytes(value.data) if hasattr(value, "data") else bytes(value)
    return json.loads(to_geojson(wkb.loads(payload)))


def layer_name(variable: str, fecha: date, crop: str, resolution: str = "0p1") -> str:
    """Tileserver id: agua-util_2026-09-08_S1_0p1."""
    return f"{variable.replace('_', '-')}_{fecha.isoformat()}_{crop}_{resolution}"


def geojson_name(out_dir: Path, variable: str, fecha: date, crop: str) -> Path:
    return out_dir / f"{layer_name(variable, fecha, crop)}.geojson"


async def features_for_date(
    fecha: date,
    id_cultivo_general: int,
    id_provincias: list[int],
    variable: str,
) -> list[dict]:
    stmt = select(BalanceHidricoMerge0p1.__table__.c).where(
        BalanceHidricoMerge0p1.fecha == fecha,
        BalanceHidricoMerge0p1.id_cultivo_general == id_cultivo_general,
        BalanceHidricoMerge0p1.id_provincia.in_(id_provincias),
    )
    balance = await BalanceHidricoMerge0p1.fetch_df(stmt)
    if balance.empty:
        return []
    formitas = await FormitasMerge0p1.fetch_df(
        select(FormitasMerge0p1.__table__.c).where(
            FormitasMerge0p1.id_provincia.in_(id_provincias)
        )
    )
    merged = balance.merge(
        formitas,
        on=["id_formita", "id_provincia", "id_departamento", "id_nodo", "id_suelo"],
        how="inner",
    )
    features = []
    for _, row in merged.iterrows():
        if row.get("shape_formita") is None or (isinstance(row["shape_formita"], float) and pd.isna(row["shape_formita"])):
            continue
        props = {
            "id_formita": int(row["id_formita"]),
            "id_provincia": int(row["id_provincia"]),
            "id_departamento": int(row["id_departamento"]),
            "id_cultivo_general": int(id_cultivo_general),
            "fecha": fecha.isoformat(),
            variable: float(row[variable]) if pd.notna(row[variable]) else None,
            "pp_from": row.get("pp_from"),
            "etp_from": row.get("etp_from"),
        }
        features.append(
            {
                "type": "Feature",
                "geometry": _to_geojson_geom(row["shape_formita"]),
                "properties": props,
            }
        )
    return features


def write_geojson(path: Path, features: list[dict]) -> Path:
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    logger.info("wrote %s (%s features)", path.name, len(features))
    return path
