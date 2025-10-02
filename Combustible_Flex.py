import streamlit as st
import pandas as pd
import io
import time
import matplotlib.pyplot as plt
import seaborn as sns

# ===============================
# FUNCIONES AUXILIARES
# ===============================

def cargar_datos(file_abastecimientos, file_horas):
    abastecimientos = pd.read_excel(file_abastecimientos)
    horas_trabajadas = pd.read_excel(file_horas, dtype={'Código Equipo': object})
    return abastecimientos, horas_trabajadas

def limpiar_datos(abastecimientos, horas_trabajadas):
    # Eliminar códigos que empiezan por letras
    abastecimientos = abastecimientos[abastecimientos['Código Equipo'].astype(str).str.match(r'^\d+$')]
    
    # Convertir Código Equipo a numérico
    abastecimientos['Código Equipo'] = abastecimientos['Código Equipo'].astype(int)
    horas_trabajadas['Código Equipo'] = horas_trabajadas['Código Equipo'].astype(int)

    # Convertir fechas
    abastecimientos['Fecha Consumo'] = pd.to_datetime(abastecimientos['Fecha Consumo'], format='%d/%m/%Y')
    horas_trabajadas['Fecha'] = pd.to_datetime(horas_trabajadas['Fecha'], format='%d/%m/%Y %I:%M %p')

    return abastecimientos, horas_trabajadas

def procesar_datos(abastecimientos, horas_trabajadas, barra_progreso, estado_texto):
    abastecimientos_agrupados = abastecimientos.groupby(['Código Equipo', 'Fecha Consumo']).agg({
        'Cantidad': 'sum'
    }).reset_index()

    horas_trabajadas_agrupadas = horas_trabajadas.groupby(['Código Equipo', 'Fecha']).agg({
        'Duracion (horas)': 'sum'
    }).reset_index()

    abastecimientos_agrupados = abastecimientos_agrupados.rename(columns={'Fecha Consumo': 'Fecha', 'Cantidad': 'Galones'})
    horas_trabajadas_agrupadas = horas_trabajadas_agrupadas.rename(columns={'Duracion (horas)': 'Horas Trabajadas'})

    resultados = []
    equipos = abastecimientos_agrupados['Código Equipo'].unique()
    total = len(equipos)

    for idx, equipo in enumerate(equipos):
        datos_abastecimiento = abastecimientos_agrupados[abastecimientos_agrupados['Código Equipo'] == equipo].sort_values('Fecha')
        datos_horas = horas_trabajadas_agrupadas[horas_trabajadas_agrupadas['Código Equipo'] == equipo]

        for i in range(len(datos_abastecimiento) - 1):
            fila_actual = datos_abastecimiento.iloc[i]
            fila_siguiente = datos_abastecimiento.iloc[i + 1]
            fecha_inicio = fila_actual['Fecha']
            fecha_fin = fila_siguiente['Fecha']
            horas_intervalo = datos_horas[(datos_horas['Fecha'] > fecha_inicio) & (datos_horas['Fecha'] <= fecha_fin)]
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

        # Actualizar barra de progreso
        progreso = (idx + 1) / total
        barra_progreso.progress(progreso)
        estado_texto.text(f"⏳ Procesando equipo {equipo} ({idx + 1}/{total})")

    return pd.DataFrame(resultados)

def descargar_resultado(df, nombre_archivo, etiqueta):
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

    if file_abastecimientos and file_horas:
        st.info("📥 Cargando archivos...")
        abastecimientos, horas_trabajadas = cargar_datos(file_abastecimientos, file_horas)

        st.info("🧹 Limpiando y preparando los datos...")
        abastecimientos, horas_trabajadas = limpiar_datos(abastecimientos, horas_trabajadas)

        barra_progreso = st.progress(0)
        estado_texto = st.empty()

        st.info("⚙️ Procesando información...")
        df_resultados = procesar_datos(abastecimientos, horas_trabajadas, barra_progreso, estado_texto)

        barra_progreso.empty()
        estado_texto.text("✅ Procesamiento completado")

        st.success("✅ ¡Datos procesados con éxito!")
        st.dataframe(df_resultados)

        descargar_resultado(df_resultados, "Resultado_final.xlsx", "archivo Excel de resultados")

        # Guardar en sesión para usar en Tab 2
        st.session_state['df_resultados'] = df_resultados
        st.session_state['horas_trabajadas'] = horas_trabajadas

# -------------------------------
# TAB 2: VISUALIZACIÓN
# -------------------------------
with tab2:
    st.header("📊 Visualización y Análisis")

    if 'df_resultados' in st.session_state and 'horas_trabajadas' in st.session_state:
        df_resultados = st.session_state['df_resultados']
        horas_trabajadas = st.session_state['horas_trabajadas']

        df_viz = df_resultados.copy()
        df_viz['Mes'] = df_viz['Fecha Inicio'].dt.to_period('M').dt.to_timestamp()

        # --- Actividad dominante con Nombre Actividad ---
        horas_actividad = horas_trabajadas.copy()
        horas_actividad['Mes'] = horas_actividad['Fecha'].dt.to_period('M').dt.to_timestamp()

        if "Nombre Actividad" in horas_actividad.columns:
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
        else:
            actividad_dominante = pd.DataFrame(columns=['Código Equipo','Mes','Actividad Dominante','Horas Actividad Dominante'])

        # --- Resumen ---
        resumen = df_viz.groupby(['Código Equipo', 'Mes']).agg(
            media_consumo=('Galones por Hora', 'mean'),
            desviacion=('Galones por Hora', 'std'),
            registros=('Galones por Hora', 'count')
        ).reset_index()

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

        # --- Boxplot de dispersión ---
        st.subheader("📦 Boxplot de dispersión por mes (todos los equipos)")
        fig2, ax2 = plt.subplots(figsize=(10,5))
        sns.boxplot(data=df_viz, x='Mes', y='Galones por Hora', ax=ax2)
        sns.stripplot(data=df_viz, x='Mes', y='Galones por Hora', ax=ax2, color='red', alpha=0.5, jitter=0.2)
        ax2.set_title("Distribución de consumo (Gal/hora) por mes")
        ax2.set_ylabel("Gal/hora")
        st.pyplot(fig2)

        # --- Tabla resumen ---
        st.subheader("📋 Resumen mensual con actividad dominante")
        st.dataframe(resumen)

        # --- Descargar resumen ---
        descargar_resultado(resumen, "Resumen_Mensual.xlsx", "resumen mensual")

    else:
        st.warning("⚠️ Primero procesa los datos en la pestaña 'Procesamiento'.")

