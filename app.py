"""
app.py — Dashboard DOSI-4.0 (Poka-Yoke + IoT + auditoría 5S digital).

Estación de pesaje de micro-ingredientes · Planta de alimentos balanceados.
Ejecutar con:  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import config as cfg
from modules import datos, graficos, kpis

st.set_page_config(page_title="DOSI-4.0 · Dashboard", page_icon="⚖️", layout="wide",
                   initial_sidebar_state="expanded")

# ---------------------------------------------------------------------------
# Estilos (tema claro, tipografía grande para proyectar)
# ---------------------------------------------------------------------------
st.markdown(f"""
<style>
html, body, [class*="css"] {{ font-size: 17px; }}
.block-container {{ padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1600px; }}
h1 {{ color: {cfg.COLOR_PRIMARIO}; font-size: 2.1rem !important; margin-bottom: 0 !important; }}
h2, h3 {{ color: {cfg.COLOR_PRIMARIO}; }}
.subtitulo {{ color: {cfg.COLOR_GRIS}; font-size: 1.05rem; margin-bottom: .8rem; }}
.aviso {{ background: #FFF4E5; border: 2px solid {cfg.COLOR_AMBAR}; border-left: 10px solid {cfg.COLOR_ROJO};
          color: #7A2E00; padding: .7rem 1rem; border-radius: 8px; font-weight: 700; font-size: 1.15rem;
          letter-spacing: .02em; margin: .4rem 0 1rem 0; }}
