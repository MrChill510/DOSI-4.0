"""
modules/graficos.py — Figuras Plotly del dashboard DOSI-4.0.

Cada función recibe datos ya agregados/filtrados y devuelve un go.Figure.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import config as cfg

FUENTE = dict(family="Segoe UI, Roboto, Arial, sans-serif", size=16, color="#1F2937")


def _estilo(fig: go.Figure, titulo: str, alto: int = 420) -> go.Figure:
    """Aplica el estilo común: tema claro, tipografía grande, título descriptivo."""
    fig.update_layout(
        template="plotly_white",
        title=dict(text=titulo, font=dict(size=20, color=cfg.COLOR_PRIMARIO), x=0.01, xanchor="left"),
        font=FUENTE,
        height=alto,
        margin=dict(l=60, r=30, t=70, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1),
        hoverlabel=dict(font_size=14),
        separators=", ",  # coma decimal, espacio de miles
    )
    return fig


def figura_vacia(mensaje: str, titulo: str = "", alto: int = 300) -> go.Figure:
    """Figura en blanco con un mensaje centrado (para casos sin datos)."""
    fig = go.Figure()
    fig.add_annotation(text=mensaje, showarrow=False, font=dict(size=18, color=cfg.COLOR_GRIS),
                       xref="paper", yref="paper", x=0.5, y=0.5)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _estilo(fig, titulo, alto)


# ---------------------------------------------------------------------------
# 3. Gráfico de control del peso
# ---------------------------------------------------------------------------

def grafico_control(df: pd.DataFrame, en_kg: bool) -> go.Figure:
    """Gráfico de control de la pesada con objetivo, límites y puntos fuera de rango.

    Args:
        df: pesadas filtradas y enriquecidas, ordenadas por fecha_hora.
        en_kg: True -> eje en kg (útil con un solo ingrediente);
               False -> desviación % respecto al objetivo (comparable entre ingredientes).
    """
    d = df.sort_values("fecha_hora").reset_index(drop=True)
    d["n"] = d.index + 1
    if en_kg:
        y = d["peso_real_kg"]
        obj = d["peso_objetivo_kg"]
        lsup = obj * (1 + d["tolerancia_pct"] / 100)
        linf = obj * (1 - d["tolerancia_pct"] / 100)
        eje_y, titulo = "Peso real (kg)", "Gráfico de control del peso real vs. objetivo (kg)"
    elif d["tolerancia_pct"].nunique() == 1:
        # Todas las pesadas comparten tolerancia: desviación % con límites fijos
        tol = float(d["tolerancia_pct"].iloc[0])
        y = d["desviacion_pct"]
        obj = pd.Series(0.0, index=d.index)
        lsup, linf = pd.Series(tol, index=d.index), pd.Series(-tol, index=d.index)
        eje_y, titulo = "Desviación respecto al objetivo (%)", \
            f"Gráfico de control: desviación % de cada pesada (tolerancia ±{tol:g} %)".replace(".", ",")
    else:
        # Tolerancias distintas por ingrediente: se expresa la desviación como % de la
        # tolerancia permitida, así ±100 % es siempre el límite (comparable entre ingredientes)
        y = d["desviacion_pct"] / d["tolerancia_pct"] * 100
        obj = pd.Series(0.0, index=d.index)
        lsup, linf = pd.Series(100.0, index=d.index), pd.Series(-100.0, index=d.index)
        eje_y, titulo = "Desviación como % de la tolerancia", \
            "Gráfico de control: uso de la tolerancia en cada pesada (±100 % = límite)"

    fuera = ~d["dentro_tolerancia"]
    fig = go.Figure()
    # Límites y objetivo como líneas escalonadas (cambian si cambia el ingrediente)
    fig.add_trace(go.Scatter(x=d["n"], y=lsup, mode="lines", line=dict(color=cfg.COLOR_ROJO, dash="dash", width=1.5, shape="hv"),
                             name="Límite superior", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=d["n"], y=linf, mode="lines", line=dict(color=cfg.COLOR_ROJO, dash="dash", width=1.5, shape="hv"),
                             name="Límite inferior", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=d["n"], y=obj, mode="lines", line=dict(color=cfg.COLOR_VERDE, width=2, shape="hv"),
                             name="Objetivo", hoverinfo="skip"))

    custom = d[["fecha_hora", "ingrediente", "producto", "peso_objetivo_kg", "peso_real_kg",
                "desviacion_pct", "tolerancia_pct", "resultado_poka_yoke", "lote"]].copy()
    custom["fecha_hora"] = custom["fecha_hora"].dt.strftime("%d/%m/%Y %H:%M")
    hover = ("Pesada N.° %{x}<br>%{customdata[0]}<br><b>%{customdata[1]}</b> — %{customdata[2]}"
             "<br>Lote: %{customdata[8]}<br>Objetivo: %{customdata[3]:.3f} kg · Real: %{customdata[4]:.3f} kg"
             "<br>Desviación: %{customdata[5]:+.2f} % (tol. ±%{customdata[6]:.1f} %)"
             "<br>Poka-Yoke: %{customdata[7]}<extra></extra>")
    for mascara, nombre, color, tam in ((~fuera, "Dentro de tolerancia", cfg.COLOR_PRIMARIO, 6),
                                        (fuera, "Fuera de tolerancia", cfg.COLOR_ROJO, 10)):
        fig.add_trace(go.Scatter(
            x=d.loc[mascara, "n"], y=y[mascara], mode="markers", name=nombre,
            marker=dict(color=color, size=tam, line=dict(width=1, color="white"),
                        symbol="circle" if nombre.startswith("Dentro") else "diamond"),
            customdata=custom[mascara].values, hovertemplate=hover,
        ))
    fig.update_xaxes(title="N.° de pesada (orden cronológico)", rangeslider=dict(visible=True, thickness=0.06))
    fig.update_yaxes(title=eje_y, zeroline=False)
    return _estilo(fig, titulo, alto=500)


# ---------------------------------------------------------------------------
# 4. Errores por tipo
# ---------------------------------------------------------------------------

def grafico_errores_tipo(conteo: pd.DataFrame, por_turno: bool) -> go.Figure:
    """Barras horizontales de errores por tipo, opcionalmente agrupadas por turno."""
    fig = go.Figure()
    if por_turno:
        for turno, g in conteo.groupby("turno"):
            fig.add_trace(go.Bar(y=g["tipo_error"], x=g["errores"], name=f"Turno {turno}", orientation="h",
                                 marker_color=cfg.COLORES_TURNO.get(turno, cfg.COLOR_GRIS),
                                 text=g["errores"], textposition="outside",
                                 hovertemplate="%{y}<br>Errores: %{x}<extra>" + str(turno) + "</extra>"))
        fig.update_layout(barmode="group")
    else:
        c = conteo.sort_values("errores")
        fig.add_trace(go.Bar(y=c["tipo_error"], x=c["errores"], orientation="h", marker_color=cfg.COLOR_PRIMARIO,
                             text=c["errores"], textposition="outside", showlegend=False,
                             hovertemplate="%{y}<br>Errores: %{x}<extra></extra>"))
    fig.update_xaxes(title="N.° de errores registrados", rangemode="tozero")
    fig.update_yaxes(title="", categoryorder="array" if por_turno else None,
                     categoryarray=list(reversed(cfg.TIPOS_ERROR)) if por_turno else None)
    return _estilo(fig, "Errores de dosificación por tipo" + (" y turno" if por_turno else ""), alto=420)


# ---------------------------------------------------------------------------
# 5. Serie de tiempo
# ---------------------------------------------------------------------------

def grafico_serie_tiempo(serie: pd.DataFrame, por: str) -> go.Figure:
    """Dos paneles compartiendo eje X: tasa de error (%) y tiempo de ciclo medio (s)."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.10,
                        subplot_titles=("Tasa de error de dosificación (%)", "Tiempo medio de ciclo (s)"))
    grupos = [("Total", serie)] if por == "día" else list(serie.groupby("turno"))
    for nombre, g in grupos:
        color = cfg.COLOR_PRIMARIO if nombre == "Total" else cfg.COLORES_TURNO.get(nombre, cfg.COLOR_GRIS)
        etiqueta = "Todos los turnos" if nombre == "Total" else f"Turno {nombre}"
        fig.add_trace(go.Scatter(x=g["fecha"], y=g["tasa_error_pct"], mode="lines+markers", name=etiqueta,
                                 line=dict(color=color, width=2), marker=dict(size=6), legendgroup=etiqueta,
                                 customdata=g[["pesadas"]].values,
                                 hovertemplate="%{x|%d/%m/%Y}<br>Tasa de error: %{y:.1f} %"
                                               "<br>Pesadas: %{customdata[0]}<extra>" + etiqueta + "</extra>"),
                      row=1, col=1)
        fig.add_trace(go.Scatter(x=g["fecha"], y=g["tiempo_ciclo_medio_s"], mode="lines+markers", name=etiqueta,
                                 line=dict(color=color, width=2, dash="dot"), marker=dict(size=6),
                                 legendgroup=etiqueta, showlegend=False,
                                 hovertemplate="%{x|%d/%m/%Y}<br>Ciclo medio: %{y:.1f} s<extra>" + etiqueta + "</extra>"),
                      row=2, col=1)
    fig.update_yaxes(title="%", rangemode="tozero", row=1, col=1)
    fig.update_yaxes(title="s", row=2, col=1)
    fig.update_xaxes(tickformat="%d/%m", row=2, col=1)
    fig.update_annotations(font=dict(size=15, color="#374151"))
    titulo = "Evolución de la tasa de error y del tiempo de ciclo " + ("por día" if por == "día" else "por día y turno")
    return _estilo(fig, titulo, alto=560)


