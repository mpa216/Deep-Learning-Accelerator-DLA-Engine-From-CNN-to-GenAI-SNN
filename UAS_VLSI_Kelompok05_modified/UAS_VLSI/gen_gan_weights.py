import numpy as np
import os

# ==========================================
# Konfigurasi Arsitektur (Sesuai MATLAB)
# ==========================================
# Generator
Z_DIM = 2          # Input Latent
G_HIDDEN = 3       # Neurons di Hidden Layer
IMG_PIXELS = 9     # Output 3x3

# Discriminator
D_HIDDEN = 3       # Neurons di Hidden Layer
D_OUTPUT = 1       # Output Real/Fake

# Format Fixed Point Q4.12
INT_BITS = 4
FRAC_BITS = 12
WIDTH = 16
SCALE = 2**FRAC_BITS

def float_to_hex(value):
    """Mengubah float menjadi string hex 16-bit signed (Q4.12)"""
    # Clip value untuk mencegah overflow range Q4.12 (-8.0 s/d 7.999)
    min_val = -(2**(INT_BITS-1))
    max_val = (2**(INT_BITS-1)) - (1/SCALE)
    
    val_clamped = np.clip(value, min_val, max_val)
    
    int_val = int(round(val_clamped * SCALE))
    if int_val < 0:
        int_val = (1 << WIDTH) + int_val
    
    return f"{int_val & 0xFFFF:04X}"

def save_hex_file(filename, data_array, comment=""):
    """Menyimpan array numpy ke file .hex/.mem"""
    with open(filename, 'w') as f:
        # f.write(f"// {comment}\n") # Comment opsional, hati-hati di readmemh
        flat_data = data_array.flatten()
        for val in flat_data:
            f.write(f"{float_to_hex(val)}\n")
    print(f"Generated: {filename}")

# ==========================================
# 1. Generate Random Weights & Biases
# ==========================================
np.random.seed(42) # Agar hasil konsisten

# --- Generator Weights ---
# Layer 1: Input (2) -> Hidden (3)
W_G1 = np.random.uniform(-1, 1, (Z_DIM, G_HIDDEN)) # Shape (2, 3)
b_G1 = np.random.uniform(-0.5, 0.5, (G_HIDDEN))    # Shape (3,)

# Layer 2: Hidden (3) -> Output (9)
W_G2 = np.random.uniform(-1, 1, (G_HIDDEN, IMG_PIXELS)) # Shape (3, 9)
b_G2 = np.random.uniform(-0.5, 0.5, (IMG_PIXELS))       # Shape (9,)

# --- Discriminator Weights ---
# Layer 1: Input (9) -> Hidden (3)
W_D1 = np.random.uniform(-1, 1, (IMG_PIXELS, D_HIDDEN))
b_D1 = np.random.uniform(-0.5, 0.5, (D_HIDDEN))

# Layer 2: Hidden (3) -> Output (1)
W_D2 = np.random.uniform(-1, 1, (D_HIDDEN, D_OUTPUT))
b_D2 = np.random.uniform(-0.5, 0.5, (D_OUTPUT))

# ==========================================
# 2. Simpan File Hex untuk Verilog
# ==========================================
# Note: Matriks di Verilog biasanya disimpan row-major atau sesuai urutan address ROM
# Kita simpan W_G1 flattened: w00, w01, w02...

save_hex_file("rom_g_w1.mem", W_G1, "Generator Weights Layer 1 (2x3)")
save_hex_file("rom_g_b1.mem", b_G1, "Generator Bias Layer 1 (3)")
save_hex_file("rom_g_w2.mem", W_G2, "Generator Weights Layer 2 (3x9)")
save_hex_file("rom_g_b2.mem", b_G2, "Generator Bias Layer 2 (9)")

save_hex_file("rom_d_w1.mem", W_D1, "Discriminator Weights Layer 1 (9x3)")
save_hex_file("rom_d_b1.mem", b_D1, "Discriminator Bias Layer 1 (3)")
save_hex_file("rom_d_w2.mem", W_D2, "Discriminator Weights Layer 2 (3x1)")
save_hex_file("rom_d_b2.mem", b_D2, "Discriminator Bias Layer 2 (1)")

# ==========================================
# 3. Generate Test Vectors & Expected Output
# ==========================================
# Fungsi Aktivasi (Mirip PWL behavior)
def activation_tanh(x):
    return np.tanh(x)

def activation_sigmoid(x):
    return 1 / (1 + np.exp(-x))

# Buat 5 test case random noise z
num_tests = 5
z_inputs = np.random.uniform(-1, 1, (num_tests, Z_DIM))

print("\n--- Verification Data (Copy to Check) ---")
with open("test_vectors.txt", "w") as f:
    for i in range(num_tests):
        z = z_inputs[i]
        
        # --- Feed Forward Generator (Python Float Reference) ---
        # Layer 1
        # Dot product: Input (1x2) dot W (2x3) + b (3)
        h1_pre = np.dot(z, W_G1) + b_G1
        h1_act = activation_tanh(h1_pre) # Asumsi Hidden pakai Tanh
        
        # Layer 2
        # Dot product: Hidden (1x3) dot W (3x9) + b (9)
        out_pre = np.dot(h1_act, W_G2) + b_G2
        out_pixel = activation_sigmoid(out_pre) # Output image pakai Sigmoid (0-1)
        
        # Format Log untuk Debugging
        log_str = f"Test Case {i}:\n"
        log_str += f"  Input Z (Float): {z}\n"
        log_str += f"  Input Z (Hex)  : {[float_to_hex(val) for val in z]}\n"
        log_str += f"  L1 Pre-Act     : {h1_pre}\n"
        log_str += f"  L1 Post-Act    : {h1_act}\n"
        log_str += f"  Output Pixel   : {out_pixel}\n"
        log_str += f"  Output Hex     : {[float_to_hex(val) for val in out_pixel]}\n"
        print(log_str)
        f.write(log_str + "\n")

    # Simpan input Z ke file hex agar bisa di load testbench
    save_hex_file("input_z.mem", z_inputs)

print("Selesai. File .mem siap digunakan untuk inisialisasi ROM Verilog.")