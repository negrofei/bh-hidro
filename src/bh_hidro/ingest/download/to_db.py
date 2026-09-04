"""Daily NetCDF → reticula_land → MySQL upsert."""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import xarray as xr

from bh_hidro.db.models.atmospheric import DatoERALand, WRF0p1
from bh_hidro.db.models.grids import ReticulaLand

logger = logging.getLogger(__name__)


def dataset_to_frame(ds: xr.Dataset) -> pd.DataFrame:
    lon_name = "longitude" if "longitude" in ds.dims else "lon"
    lat_name = "latitude" if "latitude" in ds.dims else "lat"
    df = ds.to_dataframe().reset_index()
    df = df.loc[:, ~df.columns.duplicated()]
    df = df.rename(columns={"time": "fecha", lon_name: "lon_nodo", lat_name: "lat_nodo"})
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    if "day_prono" in ds.attrs:
        df["day_prono"] = int(ds.attrs["day_prono"])
    df["lat_nodo"] = df["lat_nodo"].astype(float).round(2)
    df["lon_nodo"] = df["lon_nodo"].astype(float).round(2)
    if "number" in df.columns:
        df = df.drop(columns=["number"])
    return df


async def attach_nodos(df: pd.DataFrame) -> pd.DataFrame:
    grid = await ReticulaLand.read_all()
    coords = grid[["lat_nodo", "lon_nodo"]].astype(float).round(2)
    merged = df.merge(
        pd.concat([coords, grid[["id_nodo"]]], axis=1),
        on=["lat_nodo", "lon_nodo"],
    ).drop(columns=["lat_nodo", "lon_nodo"])
    return merged.dropna()


def keep_table_columns(df: pd.DataFrame, model) -> pd.DataFrame:
    cols = [c.name for c in model.__table__.columns]
    return df[[c for c in cols if c in df.columns]]


async def upsert_eraland(ds: xr.Dataset, chunk: int = 10000) -> int:
    df = keep_table_columns(await attach_nodos(dataset_to_frame(ds)), DatoERALand)
    await DatoERALand.upsert_df(df, chunk_size=chunk)
    return len(df)


async def upsert_wrf(ds: xr.Dataset, chunk: int = 10000, today: date | None = None) -> int:
    cutoff = (today or date.today()) - timedelta(days=7)
    from sqlalchemy import text

    from bh_hidro.db.session import get_session

    async with get_session() as session:
        await session.execute(text("DELETE FROM wrf0p1 WHERE fecha <= :cutoff"), {"cutoff": cutoff})
        await session.commit()
    df = keep_table_columns(await attach_nodos(dataset_to_frame(ds)), WRF0p1)
    await WRF0p1.upsert_df(df, chunk_size=chunk)
    return len(df)
