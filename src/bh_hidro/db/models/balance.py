"""Daily water-balance results on formitas (merge 0p1)."""

from datetime import date

from sqlalchemy import Column, Date, ForeignKey, ForeignKeyConstraint, Integer, Numeric, String, and_, select

from bh_hidro.db.base import Base
from bh_hidro.db.mixins import ProvinceScoped


class BalanceHidricoMerge0p1(Base, ProvinceScoped):
    __tablename__ = "balance_hidrico_merge0p1"

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
    async def dates_for_crop_province(
        cls,
        id_cultivo_general: int,
        id_provincia: int,
        fecha_desde: date | None = None,
    ):
        stmt = (
            select(cls.__table__.c.fecha.label("fecha"))
            .where(
                cls.id_provincia == id_provincia,
                cls.id_cultivo_general == id_cultivo_general,
            )
            .distinct()
        )
        if fecha_desde is not None:
            stmt = stmt.where(cls.fecha >= fecha_desde)
        return await cls.fetch_df(stmt)

    @classmethod
    async def by_fecha_crop_province(
        cls,
        fecha: date,
        id_cultivo_general: int,
        id_provincia: int,
    ):
        return await cls.fetch_df(
            select(cls.__table__.c).where(
                and_(
                    cls.fecha == fecha,
                    cls.id_cultivo_general == id_cultivo_general,
                    cls.id_provincia == id_provincia,
                )
            )
        )

    def __repr__(self) -> str:
        return (
            f"BalanceHidricoMerge0p1(formita={self.id_formita}, "
            f"cultivo={self.id_cultivo_general}, fecha={self.fecha})"
        )


class EstadisticasDepartamento0p1(Base, ProvinceScoped):
    __tablename__ = "estadisticas_departamento0p1"

    id_provincia = Column(Integer, ForeignKey("provincias.id_provincia"), primary_key=True)
    id_departamento = Column(
        Integer, ForeignKey("departamentos.id_departamento"), primary_key=True
    )
    id_cultivo_general = Column(
        Integer, ForeignKey("cultivos_generales.id_cultivo_general"), primary_key=True
    )
    fecha = Column(Date, primary_key=True)

    agua_util_mean = Column(Numeric(9, 5))
    agua_util_min = Column(Numeric(9, 5))
    agua_util_max = Column(Numeric(9, 5))
    prop_sequia = Column(Numeric(5, 4))
    prop_escasas = Column(Numeric(5, 4))
    prop_regulares = Column(Numeric(5, 4))
    prop_adecuadas = Column(Numeric(5, 4))
    prop_optimas = Column(Numeric(5, 4))
    prop_excesivas = Column(Numeric(5, 4))
    prop_muy_excesivas = Column(Numeric(5, 4))

    def __repr__(self) -> str:
        return (
            f"EstadisticasDepartamento0p1(depto={self.id_departamento}, "
            f"cultivo={self.id_cultivo_general}, fecha={self.fecha})"
        )
