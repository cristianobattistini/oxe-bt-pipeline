import argparse
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import sys
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embodied_bt_brain.agentic_teacher import AgenticTeacherLoop
from embodied_bt_brain.agentic_teacher.agents import (
    ArchitectAgent,
    ConformanceAgent,
    CriticAgent,
    FeasibilityAgent,
    IdAssignerAgent,
    IdPatchabilityAgent,
    RobustnessAgent,
    SceneAnalysisAgent,
    SchemaAgent,
    ScorerAgent,
    SubtreeEnablementAgent,
)
from embodied_bt_brain.agentic_teacher.teacher_loop import SkipEpisode
from embodied_bt_brain.agentic_teacher.llm_client import AzureLLMClient
from embodied_bt_brain.dataset_proposer_agentic.input_sources.oxe_episodes import iter_oxe_episodes
from embodied_bt_brain.dataset_proposer_agentic.output_writers.audit_logger import AuditLogger
from embodied_bt_brain.dataset_proposer_agentic.output_writers.bt_tree_writer import BtFolderWriter
from embodied_bt_brain.dataset_proposer_agentic.output_writers.dataset_writer import JsonlWriter
from embodied_bt_brain.dataset_proposer_agentic.utils.instruction_parser import normalize_instruction
from embodied_bt_brain.primitive_library.validator import load_default_pal_spec


def build_agents(model: Optional[str], *, enable_feasibility: bool, enable_scene_analysis: bool, enable_critic: bool, enable_id_patchability_llm: bool) -> dict:
    pal_spec = load_default_pal_spec()
    llm_client = AzureLLMClient(model=model)
    agents = {
        "architect": ArchitectAgent(llm_client, model=model),
        "feasibility": FeasibilityAgent(enabled=enable_feasibility, llm_client=llm_client, model=model),
        "scene_analysis": SceneAnalysisAgent(enabled=enable_scene_analysis, llm_client=llm_client, model=model),
        "conformance": ConformanceAgent(pal_spec, llm_client=llm_client, model=model),
        "schema": SchemaAgent(llm_client=llm_client, model=model),
        "robustness": RobustnessAgent(llm_client=llm_client, model=model),
        "subtree_enablement": SubtreeEnablementAgent(llm_client=llm_client, model=model),
        "id_assigner": IdAssignerAgent(),
        "scorer": ScorerAgent(llm_client=llm_client, model=model),
    }
    if enable_critic:
        agents["critic"] = CriticAgent(llm_client, model=model, max_iterations=2, strict_mode=True)
    if enable_id_patchability_llm:
        agents["id_patchability"] = IdPatchabilityAgent(llm_client=llm_client, model=model)
    return agents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate proposer dataset from OXE episodes.")
    parser.add_argument("--out-root", default="out_temp", help="Path to out_temp directory.")
    parser.add_argument("--output-dir", default="dataset_agentic", help="Output dataset root.")
    parser.add_argument("--limit", type=int, default=None, help="Max episodes to process.")
    parser.add_argument("--datasets", nargs="*", default=None, help="Dataset IDs filter.")
    parser.add_argument(
        "--output-mode",
        choices=["bt", "jsonl"],
        default="bt",
        help="Write BT files or JSONL dataset.",
    )
    parser.add_argument("--copy-images", action="store_true", help="Copy images into output dir.")
    parser.add_argument("--allow-missing-contact-sheet", action="store_true")
    parser.add_argument("--val-ratio", type=float, default=0.0, help="Fraction to send to val split.")
    parser.add_argument("--val-seed", default="pal_v1", help="Seed for deterministic split.")
    parser.add_argument("--log-every", type=int, default=100, help="Log progress every N items.")
    parser.add_argument("--no-resume", action="store_true", help="Do not skip existing episodes.")
    parser.add_argument("--model", default=None, help="Azure OpenAI deployment name.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first error.")
    parser.add_argument("--no-feasibility", action="store_true", help="Disable feasibility pre-check.")
    parser.add_argument("--no-scene-analysis", action="store_true", help="Disable scene analysis pre-step.")
    parser.add_argument("--enable-critic", action="store_true", help="Enable Socratic Critic Agent (max 2 iterations, blocking).")
    parser.add_argument(
        "--id-patchability-llm",
        action="store_true",
        help="Enable an extra LLM step to add IDs (experimental; deterministic id_assigner always runs).",
    )
    parser.add_argument(
        "--dump-intermediate",
        action="store_true",
        help="Write intermediate BT outputs for each agent.",
    )
    parser.add_argument(
        "--tqdm",
        action="store_true",
        help="Show progress bar for episodes.",
    )
    parser.add_argument(
        "--tqdm-agents",
        action="store_true",
        help="Show per-agent progress for each episode.",
    )
    return parser.parse_args()


def _load_existing_ids(data_path: Path) -> Set[Tuple[str, str]]:
    existing: Set[Tuple[str, str]] = set()
    if not data_path.exists():
        return existing
    with data_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            metadata = record.get("metadata", {})
            dataset_id = metadata.get("dataset_id")
            episode_id = metadata.get("episode_id")
            if dataset_id and episode_id:
                existing.add((str(dataset_id), str(episode_id)))
    return existing


