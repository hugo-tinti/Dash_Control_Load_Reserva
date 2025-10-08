# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import warnings
import matplotlib.colors as colors
import unicodedata
import logging
from pathlib import Path
from typing import Dict, List, Optional
import functools
import io
import seaborn as sns

# =========================
# SUPRESIÓN DE WARNINGS
# =========================
warnings.filterwarnings('ignore')

# =========================
# CONFIGURACIÓN DE PÁGINA Y TEMA
# =========================
st.set_page_config(
    page_title="Análisis Agudo-Crónico CAI",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Paleta y tema general (consistente entre Matplotlib y Plotly)
PALETA = {
    "fondo_fig": "#ffffff",
    "fondo_axes": "#f8f9fa",
    "grid": "#e9ecef",
    "grid_light": "#f1f3f5",
    "texto": "#212529",
    "borde": "#495057",
    "titulo": "#1a1d29",
    "subtitulo": "#495057",
    "sombra": "#00000025",
    "bar_borde": "#343a40",
    "rojo": "#b22222",
    "rojo_claro": "rgba(178,34,34,0.8)",
    "azul": "#20639b",
    "azul_line": "rgba(32,99,155,1.0)",
    "azul_claro": "rgba(30,144,255,0.6)",
    "azul_borde": "rgba(30,144,255,1.0)",
    "amarillo": "#DAA520",
    "gris": "#6c757d",
    "gris_suave": "#e9ecef",
    "verde_area": "rgba(0,128,0,0.10)",
    "amarillo_area": "rgba(255,215,0,0.12)",
    "rojo_area": "rgba(220,20,60,0.08)"
}

# Ajustes Matplotlib y Seaborn
plt.rcParams.update({
    "axes.facecolor": PALETA["fondo_axes"],
    "figure.facecolor": PALETA["fondo_fig"],
    "axes.edgecolor": PALETA["borde"],
    "axes.labelcolor": PALETA["titulo"],
    "xtick.color": PALETA["texto"],
    "ytick.color": PALETA["texto"],
    "grid.color": PALETA["grid"],
    "grid.linestyle": "--",
    "grid.alpha": 0.7,
    "axes.titleweight": "bold",
    "axes.titlepad": 14,
    "axes.spines.top": False,
    "axes.spines.right": False,
})
sns.set_theme(context="talk", style="whitegrid")

# =========================
# CONFIGURACIÓN GLOBAL
# =========================

CONFIG_ANALISIS = {
    'rutas': {
        # Cambiado a ruta relativa, el archivo Excel debe estar en la misma carpeta que el script
        'archivo_principal': 'GpsDataBase.xlsx',
        'archivo_20w': 'GpsDataBase.xlsx'
    },
    'columnas': {
        'fecha': 'Fecha',
        'jugador': 'Atleta',
        'turno': 'Turno',
        'md': 'MD'
    },
    'jugadores_excluir': [
        "Alan Laprida",
        "Alexis Canelo",
        "Braian Martinez",
        "Jhony Quiñones",
        "Juan Manuel Fedorco"
    ],
    'variables_analisis': [
        'Distancia Total',
        'Tot +16',
        'Dis +25',
        'Mts Acc +3',
        'Mts Dcc -3',
        'Pot Met +20 Mts',
        'Pot Met +55 Mts',
    ],
    'acr_thresholds': {
        'low': 0.8,
        'high': 1.3
    },
    'ratio_axis_max': 2.5,
    'años_analisis': [2024, 2025],
    'estilo_visual': {
        'figura_facecolor': PALETA["fondo_fig"],
        'axes_facecolor': PALETA["fondo_axes"],
        'grid_color': PALETA["grid"],
        'grid_alpha': 0.8,
        'grid_linewidth': 1.2,
        'spine_color': PALETA["borde"],
        'spine_linewidth': 2.2,
        'texto_color': PALETA["texto"],
        'borde_color': PALETA["bar_borde"],
        'sombra_color': PALETA["sombra"],
        'titulo_color': PALETA["titulo"],
        'subtitulo_color': PALETA["subtitulo"]
    }
}

# =========================
# LOGGING
# =========================
def configurar_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger(__name__)

logger = configurar_logging()

def log_operacion(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger.info(f"Iniciando: {func.__name__}")
        try:
            resultado = func(*args, **kwargs)
            logger.info(f"Completado exitosamente: {func.__name__}")
            return resultado
        except Exception as e:
            logger.error(f"Error en {func.__name__}: {e}")
            raise
    return wrapper

# =========================
# CARGA DE DATOS
# =========================
@st.cache_data(show_spinner=False)
def cargar_datos():
    """Carga los datos del archivo Excel"""
    try:
        df_CAI_Reserva = CONFIG_ANALISIS['rutas']['archivo_principal']
        df = pd.read_excel(df_CAI_Reserva)

        if 'Fecha' in df.columns:
            df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
            df = df.dropna(subset=['Fecha'])

        return df
    except Exception as e:
        st.error(f"Error al cargar los datos: {e}")
        return None

# =========================
# VALIDACIÓN Y GESTIÓN
# =========================
class ValidadorDatos:
    @staticmethod
    def validar_archivo_existe(file_path: str) -> bool:
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")
        return True

    @staticmethod
    def validar_columnas_requeridas(df: pd.DataFrame, columnas_requeridas: List[str]) -> List[str]:
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        if columnas_faltantes:
            logger.warning(f"Columnas faltantes: {columnas_faltantes}")
        return columnas_faltantes

    @staticmethod
    def validar_datos_no_vacios(df: pd.DataFrame, columnas_criticas: List[str]) -> Dict[str, int]:
        columnas_vacias = {}
        for col in columnas_criticas:
            if col in df.columns:
                nulos = df[col].isna().sum()
                if nulos == len(df):
                    columnas_vacias[col] = nulos
                    logger.warning(f"Columna completamente vacía: {col}")
        return columnas_vacias

class GestorDatos:
    def __init__(self, config: Dict):
        self.config = config
        self.validador = ValidadorDatos()

    @log_operacion
    def cargar_datos_seguros(self, file_path: str) -> Optional[pd.DataFrame]:
        try:
            self.validador.validar_archivo_existe(file_path)
            df = pd.read_excel(file_path)
            logger.info(f"Datos cargados: {len(df)} filas desde {file_path}")
            columnas_requeridas = list(self.config['columnas'].values())
            self.validador.validar_columnas_requeridas(df, columnas_requeridas)
            self.validador.validar_datos_no_vacios(df, columnas_requeridas)
            return df
        except Exception as e:
            logger.error(f"Error al cargar datos desde {file_path}: {e}")
            return None


    @log_operacion
    def procesar_dataset_unificado(self, df: pd.DataFrame, es_dataset_20w: bool = False, fecha_limite: pd.Timestamp = None) -> Dict:
        if df is None:
            logger.error("DataFrame es None, no se puede procesar")
            return {}

        col_fecha = self.config['columnas']['fecha']
        col_jugador = self.config['columnas']['jugador']
        col_turno = self.config['columnas']['turno']

        df[col_fecha] = pd.to_datetime(df[col_fecha])

        if fecha_limite is not None:
            df = df[df[col_fecha] <= fecha_limite]

        datos_por_año = {}
        for año in self.config['años_analisis']:
            df_año = df[df[col_fecha].dt.year == año]
            df_año = df_año[~df_año[col_jugador].isin(self.config['jugadores_excluir'])]
            datos_por_año[año] = df_año

        if len(df) == 0 or all(len(v) == 0 for v in datos_por_año.values()):
            return {}

        df_actual = datos_por_año[max(self.config['años_analisis'])]
        if len(df_actual) == 0:
            years_with_data = [a for a, d in datos_por_año.items() if len(d) > 0]
            if not years_with_data:
                return {}
            df_actual = datos_por_año[max(years_with_data)]

        last_date = df_actual[col_fecha].max()
        last_day_data = df_actual[df_actual[col_fecha] == last_date].copy()
        last_day_data['TurnoNorm'] = last_day_data[col_turno].apply(self._normalizar_turno)
        ultimo_entrenamiento = self._obtener_ultimo_entrenamiento(last_day_data, col_turno)
        info_entrenamiento = self._extraer_info_entrenamiento(ultimo_entrenamiento, last_date)
        jugadores_unicos = sorted(ultimo_entrenamiento[self.config['columnas']['jugador']].dropna().astype(str).unique())
        entrenamiento_unico = ultimo_entrenamiento.groupby(col_jugador, as_index=False).mean(numeric_only=True)

        return {
            'datos_por_año': datos_por_año,
            'ultimo_entrenamiento': ultimo_entrenamiento,
            'info_entrenamiento': info_entrenamiento,
            'jugadores_unicos': jugadores_unicos,
            'entrenamiento_unico': entrenamiento_unico,
            'es_dataset_20w': es_dataset_20w,
            'last_date': last_date
        }

    def _normalizar_turno(self, turno) -> str:
        if pd.isna(turno):
            return ""
        turno = str(turno).strip().upper()
        turno = ''.join(c for c in unicodedata.normalize('NFD', turno) if unicodedata.category(c) != 'Mn')
        if turno in ['M', 'MANANA', 'AM', 'MAÑANA']:
            return 'M'
        elif turno in ['T', 'TARDE', 'PM']:
            return 'T'
        else:
            return turno

    def _obtener_ultimo_entrenamiento(self, last_day_data: pd.DataFrame, col_turno: str) -> pd.DataFrame:
        if len(last_day_data) == 0:
            return last_day_data
        if (last_day_data['TurnoNorm'] == 'T').any():
            return last_day_data[last_day_data['TurnoNorm'] == 'T']
        elif (last_day_data['TurnoNorm'] == 'M').any():
            return last_day_data[last_day_data['TurnoNorm'] == 'M']
        else:
            return last_day_data

    def _extraer_info_entrenamiento(self, entrenamiento: pd.DataFrame, fecha: pd.Timestamp) -> Dict:
        if len(entrenamiento) == 0:
            return {}
        turno_val = entrenamiento.iloc[0][self.config['columnas']['turno']]
        turno_norm = self._normalizar_turno(turno_val)
        turno_str = "Mañana" if turno_norm == 'M' else ("Tarde" if turno_norm == 'T' else str(turno_val))
        dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        dia_semana = dias_semana[fecha.dayofweek]

        md_info = ""
        col_md = self.config['columnas'].get('md', 'MD')
        if col_md in entrenamiento.columns:
            md_val = entrenamiento.iloc[0][col_md]
            if not pd.isna(md_val):
                md_info = f" | MD: {md_val}"

        return {
            'fecha': fecha,
            'dia_semana': dia_semana,
            'turno': turno_str,
            'md_info': md_info
        }

# =========================
# CÁLCULOS ACR y GRÁFICOS
# =========================
def _ensure_numeric_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors='coerce')

def _weeks_from_days(days: int) -> int:
    return max(int(round(days / 7)), 1)

def calcular_ewma_semanal(player_data, variable, acute_span=7, chronic_span=21):
    """Calcula EWMA semanal y ratio agudo:crónico para un jugador con suma de lunes a domingo."""
    if player_data is None or len(player_data) == 0:
        return None
    if variable not in player_data.columns:
        return None

    dfp = player_data.copy()
    dfp = dfp.sort_values('Fecha').reset_index(drop=True)
    dfp[variable] = _ensure_numeric_series(dfp[variable])
    dfp = dfp.dropna(subset=[variable])
    dfp = dfp[dfp[variable] >= 0]

    if len(dfp) == 0:
        return None

    dfp['semana'] = dfp['Fecha'].dt.to_period('W-SUN')

    weekly_load = dfp.groupby('semana').agg({
        variable: 'sum',
        'Fecha': 'max'
    }).reset_index()

    weekly_load.rename(columns={
        variable: f'{variable}_load_semanal',
        'Fecha': 'fecha_cierre_semana'
    }, inplace=True)

    acute_weeks = _weeks_from_days(acute_span)
    chronic_weeks = _weeks_from_days(chronic_span)

    if len(weekly_load) < max(acute_weeks, chronic_weeks):
        return None

    weekly_load['acute'] = weekly_load[f'{variable}_load_semanal'].ewm(span=acute_weeks, adjust=False).mean()
    weekly_load['chronic'] = weekly_load[f'{variable}_load_semanal'].ewm(span=chronic_weeks, adjust=False).mean()

    weekly_load['acr_ratio'] = np.where(
        weekly_load['chronic'] > 0,
        weekly_load['acute'] / weekly_load['chronic'],
        np.nan
    )

    return weekly_load

def crear_grafico_ewma_semanal(weekly_data, player_name, variable, low_thr=0.8, high_thr=1.3, ratio_axis_max=2.5):
    """Crea gráfico EWMA semanal con eje Y dual mostrando suma semanal de metros y ACR."""
    if weekly_data is None or len(weekly_data) == 0:
        return None

    fig = go.Figure()

    # Barras: Carga semanal total
    fig.add_trace(go.Bar(
        x=weekly_data['fecha_cierre_semana'],
        y=weekly_data[f'{variable}_load_semanal'],
        name=f'Carga Semanal Total ({variable})',
        marker_color=PALETA["azul_claro"],
        marker_line=dict(color=PALETA["azul_borde"], width=1),
        opacity=0.95,
        yaxis='y',
        hovertemplate='<b>Semana:</b> %{x|%d/%m/%Y}<br><b>Carga Total:</b> %{y:.0f} m<extra></extra>'
    ))

    # Línea: ACR
    fig.add_trace(go.Scatter(
        x=weekly_data['fecha_cierre_semana'],
        y=weekly_data['acr_ratio'],
        mode='lines+markers',
        name='Ratio Agudo:Crónico',
        line=dict(color='crimson', width=3),
        marker=dict(size=8, color='crimson', line=dict(width=1, color='white')),
        yaxis='y2',
        hovertemplate='<b>Semana:</b> %{x|%d/%m/%Y}<br><b>ACR:</b> %{y:.2f}<extra></extra>'
    ))

    # Layout
    fig.update_layout(
        title=f"Análisis ACR Semanal: {player_name}<br><sup>Suma Semanal (Lunes-Domingo) - {variable}</sup>",
        xaxis=dict(
            title="Fecha de Cierre de Semana (Domingo)",
            type='date',
            tickformat='%d/%m/%Y',
            tickangle=0,
            showgrid=True,
            gridcolor=PALETA["grid_light"]
        ),
        yaxis=dict(
            title=f"Carga Semanal Total - {variable} (m)",
            showgrid=True,
            gridcolor=PALETA["grid"]
        ),
        yaxis2=dict(
            title="Ratio ACR",
            overlaying='y',
            side='right',
            showgrid=False,
            range=[0, ratio_axis_max]
        ),
        hovermode='x unified',
        height=620,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            bgcolor="rgba(255,255,255,0.6)",
            bordercolor=PALETA["borde"], borderwidth=1
        ),
        plot_bgcolor=PALETA["fondo_fig"],
        paper_bgcolor=PALETA["fondo_fig"],
        margin=dict(l=50, r=50, t=80, b=50)
    )

    # Bandas de riesgo ACR
    fig.add_hline(y=low_thr, line_dash="dash", line_color="orange", opacity=0.9,
                  annotation_text=f"Carga Baja ({low_thr})", annotation_position="right", yref='y2')
    fig.add_hline(y=high_thr, line_dash="dash", line_color="red", opacity=0.9,
                  annotation_text=f"Alto Riesgo ({high_thr})", annotation_position="right", yref='y2')

    # Sombras de zonas
    fig.add_shape(type="rect", xref="paper", yref="y2", x0=0, y0=low_thr, x1=1, y1=high_thr,
                  fillcolor=PALETA["verde_area"], opacity=1.0, layer="below", line_width=0)
    fig.add_shape(type="rect", xref="paper", yref="y2", x0=0, y0=0, x1=1, y1=low_thr,
                  fillcolor=PALETA["amarillo_area"], opacity=1.0, layer="below", line_width=0)
    fig.add_shape(type="rect", xref="paper", yref="y2", x0=0, y0=high_thr, x1=1, y1=ratio_axis_max,
                  fillcolor=PALETA["rojo_area"], opacity=1.0, layer="below", line_width=0)

    return fig

