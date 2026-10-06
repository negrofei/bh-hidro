from sqlalchemy.orm import configure_mappers

from bh_hidro.db.base import Base
from bh_hidro.db.models import __all__ as MODEL_NAMES
from bh_hidro.db import models  # noqa: F401

EXPECTED_TABLES = {
    "provincias",
    "departamentos",
    "reticula_land",
    "reticulaLand_provincia",
    "reticula_imerg",
    "reticulaimerg_provincia",
    "patronKc_del_nodo_land",
    "origen_imerg",
    "suelo",
    "tipos_cultivo",
    "cultivos_generales",
    "patron_kc",
    "suelo_por_centroide",
    "kc_por_centroide_por_cultivo",
    "etapa_fenologica",
    "relacion_etapa_patron",
    "gdd_por_nodo_etapa",
    "suelo_shapefile_Merge",
    "formitas_merge_0p1",
    "datos_eraland",
    "wrf0p1",
    "gfs0p1",
    "imerg0p1",
    "imerg",
    "balance_hidrico_merge0p1",
    "estadisticas_departamento0p1",
    "usuario_campo",
    "usuario_campana",
    "balance_hidrico_custom0p1",
}

EXCLUDED_TABLES = {
    "datos_era5",
    "reticula_era5",
    "reticulaERA5_provincia",
    "gfs0p25",
    "wrf0p25",
    "imerg0p25",
    "formitas_merge_0p25",
    "formitas_noAgr_0p1",
    "balance_hidrico_merge0p25",
    "balance_hidrico_noAgr0p1",
    "estaciones",
}


def test_mappers_configure():
    configure_mappers()


def test_expected_tables_match_prod_names():
    configure_mappers()
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_first_cut_excludes_era5_gfs025():
    configure_mappers()
    names = set(Base.metadata.tables)
    assert names.isdisjoint(EXCLUDED_TABLES)


def test_gfs0p1_columns():
    cols = {c.name for c in Base.metadata.tables["gfs0p1"].columns}
    assert {"id_nodo", "fecha", "t2m_min", "t2m_max", "tp", "etp", "day_prono"} <= cols


def test_public_model_exports():
    for name in MODEL_NAMES:
        assert hasattr(models, name)


def test_balance_fk_points_at_formitas():
    table = Base.metadata.tables["balance_hidrico_merge0p1"]
    fks = {fk.target_fullname for fk in table.foreign_keys}
    assert any(name.startswith("formitas_merge_0p1.") for name in fks)
    assert "datos_eraland" in Base.metadata.tables
    cols = {c.name for c in table.columns}
    assert {"almacenaje", "agua_util", "pp_from", "etp_from"} <= cols


def test_eraland_has_temperature_and_etp():
    cols = {c.name for c in Base.metadata.tables["datos_eraland"].columns}
    assert {"id_nodo", "fecha", "t2m_min", "t2m_max", "tp", "etp", "pev"} <= cols


def test_status_reports_model_count(capsys):
    from bh_hidro.cli import main

    assert main(["status"]) == 0
    assert f"models:   {len(EXPECTED_TABLES)} tables" in capsys.readouterr().out


def test_dates_loaded_select_keeps_fecha_name():
    from sqlalchemy import select

    from bh_hidro.db.models.atmospheric import Imerg0p1

    broken = select(Imerg0p1.__table__.c.fecha.distinct(), Imerg0p1.id_origen)
    assert "fecha" not in broken.selected_columns.keys()

    stmt = (
        select(Imerg0p1.__table__.c.fecha.label("fecha"), Imerg0p1.id_origen)
        .where(Imerg0p1.fecha.between("2000-01-01", "2000-01-03"))
        .distinct()
    )
    assert list(stmt.selected_columns.keys())[0] == "fecha"
    assert "id_origen" in stmt.selected_columns.keys()
