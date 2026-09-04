"""FAO Penman-Monteith. Ported from bhERA5 calculations.py — do not rewrite the math."""
import re

import numpy as np
import pandas as pd
from datetime import date, timedelta
import xarray as xr
from pint import UnitRegistry, Unit


unit = UnitRegistry(autoconvert_offset_to_baseunit=True)
Q_ = unit.Quantity


### Parametros
# calor latente de vaporización del agua a 20°C
CALOR_LATENTE_VAP = 2.45 * unit.megajoule/unit.kilogram # MJ kg^-1 
# calor especifico del aire a presión constante
CALOR_SPEC_PRES_CONST = 1.013e-3 * unit.megajoule/(unit.kilogram * unit.delta_degC) # MJ kg^-1 °C^-1
# NOTA: segun lo que pude ver es 1.003e-3
# cociente del peso molecular de vapor de agua /aire seco
EPS = 0.622 * unit.dimensionless 
# constante solar
CONSTANTE_SOLAR = 0.082 * unit.megajoule/(unit.metre**2 * unit.minute)# MJ m^-2 min^-1
# Constante de vapor de agua
CONSTANTE_VAPOR_DE_AGUA = 461.5 * unit.joule/(unit.kilogram * unit.kelvin) # J kg^-1 K^-1
# Constante aire seco
CONSTANTE_AIRE_SECO = 287.05 * unit.joule/(unit.kilogram * unit.kelvin) # J kg^-1 K^-1

def _xr2units(var: xr.DataArray, unidad: Unit) -> Q_:
    """
    Función para convertir las unidades de un xarray.DataArray a otra unidad (Unit.Registry.Quantity).
    Si no es un xarray.DataArray, simplemente asigna esa <unidad> a la variable <var>. 
    
    Params:
    -------
        var :  (xarray.DataArray or float)
            La variable a convertir
        unidad : UnitRegistry.unit
            La unidad deseada.

    Returns:
    -------
        var : unit.Quantity
            La variable en la unidad deseada.
    Example:
    -------
        # Transformo de hPa a kPa
        > import numpy as np
        > pres = xarray.DataArray(data=np.random.rand(10,10), attrs={'units':'hPa'})
        > pres_kpa = _xr2units(pres, unit.kPa)
    """
    if isinstance(var, xr.DataArray):
        if not hasattr(var, "units"):
            raise AttributeError(f"La variable {var} debe tener el atributo 'units' definido")
        u = var.units
        var = var.to_numpy()
        # Transformo unidades del estilo m s-1 en m s^-1
        if re.search(r"([a-zA-Z])([-]?)(\d)", u):
            u =  re.sub(r"([a-zA-Z])([-]?)(\d)", r"\1**\2\3", u)
        # Pongo este parche porque tengo las bolas llenas
        if (unit(u).units == unit.kelvin) and (unidad == unit.delta_degC):
            var = var - 273.15 
        var = Q_(var, u)
        if (unit(u).units == unit.degree_Celsius) and (unidad == unit.delta_degC):
            var = Q_(var, u).to('K') - Q_(273.15, 'K')
        var = var.to(unidad)
    # elif isinstance(var, Q_): # TODO Esto hay que arreglarlo. 
        # var = Q_(var, unidad)
    else:
        var = Q_(var, unidad)
    return var

### Calculos
def constante_psicrometrica(pres: xr.DataArray, calor_latente_vap: Q_, calor_spec_pres_const: Q_, eps: Q_) -> Q_:
    """
    Params:
    -------
        pres: xr.DataArray
            presion atmosférica (kPa)
        calor_latente_vap: Q_
            calor latente de vaporización, 2.45 MJ kg^-1
        calor_spec_pres_const: Q_
            calor específico a presión constante, 1.013e-3 MJ kg^-1 °C^-1
        eps: Q_
            cociente del peso molecular de vapor de agua /aire seco, 0,622
    Returns:
    -------
    constante_psicrometrica: Q_
        constante psicrométrica [ kPa °C^-1],
    """
    pres = _xr2units(pres, unit.kPa)
    return calor_spec_pres_const * pres / (eps*calor_latente_vap)


def presion_vapor(T: xr.DataArray) -> Q_:
    """
    La presión de vapor esta calculado con la ecuación de Tetens, que segun esto:
    https://www.wikiwand.com/en/Vapour_pressure_of_water es
    menos precisa que la ecuación de Buck para los rangos de temperatura típicos de interés. 
    
    Params:
    -------
        T: xarray.DataArray
            temperatura en °K
        Si T es temperatura real, es presion de saturacion. 
        Si T es temperatura de rocio, es presion de vapor real
    Returns:
    -------
        presion_vapor: Q_
            presión de vapor [kPa]
    """

    Tc = _xr2units(T, unit.delta_degC)
    e = Q_(0.61078, unit.kPa) * np.exp((Q_(17.27, 'dimensionless') * Tc)/(Tc + Q_(237.3, unit.delta_degC)))
    return e

