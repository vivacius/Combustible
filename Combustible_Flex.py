import streamlit as st
import pandas as pd
import io
import matplotlib.pyplot as plt
import seaborn as sns

# ===============================
# FUNCIONES AUXILIARES
# ===============================

@st.cache_data
def cargar_datos(file_abastecimientos, file_horas):
    abastecimientos = pd.read_excel(file_abastecimientos)
    horas_trabajadas = pd.read_excel(file_horas, dtype={'Código Equipo': object})
    return abastecimientos, horas_trabajadas

@st.cache_data
def procesar_datos(abastecimientos, horas_trabajadas):
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

tab1, tab2 = st.tabs(["⚙️ Procesamiento", "📊 Visualización"])

# -------------------------------
# TAB 1: PROCESAMIENTO
# -------------------------------
with tab1:
    st.header("⚙️ Procesamiento de datos")

    file_abastecimientos = st.file_uploader("📂 Archivo de Abastecimientos", type=["xlsx"])
    file_horas = st.file_uploader("📂 Archivo de Horas Trabajadas", type=["xlsx"])
    file_clasificacion = st.file_uploader("📂 Clasificación de Equipos", type=["xlsx", "csv"])

    if file_abastecimientos and file_horas:
        st.info("📥 Cargando archivos...")
        abastecimientos, horas_trabajadas = cargar_datos(file_abastecimientos, file_horas)

        # Limpieza
        abastecimientos = abastecimientos[abastecimientos['Código Equipo'].astype(str).str.match(r'^\d+$')]
        abastecimientos['Código Equipo'] = abastecimientos['Código Equipo'].astype(int)
        horas_trabajadas['Código Equipo'] = horas_trabajadas['Código Equipo'].astype(int)

        abastecimientos['Fecha Consumo'] = pd.to_datetime(abastecimientos['Fecha Consumo'], format='%d/%m/%Y')
        horas_trabajadas['Fecha'] = pd.to_datetime(horas_trabajadas['Fecha'], format='%d/%m/%Y %I:%M %p')

        df_resultados = procesar_datos(abastecimientos, horas_trabajadas)

        if file_clasificacion:
            if file_clasificacion.name.endswith(".csv"):
                clasificacion = pd.read_csv(file_clasificacion)
            else:
                clasificacion = pd.read_excel(file_clasificacion)

            clasificacion['EQUIPO3'] = clasificacion['EQUIPO3'].astype(int)
            df_resultados = df_resultados.merge(
                clasificacion[['EQUIPO3', 'ZONA', 'CATEGORIA', 'x̅ HISTORICA']], 
                left_on='Código Equipo', right_on='EQUIPO3', how='left'
            )
            df_resultados['ZONA'] = df_resultados['ZONA'].fillna("OTROS FRENTES")
            df_resultados.drop(columns=['EQUIPO3'], inplace=True)

        st.success("✅ ¡Datos procesados con éxito!")
        st.dataframe(df_resultados.head(50))

        descargar_resultado(df_resultados, "Resultado_final.xlsx", "archivo Excel de resultados")

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

        # Filtros
        col1, col2 = st.columns([2,1])
        with col1:
            rango_fecha = st.date_input("📆 Rango de fechas", [])
        with col2:
            categorias_sel = st.multiselect("📂 Categoría", df_resultados['CATEGORIA'].dropna().unique())

        df_filtros = df_resultados.copy()
        if rango_fecha and len(rango_fecha) == 2:
            df_filtros = df_filtros[(df_filtros['Fecha Inicio'] >= rango_fecha[0]) & 
                                    (df_filtros['Fecha Fin'] <= rango_fecha[1])]
        if categorias_sel:
            df_filtros = df_filtros[df_filtros['CATEGORIA'].isin(categorias_sel)]

        # Agregar Mes
        df_viz = df_filtros.copy()
        df_viz['Mes'] = df_viz['Fecha Inicio'].dt.to_period('M').dt.to_timestamp()

        # Resumen mensual ponderado
        resumen = df_viz.groupby(['Código Equipo', 'Mes']).agg(
            galones_totales=('Galones', 'sum'),
            horas_totales=('Horas Trabajadas', 'sum')
        ).reset_index()

        resumen['media_consumo'] = resumen['galones_totales'] / resumen['horas_totales']
        resumen['desviacion'] = df_viz.groupby(['Código Equipo','Mes'])['Galones por Hora'].std().values
        resumen['registros'] = df_viz.groupby(['Código Equipo','Mes'])['Galones por Hora'].count().values
        resumen['Año'] = resumen['Mes'].dt.year

        # Merge con media histórica
        if 'x̅ HISTORICA' in df_resultados.columns:
            resumen = resumen.merge(df_resultados[['Código Equipo','x̅ HISTORICA']].drop_duplicates(), 
                                    on='Código Equipo', how='left')
            resumen['% diferencia'] = ((resumen['media_consumo'] - resumen['x̅ HISTORICA']) / resumen['x̅ HISTORICA']) * 100

        # Tabla pivote estilo calendario
        st.subheader("📅 Tabla mensual (Gal/hora)")
        tabla_mes = resumen.pivot_table(
            index='Código Equipo',
            columns=resumen['Mes'].dt.strftime("%B"),
            values='media_consumo',
            aggfunc='mean'
        ).round(2)
        st.dataframe(tabla_mes.style.background_gradient(cmap="RdYlGn_r"))

        # KPIs último mes
        if not resumen.empty:
            ultimo_mes = resumen['Mes'].max()
            resumen_mes = resumen[resumen['Mes'] == ultimo_mes]

            top_mejores = resumen_mes.nsmallest(5, 'media_consumo')
            top_peores = resumen_mes.nlargest(5, 'media_consumo')

            st.subheader(f"🏆 Top equipos – {ultimo_mes.strftime('%B %Y')}")
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("✅ **Más eficientes (menor gal/hora)**")
                st.table(top_mejores[['Código Equipo','media_consumo','x̅ HISTORICA']].round(2))
            with col2:
                st.markdown("⚠️ **Menos eficientes (mayor gal/hora)**")
                st.table(top_peores[['Código Equipo','media_consumo','x̅ HISTORICA']].round(2))

            # Informe automático de desempeño
            st.subheader("📌 Informe automático de desempeño vs histórico")

            if 'x̅ HISTORICA' in resumen_mes.columns:
                equipos_revisar = resumen_mes[(resumen_mes['% diferencia'] > 10) | (resumen_mes['% diferencia'] < -10)]
                equipos_ok = resumen_mes[(resumen_mes['% diferencia'] >= -10) & (resumen_mes['% diferencia'] <= 10)]

                if not equipos_revisar.empty:
                    lista = ", ".join([f"{row['Código Equipo']} ({row['% diferencia']:+.1f}%)" for _, row in equipos_revisar.iterrows()])
                    st.error(f"⚠️ Equipos a revisar (consumo anormal): {lista}")

                if not equipos_ok.empty:
                    lista = ", ".join([f"{row['Código Equipo']} ({row['% diferencia']:+.1f}%)" for _, row in equipos_ok.iterrows()])
                    st.info(f"🟢 Equipos dentro de lo esperado: {lista}")

        # --- Análisis por Actividad ---
        st.subheader("🛠️ Análisis por Actividad")
        if "Nombre Actividad" in horas_trabajadas.columns:
            df_actividades = df_viz.merge(
                horas_trabajadas[['Código Equipo','Fecha','Nombre Actividad','Duracion (horas)']],
                left_on=['Código Equipo','Fecha Inicio'],
                right_on=['Código Equipo','Fecha'],
                how='left'
            )
            actividad_resumen = df_actividades.groupby('Nombre Actividad').agg(
                galones_totales=('Galones','sum'),
                horas_totales=('Horas Trabajadas','sum')
            ).reset_index()
            actividad_resumen['consumo_promedio'] = actividad_resumen['galones_totales'] / actividad_resumen['horas_totales']

            top_5_mayor = actividad_resumen.nlargest(5,'consumo_promedio')
            top_5_menor = actividad_resumen.nsmallest(5,'consumo_promedio')

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("🔝 **Top 5 actividades más consumidoras**")
                st.table(top_5_mayor[['Nombre Actividad','consumo_promedio']].round(2))
            with col2:
                st.markdown("✅ **Top 5 actividades más eficientes**")
                st.table(top_5_menor[['Nombre Actividad','consumo_promedio']].round(2))

        # Boxplot sin outliers
        st.subheader("📦 Distribución mensual sin outliers")
        fig3, ax3 = plt.subplots(figsize=(10,5))
        sns.boxplot(data=df_viz, x='Mes', y='Galones por Hora', ax=ax3, showfliers=False, color="skyblue")
        ax3.set_title("Consumo mensual (Gal/hora) sin outliers")
        ax3.set_ylabel("Gal/hora")
        st.pyplot(fig3)

        # Boxplot solo con outliers
        st.subheader("🚨 Outliers de consumo mensual")
        fig4, ax4 = plt.subplots(figsize=(10,5))
        for mes, grupo in df_viz.groupby('Mes'):
            q1 = grupo['Galones por Hora'].quantile(0.25)
            q3 = grupo['Galones por Hora'].quantile(0.75)
            iqr = q3 - q1
            lower, upper = q1 - 1.5*iqr, q3 + 1.5*iqr
            outliers = grupo[(grupo['Galones por Hora'] < lower) | (grupo['Galones por Hora'] > upper)]
            for _, row in outliers.iterrows():
                ax4.text(mes, row['Galones por Hora'], str(row['Código Equipo']), fontsize=8, ha='center')
            ax4.scatter([mes]*len(outliers), outliers['Galones por Hora'], color="red", alpha=0.7)
        ax4.set_title("Valores atípicos (Outliers) de consumo mensual")
        ax4.set_ylabel("Gal/hora")
        st.pyplot(fig4)

        # Descargas
        with st.expander("📥 Descargas"):
            descargar_resultado(resumen, "Resumen_Mensual.xlsx", "resumen mensual")

    else:
        st.warning("⚠️ Primero procesa los datos en la pestaña 'Procesamiento'.")