def obtener_atletas_criticos(df, variable, low_thr=0.8, high_thr=1.3, acute_span=7, chronic_span=21):
    """Obtiene atletas con ratios críticos según umbrales configurables."""
    atletas_criticos = []

    if df is None or len(df) == 0 or variable not in df.columns:
        return pd.DataFrame([])

    for atleta in df['Atleta'].dropna().unique():
        player_data = df[df['Atleta'] == atleta].copy()
        weekly_ewma = calcular_ewma_semanal(player_data, variable, acute_span, chronic_span)
        if weekly_ewma is not None and len(weekly_ewma) > 0:
            ultimo_ratio = weekly_ewma['acr_ratio'].iloc[-1]
            if not pd.isna(ultimo_ratio):
                if ultimo_ratio > high_thr:
                    atletas_criticos.append({
                        'Atleta': atleta,
                        'Último_Ratio': float(ultimo_ratio),
                        'Estado': '🚨 ALTO RIESGO',
                        'Color': 'red'
                    })
                elif ultimo_ratio < low_thr:
                    atletas_criticos.append({
                        'Atleta': atleta,
                        'Último_Ratio': float(ultimo_ratio),
                        'Estado': '⚠️ CARGA BAJA',
                        'Color': 'orange'
                    })

    return pd.DataFrame(atletas_criticos).sort_values('Último_Ratio', ascending=False)

