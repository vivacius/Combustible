import streamlit as st
import pandas as pd
import io
import matplotlib.pyplot as plt
import seaborn as sns

# ===============================
# FUNCIONES AUXILIARES CON CACHÉ
# ===============================

@st.cache_data
def cargar_datos(file_abastecimientos, file_horas):
    """Carga y devuelve los DataFrames desde los archivos subidos."""
    abastecimientos = pd.read_excel(file_abastecimientos)
    horas_trabajadas = pd.read_excel(file_horas, dtype={'Código Equipo': object})
    return abastecimientos, horas_trabajadas

@st.cache_data
def procesar_datos(abastecimientos, horas_trabajadas):
    """Procesa los datos para calcular galones por hora trabajada."""
    abastecimientos_agrupados = abastecimientos.groupby(['Código Equipo', 'Fecha Consumo']).agg({
        'Cantidad': 'sum'
    }).reset_index()

    horas_trabajadas_agrupadas = horas_trabajadas.groupby(['Código Equipo', 'Fecha']).agg({
        'Duracion (horas)': 'sum'
    }).reset_index()

    abastecimientos_agrupados = abastecimientos_agrupados.rename(
        columns={'Fecha Consumo': 'Fecha', 'Cantidad': 'Galones'}
    )
    horas_trabajadas_agrupadas = horas_trabajadas_agrupadas.rename(
        columns={'Duracion (horas)': 'Horas Trabajadas'}
    )

    resultados = []
    equipos = abastecimientos_agrupados['Código Equipo'].unique()

    for equipo in equipos:
        datos_abastecimiento = abastecimientos_agrupados[
            abastecimientos_agrupados['Código Equipo'] == equipo
        ].sort_values('Fecha')

        datos_horas = horas_trabajadas_agrupadas[
            horas_trabajadas_agrupadas['Código Equipo'] == equipo
        ]

        for i in range(len(datos_abastecimiento) - 1):
            fila_actual = datos_abastecimiento.iloc[i]
            fila_siguiente = datos_abastecimiento.iloc[i + 1]
            fecha_inicio = fila_actual['Fecha']
            fecha_fin = fila_siguiente['Fecha']
            horas_intervalo = datos_horas[
                (datos_horas['Fecha'] > fecha_inicio) & (datos_horas['Fecha'] <= fecha_fin)
            ]
            horas_trabajadas_total = horas_intervalo['Horas Trabajadas'].sum()
            galones_intervalo = fila_actual['Galones']

            resultados.append({
                'Código Equipo': equipo,
                'Fecha Inicio': fecha_inicio,
                'Fecha Fin': fecha_fin,
                'Horas Trabajadas': horas_trabajadas_total,
                'Galones': galones_intervalo,
                'Galones por Hora': galones_intervalo / horas_trabajadas_total if horas_trabajadas_total > 0 else 0
            })

    return pd.DataFrame(resultados)

