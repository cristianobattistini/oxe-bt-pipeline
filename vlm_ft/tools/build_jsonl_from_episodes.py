import os
import json
import shutil
import random
from pathlib import Path
from typing import List

import argparse

def build_full_user_text(system_msg, instruction, actions=None):
    parts = []
    if system_msg.strip():
        parts.append(system_msg.strip())
    if instruction.strip():
        parts.append(instruction.strip())
    if actions and actions.strip():
        parts.append(actions.strip())
    return "\n".join(parts)

def find_episodes(dataset_root: Path) -> List[Path]:
    # Supporta più dataset nella root (come austin_buds_dataset_converted_externally_xxx)
    return sorted(ep for ep in dataset_root.rglob("episode_*") if ep.is_dir())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", required=True, help="Cartella root dei dataset (es: data/dataset)")
    parser.add_argument("--output-root", required=True, help="Cartella di destinazione finale (es: output/)")
    parser.add_argument("--frames-dirname", default="sampled_frames", help="Sottocartella dei frame")
    parser.add_argument("--frames-glob", default="frame_*.jpg", help="Pattern per i frame")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--val-ratio", type=float, default=0.1, help="Proporzione validation [0-1]")
    parser.add_argument("--actions-filename", default="actions.txt", help="Nome file azioni opzionale")
    args = parser.parse_args()

    random.seed(args.seed)
    dataset_root = Path(args.dataset_root).resolve()
    output_root = Path(args.output_root).resolve()

    episodes = find_episodes(dataset_root)
    episodes = [ep for ep in episodes if (ep / args.frames_dirname).exists()]

    print(f"Found {len(episodes)} episodes.")

    # Shuffle e split PER EPISODIO (robustezza!)
    random.shuffle(episodes)
    split_n = int(len(episodes) * (1 - args.val_ratio))
    train_episodes = episodes[:split_n]
    val_episodes = episodes[split_n:]

    splits = [("train", train_episodes), ("val", val_episodes)]

    for split_name, split_episodes in splits:
        split_dir = output_root / split_name
        images_dir = split_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        data_jsonl = split_dir / "data.jsonl"

        total_samples = 0

        with data_jsonl.open("w", encoding="utf-8") as f:
            for ep_dir in split_episodes:
                # Dataset root per path relativo
                dataset_subroot = ep_dir.relative_to(dataset_root).parts[0]  # Es: austin_buds_dataset_converted_externally_xyz
                rel_episode = ep_dir.relative_to(dataset_root)

                # Lettura file txt/xml
                system_msg = (ep_dir / "system_message.txt").read_text(encoding="utf-8").strip() if (ep_dir / "system_message.txt").exists() else ""
                instruction = (ep_dir / "instruction.txt").read_text(encoding="utf-8").strip() if (ep_dir / "instruction.txt").exists() else ""
                actions = (ep_dir / args.actions_filename).read_text(encoding="utf-8").strip() if (ep_dir / args.actions_filename).exists() else ""
                bt_xml = (ep_dir / "bt.xml").read_text(encoding="utf-8").strip() if (ep_dir / "bt.xml").exists() else None
                assert bt_xml, f"Missing bt.xml in {ep_dir}"

                frames_dir = ep_dir / args.frames_dirname
                frame_list = sorted(frames_dir.glob(args.frames_glob))

                for frame_path in frame_list:
                    # Calcola path relativo dentro images/
                    rel_img_path = rel_episode / frame_path.name     # episode_xx/frame_0001.jpg
                    dest_img_path = images_dir / rel_img_path        # full path in output

                    dest_img_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(frame_path, dest_img_path)

                    # Costruisci testo completo
                    user_text = build_full_user_text(system_msg, instruction, actions)
                    image_field = f"images/{rel_img_path.as_posix()}"

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
                    f.write(json.dumps(sample, ensure_ascii=False) + "\n")
                    total_samples += 1

        print(f"{split_name}: {total_samples} samples ({len(split_episodes)} episodes) written to {data_jsonl}")

if __name__ == "__main__":
    main()
