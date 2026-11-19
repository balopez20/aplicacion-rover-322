import streamlit as st
import pandas as pd
import struct
import datetime

st.set_page_config(page_title="Generador Disquete CNC - Biesse Rover 322", layout="wide")

st.title("💾 Generador de Imagen de Disquete (.IMG) - Biesse Rover 322")
st.markdown("Configura las dimensiones, perforaciones y descarga el archivo `.img` (1.44 MB) listo para el emulador USB y CNi Floppy.")

# ==============================================================================
# 1. FUNCIÓN PARA CREAR IMAGEN DE DISQUETE COMPATIBLE CON CNI FLOPPY
# ==============================================================================
def crear_imagen_disquete_cni(nombre_archivo_8_3: str, contenido_bytes: bytes) -> bytes:
    SECTOR_SIZE = 512
    TOTAL_SECTORS = 2880  # 1.44 MB
    img = bytearray(SECTOR_SIZE * TOTAL_SECTORS)

    # --- Boot Sector específico para CNi Floppy / FAT12 ---
    boot = bytearray(512)
    boot[0:3] = b'\xEB\x3C\x90'
    boot[3:11] = b'MSDOS5.0'
    struct.pack_into('<H', boot, 11, SECTOR_SIZE)
    boot[13] = 1                             # Sectores por cluster
    struct.pack_into('<H', boot, 14, 1)      # Sectores reservados
    boot[16] = 2                             # Número de FATs
    struct.pack_into('<H', boot, 17, 224)    # Entradas en directorio raíz
    struct.pack_into('<H', boot, 19, TOTAL_SECTORS)
    boot[21] = 0xF0                          # Descriptor de medio (Disquete 1.44)
    struct.pack_into('<H', boot, 22, 9)      # Sectores por FAT
    struct.pack_into('<H', boot, 24, 18)     # Sectores por pista
    struct.pack_into('<H', boot, 26, 2)      # Cabezales
    struct.pack_into('<I', boot, 28, 0)      # Sectores ocultos
    boot[36] = 0x00                          # Unidad física
    boot[38] = 0x29                          # Firma de arranque extendida
    struct.pack_into('<I', boot, 39, 0x19950820) # Serial del volumen
    boot[43:54] = b'CNIFLOPPY   '            # Etiqueta requerida por entorno CNi
    boot[54:62] = b'FAT12   '
    boot[510:512] = b'\x55\xAA'
    img[0:512] = boot

    # --- Formatear nombre de archivo a estándar 8.3 ---
    partes = nombre_archivo_8_3.upper().split('.')
    nombre = partes[0][:8].ljust(8, ' ')
    ext = (partes[1][:3] if len(partes) > 1 else '').ljust(3, ' ')
    dos_name = (nombre + ext).encode('ascii', errors='ignore')

    # --- Cálculo de espacios en FAT12 ---
    tamano = len(contenido_bytes)
    num_clusters = max(1, (tamano + SECTOR_SIZE - 1) // SECTOR_SIZE)

    fat = bytearray(9 * SECTOR_SIZE)
    fat[0] = 0xF0
    fat[1] = 0xFF
    fat[2] = 0xFF

    def set_fat12_entry(fat_buf, cluster, value):
        offset = (cluster * 3) // 2
        if cluster % 2 == 0:
            fat_buf[offset] = value & 0xFF
            fat_buf[offset + 1] = (fat_buf[offset + 1] & 0xF0) | ((value >> 8) & 0x0F)
        else:
            fat_buf[offset] = (fat_buf[offset] & 0x0F) | ((value << 4) & 0xF0)
            fat_buf[offset + 1] = (value >> 4) & 0xFF

    for c in range(2, 2 + num_clusters):
        next_c = 0xFFF if c == (2 + num_clusters - 1) else (c + 1)
        set_fat12_entry(fat, c, next_c)

    img[512 : 512 + len(fat)] = fat
    img[512 + len(fat) : 512 + 2*len(fat)] = fat

    # --- Directorio Raíz ---
    root_offset = 19 * SECTOR_SIZE
    entry = bytearray(32)
    entry[0:11] = dos_name
    entry[11] = 0x20  # Atributo Archive
    struct.pack_into('<H', entry, 26, 2)     # Cluster inicial = 2
    struct.pack_into('<I', entry, 28, tamano)
    img[root_offset : root_offset + 32] = entry

    # --- Área de Datos ---
    data_offset = 33 * SECTOR_SIZE
    img[data_offset : data_offset + tamano] = contenido_bytes

    return bytes(img)

# ==============================================================================
# 2. INTERFAZ DE USUARIO: DIMENSIONES Y CONFIGURACIÓN
# ==============================================================================
col_dim, col_prog = st.columns([1, 1])

with col_dim:
    st.subheader("1️⃣ Dimensiones de la Pieza (mm)")
    c1, c2, c3 = st.columns(3)
    lpx = c1.number_input("Largo (LX)", min_value=10.0, value=804.0, step=1.0)
    lpy = c2.number_input("Ancho (LY)", min_value=10.0, value=480.0, step=1.0)
    lz = c3.number_input("Espesor (LZ)", min_value=3.0, value=15.0, step=0.5)

with col_prog:
    st.subheader("2️⃣ Nombre del Programa")
    c_nom, c_ext = st.columns(2)
    nombre_pieza = c_nom.text_input("Nombre (Máx. 8 caracteres)", value="PIEZA01", max_chars=8).upper()
    extension = c_ext.selectbox("Extensión", ["Sin extensión", ".NC", ".PGM"], index=0)

st.divider()

# ==============================================================================
# 3. TABLAS EDITABLES DE PERFORACIONES
# ==============================================================================
col_v, col_h = st.columns(2)

with col_v:
    st.subheader("⬇️ Perforaciones Verticales")
    df_vert_init = pd.DataFrame([
        {"X (mm)": 40.5, "Y (mm)": 32.0, "Profundidad (mm)": 11.0, "Herramienta (T)": 1, "Ciclo": "G98"},
        {"X (mm)": 40.5, "Y (mm)": 448.0, "Profundidad (mm)": 11.0, "Herramienta (T)": 1, "Ciclo": "G98"},
    ])
    df_vert = st.data_editor(df_vert_init, num_rows="dynamic", use_container_width=True, key="ed_v")

with col_h:
    st.subheader("➡️ Perforaciones Horizontales")
    df_horiz_init = pd.DataFrame([
        {"X (mm)": 8.5, "Y (mm)": 32.0, "Profundidad (mm)": 22.0, "Herramienta (T)": 10, "Ciclo": "G99"},
        {"X (mm)": 8.5, "Y (mm)": 448.0, "Profundidad (mm)": 22.0, "Herramienta (T)": 10, "Ciclo": "G99"},
        {"X (mm)": 8.5, "Y (mm)": 160.0, "Profundidad (mm)": 22.0, "Herramienta (T)": 8, "Ciclo": "G99"},
        {"X (mm)": 8.5, "Y (mm)": 320.0, "Profundidad (mm)": 22.0, "Herramienta (T)": 8, "Ciclo": "G99"},
    ])
    df_horiz = st.data_editor(df_horiz_init, num_rows="dynamic", use_container_width=True, key="ed_h")

# ==============================================================================
# 4. CONSTRUCCIÓN DEL CÓDIGO Y DESCARGA
# ==============================================================================
def construir_codigo_cnc(lpx, lpy, lz, df_v, df_h):
    lineas = []
    # Cabecera estricta G71 al inicio
    lineas.append("%")
    lineas.append(f"N10 G71 LX={lpx:g} LY={lpy:g} LZ={lz:g} HC1 Z=PRK")
    lineas.append("N11 LO:")
    lineas.append("N20 Y=PRK Z=PRK")

    num_linea = 10
    for _, row in df_h.dropna().iterrows():
        lineas.append(f"N{num_linea} X{float(row['X (mm)']):.2f} Y{float(row['Y (mm)']):.2f} PRF={float(row['Profundidad (mm)']):.2f} L={row['Ciclo']} T{int(row['Herramienta (T)'])}")
        num_linea += 10

    for _, row in df_v.dropna().iterrows():
        lineas.append(f"N{num_linea} X{float(row['X (mm)']):.2f} Y{float(row['Y (mm)']):.2f} PRF={float(row['Profundidad (mm)']):.2f} L={row['Ciclo']} T{int(row['Herramienta (T)'])}")
        num_linea += 10

    lineas.append("%")
    return "\r\n".join(lineas) + "\r\n"

try:
    codigo_cnc = construir_codigo_cnc(lpx, lpy, lz, df_vert, df_horiz)

    nombre_interno = nombre_pieza if extension == "Sin extensión" else f"{nombre_pieza}{extension}"
    bytes_cnc = codigo_cnc.encode("ascii", errors="ignore")
    imagen_disquete_bytes = crear_imagen_disquete_cni(nombre_interno, bytes_cnc)

    st.divider()
    col_code, col_down = st.columns([1.2, 1])

    with col_code:
        st.subheader("📄 Vista Previa del Código CNC")
        st.code(codigo_cnc, language="text")

    with col_down:
        st.subheader("💾 Descarga")
        st.info(f"Archivo interno: `{nombre_interno}` (Formato CNi Floppy 1.44 MB)")
        st.download_button(
            label=f"⬇️ Descargar Imagen ({nombre_pieza}.img)",
            data=imagen_disquete_bytes,
            file_name=f"{nombre_pieza}.img",
            mime="application/octet-stream",
            type="primary",
            use_container_width=True
        )
except Exception as e:
    st.error(f"Error al procesar la aplicación: {e}")