def descargar_resultado(df, nombre_archivo, etiqueta):
    """Permite descargar un DataFrame en Excel."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Resultados')
    buffer.seek(0)
    st.download_button(
        label=f"📥 Descargar {etiqueta}",
        data=buffer,
        file_name=nombre_archivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ===============================
# INTERFAZ STREAMLIT
# ===============================

st.set_page_config(page_title="Consumo de Combustible", layout="wide")
st.title("⛽ Seguimiento de Consumo Gal/Hora en Equipos")

# Tabs principales
tab1, tab2 = st.tabs(["⚙️ Procesamiento", "📊 Visualización"])

# -------------------------------
# TAB 1: PROCESAMIENTO
# -------------------------------
with tab1:
    st.header("⚙️ Procesamiento de datos")

    file_abastecimientos = st.file_uploader("📂 Sube el archivo de Abastecimientos", type=["xlsx"], key="abastecimientos")
    file_horas = st.file_uploader("📂 Sube el archivo de Horas Trabajadas", type=["xlsx"], key="horas")
    file_clasificacion = st.file_uploader("📂 Sube el archivo de Clasificación de Equipos", type=["xlsx", "csv"], key="clasificacion")

    if file_abastecimientos and file_horas:
        st.info("📥 Cargando archivos...")
        abastecimientos, horas_trabajadas = cargar_datos(file_abastecimientos, file_horas)

        # Limpieza
        abastecimientos = abastecimientos[abastecimientos['Código Equipo'].astype(str).str.match(r'^\d+$')]
        abastecimientos['Código Equipo'] = abastecimientos['Código Equipo'].astype(int)
        horas_trabajadas['Código Equipo'] = horas_trabajadas['Código Equipo'].astype(int)

        # Fechas
        abastecimientos['Fecha Consumo'] = pd.to_datetime(abastecimientos['Fecha Consumo'], format='%d/%m/%Y')
        horas_trabajadas['Fecha'] = pd.to_datetime(horas_trabajadas['Fecha'], format='%d/%m/%Y %I:%M %p')

        # Procesar con caché
        df_resultados = procesar_datos(abastecimientos, horas_trabajadas)

        # --- Enriquecer con clasificación ---
        if file_clasificacion:
            if file_clasificacion.name.endswith(".csv"):
                clasificacion = pd.read_csv(file_clasificacion)
            else:
                clasificacion = pd.read_excel(file_clasificacion)

            clasificacion['EQUIPO3'] = clasificacion['EQUIPO3'].astype(int)
            df_resultados = df_resultados.merge(clasificacion[['EQUIPO3', 'ZONA']], 
                                                left_on='Código Equipo', right_on='EQUIPO3', how='left')
            df_resultados['ZONA'] = df_resultados['ZONA'].fillna("OTROS FRENTES")
            df_resultados.drop(columns=['EQUIPO3'], inplace=True)

        st.success("✅ ¡Datos procesados con éxito!")
        st.dataframe(df_resultados)

        descargar_resultado(df_resultados, "Resultado_final.xlsx", "archivo Excel de resultados")

        # Guardar en sesión para Tab 2
        st.session_state['df_resultados'] = df_resultados
        st.session_state['horas_trabajadas'] = horas_trabajadas

# -------------------------------
# TAB 2: VISUALIZACIÓN
# -------------------------------
with tab2:
    st.header("📊 Visualización y Análisis")

    if 'df_resultados' in st.session_state:
        df_resultados = st.session_state['df_resultados']
        horas_trabajadas = st.session_state['horas_trabajadas']

        # 🔹 Filtro por zona
        zonas = df_resultados['ZONA'].unique()
        zonas_sel = st.multiselect("🌍 Filtrar por ZONA", zonas, default=zonas)
        df_resultados = df_resultados[df_resultados['ZONA'].isin(zonas_sel)]

        # Agregar columna Mes
        df_viz = df_resultados.copy()
        df_viz['Mes'] = df_viz['Fecha Inicio'].dt.to_period('M').dt.to_timestamp()

        # --- Resumen con año y actividad dominante ---
        resumen = df_viz.groupby(['Código Equipo', 'Mes']).agg(
            media_consumo=('Galones por Hora', 'mean'),
            desviacion=('Galones por Hora', 'std'),
            registros=('Galones por Hora', 'count')
        ).reset_index()

        resumen['Año'] = resumen['Mes'].dt.year

        if "Nombre Actividad" in horas_trabajadas.columns:
            horas_actividad = horas_trabajadas.copy()
            horas_actividad['Mes'] = horas_actividad['Fecha'].dt.to_period('M').dt.to_timestamp()

            actividad_dominante = (
                horas_actividad.groupby(['Código Equipo', 'Mes', 'Nombre Actividad'])
                .agg(horas_totales=('Duracion (horas)', 'sum'))
                .reset_index()
            )

            actividad_dominante = (
                actividad_dominante.sort_values(['Código Equipo', 'Mes', 'horas_totales'], ascending=[True, True, False])
                .groupby(['Código Equipo', 'Mes'])
                .first()
                .reset_index()[['Código Equipo', 'Mes', 'Nombre Actividad', 'horas_totales']]
            )
            actividad_dominante = actividad_dominante.rename(columns={
                'Nombre Actividad': 'Actividad Dominante',
                'horas_totales': 'Horas Actividad Dominante'
            })

            resumen = resumen.merge(actividad_dominante, on=['Código Equipo', 'Mes'], how='left')

        # ======================
        # 📊 KPIs del último mes
        # ======================
        if not resumen.empty:
            ultimo_mes = resumen['Mes'].max()
            resumen_mes = resumen[resumen['Mes'] == ultimo_mes]

            top_mejores = resumen_mes.nsmallest(5, 'media_consumo')
            top_peores = resumen_mes.nlargest(5, 'media_consumo')

            st.subheader(f"🏆 Top equipos – {ultimo_mes.strftime('%B %Y')}")
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("✅ **Más eficientes (menor gal/hora)**")
                st.table(top_mejores[['Código Equipo', 'media_consumo', 'Actividad Dominante']].round(2))

            with col2:
                st.markdown("⚠️ **Menos eficientes (mayor gal/hora)**")
                st.table(top_peores[['Código Equipo', 'media_consumo', 'Actividad Dominante']].round(2))

        # --- Gráfico de tendencia ---
        st.subheader("📈 Tendencia mensual por equipo")
        equipos = resumen['Código Equipo'].unique()
        if len(equipos) > 0:
            equipo_sel = st.selectbox("Selecciona un equipo", equipos)
            df_equipo = resumen[resumen['Código Equipo'] == equipo_sel]

            fig, ax = plt.subplots(figsize=(8,4))
            ax.plot(df_equipo['Mes'], df_equipo['media_consumo'], marker='o', label="Media Gal/hora")
            if not df_equipo['desviacion'].isnull().all():
                ax.fill_between(df_equipo['Mes'],
                                df_equipo['media_consumo'] - df_equipo['desviacion'],
                                df_equipo['media_consumo'] + df_equipo['desviacion'],
                                alpha=0.2, label="±1 Desv.Est.")
            ax.set_title(f"Consumo mensual Equipo {equipo_sel}")
            ax.set_ylabel("Gal/hora")
            ax.legend()
            st.pyplot(fig)

        # --- Boxplot limpio y dinámico ---
        st.subheader("📦 Distribución de consumo (Boxplot)")
        modo = st.radio("Modo de visualización", ["Todos los equipos", "Un equipo específico"])
        fig2, ax2 = plt.subplots(figsize=(10,5))

        if modo == "Todos los equipos":
            sns.boxplot(data=df_viz, x='Mes', y='Galones por Hora', ax=ax2, color="lightblue")
            sns.stripplot(data=df_viz, x='Mes', y='Galones por Hora', ax=ax2, color='red', alpha=0.5, jitter=0.2)
            ax2.set_title("Distribución mensual de consumo (Todos los equipos)")
        else:
            equipo_box = st.selectbox("Selecciona equipo para boxplot", df_viz['Código Equipo'].unique())
            df_equipo_box = df_viz[df_viz['Código Equipo'] == equipo_box]
            sns.boxplot(data=df_equipo_box, x='Mes', y='Galones por Hora', ax=ax2, color="lightgreen")
            sns.stripplot(data=df_equipo_box, x='Mes', y='Galones por Hora', ax=ax2, color='red', alpha=0.6, jitter=0.2)
            ax2.set_title(f"Distribución mensual de consumo – Equipo {equipo_box}")

        ax2.set_ylabel("Gal/hora")
        st.pyplot(fig2)

        # --- Descargar resumen ---
        descargar_resultado(resumen, "Resumen_Mensual.xlsx", "resumen mensual")

    else:
        st.warning("⚠️ Primero procesa los datos en la pestaña 'Procesamiento'.")


