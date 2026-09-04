"""Kc strategies. Calendar (cron) vs GDD (user sowing date). Copied interpolation, not rewritten."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import date, timedelta

import numpy as np
import pandas as pd

from bh_hidro.balance.engine import STUBBLE_KC

logger = logging.getLogger(__name__)


def juliano2fechas(julianos: pd.Series, fecha: date) -> np.ndarray:
    if "juliano" not in julianos.name:
        raise ValueError("Este dataframe no tiene columna 'juliano'")

    fechas = julianos.apply(lambda x: date(fecha.year, 1, 1) + timedelta(days=(x - 1)))
    fechas = np.where(fechas < fechas.iloc[0], fechas + timedelta(days=365), fechas)

    if any(julianos.diff() < 0):
        idx = int(np.where((julianos.diff() < 0).to_numpy() == True)[0][0])  # noqa: E712
        if any(int(fecha.strftime("%j")) > julianos.iloc[:idx]):
            pass
        else:
            fechas = fechas - timedelta(days=365)
    return fechas


class KcStrategy(ABC):
    @abstractmethod
    def kc_for_date(self, *args, **kwargs):
        raise NotImplementedError


class CalendarKc(KcStrategy):
    """Julian-day mean phenology from patron_kc / rel_etapa_patron."""

    def kc_for_date(
        self,
        fecha: date,
        patron: int | list | tuple,
        id_tipo_cultivo: int | list | tuple,
        df_fenologia: pd.DataFrame,
        reletapapatron: pd.DataFrame,
        nombre_cultivos: dict[int, str] | None = None,
    ) -> float:
        nombre_cultivos = nombre_cultivos or {}
        if isinstance(id_tipo_cultivo, int):
            nombre_cultivo = nombre_cultivos.get(id_tipo_cultivo, str(id_tipo_cultivo))
        else:
            nombre_cultivo = nombre_cultivos.get(id_tipo_cultivo[0], str(id_tipo_cultivo[0]))

        if isinstance(patron, int):
            patron2 = pd.DataFrame([patron], columns=["id_patron"])
        else:
            patron2 = pd.DataFrame(list(patron), columns=["id_patron"])
        patron2.id_patron = patron2.id_patron.astype(int)

        df_etapa_patron = pd.merge(reletapapatron, patron2, on="id_patron", how="inner")

        if isinstance(id_tipo_cultivo, int):
            pass
        elif len(id_tipo_cultivo) > 1:
            df_fenologia = df_fenologia[df_fenologia.id_tipo_cultivo.isin(id_tipo_cultivo)]
        elif len(id_tipo_cultivo) == 1:
            id_tipo_cultivo = id_tipo_cultivo[0]
        else:
            raise ValueError("Invalid crop type configuration")

        if not all(df_fenologia.nombre_etapa.unique() == "Unico"):
            df_etapa_patron = df_etapa_patron[
                df_etapa_patron["id_etapa"].isin(df_fenologia["id_etapa"])
            ].drop_duplicates()

        if not (df_fenologia.nombre_etapa == "Unico").any() and patron2.size > 1:
            cult, pat = id_tipo_cultivo[0], patron[0]
            df0 = pd.merge(
                df_etapa_patron[df_etapa_patron["id_patron"] == pat],
                df_fenologia[df_fenologia["id_tipo_cultivo"] == cult],
                on="id_etapa",
                how="inner",
            )
            for cult, pat in zip(id_tipo_cultivo[1:], patron[1:]):
                df0 = pd.concat(
                    [
                        df0,
                        pd.merge(
                            df_etapa_patron[df_etapa_patron["id_patron"] == pat],
                            df_fenologia[df_fenologia["id_tipo_cultivo"] == cult],
                            on="id_etapa",
                            how="inner",
                        ),
                    ]
                )
            df_etapa_patron = df0

        if (df_fenologia.nombre_etapa == "Unico").any():
            return float(
                df_fenologia[df_fenologia["id_tipo_cultivo"] == id_tipo_cultivo].kc.item()
            )

        df_etapa_patron["fechas"] = juliano2fechas(df_etapa_patron["juliano"], fecha=fecha)
        if (fecha < df_etapa_patron["fechas"].iloc[0]) or (fecha > df_etapa_patron["fechas"].iloc[-1]):
            logger.debug("For date %s in stubble stage for %s", fecha, nombre_cultivo)
            return STUBBLE_KC

        df_etapa_patron_sorted = df_etapa_patron.sort_values("fechas")
        fechas_numericas = df_etapa_patron_sorted["fechas"].apply(lambda x: x.toordinal())
        for col in ("kc", "id_tipo_cultivo", "nombre_etapa"):
            if col in df_etapa_patron_sorted.columns:
                df_etapa_patron_sorted = df_etapa_patron_sorted.drop(columns=[col])
        df_merged = df_fenologia.merge(df_etapa_patron_sorted, on="id_etapa")
        kc_values = df_merged["kc"].astype(float).values
        return float(np.interp(fecha.toordinal(), fechas_numericas, kc_values))


class GddKc(KcStrategy):
    """Growing-degree-day stages from sowing date + gdd_por_nodo_etapa."""

    def kc_for_date(
        self,
        gdd: float,
        patron: int | list | tuple,
        id_tipo_cultivo: int | list | tuple,
        id_nodo: int,
        df_fenologia: pd.DataFrame,
        reletapapatron: pd.DataFrame,
        gdd_umbral_etapas: pd.DataFrame,
        nombre_cultivos: dict[int, str] | None = None,
    ) -> float:
        if isinstance(id_tipo_cultivo, (list, tuple)):
            id_tipo_cultivo = id_tipo_cultivo[0]
        if isinstance(patron, (list, tuple)):
            patron = patron[0]
        nombre_cultivos = nombre_cultivos or {}

        if (df_fenologia.nombre_etapa == "Unico").any():
            return float(df_fenologia[df_fenologia["id_tipo_cultivo"] == id_tipo_cultivo].kc.item())

        patron_df = pd.DataFrame([patron], columns=["id_patron"])
        patron_df.id_patron = patron_df.id_patron.astype(int)
        df_etapa_patron = pd.merge(reletapapatron, patron_df, on="id_patron", how="inner")
        df_etapa_patron = df_etapa_patron[
            df_etapa_patron["id_etapa"].isin(df_fenologia["id_etapa"])
        ].drop_duplicates()

        gdd_nodo = gdd_umbral_etapas[
            (gdd_umbral_etapas["id_nodo"] == id_nodo) & (gdd_umbral_etapas["id_patron"] == patron)
        ]
        if gdd_nodo.empty:
            return STUBBLE_KC

        df_merged = df_fenologia.merge(df_etapa_patron[["id_etapa"]], on="id_etapa").merge(
            gdd_nodo[["id_etapa", "gdd_umbral"]],
            on="id_etapa",
        )
        df_merged = df_merged.sort_values("gdd_umbral")
        if df_merged.empty:
            raise ValueError(f"Sin GDD umbral para nodo {id_nodo} patron {patron}")
        gdd_thresholds = df_merged["gdd_umbral"].astype(float).values
        kc_values = df_merged["kc"].astype(float).values
        if gdd < gdd_thresholds[0] or gdd > gdd_thresholds[-1]:
            return STUBBLE_KC
        return float(np.interp(gdd, gdd_thresholds, kc_values))


def add_cumulative_gdd_by_node(
    data: pd.DataFrame,
    t_base: float,
    t_upp: float,
    temp_max_col: str = "t2m_max",
    temp_min_col: str = "t2m_min",
    node_col: str = "id_nodo",
    date_col: str = "fecha",
    out_col: str = "gdd",
) -> pd.DataFrame:
    if data.empty:
        raise ValueError("Data is empty for add_cumulative_gdd_by_node")
    result = data.sort_values([node_col, date_col]).copy()
    temp_max = pd.to_numeric(result[temp_max_col], errors="coerce")
    temp_min = pd.to_numeric(result[temp_min_col], errors="coerce")
    if (temp_min > 200).all():
        temp_min = temp_min - 273.15
        temp_max = temp_max - 273.15
    temp_max = temp_max.clip(lower=t_base, upper=t_upp)
    temp_min = temp_min.clip(upper=t_upp)
    t_mean = (temp_max + temp_min) / 2.0
    gdd_daily = t_mean.clip(lower=t_base) - t_base
    if (t_mean < t_base).any():
        gdd_daily = gdd_daily.where(t_mean >= t_base, 0)
    result[out_col] = gdd_daily.groupby(result[node_col]).cumsum()
    return result
