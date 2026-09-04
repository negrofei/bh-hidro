"""FAO daily soil-water bucket. Copied from bhERA5 balance_hidrico_pandarized — do not rewrite the math."""

from __future__ import annotations

import numpy as np
import pandas as pd

BALANCE_INDEX = [
    "id_formita",
    "id_provincia",
    "id_departamento",
    "id_suelo",
    "id_nodo",
    "id_cultivo_general",
]
WATER_UTILIZATION_FACTOR = 0.5
NON_AGRICULTURAL_SOIL = 1096
STUBBLE_KC = 0.4


def balance_hidrico_pandarized(super_dataframe: pd.DataFrame) -> tuple[pd.Series, ...]:
    pto_marchitez_permanente = super_dataframe.pmp
    capa_campo = super_dataframe.capacidad_campo
    coef_escurrimiento = super_dataframe.coef_escurrimiento
    coef_percolacion = super_dataframe.coef_percolacion
    kc = super_dataframe.kc
    etp = super_dataframe.etp

    try:
        precip_diaria = super_dataframe.tp
    except Exception:
        precip_diaria = super_dataframe.PP

    almacenaje_dia_prev = super_dataframe.almacenaje
    exceso_dia_prev = super_dataframe.exceso

    limite_desecamiento = ((pto_marchitez_permanente / capa_campo) - 0.4) * 2.5
    limite_desecamiento[limite_desecamiento < 0] = 0
    limite_desecamiento[limite_desecamiento > 1] = 1

    alm_minimo = limite_desecamiento * pto_marchitez_permanente
    etr = almacenaje_dia_prev / capa_campo * etp * kc

    esc = np.where(
        (exceso_dia_prev != 0) | (precip_diaria != 0),
        coef_escurrimiento
        * (precip_diaria + exceso_dia_prev)
        * np.exp(-(capa_campo - almacenaje_dia_prev) / (precip_diaria + exceso_dia_prev)),
        0,
    )
    esc = pd.Series(esc, index=etr.index)

    alm_umbral = pto_marchitez_permanente + 0.5 * (capa_campo - pto_marchitez_permanente)
    per = np.where(
        almacenaje_dia_prev > alm_umbral,
        coef_percolacion * (almacenaje_dia_prev - alm_umbral),
        0,
    )
    per = pd.Series(per, index=etr.index)

    almacenaje = exceso_dia_prev + almacenaje_dia_prev + precip_diaria - esc - per - etr
    exceso = np.where(almacenaje > capa_campo, almacenaje - capa_campo, 0)
    exceso = pd.Series(exceso, index=etr.index)
    almacenaje = np.where(almacenaje > capa_campo, capa_campo, almacenaje)
    almacenaje = np.where(almacenaje < alm_minimo, alm_minimo, almacenaje)
    almacenaje = pd.Series(almacenaje, index=etr.index)
    agua_util = (almacenaje - pto_marchitez_permanente) / (capa_campo - pto_marchitez_permanente)
    return almacenaje, exceso, precip_diaria, esc, per, etr, agua_util


def initial_almacenaje(pmp: pd.Series, capacidad_campo: pd.Series) -> pd.Series:
    return pmp + WATER_UTILIZATION_FACTOR * (capacidad_campo - pmp)
