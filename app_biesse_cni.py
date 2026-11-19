import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import struct
import re
import os

st.set_page_config(page_title="Biesse Rover 322", page_icon="🪚", layout="wide")
st.title("Biesse CNi RT480")

FLOPPY_SIZE = 1474560
DIR_OFFSET = 0x9A00
DIR_END = 0xB000
FIRST_DATA_OFFSET = 0xD800
RUTAS_PLANTILLA_DEFAULT = ["00036RV1.ima.IMG", r"F:\programas rover n2 actualizados 2018\Nueva carpeta\00036RV1.ima.IMG"]

def generar_secciones_cni(lpx, lpy, lpz, hc, df_vert, df_horiz, df_fresado):
    lineas_tabla = []
    for _, r in df_vert.dropna(subset=["X", "Y"]).iterrows():
        c = int(r.get("C", 1))
        x = f"{float(r['X']):g}"
        y = f"{float(r['Y']):g}"
        dp = f"{float(r['Profundidad']):g}" if pd.notna(r.get("Profundidad")) else "15"
        diam = f"{float(r['Diametro']):g}" if pd.notna(r.get("Diametro")) else "5"
        tipo = int(r.get("Tipo", 2)) if pd.notna(r.get("Tipo")) else 2
        rep_val = int(r.get("Rep", 1)) if pd.notna(r.get("Rep")) else 1
        rep = f"{rep_val}" if rep_val > 1 else ""
        off_x = f"{float(r['Off_X']):g}" if pd.notna(r.get("Off_X")) and float(r.get("Off_X", 0)) != 0 else ""
        off_y = f"{float(r['Off_Y']):g}" if pd.notna(r.get("Off_Y")) and float(r.get("Off_Y", 0)) != 0 else ""
        lineas_tabla.append(f"V,{c},{x:<8},{y:<9},{dp:<6},{diam:<6},{tipo},{rep:<3},{off_x:<7},{off_y:<7},  ,")

    for _, r in df_horiz.dropna(subset=["Z", "Profundidad"]).iterrows():
        c = int(r.get("C", 1))
        s = int(r.get("S", 1))
        x_val = r.get("X")
        y_val = r.get("Y")
        x_str = f"{float(x_val):g}" if pd.notna(x_val) and x_val != "" else ""
        y_str = f"{float(y_val):g}" if pd.notna(y_val) and y_val != "" else ""
        z_str = f"{float(r['Z']):g}" if pd.notna(r.get("Z")) and float(r["Z"]) != 0 else ""
        dp = f"{float(r['Profundidad']):g}"
        diam = f"{float(r['Diametro']):g}" if pd.notna(r.get("Diametro")) else "8"
        tipo = int(r.get("Tipo", 2)) if pd.notna(r.get("Tipo")) else 2
        rep_val = int(r.get("Rep", 1)) if pd.notna(r.get("Rep")) else 1
        rep = f"{rep_val}" if rep_val > 1 else ""
        off_x = f"{float(r['Off_X']):g}" if pd.notna(r.get("Off_X")) and float(r.get("Off_X", 0)) != 0 else ""
        off_y = f"{float(r['Off_Y']):g}" if pd.notna(r.get("Off_Y")) and float(r.get("Off_Y", 0)) != 0 else ""
        off_z = f"{float(r['Off_Z']):g}" if pd.notna(r.get("Off_Z")) and float(r.get("Off_Z", 0)) != 0 else ""
        lineas_tabla.append(f"O,{c},{s},{x_str:<8},{y_str:<9},{z_str:<7},{dp:<6},{diam:<6},{tipo},{rep:<3},{off_x:<7},{off_y:<7},{off_z:<7},  ,")

    if not lineas_tabla:
        lineas_tabla.append("V,1,8.5     ,32       ,22    ,7     ,1,2  ,0      ,416    ,  ,")

    sec_tabla = "\n".join(lineas_tabla) + "\n"
    sec_props = f"LPX={lpx:g}                      \nLPY={lpy:g}                       \nLPZ={lpz:g}                        \n"
    
    lineas_opt, n_opt = [], 10
    for _, r in df_horiz.dropna(subset=["Z", "Profundidad"]).iterrows():
        c = int(r.get("C", 1))
        x_v = float(r["X"]) if pd.notna(r.get("X")) and r["X"] != "" else 0.0
        y_v = float(r["Y"]) if pd.notna(r.get("Y")) and r["Y"] != "" else 0.0
        z_v = float(r["Z"]) if pd.notna(r.get("Z")) else 0.0
        prof = float(r["Profundidad"]) if pd.notna(r.get("Profundidad")) else 10.0
        herr = str(r.get("Herramienta", "TH8"))
        rep = max(1, int(r.get("Rep", 1))) if pd.notna(r.get("Rep")) else 1
        ox = float(r["Off_X"]) if pd.notna(r.get("Off_X")) else 0.0
        oy = float(r["Off_Y"]) if pd.notna(r.get("Off_Y")) else 0.0
        oz = float(r["Off_Z"]) if pd.notna(r.get("Off_Z")) else 0.0

        for step in range(rep):
            cx, cy, cz = x_v + step * ox, y_v + step * oy, z_v + step * oz
            g_face = f"G{c}" if c in [1, 3, 4] else "G1"
            lineas_opt.append(f"N{n_opt} QX={cx:.2f} QY={cy:.2f} PRF={prof:.2f} QZ={cz:.2f} QQN=1 L={g_face} {herr}")
            n_opt += 10

    for _, r in df_vert.dropna(subset=["X", "Y"]).iterrows():
        xv, yv = float(r["X"]), float(r["Y"])
        prof = float(r["Profundidad"]) if pd.notna(r.get("Profundidad")) else 15.0
        herr, ciclo = str(r.get("Herramienta", "T26")), str(r.get("Ciclo", "G99"))
        rep = max(1, int(r.get("Rep", 1))) if pd.notna(r.get("Rep")) else 1
        ox = float(r["Off_X"]) if pd.notna(r.get("Off_X")) else 0.0
        oy = float(r["Off_Y"]) if pd.notna(r.get("Off_Y")) else 0.0
        for step in range(rep):
            lineas_opt.append(f"N{n_opt} X{xv + step * ox:.2f} Y{yv + step * oy:.2f} PRF={prof:.2f} UF=1.00 L={ciclo} {herr}")
            n_opt += 10

    lineas_opt.append("%")
    sec_opt = "\n".join(lineas_opt) + "\n"

    lineas_prof = [f"N10 G71 LX={lpx:g} LY={lpy:g} LZ={lpz:g} HC{hc} Z=PRK                                    ", "N11 LO:"]
    n_prof, puntos_fresado = 20, df_fresado.dropna(subset=["X", "Y"]) if not df_fresado.empty else pd.DataFrame()
    if not puntos_fresado.empty:
        primer = puntos_fresado.iloc[0]
        lineas_prof.append(f"N{n_prof} G0 X={float(primer['X']):.2f} Y={float(primer['Y']):.2f} Z={float(primer['Z']):.2f} {str(primer.get('Spindle', 'TP1'))} L=PON")
        n_prof += 10
        for _, row in puntos_fresado.iloc[1:].iterrows():
            tipo, rx, ry, rz = str(row["Movimiento"]), float(row['X']), float(row['Y']), float(row['Z'])
            if tipo == "Lineal (G1)": lineas_prof.append(f"N{n_prof} G1 X={rx:.2f} Y={ry:.2f} Z={rz:.2f}")
            elif tipo == "Arco Horario (G4)": lineas_prof.append(f"N{n_prof} G4 X={rx:.2f} Y={ry:.2f} R={float(row.get('Radio', 10.0)):.2f}")
            elif tipo == "Arco Antihorario (G5)": lineas_prof.append(f"N{n_prof} G5 X={rx:.2f} Y={ry:.2f} R={float(row.get('Radio', 10.0)):.2f}")
            n_prof += 10
        lineas_prof.append(f"N{n_prof} L=POFF")
        n_prof += 10

    lineas_prof.extend([f"N{n_prof} Y=PRK Z=PRK", "%"])
    sec_prof = "\n".join(lineas_prof) + "\n"
    return sec_tabla, sec_props, sec_opt, sec_prof

