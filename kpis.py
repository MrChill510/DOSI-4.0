"""
modules/kpis.py — Filtros y cálculo de indicadores del dashboard DOSI-4.0.

Funciones puras: reciben DataFrames y parámetros, devuelven DataFrames o dicts.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config as cfg

# Texto con la definición de cada KPI (se muestra en pantalla)
DEFINICIONES = {
    "total": "Número de pesadas registradas en el filtro actual.",
    "dentro_tol": "Pesadas con |peso real − objetivo| / objetivo × 100 ≤ tolerancia %, "
                  "dividido entre el total de pesadas.",
    "deteccion": "Errores con resultado ALERTA o BLOQUEO ÷ total de errores registrados "
                 "(tipo_error ≠ 'Ninguno').",
    "ciclo": "Promedio de tiempo_ciclo_s de las pesadas filtradas.",
    "5s": "Promedio de las 5 S (0-100) de las auditorías del rango de fechas y turnos "
          "filtrados. Semáforo: verde ≥ {v}, ámbar {a}-{v1}, rojo < {a}.",
}


# ---------------------------------------------------------------------------
# Preparación y filtros
# ---------------------------------------------------------------------------

def enriquecer_pesadas(df: pd.DataFrame, tolerancia_global: float | None = None) -> pd.DataFrame:
    """Agrega columnas derivadas: desviación, dentro de tolerancia, error y detección.

    Args:
        df: pesadas validadas.
        tolerancia_global: si se indica, reemplaza la tolerancia_pct del archivo
            (parámetro configurable desde la barra lateral).

    Returns:
        Copia del DataFrame con columnas: fecha, desviacion_pct, dentro_tolerancia,
        es_error, detectado.
    """
    d = df.copy()
    if tolerancia_global is not None:
        d["tolerancia_pct"] = float(tolerancia_global)
    d["fecha"] = d["fecha_hora"].dt.normalize()
    d["desviacion_pct"] = (d["peso_real_kg"] - d["peso_objetivo_kg"]) / d["peso_objetivo_kg"] * 100
    d["dentro_tolerancia"] = d["desviacion_pct"].abs() <= d["tolerancia_pct"]
    d["es_error"] = d["tipo_error"] != cfg.SIN_ERROR
    d["detectado"] = d["es_error"] & d["resultado_poka_yoke"].isin(["ALERTA", "BLOQUEO"])
    return d


def aplicar_filtros(df: pd.DataFrame, fecha_ini, fecha_fin, turnos: list, productos: list,
                    ingredientes: list, operarios: list) -> pd.DataFrame:
    """Filtra las pesadas. Una lista vacía significa "todos".

    Args:
        df: pesadas enriquecidas.
        fecha_ini, fecha_fin: rango de fechas (inclusive).
        turnos, productos, ingredientes, operarios: valores seleccionados.

    Returns:
        DataFrame filtrado (puede quedar vacío).
    """
    m = (df["fecha"] >= pd.Timestamp(fecha_ini)) & (df["fecha"] <= pd.Timestamp(fecha_fin))
    for col, valores in (("turno", turnos), ("producto", productos),
                         ("ingrediente", ingredientes), ("operario_codigo", operarios)):
        if valores:
            m &= df[col].isin(valores)
    return df[m]


def filtrar_5s(df5s: pd.DataFrame, fecha_ini, fecha_fin, turnos: list) -> pd.DataFrame:
    """Filtra las auditorías 5S por fecha y turno (no tienen producto ni operario)."""
    m = (df5s["fecha"] >= pd.Timestamp(fecha_ini)) & (df5s["fecha"] <= pd.Timestamp(fecha_fin))
    if turnos:
        m &= df5s["turno"].isin(turnos)
    d = df5s[m].copy()
    d["puntaje_global"] = d[cfg.COLUMNAS_S].mean(axis=1)
    return d


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------

def semaforo(puntaje: float | None, umbral_verde: float = cfg.UMBRAL_VERDE,
             umbral_ambar: float = cfg.UMBRAL_AMBAR) -> tuple[str, str]:
    """Devuelve (estado, color) del semáforo 5S para un puntaje 0-100."""
    if puntaje is None or pd.isna(puntaje):
        return "Sin datos", cfg.COLOR_GRIS
    if puntaje >= umbral_verde:
        return "Verde", cfg.COLOR_VERDE
    if puntaje >= umbral_ambar:
        return "Ámbar", cfg.COLOR_AMBAR
    return "Rojo", cfg.COLOR_ROJO


def _pct(num: float, den: float) -> float | None:
    """Porcentaje seguro (None si el denominador es 0)."""
    return None if den == 0 else 100.0 * num / den


def calcular_kpis(df: pd.DataFrame, df5s: pd.DataFrame) -> dict:
    """Calcula los KPIs de la fila de tarjetas.

    Args:
        df: pesadas filtradas y enriquecidas.
        df5s: auditorías 5S filtradas (con puntaje_global).

    Returns:
        dict con total, pct_dentro_tol, pct_deteccion, n_errores, n_detectados,
        tiempo_ciclo_medio y puntaje_5s (None cuando no hay datos).
    """
    total = len(df)
    n_err = int(df["es_error"].sum()) if total else 0
    n_det = int(df["detectado"].sum()) if total else 0
    ciclo = df["tiempo_ciclo_s"].mean() if total else np.nan
    p5s = df5s["puntaje_global"].mean() if len(df5s) else np.nan
    return {
        "total": total,
        "pct_dentro_tol": _pct(df["dentro_tolerancia"].sum(), total) if total else None,
        "n_errores": n_err,
        "n_detectados": n_det,
        "pct_deteccion": _pct(n_det, n_err),
        "tasa_error": _pct(n_err, total) if total else None,
        "tiempo_ciclo_medio": None if pd.isna(ciclo) else float(ciclo),
        "puntaje_5s": None if pd.isna(p5s) else float(p5s),
    }


# ---------------------------------------------------------------------------
# Agregaciones para gráficos
# ---------------------------------------------------------------------------

def errores_por_tipo(df: pd.DataFrame, por_turno: bool = False) -> pd.DataFrame:
    """Cuenta errores por tipo (opcionalmente separados por turno).

    Returns:
        DataFrame con columnas tipo_error, [turno], errores. Incluye los cinco
        tipos estándar aunque tengan 0 casos.
    """
    err = df[df["es_error"]]
    claves = ["tipo_error", "turno"] if por_turno else ["tipo_error"]
    conteo = err.groupby(claves, observed=True).size().rename("errores").reset_index()
    tipos = list(dict.fromkeys(cfg.TIPOS_ERROR + sorted(set(err["tipo_error"]) - set(cfg.TIPOS_ERROR))))
    if por_turno:
        turnos = sorted(df["turno"].unique())
        base = pd.MultiIndex.from_product([tipos, turnos], names=claves).to_frame(index=False)
    else:
        base = pd.DataFrame({"tipo_error": tipos})
    out = base.merge(conteo, on=claves, how="left").fillna({"errores": 0})
    out["errores"] = out["errores"].astype(int)
    return out


def serie_temporal(df: pd.DataFrame, por: str = "día") -> pd.DataFrame:
    """Tasa de error (%) y tiempo de ciclo medio por día o por día y turno.

    Args:
        df: pesadas filtradas.
        por: "día" o "turno" (día + turno).

    Returns:
        DataFrame con fecha, [turno], pesadas, tasa_error_pct, tiempo_ciclo_medio_s.
    """
    claves = ["fecha"] if por == "día" else ["fecha", "turno"]
    g = df.groupby(claves, observed=True).agg(
        pesadas=("es_error", "size"),
        errores=("es_error", "sum"),
        tiempo_ciclo_medio_s=("tiempo_ciclo_s", "mean"),
    ).reset_index()
    g["tasa_error_pct"] = 100 * g["errores"] / g["pesadas"]
    return g


def resumen_5s(df5s: pd.DataFrame) -> pd.Series:
    """Promedio de cada S en el periodo filtrado (para el radar)."""
    return df5s[cfg.COLUMNAS_S].mean()


def evolucion_5s(df5s: pd.DataFrame) -> pd.DataFrame:
    """Puntaje global 5S por fecha de auditoría y turno."""
    return (df5s.groupby(["fecha", "turno"], observed=True)["puntaje_global"]
            .mean().reset_index())


def comparativo_periodos(df: pd.DataFrame, df5s: pd.DataFrame) -> pd.DataFrame | None:
    """Compara antes vs después en tasa de error, tiempo de ciclo y puntaje 5S.

    Returns:
        DataFrame con periodo, tasa_error_pct, tiempo_ciclo_medio_s, puntaje_5s,
        o None si las pesadas no tienen la columna 'periodo'.
    """
    if "periodo" not in df.columns or df["periodo"].isna().all():
        return None
    g = df.dropna(subset=["periodo"]).groupby("periodo", observed=True).agg(
        pesadas=("es_error", "size"), errores=("es_error", "sum"),
        tiempo_ciclo_medio_s=("tiempo_ciclo_s", "mean"),
    )
    g["tasa_error_pct"] = 100 * g["errores"] / g["pesadas"]
    if "periodo" in df5s.columns and len(df5s):
        g["puntaje_5s"] = df5s.groupby("periodo", observed=True)["puntaje_global"].mean()
    else:
        g["puntaje_5s"] = np.nan
    orden = [p for p in ("antes", "después") if p in g.index]
    return g.loc[orden].reset_index()


def alertas_recientes(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Últimas n pesadas con resultado ALERTA o BLOQUEO (más reciente primero)."""
    cols = ["fecha_hora", "turno", "producto", "ingrediente", "lote", "operario_codigo",
            "peso_objetivo_kg", "peso_real_kg", "desviacion_pct", "resultado_poka_yoke",
            "tipo_error"]
    a = df[df["resultado_poka_yoke"].isin(["ALERTA", "BLOQUEO"])]
    return a.sort_values("fecha_hora", ascending=False).head(n)[cols]
