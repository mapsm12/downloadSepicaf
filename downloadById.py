#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
downloadById.py — Descarga datos de un flotador ARGO usando argopy y guarda en NetCDF.

USO BÁSICO
----------
1) Pasando el código WMO del flotador:
   python downloadById.py 3902585

2) Pasando un archivo .py que contenga el código:
   # contenido de mi_flotador.py:
   # FLOAT_ID = 3902585
   #
   # o:
   # ARGO_CODE = 3902585
   #
   # o:
   # ARGO_CODES = [3902585, 6903002]
   # (en este caso se toma el primero de la lista)

   python downloadById.py mi_flotador.py

OPCIONES
--------
--days N        Número de días hacia atrás desde hoy (UTC) para el rango temporal.
                Si NO se proporciona, se usa TODO el periodo disponible (sin filtro temporal).
--src SRC       Fuente de datos de argopy: erddap o gdac (por defecto: erddap)
--mode MODE     Modo de argopy: expert o standard (por defecto: expert)
-o, --output    Nombre de archivo de salida (.nc). Si no se da, se genera uno automáticamente.

EJEMPLOS
--------
# TODO el periodo disponible del flotador 3902585 (erddap, modo expert):
python downloadById.py 3902585

# Últimos 90 días:
python downloadById.py 3902585 --days 90

# Usando archivo .py con FLOAT_ID:
python downloadById.py mi_flotador.py --days 60

SALIDA
------
Genera un archivo NetCDF con nombre tipo:
  argo_<codigo>_<YYYYMMDD-YYYYMMDD>.nc
donde el rango de fechas se infiere de los datos (mínimo y máximo de TIME/JULD/time).
Si no se puede inferir rango temporal, usa:
  argo_<codigo>_full.nc

NOTA IMPORTANTE
---------------
Este script descarga todos los datos disponibles para el flotador y,
si se indica --days, aplica el filtro temporal en Python (xarray),
ya que en tu versión de argopy no está disponible el método .time()
encadenado a .float().

