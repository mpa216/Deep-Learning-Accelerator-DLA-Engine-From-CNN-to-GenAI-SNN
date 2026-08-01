import numpy as np
import os

# Konfigurasi Q4.12
INT_BITS = 4
FRAC_BITS = 12
WIDTH = 16
SCALE = 2**FRAC_BITS

def float_to_hex(value):
    """Convert float to 16-bit signed hex string"""
    min_val = -(2**(INT_BITS-1))
    max_val = (2**(INT_BITS-1)) - (1/SCALE)
    val_clamped = np.clip(value, min_val, max_val)
    
    int_val = int(round(val_clamped * SCALE))
    if int_val < 0:
        int_val = (1 << WIDTH) + int_val
    return f"{int_val & 0xFFFF:04X}"

def convert_txt_to_mem(txt_filename, mem_filename):
    """Membaca file spasi-separated dari MATLAB dan simpan ke .mem"""
    if not os.path.exists(txt_filename):
        print(f"[WARN] {txt_filename} not found! Skipping.")
        return

    print(f"Converting {txt_filename} -> {mem_filename}...")
    with open(txt_filename, 'r') as f_in, open(mem_filename, 'w') as f_out:
        # Baca semua angka dalam file (matlab dlmwrite pakai spasi/newline)
        content = f_in.read().split()
        for val_str in content:
            val_float = float(val_str)
            hex_str = float_to_hex(val_float)
            f_out.write(hex_str + "\n")

# --- EXECUTION ---
# Generator Weights
convert_txt_to_mem("raw_Wg1.txt", "rom_g_w1.mem")
convert_txt_to_mem("raw_bg1.txt", "rom_g_b1.mem")
convert_txt_to_mem("raw_Wg2.txt", "rom_g_w2.mem")
convert_txt_to_mem("raw_bg2.txt", "rom_g_b2.mem")

# Discriminator Weights
convert_txt_to_mem("raw_Wd1.txt", "rom_d_w1.mem")
convert_txt_to_mem("raw_bd1.txt", "rom_d_b1.mem")
convert_txt_to_mem("raw_Wd2.txt", "rom_d_w2.mem")
convert_txt_to_mem("raw_bd2.txt", "rom_d_b2.mem")

# Test Input Vectors
convert_txt_to_mem("raw_input_z.txt", "input_z.mem")

print("Conversion Complete. .mem files are ready for Verilog simulation.")