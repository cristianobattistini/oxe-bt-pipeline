"""
OXE → Triplet Builder (RLDS-aligned) — multi-dataset config.
Usa la semantica OXE: episodi con campo 'steps'.
"""

# Puoi lasciare 'dataset' vuoto quando usi 'datasets'.
dataset  = ""

# Dataset reali (usa questi nomi TFDS; se la tua copia locale è registrata, funzionano).
# In alcuni rilasci i PR2/xarm compaiono come *_converted_externally_to_rlds/0.1.0.
# Se uno dei nomi non viene risolto, prova a sostituirlo con la variante *_converted_externally_to_rlds/0.1.0.
datasets = [
    "columbia_cairlab_pusht_real/0.1.0",
    "utokyo_pr2_opening_fridge/0.1.0",
    "utokyo_pr2_tabletop_manipulation/0.1.0",
    "utokyo_xarm_pick_and_place/0.1.0",
    "cmu_stretch/0.1.0",
    # "utokyo_pr2_opening_fridge_converted_externally_to_rlds/0.1.0",
    # "utokyo_pr2_tabletop_manipulation_converted_externally_to_rlds/0.1.0",
    # "utokyo_xarm_pick_and_place_converted_externally_to_rlds/0.1.0",
]

# Subset rapido per prove (puoi aumentare in seguito)
split = "train[:100%]"

# Output root
out_root = "out"

# Chiavi RLDS di default
image_key = "steps/observation/image"
instruction_key = "natural_language_instruction"

# Override per dataset specifici (se differiscono dalle chiavi di default)
dataset_keys = {
    "columbia_cairlab_pusht_real/0.1.0": ("steps/observation/image", "natural_language_instruction"),
    "utokyo_pr2_opening_fridge/0.1.0": ("observation/image", "language_instruction"),
    "utokyo_pr2_tabletop_manipulation/0.1.0": ("observation/image", "language_instruction"),
    "utokyo_xarm_pick_and_place/0.1.0": ("observation/image", "language_instruction"),
    "cmu_stretch/0.1.0": ("observation/image", "language_instruction"),
}


# Quanti frame max per episodio (GIF inclusa se ≥2)
max_frames = 100

# Limite episodi per dataset (fase di prova)
limit_episodes_per_dataset = 10

# Soglie (per step successivi)
eps_pos = 0.02
eps_rot = 0.087
delta_move = 1e-3


tfds_data_dir = "/home/kcbat/tensorflow_datasets"
