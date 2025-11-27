#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os
import json
import random
import argparse
import shutil
from pathlib import Path
from collections import defaultdict


def augment_instruction_with_actions(instruction: str, actions_line: str) -> str:
    """
    Append actions to instruction if not already present and add a constraint reminder.
    """
    reminder = (
        "\nCONSTRAINT: Only the actions listed in the array below "
        "can be used in the behavior tree. Do NOT invent or add any other actions."
    )
    if not actions_line or "actions=[" in instruction:
        return instruction
    if instruction.strip():
        return instruction.rstrip() + "\n" + actions_line + reminder
    return actions_line + reminder


def find_first_frame(sampled_frames_dir: Path) -> Path:
    """
    Trova il primo frame provando diversi pattern:
    - frame_0000.jpg (4 cifre)
    - frame_000.jpg (3 cifre)
    - frame_00.jpg (2 cifre)
    - frame_0.jpg (1 cifra)
    Restituisce il primo che trova, None se nessuno esiste.
    """
    if not sampled_frames_dir.exists():
        return None
    
    # Pattern da provare in ordine di preferenza
    patterns = [
        "frame_0000.jpg",
        "frame_000.jpg",
        "frame_00.jpg",
        "frame_0.jpg"
    ]
    
    for pattern in patterns:
        candidate = sampled_frames_dir / pattern
        if candidate.exists():
            return candidate
    
    return None


def process_episode(ep_dir: Path, args, split_dir: Path, episodes_root: Path) -> tuple:
    """
    Returns: (samples_list, skip_reason_or_None)
    """
    samples = []


    # Load metadata
    meta_path = ep_dir / args.meta_filename
    if not meta_path.exists():
        return samples, "missing meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as e:
        return samples, f"corrupted meta.json: {str(e)[:50]}"


    # Load BT XML
    xml_path = ep_dir / args.xml_filename
    if not xml_path.exists():
        return samples, "missing bt.xml"
    
    try:
        bt_xml = xml_path.read_text(encoding="utf-8").strip()
    except Exception as e:
        return samples, f"corrupted bt.xml: {str(e)[:50]}"


    # Get instruction from meta
    instruction = meta.get("task_instruction", "")


    # Apply instruction dropout (optional, for data augmentation)
    if args.dropout_ratio > 0 and random.random() < args.dropout_ratio:
        instruction = ""


    # Load and append actions (if exists)
    actions_path = ep_dir / args.actions_filename
    actions_line = actions_path.read_text(encoding="utf-8").strip() if actions_path.exists() else ""
    if actions_line:
        instruction = augment_instruction_with_actions(instruction, actions_line)


    # System message (identical for all episodes)
    system_msg = (
        "You are a BehaviorTree.CPP code generator.\n"
        "CONSTRAINTS:\n"
        "- Always ground your decisions in the PROVIDED MEDIA (video frames or images).\n"
        "- Output ONLY one valid BehaviorTree.CPP XML tree.\n"
        "- Do NOT add explanations, comments, or markdown."
    )


    # ------ FIND FIRST FRAME WITH FLEXIBLE PATTERN ------
    sampled_frames_dir = ep_dir / "sampled_frames"
    first_frame = find_first_frame(sampled_frames_dir)
    
    if first_frame is None:
        if not sampled_frames_dir.exists():
            return samples, "missing sampled_frames/ directory"
        else:
            return samples, "missing frame_0*.jpg (no frame_0.jpg, frame_00.jpg, frame_000.jpg, or frame_0000.jpg found)"


    # Calculate output image path (always normalize to frame_0000.jpg in output)
    rel_episode = ep_dir.relative_to(episodes_root)
    rel_img_path = rel_episode / "sampled_frames" / "frame_0000.jpg"
    dest_img_path = split_dir / "images" / rel_img_path
    dest_img_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(first_frame, dest_img_path)
    image_field = f"images/{rel_img_path.as_posix()}"


    # Build user text block
    parts = [system_msg]
    if instruction.strip():
        parts.append(f"INSTRUCTION: {instruction.strip()}")
    user_text = "\n".join(parts)


    sample = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image", "image": image_field}
                ]
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": bt_xml}
                ]
            }
        ]
    }
    samples.append(sample)
    return samples, None  # Success!