def humedad_especifica_a_temp_rocio(SH: xr.DataArray, P: xr.DataArray) -> Q_:
    """
    Params:
    -------
        SH: xarray.DataArray
        humedad específica [kg kg^-1]
        P: xarray.DataArray
        presión atmosférica [kPa]
        Returns:
    -------
    T_rocio: Q_
    temperatura de rocio [°C]
    """
    R = CONSTANTE_AIRE_SECO/CONSTANTE_VAPOR_DE_AGUA
    sh = _xr2units(SH, SH.units)
    pres = _xr2units(P, P.units)
    p0 = Q_(0.61078, unit.kPa)
    T0 = Q_(237.3, unit.delta_degC)
    U = Q_(17.27, 'dimensionless')
    func = np.log(1/p0 * sh * pres.to(unit.kPa) / (sh * sh * R + R))
    T_rocio = T0 *func/ (U - func)
    return T_rocio


def pendiente_presion_saturacion(T: xr.DataArray) -> Q_:
    """
    Params:
    -------
        T: xarray.DataArray
            temperatura en °C
    Returns:
    -------
        delta: Q_ 
            pendiente de la curva de la presión de saturación de vapor a la temperatura del aire T, [kPa °C-1]
    """
    Tc = _xr2units(T, unit.delta_degC)
    A = Q_(4098, unit.delta_degC)
    e = presion_vapor(T)
    delta = A * e/(Tc + Q_(237.3, unit.delta_degC))**2
    return delta


def velocidad_viento_2metros(u: xr.DataArray, altura: float) -> Q_:
    """
    Params:
    -------
        u: xarray.DataArray
            viento a determinada altura
        altura:                     
            altura en m en la que disponés del dato de viento
    Returns:
    -------
        velocidad_viento_2metros: Q_    
    """
    uz = _xr2units(u,unit.meter/unit.second)
    z = _xr2units(altura,unit.meter)
    c1 = Q_(67.8, unit.meter**(-1))
    c2 = Q_(5.42, unit.dimensionless)
    c3 = Q_(4.87, unit.dimensionless)
    u2 = uz*c3/(np.log(c1*z-c2))
    return u2


### EVAPOTRANSPIRACION
def etp_calc(
    radiacion_neta: Q_,
    flujo_calor_suelo: Q_,
    temperatura_media: Q_,
    velocidad_viento2m: Q_,
    presion_vapor_saturacion: Q_, 
    presion_vapor_real: Q_,
    pendiente_presion_saturacion: Q_,
    constante_psicrometrica: Q_,
    ) -> Q_:
    """
    Ecuación 6 del documento de la FAO.
    
    radiacion_neta [MJ m^-2 dia^-1]:            diferencia entre la radiación neta de onda corta y la radiación neta de onda larga
    flujo_calor_suelo [MJ m^-2 dia^-1]:         flujo del calor del suelo (G)  
    temperatura_media [°C]:                     temperatura media del aire
    velocidad_viento2m [m s^-1]:                velocidad del viento a 2 m de altura
    presion_vapor_saturacion [kPa]:             presion de vapor de saturación
    presion_vapor_real [kPa]:                   presion de vapor real
    pendiente_presion_saturacion [kPa °C^-1]:   pendiente de la curva de presion de vapor
    constante_psicrometrica [kPa °C^-1]:        constante psicrometrica

    etp_calc:                                   evapotranspiración de referencia [mm dia^-1]
    """
    # A es la inversa del calor latente de vaporización
    A = Q_(0.408, unit.kilogram/unit.megajoule)   
    termino1 =  A * pendiente_presion_saturacion * (radiacion_neta - flujo_calor_suelo) 
    B = Q_(900,unit.kilogram*unit.delta_degC*unit.seconds/(unit.kilopascal*unit.meter**3))
    termino2 = constante_psicrometrica * B * velocidad_viento2m * (presion_vapor_saturacion-presion_vapor_real)/(_xr2units(temperatura_media,unit.delta_degC) +Q_(273, unit.delta_degC))
    C = Q_(0.34, unit.seconds/unit.meter)
    termino3 = pendiente_presion_saturacion + constante_psicrometrica * (1 + C*velocidad_viento2m)
    etp = (termino1 + termino2)/termino3
    return etp


