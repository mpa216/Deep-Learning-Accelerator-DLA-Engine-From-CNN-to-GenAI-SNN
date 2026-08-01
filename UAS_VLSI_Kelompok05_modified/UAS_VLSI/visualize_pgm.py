import numpy as np
import matplotlib.pyplot as plt
import glob
import os

def parse_pgm(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()
    
    # Filter baris komentar dan ambil data
    data_lines = [l.strip() for l in lines if not l.startswith('#') and l.strip()]
    
    # Header check (P2)
    if data_lines[0] != 'P2':
        raise ValueError("Format bukan PGM ASCII (P2)")
    
    # Ambil dimensi (biasanya baris ke-2: "3 3")
    dims = data_lines[1].split()
    width, height = int(dims[0]), int(dims[1])
    
    # Ambil nilai max (255)
    max_val = int(data_lines[2])
    
    # Ambil data pixel (sisanya)
    pixel_data = []
    for line in data_lines[3:]:
        pixel_data.extend([int(x) for x in line.split()])
    
    return np.array(pixel_data).reshape((height, width))

# Cari semua file gen_img_*.pgm
pgm_files = sorted(glob.glob("gen_img_*.pgm"))

if not pgm_files:
    print("Tidak ditemukan file .pgm! Pastikan simulasi Verilog sudah dijalankan.")
    exit()

# Plotting
plt.figure(figsize=(10, 5))

for i, pgm_file in enumerate(pgm_files):
    img_data = parse_pgm(pgm_file)
    
    # Subplot untuk setiap gambar
    plt.subplot(1, len(pgm_files), i+1)
    
    # Tampilkan dengan interpolation='nearest' agar pixel terlihat kotak tegas
    plt.imshow(img_data, cmap='gray', vmin=0, vmax=255, interpolation='nearest')
    plt.title(f"Output Verilog #{i}\n({pgm_file})")
    plt.axis('off')

plt.tight_layout()
plt.savefig("verilog_result_upscaled.png")
print("Gambar berhasil disimpan sebagai 'verilog_result_upscaled.png'")
plt.show()