"""0p1 ORM contract. 0p25 / ERA5 / NoAgr / estaciones quedan fuera."""

from bh_hidro.db.models.geographic import Departamento, Provincia
from bh_hidro.db.models.grids import (
    OrigenImerg,
    PatronKcXNodoLand,
    ReticulaImerg,
    ReticulaImergProvinciaAssociation,
    ReticulaLand,
    ReticulaLandProvinciaAssociation,
)
from bh_hidro.db.models.agricultural import (
    CultivoGeneral,
    EtapaFenologica,
    GDDPorNodoEtapa,
    KcXCentroideXCultivo,
    PatronKc,
    RelEtapaPatron,
    Suelo,
    SueloXCentroide,
    TipoCultivo,
)
from bh_hidro.db.models.shapefiles import SueloShapefileMerge
from bh_hidro.db.models.formitas import FormitasMerge0p1
from bh_hidro.db.models.atmospheric import DatoERALand, GFS0p1, Imerg0p1, ImergNative, WRF0p1
from bh_hidro.db.models.balance import BalanceHidricoMerge0p1, EstadisticasDepartamento0p1
from bh_hidro.db.models.custom import (
    BalanceHidricoCustom0p1,
    UsuarioCampana,
    UsuarioCampo,
)

__all__ = [
    "Provincia",
    "Departamento",
    "ReticulaLand",
    "ReticulaLandProvinciaAssociation",
    "ReticulaImerg",
    "ReticulaImergProvinciaAssociation",
    "PatronKcXNodoLand",
    "OrigenImerg",
    "Suelo",
    "TipoCultivo",
    "CultivoGeneral",
    "PatronKc",
    "SueloXCentroide",
    "KcXCentroideXCultivo",
    "EtapaFenologica",
    "RelEtapaPatron",
    "GDDPorNodoEtapa",
    "SueloShapefileMerge",
    "FormitasMerge0p1",
    "DatoERALand",
    "WRF0p1",
    "GFS0p1",
    "Imerg0p1",
    "ImergNative",
    "BalanceHidricoMerge0p1",
    "EstadisticasDepartamento0p1",
    "UsuarioCampo",
    "UsuarioCampana",
    "BalanceHidricoCustom0p1",
]
