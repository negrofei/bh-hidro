from datetime import date
from pathlib import Path

from bh_hidro.output.geojson import geojson_name, layer_name


def test_layer_name_matches_tileserver():
    assert layer_name("agua_util", date(2000, 1, 3), "S1") == "agua-util_2000-01-03_S1_0p1"


def test_geojson_name_uses_iso_date(tmp_path: Path):
    path = geojson_name(tmp_path, "agua_util", date(2000, 1, 1), "S1")
    assert path.name == "agua-util_2000-01-01_S1_0p1.geojson"