# ---------------------------------------------------------------------------
# 6. Auditoría 5S
# ---------------------------------------------------------------------------

def grafico_radar_5s(promedios: pd.Series, umbral_verde: float) -> go.Figure:
    """Radar del puntaje promedio de cada S, con la meta (umbral verde) como referencia."""
    etiquetas = ["Seiri<br>(clasificar)", "Seiton<br>(ordenar)", "Seiso<br>(limpiar)",
                 "Seiketsu<br>(estandarizar)", "Shitsuke<br>(disciplina)"]
    valores = [float(promedios[c]) for c in cfg.COLUMNAS_S]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=[umbral_verde] * 5 + [umbral_verde], theta=etiquetas + etiquetas[:1],
                                  mode="lines", name=f"Meta ({umbral_verde:.0f})",
                                  line=dict(color=cfg.COLOR_VERDE, dash="dash"), hoverinfo="skip"))
    fig.add_trace(go.Scatterpolar(r=valores + valores[:1], theta=etiquetas + etiquetas[:1], fill="toself",
                                  name="Puntaje promedio", line=dict(color=cfg.COLOR_PRIMARIO, width=2),
                                  fillcolor="rgba(31,78,121,0.25)",
                                  hovertemplate="%{theta}<br>%{r:.1f} / 100<extra></extra>"))
    fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100], tickfont=dict(size=11, color=cfg.COLOR_GRIS),
                                                 angle=54, tickangle=54),
                                 angularaxis=dict(tickfont=dict(size=14), rotation=90, direction="clockwise")))
    fig = _estilo(fig, "Auditoría 5S: puntaje promedio por S", alto=480)
    fig.update_layout(margin=dict(l=90, r=90, t=90, b=70),
                      legend=dict(orientation="h", yanchor="top", y=-0.06, xanchor="center", x=0.5))
    return fig