.aviso small {{ display:block; font-weight: 400; font-size: .9rem; color: #7A4A00; letter-spacing: 0; }}
.tarjeta {{ background: {cfg.COLOR_FONDO_TARJETA}; border-radius: 12px; padding: 14px 16px 10px 16px;
            border-top: 5px solid {cfg.COLOR_PRIMARIO}; height: 100%; min-height: 268px; }}
.tarjeta .etq {{ font-size: .95rem; color: #374151; font-weight: 600; }}
.tarjeta .val {{ font-size: 2.3rem; font-weight: 800; color: #111827; line-height: 1.15; margin: 4px 0; }}
.tarjeta .sub {{ font-size: .9rem; color: #4B5563; }}
.tarjeta .def {{ font-size: .76rem; color: {cfg.COLOR_GRIS}; margin-top: 6px; line-height: 1.25; }}
.pildora {{ display:inline-block; padding: 2px 12px; border-radius: 999px; color: white; font-weight: 700;
            font-size: .95rem; }}
.stTabs [data-baseweb="tab"] {{ font-size: 1.05rem; font-weight: 600; }}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Carga de datos (cacheada)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Generando datos simulados…")
def cargar_simulados(semilla: int, n_pesadas: int, incluir_periodo: bool):
    """Pesadas y auditorías 5S simuladas (reproducibles con la semilla)."""
    return (datos.generar_pesadas_simuladas(semilla, n_pesadas, incluir_periodo),
            datos.generar_5s_simulado(semilla, incluir_periodo))


@st.cache_data(show_spinner="Leyendo CSV…")
def cargar_csv(contenido: bytes, tipo: str):
    """Lee y valida un CSV subido. tipo = 'pesadas' | '5s'. Devuelve (df | None, mensajes)."""
    try:
        crudo = datos.leer_csv(contenido)
    except ValueError as exc:
        return None, [str(exc)]
    return datos.validar_pesadas(crudo) if tipo == "pesadas" else datos.validar_5s(crudo)


def fmt(valor, patron: str, vacio: str = "—") -> str:
    """Formatea un número o devuelve un guion si es None."""
    return vacio if valor is None else patron.format(valor).replace(".", ",")


def tarjeta(col, etiqueta: str, valor: str, sub: str, definicion: str, color_borde: str = cfg.COLOR_PRIMARIO):
    """Dibuja una tarjeta KPI con su definición en texto pequeño."""
    col.markdown(f"""<div class="tarjeta" style="border-top-color:{color_borde}">
        <div class="etq">{etiqueta}</div><div class="val">{valor}</div>
        <div class="sub">{sub}</div><div class="def">ⓘ {definicion}</div></div>""",
                 unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Barra lateral: fuente de datos y parámetros
# ---------------------------------------------------------------------------
st.sidebar.markdown(f"## ⚖️ DOSI-4.0")
st.sidebar.caption("Poka-Yoke + IoT + auditoría 5S digital")

with st.sidebar.expander("📂 Fuente de datos", expanded=False):
    archivo_pes = st.file_uploader("CSV de pesadas", type=["csv"], key="up_pesadas")
    archivo_5s = st.file_uploader("CSV de auditoría 5S", type=["csv"], key="up_5s")
    st.caption("Sin archivos se usan datos simulados. Columnas esperadas en la pestaña "
               "«Datos y alertas» y en el README.")

with st.sidebar.expander("⚙️ Parámetros", expanded=False):
    umbral_verde = st.number_input("Semáforo 5S: verde desde", 0, 100, cfg.UMBRAL_VERDE, key="p_verde")
    umbral_ambar = st.number_input("Semáforo 5S: ámbar desde", 0, 100, cfg.UMBRAL_AMBAR, key="p_ambar")
    if umbral_ambar >= umbral_verde:
        st.warning("El umbral ámbar debe ser menor que el verde; se usan los valores por defecto.")
        umbral_verde, umbral_ambar = cfg.UMBRAL_VERDE, cfg.UMBRAL_AMBAR
    usar_tol_global = st.checkbox("Usar una tolerancia única para todos los ingredientes", key="p_tol_on")
    tol_global = st.number_input("Tolerancia única (± %)", 0.1, 20.0, 2.0, 0.1, key="p_tol",
                                 disabled=not usar_tol_global)
    st.markdown("**Datos simulados**")
    semilla = st.number_input("Semilla", 0, 99999, cfg.SEMILLA, key="p_semilla")
    n_pesadas = st.number_input("N.° de pesadas", 50, 5000, cfg.N_PESADAS, 50, key="p_n")
    demo_periodo = st.checkbox("Incluir columna 'periodo' (demo del comparativo)", True, key="p_periodo")

# --- Resolver la fuente de cada conjunto de datos ---------------------------
df_sim, df5s_sim = cargar_simulados(int(semilla), int(n_pesadas), bool(demo_periodo))
mensajes: list[tuple[str, str]] = []   # (nivel, texto)

df_pes, pes_real = df_sim, False
if archivo_pes is not None:
    d, msgs = cargar_csv(archivo_pes.getvalue(), "pesadas")
    if d is None:
        mensajes.append(("error", f"No se pudo usar «{archivo_pes.name}»: " + " ".join(msgs) +
                         " Se muestran datos simulados."))
    else:
        df_pes, pes_real = d, True
        mensajes += [("warning", m) for m in msgs]

df_5s, s5_real = df5s_sim, False
if archivo_5s is not None:
    d, msgs = cargar_csv(archivo_5s.getvalue(), "5s")
    if d is None:
        mensajes.append(("error", f"No se pudo usar «{archivo_5s.name}»: " + " ".join(msgs) +
                         " Se muestran auditorías simuladas."))
    else:
        df_5s, s5_real = d, True
        mensajes += [("warning", m) for m in msgs]

df_pes = kpis.enriquecer_pesadas(df_pes, tol_global if usar_tol_global else None)

# ---------------------------------------------------------------------------
# Filtros (en st.session_state). Se reinician si cambia la fuente de datos.
# ---------------------------------------------------------------------------
fecha_min = min(df_pes["fecha"].min(), df_5s["fecha"].min()).date()
fecha_max = max(df_pes["fecha"].max(), df_5s["fecha"].max()).date()
firma = (pes_real, s5_real, archivo_pes.name if archivo_pes else None,
         archivo_5s.name if archivo_5s else None, int(semilla), int(n_pesadas), str(fecha_min), str(fecha_max))


def reiniciar_filtros():
    """Restablece los filtros a 'todos' y al rango completo de fechas."""
    st.session_state["f_fechas"] = (fecha_min, fecha_max)
    for k in ("f_turno", "f_producto", "f_ingrediente", "f_operario"):
        st.session_state[k] = []


if st.session_state.get("firma_datos") != firma:
    st.session_state["firma_datos"] = firma
    reiniciar_filtros()

st.sidebar.markdown("### 🔎 Filtros")
st.sidebar.date_input("Rango de fechas", min_value=fecha_min, max_value=fecha_max, key="f_fechas",
                      format="DD/MM/YYYY")
opciones = lambda col: sorted(df_pes[col].dropna().unique().tolist())  # noqa: E731
st.sidebar.multiselect("Turno", opciones("turno"), key="f_turno", placeholder="Todos")
st.sidebar.multiselect("Producto", opciones("producto"), key="f_producto", placeholder="Todos")
st.sidebar.multiselect("Ingrediente", opciones("ingrediente"), key="f_ingrediente", placeholder="Todos")
st.sidebar.multiselect("Operario (código)", opciones("operario_codigo"), key="f_operario", placeholder="Todos")
st.sidebar.button("↺ Restablecer filtros", on_click=reiniciar_filtros, width="stretch")

rango = st.session_state["f_fechas"]
f_ini, f_fin = (rango[0], rango[1]) if isinstance(rango, (tuple, list)) and len(rango) == 2 else \
    ((rango[0], rango[0]) if isinstance(rango, (tuple, list)) and rango else (fecha_min, fecha_max))

df = kpis.aplicar_filtros(df_pes, f_ini, f_fin, st.session_state["f_turno"], st.session_state["f_producto"],
                          st.session_state["f_ingrediente"], st.session_state["f_operario"])
df5 = kpis.filtrar_5s(df_5s, f_ini, f_fin, st.session_state["f_turno"])

# ---------------------------------------------------------------------------
# Encabezado y aviso de datos ilustrativos
# ---------------------------------------------------------------------------
st.markdown("# DOSI-4.0 · Monitoreo de la estación de pesaje de micro-ingredientes")
st.markdown('<div class="subtitulo">Prototipo Poka-Yoke + IoT + auditoría 5S digital · Planta de alimentos '
            'balanceados (piloto, 2 turnos) · Operarios identificados solo por código</div>',
            unsafe_allow_html=True)

if not (pes_real and s5_real):
    cuales = ("pesadas y auditoría 5S" if not pes_real and not s5_real
              else "pesadas" if not pes_real else "auditoría 5S")
    st.markdown(f'<div class="aviso">⚠ {cfg.AVISO_ILUSTRATIVO}'
                f'<small>Conjunto simulado: {cuales}. Generado con semilla fija solo para demostrar el '
                f'funcionamiento del tablero; no debe citarse como evidencia de mejora.</small></div>',
                unsafe_allow_html=True)

for nivel, texto in mensajes:
    getattr(st, nivel)(texto)

if df.empty:
    st.info("🔍 Ningún registro cumple con los filtros seleccionados. Amplía el rango de fechas o "
            "quita alguno de los filtros (botón «Restablecer filtros» en la barra lateral).")
    st.stop()

# ---------------------------------------------------------------------------
# Fila de KPIs
# ---------------------------------------------------------------------------
k = kpis.calcular_kpis(df, df5)
estado, color_sem = kpis.semaforo(k["puntaje_5s"], umbral_verde, umbral_ambar)
c1, c2, c3, c4, c5 = st.columns(5)
tarjeta(c1, "Total de pesadas", f"{k['total']:,}".replace(",", " "),
        f"{df['lote'].nunique()} lotes · {df['fecha'].nunique()} días", kpis.DEFINICIONES["total"])
tarjeta(c2, "Pesadas dentro de tolerancia", fmt(k["pct_dentro_tol"], "{:.1f} %"),
        f"{int(df['dentro_tolerancia'].sum())} de {k['total']}", kpis.DEFINICIONES["dentro_tol"])
tarjeta(c3, "Errores detectados por el Poka-Yoke", fmt(k["pct_deteccion"], "{:.1f} %", "Sin errores"),
        f"{k['n_detectados']} de {k['n_errores']} errores · tasa de error {fmt(k['tasa_error'], '{:.1f} %')}",
        kpis.DEFINICIONES["deteccion"])
tarjeta(c4, "Tiempo medio de ciclo", fmt(k["tiempo_ciclo_medio"], "{:.1f} s"),
        "por pesada", kpis.DEFINICIONES["ciclo"])
tarjeta(c5, "Puntaje 5S global", fmt(k["puntaje_5s"], "{:.1f}"),
        f'<span class="pildora" style="background:{color_sem}">● {estado}</span> · {len(df5)} auditorías',
        kpis.DEFINICIONES["5s"].format(v=umbral_verde, a=umbral_ambar, v1=umbral_verde - 1), color_sem)

st.write("")

# ---------------------------------------------------------------------------
# Pestañas de análisis
# ---------------------------------------------------------------------------
t1, t2, t3, t4, t5, t6 = st.tabs(["📈 Control del peso", "📊 Errores por tipo", "⏱ Tendencias",
                                  "🧹 Auditoría 5S", "⚖ Antes vs. después", "📋 Datos y alertas"])

with t1:
    un_ingrediente = df["ingrediente"].nunique() == 1
    st.plotly_chart(graficos.grafico_control(df, en_kg=un_ingrediente), width="stretch")
    st.caption("Rombos rojos = pesadas fuera de tolerancia. "
               + ("Eje en kg porque hay un solo ingrediente filtrado." if un_ingrediente else
                  "Con varios ingredientes el eje muestra la desviación % = (real − objetivo) / objetivo × 100; "
                  "si las tolerancias difieren, se expresa como % de la tolerancia (±100 % = límite). "
                  "Filtra un solo ingrediente para verlo en kg.")
               + " Usa la barra inferior o arrastra para hacer zoom.")
    st.markdown("#### 🚨 Alertas recientes (últimas 10 con ALERTA o BLOQUEO)")
    alertas = kpis.alertas_recientes(df, 10)
    if alertas.empty:
        st.success("No hay pesadas con ALERTA o BLOQUEO en el filtro actual.")
    else:
        def _color_resultado(v):
            return f"background-color: {cfg.COLORES_RESULTADO.get(v, 'white')}; color: white; font-weight: 700"
        estilo = (alertas.style.map(_color_resultado, subset=["resultado_poka_yoke"])
                  .format({"fecha_hora": lambda x: x.strftime("%d/%m/%Y %H:%M"), "peso_objetivo_kg": "{:.3f}",
                           "peso_real_kg": "{:.3f}", "desviacion_pct": "{:+.2f} %"}))
        st.dataframe(estilo, hide_index=True, width="stretch",
                     column_config={"fecha_hora": "Fecha y hora", "turno": "Turno", "producto": "Producto",
                                    "ingrediente": "Ingrediente", "lote": "Lote", "operario_codigo": "Operario",
                                    "peso_objetivo_kg": "Objetivo (kg)", "peso_real_kg": "Real (kg)",
                                    "desviacion_pct": "Desviación", "resultado_poka_yoke": "Resultado",
                                    "tipo_error": "Tipo de error"})

with t2:
    comparar = st.toggle("Comparar turnos", value=False, key="cmp_turnos")
    conteo = kpis.errores_por_tipo(df, por_turno=comparar)
    if conteo["errores"].sum() == 0:
        st.plotly_chart(graficos.figura_vacia("Sin errores registrados en el filtro actual",
                                              "Errores de dosificación por tipo"), width="stretch")
    else:
        st.plotly_chart(graficos.grafico_errores_tipo(conteo, comparar), width="stretch")
    st.caption("Se cuentan las pesadas con tipo_error distinto de «Ninguno», hayan sido detectadas o no.")

with t3:
    por = st.radio("Agrupar por", ["día", "turno"], horizontal=True, key="agrupar_serie",
                   format_func=lambda x: "Día" if x == "día" else "Día y turno")
    st.plotly_chart(graficos.grafico_serie_tiempo(kpis.serie_temporal(df, por), por), width="stretch")
    st.caption("Tasa de error = pesadas con error ÷ pesadas del periodo × 100. "
               "Tiempo de ciclo = promedio de tiempo_ciclo_s.")

with t4:
    if df5.empty:
        st.info("No hay auditorías 5S en el rango de fechas y turnos seleccionados.")
    else:
        a, b = st.columns(2)
        a.plotly_chart(graficos.grafico_radar_5s(kpis.resumen_5s(df5), umbral_verde), width="stretch")
        b.plotly_chart(graficos.grafico_evolucion_5s(kpis.evolucion_5s(df5), umbral_verde, umbral_ambar),
                       width="stretch")
        st.caption("Puntaje global = promedio simple de Seiri, Seiton, Seiso, Seiketsu y Shitsuke (0-100). "
                   "La auditoría 5S solo responde a los filtros de fecha y turno.")

with t5:
    comp = kpis.comparativo_periodos(df, df5)
    if comp is None:
        st.info("ℹ️ El archivo de pesadas no tiene la columna **periodo** (valores «antes» / «después»), "
                "por lo que no se puede construir el comparativo.")
    else:
        if not pes_real:
            st.warning("Comparativo construido con datos simulados: solo demuestra el gráfico, "
                       "no es evidencia de mejora.")
        st.plotly_chart(graficos.grafico_comparativo(comp), width="stretch")
        tabla = comp.assign(periodo=comp["periodo"].str.capitalize()).rename(columns={"periodo": "Periodo", "pesadas": "Pesadas", "errores": "Errores",
                                     "tasa_error_pct": "Tasa de error (%)",
                                     "tiempo_ciclo_medio_s": "Ciclo medio (s)", "puntaje_5s": "Puntaje 5S"})
        st.dataframe(tabla.round(2), hide_index=True, width="stretch")

with t6:
    st.markdown("#### Registro detallado de pesadas")
    f1, f2 = st.columns([2, 3])
    res_sel = f1.multiselect("Resultado Poka-Yoke", ["OK", "ALERTA", "BLOQUEO"], key="tabla_res",
                             placeholder="Todos")
    texto = f2.text_input("Buscar (lote, ingrediente, producto, tipo de error)", key="tabla_buscar")
    tabla = df.copy()
    if res_sel:
        tabla = tabla[tabla["resultado_poka_yoke"].isin(res_sel)]
    if texto:
        patron = texto.strip().lower()
        m = pd.Series(False, index=tabla.index)
        for col in ("lote", "ingrediente", "producto", "tipo_error"):
            m |= tabla[col].astype(str).str.lower().str.contains(patron, regex=False)
        tabla = tabla[m]
    columnas = cfg.COLUMNAS_PESADAS + (["periodo"] if "periodo" in tabla.columns else []) + \
        ["desviacion_pct", "dentro_tolerancia"]
    tabla = tabla[columnas].sort_values("fecha_hora", ascending=False)
    st.caption(f"{len(tabla)} registros · haz clic en el encabezado de una columna para ordenar.")
    st.dataframe(tabla, hide_index=True, width="stretch", height=440,
                 column_config={
                     "fecha_hora": st.column_config.DatetimeColumn("Fecha y hora", format="DD/MM/YYYY HH:mm"),
                     "peso_objetivo_kg": st.column_config.NumberColumn("Objetivo (kg)", format="%.3f"),
                     "peso_real_kg": st.column_config.NumberColumn("Real (kg)", format="%.3f"),
                     "tolerancia_pct": st.column_config.NumberColumn("Tol. (%)", format="%.1f"),
                     "desviacion_pct": st.column_config.NumberColumn("Desviación (%)", format="%+.2f"),
                     "tiempo_ciclo_s": st.column_config.NumberColumn("Ciclo (s)", format="%.1f"),
                     "dentro_tolerancia": st.column_config.CheckboxColumn("Dentro de tol."),
                 })
    csv = tabla.assign(fecha_hora=tabla["fecha_hora"].dt.strftime("%Y-%m-%d %H:%M:%S")) \
        .to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇ Descargar datos filtrados (CSV)", csv, file_name="dosi40_pesadas_filtradas.csv",
                       mime="text/csv", disabled=tabla.empty)
    with st.expander("Formato esperado de los CSV"):
        st.markdown("**Pesadas:** " + ", ".join(f"`{c}`" for c in cfg.COLUMNAS_PESADAS) +
                    " · opcional `periodo` (antes/después).  \n**Auditoría 5S:** " +
                    ", ".join(f"`{c}`" for c in cfg.COLUMNAS_5S) + " (0-100) · opcional `periodo`.  \n"
                    "Separador `,` o `;`; se acepta coma decimal.")

st.divider()
st.caption("DOSI-4.0 · Prototipo académico · Indicadores calculados en modules/kpis.py · "
           "Sin nombres reales de personas ni de la empresa.")