Instituto Geofísico del Perú (IGP)
IGP: Ciencia para protegernos, ciencia para avanzar
"""

import argparse
import logging
import os
import warnings
from datetime import datetime, timedelta
from typing import Optional, Tuple

import numpy as np
import xarray as xr
import argopy
from argopy import DataFetcher as ArgoDataFetcher

# =====================================================
# LOGGING
# =====================================================
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger("downloadById")


# =====================================================
# 1. FUNCIONES AUXILIARES
# =====================================================

def leer_codigo_desde_arg(arg: str) -> int:
    """
    Interpreta el argumento principal:
    - Si es un número: lo devuelve como int.
    - Si termina en .py y existe: importa FLOAT_ID, ARGO_CODE o ARGO_CODES[0].
    """
    # Caso 1: es un entero (ej. "3902585")
    try:
        code = int(arg)
        logger.info(f"Código leído desde línea de comandos: {code}")
        return code
    except ValueError:
        pass  # no es número simple, probamos como .py

    # Caso 2: archivo .py
    if arg.endswith(".py") and os.path.exists(arg):
        import importlib.util

        logger.info(f"Leyendo código desde archivo de configuración Python: {arg}")
        spec = importlib.util.spec_from_file_location("float_cfg_mod", arg)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore

        if hasattr(mod, "FLOAT_ID"):
            code = int(getattr(mod, "FLOAT_ID"))
            logger.info(f"Usando FLOAT_ID definido en {arg}: {code}")
            return code
        if hasattr(mod, "ARGO_CODE"):
            code = int(getattr(mod, "ARGO_CODE"))
            logger.info(f"Usando ARGO_CODE definido en {arg}: {code}")
            return code
        if hasattr(mod, "ARGO_CODES"):
            lista = getattr(mod, "ARGO_CODES")
            if isinstance(lista, (list, tuple)) and len(lista) > 0:
                code = int(lista[0])
                logger.info(f"Usando primer elemento de ARGO_CODES en {arg}: {code}")
                return code

        logger.error(f"El archivo {arg} no define FLOAT_ID, ARGO_CODE ni ARGO_CODES usable.")
        raise SystemExit(1)

    logger.error(
        f"Argumento inválido: {arg}. Debe ser un entero (código WMO) o un .py existente."
    )
    raise SystemExit(1)


def _get_time_var(ds: xr.Dataset) -> Optional[str]:
    """Devuelve el nombre de la variable de tiempo (TIME, JULD o time), si existe."""
    for cand in ("TIME", "JULD", "time"):
        if cand in ds.variables:
            return cand
    return None


def _ensure_time_datetime(ds: xr.Dataset, time_var: str) -> Tuple[xr.Dataset, xr.DataArray]:
    """
    Asegura que ds[time_var] sea datetime64.
    Si no lo es, intenta convertir con decode_cf (si falla, deja como está).
    """
    t = ds[time_var]
    if np.issubdtype(t.dtype, np.datetime64):
        return ds, t

    logger.info(f"Intentando convertir variable de tiempo '{time_var}' a datetime64 usando decode_cf...")
    try:
        t_dec = xr.decode_cf(ds[[time_var]])[time_var]
        ds = ds.assign_coords({time_var: t_dec})
        t = ds[time_var]
        logger.info(f"Conversión exitosa: dtype={t.dtype}")
        return ds, t
    except Exception as exc:
        logger.warning(
            f"No se pudo convertir la variable de tiempo '{time_var}' a datetime. "
            f"Se deja sin cambios. Detalle: {exc}"
        )
        return ds, t


def filtrar_por_tiempo(ds: xr.Dataset, t0: datetime, t1: datetime) -> xr.Dataset:
    """
    Filtra el Dataset en el rango [t0, t1] usando la variable de tiempo disponible.
    Intenta TIME, luego JULD, luego time.
    El filtrado se hace con .where(mask, drop=True) para evitar problemas de índice.
    """
    logger.info("Aplicando filtro temporal en xarray...")

    time_var = _get_time_var(ds)
    if time_var is None:
        logger.warning("No se encontró variable de tiempo (TIME/JULD/time). No se aplica filtro temporal.")
        return ds

    logger.info(f"Variable de tiempo detectada: {time_var}")
    ds, t = _ensure_time_datetime(ds, time_var)

    if not np.issubdtype(t.dtype, np.datetime64):
        logger.warning(
            f"La variable de tiempo '{time_var}' no es datetime64 después de intentar decode_cf. "
            "Se omite el filtro temporal."
        )
        return ds

    # Construimos máscara booleana
    t0_np = np.datetime64(t0)
    t1_np = np.datetime64(t1)
    mask = (t >= t0_np) & (t <= t1_np)

    if not mask.any():
        logger.warning("No hay datos dentro del rango temporal solicitado. Dataset se vacía.")
        # Suponemos que el tiempo tiene una única dimensión
        time_dim = t.dims[0] if len(t.dims) > 0 else None
        if time_dim is not None and time_dim in ds.dims:
            return ds.isel({time_dim: slice(0, 0)})
        else:
            # Fallback: devolvemos dataset original (sin filtrar)
            return ds

    # Filtro con where, evitando el problema de índice
    ds_filtrado = ds.where(mask, drop=True)

    # Intentar estimar número de perfiles/puntos
    n_perfiles = ds_filtrado.dims.get("N_PROF", None)
    if n_perfiles is None:
        # si no existe N_PROF, usamos la dimensión de 't'
        if len(t.dims) > 0:
            td = t.dims[0]
            n_perfiles = ds_filtrado.dims.get(td, "desconocido")
        else:
            n_perfiles = "desconocido"

    logger.info(f"Perfiles/puntos en rango temporal: {n_perfiles}")
    logger.info(f"Dimensiones después del filtro temporal: {dict(ds_filtrado.sizes)}")

    return ds_filtrado


def inferir_rango_temporal_desde_ds(ds: xr.Dataset) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Infere las fechas mínima y máxima del dataset a partir de la variable TIME/JULD/time.
    Devuelve (tmin, tmax) como datetime UTC, o (None, None) si no se puede.
    """
    time_var = _get_time_var(ds)
    if time_var is None:
        logger.warning("No se encontró variable de tiempo para inferir rango temporal del dataset.")
        return None, None

    ds, t = _ensure_time_datetime(ds, time_var)

    if not np.issubdtype(t.dtype, np.datetime64):
        logger.warning(
            f"No se puede inferir rango temporal porque '{time_var}' no es datetime64 "
            "ni se pudo convertir con decode_cf."
        )
        return None, None

    if t.size == 0:
        logger.warning("La variable de tiempo está vacía; no se puede inferir rango temporal.")
        return None, None

    # t.min() y t.max() devuelven np.datetime64
    tmin64 = np.datetime64(t.min().values)
    tmax64 = np.datetime64(t.max().values)

    def to_py_datetime(dt64: np.datetime64) -> datetime:
        # convertir a segundos desde epoch y luego a datetime UTC
        return datetime.utcfromtimestamp(
            (dt64 - np.datetime64("1970-01-01T00:00:00")) / np.timedelta64(1, "s")
        )

    t0 = to_py_datetime(tmin64)
    t1 = to_py_datetime(tmax64)

    logger.info(f"Rango temporal en datos: {t0:%Y-%m-%d} → {t1:%Y-%m-%d}")
    return t0, t1


