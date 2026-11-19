import streamlit as st
import pandas as pd
import struct
import datetime

st.set_page_config(page_title="Generador Disquete CNC - Biesse Rover 322", layout="wide")

st.title("💾 Generador de Imagen de Disquete (.IMG) - Biesse Rover 322")
st.markdown("Configura las dimensiones, perforaciones verticales y horizontales, y descarga el archivo `.img` (1.44 MB FAT12) listo para el emulador USB.")

# ==============================================================================
# 1. FUNCIÓN PARA CREAR IMAGEN DE DISQUETE FAT12 (1.44 MB) EN MEMORIA
# ==============================================================================
def crear_imagen_disquete_fat12(nombre_archivo_8_3: str, contenido_bytes: bytes) -> bytes:
    """
    Crea una imagen binaria cruda de disquete de 3.5" HD (1.44 MB = 1,474,560 bytes)
    formateada en FAT12 e inserta el archivo CNC en el directorio raíz.
    """
    SECTOR_SIZE = 512
    TOTAL_SECTORS = 2880  # 1.44 MB
    img = bytearray(SECTOR_SIZE * TOTAL_SECTORS)

    # --- Boot Sector (Sector 0) ---
    boot = bytearray(512)
    boot[0:3] = b'\xEB\x3C\x90'              # JMP instruction
    boot[3:11] = b'MSDOS5.0'                 # OEM Name
    struct.pack_into('<H', boot, 11, 512)    # Bytes per sector
    boot[13] = 1                             # Sectors per cluster
    struct.pack_into('<H', boot, 14, 1)      # Reserved sectors
    boot[16] = 2                             # Number of FATs
    struct.pack_into('<H', boot, 17, 224)    # Root directory entries
    struct.pack_into('<H', boot, 19, 2880)   # Total sectors
    boot[21] = 0xF0                          # Media descriptor (1.44MB floppy)
    struct.pack_into('<H', boot, 22, 9)      # Sectors per FAT
    struct.pack_into('<H', boot, 24, 18)     # Sectors per track
    struct.pack_into('<H', boot, 26, 2)      # Number of heads
    struct.pack_into('<I', boot, 28, 0)      # Hidden sectors
    boot[36] = 0x00                          # Drive number
    boot[38] = 0x29                          # Extended boot signature
    struct.pack_into('<I', boot, 39, 0x12345678) # Volume serial number
    boot[43:54] = b'BIESSE_CNC '             # Volume label (11 bytes)
    boot[54:62] = b'FAT12   '                # File system type
    boot[510:512] = b'\x55\xAA'              # Boot signature
    img[0:512] = boot

    # --- Preparar nombre 8.3 (ej. "PIEZA01    ") ---
    partes = nombre_archivo_8_3.upper().split('.')
    nombre = partes[0][:8].ljust(8, ' ')
    ext = (partes[1][:3] if len(partes) > 1 else '').ljust(3, ' ')
    dos_name = (nombre + ext).encode('ascii', errors='ignore')

    # --- Calcular clusters necesarios (1 cluster = 512 bytes) ---
    tamano = len(contenido_bytes)
    num_clusters = max(1, (tamano + SECTOR_SIZE - 1) // SECTOR_SIZE)

    # --- Construir Tabla FAT12 (Sectores 1-9 y 10-18) ---
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

    img[512 : 512 + len(fat)] = fat          # FAT 1
    img[512 + len(fat) : 512 + 2*len(fat)] = fat  # FAT 2

    # --- Entrada en el Directorio Raíz (Sector 19, offset 9728) ---
    root_offset = 19 * SECTOR_SIZE
    now = datetime.datetime.now()
    dos_time = (now.hour << 11) | (now.minute << 5) | (now.second // 2)
    dos_date = ((now.year - 1980) << 9) | (now.month << 5) | now.day

    entry = bytearray(32)
    entry[0:11] = dos_name
    entry[11] = 0x20                         # Atributo: Archive
    struct.pack_into('<H', entry, 22, dos_time)
    struct.pack_into('<H', entry, 24, dos_date)
    struct.pack_into('<H', entry, 26, 2)     # Primer cluster = 2
    struct.pack_into('<I', entry, 28, tamano)
    img[root_offset : root_offset + 32] = entry

    # --- Escribir los datos del archivo en el Área de Datos (Sector 33 en adelante) ---
    data_offset = 33 * SECTOR_SIZE
    img[data_offset : data_offset + tamano] = contenido_bytes

    return bytes(img)


# ==============================================================================
# 2. INTERFAZ DE USUARIO: DIMENSIONES Y PERFORACIONES
# ==============================================================================
col_dim, col_prog = st.columns([1, 1])

with col_dim:
    st.subheader("1️⃣ Dimensiones de la Pieza (mm)")
    c1, c2, c3 = st.columns(3)
    lpx = c1.number_input("Largo (LX)", min_value=10.0, value=804.0, step=1.0)
    lpy = c2.number_input("Ancho (LY)", min_value=10.0, value=480.0, step=1.0)
    lz = c3.number_input("Espesor (LZ)", min_value=3.0, value=15.0, step=0.5)

with col_prog:
    st.subheader("2️⃣ Nombre del Programa en Disquete")
    c_nom, c_ext = st.columns(2)
    nombre_pieza = c_nom.text_input("Nombre (Máx. 8 caracteres)", value="PIEZA01", max_chars=8).upper()
    extension = c_ext.selectbox("Extensión en Disquete", ["Sin extensión (Biesse estándar)", ".NC", ".PGM"], index=0)

st.divider()

# --- Tablas Editables para Perforaciones Verticales y Horizontales ---
col_v, col_h = st.columns(2)

with col_v:
    st.subheader("⬇️ Perforaciones Verticales")
    st.caption("Perforaciones sobre la cara del tablero (Eje Z).")
    df_vert_init = pd.DataFrame([
        {"X (mm)": 40.5, "Y (mm)": 32.0, "Profundidad (mm)": 11.0, "Herramienta (T)": 1, "Ciclo": "G98"},
        {"X (mm)": 40.5, "Y (mm)": 448.0, "Profundidad (mm)": 11.0, "Herramienta (T)": 1, "Ciclo": "G98"},
    ])
    df_vert = st.data_editor(
        df_vert_init,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_vertical",
        column_config={
            "Ciclo": st.column_config.SelectboxColumn("Ciclo", options=["G98", "G99"], default="G98")
        }
    )

with col_h:
    st.subheader("➡️ Perforaciones Horizontales")
    st.caption("Perforaciones en los cantos del tablero (Ejes X / Y).")
    df_horiz_init = pd.DataFrame([
        {"X (mm)": 8.5, "Y (mm)": 32.0, "Z Canto (mm)": 7.5, "Profundidad (mm)": 22.0, "Herramienta (T)": 10, "Ciclo": "G99"},
        {"X (mm)": 8.5, "Y (mm)": 448.0, "Z Canto (mm)": 7.5, "Profundidad (mm)": 22.0, "Herramienta (T)": 10, "Ciclo": "G99"},
        {"X (mm)": 8.5, "Y (mm)": 160.0, "Z Canto (mm)": 7.5, "Profundidad (mm)": 22.0, "Herramienta (T)": 8, "Ciclo": "G99"},
        {"X (mm)": 8.5, "Y (mm)": 320.0, "Z Canto (mm)": 7.5, "Profundidad (mm)": 22.0, "Herramienta (T)": 8, "Ciclo": "G99"},
    ])
    df_horiz = st.data_editor(
        df_horiz_init,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_horizontal",
        column_config={
            "Ciclo": st.column_config.SelectboxColumn("Ciclo", options=["G99", "G98"], default="G99")
        }
    )

# ==============================================================================
# 3. CONSTRUCCIÓN DEL CÓDIGO CNC ORDENADO (CABECERA G71 AL INICIO)
# ==============================================================================
def construir_codigo_cnc(lpx, lpy, lz, df_v, df_h):
    lineas = []
    # Cabecera obligatoria al inicio
    lineas.append("%")
    lineas.append(f"N10 G71 LX={lpx:g} LY={lpy:g} LZ={lz:g} HC1 Z=PRK")
    lineas.append("N11 LO:")
    lineas.append("N20 Y=PRK Z=PRK")

    num_linea = 10

    # Agregar perforaciones horizontales
    for _, row in df_h.dropna().iterrows():
        x = float(row["X (mm)"])
        y = float(row["Y (mm)"])
        prof = float(row["Profundidad (mm)"])
        t = int(row["Herramienta (T)"])
        ciclo = str(row["Ciclo"])
        # Si tu postprocesador usa Z en horizontales, puedes agregar Z={row['Z Canto (mm)']:.2f}
        lineas.append(f"N{num_linea} X{x:.2f} Y{y:.2f} PRF={prof:.2f} L={ciclo} T{t}")
        num_linea += 10

    # Agregar perforaciones verticales
    for _, row in df_v.dropna().iterrows():
        x = float(row["X (mm)"])
        y = float(row["Y (mm)"])
        prof = float(row["Profundidad (mm)"])
        t = int(row["Herramienta (T)"])
        ciclo = str(row["Ciclo"])
        lineas.append(f"N{num_linea} X{x:.2f} Y{y:.2f} PRF={prof:.2f} L={ciclo} T{t}")
        num_linea += 10

    lineas.append("%")
    # El control CNi de Biesse usa saltos de línea estilo DOS (\r\n)
    return "\r\n".join(lineas) + "\r\n"


codigo_cnc = construir_codigo_cnc(lpx, lpy, lz, df_vert, df_horiz)

# Determinar nombre interno dentro del disquete
if extension == "Sin extensión (Biesse estándar)":
    nombre_interno = nombre_pieza
else:
    nombre_interno = f"{nombre_pieza}{extension}"

# Generar la imagen de disquete .IMG de 1.44 MB
bytes_cnc = codigo_cnc.encode("ascii", errors="ignore")
imagen_disquete_bytes = crear_imagen_disquete_fat12(nombre_interno, bytes_cnc)

# ==============================================================================
# 4. VISTA PREVIA Y DESCARGA DE IMAGEN DE DISQUETE (.IMG)
# ==============================================================================
st.divider()
col_code, col_down = st.columns([1.2, 1])

with col_code:
    st.subheader("📄 Vista Previa del Código Generado")
    st.code(codigo_cnc, language="text")

with col_down:
    st.subheader("💾 Descargar Imagen de Disquete")
    st.info(
        f"**Archivo interno en disquete:** `{nombre_interno}`\n\n"
        f"**Formato de imagen:** Disquete 3.5\" HD (1.44 MB / FAT12)\n\n"
        f"**Tamaño exacto:** `{len(imagen_disquete_bytes):,}` bytes"
    )
    
    st.download_button(
        label=f"⬇️ Descargar Imagen de Disquete ({nombre_pieza}.img)",
        data=imagen_disquete_bytes,
        file_name=f"{nombre_pieza}.img",
        mime="application/octet-stream",
        type="primary",
        use_container_width=True
    )
