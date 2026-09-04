"""0.1° land grid, IMERG native grid, and node–province associations."""

from __future__ import annotations

import json

import pandas as pd
from sqlalchemy import Column, ForeignKey, Integer, JSON, Numeric, String, select
from sqlalchemy.orm import relationship

from bh_hidro.db.base import Base
from bh_hidro.db.mixins import ProvinceScoped, TableOps


class ReticulaLand(Base, TableOps):
    __tablename__ = "reticula_land"

    id_nodo = Column(Integer, primary_key=True)
    lat_nodo = Column(Numeric(6, 4), nullable=False)
    lon_nodo = Column(Numeric(7, 4), nullable=False)

    reticula_provincias = relationship(
        "ReticulaLandProvinciaAssociation", back_populates="reticula"
    )

    def __repr__(self) -> str:
        return f"ReticulaLand(id_nodo={self.id_nodo}, lat={self.lat_nodo}, lon={self.lon_nodo})"


class ReticulaLandProvinciaAssociation(Base, ProvinceScoped):
    __tablename__ = "reticulaLand_provincia"

    id_nodo = Column(Integer, ForeignKey("reticula_land.id_nodo"), primary_key=True)
    id_provincia = Column(Integer, ForeignKey("provincias.id_provincia"), primary_key=True)
    id_departamento = Column(
        Integer, ForeignKey("departamentos.id_departamento"), primary_key=True
    )

    reticula = relationship("ReticulaLand", back_populates="reticula_provincias")
    provincia = relationship("Provincia", back_populates="reticula_land_provincias")

    def __repr__(self) -> str:
        return (
            f"ReticulaLandProvinciaAssociation(nodo={self.id_nodo}, "
            f"provincia={self.id_provincia}, depto={self.id_departamento})"
        )


class ReticulaImerg(Base, TableOps):
    __tablename__ = "reticula_imerg"

    id_nodo = Column(Integer, primary_key=True)
    lat_nodo = Column(Numeric(6, 4), nullable=False)
    lon_nodo = Column(Numeric(7, 4), nullable=False)

    reticula_provincias = relationship(
        "ReticulaImergProvinciaAssociation", back_populates="reticula"
    )

    def __repr__(self) -> str:
        return f"ReticulaImerg(id_nodo={self.id_nodo})"


class ReticulaImergProvinciaAssociation(Base, ProvinceScoped):
    __tablename__ = "reticulaimerg_provincia"

    id_nodo = Column(Integer, ForeignKey("reticula_imerg.id_nodo"), primary_key=True)
    id_provincia = Column(Integer, ForeignKey("provincias.id_provincia"), primary_key=True)
    id_departamento = Column(
        Integer, ForeignKey("departamentos.id_departamento"), primary_key=True
    )

    reticula = relationship("ReticulaImerg", back_populates="reticula_provincias")
    provincia = relationship("Provincia", back_populates="reticula_imerg_provincias")

    def __repr__(self) -> str:
        return (
            f"ReticulaImergProvinciaAssociation(nodo={self.id_nodo}, "
            f"provincia={self.id_provincia}, depto={self.id_departamento})"
        )


class PatronKcXNodoLand(Base, TableOps):
    __tablename__ = "patronKc_del_nodo_land"

    id_patronkcnodo = Column(Integer, primary_key=True)
    id_nodo = Column(Integer, ForeignKey("reticula_land.id_nodo"))
    id_cultivo_general = Column(Integer, nullable=False)
    id_tipo_cultivo = Column(JSON)
    id_patron = Column(JSON)

    @classmethod
    async def for_cultivo_general(cls, id_cultivo_general: int) -> pd.DataFrame:
        return await cls.fetch_df(
            select(cls.__table__.c).where(cls.id_cultivo_general == id_cultivo_general)
        )

    @classmethod
    async def read_exploded(cls) -> pd.DataFrame:
        """Parse JSON Kc pattern columns and join crop/pattern catalogs."""
        df = await cls.read_all()
        df["id_tipo_cultivo"] = df["id_tipo_cultivo"].apply(
            lambda x: json.loads(x) if pd.notnull(x) and not isinstance(x, list) else (x or [])
        )
        df["id_patron"] = df["id_patron"].apply(
            lambda x: json.loads(x) if pd.notnull(x) and not isinstance(x, list) else (x or [])
        )
        df = df.explode("id_tipo_cultivo").explode("id_patron")
        df["id_tipo_cultivo"] = pd.to_numeric(df["id_tipo_cultivo"], errors="coerce").astype(
            "Int64"
        )
        df["id_patron"] = pd.to_numeric(df["id_patron"], errors="coerce").astype("Int64")

        from bh_hidro.db.models.agricultural import PatronKc, TipoCultivo

        tipos = await TipoCultivo.read_all()
        patrones = await PatronKc.read_all()
        df = df.merge(tipos, on="id_tipo_cultivo", how="left", suffixes=("", "_tipo"))
        return df.merge(patrones, on="id_patron", how="left", suffixes=("", "_patron"))

    def __repr__(self) -> str:
        return (
            f"PatronKcXNodoLand(nodo={self.id_nodo}, cultivo={self.id_cultivo_general})"
        )


class OrigenImerg(Base, TableOps):
    __tablename__ = "origen_imerg"

    id_origen = Column(Integer, primary_key=True)
    nombre = Column(String(20), nullable=False)
    descripcion = Column(String(100))

    SEED = [
        {"id_origen": 1, "nombre": "ImergCalib", "descripcion": "ImergCalibradoFTP"},
        {"id_origen": 2, "nombre": "final", "descripcion": "ImergFinal"},
        {"id_origen": 3, "nombre": "late", "descripcion": "Imerg Late run"},
        {"id_origen": 4, "nombre": "early", "descripcion": "Imerg Early run"},
    ]

    @classmethod
    async def id_by_name(cls, name: str) -> int:
        df = await cls.read_all()
        return int(df.loc[df.nombre == name, "id_origen"].item())

    def __repr__(self) -> str:
        return f"OrigenImerg(id={self.id_origen}, nombre={self.nombre!r})"
