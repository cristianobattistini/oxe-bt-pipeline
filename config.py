"""
Minimal configuration file for OXE → Triplet Builder.
Contains default parameters and thresholds.
"""

# Dataset settings
dataset = "language_table"
split = "train[:1]"
out_root = "out"

# Quale campo contiene l'immagine e l'istruzione nel dataset scelto
image_key = "image"                          # es. "image" oppure "observation.image" se avessi una struttura annidata
instruction_key = "natural_language_instruction"

# Visualizzazione
max_frames = 8

# Soglie (usate in step successivi)
eps_pos = 0.02
eps_rot = 0.087
delta_move = 1e-3
