import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import struct
import re
import os

st.set_page_config(page_title="Generador CNi RT480 - Biesse Rover 322", page_icon="🪚", layout="wide")
st.title("🪚 Generador de Disquetes (.IMG) - Biesse CNi RT480")

FLOPPY_SIZE = 1474560
DIR_OFFSET = 0x9A00
DIR_END = 0xB000
FIRST_DATA_OFFSET = 0xD800
RUTAS_PLANTILLA_DEFAULT = ["00036RV1.ima.IMG", r"F:\programas rover n2 actualizados 2018\Nueva carpeta\00036RV1.ima.IMG"]

def generar_codigo_cnc_plano(lpx, lpy, lpz, hc, df_vert, df_horiz, df_fresado):
    """
    Genera el código CNC plano estándar con G71 al inicio y todas las operaciones secuenciales.
    """
    lineas = []
    lineas.append("%")
    lineas.append(f"N10 G71 LX={lpx:g} LY={lpy:g} LZ={lpz:g} HC{hc} Z=PRK")
    lineas.append("N11 LO:")
    lineas.append("N20 Y=PRK Z=PRK")
    
    n_linea = 30
    
    # 1. Perforaciones Horizontales
    for _, r in df_horiz.dropna(subset=["Z", "Profundidad"]).iterrows():
        c = int(r.get("C", 1))
        x_val = float(r["X"]) if pd.notna(r.get("X")) and r["X"] != "" else 0.0
        y_val = float(r["Y"]) if pd.notna(r.get("Y")) and r["Y"] != "" else 0.0
        z_pos = float(r["Z"]) if pd.notna(r.get("Z")) else 0.0
        prof = float(r["Profundidad"]) if pd.notna(r.get("Profundidad")) else 10.0
        herr = str(r.get("Herramienta", "TH8"))
        rep = max(1, int(r.get("Rep", 1))) if pd.notna(r.get("Rep")) else 1
        off_x = float(r["Off_X"]) if pd.notna(r.get("Off_X")) else 0.0
        off_y = float(r["Off_Y"]) if pd.notna(r.get("Off_Y")) else 0.0
        off_z = float(r["Off_Z"]) if pd.notna(r.get("Off_Z")) else 0.0

        for step in range(rep):
            cur_x = x_val + step * off_x
            cur_y = y_val + step * off_y
            cur_z = z_pos + step * off_z
            
            if c == 1:
                lineas.append(f"N{n_linea} QX=0.00 QY={cur_y:.2f} PRF={prof:.2f} QZ={cur_z:.2f} QQN=1 L=G1 {herr}")
            elif c == 3:
                lineas.append(f"N{n_linea} QX={lpx:.2f} QY={cur_y:.2f} PRF={prof:.2f} QZ={cur_z:.2f} QQN=1 L=G3 {herr}")
            elif c == 4:
                lineas.append(f"N{n_linea} QX={cur_x:.2f} QY=0.00 PRF={prof:.2f} QZ={cur_z:.2f} QQN=1 L=G4 {herr}")
            else:
                lineas.append(f"N{n_linea} QX={cur_x:.2f} QY={cur_y:.2f} PRF={prof:.2f} QZ={cur_z:.2f} QQN=1 L=G2 {herr}")
            n_linea += 10

    # 2. Perforaciones Verticales
    for _, r in df_vert.dropna(subset=["X", "Y"]).iterrows():
        x_base, y_base = float(r["X"]), float(r["Y"])
        prof = float(r["Profundidad"]) if pd.notna(r.get("Profundidad")) else 15.0
        herr, ciclo = str(r.get("Herramienta", "T10")), str(r.get("Ciclo", "G99"))
        rep = max(1, int(r.get("Rep", 1))) if pd.notna(r.get("Rep")) else 1
        off_x = float(r["Off_X"]) if pd.notna(r.get("Off_X")) else 0.0
        off_y = float(r["Off_Y"]) if pd.notna(r.get("Off_Y")) else 0.0
        for step in range(rep):
            lineas.append(f"N{n_linea} X{x_base + step * off_x:.2f} Y{y_base + step * off_y:.2f} PRF={prof:.2f} L={ciclo} {herr}")
            n_linea += 10

    # 3. Fresado / Profiling (Opcional)
    puntos_fresado = df_fresado.dropna(subset=["X", "Y"]) if not df_fresado.empty else pd.DataFrame()
    if not puntos_fresado.empty:
        primer = puntos_fresado.iloc[0]
        lineas.append(f"N{n_linea} G0 X={float(primer['X']):.2f} Y={float(primer['Y']):.2f} Z={float(primer['Z']):.2f} {str(primer.get('Spindle', 'TP1'))} L=PON")
        n_linea += 10
        for _, row in puntos_fresado.iloc[1:].iterrows():
            tipo, rx, ry, rz = str(row["Movimiento"]), float(row['X']), float(row['Y']), float(row['Z'])
            if tipo == "Lineal (G1)":
                lineas.append(f"N{n_linea} G1 X={rx:.2f} Y={ry:.2f} Z={rz:.2f}")
            elif tipo == "Arco Horario (G4)":
                lineas.append(f"N{n_linea} G4 X={rx:.2f} Y={ry:.2f} R={float(row.get('Radio', 10.0)):.2f}")
            elif tipo == "Arco Antihorario (G5)":
                lineas.append(f"N{n_linea} G5 X={rx:.2f} Y={ry:.2f} R={float(row.get('Radio', 10.0)):.2f}")
            n_linea += 10
        lineas.append(f"N{n_linea} L=POFF")
        n_linea += 10

    lineas.append(f"N{n_linea} Y=PRK Z=PRK")
    lineas.append("%")
    
    return "\r\n".join(lineas) + "\r\n"

