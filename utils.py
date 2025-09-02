import os
import tensorflow_datasets as tfds
from PIL import Image
import numpy as np
import json

from rlds import rlds_metadata

# === CONFIG ===
DATASET_PATH = "C:/Users/Crist/tensorflow_datasets/columbia_cairlab_pusht_real/0.1.0"
OUTPUT_DIR = "out/triplets_columbia"
SPLIT = "train[:3]"  # usa solo 3 episodi per test
IMAGE_SIZE = (256, 256)

# === CREA CARTELLA DI OUTPUT ===
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === CARICAMENTO DATASET ===
builder = tfds.builder_from_directory(DATASET_PATH)
ds = builder.as_dataset(split=SPLIT, shuffle_files=False)

# === PARSING EPISODI CON RLDS ===
episodes = rlds_metadata.get_episodes(ds)

print(f"[INFO] Episodi trovati: {len(episodes)}")

for i, ep in enumerate(episodes):
    steps = ep["steps"]
    metadata = ep.get("episode_metadata", {})

    # === ESTRATTORE: immagine iniziale ===
    first_obs = steps[0]["observation"]
    img_array = first_obs["rgb_static"]  # RGB image (HxWx3), dtype=uint8
    pil_img = Image.fromarray(np.array(img_array))
    pil_img = pil_img.resize(IMAGE_SIZE)
    
    # === PATH DI SALVATAGGIO ===
    img_path = os.path.join(OUTPUT_DIR, f"ep_{i:03d}.jpg")
    json_path = os.path.join(OUTPUT_DIR, f"ep_{i:03d}.json")

    # === ISTRUZIONE ===
    instruction = metadata.get("language_instruction", "No instruction")

    # === AZIONI (primi 5 step per esempio) ===
    actions = []
    for step in steps[:5]:
        action = step["action"]
        actions.append({k: action[k] for k in action})  # copia pulita

    # === SALVATAGGIO ===
    pil_img.save(img_path)

    with open(json_path, "w") as f:
        json.dump({
            "instruction": instruction,
            "actions": actions
        }, f, indent=2)

    print(f"[OK] Episodio {i}: salvato {img_path} + {json_path}")
