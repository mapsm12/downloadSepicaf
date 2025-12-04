# downloadById.py

Script en Python para **descargar datos ARGO de un flotador específico** usando [`argopy`](https://github.com/euroargodev/argopy) y guardarlos en un archivo NetCDF listo para análisis.

Incluye:

- Interfaz por línea de comandos.
- Soporte para leer el ID del flotador desde un archivo `.py`.
- Opción para filtrar por los últimos `N` días (o descargar **todo** el historial).
- Nombre de salida automático con rango temporal.
- Metadatos con la afiliación IGP y el lema institucional:

> **IGP: Ciencia para protegernos, ciencia para avanzar**

---

## 🧩 Requisitos

- Python 3.8+
- Paquetes:

```bash
pip install argopy xarray numpy
