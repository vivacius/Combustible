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

        # Limpieza de claves y fechas
        abastecimientos = abastecimientos[abastecimientos['Código Equipo'].astype(str).str.match(r'^\d+$')]
        abastecimientos['Código Equipo'] = abastecimientos['Código Equipo'].astype(int)
        horas_trabajadas['Código Equipo'] = horas_trabajadas['Código Equipo'].astype(int)

        abastecimientos['Fecha Consumo'] = pd.to_datetime(abastecimientos['Fecha Consumo'], format='%d/%m/%Y')
        horas_trabajadas['Fecha'] = pd.to_datetime(horas_trabajadas['Fecha'], format='%d/%m/%Y %I:%M %p')

        # Procesamiento cacheado
        df_resultados = procesar_datos(abastecimientos, horas_trabajadas)

        # Merge con clasificación (ZONA, CATEGORIA, x̅ HISTORICA)
        if file_clasificacion:
            if file_clasificacion.name.endswith(".csv"):
                clasificacion = pd.read_csv(file_clasificacion)
            else:
                clasificacion = pd.read_excel(file_clasificacion)

            # normalizar tipos
            clasificacion['EQUIPO3'] = clasificacion['EQUIPO3'].astype(int)

            # convertir x̅ HISTORICA con coma decimal a float
            if 'x̅ HISTORICA' in clasificacion.columns:
                clasificacion['x̅ HISTORICA'] = (
                    clasificacion['x̅ HISTORICA'].astype(str)
                    .str.replace(' ', '', regex=False)
                    .str.replace(',', '.', regex=False)
                )
                clasificacion['x̅ HISTORICA'] = pd.to_numeric(clasificacion['x̅ HISTORICA'], errors='coerce')

            cols_merge = ['EQUIPO3', 'ZONA', 'CATEGORIA']
            if 'x̅ HISTORICA' in clasificacion.columns:
                cols_merge.append('x̅ HISTORICA')

            df_resultados = df_resultados.merge(
                clasificacion[cols_merge],
                left_on='Código Equipo', right_on='EQUIPO3', how='left'
            )

            df_resultados['ZONA'] = df_resultados['ZONA'].fillna("OTROS FRENTES")
            df_resultados.drop(columns=['EQUIPO3'], inplace=True, errors='ignore')

        st.success("✅ ¡Datos procesados con éxito!")
        st.dataframe(df_resultados.head(50))

        descargar_resultado(df_resultados, "Resultado_final.xlsx", "archivo Excel de resultados")

        # Guardar en sesión para visualización
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

        # ========= Filtros (Fecha, Categoría, Zona) =========
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
            df_filtros = df_filtros[(df_filtros['Fecha Inicio'] >= rango_fecha[0]) &
                                    (df_filtros['Fecha Fin'] <= rango_fecha[1])]
        if categorias_sel:
            df_filtros = df_filtros[df_filtros['CATEGORIA'].isin(categorias_sel)]
        if zonas_sel:
            df_filtros = df_filtros[df_filtros['ZONA'].isin(zonas_sel)]

        if df_filtros.empty:
            st.warning("No hay datos con los filtros seleccionados.")
            st.stop()

        # Agregar Mes
        df_viz = df_filtros.copy()
        df_viz['Mes'] = df_viz['Fecha Inicio'].dt.to_period('M').dt.to_timestamp()

        # ========= Resumen mensual ponderado por horas =========
        resumen = df_viz.groupby(['Código Equipo', 'Mes']).agg(
            galones_totales=('Galones', 'sum'),
            horas_totales=('Horas Trabajadas', 'sum')
        ).reset_index()

        resumen['media_consumo'] = resumen['galones_totales'] / resumen['horas_totales']
        # métricas auxiliares
        resumen['desviacion'] = df_viz.groupby(['Código Equipo','Mes'])['Galones por Hora'].std().values
        resumen['registros'] = df_viz.groupby(['Código Equipo','Mes'])['Galones por Hora'].count().values
        resumen['Año'] = resumen['Mes'].dt.year

        # traer histórica por equipo
        if 'x̅ HISTORICA' in df_resultados.columns:
            resumen = resumen.merge(
                df_resultados[['Código Equipo', 'x̅ HISTORICA']].drop_duplicates(),
                on='Código Equipo', how='left'
            )
            resumen['% diferencia'] = ((resumen['media_consumo'] - resumen['x̅ HISTORICA']) /
                                       resumen['x̅ HISTORICA']) * 100

        # ========= Tabla pivote absoluta =========
st.subheader("📅 Tabla mensual (Gal/hora ponderado)")

tabla_mes_abs = resumen.pivot_table(
    index='Código Equipo',
    columns=resumen['Mes'].dt.strftime("%B"),
    values='media_consumo',
    aggfunc='mean'
).round(2)

st.dataframe(
    tabla_mes_abs.style.background_gradient(cmap="RdYlGn_r", axis=None)
)

# ========= Tabla pivote comparada contra histórico =========
if 'x̅ HISTORICA' in resumen.columns:
    st.subheader("📊 Tabla mensual (% diferencia vs histórico)")

    resumen['% dif vs histórico'] = ((resumen['media_consumo'] - resumen['x̅ HISTORICA']) /
                                     resumen['x̅ HISTORICA']) * 100

    tabla_mes_hist = resumen.pivot_table(
        index='Código Equipo',
        columns=resumen['Mes'].dt.strftime("%B"),
        values='% dif vs histórico',
        aggfunc='mean'
    ).round(1)

    st.dataframe(
        tabla_mes_hist.style.background_gradient(cmap="RdYlGn_r", axis=None)
                           .format("{:+.1f}%")
    )