# =========================
# VISUALIZACIONES AVANZADAS (BARRAS COMPARATIVAS)
# =========================
class GeneradorVisualizaciones:
    def __init__(self, config: Dict):
        self.config = config

    def crear_colormap_profesional(self, color_base: str, intensidad: float = 1.0):
        if color_base == 'rojo':
            if intensidad < 0.3:
                color_inicio = np.array([1.0, 0.65, 0.65])
                color_medio = np.array([0.95, 0.15, 0.15])
                color_final = np.array([0.60, 0.00, 0.00])
            elif intensidad < 0.6:
                color_inicio = np.array([0.95, 0.25, 0.25])
                color_medio = np.array([0.85, 0.10, 0.10])
                color_final = np.array([0.45, 0.00, 0.00])
            else:
                color_inicio = np.array([0.85, 0.06, 0.06])
                color_medio = np.array([0.65, 0.00, 0.00])
                color_final = np.array([0.30, 0.00, 0.00])
            positions = [0.0, 0.65, 1.0]
            colors_list = [color_inicio, color_medio, color_final]
        elif color_base == 'azul':
            color_inicio = np.array([0.25, 0.55, 1.0])
            color_medio = np.array([0.10, 0.25, 0.85])
            color_final = np.array([0.00, 0.00, 0.35])
            positions = [0.0, 0.5, 1.0]
            colors_list = [color_inicio, color_medio, color_final]
        elif color_base == 'amarillo':
            if intensidad > 0.5:
                color_inicio = np.array([1.0, 0.95, 0.60])
                color_medio = np.array([0.85, 0.75, 0.25])
                color_final = np.array([0.45, 0.25, 0.05])
            else:
                color_inicio = np.array([1.0, 0.98, 0.90])
                color_medio = np.array([0.95, 0.85, 0.35])
                color_final = np.array([0.85, 0.65, 0.05])
            positions = [0.0, 0.75, 1.0]
            colors_list = [color_inicio, color_medio, color_final]
        else:
            color_inicio = np.array([0.85, 0.85, 0.85])
            color_medio = np.array([0.6, 0.6, 0.6])
            color_final = np.array([0.35, 0.35, 0.35])
            positions = [0.0, 0.6, 1.0]
            colors_list = [color_inicio, color_medio, color_final]

        cmap = colors.LinearSegmentedColormap.from_list(
            'custom',
            list(zip(positions, colors_list)) if len(positions) > 2 else colors_list
        )
        return cmap

    def aplicar_gradiente_profesional(self, ax, bar, color_base: str, intensidad: float = 1.0):
        bar.set_facecolor("none")
        bar.set_zorder(3)
        x, y = bar.get_xy()
        width = bar.get_width()
        height = bar.get_height()

        # Sombra
        sombra_offset = width * 0.03
        ax.add_patch(plt.Rectangle(
            (x + sombra_offset, y - sombra_offset),
            width, height,
            facecolor=self.config['estilo_visual']['sombra_color'],
            zorder=1, alpha=0.45
        ))

        # Gradiente
        if color_base in ['rojo', 'amarillo']:
            gradient_points = np.concatenate([np.linspace(0, 0.6, 400), np.linspace(0.6, 1.0, 500)])
        else:
            gradient_points = np.linspace(0, 1, 800)

        gradient = gradient_points.reshape(-1, 1)
        cmap = self.crear_colormap_profesional(color_base, intensidad)

        ax.imshow(gradient, extent=[x, x+width, y, y+height],
                  aspect='auto', cmap=cmap, zorder=2, alpha=0.95,
                  interpolation='bicubic')

        ax.add_patch(plt.Rectangle(
            (x, y), width, height,
            facecolor="none",
            edgecolor=self.config['estilo_visual']['borde_color'],
            linewidth=2.0, alpha=0.9, zorder=4
        ))

