"""Sequential GeoJSON (+ tippecanoe if available). No PNG in the cron."""

from __future__ import annotations

import logging
from datetime import date

from bh_hidro.balance.crops import crop_ids
from bh_hidro.config import Settings, get_settings
from bh_hidro.db.models.geographic import Provincia
from bh_hidro.ingest.download.windows import daterange
from bh_hidro.output.geojson import features_for_date, geojson_name, write_geojson
from bh_hidro.output.ini import OutputIni
from bh_hidro.output.tiles import geojson_to_mbtiles

logger = logging.getLogger(__name__)


async def run_output(
    settings: Settings | None = None,
    start: date | None = None,
    end: date | None = None,
    dry_run: bool = False,
    today: date | None = None,
) -> dict[str, dict[date, str]]:
    settings = settings or get_settings()
    cfg = OutputIni.load(settings.output_config, settings=settings, start=start, end=end, today=today)
    dates = daterange(cfg.start, cfg.end)
    try:
        crops = await crop_ids(cfg.crops)
        provinces = await Provincia.ids_by_names(cfg.provinces)
    except Exception as exc:
        logger.warning("Could not read crops/provinces from MySQL (%s)", exc)
        if dry_run:
            return {"output": {d: "dry-run" for d in dates}}
        raise

    logger.info("Starting output workflow %s..%s variable=%s", cfg.start, cfg.end, cfg.variable)
    out: dict[str, dict[date, str]] = {}
    for _, crop in crops.iterrows():
        crop_id = int(crop["id_cultivo_general"])
        code = str(crop.get("codigo", crop_id))
        out[code] = {}
        for fecha in dates:
            if dry_run:
                out[code][fecha] = "dry-run"
                continue
            try:
                logger.info("Generating %s for crop %s on %s", cfg.variable, code, fecha)
                features = await features_for_date(fecha, crop_id, provinces, cfg.variable)
                if not features:
                    logger.warning("No balance features for crop %s %s; skip", code, fecha)
                    out[code][fecha] = "skip"
                    continue
                path = geojson_name(cfg.out_dir, cfg.variable, fecha, code)
                write_geojson(path, features)
                tiles = geojson_to_mbtiles(path, cfg.tiles_dir, cfg.min_zoom, cfg.max_zoom)
                out[code][fecha] = "ok" if tiles else f"geojson:{path.name}"
            except Exception as exc:
                logger.exception("output %s %s failed: %s", code, fecha, exc)
                out[code][fecha] = "ERROR"
    logger.info("Output workflow finish")
    return out