def construir_nombre_salida(
    float_id: int, t0: datetime, t1: datetime, salida_usuario: Optional[str]
) -> str:
    """
    Construye el nombre del archivo de salida:
    - Si el usuario dio -o/--output, se usa tal cual.
    - Si no, genera: argo_<id>_<YYYYMMDD-YYYYMMDD>.nc
    """
    if salida_usuario:
        logger.info(f"Nombre de salida proporcionado por el usuario: {salida_usuario}")
        return salida_usuario

    rango = f"{t0:%Y%m%d}-{t1:%Y%m%d}"
    nombre = f"argo_{float_id}_{rango}.nc"
    logger.info(f"Nombre de salida generado automáticamente: {nombre}")
    return nombre


def añadir_attrs_igp(ds: xr.Dataset, float_id: int) -> xr.Dataset:
    """
    Añade atributos globales de institución y lema del IGP.
    """
    attrs = dict(ds.attrs) if isinstance(ds.attrs, dict) else {}
    attrs.update({
        "institution": "Instituto Geofísico del Perú (IGP)",
        "acknowledgement": "IGP: Ciencia para protegernos, ciencia para avanzar",
        "argo_float_id": str(float_id),
        "history": (
            attrs.get("history", "") +
            f"\nCreated by downloadById.py on {datetime.utcnow().isoformat()}Z"
        ).strip()
    })
    return ds.assign_attrs(attrs)


# =====================================================
# 2. FUNCIÓN PRINCIPAL
# =====================================================

