def crear_imagen_disquete_cni(nombre_archivo_8_3: str, contenido_bytes: bytes) -> bytes:
    """
    Crea una imagen de disquete compatible con CNi Floppy para controles Biesse (CNi RT480).
    """
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
    boot[43:54] = b'CNIFLOPPY   '            # Etiqueta requerida por el entorno CNi
    boot[54:62] = b'FAT12   '
    boot[510:512] = b'\x55\xAA'
    img[0:512] = boot

    # --- Formatear nombre de archivo a estándar 8.3 (obligatorio para CNi) ---
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
    entry[11] = 0x20  # Atributo de archivo (Archive)
    struct.pack_into('<H', entry, 26, 2)     # Inicia en el cluster 2
    struct.pack_into('<I', entry, 28, tamano)
    img[root_offset : root_offset + 32] = entry

    # --- Área de Datos ---
    data_offset = 33 * SECTOR_SIZE
    img[data_offset : data_offset + tamano] = contenido_bytes

    return bytes(img)