def grafico_evolucion_5s(evol: pd.DataFrame, umbral_verde: float, umbral_ambar: float) -> go.Figure:
    """Evolución del puntaje global 5S por fecha y turno, con bandas del semáforo."""
    fig = go.Figure()
    fig.add_hrect(y0=umbral_verde, y1=100, fillcolor=cfg.COLOR_VERDE, opacity=0.08, line_width=0)
    fig.add_hrect(y0=umbral_ambar, y1=umbral_verde, fillcolor=cfg.COLOR_AMBAR, opacity=0.10, line_width=0)
    fig.add_hrect(y0=0, y1=umbral_ambar, fillcolor=cfg.COLOR_ROJO, opacity=0.06, line_width=0)
    for turno, g in evol.groupby("turno"):
        fig.add_trace(go.Scatter(x=g["fecha"], y=g["puntaje_global"], mode="lines+markers", name=f"Turno {turno}",
                                 line=dict(color=cfg.COLORES_TURNO.get(turno, cfg.COLOR_GRIS), width=2.5),
                                 marker=dict(size=8),
                                 hovertemplate="%{x|%d/%m/%Y}<br>Puntaje 5S: %{y:.1f}<extra>Turno " + str(turno) + "</extra>"))
    ymin = max(0, min(evol["puntaje_global"].min() - 10, umbral_ambar - 10)) if len(evol) else 0
    fig.update_yaxes(title="Puntaje global 5S (0-100)", range=[ymin, 100])
    fig.update_xaxes(title="Fecha de auditoría", tickformat="%d/%m")
    return _estilo(fig, "Evolución del puntaje global 5S (bandas = semáforo)", alto=440)


# ---------------------------------------------------------------------------
# 7. Comparativo antes vs después
# ---------------------------------------------------------------------------

def grafico_comparativo(comp: pd.DataFrame) -> go.Figure:
    """Barras agrupadas antes/después para tasa de error, tiempo de ciclo y puntaje 5S."""
    metricas = [("tasa_error_pct", "Tasa de error (%)", "%{y:.1f} %"),
                ("tiempo_ciclo_medio_s", "Tiempo medio de ciclo (s)", "%{y:.1f} s"),
                ("puntaje_5s", "Puntaje global 5S", "%{y:.1f}")]
    fig = make_subplots(rows=1, cols=3, subplot_titles=[m[1] for m in metricas], horizontal_spacing=0.08)
    for i, (col, _, fmt) in enumerate(metricas, start=1):
        for _, fila in comp.iterrows():
            val = fila[col]
            fig.add_trace(go.Bar(x=[fila["periodo"].capitalize()], y=[val],
                                 marker_color=cfg.COLORES_PERIODO.get(fila["periodo"], cfg.COLOR_GRIS),
                                 texttemplate=fmt if pd.notna(val) else "s/d", textposition="outside",
                                 name=fila["periodo"].capitalize(), showlegend=(i == 1),
                                 legendgroup=fila["periodo"],
                                 hovertemplate="%{x}: %{y:.2f}<extra></extra>"),
                          row=1, col=i)
        maximo = comp[col].max()
        if pd.notna(maximo):
            fig.update_yaxes(range=[0, maximo * 1.25], row=1, col=i)
    fig.update_annotations(font=dict(size=15, color="#374151"))
    fig = _estilo(fig, "Comparativo antes vs. después de la implementación", alto=440)
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.14, xanchor="center", x=0.5),
                      margin=dict(t=90, b=90))
    return fig