def generar_disquete_con_codigo_plano(bytes_molde, nombre_prog, contenido_cnc):
    img = bytearray(bytes_molde)
    if len(img) < FLOPPY_SIZE: 
        img.extend(b'\xE5' * (FLOPPY_SIZE - len(img)))
    else: 
        img = img[:FLOPPY_SIZE]
    
    nombre_limpio = re.sub(r'[^A-Z0-9_-]', '', str(nombre_prog).replace('"', '').replace("'", "").upper())[:11] or "M01039-25"
    datos_bytes = contenido_cnc.encode('ascii', errors='ignore')

    # Inyectar directamente el contenido plano en el área de datos del molde
    img[FIRST_DATA_OFFSET : FIRST_DATA_OFFSET + len(datos_bytes)] = datos_bytes

    # Limpiar resto de cluster si sobra espacio
    fin_real = FIRST_DATA_OFFSET + len(datos_bytes)
    espacio_cluster = 4096 * 4
    if fin_real < FIRST_DATA_OFFSET + espacio_cluster:
        img[fin_real : FIRST_DATA_OFFSET + espacio_cluster] = b'\xE5' * ((FIRST_DATA_OFFSET + espacio_cluster) - fin_real)

    # Actualizar entrada en el directorio raíz del disquete
    entry_off = DIR_OFFSET
    entrada = bytearray(32)
    entrada[0] = 0x01
    entrada[1:12] = nombre_limpio.ljust(11, ' ').encode('ascii')
    registros_128 = (len(datos_bytes) + 127) // 128
    entrada[15] = registros_128 & 0xFF
    entrada[16] = 0x0A  # Cluster inicial

    img[DIR_OFFSET:DIR_END] = b'\xE5' * (DIR_END - DIR_OFFSET)
    img[entry_off : entry_off + 32] = entrada

    return bytes(img)

if "cola_disquete" not in st.session_state: st.session_state.cola_disquete = {}

tab1, tab2, tab3 = st.tabs(["1️⃣ Diseñador de Pieza", "2️⃣ Extractor de Respaldos", "3️⃣ Generar Disquete (.IMG)"])