def _assign_split(dataset_id: str, episode_id: str, val_ratio: float, seed: str) -> str:
    if val_ratio <= 0.0:
        return "train"
    if val_ratio >= 1.0:
        return "val"
    key = f"{seed}:{dataset_id}:{episode_id}".encode("utf-8")
    digest = hashlib.sha1(key).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF
    return "val" if bucket < val_ratio else "train"


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    require_contact_sheet = not args.allow_missing_contact_sheet
    resume = not args.no_resume
    val_ratio = args.val_ratio
    if val_ratio < 0.0 or val_ratio > 1.0:
        raise ValueError("val-ratio must be between 0 and 1")

    agents = build_agents(
        args.model,
        enable_feasibility=not args.no_feasibility,
        enable_scene_analysis=not args.no_scene_analysis,
        enable_critic=args.enable_critic,
        enable_id_patchability_llm=args.id_patchability_llm,
    )
    teacher = AgenticTeacherLoop(agents)

    writer_train = None
    writer_val = None
    if args.output_mode == "jsonl":
        writer_train = JsonlWriter(args.output_dir, split="train", copy_images=args.copy_images)
        writer_val = JsonlWriter(args.output_dir, split="val", copy_images=args.copy_images)
    else:
        writer_train = BtFolderWriter(args.output_dir, split="train")
        writer_val = BtFolderWriter(args.output_dir, split="val")
    audit_train = AuditLogger(args.output_dir, split="train")
    audit_val = AuditLogger(args.output_dir, split="val")

    existing_ids: Set[Tuple[str, str]] = set()
    if resume and args.output_mode == "jsonl":
        existing_ids |= _load_existing_ids(writer_train.data_path)
        existing_ids |= _load_existing_ids(writer_val.data_path)
        if existing_ids:
            logging.info("resume enabled: found %d existing episodes", len(existing_ids))

    processed = 0
    skipped = 0
    seen = 0
    agent_steps: List[str] = []
    if agents.get("feasibility") is not None:
        agent_steps.append("feasibility")
    if agents.get("scene_analysis") is not None:
        agent_steps.append("scene_analysis")
    agent_steps.append("architect")
    agent_steps += [name for name in teacher.pipeline if agents.get(name) is not None]
    if teacher.enable_post_id_assignment and agents.get("id_assigner") is not None:
        agent_steps.append("id_assigner")
    if agents.get("scorer") is not None:
        agent_steps.append("scorer")

    episodes_iter = iter_oxe_episodes(
        args.out_root,
        datasets=args.datasets,
        require_contact_sheet=require_contact_sheet,
    )
    episodes_bar = None
    if args.tqdm:
        total = args.limit if args.limit is not None else None
        episodes_bar = tqdm(total=total, desc="episodes_processed")

    for episode in episodes_iter:
        seen += 1
        instruction = normalize_instruction(str(episode["instruction"]))
        contact_sheet = episode.get("contact_sheet")
        if not contact_sheet:
            continue

        dataset_id = str(episode["dataset_id"])
        episode_id = str(episode["episode_id"])
        key = (dataset_id, episode_id)
        if resume and args.output_mode == "jsonl" and key in existing_ids:
            skipped += 1
            if args.log_every and skipped % args.log_every == 0:
                logging.info("skipped %d existing episodes", skipped)
            continue

        split = _assign_split(dataset_id, episode_id, val_ratio, args.val_seed)
        writer = writer_val if split == "val" else writer_train
        audit_logger = audit_val if split == "val" else audit_train

        if args.output_mode == "bt" and resume and writer.episode_exists(dataset_id, episode_id):
            skipped += 1
            continue

        try:
            if args.tqdm_agents:
                with tqdm(total=len(agent_steps), desc="agents", leave=False) as agent_bar:
                    result = teacher.generate_bt(
                        instruction,
                        str(contact_sheet),
                        record_steps=args.dump_intermediate,
                        on_agent_step=lambda _: agent_bar.update(1),
                    )
            else:
                result = teacher.generate_bt(
                    instruction,
                    str(contact_sheet),
                    record_steps=args.dump_intermediate,
                )
        except SkipEpisode as exc:
            skipped += 1
            logging.info("skipping %s/%s: %s", dataset_id, episode_id, exc.reason)
            continue
        except Exception as exc:
            logging.exception("failed %s/%s: %s", dataset_id, episode_id, exc)
            if args.fail_fast:
                raise
            continue
        bt_xml = result["bt_xml"]

        if args.output_mode == "jsonl":
            image_path = writer.prepare_image_path(
                str(contact_sheet),
                dataset_id,
                episode_id,
            )

            metadata = {
                "source": "oxe",
                "dataset_id": dataset_id,
                "episode_id": episode_id,
                "verdict": result["verdict"],
                "score": result["score"],
                "split": split,
            }

            record = writer.build_record(
                instruction=instruction,
                image_path=image_path,
                bt_xml=bt_xml,
                metadata=metadata,
            )
            writer.write_record(record)
        else:
            writer.write_episode(
                dataset_id=dataset_id,
                episode_id=episode_id,
                bt_xml=bt_xml,
                contact_sheet_path=str(contact_sheet),
                instruction=instruction,
                steps=result.get("steps") if args.dump_intermediate else None,
            )
        audit_logger.write(
            dataset_id=dataset_id,
            episode_id=episode_id,
            audit_log=result["audit_log"],
            score=result["score"],
            verdict=result["verdict"],
        )
        processed += 1
        if episodes_bar is not None:
            episodes_bar.update(1)
        if args.log_every and processed % args.log_every == 0:
            logging.info(
                "processed=%d skipped=%d seen=%d (last split=%s)",
                processed,
                skipped,
                seen,
                split,
            )
        if args.limit is not None and processed >= args.limit:
            break

    if episodes_bar is not None:
        episodes_bar.close()

    logging.info(
        "done: processed=%d skipped=%d seen=%d val_ratio=%.3f mode=%s",
        processed,
        skipped,
        seen,
        val_ratio,
        args.output_mode,
    )


if __name__ == "__main__":
    main()
