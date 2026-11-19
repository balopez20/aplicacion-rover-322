import streamlit as st

def generar_archivo_cnc(lpx, lpy, lz, operaciones):
    """
    Genera el contenido del archivo CNC para la Biesse Rover 322 (control CNi RT480)
    garantizando que la cabecera G71 esté al inicio.
    """
    lineas = []
    
    # 1. Inicio de archivo y cabecera G71 obligatoria en la parte superior
    lineas.append("%")
    lineas.append(f"N10 G71 LX={lpx} LY={lpy} LZ={lz} HC1 Z=PRK")
    lineas.append("N11 LO:")
    lineas.append("N20 Y=PRK Z=PRK")
    
    # 2. Bucle para agregar las operaciones (perforaciones, ruteos, etc.) de forma ordenada
    for i, op in enumerate(operaciones, start=1):
        num_linea = i * 10
        # Ejemplo de formato: N10 X8.50 Y32.00 PRF=22.00 L=G99 T10
        lineas.append(
            f"N{num_linea} X{op['x']:.2f} Y{op['y']:.2f} "
            f"PRF={op['prof']:.2f} L={op['ciclo']} T{op['herramienta']}"
        )
    
    # 3. Cierre del archivo
    lineas.append("%")
    
    return "\n".join(lineas)

# --- Ejemplo de integración en tu interfaz de Streamlit ---
st.subheader("Generador de Código CNC - Biesse Rover 322")

# Entradas de dimensiones de la pieza
lpx = st.number_input("Largo de la pieza (LX)", value=804.0)
lpy = st.number_input("Ancho de la pieza (LY)", value=480.0)
lz = st.number_input("Espesor de la pieza (LZ)", value=15.0)

# Simulación de datos de perforaciones (estos vendrían de tu lógica o inputs anteriores)
operaciones_ejemplo = [
    {"x": 8.50, "y": 32.00, "prof": 22.00, "ciclo": "G99", "herramienta": "T10"},
    {"x": 8.50, "y": 448.00, "prof": 22.00, "ciclo": "G99", "herramienta": "T10"},
    {"x": 8.50, "y": 160.00, "prof": 22.00, "ciclo": "G99", "herramienta": "T8"},
    {"x": 8.50, "y": 320.00, "prof": 22.00, "ciclo": "G99", "herramienta": "T8"},
    {"x": 40.50, "y": 32.00, "prof": 11.00, "ciclo": "G98", "herramienta": "T1"},
    {"x": 40.50, "y": 448.00, "prof": 11.00, "ciclo": "G98", "herramienta": "T1"}
]

if st.button("Generar y Descargar PIEZA01"):
    # Generar el contenido ordenado
    contenido_cnc = generar_archivo_cnc(lpx, lpy, lz, operaciones_ejemplo)
    
    # Botón de descarga directa en Streamlit
    st.download_button(
        label="Descargar PIEZA01.NC",
        data=contenido_cnc,
        file_name="PIEZA01.NC",
        mime="text/plain"
    )
    
    st.success("¡Código generado correctamente con la cabecera en orden!")
    st.code(contenido_cnc, language="text")
