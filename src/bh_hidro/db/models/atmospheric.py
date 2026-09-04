"""Atmospheric daily series on the 0.1° land grid. ERA5 / GFS stay out."""

from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import Column, Date, ForeignKey, Index, Integer, Numeric, and_, select

from bh_hidro.db.base import Base
from bh_hidro.db.mixins import GridLinked


class DatoERALand(Base, GridLinked):
    __tablename__ = "datos_eraland"

    id_nodo = Column(Integer, ForeignKey("reticula_land.id_nodo"), primary_key=True)
    fecha = Column(Date, primary_key=True)
    t2m_min = Column(Numeric(9, 6), nullable=False)
    t2m_max = Column(Numeric(9, 6), nullable=False)
    tp = Column(Numeric(9, 6), nullable=False)
    etp = Column(Numeric(9, 7), nullable=False)
    pev = Column(Numeric(9, 6), nullable=False)

    def __repr__(self) -> str:
        return f"DatoERALand(nodo={self.id_nodo}, fecha={self.fecha})"


class WRF0p1(Base, GridLinked):
    __tablename__ = "wrf0p1"

    id_nodo = Column(Integer, ForeignKey("reticula_land.id_nodo"), primary_key=True)
    fecha = Column(Date, primary_key=True)
    tp = Column(Numeric(9, 6), nullable=False)
    etp = Column(Numeric(9, 7), nullable=False)
    day_prono = Column(Integer, nullable=False)

    @classmethod
    async def dates_loaded_day0(cls, provincias: list[int]) -> pd.DataFrame:
        nodes = await cls.association().read_by_provincias(provincias)
        return await cls.fetch_df(
            select(cls.__table__.c.fecha.distinct()).where(
                cls.id_nodo.in_(nodes["id_nodo"].tolist()),
                cls.day_prono == 0,
            )
        )

    def __repr__(self) -> str:
        return f"WRF0p1(nodo={self.id_nodo}, fecha={self.fecha})"


class Imerg0p1(Base, GridLinked):
    """IMERG interpolated onto the land grid. Source of precip #1 for balance."""

    __tablename__ = "imerg0p1"

    id_nodo = Column(Integer, ForeignKey("reticula_land.id_nodo"), primary_key=True)
    fecha = Column(Date, primary_key=True)
    precip = Column(Numeric(5, 2), nullable=False)
    id_origen = Column(Integer, ForeignKey("origen_imerg.id_origen"), nullable=False)

    __table_args__ = (Index("idx_imerg0p1_fecha", "fecha"),)

    @classmethod
    async def dates_loaded(cls, date_ini: str, date_fin: str) -> pd.DataFrame:
        return await cls.fetch_df(
            select(cls.__table__.c.fecha.distinct(), cls.id_origen).where(
                cls.fecha.between(date_ini, date_fin)
            )
        )

    def __repr__(self) -> str:
        return f"Imerg0p1(nodo={self.id_nodo}, fecha={self.fecha})"


class ImergNative(Base, GridLinked):
    """Native IMERG grid (reticula_imerg) before interpolation to land."""

    __tablename__ = "imerg"
    _grid = "imerg"

    id_nodo = Column(Integer, ForeignKey("reticula_imerg.id_nodo"), primary_key=True)
    fecha = Column(Date, primary_key=True)
    precip = Column(Numeric(5, 2), nullable=False)
    id_origen = Column(Integer, ForeignKey("origen_imerg.id_origen"), nullable=False)

    __table_args__ = (Index("idx_imerg_fecha", "fecha"),)

    @classmethod
    def association(cls):
        from bh_hidro.db.models.grids import ReticulaImergProvinciaAssociation

        return ReticulaImergProvinciaAssociation

    @classmethod
    def grid(cls):
        from bh_hidro.db.models.grids import ReticulaImerg

        return ReticulaImerg

    @classmethod
    async def dates_loaded(cls, date_ini: str, date_fin: str) -> pd.DataFrame:
        return await cls.fetch_df(
            select(cls.__table__.c.fecha.distinct(), cls.id_origen).where(
                cls.fecha.between(date_ini, date_fin)
            )
        )

    @classmethod
    async def delete_by_fecha_origen(cls, fecha: date, id_origen: int) -> None:
        from bh_hidro.db.session import get_session

        async with get_session() as session:
            await session.execute(
                cls.__table__.delete().where(
                    and_(cls.fecha == fecha, cls.id_origen == id_origen)
                )
            )
            await session.commit()

    def __repr__(self) -> str:
        return f"ImergNative(nodo={self.id_nodo}, fecha={self.fecha})"
