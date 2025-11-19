#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import random
import argparse
import shutil
from pathlib import Path
from typing import List, Tuple, Optional


def load_actions_line(ep_dir: Path, actions_filename: str) -> Optional[str]:
    """Load actions=[...] line from actions.txt"""
    p = ep_dir / actions_filename
    if not p.exists():
        return None
    try:
        line = p.read_text(encoding="utf-8").strip()
        return line if line else None
    except Exception:
        return None


def augment_instruction_with_actions(instruction: str, actions_line: str) -> str:
    """Append actions to instruction if not already present"""
    if not actions_line or "actions=[" in instruction:
        return instruction
    
    if instruction.strip():
        return instruction.rstrip() + "\n" + actions_line
    return actions_line


def discover_episodes(root: Path) -> List[Tuple[str, Path]]:
    """
    Find episodes in:
      1) root/<dataset_name>/episode_*/
      2) root/episode_*/ (fallback)
    Returns: [(dataset_name, episode_path), ...]
    """
    out = []
    found_any = False
    
    # Try dataset/episode_* structure
    for ds_dir in sorted(root.iterdir()):
        if ds_dir.is_dir():
            eps = sorted([p for p in ds_dir.glob("episode_*") if p.is_dir()])
            if eps:
                found_any = True
                for ep in eps:
                    out.append((ds_dir.name, ep))
    
    if found_any:
        return out
    
    # Fallback: episodes directly in root
    eps = sorted([p for p in root.glob("episode_*") if p.is_dir()])
    for ep in eps:
        out.append((root.name or "default", ep))
    
    return out


def create_video_sample(system_msg: str, instruction: str, video_path: str, 
                       bt_xml: str, dataset_id: str, episode_id: str) -> dict:
    """Create a training sample with video"""
    content = [
        {"type": "text", "text": system_msg}
    ]
    
    if instruction.strip():
        content.append({"type": "text", "text": f"INSTRUCTION: {instruction}"})
    
    content.append({"type": "video", "path": video_path})
    
    return {
        "messages": [
            {"role": "user", "content": content},
            {"role": "assistant", "content": [{"type": "text", "text": bt_xml}]}
        ],
        "meta": {
            "dataset_id": dataset_id,
            "episode_id": episode_id,
            "type": "video"
        }
    }


def create_image_sample(system_msg: str, instruction: str, image_path: str,
                       bt_xml: str, dataset_id: str, episode_id: str, local_id: str) -> dict:
    """Create a training sample with image"""
    content = [
        {"type": "text", "text": system_msg}
    ]
    
    if instruction.strip():
        content.append({"type": "text", "text": f"INSTRUCTION: {instruction}"})
    
    content.append({"type": "image", "path": image_path})
    
    return {
        "messages": [
            {"role": "user", "content": content},
            {"role": "assistant", "content": [{"type": "text", "text": bt_xml}]}
        ],
        "meta": {
            "dataset_id": dataset_id,
            "episode_id": episode_id,
            "local_id": local_id,
            "type": "image"
        }
    }


def process_episode(ep_dir: Path, dataset_id: str, args, split_dir: Path, 
                   episodes_root: Path) -> List[dict]:
    """
    Process one episode and return list of samples.
    
    Returns:
        - 1 sample with video + full BT
        - N samples with local images + same full BT (if --enable-locals)
    """
    samples = []
    
    # Load metadata
    meta_path = ep_dir / args.meta_filename
    if not meta_path.exists():
        return samples
    
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return samples
    
    # Load BT XML
    xml_path = ep_dir / args.xml_filename
    if not xml_path.exists():
        return samples
    
    bt_xml = xml_path.read_text(encoding="utf-8").strip()
    
    # Get instruction
    instruction = meta.get("task_instruction", "")
    
    # Apply instruction dropout
    if args.dropout_ratio > 0 and random.random() < args.dropout_ratio:
        instruction = ""
    
    # Load and append actions
    actions_line = load_actions_line(ep_dir, args.actions_filename)
    if actions_line:
        instruction = augment_instruction_with_actions(instruction, actions_line)
    
    # System message
    system_msg = (
        "You are a BehaviorTree.CPP code generator.\n"
        "CONSTRAINTS:\n"
        "- Always ground your decisions in the PROVIDED MEDIA (video frames or images).\n"
        "- Output ONLY one valid BehaviorTree.CPP XML tree.\n"
        "- Do NOT add explanations, comments, or markdown."
    )
    
    # ========================================================================
    # 1. VIDEO SAMPLE
    # ========================================================================
    video_path = ep_dir / args.video_filename
    if video_path.exists():
        if args.no_copy_video:
            video_field = str(video_path.resolve())
        else:
            dest = split_dir / args.videos_subdir / dataset_id / ep_dir.name / args.video_filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(video_path, dest)
            video_field = str(dest.relative_to(split_dir))
        
        samples.append(create_video_sample(
            system_msg, instruction, video_field, bt_xml, dataset_id, ep_dir.name
        ))
    
    # ========================================================================
    # 2. LOCAL IMAGE SAMPLES (with SAME full BT)
    # ========================================================================
    if args.enable_locals:
        locals_dir = ep_dir / args.locals_dirname
        if locals_dir.exists() and locals_dir.is_dir():
            for local_dir in sorted(locals_dir.iterdir()):
                if not local_dir.is_dir():
                    continue
                
                # Find images in this local directory
                images = sorted(local_dir.glob(args.local_image_glob))
                
                for img in images:
                    if args.no_copy_image:
                        image_field = str(img.resolve())
                    else:
                        rel_path = img.relative_to(episodes_root)
                        dest = split_dir / args.images_subdir / rel_path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(img, dest)
                        image_field = str(dest.relative_to(split_dir))
                    
                    samples.append(create_image_sample(
                        system_msg, instruction, image_field, bt_xml,
                        dataset_id, ep_dir.name, local_dir.name
                    ))
    
    return samples


