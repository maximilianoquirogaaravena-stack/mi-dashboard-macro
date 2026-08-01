"""
fetch_data.py
Pega a la API del BCRA (Estadísticas Monetarias v4.0) y a DolarAPI (fuente Ámbito Financiero)
y guarda los resultados en CSV.
"""

import requests
import pandas as pd
from datetime import datetime, date
import warnings
import os

# --- Config ---
BCRA_BASE = "https://api.bcra.gob.ar/estadisticas/v4.0"
AMBITO_BASE = "https://dolarapi.com/v1/ambito"

VARIABLES_BCRA = {
    "reservas_internacionales": 1,
    "tc_mayorista": 5,
    "base_monetaria": 15,
    "inflacion_mensual": 27,
    "m2": 109,
}


def _get(url, params=None):
    """GET genérico con manejo del problema de SSL conocido en la API del BCRA."""
    try:
        r = requests.get(url, params=params, timeout=15)
    except requests.exceptions.SSLError:
        warnings.warn("SSL falló, reintentando sin verificación (conocido en api.bcra.gob.ar)")
        r = requests.get(url, params=params, timeout=15, verify=False)
        requests.packages.urllib3.disable_warnings()
    r.raise_for_status()
    return r.json()


def get_bcra_serie(id_variable: int, desde: str = None, hasta: str = None):
    """Trae la serie histórica completa de una variable, paginando si hace falta."""
    params = {"limit": 3000, "offset": 0}
    if desde:
        params["desde"] = desde
    if hasta:
        params["hasta"] = hasta

    all_detalle = []
    while True:
        data = _get(f"{BCRA_BASE}/Monetarias/{id_variable}", params=params)
        detalle = data["results"][0]["detalle"]
        all_detalle.extend(detalle)

        count = data["metadata"]["resultset"]["count"]
        if params["offset"] + len(detalle) >= count or len(detalle) == 0:
            break
        params["offset"] += params["limit"]

    df = pd.DataFrame(all_detalle)
    df["idVariable"] = id_variable
    return df


def get_all_bcra_variables(desde: str = None):
    """Trae todas las series definidas en VARIABLES_BCRA y las junta en un solo DataFrame largo."""
    frames = []
    for nombre, id_variable in VARIABLES_BCRA.items():
        try:
            df = get_bcra_serie(id_variable, desde=desde)
            df["variable"] = nombre
            frames.append(df)
            print(f"OK  {nombre} (id={id_variable}): {len(df)} registros")
        except Exception as e:
            print(f"ERROR {nombre} (id={id_variable}): {e}")
    return pd.concat(frames, ignore_index=True)


def get_ambito_dolares():
    """Trae todas las cotizaciones de dólar según Ámbito Financiero."""
    data = _get(f"{AMBITO_BASE}/dolares")
    df = pd.DataFrame(data)
    df["fecha_consulta"] = datetime.now().isoformat()
    return df


def append_csv(df, path):
    """Guarda agregando al histórico si el archivo ya existe, sin duplicar el header."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    file_exists = os.path.isfile(path)
    df.to_csv(path, mode="a", index=False, header=not file_exists)


if __name__ == "__main__":
    print("=== BCRA ===")
    os.makedirs("data", exist_ok=True)
    bcra_data = get_all_bcra_variables(desde="2020-01-01")
    bcra_data.to_csv("data/bcra_historico.csv", index=False)
    print(bcra_data.tail())

    print("\n=== Ámbito Financiero ===")
    dolares = get_ambito_dolares()
    append_csv(dolares, "data/dolares_historico.csv")
    print(dolares)