def generar_disquete_con_molde(bytes_molde, nombre_prog, meta):
    img = bytearray(bytes_molde)
    if len(img) < FLOPPY_SIZE: 
        img.extend(b'\xE5' * (FLOPPY_SIZE - len(img)))
    else: 
        img = img[:FLOPPY_SIZE]
    
    nombre_limpio = re.sub(r'[^A-Z0-9_-]', '', str(nombre_prog).replace('"', '').replace("'", "").upper())[:11] or "M01039-25"

    sec_t = meta["sec_tabla"].encode('ascii', errors='ignore')
    sec_p = meta["sec_props"].encode('ascii', errors='ignore')
    sec_o = meta["sec_opt"].encode('ascii', errors='ignore')
    sec_pr = meta["sec_prof"].encode('ascii', errors='ignore')
    
    b_tabla = b"11" + sec_t
    b_props = sec_p
    b_opt = sec_o
    b_prof = sec_pr
    b_pie = b"G98        G99        *:\x1a"

    # CLONACIÓN DE CABECERA NATIVA: Buscamos la cabecera original en la plantilla para heredar sus bytes exactos
    cab = bytearray(img[FIRST_DATA_OFFSET : FIRST_DATA_OFFSET + 51])
    if len(cab) < 51:
        cab = bytearray(51)
        cab[0] = 0x00
    else:
        cab[0] = 0x00  # Forzar bandera de Programa Principal editable

    off_tabla = 51
    off_props = off_tabla + len(b_tabla)
    off_opt = off_props + len(b_props)
    off_prof = off_opt + len(b_opt)
    off_pie = off_prof + len(b_prof)
    off_fin = off_pie + len(b_pie)

    struct.pack_into('<H', cab, 21, off_props)
    struct.pack_into('<H', cab, 23, off_tabla)
    struct.pack_into('<H', cab, 26, len(b_opt))
    struct.pack_into('<H', cab, 28, off_opt)
    struct.pack_into('<H', cab, 33, off_prof)
    struct.pack_into('<H', cab, 36, len(b_prof))
    struct.pack_into('<H', cab, 38, off_prof)
    struct.pack_into('<H', cab, 41, len(b_pie))
    struct.pack_into('<H', cab, 43, off_pie)
    struct.pack_into('<H', cab, 46, len(b_pie))
    struct.pack_into('<H', cab, 48, off_fin)

    bloque_final = bytes(cab) + b_tabla + b_props + b_opt + b_prof + b_pie

    img[FIRST_DATA_OFFSET : FIRST_DATA_OFFSET + len(bloque_final)] = bloque_final

    espacio_cluster = 4096 * 3
    fin_real = FIRST_DATA_OFFSET + len(bloque_final)
    if fin_real < FIRST_DATA_OFFSET + espacio_cluster:
        img[fin_real : FIRST_DATA_OFFSET + espacio_cluster] = b'\xE5' * ((FIRST_DATA_OFFSET + espacio_cluster) - fin_real)

    entry_off = DIR_OFFSET
    entrada = bytearray(32)
    entrada[0] = 0x01
    entrada[1:12] = nombre_limpio.ljust(11, ' ').encode('ascii')
    registros_128 = (len(bloque_final) + 127) // 128
    entrada[15] = registros_128 & 0xFF
    entrada[16] = 0x0A

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
        lpx, lpy, lpz, hc = c2.number_input("LPX (mm)", 50.0, 3200.0, 1200.0, 1.0), c3.number_input("LPY (mm)", 50.0, 1500.0, 353.0, 1.0), c4.number_input("LPZ (mm)", 3.0, 100.0, 15.0, 1.0), int(c5.number_input("HC", 1, 4, 1, 1))
        comentario = st.text_input("Comment (Opcional)", value="")

        st.subheader("Drilling tables — Vertical drills")
        df_vert_default = pd.DataFrame([
            {"C": 1, "X": 358.0, "Y": 23.0, "Profundidad": 12.0, "Diametro": 5.0, "Tipo": 2, "Rep": 4, "Off_X": 288.0, "Off_Y": 0.0, "Herramienta": "T26", "Ciclo": "G99"}
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
        df_horiz_default = pd.DataFrame(columns=["C", "S", "X", "Y", "Z", "Profundidad", "Diametro", "Tipo", "Rep", "Off_X", "Off_Y", "Off_Z", "Herramienta"])
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

        sec_tabla, sec_props, sec_opt, sec_prof = generar_secciones_cni(lpx, lpy, lpz, hc, df_vert, df_horiz, df_fresado)

        st.subheader("Vista previa de las 4 pestañas CNi")
        p_prof, p_opt, p_tab = st.tabs(["Profiling", "Optimized drilling", "Drilling tables"])
        with p_prof: sec_prof_edit = st.text_area("Profiling:", value=sec_prof, height=140)
        with p_opt: sec_opt_edit = st.text_area("Optimized drilling:", value=sec_opt, height=140)
        with p_tab: sec_tabla_edit = st.text_area("Drilling tables:", value=sec_tabla, height=140)

        if st.button("➕ Agregar a la Cola del Disquete", type="primary", use_container_width=True):
            nombre_limpio_key = re.sub(r'[^A-Z0-9_-]', '', str(nombre_prog).replace('"', '').replace("'", "").upper())[:11]
            st.session_state.cola_disquete[nombre_limpio_key] = {
                "sec_tabla": sec_tabla_edit, 
                "sec_props": sec_props, 
                "sec_opt": sec_opt_edit, 
                "sec_prof": sec_prof_edit
            }
            st.success(f"Programa '{nombre_limpio_key}' agregado correctamente con sus 4 secciones.")

with tab2:
    st.subheader("Extractor de Programas desde Imagen CNi")
    archivo_subido = st.file_uploader("Subir archivo (.img, .bin, .txt)", type=["img", "bin", "txt"])
    if archivo_subido is not None:
        texto = archivo_subido.read().decode('latin-1', errors='ignore')
        encontrados = re.findall(r'(LPX=\d+(?:\.\d+)?\s+LPY=\d+(?:\.\d+)?\s+LPZ=\d+(?:\.\d+)?.*?%)', texto, re.DOTALL)
        st.write(f"Programas encontrados: **{len(encontrados)}**")
        for i, bloque in enumerate(encontrados):
            with st.expander(f"Programa #{i+1}"):
                st.code(re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xff]', '', bloque).strip())

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
        nombre_key, meta_prog = list(st.session_state.cola_disquete.items())[0]
        imagen_final = generar_disquete_con_molde(bytes_molde, nombre_key, meta_prog)
        
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
