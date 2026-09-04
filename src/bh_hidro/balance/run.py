"""Sequential 0p1 calendar-Kc balance. No multiprocessing, no NoAgr, no 0.25°."""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd

from bh_hidro.balance.crops import (
    base_frame,
    crop_ids,
    fenologia,
    nombres_tipo,
    rel_etapa_patron,
    tipos_from_cultivo_general,
)
from bh_hidro.balance.engine import BALANCE_INDEX, balance_hidrico_pandarized, initial_almacenaje
from bh_hidro.balance.ini import BalanceIni
from bh_hidro.balance.kc import CalendarKc
from bh_hidro.balance.sources import get_etp, get_precip
from bh_hidro.balance.stats import stats_from_balance, upsert_stats
from bh_hidro.config import Settings, get_settings
from bh_hidro.db.models.balance import BalanceHidricoMerge0p1
from bh_hidro.db.models.geographic import Provincia
from bh_hidro.ingest.download.windows import daterange
from bh_hidro.ingest.download.to_db import keep_table_columns

logger = logging.getLogger(__name__)


def _numeric_ids(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if col.startswith("id_") or col in ("fecha", "pp_from", "etp_from"):
            continue
        df[col] = pd.to_numeric(df[col], errors="ignore")
    return df


def attach_calendar_kc(
    super_df: pd.DataFrame,
    fecha: date,
    df_fenologia: pd.DataFrame,
    reletapapatron: pd.DataFrame,
    nombre_cultivos: dict[int, str],
) -> pd.DataFrame:
    kc = CalendarKc()
    grouped = super_df.groupby(["id_patron", "id_tipo_cultivo"], sort=False)
    rows = []
    for (patron, tipo), _group in grouped:
        rows.append(
            {
                "id_patron": patron,
                "id_tipo_cultivo": tipo,
                "kc": kc.kc_for_date(
                    fecha=fecha,
                    patron=patron,
                    id_tipo_cultivo=tipo,
                    df_fenologia=df_fenologia,
                    reletapapatron=reletapapatron,
                    nombre_cultivos=nombre_cultivos,
                ),
            }
        )
    return super_df.merge(pd.DataFrame(rows), on=["id_patron", "id_tipo_cultivo"], how="left")


async def previous_state(
    base: pd.DataFrame,
    fecha: date,
    id_cultivo_general: int,
    id_provincia: int,
) -> pd.DataFrame:
    ayer = fecha - timedelta(days=1)
    loaded = await BalanceHidricoMerge0p1.by_fecha_crop_province(ayer, id_cultivo_general, id_provincia)
    if not loaded.empty:
        return loaded
    existing = await BalanceHidricoMerge0p1.dates_for_crop_province(id_cultivo_general, id_provincia)
    if not existing.empty:
        last = max(row.date() if hasattr(row, "date") else row for row in existing["fecha"])
        if last < ayer:
            logger.warning("Using last loaded balance %s as previous state for %s", last, fecha)
            return await BalanceHidricoMerge0p1.by_fecha_crop_province(last, id_cultivo_general, id_provincia)
    logger.warning("No balance for %s; initializing almacenaje at 50%% agua útil", ayer)
    init = base[BALANCE_INDEX].copy()
    init["fecha"] = ayer
    init["almacenaje"] = initial_almacenaje(base["pmp"].astype(float), base["capacidad_campo"].astype(float))
    init["exceso"] = 0.0
    init["escurrimiento"] = 0.0
    init["percolacion"] = 0.0
    init["agua_util"] = 0.5
    init["pp_from"] = "init"
    init["etp_from"] = "init"
    return init


async def dates_to_run(cfg: BalanceIni, id_cultivo_general: int, id_provincia: int) -> list[date]:
    wanted = daterange(cfg.start, cfg.end)
    existing = await BalanceHidricoMerge0p1.dates_for_crop_province(id_cultivo_general, id_provincia)
    if existing.empty:
        return wanted
    loaded = {row.date() if hasattr(row, "date") else row for row in existing["fecha"]}
    last = max(loaded)
    return [d for d in wanted if d > last]


async def run_one_day(
    base: pd.DataFrame,
    fecha: date,
    id_cultivo_general: int,
    id_provincia: int,
    df_fenologia: pd.DataFrame,
    reletapapatron: pd.DataFrame,
    nombre_cultivos: dict[int, str],
    precip_priority: list[str],
    etp_priority: list[str],
) -> pd.DataFrame:
    prev = await previous_state(base, fecha, id_cultivo_general, id_provincia)
    precip, from_pp = await get_precip(fecha, id_provincia, precip_priority)
    etp, from_etp = await get_etp(fecha, id_provincia, etp_priority)
    super_df = base.merge(etp, on="id_nodo").merge(precip, on="id_nodo")
    prev_cols = prev.reset_index(drop=True)
    keep = [c for c in (*BALANCE_INDEX, "almacenaje", "exceso") if c in prev_cols.columns]
    super_df = super_df.merge(prev_cols[keep], on=BALANCE_INDEX, how="left")
    super_df = attach_calendar_kc(super_df, fecha, df_fenologia, reletapapatron, nombre_cultivos)
    super_df = _numeric_ids(super_df)
    for col in ("pmp", "capacidad_campo", "coef_escurrimiento", "coef_percolacion", "kc", "etp", "tp", "almacenaje", "exceso"):
        super_df[col] = super_df[col].astype(float)
    almacenaje, exceso, _pp, esc, per, _etr, agua_util = balance_hidrico_pandarized(super_df)
    out = super_df[BALANCE_INDEX].copy()
    out["fecha"] = fecha
    out["almacenaje"] = almacenaje.round(3).values
    out["exceso"] = exceso.round(3).values
    out["escurrimiento"] = esc.round(3).values
    out["percolacion"] = per.round(3).values
    out["agua_util"] = agua_util.round(3).values
    out["pp_from"] = from_pp
    out["etp_from"] = from_etp
    if "area_formita" in super_df.columns:
        out["area_formita"] = super_df["area_formita"].values
    return out.dropna(subset=BALANCE_INDEX + ["almacenaje", "agua_util"])


async def run_crop_province(cfg: BalanceIni, id_cultivo_general: int, id_provincia: int, dry_run: bool) -> dict[date, str]:
    dates = await dates_to_run(cfg, id_cultivo_general, id_provincia)
    logger.info("balance crop=%s provincia=%s dates=%s", id_cultivo_general, id_provincia, dates)
    if dry_run:
        return {d: "dry-run" for d in dates}
    if not dates:
        return {}
    base = await base_frame(id_cultivo_general, id_provincia)
    if base.empty:
        logger.warning("No formitas for crop=%s provincia=%s", id_cultivo_general, id_provincia)
        return {d: "skip" for d in dates}
    tipos = await tipos_from_cultivo_general(id_cultivo_general)
    df_fenologia = await fenologia(tipos)
    reletapapatron = await rel_etapa_patron()
    nombre_cultivos = await nombres_tipo(base["id_tipo_cultivo"].unique())
    out: dict[date, str] = {}
    for fecha in dates:
        try:
            rows = await run_one_day(
                base,
                fecha,
                id_cultivo_general,
                id_provincia,
                df_fenologia,
                reletapapatron,
                nombre_cultivos,
                cfg.precip_priority,
                cfg.etp_priority,
            )
            payload = keep_table_columns(rows, BalanceHidricoMerge0p1)
            await BalanceHidricoMerge0p1.upsert_df(payload, chunk_size=cfg.chunk_size)
            stats_src = payload.copy()
            if "area_formita" in rows.columns:
                stats_src["area_formita"] = rows["area_formita"].values
            stats = stats_from_balance(stats_src, fecha, id_cultivo_general)
            await upsert_stats(stats, chunk=cfg.chunk_size)
            out[fecha] = f"ok:{len(payload)}"
        except Exception as exc:
            logger.error("balance %s %s %s failed: %s", id_cultivo_general, id_provincia, fecha, exc)
            out[fecha] = "ERROR"
    return out


async def run_balance(
    settings: Settings | None = None,
    start: date | None = None,
    end: date | None = None,
    dry_run: bool = False,
    today: date | None = None,
) -> dict[str, dict[date, str]]:
    settings = settings or get_settings()
    cfg = BalanceIni.load(settings.balance_config, settings=settings, start=start, end=end, today=today)
    try:
        crops = await crop_ids(cfg.crops)
        provinces = await Provincia.ids_by_names(cfg.provinces)
    except Exception as exc:
        logger.warning("Could not read crops/provinces from MySQL (%s)", exc)
        if dry_run:
            return {"balance": {d: "dry-run" for d in daterange(cfg.start, cfg.end)}}
        raise
    results: dict[str, dict[date, str]] = {}
    for _, crop in crops.iterrows():
        crop_id = int(crop["id_cultivo_general"])
        code = crop.get("codigo", crop_id)
        for prov_id in provinces:
            key = f"{code}:{prov_id}"
            try:
                results[key] = await run_crop_province(cfg, crop_id, prov_id, dry_run)
            except Exception as exc:
                logger.error("balance %s failed: %s", key, exc)
                results[key] = {cfg.start: "ERROR"}
    return results