with tab1:
    col_izq, col_der = st.columns([1.25, 1])
    with col_izq:
        st.subheader("Properties (Dimensiones del Tablero)")
        c1, c2, c3, c4, c5 = st.columns([1.4, 1, 1, 1, 0.7])
        nombre_prog = c1.text_input("Name (Ej: M01039-25)", value="M01039-25", max_chars=11).upper()
        lpx, lpy, lpz, hc = c2.number_input("LPX (mm)", 50.0, 3200.0, 804.0, 1.0), c3.number_input("LPY (mm)", 50.0, 1500.0, 480.0, 1.0), c4.number_input("LPZ (mm)", 3.0, 100.0, 15.0, 1.0), int(c5.number_input("HC", 1, 4, 1, 1))
        comentario = st.text_input("Comment (Opcional)", value="")

        st.subheader("Drilling tables — Vertical drills")
        df_vert_default = pd.DataFrame([
            {"C": 1, "X": 8.5, "Y": 32.0, "Profundidad": 22.0, "Diametro": 7.0, "Tipo": 1, "Rep": 2, "Off_X": 0.0, "Off_Y": 416.0, "Herramienta": "T10", "Ciclo": "G99"},
            {"C": 1, "X": 8.5, "Y": 160.0, "Profundidad": 22.0, "Diametro": 6.0, "Tipo": 1, "Rep": 2, "Off_X": 0.0, "Off_Y": 160.0, "Herramienta": "T8", "Ciclo": "G99"},
            {"C": 1, "X": 40.5, "Y": 32.0, "Profundidad": 11.0, "Diametro": 9.0, "Tipo": 2, "Rep": 2, "Off_X": 0.0, "Off_Y": 416.0, "Herramienta": "T1", "Ciclo": "G98"}
        ])
        df_vert = st.data_editor(df_vert_default, num_rows="dynamic", use_container_width=True, column_config={
            "C": st.column_config.NumberColumn("C", min_value=1, max_value=4, step=1),
            "X": st.column_config.NumberColumn("X", format="%.2f"), "Y": st.column_config.NumberColumn("Y", format="%.2f"),
            "Profundidad": st.column_config.NumberColumn("Dp.", format="%.2f"), "Diametro": st.column_config.NumberColumn("Ø", format="%.1f"),
            "Tipo": st.column_config.NumberColumn("T", min_value=1, max_value=3, step=1), "Rep": st.column_config.NumberColumn("Rep", min_value=1, max_value=50, step=1),
            "Off_X": st.column_config.NumberColumn("Off. X", format="%.2f"), "Off_Y": st.column_config.NumberColumn("Off. Y", format="%.2f"),
            "Herramienta": st.column_config.SelectboxColumn("Broca", options=["T1","T4","T5","T6","T7","T8","T9","T10","T12","T15","T16","T25","T26"]),
            "Ciclo": st.column_config.SelectboxColumn("Ciclo", options=["G98", "G99"])
        })

        st.subheader("Drilling tables — Horizontal drills")
        df_horiz_default = pd.DataFrame([
            {"C": 1, "S": 1, "X": 48.0, "Y": None, "Z": 7.5, "Profundidad": 24.0, "Diametro": 8.0, "Tipo": 2, "Rep": 3, "Off_X": 0.0, "Off_Y": 70.0, "Off_Z": 0.0, "Herramienta": "TH8"}
        ])
        df_horiz = st.data_editor(df_horiz_default, num_rows="dynamic", use_container_width=True, column_config={
            "C": st.column_config.NumberColumn("C", min_value=1, max_value=4, step=1),
            "S": st.column_config.NumberColumn("S", min_value=1, max_value=4, step=1),
            "X": st.column_config.NumberColumn("X", format="%.2f"),
            "Y": st.column_config.NumberColumn("Y", format="%.2f"),
            "Z": st.column_config.NumberColumn("Z", format="%.2f"),
            "Profundidad": st.column_config.NumberColumn("Dp.", format="%.2f"),
            "Diametro": st.column_config.NumberColumn("Ø", format="%.1f"),
            "Tipo": st.column_config.NumberColumn("T", min_value=1, max_value=3, step=1),
            "Rep": st.column_config.NumberColumn("Rep", min_value=1, max_value=50, step=1),
            "Off_X": st.column_config.NumberColumn("Off. X", format="%.2f"),
            "Off_Y": st.column_config.NumberColumn("Off. Y", format="%.2f"),
            "Off_Z": st.column_config.NumberColumn("Off. Z", format="%.2f"),
            "Herramienta": st.column_config.SelectboxColumn("Broca", options=["TH2", "TH4", "TH5", "TH6", "TH7", "TH8"])
        })

        with st.expander("Profiling / Fresado (Opcional)"):
            df_fresado = st.data_editor(pd.DataFrame(columns=["Movimiento", "X", "Y", "Z", "Radio", "Spindle"]), num_rows="dynamic", use_container_width=True, column_config={
                "Movimiento": st.column_config.SelectboxColumn(options=["Lineal (G1)", "Arco Horario (G4)", "Arco Antihorario (G5)"]),
                "Spindle": st.column_config.SelectboxColumn(options=["TP1", "TP2"])
            })

    with col_der:
        st.subheader("Vista Previa 2D")
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.add_patch(patches.Rectangle((0, 0), lpx, lpy, linewidth=2, edgecolor='#1f77b4', facecolor='#f4e4c1'))
        for _, r in df_vert.dropna(subset=["X", "Y"]).iterrows():
            rep = max(1, int(r.get("Rep", 1))) if pd.notna(r.get("Rep")) else 1
            ox, oy = float(r["Off_X"]) if pd.notna(r.get("Off_X")) else 0.0, float(r["Off_Y"]) if pd.notna(r.get("Off_Y")) else 0.0
            color = 'crimson' if r.get("Ciclo") == "G99" else 'royalblue'
            for step in range(rep): ax.plot(float(r["X"]) + step * ox, float(r["Y"]) + step * oy, 'o', color=color, markersize=6)
        ax.set_xlim(-30, lpx + 30)
        ax.set_ylim(-30, lpy + 30)
        ax.set_aspect('equal')
        ax.grid(True, linestyle=':', alpha=0.6)
        ax.set_title(f"{nombre_prog} ({lpx:g} x {lpy:g} x {lpz:g} mm)")
        st.pyplot(fig)

        codigo_cnc_generado = generar_codigo_cnc_plano(lpx, lpy, lpz, hc, df_vert, df_horiz, df_fresado)

        st.subheader("Código CNC Generado (Plano y Ordenado)")
        st.text_area("Vista previa .NC:", value=codigo_cnc_generado, height=200)

        if st.button("➕ Agregar a la Cola del Disquete", type="primary", use_container_width=True):
            nombre_limpio_key = re.sub(r'[^A-Z0-9_-]', '', str(nombre_prog).replace('"', '').replace("'", "").upper())[:11]
            st.session_state.cola_disquete[nombre_limpio_key] = codigo_cnc_generado
            st.success(f"Programa '{nombre_limpio_key}' agregado correctamente.")

