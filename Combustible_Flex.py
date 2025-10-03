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
    # Agregaciones base
    abastecimientos_agrupados = abastecimientos.groupby(['Código Equipo', 'Fecha Consumo']).agg({
        'Cantidad': 'sum'
    }).reset_index()

    horas_trabajadas_agrupadas = horas_trabajadas.groupby(['Código Equipo', 'Fecha']).agg({
        'Duracion (horas)': 'sum'
    }).reset_index()

    # Renombres
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
    file_clasificacion = st.file_uploader("📂 Clasificación de Equipos (incluye ZONA, CATEGORIA, x̅ HISTORICA)", type=["xlsx", "csv"])

    if file_abastecimientos and file_horas:
        st.info("📥 Cargando archivos...")
        abastecimientos, horas_trabajadas = cargar_datos(file_abastecimientos, file_horas)

        # Limpieza
        abastecimientos = abastecimientos[abastecimientos['Código Equipo'].astype(str).str.match(r'^\d+$')]
        abastecimientos['Código Equipo'] = abastecimientos['Código Equipo'].astype(int)
        horas_trabajadas['Código Equipo'] = horas_trabajadas['Código Equipo'].astype(int)

        abastecimientos['Fecha Consumo'] = pd.to_datetime(abastecimientos['Fecha Consumo'], format='%d/%m/%Y')
        horas_trabajadas['Fecha'] = pd.to_datetime(horas_trabajadas['Fecha'], format='%d/%m/%Y %I:%M %p')

        # Procesamiento
        df_resultados = procesar_datos(abastecimientos, horas_trabajadas)

        # Merge con clasificación
        if file_clasificacion:
            if file_clasificacion.name.endswith(".csv"):
                clasificacion = pd.read_csv(file_clasificacion)
            else:
                clasificacion = pd.read_excel(file_clasificacion)

            clasificacion['EQUIPO3'] = clasificacion['EQUIPO3'].astype(int)
            if 'x̅ HISTORICA' in clasificacion.columns:
                clasificacion['x̅ HISTORICA'] = (
                    clasificacion['x̅ HISTORICA'].astype(str)
                    .str.replace(',', '.', regex=False)
                )
                clasificacion['x̅ HISTORICA'] = pd.to_numeric(clasificacion['x̅ HISTORICA'], errors='coerce')

            df_resultados = df_resultados.merge(
                clasificacion[['EQUIPO3', 'ZONA', 'CATEGORIA', 'x̅ HISTORICA']],
                left_on='Código Equipo', right_on='EQUIPO3', how='left'
            )
            df_resultados['ZONA'] = df_resultados['ZONA'].fillna("OTROS FRENTES")
            df_resultados.drop(columns=['EQUIPO3'], inplace=True, errors='ignore')

        st.success("✅ ¡Datos procesados con éxito!")
        st.dataframe(df_resultados.head(50))

        descargar_resultado(df_resultados, "Resultado_final.xlsx", "archivo Excel de intervalos")

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

        # ========= Filtros =========
        c1, c2, c3 = st.columns([1.5, 1.2, 1.3])
        with c1:
            rango_fecha = st.date_input("📆 Rango de fechas", [])
        with c2:
            categorias = sorted(df_resultados['CATEGORIA'].dropna().unique()) if 'CATEGORIA' in df_resultados.columns else []
            categorias_sel = st.multiselect("📂 Categoría", categorias, default=categorias)
        with c3:
            zonas = sorted(df_resultados['ZONA'].dropna().unique()) if 'ZONA' in df_resultados.columns else []
            zonas_sel = st.multiselect("🌍 Zona", zonas, default=zonas)

        df_filtros = df_resultados.copy()
        if rango_fecha and len(rango_fecha) == 2:
            fecha_inicio_sel = pd.to_datetime(rango_fecha[0])
            fecha_fin_sel = pd.to_datetime(rango_fecha[1])
            df_filtros = df_filtros[(df_filtros['Fecha Inicio'] >= fecha_inicio_sel) &
                                    (df_filtros['Fecha Fin'] <= fecha_fin_sel)]
        if categorias_sel:
            df_filtros = df_filtros[df_filtros['CATEGORIA'].isin(categorias_sel)]
        if zonas_sel:
            df_filtros = df_filtros[df_filtros['ZONA'].isin(zonas_sel)]

        if df_filtros.empty:
            st.warning("No hay datos con los filtros seleccionados.")
            st.stop()

        # ========= Resumen mensual basado en intervalos =========
        df_viz = df_filtros.copy()
        df_viz['Mes'] = df_viz['Fecha Inicio'].dt.to_period('M').dt.to_timestamp()

        resumen = df_viz.groupby(['Código Equipo', 'Mes']).agg(
            media_consumo=('Galones por Hora', 'mean'),
            desviacion=('Galones por Hora', 'std'),
            registros=('Galones por Hora', 'count')
        ).reset_index()
        resumen['Año'] = resumen['Mes'].dt.year

        if 'x̅ HISTORICA' in df_resultados.columns:
            resumen = resumen.merge(
                df_resultados[['Código Equipo', 'x̅ HISTORICA']].drop_duplicates(),
                on='Código Equipo', how='left'
            )
            resumen['% dif vs histórico'] = ((resumen['media_consumo'] - resumen['x̅ HISTORICA']) /
                                             resumen['x̅ HISTORICA']) * 100

        # ========= Tablas =========
        # ========= Tabla mensual Gal/hora =========
        st.subheader("📅 Tabla mensual (Gal/hora)")
        
        tabla_mes_abs = resumen.pivot_table(
            index='Código Equipo',
            columns=resumen['Mes'].dt.strftime("%B"),
            values='media_consumo',
            aggfunc='mean'
        ).round(2)
        
        st.dataframe(tabla_mes_abs)
        
        # ========= Tabla mensual % dif vs histórico =========
        if 'x̅ HISTORICA' in resumen.columns:
            st.subheader("📊 Tabla mensual (% diferencia vs histórico)")
        
            # función para colorear según condiciones
            def color_dif(val):
                if pd.isna(val):
                    return ""
                if -10 <= val <= 10:
                    return "color: blue; font-weight: bold;"   # dentro del rango aceptable
                elif val < -10:
                    return "color: green; font-weight: bold;"  # mejor que histórico
                else:
                    return "color: red; font-weight: bold;"    # peor que histórico
        
            tabla_mes_hist = resumen.pivot_table(
                index='Código Equipo',
                columns=resumen['Mes'].dt.strftime("%B"),
                values='% dif vs histórico',
                aggfunc='mean'
            ).round(1)
        
            st.dataframe(
                tabla_mes_hist.style.applymap(color_dif).format("{:+.1f}%")
            )
        else:
            st.warning("⚠️ No se encontró la columna de media histórica (x̅ HISTORICA).")

        # ========= Informe automático =========
        if not resumen.empty and 'x̅ HISTORICA' in resumen.columns:
            ultimo_mes = resumen['Mes'].max()
            resumen_mes = resumen[resumen['Mes'] == ultimo_mes]

            equipos_alerta = resumen_mes[(resumen_mes['% dif vs histórico'] > 10) | (resumen_mes['% dif vs histórico'] < -10)]
            equipos_ok = resumen_mes[(resumen_mes['% dif vs histórico'] >= -10) & (resumen_mes['% dif vs histórico'] <= 10)]

            st.subheader("📌 Informe automático")
            if not equipos_alerta.empty:
                lista = ", ".join([f"{int(row['Código Equipo'])} ({row['% dif vs histórico']:+.1f}%)" for _, row in equipos_alerta.iterrows()])
                st.error(f"⚠️ Equipos a revisar: {lista}")
            if not equipos_ok.empty:
                lista = ", ".join([f"{int(row['Código Equipo'])} ({row['% dif vs histórico']:+.1f}%)" for _, row in equipos_ok.iterrows()])
                st.info(f"🟢 Equipos dentro de lo esperado: {lista}")

        # ========= Top actividades =========
        st.subheader("🛠️ Top actividades")
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
            actividad_resumen = actividad_resumen.dropna(subset=['consumo_promedio'])

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("🔝 **Top 5 más consumidoras**")
                st.table(actividad_resumen.nlargest(5,'consumo_promedio')[['Nombre Actividad','consumo_promedio']].round(2))
            with col2:
                st.markdown("✅ **Top 5 más eficientes**")
                st.table(actividad_resumen.nsmallest(5,'consumo_promedio')[['Nombre Actividad','consumo_promedio']].round(2))

        # ========= Boxplots =========
        st.subheader("📦 Distribución mensual sin outliers")
        fig3, ax3 = plt.subplots(figsize=(10,5))
        sns.boxplot(data=df_viz, x='Mes', y='Galones por Hora', ax=ax3, showfliers=False, color="skyblue")
        ax3.set_title("Consumo mensual (Gal/hora) sin outliers")
        st.pyplot(fig3)

        st.subheader("🚨 Outliers de consumo mensual")
        fig4, ax4 = plt.subplots(figsize=(10,5))
        for mes, grupo in df_viz.groupby('Mes'):
            q1 = grupo['Galones por Hora'].quantile(0.25)
            q3 = grupo['Galones por Hora'].quantile(0.75)
            iqr = q3 - q1
            lower, upper = q1 - 1.5*iqr, q3 + 1.5*iqr
            outliers = grupo[(grupo['Galones por Hora'] < lower) | (grupo['Galones por Hora'] > upper)]
            ax4.scatter([mes]*len(outliers), outliers['Galones por Hora'], color="red", alpha=0.7)
            for _, row in outliers.iterrows():
                ax4.text(mes, row['Galones por Hora'], str(int(row['Código Equipo'])), fontsize=8, ha='center')
        ax4.set_title("Valores atípicos de consumo mensual")
        st.pyplot(fig4)

        # ========= Descarga =========
        with st.expander("📥 Descargas"):
            descargar_resultado(resumen, "Resumen_Mensual.xlsx", "resumen mensual")

