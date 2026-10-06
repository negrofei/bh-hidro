"""0p1 calendar-Kc balance. One process per (crop, province); dates stay sequential."""

from __future__ import annotations

import asyncio
import logging
import multiprocessing as mp
import os
from datetime import date, timedelta
from pathlib import Path
from typing import NamedTuple

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
from bh_hidro.db.connection import dispose_engine
from bh_hidro.db.models.balance import BalanceHidricoMerge0p1
from bh_hidro.db.models.geographic import Provincia
from bh_hidro.ingest.download.windows import daterange
from bh_hidro.ingest.download.to_db import keep_table_columns
from bh_hidro.ingest.pool import map_processes
from bh_hidro.log import setup_process_logging

logger = logging.getLogger(__name__)


class MissingPreviousBalance(Exception):
    """Yesterday is missing and policy forbids init / continue-from-last."""


class BalancePairTask(NamedTuple):
    crop_id: int
    crop_code: str
    province_id: int
    cfg: BalanceIni
    dry_run: bool
    logmode: str
    log_dir: str


def _numeric_ids(df: pd.DataFrame) -> pd.DataFrame:
    skip = {"fecha", "pp_from", "etp_from"}
    for col in df.columns:
        if col.startswith("id_") or col in skip:
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def initial_state_frame(base: pd.DataFrame, ayer: date) -> pd.DataFrame:
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
    logger.debug("Kc groups=%s for %s", len(rows), fecha)
    return super_df.merge(pd.DataFrame(rows), on=["id_patron", "id_tipo_cultivo"], how="left")


async def previous_state(
    base: pd.DataFrame,
    fecha: date,
    id_cultivo_general: int,
    id_provincia: int,
    *,
    first_day: date,
    raise_if_data_gap: bool,
) -> pd.DataFrame:
    """Previous-day almacenaje. 50% init only for FIRST_DAY_OF_ALL_TIME."""
    ayer = fecha - timedelta(days=1)
    loaded = await BalanceHidricoMerge0p1.by_fecha_crop_province(ayer, id_cultivo_general, id_provincia)
    if not loaded.empty:
        logger.debug("Yesterday %s is in database for crop=%s provincia=%s", ayer, id_cultivo_general, id_provincia)
        return loaded

    if fecha == first_day:
        logger.warning(
            "First day of all time %s; initializing almacenaje at 50%% agua útil",
            fecha,
        )
        return initial_state_frame(base, ayer)

    existing = await BalanceHidricoMerge0p1.dates_for_crop_province(id_cultivo_general, id_provincia)
    last: date | None = None
    if not existing.empty:
        last = max(row.date() if hasattr(row, "date") else row for row in existing["fecha"])

    if last is not None and last < ayer and not raise_if_data_gap:
        logger.warning(
            "No balance for %s; continuing from last loaded %s (raise_if_data_gap=False)",
            ayer,
            last,
        )
        return await BalanceHidricoMerge0p1.by_fecha_crop_province(last, id_cultivo_general, id_provincia)

    if last is not None and last < ayer:
        raise MissingPreviousBalance(
            f"No balance for {ayer} (crop={id_cultivo_general} provincia={id_provincia}); "
            f"last loaded {last}. Set raise_if_data_gap=False to continue from last."
        )
    raise MissingPreviousBalance(
        f"No balance for {ayer} (crop={id_cultivo_general} provincia={id_provincia}); "
        f"cannot init except on first_day={first_day}"
    )


