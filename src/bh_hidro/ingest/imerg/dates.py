"""IMERG dates: operative window clipped to yesterday."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from bh_hidro.ingest.download.windows import daterange


def needs_next_month_listing(fecha: date) -> bool:
    return fecha.month != (fecha + timedelta(days=1)).month


def clip_imerg(start: date, end: date, today: date) -> list[date]:
    last = today - timedelta(days=1)
    end = min(end, last)
    if start > end:
        return []
    return daterange(start, end)


def best_origin_by_date(loaded: pd.DataFrame | None) -> dict[date, int]:
    if loaded is None or loaded.empty:
        return {}
    df = loaded.copy()
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    return df.groupby("fecha", sort=False)["id_origen"].min().to_dict()
