"""
config.py — Parámetros por defecto del dashboard DOSI-4.0.

Todos los valores pueden modificarse aquí o, durante la exposición,
desde el panel "Parámetros" de la barra lateral.
"""

# ---------------------------------------------------------------------------
# Datos simulados
# ---------------------------------------------------------------------------
SEMILLA = 42                 # semilla fija -> los datos simulados son reproducibles
N_PESADAS = 500              # número aproximado de pesadas simuladas
DIAS_SIMULADOS = 56          # 8 semanas de operación simulada
FECHA_INICIO = "2026-08-03"  # lunes de inicio de la simulación

TURNOS = ["Mañana", "Tarde"]
PRODUCTOS = ["BIO AVEMIX PLUS", "NUTRIMAX", "CORIMIX", "PICO DE ACERO"]
OPERARIOS = ["OP-01", "OP-02", "OP-03", "OP-04", "OP-05", "OP-06"]

# Micro-ingredientes: nombre -> (peso objetivo base en kg, tolerancia %)
INGREDIENTES = {
    "Premix vitamínico": (2.50, 2.0),
    "Premix mineral": (3.00, 2.0),
    "DL-Metionina": (1.80, 1.5),
    "L-Lisina HCl": (2.20, 1.5),
    "Coccidiostato": (0.50, 1.0),
    "Sal industrial": (4.00, 3.0),
    "Antioxidante": (0.25, 1.0),
    "Enzima fitasa": (0.10, 1.0),
}

# ---------------------------------------------------------------------------
# Semáforo 5S (puntaje 0-100)
# ---------------------------------------------------------------------------
UMBRAL_VERDE = 85   # verde  >= 85
UMBRAL_AMBAR = 70   # ámbar  70-84 ; rojo < 70

# ---------------------------------------------------------------------------
# Paleta (consistente en KPIs y gráficos)
# ---------------------------------------------------------------------------
COLOR_VERDE = "#2E7D32"
COLOR_AMBAR = "#E0A100"
COLOR_ROJO = "#C62828"
COLOR_PRIMARIO = "#1F4E79"   # azul institucional sobrio
COLOR_SECUNDARIO = "#7A9CC6"
COLOR_GRIS = "#6B7280"
COLOR_FONDO_TARJETA = "#F5F7FA"

COLORES_RESULTADO = {"OK": COLOR_VERDE, "ALERTA": COLOR_AMBAR, "BLOQUEO": COLOR_ROJO}
COLORES_TURNO = {"Mañana": COLOR_PRIMARIO, "Tarde": COLOR_SECUNDARIO}
COLORES_PERIODO = {"antes": COLOR_GRIS, "después": COLOR_PRIMARIO}

# ---------------------------------------------------------------------------
# Esquema de los CSV
# ---------------------------------------------------------------------------
COLUMNAS_PESADAS = [
    "fecha_hora", "turno", "producto", "ingrediente", "lote", "operario_codigo",
    "peso_objetivo_kg", "peso_real_kg", "tolerancia_pct", "resultado_poka_yoke",
    "tipo_error", "tiempo_ciclo_s", "estado_estacion",
]
COLUMNAS_5S = ["fecha", "turno", "seiri", "seiton", "seiso", "seiketsu", "shitsuke"]
COLUMNAS_S = ["seiri", "seiton", "seiso", "seiketsu", "shitsuke"]

TIPOS_ERROR = [
    "Ingrediente equivocado", "Sobrepeso", "Subpeso", "Secuencia", "Lote no autorizado",
]
SIN_ERROR = "Ninguno"

AVISO_ILUSTRATIVO = "DATOS ILUSTRATIVOS, NO SON RESULTADOS DE VALIDACIÓN"
