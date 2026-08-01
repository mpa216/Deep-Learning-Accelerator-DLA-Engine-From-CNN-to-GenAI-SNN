import matplotlib.pyplot as plt
import glob
import os

def read_pgm(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()
    
    # Hapus comments dan whitespace
    data = []
    for line in lines:
        for part in line.split():
            if '#' not in part:
                data.append(part)
    
    # Header PGM: P2, Width, Height, MaxVal
    # Data dimulai dari index 4
    width = int(data[1])
    height = int(data[2])
    pixels = [int(p) for p in data[4:]]
    
    return pixels, width, height

# Cari semua file .pgm
files = sorted(glob.glob("gen_img_*.pgm"))

if not files:
    print("Tidak ada file .pgm ditemukan!")
else:
    plt.figure(figsize=(10, 2))
    
    for i, fname in enumerate(files):
        pixels, w, h = read_pgm(fname)
        
        # Reshape array 1D jadi 2D untuk ditampilkan
        # (Matplotlib butuh list of lists)
        img_matrix = [pixels[j*w : (j+1)*w] for j in range(h)]
        
        plt.subplot(1, len(files), i+1)
        plt.imshow(img_matrix, cmap='gray', vmin=0, vmax=255)
        plt.title(fname)
        plt.axis('off')

    print("Menampilkan hasil...")
    plt.show()