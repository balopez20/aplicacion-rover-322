import streamlit as st
import matplotlib.pyplot as plt
import io

st.set_page_config(page_title="Generador CNC Biesse Rover 322", layout="wide")

st.title("🛠️ Generador de Código CNC y Esquema - Biesse Rover 322")
st.markdown("Aplicación para la generación de archivos `.NC` ordenados y visualización gráfica del panel.")

# --- Panel Lateral de Configuración ---
st.sidebar.header("Dimensiones de la Pieza (mm)")
lpx = st.sidebar.number_input("Largo (LX)", value=804.0, step=1.0)
lpy = st.sidebar.number_input("Ancho (LY)", value=480.0, step=1.0)
lz = st.sidebar.number_input("Espesor (LZ)", value=15.0, step=0.5)

st.sidebar.header("Definición de Operaciones")
# Ejemplo de operaciones predeterminadas editables o estructuradas
operaciones_por_defecto = [
    {"x": 8.50, "y": 32.00, "prof": 22.00, "ciclo": "G99", "herramienta": "10"},
    {"x": 8.50, "y": 448.00, "prof": 22.00, "ciclo": "G99", "herramienta": "10"},
    {"x": 8.50, "y": 160.00, "prof": 22.00, "ciclo": "G99", "herramienta": "8"},
    {"x": 8.50, "y": 320.00, "prof": 22.00, "ciclo": "G99", "herramienta": "8"},
    {"x": 40.50, "y": 32.00, "prof": 11.00, "ciclo": "G98", "herramienta": "1"},
    {"x": 40.50, "y": 448.00, "prof": 11.00, "ciclo": "G98", "herramienta": "1"}
]

# --- Funciones de Generación ---
def generar_archivo_cnc(lpx, lpy, lz, operaciones):
    """Genera el texto plano del código CNC respetando el G71 arriba."""
    lineas = []
    lineas.append("%")
    lineas.append(f"N10 G71 LX={lpx} LY={lpy} LZ={lz} HC1 Z=PRK")
    lineas.append("N11 LO:")
    lineas.append("N20 Y=PRK Z=PRK")
    
    for i, op in enumerate(operaciones, start=1):
        num_linea = i * 10
        lineas.append(
            f"N{num_linea} X{op['x']:.2f} Y{op['y']:.2f} "
            f"PRF={op['prof']:.2f} L={op['ciclo']} T{op['herramienta']}"
        )
    lineas.append("%")
    return "\n".join(lineas)

def generar_grafico_pieza(lpx, lpy, operaciones):
    """Genera un gráfico en Matplotlib con las dimensiones del tablero y las perforaciones."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Dibujar el contorno del tablero
    rect = plt.Rectangle((0, 0), lpx, lpy, linewidth=2, edgecolor='#1f77b4', facecolor='#f8f9fa', label='Tablero')
    ax.add_patch(rect)
    
    # Graficar cada punto de mecanizado
    for i, op in enumerate(operaciones, start=1):
        ax.plot(op['x'], op['y'], marker='o', markersize=10, color='#d62728')
        ax.text(op['x'] + 8, op['y'], f"P{i}: T{op['herramienta']}\n(X:{op['x']}, Y:{op['y']})", 
                fontsize=8, verticalalignment='center', color='#333333', 
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7, edgecolor='#cccccc'))

    ax.set_xlim(-30, lpx + 80)
    ax.set_ylim(-30, lpy + 50)
    ax.set_aspect('equal')
    ax.set_xlabel("Eje X (mm)", fontsize=10, fontweight='bold')
    ax.set_ylabel("Eje Y (mm)", fontsize=10, fontweight='bold')
    ax.set_title(f"Esquema Técnico - Panel {lpx} x {lpy} mm", fontsize=12, fontweight='bold')
    ax.grid(True, linestyle='--', alpha=0.5)
    
    # Guardar en buffer de memoria para permitir descarga de imagen si se desea
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches='tight', dpi=300)
    buf.seek(0)
    
    return fig, buf

# --- Procesamiento Principal ---
contenido_cnc = generar_archivo_cnc(lpx, lpy, lz, operaciones_por_defecto)
figura, buffer_img = generar_grafico_pieza(lpx, lpy, operaciones_por_defecto)

# Layout en columnas para mostrar ambos resultados simultáneamente
col1, col2 = st.columns(2)

with col1:
    st.subheader("📄 Código CNC Generado")
    st.text_area("Vista previa del archivo .NC", contenido_cnc, height=300)
    
    st.download_button(
        label="📥 Descargar Archivo CNC (PIEZA01.NC)",
        data=contenido_cnc,
        file_name="PIEZA01.NC",
        mime="text/plain",
        type="primary"
    )

with col2:
    st.subheader("🖼️ Esquema Gráfico de la Pieza")
    st.pyplot(figura)
    
    st.download_button(
        label="📥 Descargar Imagen del Esquema (PNG)",
        data=buffer_img,
        file_name="PIEZA01_Esquema.png",
        mime="image/png"
    )

st.success("✨ Aplicación sincronizada: El código incluye el bloque `G71` al inicio y la imagen muestra el posicionamiento exacto para la máquina.")
