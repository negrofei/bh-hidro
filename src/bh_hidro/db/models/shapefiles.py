"""Agricultural soil polygons (merge). NoAgr stays out of the first cut."""

from geoalchemy2 import Geometry
from sqlalchemy import Column, ForeignKey, Integer

from bh_hidro.db.base import Base
from bh_hidro.db.mixins import ProvinceScoped


class SueloShapefileMerge(Base, ProvinceScoped):
    __tablename__ = "suelo_shapefile_Merge"

    id_suelo_shapefile = Column(Integer, primary_key=True)
    id_suelo = Column(Integer, ForeignKey("suelo.id_suelo"))
    id_provincia = Column(Integer, ForeignKey("provincias.id_provincia"))
    geometry = Column(Geometry("GEOMETRY", srid=4326))

    def __repr__(self) -> str:
        return (
            f"SueloShapefileMerge(id={self.id_suelo_shapefile}, "
            f"suelo={self.id_suelo}, provincia={self.id_provincia})"
        )
