import argparse, json
from pathlib import Path
from typing import Optional, List
from .config import PATHS, SUPPORTED_DATASETS, MODEL
from .datasets import list_episodes, slice_episodes
from .pipeline import load_node_library, discover_local_slots, run_local_generation
from .prompts import build_cached_block
from .client_mock import MockLLM
from .client_live import LiveLLM


def main():
    ap = argparse.ArgumentParser(description="Generate local subtrees via GPT-5 Thinking (mock/live)")
    ap.add_argument("--dataset", required=True, choices=SUPPORTED_DATASETS)
    ap.add_argument("--version", default="0.1.0")

    # consenti usare from/to insieme, ma impedisci mixing con --ids
    ap.add_argument("--from", dest="start", type=int)
    ap.add_argument("--to", dest="end", type=int)

    group = ap.add_mutually_exclusive_group()
    group.add_argument("--ids", dest="ids", type=str, help="comma-separated episode numbers, e.g., 1,7,12")

    ap.add_argument("--mode", choices=["mock", "live"], default="mock")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--budget", type=float, default=None, help="guardia di budget per singola chiamata")
    ap.add_argument("--fixture", type=str, default=str((PATHS.project_root/"bt_local_gen"/"fixtures"/"sample_llm_response.txt")))
    ap.add_argument("--dump-prompts", action="store_true", help="salva cached_block, local_prompt e prompt fuso per ogni chiamata")
    ap.add_argument("--print-prompt", action="store_true", help="stampa a stdout il prompt fuso")
    ap.add_argument("--print-max-chars", type=int, default=0, help="limite stampa prompt (0 = completo)")
    ap.add_argument("--model", type=str, help="override del model id (es. gpt-5, gpt-4o, gpt-4o-mini)")

    args = ap.parse_args()

    if args.ids and (args.start or args.end):
        raise SystemExit("usa o --ids oppure --from/--to, non entrambi")

    # Override modello se richiesto (MODEL è dataclass frozen: usa object.__setattr__)
    if args.model:
        object.__setattr__(MODEL, "name", args.model)
        
    episodes = list_episodes(args.dataset)
    if not episodes:
        raise SystemExit("nessun episodio trovato")

    if args.ids:
        ids = [int(x) for x in args.ids.split(",") if x.strip()]
    else:
        ids = None

    selected = slice_episodes(episodes, args.start, args.end, ids)

    node_library = load_node_library(PATHS.node_library)
    cached_block = build_cached_block(node_library)

    if args.mode == "mock":
        llm = MockLLM(Path(args.fixture))
    else:
        llm = LiveLLM()

    stats = {"episodes": 0, "calls": 0, "cost_usd": 0.0}

    for ep in selected:
        slots = discover_local_slots(ep.path)
        if not slots:
            continue
        for io in slots:
            # directory dump per questo slot (se richiesto)
            dump_dir = None
            if args.dump_prompts:
                dump_dir = PATHS.logs_root / args.dataset / ep.episode_id / io.local_dir.name
            res = run_local_generation(
                io,
                node_library=node_library,
                llm=llm,
                mode=args.mode,
                overwrite=args.overwrite,
                budget_guard=args.budget,
                cached_block=cached_block,
                dump_dir=dump_dir,
                echo_prompt=args.print_prompt,
                echo_max_chars=args.print_max_chars,            
            )
            if not res.get("skipped"):
                stats["calls"] += 1
                stats["cost_usd"] += float(res.get("cost_usd", 0.0))
        stats["episodes"] += 1

    print(json.dumps(stats, indent=2))

if __name__ == "__main__":
    main()


# python -m bt_local_gen.cli \
#   --mode live \
#   --dataset columbia_cairlab_pusht_real_0.1.0 \
#   --from 11 --to 11 \
#   --model gpt-5 \
#   --dry-run \
#   --print-prompt --print-max-chars 1200 \
#   --dump-prompts
