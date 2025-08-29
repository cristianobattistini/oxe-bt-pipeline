import os
from pathlib import Path
from typing import List

import tensorflow_datasets as tfds
from PIL import Image
import numpy as np
import json

def dataset2path(dataset_name: str) -> str:
    """
    Map dataset name to its correct GCS path and version.
    """
    if dataset_name == 'robo_net':
        version = '1.0.0'
    elif dataset_name == 'language_table':
        version = '0.0.1'
    else:
        version = '0.1.0'
    return f'gs://gresearch/robotics/{dataset_name}/{version}'

def load_oxe_dataset(dataset_name: str, split: str = 'train[:3]') -> List[dict]:
    """
    Load a small number of episodes from a specific Open-X-Embodiment dataset.
    
    Args:
        dataset_name (str): Name of the dataset (e.g., 'language_table').
        split (str): TFDS split string (e.g., 'train[:3]').

    Returns:
        List of episodes as dictionaries.
    """
    builder_path = dataset2path(dataset_name)
    builder = tfds.builder_from_directory(builder_dir=builder_path)
    dataset = builder.as_dataset(split=split)
    return list(tfds.as_numpy(dataset))

def save_episode_to_disk(episode: dict, out_dir: str, display_key: str = 'image'):
    """
    Save one episode to disk as raw frames and instruction (if available).

    Args:
        episode (dict): An episode from the dataset.
        out_dir (str): Output directory path.
        display_key (str): Key in observation to extract frame images.
    """
    os.makedirs(out_dir, exist_ok=True)
    frame_dir = Path(out_dir) / 'raw_frames'
    frame_dir.mkdir(exist_ok=True, parents=True)

    for i, step in enumerate(episode['steps']):
        # Save image frame (if exists)
        obs = step.get('observation', {})
        if display_key in obs:
            img = Image.fromarray(obs[display_key])
            img.save(frame_dir / f'frame_{i:04d}.jpg')

    # Save language instruction (if available)
    instruction = episode.get('language_instruction')
    if instruction:
        with open(Path(out_dir) / 'instruction.txt', 'w') as f:
            f.write(instruction)

    # Save episode metadata
    with open(Path(out_dir) / 'episode_meta.json', 'w') as f:
        json.dump({k: str(type(v)) for k, v in episode.items()}, f, indent=2)

# Example usage (in another script or notebook):
episodes = load_oxe_dataset('language_table', split='train[:2]')
for idx, ep in enumerate(episodes):
    save_episode_to_disk(ep, f'sample_data/episode_{idx:03d}')