def main() -> None:
    # ----------------- Parser de argumentos -----------------
    parser = argparse.ArgumentParser(
        description="Descarga datos ARGO de un flotador y guarda en NetCDF."
    )
    parser.add_argument(
        "codigo",
        help=(
            "Código WMO del flotador (p.ej. 3902585) "
            "o archivo .py con FLOAT_ID / ARGO_CODE / ARGO_CODES."
        ),
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help=(
            "Número de días hacia atrás desde hoy (UTC) para el rango temporal. "
            "Si NO se proporciona, se usa TODO el periodo disponible (sin filtro temporal)."
        ),
    )
    parser.add_argument(
        "--src",
        choices=("erddap", "gdac"),
        default="erddap",
        help="Fuente de datos para argopy.",
    )
    parser.add_argument(
        "--mode",
        choices=("expert", "standard"),
        default="expert",
        help="Modo de argopy.",
    )
    parser.add_argument(
        "-o", "--output",
        help="Nombre de archivo NetCDF de salida. Si se omite, se genera uno automáticamente."
    )

    args = parser.parse_args()

    logger.info("=== INICIANDO DESCARGA ARGO ===")
    logger.info("IGP: Ciencia para protegernos, ciencia para avanzar")

    # ----------------- 2.1. Código de flotador -----------------
    float_id = leer_codigo_desde_arg(args.codigo)
    logger.info(f"Flotador seleccionado: {float_id}")

    # ----------------- 2.2. Rango de fechas (si se indica --days) -----------------
    if args.days is not None:
        fecha_final = datetime.utcnow()
        fecha_inicial = fecha_final - timedelta(days=args.days)
        date_range_str = f"{fecha_inicial:%Y-%m-%d} → {fecha_final:%Y-%m-%d}"
        logger.info(f"Rango de fechas solicitado (UTC): {date_range_str}")

        date_range_mm = [fecha_inicial.strftime("%Y-%m"), fecha_final.strftime("%Y-%m")]
        logger.info(f"Rango mensual aproximado (solicitado): {date_range_mm}")
    else:
        fecha_inicial = None
        fecha_final = None
        logger.info(
            "No se proporcionó --days: se descargará TODO el periodo disponible del flotador (sin filtro temporal)."
        )

    # ----------------- 2.3. Configuración argopy -----------------
    logger.info(f"Configurando argopy: src='{args.src}', mode='{args.mode}'")
    argopy.set_options(mode=args.mode, src=args.src)
    fetcher = ArgoDataFetcher(mode=args.mode, src=args.src)

    # ----------------- 2.4. Descarga -----------------
    logger.info(
        f"Descargando datos desde '{args.src}' en modo '{args.mode}' "
        f"(sin filtro temporal en servidor)..."
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            ds = fetcher.float(float_id).load().data
        except Exception as exc:
            logger.error(f"Error al descargar datos del flotador {float_id}: {exc}")
            raise SystemExit(1)

    if not isinstance(ds, xr.Dataset) or len(ds.variables) == 0:
        logger.error("No se obtuvieron datos para ese flotador.")
        raise SystemExit(1)

    logger.info(f"Dimensiones originales del dataset: {dict(ds.sizes)}")
    logger.info(f"Número de variables originales: {len(ds.data_vars)}")

    # ----------------- 2.5. Filtro temporal en xarray (opcional) -----------------
    if fecha_inicial is not None and fecha_final is not None:
        ds = filtrar_por_tiempo(ds, fecha_inicial, fecha_final)
    else:
        logger.info("Sin filtro temporal: se mantiene el rango completo de datos.")

    # ----------------- 2.6. Inferir rango temporal real para el nombre -----------------
    t0_name, t1_name = inferir_rango_temporal_desde_ds(ds)

    if t0_name is not None and t1_name is not None:
        salida_nc = construir_nombre_salida(float_id, t0_name, t1_name, args.output)
    else:
        if args.output:
            salida_nc = args.output
            logger.info(f"No se pudo inferir rango temporal; usando nombre proporcionado: {salida_nc}")
        else:
            salida_nc = f"argo_{float_id}_full.nc"
            logger.info(f"No se pudo inferir rango temporal; usando nombre por defecto: {salida_nc}")

    # ----------------- 2.7. Atributos IGP y guardado NetCDF -----------------
    ds = añadir_attrs_igp(ds, float_id)

    logger.info(f"Guardando dataset en NetCDF: {salida_nc}")
    try:
        ds.to_netcdf(salida_nc)
    except Exception as exc:
        logger.error(f"No se pudo escribir el archivo NetCDF '{salida_nc}': {exc}")
        raise SystemExit(1)

    logger.info(f"[OK] Datos guardados en: {salida_nc}")
    logger.info("=== DESCARGA COMPLETADA ===")
    logger.info("IGP: Ciencia para protegernos, ciencia para avanzar")


# =====================================================
# 3. PUNTO DE ENTRADA
# =====================================================

if __name__ == "__main__":
    main()