async def dates_to_run(cfg: BalanceIni, id_cultivo_general: int, id_provincia: int) -> list[date]:
    """Always recompute the whole window. ERALand reanalysis corrects prior WRF days."""
    wanted = daterange(cfg.start, cfg.end)
    logger.debug(
        "Recomputing balance crop=%s provincia=%s dates=%s..%s (%s days)",
        id_cultivo_general,
        id_provincia,
        wanted[0] if wanted else None,
        wanted[-1] if wanted else None,
        len(wanted),
    )
    return wanted


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
    *,
    first_day: date,
    raise_if_data_gap: bool,
) -> pd.DataFrame:
    prev = await previous_state(
        base,
        fecha,
        id_cultivo_general,
        id_provincia,
        first_day=first_day,
        raise_if_data_gap=raise_if_data_gap,
    )
    precip, from_pp = await get_precip(fecha, id_provincia, precip_priority)
    etp, from_etp = await get_etp(fecha, id_provincia, etp_priority)
    # Precip always covers every province node (missing → 0). Keep all formitas;
    # ETP must also match or we refuse the day instead of silently dropping rows.
    super_df = base.merge(precip, on="id_nodo", how="left")
    if super_df["tp"].isna().any():
        raise ValueError(
            f"precip incomplete for {fecha} provincia={id_provincia} "
            f"after {from_pp}: {int(super_df['tp'].isna().sum())} nodes"
        )
    super_df = super_df.merge(etp, on="id_nodo", how="left")
    if super_df["etp"].isna().any():
        raise ValueError(
            f"ETP incomplete for {fecha} provincia={id_provincia} after {from_etp}: "
            f"{int(super_df['etp'].isna().sum())} nodes — cannot drop formitas"
        )
    if len(super_df) != len(base):
        raise ValueError(
            f"balance rows {len(super_df)} != formitas {len(base)} on {fecha} "
            f"(pp={from_pp}, etp={from_etp})"
        )
    prev_cols = prev.reset_index(drop=True)
    keep = [c for c in (*BALANCE_INDEX, "almacenaje", "exceso") if c in prev_cols.columns]
    super_df = super_df.merge(prev_cols[keep], on=BALANCE_INDEX, how="left")
    super_df = attach_calendar_kc(super_df, fecha, df_fenologia, reletapapatron, nombre_cultivos)
    super_df = _numeric_ids(super_df)
    for col in ("pmp", "capacidad_campo", "coef_escurrimiento", "coef_percolacion", "kc", "etp", "tp", "almacenaje", "exceso"):
        super_df[col] = super_df[col].astype(float)
    logger.info(
        "Calculating balance for crop %s on %s (provincia=%s, pp=%s, etp=%s, n=%s)",
        id_cultivo_general,
        fecha,
        id_provincia,
        from_pp,
        from_etp,
        len(super_df),
    )
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
    dropped = out.dropna(subset=BALANCE_INDEX + ["almacenaje", "agua_util"])
    logger.debug(
        "FAO crop=%s provincia=%s %s au_mean=%.3f rows=%s",
        id_cultivo_general,
        id_provincia,
        fecha,
        float(dropped["agua_util"].mean()) if not dropped.empty else float("nan"),
        len(dropped),
    )
    return dropped


async def run_crop_province(cfg: BalanceIni, id_cultivo_general: int, id_provincia: int, dry_run: bool) -> dict[date, str]:
    dates = await dates_to_run(cfg, id_cultivo_general, id_provincia)
    logger.info(
        "Starting balance crop=%s provincia=%s dates=%s (recompute/upsert)",
        id_cultivo_general,
        id_provincia,
        dates,
    )
    if dry_run:
        return {d: "dry-run" for d in dates}
    if not dates:
        return {}
    logger.info("Building soil/pattern dataframe for crop=%s provincia=%s", id_cultivo_general, id_provincia)
    base = await base_frame(id_cultivo_general, id_provincia)
    if base.empty:
        logger.warning("No formitas for crop=%s provincia=%s", id_cultivo_general, id_provincia)
        return {d: "skip" for d in dates}
    logger.info(
        "Data loaded for crop=%s provincia=%s formitas=%s",
        id_cultivo_general,
        id_provincia,
        len(base),
    )
    tipos = await tipos_from_cultivo_general(id_cultivo_general)
    df_fenologia = await fenologia(tipos)
    reletapapatron = await rel_etapa_patron()
    nombre_cultivos = await nombres_tipo(base["id_tipo_cultivo"].unique())
    logger.info("Starting daily balance calculations for crop=%s provincia=%s", id_cultivo_general, id_provincia)
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
                first_day=cfg.first_day,
                raise_if_data_gap=cfg.raise_if_data_gap,
            )
            logger.info("Inserting %s rows for crop=%s provincia=%s %s", len(rows), id_cultivo_general, id_provincia, fecha)
            payload = keep_table_columns(rows, BalanceHidricoMerge0p1)
            await BalanceHidricoMerge0p1.upsert_df(payload, chunk_size=cfg.chunk_size)
            stats_src = payload.copy()
            if "area_formita" in rows.columns:
                stats_src["area_formita"] = rows["area_formita"].values
            stats = stats_from_balance(stats_src, fecha, id_cultivo_general)
            await upsert_stats(stats, chunk=cfg.chunk_size)
            out[fecha] = f"ok:{len(payload)}"
        except MissingPreviousBalance as exc:
            logger.error("balance %s %s %s skipped: %s", id_cultivo_general, id_provincia, fecha, exc)
            out[fecha] = "skip-gap"
            for later in dates[dates.index(fecha) + 1 :]:
                out[later] = "skip-gap"
                logger.error(
                    "balance %s %s %s skipped: depends on missing previous day",
                    id_cultivo_general,
                    id_provincia,
                    later,
                )
            break
        except Exception as exc:
            logger.exception("balance %s %s %s failed: %s", id_cultivo_general, id_provincia, fecha, exc)
            out[fecha] = "ERROR"
    logger.info("Balance completed for crop=%s provincia=%s", id_cultivo_general, id_provincia)
    return out


