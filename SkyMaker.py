import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image
import numpy as np
import math
import os
import threading
import time
import shutil
import random
import string

FACE_SIZE = 2048
FACE_NAMES = ['right', 'left', 'top', 'bottom', 'front', 'back']

FACE_DIRS = {
    'right':  lambda u, v: [1, -v, -u],
    'left':   lambda u, v: [-1, -v, u],
    'top':    lambda u, v: [u, 1, v],
    'bottom': lambda u, v: [u, -1, -v],
    'front':  lambda u, v: [u, -v, 1],
    'back':   lambda u, v: [-u, -v, -1],
}

def normalize(v):
    norm = math.sqrt(sum(i**2 for i in v))
    return [i / norm for i in v]

def vector_to_uv(vec):
    x, y, z = vec
    lon = math.atan2(z, x)
    lat = math.asin(y)
    u = (lon / math.pi + 1) / 2
    v = (0.5 - lat / math.pi)
    return u, v

def sample_panorama(pano_img, u, v):
    width, height = pano_img.size
    px = int(u * width) % width
    py = int(v * height) % height
    return pano_img.getpixel((px, py))

def generate_face(pano_img, face_name):
    face = Image.new("RGB", (FACE_SIZE, FACE_SIZE))
    for y in range(FACE_SIZE):
        for x in range(FACE_SIZE):
            u = 2 * (x + 0.5) / FACE_SIZE - 1
            v = 2 * (y + 0.5) / FACE_SIZE - 1
            direction = normalize(FACE_DIRS[face_name](u, v))
            pu, pv = vector_to_uv(direction)
            color = sample_panorama(pano_img, pu, pv)
            face.putpixel((x, y), color)
    return face

def mirror_blend_from_middle(img, blend_width):
    width, height = img.size
    mid = width // 2

    left_half = img.crop((0, 0, mid, height))
    mirrored = left_half.transpose(Image.FLIP_LEFT_RIGHT)

    base = img.copy()
    overlay = img.copy()
    overlay.paste(mirrored, (mid, 0))

    mask = np.zeros((height, width), dtype=np.float32)

    for x in range(blend_width):
        alpha = 1 - (x / blend_width)
        if mid + x < width:
            mask[:, mid + x] = alpha

    alpha_mask = Image.fromarray((mask * 255).astype(np.uint8)).convert("L")
    result = Image.composite(overlay, base, alpha_mask)
    return result

def combine_faces_into_template(output_path, faces_dir):
    tile_size = FACE_SIZE
    width, height = tile_size * 3, tile_size * 2
    template = Image.new("RGB", (width, height))

    layout = {
        'down':  (0, 0),
        'up':    (tile_size, 0),
        'east':  (tile_size * 2, 0),
        'north': (0, tile_size),
        'west':  (tile_size, tile_size),
        'south': (tile_size * 2, tile_size),
    }

    for name, (x, y) in layout.items():
        face_path = os.path.join(faces_dir, f"{name}.png")
        if os.path.exists(face_path):
            face = Image.open(face_path).convert("RGB")
            template.paste(face, (x, y))

    template.save(output_path)

def generate_random_foldername(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def main(pano_path, out_dir, blend_width, progress_callback):
    pano_img = Image.open(pano_path).convert('RGB')
    os.makedirs(out_dir, exist_ok=True)

    name_map = {
        'right': 'east',
        'left': 'west',
        'top': 'up',
        'bottom': 'down',
        'front': 'south',
        'back': 'north',
    }

    total_steps = len(FACE_NAMES) + 1 
    current_step = 0

    for face in FACE_NAMES:
        img = generate_face(pano_img, face)

        if face == 'top':
            img = img.rotate(90, expand=True)
        elif face == 'bottom':
            img = img.rotate(-90, expand=True)

        if face in ['top', 'bottom', 'left']:
            img = mirror_blend_from_middle(img, blend_width=blend_width)

        output_path = os.path.join(out_dir, f"{name_map[face]}.png")
        img.save(output_path)

        current_step += 1
        progress_callback(int((current_step / total_steps) * 100))

    output_template = "sky_result.png"
    combine_faces_into_template(output_template, out_dir)
    progress_callback(100)

    src_overlay_dir = "SkyOverlayPack"
    temp_overlay_dir = os.path.join(out_dir, "SkyOverlayPack")

    if os.path.exists(src_overlay_dir):
        shutil.copytree(src_overlay_dir, temp_overlay_dir, dirs_exist_ok=True)
        Image.open(pano_path).convert("RGB").save(os.path.join(temp_overlay_dir, "pack.png"), "PNG")

        target_paths = [
            os.path.join(temp_overlay_dir, "assets", "minecraft", "mcpatcher", "sky", "world0", "cloud1.png"),
            os.path.join(temp_overlay_dir, "assets", "minecraft", "optifine", "sky", "world0", "cloud1.png"),
        ]
        for target_path in target_paths:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.copy("sky_result.png", target_path)

        rnd_folder = generate_random_foldername()
        final_dir = os.path.join(".", rnd_folder)
        os.makedirs(final_dir, exist_ok=True)

        shutil.move(temp_overlay_dir, os.path.join(final_dir, "SkyOverlayPack"))

        try:
            os.remove("sky_result.png")
        except FileNotFoundError:
            pass

        for face_file in name_map.values():
            path = os.path.join(out_dir, f"{face_file}.png")
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

        try:
            os.rmdir(out_dir)
        except OSError:
            print(f"Ordner {out_dir} ist nicht leer oder konnte nicht gelöscht werden.")
    else:
        print("Ordner 'SkyOverlayPack' wurde nicht gefunden.")

root = tk.Tk()
root.title("Skymaker by vuacy")
root.geometry("400x300")

tk.Label(root, text="Smooth Edge Blend Size (Recommended: 200)").pack(pady=5)

blend_values = [str(i) for i in range(50, 501, 10)]
blend_box = ttk.Combobox(root, values=blend_values, state="readonly")
blend_box.set("200")
blend_box.pack(pady=5)

selected_file_label = tk.Label(root, text="No image selected.")
selected_file_label.pack(pady=5)

progress = ttk.Progressbar(root, length=300, mode='determinate')
progress.pack(pady=10)
progress.pack_forget()

selected_file = None

def select_image():
    file = filedialog.askopenfilename(
        title="Select Image",
        filetypes=[("JPEG Dateien", "*.jpg;*.jpeg"), ("PNG Dateien", "*.png"), ("Alle Dateien", "*.*")]
    )
    if file:
        global selected_file
        selected_file = file
        selected_file_label.config(text=f"Selected: {os.path.basename(file)}")
        create_btn.pack(pady=10)

def run_creation():
    blend_width = int(blend_box.get())
    output_folder = "sky_output_layers"

    progress["value"] = 0
    progress.pack()
    create_btn.config(state="disabled")
    select_btn.config(state="disabled")

    def update_progress(value):
        progress["value"] = value
        root.update_idletasks()

    def task():
        main(selected_file, output_folder, blend_width, update_progress)
        time.sleep(0.5)
        root.quit()

    threading.Thread(target=task).start()

select_btn = tk.Button(root, text="Select Image", command=select_image)
select_btn.pack(pady=10)

create_btn = tk.Button(root, text="Create Sky", command=run_creation)

root.mainloop()