class AnalizadorEntrenamientos:
    def __init__(self, config: Dict):
        self.config = config
        self.gestor_datos = GestorDatos(config)
        self.visualizador = GeneradorVisualizaciones(config)

    def ejecutar_analisis_comparativo(self, df, fecha_limite=None):
        """Ejecuta análisis comparativo para Streamlit con filtro de fecha"""
        if df is None:
            st.error("No se pudieron cargar los datos")
            return

        datos_principal = self.gestor_datos.procesar_dataset_unificado(df, False, fecha_limite)
        if not datos_principal:
            st.error("No se pudieron procesar los datos")
            return

        if fecha_limite:
            st.info(f"Mostrando análisis hasta la fecha: {fecha_limite.strftime('%d/%m/%Y')}")

        for variable in self.config['variables_analisis']:
            if variable in df.columns:
                st.subheader(f"📊 {variable}")
                self._analizar_variable_streamlit(variable, datos_principal)
                st.markdown("---")

    def _analizar_variable_streamlit(self, variable: str, datos: Dict):
        """Analiza una variable específica para Streamlit"""
        try:
            data, pestañas = self._preparar_datos_analisis(variable, datos)
            fig = self._generar_grafico_profesional_streamlit(variable, data, datos['info_entrenamiento'], pestañas)
            if fig:
                st.pyplot(fig, use_container_width=True)
                plt.close(fig)
        except Exception as e:
            st.error(f"Error al procesar {variable}: {e}")

    def _preparar_datos_analisis(self, variable: str, datos: Dict):
        col_jugador = self.config['columnas']['jugador']
        col_fecha = self.config['columnas']['fecha']
        col_turno = self.config['columnas']['turno']

        turno_actual = datos['info_entrenamiento']['turno']
        tipo_turno = self.gestor_datos._normalizar_turno(turno_actual)
        fecha_actual = datos['last_date']

        data = pd.DataFrame({col_jugador: datos['jugadores_unicos']})
        data = data.set_index(col_jugador)

        valores_ultimo = datos['entrenamiento_unico'].set_index(col_jugador)[variable] if variable in datos['entrenamiento_unico'].columns else pd.Series(dtype=float)
        data['valor'] = valores_ultimo.reindex(data.index)

        historico_total = pd.concat([datos['datos_por_año'][año] for año in self.config['años_analisis']], axis=0)
        historico_total = historico_total.copy()
        historico_total['TurnoNorm'] = historico_total[col_turno].apply(self.gestor_datos._normalizar_turno)

        mean_total = historico_total.groupby(col_jugador)[variable].mean(numeric_only=True)
        std_total = historico_total.groupby(col_jugador)[variable].std(numeric_only=True)

        data['mean'] = mean_total.reindex(data.index)
        data['std'] = std_total.reindex(data.index)

        data['z'] = np.where(
            (data['std'] > 0) & (~data['valor'].isna()) & (~data['mean'].isna()),
            (data['valor'] - data['mean']) / data['std'],
            np.nan
        )

        pestañas = {}
        for jugador in data.index:
            mask = (
                (historico_total[col_jugador] == jugador) &
                (historico_total['TurnoNorm'] == tipo_turno) &
                (historico_total[col_fecha] < fecha_actual)
            )
            ultimos = historico_total[mask].sort_values(col_fecha, ascending=False).head(4)
            if len(ultimos) > 0:
                pestañas[jugador] = {
                    'media3w': ultimos[variable].mean(),
                    'std3w': ultimos[variable].std()
                }
            else:
                pestañas[jugador] = {'media3w': np.nan, 'std3w': np.nan}

        return data.sort_values('z', ascending=False, na_position='last'), pestañas

    def _generar_grafico_profesional_streamlit(self, variable: str, data: pd.DataFrame, info_entrenamiento: Dict, pestañas: Dict):
        """Genera gráfico profesional optimizado para Streamlit"""
        fig, ax1 = plt.subplots(figsize=(18, 10))
        fig.patch.set_facecolor(self.config['estilo_visual']['figura_facecolor'])

        x = np.arange(len(data.index))
        bars = ax1.bar(
            x, data['valor'],
            edgecolor=self.config['estilo_visual']['borde_color'],
            width=0.48, zorder=5, alpha=0.98, linewidth=1.8
        )

        # Aplicar gradiente según z-score
        for i, (idx, row) in enumerate(data.iterrows()):
            bar = bars[i]
            if pd.isna(row['valor']) or pd.isna(row['mean']) or pd.isna(row['std']) or row['std'] == 0:
                self.visualizador.aplicar_gradiente_profesional(ax1, bar, 'gris', 0.5)
            elif row['z'] > 1:
                intensidad_roja = min((row['z'] - 1) / 0.8, 1.0)
                self.visualizador.aplicar_gradiente_profesional(ax1, bar, 'rojo', intensidad_roja)
            elif row['z'] < -1:
                intensidad_azul = min(abs(row['z'] + 1) / 0.8, 1.0)
                self.visualizador.aplicar_gradiente_profesional(ax1, bar, 'azul', intensidad_azul)
            else:
                diferencia_relativa = abs(row['valor'] - row['mean']) / row['mean'] if (row['mean'] is not None and not pd.isna(row['mean']) and row['mean'] != 0) else 0
                if row['valor'] > row['mean']:
                    intensidad_amarilla = 0.65 + min(diferencia_relativa * 3, 0.35)
                else:
                    intensidad_amarilla = max(0.15, 0.45 - diferencia_relativa * 2)
                self.visualizador.aplicar_gradiente_profesional(ax1, bar, 'amarillo', intensidad_amarilla)

        # Límites de eje Y (considerando barras, bandas y bigotes)
        max_bar_value = (data['valor'].max() if not data['valor'].isna().all() else 0)
        max_std_value = ((data['mean'] + data['std']).max(skipna=True) if not (data[['mean','std']].isna().all().all()) else 0)
        max_3w = max([
            (pest['media3w'] + pest['std3w'])
            for pest in pestañas.values()
            if not pd.isna(pest['media3w']) and not pd.isna(pest['std3w'])
        ] + [0])
        y_max_limit = max(max_bar_value, max_std_value, max_3w) * 1.15 if max(max_bar_value, max_std_value, max_3w) > 0 else 1

        self._configurar_grafico_profesional(ax1, data, variable, info_entrenamiento, bars, pestañas, y_max_limit)
        plt.tight_layout(rect=[0, 0.15, 1, 0.97])

        # Leyenda custom
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#8b1f1a', edgecolor='#495057', linewidth=1.5,
                  label='🔴 SOBRECARGA (+1 STD) - Recuperación/Diferenciado'),
            Patch(facecolor='#DAA520', edgecolor='#495057', linewidth=1.5,
                  label='🟡 RANGO NORMAL (±1 STD) - Carga Óptima'),
            Patch(facecolor='#20639b', edgecolor='#495057', linewidth=1.5,
                  label='🔵 SUBCARGA (-1 STD) - Revisar Intensidad'),
            Patch(facecolor='#6c757d', edgecolor='#495057', linewidth=1.5,
                  label='⚪ SIN HISTÓRICO - Datos Insuficientes'),
            Patch(facecolor='none', edgecolor='black', linewidth=4,
                  label='μ₄ y ±σ₄: Media y desvío últimas 4 sesiones mismo turno')
        ]
        fig.legend(
            handles=legend_elements,
            loc='lower right',
            bbox_to_anchor=(0.995, 0.020),
            fontsize=9, frameon=True, fancybox=True, shadow=False, framealpha=0.95, edgecolor='#495057',
            ncol=1
        )
        return fig

    def _configurar_grafico_profesional(self, ax, data, variable, info_entrenamiento, bars, pestañas, y_max_limit):
        estilo = self.config['estilo_visual']
        titulo = (
            f"{variable} - Comparación Actual vs Histórico\n"
            f"Día: {info_entrenamiento.get('dia_semana', '')} | "
            f"Turno: {info_entrenamiento.get('turno', '')} | "
            f"Fecha: {info_entrenamiento.get('fecha', ''):%d/%m/%Y}"
            f"{info_entrenamiento.get('md_info', '')}"
        )

        ax.set_title(titulo, fontsize=18, weight='bold', color=estilo['titulo_color'], pad=18)
        ax.set_ylabel(variable, fontsize=14, weight='bold', color=estilo['titulo_color'], labelpad=12)
        ax.set_xlabel('JUGADORES', fontsize=14, weight='bold', color=estilo['titulo_color'], labelpad=15)

        ax.set_xticks(np.arange(len(data.index)))
        ax.set_xticklabels(data.index, rotation=90, fontsize=11, weight='bold', color=estilo['texto_color'])
        ax.set_ylim(0, y_max_limit)

        # Spines
        for spine in ax.spines.values():
            spine.set_color(estilo['spine_color'])
            spine.set_linewidth(estilo['spine_linewidth'])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Grid
        ax.grid(True, linestyle='--', alpha=estilo['grid_alpha'],
                color=estilo['grid_color'], linewidth=estilo['grid_linewidth'])
        ax.set_axisbelow(True)

        # Bandas de histórico ±1 STD y media
        for i, jugador in enumerate(data.index):
            m = data.loc[jugador, 'mean']
            s = data.loc[jugador, 'std']

            if not pd.isna(m) and not pd.isna(s):
                ax.fill_between([i-0.5, i+0.5], max(m-s, 0), m+s, color=PALETA["gris_suave"], alpha=0.75, zorder=0)
                ax.plot([i-0.5, i+0.5], [m, m], color='#dc3545', linestyle='--', linewidth=2.4, zorder=1, alpha=0.95)
                ax.plot([i-0.5, i+0.5], [m+s, m+s], color=PALETA["gris"], linestyle=':', linewidth=2.0, zorder=1, alpha=0.85)
                ax.plot([i-0.5, i+0.5], [max(m-s, 0), max(m-s, 0)], color=PALETA["gris"], linestyle=':', linewidth=2.0, zorder=1, alpha=0.85)

            # Bigotes μ4 ± σ4
            pest = pestañas.get(jugador, {})
            m4 = pest.get('media3w', np.nan)
            s4 = pest.get('std3w', np.nan)
            if not pd.isna(m4) and not pd.isna(s4):
                y_bot = max(m4 - s4, 0)
                y_top = m4 + s4
                x_centro = i
                ax.plot([x_centro, x_centro], [y_bot, y_top], color='black', linewidth=3, zorder=15)
                ax.plot([x_centro-0.18, x_centro+0.18], [m4, m4], color='black', linewidth=3, zorder=16)
                label_fontsize = 10
                if m4 >= 0:
                    ax.text(x_centro+0.22, m4, 'μ₄', va='center', ha='left', fontsize=label_fontsize, color='black', weight='bold', zorder=17)
                if y_top >= 0:
                    ax.text(x_centro+0.22, y_top, '+σ₄', va='center', ha='left', fontsize=label_fontsize, color='black', weight='bold', zorder=17)
                if y_bot > 0:
                    ax.text(x_centro+0.22, y_bot, '-σ₄', va='center', ha='left', fontsize=label_fontsize, color='black', weight='bold', zorder=17)

        # Etiquetas de valor, media y z-score
        for i, (bar, valor) in enumerate(zip(bars, data['valor'])):
            if not np.isnan(valor):
                x_text = bar.get_x() + bar.get_width() / 2
                y_text = bar.get_height()
                media = data['mean'].iloc[i]
                zscore = data['z'].iloc[i]
                media_disp = int(round(media)) if not pd.isna(media) else 0
                z_disp = f"{zscore:.2f}" if not pd.isna(zscore) else "NA"

                texto = f'{int(round(valor))}\nμ={media_disp}\nz={z_disp}'
                ax.text(
                    x_text, y_text + y_max_limit*0.018,
                    texto,
                    ha='center', va='bottom', fontsize=8.5, weight='bold',
                    color=PALETA["texto"], zorder=6
                )