def _balance_pair_worker(task: BalancePairTask) -> dict[date, str]:
    mp.current_process().name = f"balance_cult{task.crop_id}_prov{task.province_id}"
    setup_process_logging(Path(task.log_dir), task.logmode, mp.current_process().name)
    logger.info(
        "Process started for crop %s:%s, province %s (pid=%s)",
        task.crop_id,
        task.crop_code,
        task.province_id,
        os.getpid(),
    )

    async def _go() -> dict[date, str]:
        try:
            return await run_crop_province(task.cfg, task.crop_id, task.province_id, task.dry_run)
        finally:
            await dispose_engine()

    result = asyncio.run(_go())
    logger.info("Process completed for crop %s, province %s", task.crop_id, task.province_id)
    return result


async def run_balance(
    settings: Settings | None = None,
    start: date | None = None,
    end: date | None = None,
    dry_run: bool = False,
    today: date | None = None,
    logmode: str = "info",
) -> dict[str, dict[date, str]]:
    settings = settings or get_settings()
    cfg = BalanceIni.load(settings.balance_config, settings=settings, start=start, end=end, today=today)
    logger.info("Starting balance calculation workflow")
    logger.info("Precipitation priority: %s", cfg.precip_priority)
    logger.info("ETP priority: %s", cfg.etp_priority)
    try:
        crops = await crop_ids(cfg.crops)
        provinces = await Provincia.ids_by_names(cfg.provinces)
    except Exception as exc:
        logger.warning("Could not read crops/provinces from MySQL (%s)", exc)
        if dry_run:
            return {"balance": {d: "dry-run" for d in daterange(cfg.start, cfg.end)}}
        raise
    pairs = [
        (int(crop["id_cultivo_general"]), str(crop.get("codigo", crop["id_cultivo_general"])), int(prov_id))
        for _, crop in crops.iterrows()
        for prov_id in provinces
    ]
    workers = 1 if dry_run else cfg.fetch_workers
    logger.info(
        "Loaded %s crops and %s provinces (%s pairs); workers=%s dates=%s..%s",
        len(crops),
        len(provinces),
        len(pairs),
        workers,
        cfg.start,
        cfg.end,
    )
    if workers <= 1 or len(pairs) <= 1:
        results: dict[str, dict[date, str]] = {}
        for crop_id, code, prov_id in pairs:
            key = f"{code}:{prov_id}"
            try:
                results[key] = await run_crop_province(cfg, crop_id, prov_id, dry_run)
            except Exception as exc:
                logger.exception("balance %s failed: %s", key, exc)
                results[key] = {cfg.start: "ERROR"}
        logger.info("Balance calculation workflow finish")
        return results

    await dispose_engine()
    tasks = [
        BalancePairTask(crop_id, code, prov_id, cfg, dry_run, logmode, str(settings.log_dir))
        for crop_id, code, prov_id in pairs
    ]
    rows = await asyncio.to_thread(map_processes, _balance_pair_worker, tasks, workers, desc="balance")
    results = {}
    for task, payload, err in rows:
        key = f"{task.crop_code}:{task.province_id}"
        if err is not None:
            logger.error("balance %s failed: %s", key, err)
            results[key] = {cfg.start: "ERROR"}
        else:
            results[key] = payload
            logger.info("Successfully calculated balance for crop %s, region %s", task.crop_id, task.province_id)
    logger.info("Balance calculation workflow finish")
    return results
