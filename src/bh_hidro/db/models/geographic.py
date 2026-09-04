"""Provinces and departments. Geometry is the DB contract; loading shapefiles is init, later."""

from sqlalchemy import Column, ForeignKey, Index, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry

from bh_hidro.db.base import Base
from bh_hidro.db.mixins import ProvinceScoped, TableOps


class Provincia(Base, TableOps):
    __tablename__ = "provincias"

    id_provincia = Column(Integer, primary_key=True)
    nombre = Column(String(100), unique=True, nullable=False)
    geometry = Column(Geometry("GEOMETRY", srid=4326), nullable=False)

    departamentos = relationship("Departamento", back_populates="provincia")
    reticula_land_provincias = relationship(
        "ReticulaLandProvinciaAssociation", back_populates="provincia"
    )
    reticula_imerg_provincias = relationship(
        "ReticulaImergProvinciaAssociation", back_populates="provincia"
    )

    __table_args__ = (Index("idx_provincia_nombre", "nombre"),)

    @classmethod
    async def ids_by_names(cls, names: list[str]) -> list[int]:
        df = await cls.fetch_df(select(cls.id_provincia).where(cls.nombre.in_(names)))
        return df["id_provincia"].tolist()

    def __repr__(self) -> str:
        return f"Provincia(id={self.id_provincia}, nombre={self.nombre!r})"


class Departamento(Base, ProvinceScoped):
    __tablename__ = "departamentos"

    id_departamento = Column(Integer, primary_key=True)
    id_provincia = Column(Integer, ForeignKey("provincias.id_provincia"), nullable=False)
    nombre = Column(String(100), nullable=False)
    geometry = Column(Geometry("GEOMETRY", srid=4326), nullable=False)

    provincia = relationship("Provincia", back_populates="departamentos")

    __table_args__ = (
        Index("idx_departamento_provincia", "id_provincia"),
        Index("idx_departamento_nombre", "nombre"),
        UniqueConstraint("id_provincia", "nombre", name="uq_departamento_provincia_nombre"),
    )

    def __repr__(self) -> str:
        return (
            f"Departamento(id={self.id_departamento}, nombre={self.nombre!r}, "
            f"provincia={self.id_provincia})"
        )
