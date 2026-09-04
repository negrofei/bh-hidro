"""Hourly → daily + Penman-Monteith. Sequential; D+1 GRIB must already be on disk."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from bh_hidro.physics.penman import (
    CALOR_LATENTE_VAP,
    CALOR_SPEC_PRES_CONST,
    EPS,
    constante_psicrometrica,
    etp_calc,
    pendiente_presion_saturacion,
    presion_vapor,
    velocidad_viento_2metros,
    _xr2units,
)

logger = logging.getLogger(__name__)


def hourly_to_daily(data: xr.Dataset, variables: set[str], mode: str) -> xr.Dataset:
    resampled = data.resample(time="24h", origin="start")
    grouped = {"mean": resampled.mean, "sum": resampled.sum, "min": resampled.min, "max": resampled.max}[mode]()
    daily = grouped.get(variables.intersection(data.variables))
    for var in variables:
        if var in daily.variables:
            daily[var].attrs = data[var].attrs
            daily[var].attrs.update({"mode": f"Daily {mode}"})
    if mode in {"min", "max"}:
        daily = daily.rename({var: f"{var}_{mode}" for var in variables if var in daily.variables})
    return daily


def _sel(data: xr.Dataset, when: datetime) -> xr.Dataset:
    return data.sel(time=when)


def eraland_tp_pev(data: xr.Dataset, fecha: date) -> xr.Dataset:
    """Accumulated ERALand precip/pev on the pluviometric day 12–12."""
    nxt = fecha + timedelta(days=1)
    part1 = _sel(data, datetime(nxt.year, nxt.month, nxt.day, 0)) - _sel(
        data, datetime(fecha.year, fecha.month, fecha.day, 12)
    )
    part2 = _sel(data, datetime(nxt.year, nxt.month, nxt.day, 12))
    pluvio = part1 + part2
    pluvio["tp"] = xr.DataArray(pluvio["tp"] * 1000, attrs={"units": "mm"})
    pluvio["tp"] = xr.where(pluvio["tp"].notnull() & (pluvio["tp"] < 0), 0, pluvio["tp"])
    pluvio["pev"] = xr.DataArray(pluvio["pev"] * -1000, attrs=pluvio.attrs)
    pluvio["time"] = pluvio["time"] - pd.Timedelta(days=1)
    times = pluvio["time"].values
    pluvio["tp"] = pluvio["tp"].expand_dims({"time": [times]}).transpose("time", "latitude", "longitude")
    pluvio["pev"] = pluvio["pev"].expand_dims({"time": [times]}).transpose("time", "latitude", "longitude")
    return pluvio[["tp", "pev"]]


def eraland_radiation(data: xr.Dataset, fecha: date) -> xr.Dataset:
    nxt = fecha + timedelta(days=1)
    part1 = _sel(data, datetime(nxt.year, nxt.month, nxt.day, 0)) - _sel(
        data, datetime(fecha.year, fecha.month, fecha.day, 12)
    )
    part2 = _sel(data, datetime(nxt.year, nxt.month, nxt.day, 12))
    pluvio = part1 + part2
    pluvio["Rn"] = xr.DataArray(pluvio["ssr"] + pluvio["str"], coords=pluvio["ssr"].coords, attrs={"units": data["ssr"].units})
    pluvio["G"] = xr.DataArray(
        np.where(pluvio["Rn"].to_numpy() > 0, 0.1 * pluvio["Rn"].to_numpy(), 0.5 * pluvio["Rn"].to_numpy()),
        coords=pluvio["Rn"].coords,
        attrs={"units": data["ssr"].units},
    )
    return pluvio[["Rn", "G"]]


def slice_pluviometric(data: xr.Dataset, fecha: date) -> xr.Dataset:
    start = datetime(fecha.year, fecha.month, fecha.day, 12)
    return data.sel(time=slice(start, start + timedelta(hours=24)))


def penman_etp(data: xr.Dataset) -> xr.DataArray:
    from pint import UnitRegistry

    unit = UnitRegistry(autoconvert_offset_to_baseunit=True)
    rn = _xr2units(data["Rn"], unit.megajoules / unit.meter**2)
    g = _xr2units(data["G"], unit.megajoules / unit.meter**2)
    tmax, tmin = data["t2m_max"], data["t2m_min"]
    t_mean = 0.5 * tmax + 0.5 * tmin
    t_mean.attrs = {"units": "K"}
    pres = _xr2units(data["sp"], unit.kPa)
    u10 = _xr2units(data["u10"], unit.meter / unit.seconds)
    v10 = _xr2units(data["v10"], unit.meter / unit.seconds)
    u2m = velocidad_viento_2metros(np.sqrt(u10**2 + v10**2), 10)
    e = 0.5 * presion_vapor(data["d2m_max"]) + 0.5 * presion_vapor(data["d2m_min"])
    es = 0.5 * presion_vapor(tmax) + 0.5 * presion_vapor(tmin)
    values = etp_calc(
        radiacion_neta=rn,
        flujo_calor_suelo=g,
        temperatura_media=t_mean,
        velocidad_viento2m=u2m,
        presion_vapor_saturacion=es,
        presion_vapor_real=e,
        pendiente_presion_saturacion=pendiente_presion_saturacion(t_mean),
        constante_psicrometrica=constante_psicrometrica(pres, CALOR_LATENTE_VAP, CALOR_SPEC_PRES_CONST, EPS),
    )
    return xr.DataArray(np.array(values), coords=data.coords, attrs={"units": "mm dia^-1", "name": "etp"})


def eraland_daily_from_hourly(hourly_files: list[Path], fecha: date) -> xr.Dataset:
    data = xr.open_mfdataset([str(p) for p in hourly_files])
    try:
        if "expver" in data.dims:
            logger.warning("ERALand expver present, reducing with nansum")
            data = data.reduce(np.nansum, dim="expver", keep_attrs=True)
        tp_pev = eraland_tp_pev(data, fecha)
        rad = eraland_radiation(data, fecha)
        rest = slice_pluviometric(data.drop_vars(["tp", "pev"]), fecha)
        stats = xr.merge(
            [
                hourly_to_daily(rest, {"u10", "v10", "sp", "t2m", "d2m"}, "mean"),
                hourly_to_daily(rest, {"ssr", "str", "Rn", "G"}, "sum"),
                hourly_to_daily(rest, {"t2m", "d2m"}, "min"),
                hourly_to_daily(rest, {"t2m", "d2m"}, "max"),
            ]
        )
        if "time" in stats.dims and "time" in tp_pev.dims:
            pluvio_time = tp_pev.time
            stats = stats.isel(time=0)
            for name in list(stats.variables):
                if "time" not in stats[name].dims:
                    stats[name] = stats[name].expand_dims(time=pluvio_time)
                else:
                    stats[name] = stats[name].assign_coords(time=pluvio_time)
        combined = xr.merge([tp_pev, rad, stats])
        combined["etp"] = penman_etp(combined)
        if "number" in combined.variables:
            combined = combined.drop_vars("number")
        return combined
    finally:
        data.close()


def wrf_add_radiation(data: xr.Dataset) -> xr.Dataset:
    albedo = 0.23
    sw = data["ACSWDNB"].diff(dim="time")
    lw_down = data["ACLWDNB"].diff(dim="time")
    lw_up = data["ACLWUPB"].diff(dim="time")
    rn = sw + lw_down - lw_up - albedo * sw
    data["Rn"] = xr.concat([xr.zeros_like(rn.isel(time=0)), rn], dim="time").assign_coords(
        time=data["ACSWDNB"].time
    ).assign_attrs(units=data["ACSWDNB"].units)
    data["G"] = xr.where(data["Rn"] > 0, 0.1 * data["Rn"], 0.5 * data["Rn"]).assign_attrs(units=data["Rn"].units)
    return data


def wrf_add_vapor(data: xr.Dataset) -> xr.Dataset:
    data["pres_vap_real"] = (data["HR2"] * presion_vapor(data["T2"])) / 100
    data["pres_vap_real"] = data["pres_vap_real"].assign_attrs(units="kPa")
    return data


def wrf_etp(data: xr.Dataset) -> xr.DataArray:
    from pint import UnitRegistry

    unit = UnitRegistry(autoconvert_offset_to_baseunit=True)
    rn = _xr2units(data["Rn"], unit.megajoules / unit.meter**2)
    g = _xr2units(data["G"], unit.megajoules / unit.meter**2)
    tmax, tmin = data["Tmax"], data["Tmin"]
    t_mean = 0.5 * tmax + 0.5 * tmin
    t_mean.attrs = {"units": "degree_Celsius"}
    pres = _xr2units(data["PSFC"], unit.kPa)
    u2m = velocidad_viento_2metros(_xr2units(data["magViento10"], unit.meter / unit.seconds), 10)
    e = _xr2units(data["pres_vap_real"], unit.kilopascal)
    es = 0.5 * presion_vapor(tmax) + 0.5 * presion_vapor(tmin)
    values = etp_calc(
        radiacion_neta=rn,
        flujo_calor_suelo=g,
        temperatura_media=t_mean,
        velocidad_viento2m=u2m,
        presion_vapor_saturacion=es,
        presion_vapor_real=e,
        pendiente_presion_saturacion=pendiente_presion_saturacion(t_mean),
        constante_psicrometrica=constante_psicrometrica(pres, CALOR_LATENTE_VAP, CALOR_SPEC_PRES_CONST, EPS),
    )
    return xr.DataArray(np.array(values), coords=data.coords, attrs={"units": "mm dia^-1"})
