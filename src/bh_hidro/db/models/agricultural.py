"""Soil, crop catalog, Kc patterns, phenology, GDD thresholds."""

from sqlalchemy import Column, Date, ForeignKey, Integer, JSON, Numeric, String, func, select

from bh_hidro.db.base import Base
from bh_hidro.db.mixins import TableOps


class Suelo(Base, TableOps):
    __tablename__ = "suelo"

    id_suelo = Column(Integer, primary_key=True)
    tipo_suelo = Column(String(40))
    capacidad_campo = Column(Numeric(7, 4))
    pmp = Column(Numeric(7, 4))
    coef_escurrimiento = Column(Numeric(3, 2))
    coef_percolacion = Column(Numeric(9, 8))
    capacidad_campo_sfc = Column(Numeric(7, 4))
    pmp_sfc = Column(Numeric(7, 4))
    coef_escurrimiento_sfc = Column(Numeric(3, 2))
    coef_percolacion_sfc = Column(Numeric(9, 8))

    def __repr__(self) -> str:
        return f"Suelo(id={self.id_suelo}, tipo={self.tipo_suelo!r})"


class TipoCultivo(Base, TableOps):
    __tablename__ = "tipos_cultivo"

    id_tipo_cultivo = Column(Integer, primary_key=True)
    codigo = Column(String(50))
    nombre = Column(String(75))
    etapa_siembra = Column(Integer)
    etapa_cosecha = Column(Integer)
    etapa_inicioPC_deficit = Column(Integer)
    delta_inicioPC_deficit = Column(Integer)
    etapa_finPC_deficit = Column(Integer)
    delta_finPC_deficit = Column(Integer)
    etapa_inicioPC_exceso = Column(Integer)
    delta_inicioPC_exceso = Column(Integer)
    etapa_finPC_exceso = Column(Integer)
    delta_finPC_exceso = Column(Integer)
    tBase_gdd = Column(Numeric(3, 1))
    tUpper_gdd = Column(Numeric(3, 1))

    def __repr__(self) -> str:
        return f"TipoCultivo(id={self.id_tipo_cultivo}, codigo={self.codigo!r})"


class CultivoGeneral(Base, TableOps):
    __tablename__ = "cultivos_generales"

    id_cultivo_general = Column(Integer, primary_key=True)
    nombre = Column(String(75))
    codigo = Column(String(50))
    cultivos_particulares = Column(JSON)

    def __repr__(self) -> str:
        return f"CultivoGeneral(id={self.id_cultivo_general}, codigo={self.codigo!r})"


class PatronKc(Base, TableOps):
    __tablename__ = "patron_kc"

    id_patron = Column(Integer, primary_key=True)
    codigo = Column(String(10))

    def __repr__(self) -> str:
        return f"PatronKc(id={self.id_patron}, codigo={self.codigo!r})"


class SueloXCentroide(Base, TableOps):
    __tablename__ = "suelo_por_centroide"

    id_centroide = Column(Integer, primary_key=True)
    centroide = Column(String(40))
    tipo_suelo = Column(String(40))
    provincia = Column(String(40))
    x_centroide = Column(Numeric(10, 3))
    y_centroide = Column(Numeric(10, 3))


class KcXCentroideXCultivo(Base, TableOps):
    __tablename__ = "kc_por_centroide_por_cultivo"

    id_centroide_cultivo = Column(Integer, primary_key=True)
    id_centroide = Column(String(50))
    id_tipo_cultivo = Column(String(25))
    id_patron = Column(String(50))


class EtapaFenologica(Base, TableOps):
    __tablename__ = "etapa_fenologica"

    id_etapa = Column(Integer, primary_key=True)
    id_tipo_cultivo = Column(Integer, ForeignKey("tipos_cultivo.id_tipo_cultivo"))
    nombre_etapa = Column(String(30))
    kc = Column(Numeric(3, 2))

    def __repr__(self) -> str:
        return f"EtapaFenologica(id={self.id_etapa}, nombre={self.nombre_etapa!r})"


class RelEtapaPatron(Base, TableOps):
    __tablename__ = "relacion_etapa_patron"

    id_etapa = Column(Integer, ForeignKey("etapa_fenologica.id_etapa"), primary_key=True)
    id_patron = Column(Integer, ForeignKey("patron_kc.id_patron"), primary_key=True)
    juliano = Column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"RelEtapaPatron(etapa={self.id_etapa}, patron={self.id_patron}, juliano={self.juliano})"


class GDDPorNodoEtapa(Base, TableOps):
    """GDD thresholds per node/stage. Artifact of offline analysis; used by GddKc later."""

    __tablename__ = "gdd_por_nodo_etapa"

    id_provincia = Column(Integer, ForeignKey("provincias.id_provincia"), primary_key=True)
    id_cultivo_general = Column(
        Integer, ForeignKey("cultivos_generales.id_cultivo_general"), primary_key=True
    )
    id_tipo_cultivo = Column(
        Integer, ForeignKey("tipos_cultivo.id_tipo_cultivo"), primary_key=True
    )
    id_patron = Column(Integer, ForeignKey("patron_kc.id_patron"), primary_key=True)
    anio_campana = Column(Integer, primary_key=True)
    id_nodo = Column(Integer, ForeignKey("reticula_land.id_nodo"), primary_key=True)
    id_etapa = Column(Integer, ForeignKey("etapa_fenologica.id_etapa"), primary_key=True)

    nombre_etapa = Column(String(30))
    fecha = Column(Date)
    gdd_nodo_etapa = Column(Numeric(9, 2))
    gdd_promedio_etapa = Column(Numeric(9, 2))
    gdd_mediana_etapa = Column(Numeric(9, 2))
    gdd_desvio_estandar_etapa = Column(Numeric(9, 2))

    @classmethod
    async def avg_by_node(
        cls,
        id_provincia: int,
        id_cultivo_general: int,
        id_tipo_cultivo: int,
        id_patron: int,
        id_etapa: int,
    ):
        stmt = (
            select(
                cls.id_nodo,
                cls.nombre_etapa,
                func.avg(cls.gdd_nodo_etapa).label("gdd_promedio_campanas"),
                func.stddev_samp(cls.gdd_nodo_etapa).label("gdd_desvio_campanas"),
                func.count(cls.anio_campana).label("n_campanas"),
            )
            .where(
                cls.id_provincia == id_provincia,
                cls.id_cultivo_general == id_cultivo_general,
                cls.id_tipo_cultivo == id_tipo_cultivo,
                cls.id_patron == id_patron,
                cls.id_etapa == id_etapa,
            )
            .group_by(cls.id_nodo, cls.nombre_etapa)
            .order_by(cls.id_nodo)
        )
        return await cls.fetch_df(stmt)