with tab2:
    st.subheader("Extractor de Programas desde Imagen CNi")
    archivo_subido = st.file_uploader("Subir archivo (.img, .bin, .txt)", type=["img", "bin", "txt"])
    if archivo_subido is not None:
        texto = archivo_subido.read().decode('latin-1', errors='ignore')
        st.code(texto[:2000])

with tab3:
    st.subheader("Disquete CNi con Molde Nativo Verificado (00036RV1.ima.IMG)")
    bytes_molde = None
    for ruta in RUTAS_PLANTILLA_DEFAULT:
        if os.path.exists(ruta):
            with open(ruta, "rb") as f: bytes_molde = f.read()
            st.success(f"✅ Molde nativo cargado automáticamente desde: `{ruta}`")
            break

    molde_subido = st.file_uploader("O selecciona manualmente el archivo base (.IMG):", type=["img", "ima"], key="molde_uploader")
    if molde_subido is not None:
        bytes_molde = molde_subido.read()
        st.success(f"✅ Molde cargado manualmente: `{molde_subido.name}`")

    col_info, col_btn = st.columns([2, 1])
    with col_info:
        st.write("**Programas en cola:**", list(st.session_state.cola_disquete.keys()) if st.session_state.cola_disquete else "Ninguno")
    with col_btn:
        if st.button("🗑️ Vaciar Cola", use_container_width=True):
            st.session_state.cola_disquete = {}
            st.rerun()

    nombre_salida = st.text_input("Nombre del archivo para el emulador USB (Gotek):", value="DSKA0000.IMG")

    if bytes_molde is not None and st.session_state.cola_disquete:
        nombre_key, codigo_txt = list(st.session_state.cola_disquete.items())[0]
        imagen_final = generar_disquete_con_codigo_plano(bytes_molde, nombre_key, codigo_txt)
        
        st.download_button(
            label=f"⬇️ DESCARGAR DISQUETTE LISTO ({nombre_salida})", 
            data=imagen_final, 
            file_name=nombre_salida, 
            mime="application/octet-stream", 
            type="primary", 
            use_container_width=True
        )
    else:
        st.warning("⚠️ Asegúrate de tener cargado el molde y al menos un programa agregado en la cola.")