def main():
    parser = argparse.ArgumentParser(description="Build JSONL dataset in Unsloth Vision style (initial frame only)")
    parser.add_argument("--episodes_root", type=str, required=True, help="Root directory with episodes and meta.json")
    parser.add_argument("--out_root", type=str, required=True, help="Output root dir for train/val splits")
    parser.add_argument("--meta_filename", type=str, default="meta.json")
    parser.add_argument("--xml_filename", type=str, default="bt.xml")
    parser.add_argument("--actions_filename", type=str, default="actions.txt")
    parser.add_argument("--jsonl_name", type=str, default="data.jsonl")
    parser.add_argument("--train_ratio", type=float, default=0.9)
    parser.add_argument("--shuffle_seed", type=int, default=42)
    parser.add_argument("--dropout_ratio", type=float, default=0.0)
    args = parser.parse_args()


    episodes_root = Path(args.episodes_root).resolve()
    out_root = Path(args.out_root).resolve()
    train_dir = out_root / "train"
    val_dir = out_root / "val"
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)


    # Discover episodes (supports dataset_name/episode_* and fallback)
    all_episodes = []
    for ds_dir in sorted(episodes_root.iterdir()):
        if ds_dir.is_dir():
            eps = sorted([p for p in ds_dir.glob("episode_*") if p.is_dir()])
            for ep in eps:
                all_episodes.append(ep)
    if not all_episodes:
        # Fallback: episodes directly in root
        eps = sorted([p for p in episodes_root.glob("episode_*") if p.is_dir()])
        all_episodes.extend(eps)


    print(f"Found {len(all_episodes)} episodes.")


    # Shuffle and split PER episodio
    random.Random(args.shuffle_seed).shuffle(all_episodes)
    n_train = int(len(all_episodes) * args.train_ratio)
    train_episodes = all_episodes[:n_train]
    val_episodes = all_episodes[n_train:]


    def process_split(episodes, split_dir, split_name):
        jsonl_path = split_dir / args.jsonl_name
        total_samples = 0
        skip_details = defaultdict(list)  # reason -> list of episode paths
        
        with jsonl_path.open("w", encoding="utf-8") as f:
            for ep_dir in episodes:
                samples, skip_reason = process_episode(ep_dir, args, split_dir, episodes_root)
                
                if skip_reason:
                    skip_details[skip_reason].append(str(ep_dir.relative_to(episodes_root)))
                
                for sample in samples:
                    f.write(json.dumps(sample, ensure_ascii=False) + "\n")
                    total_samples += 1
        
        # Print detailed skip report
        total_skipped = sum(len(eps) for eps in skip_details.values())
        if total_skipped > 0:
            print(f"\n⚠️  Skipped {total_skipped} episodes in {split_name} split:")
            for reason, ep_list in sorted(skip_details.items()):
                print(f"\n  📌 {reason} ({len(ep_list)} episodes):")
                for ep in ep_list[:10]:  # Show first 10
                    print(f"     - {ep}")
                if len(ep_list) > 10:
                    print(f"     ... and {len(ep_list) - 10} more")
        
        return total_samples


    print("\nProcessing train split...")
    train_samples = process_split(train_episodes, train_dir, "train")
    
    print("\nProcessing val split...")
    val_samples = process_split(val_episodes, val_dir, "val")


    print("\n" + "=" * 60)
    print("✓ Dataset created successfully!")
    print("=" * 60)
    print(f"Train: {train_samples} samples in {train_dir / args.jsonl_name}")
    print(f"Val: {val_samples} samples in {val_dir / args.jsonl_name}")
    print("=" * 60)


if __name__ == "__main__":
    main()
