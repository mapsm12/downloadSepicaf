# 📦 `downloadById.py`

Script en Python para **descargar datos ARGO de un flotador específico** usando [`argopy`](https://github.com/euroargodev/argopy) y guardarlos en un archivo NetCDF listo para análisis científico (xarray, Python, MATLAB, etc.).

Incluye:

- Interfaz de **línea de comandos** (`CLI`).
- Soporte para leer el ID del flotador desde:
  - un **código WMO** (`6903002`, `3902585`, etc.), o
  - un **archivo `.py`** con variables tipo `FLOAT_ID`, `ARGO_CODE`, `ARGO_CODES`.
- Opción para:
  - Descargar **todo el historial disponible**, o
  - Filtrar sólo los **últimos N días** (`--days`).
- Nombre de salida automático según el **ID del flotador** y el **rango temporal real de los datos**.
- Atributos globales en el NetCDF con la afiliación institucional:

> **Instituto Geofísico del Perú (IGP)**  
> **IGP: Ciencia para protegernos, ciencia para avanzar**

---

## 🧩 Requisitos

### Versión de Python

- Python **3.8+** (recomendado 3.10+)

### Paquetes necesarios

Instala las dependencias mínimas con `pip`:

```bash
pip install argopy xarray numpy
````

Opcional (recomendado para mejor manejo de NetCDF):

```bash
pip install netcdf4
```

Si trabajas en un entorno con `conda` / `mamba` (por ejemplo en un clúster HPC):

```bash
mamba create -n argo_env python=3.10 argopy xarray numpy netcdf4 -c conda-forge
mamba activate argo_env
```

---

## 📁 Estructura del repositorio

Un ejemplo mínimo de repo en GitHub podría ser:

```text
.
├── downloadById.py   # Script principal
├── README.md         # Este archivo
└── examples/
    └── mi_flotador.py  # Ejemplo de archivo de configuración de flotador
```

---

## ⚙️ Instalación local

Clona el repo (o copia el script al servidor):

```bash
git clone https://github.com/tu_usuario/tu_repo_argo.git
cd tu_repo_argo
```

(O simplemente copia `downloadById.py` a la carpeta donde quieras trabajar).

Asegúrate de estar en el entorno con las dependencias instaladas (`argopy`, `xarray`, etc.), y ya puedes usar el script.

---

## 🚀 Uso básico

El script se ejecuta así:

```bash
python downloadById.py CODIGO_O_ARCHIVO [opciones]
```

donde `CODIGO_O_ARCHIVO` puede ser:

* Un **código WMO** del flotador (ejemplo `6903002`), o
* Un **archivo `.py`** que defina alguna de estas variables:

  * `FLOAT_ID`
  * `ARGO_CODE`
  * `ARGO_CODES` (se toma el **primer elemento** de la lista)

---

## 🔧 Opciones de línea de comandos

### Posicional

* `codigo`

  * Código WMO del flotador (ejemplo: `3902585`),
    **o**
  * Ruta a un archivo `.py` (ejemplo: `mi_flotador.py`).

### Opciones

| Opción                     | Tipo | Por defecto | Descripción                                                                                                                                                 |
| -------------------------- | ---- | ----------: | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--days N`                 | int  |      `None` | Número de días hacia atrás desde hoy (UTC) para filtrar datos. Si **no** se especifica, se descarga **todo** el historial disponible (sin filtro temporal). |
| `--src {erddap,gdac}`      | str  |    `erddap` | Fuente de datos para `argopy`.                                                                                                                              |
| `--mode {expert,standard}` | str  |    `expert` | Modo de `argopy`.                                                                                                                                           |
| `-o`, `--output RUTA`      | str  |      `None` | Nombre del archivo NetCDF de salida. Si se omite, se genera automáticamente a partir del rango temporal de los datos.                                       |

---

## ✅ Ejemplos de uso

### 1. Descargar TODO el historial disponible de un flotador

```bash
python downloadById.py 6903002
```

Flujo:

* No se especifica `--days` → **sin filtro temporal**, se descargan todos los datos disponibles.
* El script intenta leer la variable de tiempo (`TIME`, `JULD` o `time`), convertirla a `datetime64`, e inferir el rango mínimo y máximo.
* Nombre de salida típico:

```text
argo_6903002_20041215-20251204.nc
```

Si la variable de tiempo no se puede interpretar como fechas, se usa:

```text
argo_6903002_full.nc
```

---

### 2. Descargar sólo los últimos 90 días

```bash
python downloadById.py 6903002 --days 90
```

Flujo:

* Se calcula el rango `[hoy - 90 días, hoy]`.
* Se filtran los datos en `xarray` si se puede convertir la variable de tiempo a `datetime64`.
* Se infiere el rango real en los datos tras el filtro.
* Nombre de salida típico:

```text
argo_6903002_20250906-20251204.nc
```

---

### 3. Leer el flotador desde un archivo `.py`

Supongamos un archivo `mi_flotador.py`:

```python
# mi_flotador.py
FLOAT_ID = 3902585
# o:
# ARGO_CODE = 3902585
# o:
# ARGO_CODES = [3902585, 6903002]
```

Se ejecuta:

```bash
python downloadById.py mi_flotador.py
```

El script:

1. Importa el módulo.
2. Busca `FLOAT_ID`, `ARGO_CODE` o `ARGO_CODES`.
3. Usa el primer código encontrado.

---

### 4. Especificar el nombre del archivo de salida

```bash
python downloadById.py 3902585 --days 30 -o argo_callao_30d.nc
```

* Se descarga el flotador 3902585.
* Se filtra a los últimos 30 días (si el tiempo es interpretable).
* Se guarda exactamente como:

```text
argo_callao_30d.nc
```

aunque internamente se haya inferido el rango temporal real.

---

## 📂 Formato de salida (NetCDF)

El script guarda un archivo NetCDF con:

* Dimensiones típicas (dependen de la fuente `argopy`):

  * `N_PROF`, `N_LEVELS`, `N_POINTS`, etc.
* Variables estándar de ARGO (por ejemplo):

  * `PRES`, `TEMP`, `PSAL`, `LONGITUDE`, `LATITUDE`, etc.
* Atributos globales adicionales:

```text
institution   = "Instituto Geofísico del Perú (IGP)"
acknowledgement = "IGP: Ciencia para protegernos, ciencia para avanzar"
argo_float_id = "<código del flotador>"
history       = "... Created by downloadById.py on 2025-12-04T15:00:00Z"
```

Puedes abrir el archivo en Python con:

```python
import xarray as xr

ds = xr.open_dataset("argo_6903002_20041215-20251204.nc")
print(ds)
```

---

## 🧠 Lógica interna (resumen técnico)

1. **Lectura del ID del flotador**

   * Si el argumento es un entero → se interpreta como código WMO.
   * Si termina en `.py` y existe:

     * Se importa el archivo como módulo.
     * Se busca, en este orden:

       * `FLOAT_ID`
       * `ARGO_CODE`
       * `ARGO_CODES[0]`

2. **Descarga de datos con `argopy`**

   ```python
   argopy.set_options(mode=args.mode, src=args.src)
   fetcher = ArgoDataFetcher(mode=args.mode, src=args.src)
   ds = fetcher.float(float_id).load().data
   ```

   No se usa `.time()` en el fetcher para evitar problemas de versiones (`InvalidFetcherAccessPoint: 'time'`).

3. **Filtro temporal (opcional, si `--days` está presente)**

   * Busca variable de tiempo (en este orden):

     * `TIME`
     * `JULD`
     * `time`
   * Intenta convertirla a `datetime64` con `xr.decode_cf`.
   * Si el tipo resultante no es `datetime64`, **no se aplica filtro**.
   * Si todo va bien, se aplica:

     ```python
     mask = (t >= np.datetime64(t0)) & (t <= np.datetime64(t1))
     ds = ds.where(mask, drop=True)
     ```

4. **Nombre del archivo de salida**

   * Si se pudo convertir la variable de tiempo a `datetime64`:

     * Se calcula `tmin` y `tmax` en los datos (min y max).
     * `argo_<id>_<YYYYMMDD-YYYYMMDD>.nc`
   * Si NO se puede:

     * Si se especificó `--output`, se usa tal cual.
     * Si no, `argo_<id>_full.nc`.

5. **Atributos IGP**

   * Se añaden al `Dataset` antes de escribir el NetCDF:

     ```python
     ds.attrs["institution"]    = "Instituto Geofísico del Perú (IGP)"
     ds.attrs["acknowledgement"] = "IGP: Ciencia para protegernos, ciencia para avanzar"
     ds.attrs["argo_float_id"]  = str(float_id)
     ```

---

## 📜 Logs y depuración

El script utiliza `logging` con nivel `INFO`. Ejemplo de salida:

```text
[INFO] === INICIANDO DESCARGA ARGO ===
[INFO] IGP: Ciencia para protegernos, ciencia para avanzar
[INFO] Código leído desde línea de comandos: 6903002
[INFO] Flotador seleccionado: 6903002
[INFO] No se proporcionó --days: se descargará TODO el periodo disponible del flotador (sin filtro temporal).
[INFO] Configurando argopy: src='erddap', mode='expert'
[INFO] Descargando datos desde 'erddap' en modo 'expert' (sin filtro temporal en servidor)...
[INFO] Dimensiones originales del dataset: {'N_POINTS': 245270}
[INFO] Número de variables originales: 23
[INFO] Sin filtro temporal: se mantiene el rango completo de datos.
[INFO] Rango temporal en datos: 2004-12-15 → 2025-12-04
[INFO] Nombre de salida generado automáticamente: argo_6903002_20041215-20251204.nc
[INFO] Guardando dataset en NetCDF: argo_6903002_20041215-20251204.nc
[INFO] [OK] Datos guardados en: argo_6903002_20041215-20251204.nc
[INFO] === DESCARGA COMPLETADA ===
[INFO] IGP: Ciencia para protegernos, ciencia para avanzar
```

---

## 🛠️ Problemas frecuentes y soluciones

### 1. `InvalidFetcherAccessPoint: 'time' is not a valid access point`

Esto ocurre cuando se intenta hacer algo como:

```python
fetcher.float(float_id).time([...])
```

El script **NO** usa `.time()` en el fetcher, así que este error no debería aparecer con `downloadById.py`.
Si lo ves, probablemente es código antiguo o alguna prueba interactiva previa.

---

### 2. No se infiere el rango de fechas

Si en los logs ves:

```text
[WARN] No se puede inferir rango temporal porque 'TIME' no es datetime64 ni se pudo convertir con decode_cf.
```

Entonces:

* El NetCDF se guardará como:

  * `argo_<id>_full.nc` (si no diste `--output`), o
  * el nombre que diste con `-o/--output`.

Puedes inspeccionar la variable de tiempo manualmente:

```python
import xarray as xr
ds = xr.open_dataset("argo_6903002_full.nc")
print(ds["TIME"])
print(ds["TIME"].attrs)
```

---

### 3. Errores de red / servidor

Si el servidor ERDDAP / GDAC no responde, verás algo como:

```text
[ERROR] Error al descargar datos del flotador 6903002: <detalles>
```

En ese caso revisa:

* Conectividad a internet (si es un entorno con salida restringida).
* Si el servidor ERDDAP está disponible.
* Probar con `--src gdac` como alternativa:

```bash
python downloadById.py 6903002 --src gdac
```

---

## 🧾 Créditos

* Autor: MIGUEL ANDRADE PEREIRA
* Institución: **Instituto Geofísico del Perú (IGP)**
* Lema: **Ciencia para protegernos, ciencia para avanzar**

Sugerencias de mejora para futuro:

* Añadir opción `--plot` para generar mapas rápidos de las posiciones de los perfiles.
* Añadir opción para seleccionar sólo ciertas variables (`--vars TEMP,PSAL`).
* Añadir soporte para múltiples flotadores al mismo tiempo y guardarlos en un solo NetCDF.

