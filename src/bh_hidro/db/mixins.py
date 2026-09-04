"""Shared table operations. No shapefile init, no GeoPandas."""

from __future__ import annotations

import logging
from collections.abc import Sequence

import pandas as pd
from sqlalchemy import Select, func, inspect, select
from sqlalchemy.dialects.mysql import insert

from bh_hidro.db.session import get_session

logger = logging.getLogger(__name__)


def _as_list(value: str | int | Sequence) -> list:
    if isinstance(value, (str, int)):
        return [value]
    return list(value)


class TableOps:
    """Read / upsert helpers used by every mapped table."""

    @classmethod
    async def fetch_df(cls, stmt: Select) -> pd.DataFrame:
        async with get_session() as session:
            result = await session.execute(stmt)
            return pd.DataFrame(result.fetchall(), columns=result.keys())

    @classmethod
    async def read_all(cls) -> pd.DataFrame:
        return await cls.fetch_df(select(cls.__table__.c))

    @classmethod
    async def is_empty(cls) -> bool:
        async with get_session() as session:
            count = await session.scalar(select(func.count()).select_from(cls))
        return (count or 0) == 0

    @classmethod
    async def select_where(cls, **filters) -> pd.DataFrame:
        stmt = select(cls.__table__.c)
        for name, value in filters.items():
            column = getattr(cls, name, None)
            if column is None:
                logger.warning("Unknown column %s on %s", name, cls.__tablename__)
                continue
            stmt = stmt.where(column == value)
        return await cls.fetch_df(stmt)

    @classmethod
    async def upsert_df(cls, df: pd.DataFrame, chunk_size: int = 5000) -> None:
        if df is None or df.empty:
            logger.warning("No rows to upsert into %s", cls.__tablename__)
            return

        columns = {col.name for col in cls.__table__.columns}
        pk = {col.name for col in inspect(cls).primary_key}
        records = [
            {k: v for k, v in row.items() if k in columns}
            for row in df.astype(object).where(df.notna(), None).to_dict("records")
        ]
        if not records:
            return

        update_cols = [name for name in records[0] if name not in pk]
        async with get_session() as session:
            for start in range(0, len(records), chunk_size):
                batch = records[start : start + chunk_size]
                stmt = insert(cls.__table__).values(batch)
                if update_cols:
                    stmt = stmt.on_duplicate_key_update(
                        {name: stmt.inserted[name] for name in update_cols}
                    )
                else:
                    first_pk = next(iter(pk))
                    stmt = stmt.on_duplicate_key_update(
                        {first_pk: stmt.inserted[first_pk]}
                    )
                await session.execute(stmt)
            await session.commit()
        logger.info("Upserted %s rows into %s", len(records), cls.__tablename__)


class ProvinceScoped(TableOps):
    """Tables that have id_provincia (and optionally id_departamento)."""

    @classmethod
    async def read_by_provincias(cls, provincias: str | int | Sequence) -> pd.DataFrame:
        if provincias == "all":
            return await cls.read_all()
        ids = await resolve_province_ids(provincias)
        return await cls.fetch_df(
            select(cls.__table__.c).where(cls.id_provincia.in_(ids))
        )

    @classmethod
    async def read_by_departamentos(cls, departamentos: str | int | Sequence) -> pd.DataFrame:
        if departamentos == "all":
            return await cls.read_all()
        values = _as_list(departamentos)
        if all(isinstance(v, int) for v in values):
            return await cls.fetch_df(
                select(cls.__table__.c).where(cls.id_departamento.in_(values))
            )
        from bh_hidro.db.models.geographic import Departamento

        deptos = await Departamento.read_all()
        ids = deptos[deptos.nombre.isin(values)].id_departamento.tolist()
        return await cls.fetch_df(
            select(cls.__table__.c).where(cls.id_departamento.in_(ids))
        )


class GridLinked(TableOps):
    """Atmospheric tables on the 0.1° land grid."""

    _resolution = 0.1
    _grid = "land"

    @classmethod
    def association(cls):
        from bh_hidro.db.models.grids import ReticulaLandProvinciaAssociation

        return ReticulaLandProvinciaAssociation

    @classmethod
    def grid(cls):
        from bh_hidro.db.models.grids import ReticulaLand

        return ReticulaLand

    @classmethod
    async def dates_for_provinces(cls, provincias: list[int], **filters) -> list:
        nodes = await cls.association().read_by_provincias(provincias)
        if nodes.empty:
            return []
        stmt = select(cls.fecha.distinct()).where(cls.id_nodo.in_(nodes["id_nodo"].tolist()))
        for name, value in filters.items():
            stmt = stmt.where(getattr(cls, name) == value)
        df = await cls.fetch_df(stmt)
        if df.empty:
            return []
        return [row.date() if hasattr(row, "date") else row for row in df["fecha"].tolist()]

    @classmethod
    async def exists_fecha_province(cls, fecha, id_provincia: int) -> bool:
        from sqlalchemy import exists as sql_exists

        from bh_hidro.db.session import get_session

        nodes = await cls.association().read_by_provincias(id_provincia)
        if nodes.empty:
            return False
        stmt = select(
            sql_exists().where(
                cls.fecha == fecha,
                cls.id_nodo.in_(nodes["id_nodo"].tolist()),
            )
        )
        async with get_session() as session:
            return bool(await session.scalar(stmt))

    @classmethod
    async def by_fecha_province(cls, fecha, id_provincia: int, columns: list[str] | None = None) -> pd.DataFrame:
        nodes = await cls.association().read_by_provincias(id_provincia)
        if nodes.empty:
            return pd.DataFrame()
        if columns:
            stmt = select(*[cls.__table__.c[name] for name in columns])
        else:
            stmt = select(cls.__table__.c)
        stmt = stmt.where(
            cls.fecha == fecha,
            cls.id_nodo.in_(nodes["id_nodo"].tolist()),
        )
        return await cls.fetch_df(stmt)


async def resolve_province_ids(provincias: str | int | Sequence) -> list[int]:
    values = _as_list(provincias)
    if all(isinstance(v, int) for v in values):
        return values
    from bh_hidro.db.models.geographic import Provincia

    return await Provincia.ids_by_names(values)
