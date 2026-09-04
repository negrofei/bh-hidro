"""User field / campaign and GDD water-balance tables. Product layer; same DB."""

from __future__ import annotations

import json
from datetime import date

import pandas as pd
from sqlalchemy import (
    Column,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    JSON,
    Numeric,
    String,
    select,
)

from bh_hidro.db.base import Base
from bh_hidro.db.mixins import ProvinceScoped, TableOps


class UsuarioCampo(Base, TableOps):
    __tablename__ = "usuario_campo"

    id_usuario = Column(Integer, primary_key=True)
    id_campo = Column(Integer, primary_key=True)
    lista_formitas = Column(JSON, nullable=False)

    @classmethod
    async def formitas_for_campo(cls, id_usuario: int, id_campo: int) -> list[int]:
        df = await cls.select_where(id_usuario=id_usuario, id_campo=id_campo)
        if df.empty:
            return []
        row = df.iloc[0]["lista_formitas"]
        if isinstance(row, str):
            return json.loads(row)
        return list(row)

    def __repr__(self) -> str:
        return f"UsuarioCampo(usuario={self.id_usuario}, campo={self.id_campo})"


class UsuarioCampana(Base, TableOps):
    __tablename__ = "usuario_campana"

    id_campana = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, nullable=False)
    id_campo = Column(Integer, nullable=False)
    id_tipo_cultivo = Column(
        Integer, ForeignKey("tipos_cultivo.id_tipo_cultivo"), nullable=False
    )
    fecha_siembra = Column(Date, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["id_usuario", "id_campo"],
            ["usuario_campo.id_usuario", "usuario_campo.id_campo"],
        ),
    )

    def __repr__(self) -> str:
        return (
            f"UsuarioCampana(id={self.id_campana}, usuario={self.id_usuario}, "
            f"tipo={self.id_tipo_cultivo}, siembra={self.fecha_siembra})"
        )


class BalanceHidricoCustom0p1(Base, ProvinceScoped):
    __tablename__ = "balance_hidrico_custom0p1"

    id_campana = Column(
        Integer, ForeignKey("usuario_campana.id_campana"), primary_key=True
    )
    id_formita = Column(Integer, primary_key=True)
    id_provincia = Column(Integer, ForeignKey("provincias.id_provincia"), primary_key=True)
    id_departamento = Column(
        Integer, ForeignKey("departamentos.id_departamento"), primary_key=True
    )
    id_suelo = Column(Integer, ForeignKey("suelo.id_suelo"), primary_key=True)
    id_nodo = Column(Integer, ForeignKey("reticula_land.id_nodo"), primary_key=True)
    id_cultivo_general = Column(
        Integer, ForeignKey("cultivos_generales.id_cultivo_general"), primary_key=True
    )
    fecha = Column(Date, primary_key=True)

    almacenaje = Column(Numeric(9, 5))
    exceso = Column(Numeric(9, 5))
    escurrimiento = Column(Numeric(9, 5))
    percolacion = Column(Numeric(9, 5))
    agua_util = Column(Numeric(9, 5))
    pp_from = Column(String(20), nullable=False)
    etp_from = Column(String(20), nullable=False)
    gdd = Column(Numeric(9, 2), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["id_formita", "id_provincia", "id_departamento", "id_nodo", "id_suelo"],
            [
                "formitas_merge_0p1.id_formita",
                "formitas_merge_0p1.id_provincia",
                "formitas_merge_0p1.id_departamento",
                "formitas_merge_0p1.id_nodo",
                "formitas_merge_0p1.id_suelo",
            ],
        ),
    )

    @classmethod
    async def by_campana(
        cls,
        id_campana: int,
        fecha_desde: date | None = None,
        fecha_hasta: date | None = None,
    ) -> pd.DataFrame:
        stmt = select(cls.__table__.c).where(cls.id_campana == id_campana)
        if fecha_desde is not None:
            stmt = stmt.where(cls.fecha >= fecha_desde)
        if fecha_hasta is not None:
            stmt = stmt.where(cls.fecha <= fecha_hasta)
        return await cls.fetch_df(stmt.order_by(cls.fecha, cls.id_formita))

    def __repr__(self) -> str:
        return (
            f"BalanceHidricoCustom0p1(campana={self.id_campana}, "
            f"formita={self.id_formita}, fecha={self.fecha})"
        )