# =========================
# FUNCIÓN PRINCIPAL DE ANÁLISIS COMPARATIVO
# =========================
def ejecutar_analisis_comparativo_streamlit(df, fecha_limite=None):
    """Función principal para ejecutar el análisis en Streamlit"""
    analizador = AnalizadorEntrenamientos(CONFIG_ANALISIS)
    analizador.ejecutar_analisis_comparativo(df, fecha_limite)

# =========================
# UI: CABECERA
# =========================
st.title("⚽ Análisis Agudo-Crónico - Club Atlético Independiente")
st.caption("Monitoreo Semanal: Suma de Carga (Lunes-Domingo) y Ratio ACR")
st.markdown("---")

# =========================
# SIDEBAR CONTROLES GLOBALES
# =========================
st.sidebar.header("⚙️ Parámetros de Análisis")
with st.sidebar:
    st.markdown("Ajusta spans y umbrales para aplicar a todo el dashboard.")

    # Spans EWMA (en días)
    acute_span_days = st.number_input(
        "Agudo (días)",
        min_value=7, max_value=28, value=7, step=7,
        help="Ventana EWMA aguda en días; la carga se agrupa por semanas."
    )
    chronic_span_days = st.number_input(
        "Crónico (días)",
        min_value=14, max_value=56, value=21, step=7,
        help="Ventana EWMA crónica en días; la carga se agrupa por semanas."
    )

    # Umbrales ACR
    low_thr = st.slider(
        "Umbral bajo ACR", min_value=0.5, max_value=1.0,
        value=float(CONFIG_ANALISIS['acr_thresholds']['low']), step=0.05
    )
    high_thr = st.slider(
        "Umbral alto ACR", min_value=1.1, max_value=2.5,
        value=float(CONFIG_ANALISIS['acr_thresholds']['high']), step=0.05
    )

    # Rango máximo eje ACR
    ratio_axis_max = st.slider(
        "Máximo eje ACR", min_value=1.5, max_value=4.0,
        value=float(CONFIG_ANALISIS['ratio_axis_max']), step=0.1
    )

    # Filtro por fecha global
    st.markdown("---")
    st.subheader("Filtro por Fecha")
    usar_filtro_fecha_global = st.checkbox("Activar filtro de fecha global", value=False)
    fecha_limite_global = None

