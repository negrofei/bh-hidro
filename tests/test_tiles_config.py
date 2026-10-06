import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_generate_config_lists_dated_layers(tmp_path: Path):
    (tmp_path / "agua-util_2000-01-01_S1_0p1.mbtiles").write_bytes(b"")
    (tmp_path / "provincias.mbtiles").write_bytes(b"")
    env = {**os.environ, "TILES_DIR": str(tmp_path), "tiles_dir_local": str(tmp_path)}
    subprocess.run(
        ["sh", str(ROOT / "scripts/tiles/generate_config.sh")],
        check=True,
        env=env,
        cwd=str(ROOT),
    )
    config = json.loads((tmp_path / "config.json").read_text())
    assert config["data"]["provincias"]["mbtiles"] == "provincias.mbtiles"
    layer = "agua-util_2000-01-01_S1_0p1"
    assert layer in config["data"]
    assert config["data"][layer]["date"] == "2000-01-01"
    assert config["data"][layer]["mbtiles"] == f"{layer}.mbtiles"
