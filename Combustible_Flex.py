import streamlit as st
import pandas as pd
import io
import time

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

def descargar_resultado(df):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Resultados')
    buffer.seek(0)
    st.download_button(
        label="📥 Descargar archivo Excel",
        data=buffer,
        file_name="Resultado_final.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# Interfaz Streamlit
st.title("🛠️ Procesamiento de datos para obtención de Galones por Hora Trabajada en los Equipos")

file_abastecimientos = st.file_uploader("📂 Sube el archivo de Abastecimientos", type=["xlsx"])
file_horas = st.file_uploader("📂 Sube el archivo de Horas Trabajadas", type=["xlsx"])

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

    descargar_resultado(df_resultados)


###python -m streamlit run "$HOME\Downloads\Combustible_Flex.py"