def main():
    parser = argparse.ArgumentParser(
        description="Build JSONL dataset from robot episodes (video + images)"
    )
    
    # Required
    parser.add_argument("--episodes_root", type=str, required=True,
                       help="Root directory containing episode folders")
    parser.add_argument("--out_root", type=str, required=True,
                       help="Output directory for train/val splits")
    
    # Data split
    parser.add_argument("--train_ratio", type=float, default=0.9,
                       help="Fraction of data for training (default: 0.9)")
    parser.add_argument("--shuffle_seed", type=int, default=42)
    parser.add_argument("--limit", type=int, default=0,
                       help="Process only first N episodes (0=all)")
    
    # File names
    parser.add_argument("--meta_filename", type=str, default="meta.json")
    parser.add_argument("--xml_filename", type=str, default="bt.xml")
    parser.add_argument("--video_filename", type=str, default="contact_video.mp4")
    parser.add_argument("--actions_filename", type=str, default="actions.txt")
    parser.add_argument("--jsonl_name", type=str, default="data.jsonl")
    
    # Video options
    parser.add_argument("--videos_subdir", type=str, default="videos")
    parser.add_argument("--no-copy-video", action="store_true",
                       help="Use absolute paths instead of copying videos")
    
    # Local images (data augmentation)
    parser.add_argument("--enable-locals", action="store_true",
                       help="Also create samples from local images with same BT")
    parser.add_argument("--locals_dirname", type=str, default="locals")
    parser.add_argument("--local_image_glob", type=str, default="frame_*.jpg",
                       help="Pattern to find images in local directories")
    parser.add_argument("--images_subdir", type=str, default="images")
    parser.add_argument("--no-copy-image", action="store_true",
                       help="Use absolute paths instead of copying images")
    
    # Visual grounding
    parser.add_argument("--dropout_ratio", type=float, default=0.0,
                       help="Probability to drop instruction text (force visual grounding)")
    
    args = parser.parse_args()
    
    # Setup paths
    episodes_root = Path(args.episodes_root).resolve()
    out_root = Path(args.out_root).resolve()
    train_dir = out_root / "train"
    val_dir = out_root / "val"
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)
    
    # Discover episodes
    all_episodes = discover_episodes(episodes_root)
    if not all_episodes:
        raise SystemExit(f"No episodes found in: {episodes_root}")
    
    print(f"Found {len(all_episodes)} episodes")
    
    # Shuffle and limit
    random.Random(args.shuffle_seed).shuffle(all_episodes)
    if args.limit > 0:
        all_episodes = all_episodes[:args.limit]
        print(f"Limited to {args.limit} episodes")
    
    # Split train/val
    n_train = int(len(all_episodes) * args.train_ratio)
    train_episodes = all_episodes[:n_train]
    val_episodes = all_episodes[n_train:]
    
    print(f"Train: {len(train_episodes)} episodes")
    print(f"Val: {len(val_episodes)} episodes")
    
    # Process splits
    def process_split(episodes: List[Tuple[str, Path]], split_dir: Path):
        jsonl_path = split_dir / args.jsonl_name
        total_samples = 0
        
        with jsonl_path.open("w", encoding="utf-8") as f:
            for dataset_id, ep_dir in episodes:
                samples = process_episode(ep_dir, dataset_id, args, split_dir, episodes_root)
                for sample in samples:
                    f.write(json.dumps(sample, ensure_ascii=False) + "\n")
                    total_samples += 1
        
        return total_samples
    
    print("\nProcessing train split...")
    train_samples = process_split(train_episodes, train_dir)
    
    print("Processing val split...")
    val_samples = process_split(val_episodes, val_dir)
    
    # Summary
    print("\n" + "="*60)
    print("✓ Dataset created successfully!")
    print("="*60)
    print(f"Train: {train_samples} samples in {train_dir / args.jsonl_name}")
    print(f"Val: {val_samples} samples in {val_dir / args.jsonl_name}")
    
    if not args.no_copy_video:
        print(f"Videos: {train_dir / args.videos_subdir}")
    
    if args.enable_locals and not args.no_copy_image:
        print(f"Images: {train_dir / args.images_subdir}")
    
    if args.dropout_ratio > 0:
        print(f"Instruction dropout: {args.dropout_ratio*100:.0f}% of samples")
    
    print("="*60)


if __name__ == "__main__":
    main()
