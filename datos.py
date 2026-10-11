"""
modules/datos.py — Generación de datos simulados, lectura y validación de CSV.

Todas las funciones son puras (no dependen de Streamlit): reciben datos y
devuelven datos. El cacheo con @st.cache_data se aplica en app.py.
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd

import config as cfg

# ---------------------------------------------------------------------------
# Datos simulados
# ---------------------------------------------------------------------------

# Ingredientes que usa cada producto (secuencia de dosificación) y factor de escala
_RECETAS = {
    "BIO AVEMIX PLUS": (["Premix vitamínico", "Premix mineral", "DL-Metionina",
                         "L-Lisina HCl", "Coccidiostato", "Enzima fitasa"], 1.00),
    "NUTRIMAX": (["Premix vitamínico", "Premix mineral", "L-Lisina HCl",
                  "Sal industrial", "Antioxidante"], 1.20),
    "CORIMIX": (["Premix mineral", "DL-Metionina", "Sal industrial",
                 "Antioxidante", "Enzima fitasa"], 0.80),
    "PICO DE ACERO": (["Premix vitamínico", "DL-Metionina", "L-Lisina HCl",
                       "Coccidiostato", "Sal industrial", "Antioxidante"], 1.10),
}

_PESOS_TIPO_ERROR = {
    "Ingrediente equivocado": 0.20,
    "Sobrepeso": 0.30,
    "Subpeso": 0.30,
    "Secuencia": 0.12,
    "Lote no autorizado": 0.08,
}


def generar_pesadas_simuladas(semilla: int = cfg.SEMILLA,
                              n_pesadas: int = cfg.N_PESADAS,
                              incluir_periodo: bool = True) -> pd.DataFrame:
    """Genera un registro simulado de pesadas de micro-ingredientes.

    Se simulan batches (lotes) completos: cada lote corresponde a un producto,
    un turno y un operario, y contiene la secuencia de ingredientes de la receta.

    Args:
        semilla: semilla del generador aleatorio (resultados reproducibles).
        n_pesadas: número aproximado de pesadas a generar.
        incluir_periodo: si True, agrega la columna "periodo" (antes/después)
            dividiendo el horizonte simulado en dos mitades, solo para poder
            demostrar el gráfico comparativo.

    Returns:
        DataFrame con las columnas de cfg.COLUMNAS_PESADAS (+ "periodo").
    """
    rng = np.random.default_rng(semilla)
    inicio = pd.Timestamp(cfg.FECHA_INICIO)
    dias_laborables = [inicio + pd.Timedelta(days=d) for d in range(cfg.DIAS_SIMULADOS)
                       if (inicio + pd.Timedelta(days=d)).dayofweek < 6]  # lunes-sábado
    corte = dias_laborables[len(dias_laborables) // 2]

    tipos = list(_PESOS_TIPO_ERROR)
    probs_tipo = np.array(list(_PESOS_TIPO_ERROR.values()))
    probs_tipo = probs_tipo / probs_tipo.sum()

    filas: list[dict] = []
    n_lote = 0
    while len(filas) < n_pesadas:
        n_lote += 1
        dia = dias_laborables[rng.integers(len(dias_laborables))]
        turno = cfg.TURNOS[rng.integers(len(cfg.TURNOS))]
        hora_base = 6 if turno == "Mañana" else 14
        t = dia + pd.Timedelta(hours=hora_base) + pd.Timedelta(minutes=int(rng.integers(10, 420)))
        producto = cfg.PRODUCTOS[rng.integers(len(cfg.PRODUCTOS))]
        operario = cfg.OPERARIOS[rng.integers(len(cfg.OPERARIOS))]
        periodo = "antes" if dia < corte else "después"
        prob_error = 0.12 if periodo == "antes" else 0.04
        lote = f"L-{dia:%y%m%d}-{n_lote:03d}"
        ingredientes, escala = _RECETAS[producto]

        for ingrediente in ingredientes:
            objetivo_base, tol = cfg.INGREDIENTES[ingrediente]
            objetivo = round(objetivo_base * escala, 3)
            tipo_error = cfg.SIN_ERROR
            if rng.random() < prob_error:
                tipo_error = rng.choice(tipos, p=probs_tipo)

            # Peso real según el tipo de error
            if tipo_error == "Sobrepeso":
                desv = rng.uniform(tol * 1.1, tol * 3.0)
            elif tipo_error == "Subpeso":
                desv = -rng.uniform(tol * 1.1, tol * 3.0)
            else:
                desv = float(np.clip(rng.normal(0, tol / 3), -tol * 0.95, tol * 0.95))
            real = round(objetivo * (1 + desv / 100), 3)

            # Respuesta del Poka-Yoke (detección ~97 %)
            if tipo_error == cfg.SIN_ERROR:
                resultado = "OK"
            elif rng.random() < 0.97:
                if tipo_error in ("Sobrepeso", "Subpeso") and abs(desv) <= 2 * tol:
                    resultado = "ALERTA"
                else:
                    resultado = "BLOQUEO"
            else:
                resultado = "OK"  # error no detectado

            # Tiempo de ciclo
            base = rng.normal(75, 10) if periodo == "antes" else rng.normal(62, 8)
            extra = {"BLOQUEO": rng.uniform(40, 120), "ALERTA": rng.uniform(10, 25)}.get(resultado, 0)
            ciclo = round(max(base + extra, 25), 1)

            estado = rng.choice(["Operando", "Parada", "Calibración"], p=[0.94, 0.04, 0.02])

            fila = {
                "fecha_hora": t, "turno": turno, "producto": producto,
                "ingrediente": ingrediente, "lote": lote, "operario_codigo": operario,
                "peso_objetivo_kg": objetivo, "peso_real_kg": real, "tolerancia_pct": tol,
                "resultado_poka_yoke": resultado, "tipo_error": tipo_error,
                "tiempo_ciclo_s": ciclo, "estado_estacion": estado,
            }
            if incluir_periodo:
                fila["periodo"] = periodo
            filas.append(fila)
            t += pd.Timedelta(seconds=ciclo + rng.uniform(5, 30))

    df = pd.DataFrame(filas).sort_values("fecha_hora").reset_index(drop=True)
    return df


def generar_5s_simulado(semilla: int = cfg.SEMILLA, incluir_periodo: bool = True) -> pd.DataFrame:
    """Genera auditorías 5S semanales simuladas (una por turno y semana).

    Args:
        semilla: semilla del generador aleatorio.
        incluir_periodo: si True, agrega la columna "periodo" (antes/después).

    Returns:
        DataFrame con las columnas de cfg.COLUMNAS_5S (+ "periodo").
    """
    rng = np.random.default_rng(semilla + 1)
    inicio = pd.Timestamp(cfg.FECHA_INICIO)
    semanas = cfg.DIAS_SIMULADOS // 7
    offsets = {"seiri": 4, "seiton": 0, "seiso": -3, "seiketsu": -5, "shitsuke": -8}
    filas = []
    for s in range(semanas):
        fecha = inicio + pd.Timedelta(days=7 * s + 5)  # auditoría los sábados
        tendencia = 62 + (s / max(semanas - 1, 1)) * 26
        for turno in cfg.TURNOS:
            ajuste_turno = 0 if turno == "Mañana" else -3
            fila = {"fecha": fecha.normalize(), "turno": turno}
            for col, off in offsets.items():
                fila[col] = float(np.clip(round(tendencia + off + ajuste_turno + rng.normal(0, 3)), 0, 100))
            if incluir_periodo:
                fila["periodo"] = "antes" if s < semanas / 2 else "después"
            filas.append(fila)
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------
# Lectura y validación de CSV subidos
# ---------------------------------------------------------------------------

def leer_csv(contenido: bytes) -> pd.DataFrame:
    """Lee un CSV desde bytes detectando separador (',' o ';') y codificación.

    Args:
        contenido: bytes del archivo subido.

    Returns:
        DataFrame crudo (sin validar).

    Raises:
        ValueError: si el archivo no puede interpretarse como CSV.
    """
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            texto = contenido.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("No se pudo leer la codificación del archivo.")
    primera = texto.splitlines()[0] if texto.strip() else ""
    sep = ";" if primera.count(";") > primera.count(",") else ","
    try:
        df = pd.read_csv(io.StringIO(texto), sep=sep, dtype=str, keep_default_na=True)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"El archivo no tiene formato CSV válido ({exc}).") from exc
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def _a_numero(serie: pd.Series) -> pd.Series:
    """Convierte texto a número aceptando coma decimal (formato Excel en español)."""
    return pd.to_numeric(serie.astype("string").str.strip().str.replace(",", ".", regex=False),
                         errors="coerce")


def _normalizar_periodo(serie: pd.Series) -> pd.Series:
    """Normaliza la columna periodo a los valores 'antes' / 'después'."""
    s = serie.astype("string").str.strip().str.lower()
    s = s.replace({"despues": "después", "after": "después", "before": "antes"})
    return s.where(s.isin(["antes", "después"]))


def validar_pesadas(df: pd.DataFrame) -> tuple[pd.DataFrame | None, list[str]]:
    """Valida y limpia el CSV de pesadas.

    Args:
        df: DataFrame crudo leído del CSV.

    Returns:
        (df_limpio, mensajes). Si faltan columnas obligatorias, df_limpio es None
        y los mensajes explican qué falta.
    """
    mensajes: list[str] = []
    faltantes = [c for c in cfg.COLUMNAS_PESADAS if c not in df.columns]
    if faltantes:
        return None, [f"Faltan columnas obligatorias: {', '.join(faltantes)}."]

    d = df.copy()
    d["fecha_hora"] = pd.to_datetime(d["fecha_hora"], errors="coerce", dayfirst=False)
    for col in ("peso_objetivo_kg", "peso_real_kg", "tolerancia_pct", "tiempo_ciclo_s"):
        d[col] = _a_numero(d[col])
    for col in ("turno", "producto", "ingrediente", "lote", "operario_codigo",
                "tipo_error", "estado_estacion", "resultado_poka_yoke"):
        d[col] = d[col].astype("string").str.strip()
    d["resultado_poka_yoke"] = d["resultado_poka_yoke"].str.upper()
    d["tipo_error"] = d["tipo_error"].fillna(cfg.SIN_ERROR).replace({"": cfg.SIN_ERROR})
    for col in ("turno", "producto", "ingrediente", "operario_codigo", "estado_estacion", "lote"):
        d[col] = d[col].fillna("Sin dato")

    esenciales = ["fecha_hora", "peso_objetivo_kg", "peso_real_kg", "tolerancia_pct"]
    invalidas = d[esenciales].isna().any(axis=1) | (d["peso_objetivo_kg"] <= 0)
    if invalidas.any():
        mensajes.append(f"Se descartaron {int(invalidas.sum())} filas con fecha, pesos o "
                        "tolerancia vacíos o no numéricos.")
        d = d[~invalidas]

    validos = d["resultado_poka_yoke"].isin(["OK", "ALERTA", "BLOQUEO"])
    if (~validos).any():
        mensajes.append(f"{int((~validos).sum())} filas tenían un resultado distinto de "
                        "OK/ALERTA/BLOQUEO; se marcaron como 'OK'.")
        d.loc[~validos, "resultado_poka_yoke"] = "OK"

    if d["tiempo_ciclo_s"].isna().any():
        mensajes.append(f"{int(d['tiempo_ciclo_s'].isna().sum())} filas sin tiempo de ciclo: "
                        "se excluyen solo del cálculo del tiempo medio.")

    if "periodo" in d.columns:
        d["periodo"] = _normalizar_periodo(d["periodo"])
        if d["periodo"].isna().all():
            d = d.drop(columns="periodo")
            mensajes.append("La columna 'periodo' no tiene valores 'antes'/'después'; se ignora.")

    if d.empty:
        mensajes.append("El archivo no tiene filas válidas.")
        return None, mensajes
    return d.sort_values("fecha_hora").reset_index(drop=True), mensajes


def validar_5s(df: pd.DataFrame) -> tuple[pd.DataFrame | None, list[str]]:
    """Valida y limpia el CSV de auditorías 5S (puntajes 0-100).

    Args:
        df: DataFrame crudo leído del CSV.

    Returns:
        (df_limpio, mensajes). Si faltan columnas, df_limpio es None.
    """
    mensajes: list[str] = []
    faltantes = [c for c in cfg.COLUMNAS_5S if c not in df.columns]
    if faltantes:
        return None, [f"Faltan columnas obligatorias en el CSV 5S: {', '.join(faltantes)}."]

    d = df.copy()
    d["fecha"] = pd.to_datetime(d["fecha"], errors="coerce").dt.normalize()
    d["turno"] = d["turno"].astype("string").str.strip().fillna("Sin dato")
    for col in cfg.COLUMNAS_S:
        d[col] = _a_numero(d[col])
    fuera = (d[cfg.COLUMNAS_S] < 0) | (d[cfg.COLUMNAS_S] > 100)
    if fuera.any().any():
        mensajes.append("Algunos puntajes estaban fuera de 0-100 y se ignoraron.")
        d[cfg.COLUMNAS_S] = d[cfg.COLUMNAS_S].mask(fuera)
    invalidas = d["fecha"].isna() | d[cfg.COLUMNAS_S].isna().all(axis=1)
    if invalidas.any():
        mensajes.append(f"Se descartaron {int(invalidas.sum())} auditorías sin fecha o sin puntajes.")
        d = d[~invalidas]
    if "periodo" in d.columns:
        d["periodo"] = _normalizar_periodo(d["periodo"])
        if d["periodo"].isna().all():
            d = d.drop(columns="periodo")
    if d.empty:
        return None, mensajes + ["El CSV 5S no tiene filas válidas."]
    return d.sort_values("fecha").reset_index(drop=True), mensajes