# =========================
# CARGAR DATOS
# =========================
df = cargar_datos()

if df is not None:
    # Filtro de fecha global
    if usar_filtro_fecha_global and 'Fecha' in df.columns and len(df) > 0:
        fecha_min = df['Fecha'].min().date()
        fecha_max = df['Fecha'].max().date()
        with st.sidebar:
            fecha_limite_picker = st.date_input(
                "Analizar datos hasta la fecha (global):",
                value=fecha_max, min_value=fecha_min, max_value=fecha_max, key="fecha_limite_global"
            )
        fecha_limite_global = pd.Timestamp(fecha_limite_picker)
        st.info(f"Filtro global activo. Analizando datos hasta: {fecha_limite_global.strftime('%d/%m/%Y')}")
    else:
        st.info("Sin filtro de fecha global - analizando todos los datos disponibles.")
        fecha_limite_global = None

    # Variables disponibles para análisis
    variables_analisis = [
        'Distancia Total',
        'Tot +16',
        'Dis +25',
        'Mts Acc +3',
        'Mts Dcc -3',
        'Pot Met +20 Mts',
        'Pot Met +55 Mts'
    ]
    variables_disponibles = [var for var in variables_analisis if var in df.columns]

    if len(variables_disponibles) == 0:
        st.error("❌ No se encontraron las variables de análisis en los datos")
        st.info(f"Columnas disponibles: {list(df.columns)}")
    else:
        # Tabs: variables + comparativo avanzado
        tab_names = variables_disponibles + ['analisis_avanzado']
        tabs = st.tabs([f"📊 {v}" if v != 'analisis_avanzado' else '📈 Análisis Comparativo Avanzado' for v in tab_names])

        # Tabs individuales por variable
        for i, variable in enumerate(variables_disponibles):
            with tabs[i]:
                st.subheader(f"📊 Análisis: {variable}")
                st.caption("Carga semanal = Suma de metros de lunes a domingo")

                col1, col2 = st.columns([2, 1])

                # Columna derecha: críticos y estadísticas
                with col2:
                    st.markdown("### 🚨 Atletas en Situación Crítica")

                    atletas_criticos = obtener_atletas_criticos(
                        df if fecha_limite_global is None else df[df['Fecha'] <= fecha_limite_global],
                        variable,
                        low_thr=low_thr,
                        high_thr=high_thr,
                        acute_span=acute_span_days,
                        chronic_span=chronic_span_days
                    )

                    if len(atletas_criticos) > 0:
                        st.markdown("Atletas que requieren atención:")
                        for _, row in atletas_criticos.iterrows():
                            if row['Color'] == 'red':
                                st.error(f"🚨 {row['Atleta']} - Ratio: {row['Último_Ratio']:.2f}")
                            else:
                                st.warning(f"⚠️ {row['Atleta']} - Ratio: {row['Último_Ratio']:.2f}")

                        # Tabla resumen
                        st.dataframe(
                            atletas_criticos[['Atleta', 'Último_Ratio', 'Estado']],
                            use_container_width=True
                        )

                        # Descargar CSV
                        csv_buf = io.StringIO()
                        atletas_criticos.to_csv(csv_buf, index=False)
                        st.download_button(
                            label="Descargar críticos (CSV)",
                            data=csv_buf.getvalue(),
                            file_name=f"criticos_{variable.replace(' ','_')}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.success("✅ Todos los atletas en rangos normales")

                    # Estadísticas globales
                    st.markdown("### 📈 Estadísticas Generales")
                    atletas_con_datos = 0
                    total_ratios_criticos = 0

                    df_eval = df if fecha_limite_global is None else df[df['Fecha'] <= fecha_limite_global]
                    for atleta in df_eval['Atleta'].dropna().unique():
                        player_data = df_eval[df_eval['Atleta'] == atleta].copy()
                        weekly_ewma = calcular_ewma_semanal(player_data, variable, acute_span_days, chronic_span_days)
                        if weekly_ewma is not None and len(weekly_ewma) > 0:
                            atletas_con_datos += 1
                            ultimo_ratio = weekly_ewma['acr_ratio'].iloc[-1]
                            if not pd.isna(ultimo_ratio) and (ultimo_ratio > high_thr or ultimo_ratio < low_thr):
                                total_ratios_criticos += 1

                    met1, met2, met3 = st.columns(3)
                    with met1:
                        st.metric("Atletas analizables", atletas_con_datos, help="Número de atletas con suficiente historial para calcular ACR.")
                    with met2:
                        st.metric("Atletas en situación crítica", total_ratios_criticos, help="Atletas con ACR fuera de los umbrales establecidos.")
                    with met3:
                        pct_criticos = (total_ratios_criticos / max(atletas_con_datos, 1) * 100) if atletas_con_datos > 0 else 0
                        st.metric("% Atletas críticos", f"{pct_criticos:.1f}%", help="Proporción de atletas con ACR alto o bajo.")

                # Columna izquierda: selector y gráfico
                with col1:
                    atletas_disponibles = ['Seleccionar atleta...'] + sorted(df['Atleta'].dropna().unique().tolist())
                    atleta_seleccionado = st.selectbox(
                        f"Seleccionar atleta para {variable}:",
                        options=atletas_disponibles,
                        key=f"atleta_{variable}"
                    )

                    if atleta_seleccionado != 'Seleccionar atleta...':
                        df_plot = df if fecha_limite_global is None else df[df['Fecha'] <= fecha_limite_global]
                        player_data = df_plot[df_plot['Atleta'] == atleta_seleccionado].copy()

                        weekly_ewma = calcular_ewma_semanal(player_data, variable, acute_span_days, chronic_span_days)

                        if weekly_ewma is not None:
                            ultimo_ratio = weekly_ewma['acr_ratio'].iloc[-1]
                            ultimo_load = weekly_ewma[f'{variable}_load_semanal'].iloc[-1]
                            promedio_agudo = weekly_ewma['acute'].iloc[-1]
                            promedio_cronico = weekly_ewma['chronic'].iloc[-1]

                            met_col1, met_col2, met_col3, met_col4 = st.columns(4)
                            with met_col1:
                                st.metric("Última Carga Semanal", f"{ultimo_load:.0f} m",
                                          help="Suma total de metros de lunes a domingo.")
                            with met_col2:
                                st.metric(f"EWMA Agudo ({acute_span_days}d)", f"{promedio_agudo:.0f} m",
                                          help=f"Promedio exponencial equivalente a ~{_weeks_from_days(acute_span_days)} semanas.")
                            with met_col3:
                                st.metric(f"EWMA Crónico ({chronic_span_days}d)", f"{promedio_cronico:.0f} m",
                                          help=f"Promedio exponencial equivalente a ~{_weeks_from_days(chronic_span_days)} semanas.")
                            with met_col4:
                                if ultimo_ratio > high_thr:
                                    st.metric("Ratio ACR", f"{ultimo_ratio:.2f}", delta="Alto Riesgo", delta_color="inverse",
                                              help="Ratio Agudo:Crónico por encima del umbral alto.")
                                elif ultimo_ratio < low_thr:
                                    st.metric("Ratio ACR", f"{ultimo_ratio:.2f}", delta="Carga Baja", delta_color="inverse",
                                              help="Ratio Agudo:Crónico por debajo del umbral bajo.")
                                else:
                                    st.metric("Ratio ACR", f"{ultimo_ratio:.2f}", delta="Normal", delta_color="normal",
                                              help="Ratio Agudo:Crónico dentro de los umbrales.")

                            fig = crear_grafico_ewma_semanal(
                                weekly_ewma, atleta_seleccionado, variable,
                                low_thr=low_thr, high_thr=high_thr, ratio_axis_max=ratio_axis_max
                            )
                            if fig:
                                st.plotly_chart(fig, use_container_width=True, theme=None)

                                st.markdown("### 💡 Recomendaciones")
                                if ultimo_ratio > high_thr:
                                    st.error("🚨 ALTO RIESGO: Reducir y dosificar la carga semanal. Enfatizar recuperación.")
                                elif ultimo_ratio < low_thr:
                                    st.warning("⚠️ CARGA INSUFICIENTE: Progresar carga con foco en calidad y tolerancia.")
                                else:
                                    st.success("✅ ZONA ÓPTIMA: Mantener carga y micro-ajustar según respuesta individual.")

                                st.markdown("### 📋 Datos Semanales Recientes")
                                datos_recientes = weekly_ewma[[
                                    'fecha_cierre_semana',
                                    f'{variable}_load_semanal',
                                    'acute',
                                    'chronic',
                                    'acr_ratio'
                                ]].tail(12).copy()

                                datos_recientes['fecha_cierre_semana'] = datos_recientes['fecha_cierre_semana'].dt.strftime('%d/%m/%Y')
                                datos_recientes = datos_recientes.round(2)
                                datos_recientes.columns = [
                                    'Semana (Cierre)',
                                    f'Carga Total {variable} (m)',
                                    f'EWMA Agudo ({_weeks_from_days(acute_span_days)}w)',
                                    f'EWMA Crónico ({_weeks_from_days(chronic_span_days)}w)',
                                    'Ratio ACR'
                                ]
                                st.dataframe(datos_recientes, use_container_width=True)

                                csv_buf2 = io.StringIO()
                                datos_recientes.to_csv(csv_buf2, index=False)
                                st.download_button(
                                    label="Descargar datos semanales (CSV)",
                                    data=csv_buf2.getvalue(),
                                    file_name=f"semanal_{atleta_seleccionado.replace(' ','_')}_{variable.replace(' ','_')}.csv",
                                    mime="text/csv"
                                )
                        else:
                            st.warning(f"❌ No hay suficientes datos para analizar a {atleta_seleccionado} en {variable}")
                            st.info("Se requieren al menos 21 días de datos para el análisis")

        # Pestaña: 📈 Análisis Comparativo Avanzado
        with tabs[-1]:
            st.subheader("📈 Análisis Comparativo Avanzado")
            df_filtrado = df if fecha_limite_global is None else df[df['Fecha'] <= fecha_limite_global]
            ejecutar_analisis_comparativo_streamlit(df_filtrado, fecha_limite=fecha_limite_global)