else:
    st.warning("No se encontró la columna de media histórica (x̅ HISTORICA) en los datos.")


        # ========= KPIs último mes =========
        if not resumen.empty:
            ultimo_mes = resumen['Mes'].max()
            resumen_mes = resumen[resumen['Mes'] == ultimo_mes]

            top_mejores = resumen_mes.nsmallest(5, 'media_consumo')
            top_peores = resumen_mes.nlargest(5, 'media_consumo')

            st.subheader(f"🏆 Top equipos – {ultimo_mes.strftime('%B %Y')}")
            k1, k2 = st.columns(2)
            with k1:
                st.markdown("✅ **Más eficientes (menor gal/hora)**")
                cols_show = ['Código Equipo', 'media_consumo']
                if 'x̅ HISTORICA' in resumen_mes.columns:
                    cols_show.append('x̅ HISTORICA')
                st.table(top_mejores[cols_show].round(2))
            with k2:
                st.markdown("⚠️ **Menos eficientes (mayor gal/hora)**")
                cols_show = ['Código Equipo', 'media_consumo']
                if 'x̅ HISTORICA' in resumen_mes.columns:
                    cols_show.append('x̅ HISTORICA')
                st.table(top_peores[cols_show].round(2))

            # ========= Informe automático vs histórico (arriba y abajo) =========
            if 'x̅ HISTORICA' in resumen_mes.columns:
                st.subheader("📌 Informe automático de desempeño vs histórico")
                # alertas ±10%
                equipos_alerta = resumen_mes[(resumen_mes['% diferencia'] > 10) | (resumen_mes['% diferencia'] < -10)]
                equipos_ok = resumen_mes[(resumen_mes['% diferencia'] >= -10) & (resumen_mes['% diferencia'] <= 10)]

                if not equipos_alerta.empty:
                    lista = ", ".join([f"{int(row['Código Equipo'])} ({row['% diferencia']:+.1f}%)"
                                       for _, row in equipos_alerta.iterrows()])
                    st.error(f"⚠️ Equipos a revisar (anomalía vs histórico): {lista}")

                if not equipos_ok.empty:
                    lista = ", ".join([f"{int(row['Código Equipo'])} ({row['% diferencia']:+.1f}%)"
                                       for _, row in equipos_ok.iterrows()])
                    st.info(f"🟢 Equipos dentro de lo esperado: {lista}")

        # ========= Análisis por Actividad =========
        st.subheader("🛠️ Análisis por Actividad")
        if "Nombre Actividad" in horas_trabajadas.columns:
            # Emparejamos por Código Equipo + fecha de inicio del intervalo
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

            top_5_mayor = actividad_resumen.nlargest(5,'consumo_promedio')
            top_5_menor = actividad_resumen.nsmallest(5,'consumo_promedio')

            a1, a2 = st.columns(2)
            with a1:
                st.markdown("🔝 **Top 5 actividades más consumidoras**")
                st.table(top_5_mayor[['Nombre Actividad','consumo_promedio']].round(2))
            with a2:
                st.markdown("✅ **Top 5 actividades más eficientes**")
                st.table(top_5_menor[['Nombre Actividad','consumo_promedio']].round(2))
        else:
            st.info("No se encontró la columna 'Nombre Actividad' en Horas Trabajadas para análisis por actividad.")

        # ========= Boxplot sin outliers =========
        st.subheader("📦 Distribución mensual sin outliers")
        fig3, ax3 = plt.subplots(figsize=(10,5))
        sns.boxplot(data=df_viz, x='Mes', y='Galones por Hora', ax=ax3, showfliers=False, color="skyblue")
        ax3.set_title("Consumo mensual (Gal/hora) sin outliers")
        ax3.set_ylabel("Gal/hora")
        st.pyplot(fig3)

        # ========= Solo outliers (IQR) con etiquetas de equipo =========
        st.subheader("🚨 Outliers de consumo mensual")
        fig4, ax4 = plt.subplots(figsize=(10,5))
        any_out = False
        for mes, grupo in df_viz.groupby('Mes'):
            q1 = grupo['Galones por Hora'].quantile(0.25)
            q3 = grupo['Galones por Hora'].quantile(0.75)
            iqr = q3 - q1
            lower, upper = q1 - 1.5*iqr, q3 + 1.5*iqr
            outliers = grupo[(grupo['Galones por Hora'] < lower) | (grupo['Galones por Hora'] > upper)]
            if not outliers.empty:
                any_out = True
                ax4.scatter([mes]*len(outliers), outliers['Galones por Hora'], color="red", alpha=0.7)
                for _, row in outliers.iterrows():
                    ax4.text(mes, row['Galones por Hora'], str(int(row['Código Equipo'])), fontsize=8, ha='center')
        ax4.set_title("Valores atípicos (Outliers) de consumo mensual")
        ax4.set_ylabel("Gal/hora")
        if not any_out:
            ax4.text(0.5, 0.5, "Sin outliers para los filtros actuales", ha='center', va='center', transform=ax4.transAxes)
        st.pyplot(fig4)

        # ========= Descargas =========
        with st.expander("📥 Descargas"):
            descargar_resultado(resumen, "Resumen_Mensual.xlsx", "resumen mensual")

    else:
        st.warning("⚠️ Primero procesa los datos en la pestaña 'Procesamiento'.")

