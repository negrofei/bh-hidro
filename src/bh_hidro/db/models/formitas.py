"""Formita = node × soil polygon × department. Daily balance unit."""

from geoalchemy2 import Geometry
from sqlalchemy import Column, ForeignKey, Index, Integer, UniqueConstraint

from bh_hidro.db.base import Base
from bh_hidro.db.mixins import ProvinceScoped


class FormitasMerge0p1(Base, ProvinceScoped):
    __tablename__ = "formitas_merge_0p1"

    id_formita = Column(Integer, primary_key=True, autoincrement=True)
    id_provincia = Column(Integer, ForeignKey("provincias.id_provincia"), primary_key=True)
    id_departamento = Column(
        Integer, ForeignKey("departamentos.id_departamento"), primary_key=True
    )
    id_nodo = Column(Integer, ForeignKey("reticula_land.id_nodo"), primary_key=True)
    id_suelo = Column(Integer, ForeignKey("suelo.id_suelo"), primary_key=True)
    shape_formita = Column(Geometry("GEOMETRY", srid=4326))

    __table_args__ = (
        Index("idx_formitas_merge_formita", "id_formita"),
        Index("idx_formitas_merge_provincia", "id_provincia"),
        Index("idx_formitas_merge_dpto", "id_departamento"),
        Index("idx_formitas_merge_suelo", "id_suelo"),
        Index("idx_formitas_merge_nodo", "id_nodo"),
        UniqueConstraint(
            "id_formita",
            "id_provincia",
            "id_departamento",
            "id_suelo",
            "id_nodo",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"FormitasMerge0p1(formita={self.id_formita}, nodo={self.id_nodo}, "
            f"suelo={self.id_suelo})"
        )
