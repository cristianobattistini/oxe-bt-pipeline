from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional
import json
from .settings import PATHS
from .prompts import build_cached_block, build_local_prompt
from .validators import (
    split_two_code_blocks,
    validate_xml,
    parse_and_validate_json,
    recover_xml_json_without_fences,
)
from .caching import cache_tag_for_block  # NEW

@dataclass
class EpisodeIO:
    episode_dir: Path
    local_dir: Path
    frame_path: Path
    prompt_path: Path
    subtree_xml_path: Path
    subtree_json_path: Path

# Placeholder templates per riconoscere file "non toccati"
PLACEHOLDER_XML = (
    '<BehaviorTree ID="MainTree">\n'
    '  <Sequence>\n'
    '    <!-- perceive / align / act / verify -->\n'
    '  </Sequence>\n'
    '</BehaviorTree>\n'
)

PLACEHOLDER_JSON = (
    '{\n'
    '  "frame_index": null,\n'
    '  "local_intent": "",\n'
    '  "assumptions": "",\n'
    '  "bb_read": [],\n'
    '  "bb_write": [],\n'
    '  "coherence_with_global": "",\n'
    '  "format_checks": { "only_known_nodes": true, "only_binned_values": true }\n'
    '}\n'
)

def is_placeholder(path: Path) -> bool:
    if not path.exists():
        return True
    try:
        raw = path.read_text(encoding="utf-8")
        raw = raw.replace('\r\n', '\n').replace('\r', '\n')
        txt = raw if raw.endswith('\n') else raw + '\n'
    except Exception:
        return False
    if path.suffix == ".xml":
        return txt == PLACEHOLDER_XML
    if path.suffix == ".json":
        return txt == PLACEHOLDER_JSON
    return False

def load_node_library(path: Path) -> Dict[str, Any]:
    nl = json.loads(path.read_text(encoding="utf-8"))
    allowed = []
    for k in ("composites", "decorators", "actions", "conditions"):
        if k in nl and isinstance(nl[k], dict):
            allowed.extend(list(nl[k].keys()))
    nl["allowed_ids"] = allowed
    return nl

def discover_local_slots(ep_dir: Path):
    out = []
    for i in (1, 2, 3):
        ldir = ep_dir / "locals" / f"local_{i}"
        if not ldir.exists():
            continue
        frames = sorted(ldir.glob("frame_*.jpg"))
        if not frames:
            continue
        frame = frames[0]
        # accetta local_prompt o local_prompt.md
        prompt = ldir / "local_prompt"
        if not prompt.exists():
            alt = ldir / "local_prompt.md"
            if alt.exists():
                prompt = alt
            else:
                continue
        io = EpisodeIO(
            episode_dir=ep_dir,
            local_dir=ldir,
            frame_path=frame,
            prompt_path=prompt,
            subtree_xml_path=ldir / "subtree_.xml",
            subtree_json_path=ldir / "subtree_.json",
        )
        out.append(io)
    return out

def run_local_generation(io: EpisodeIO,
                         node_library: Dict[str, Any],
                         llm,
                         mode: str = "mock",
                         overwrite: bool = False,
                         budget_guard: Optional[float] = None,
                         cached_block: Optional[str] = None,
                         dump_dir: Optional[Path] = None,      # NEW
                         echo_prompt: bool = False,            # NEW
                         echo_max_chars: int = 0               # NEW
                         ) -> Dict[str, Any]:
    # Sicurezza: non sovrascrivere per errore
    xml_exists = io.subtree_xml_path.exists()
    json_exists = io.subtree_json_path.exists()
    xml_placeholder = is_placeholder(io.subtree_xml_path)
    json_placeholder = is_placeholder(io.subtree_json_path)

    if (not overwrite) and (
        (xml_exists and not xml_placeholder) or (json_exists and not json_placeholder)
    ):
        return {"skipped": True, "reason": "files già presenti (non placeholder)"}

    # Costruzione prompt fuso
    local_prompt_text = io.prompt_path.read_text(encoding="utf-8")
    used_cached = False
    if cached_block and not local_prompt_text.startswith(cached_block[:32]):
        prompt_text = cached_block + "\n" + local_prompt_text
        used_cached = True
    else:
        prompt_text = local_prompt_text

    cache_tag = cache_tag_for_block(cached_block) if cached_block else None

    # Dump di debug (opzionale)
    if dump_dir:
        dump_dir.mkdir(parents=True, exist_ok=True)
        (dump_dir / "cached_block.txt").write_text(cached_block or "", encoding="utf-8")
        (dump_dir / "local_prompt_raw.txt").write_text(local_prompt_text, encoding="utf-8")
        (dump_dir / "prompt_merged.txt").write_text(prompt_text, encoding="utf-8")
        meta_dbg = {
            "used_cached_block": used_cached,
            "cache_tag": cache_tag,
            "prompt_chars": len(prompt_text),
            "image": str(io.frame_path),
            "episode_dir": str(io.episode_dir),
            "local_dir": str(io.local_dir),
        }
        (dump_dir / "prompt_debug.json").write_text(json.dumps(meta_dbg, indent=2), encoding="utf-8")

    if echo_prompt:
        hdr = f"[PROMPT] chars={len(prompt_text)} cached={used_cached} tag={cache_tag}"
        print(hdr)
        if echo_max_chars and len(prompt_text) > echo_max_chars:
            print(prompt_text[:echo_max_chars] + "\n...[troncato]...")
        else:
            print(prompt_text)

    image_bytes = io.frame_path.read_bytes()

    # Chiamata LLM
    if mode == "mock":
        res = llm.complete(prompt_text, image_bytes)
        text = res.text
        input_tokens = res.input_tokens
        output_tokens = res.output_tokens
        cost = res.cost_usd
    else:
        res = llm.complete(prompt_text, image_bytes, cached_block)
        text = res.text
        input_tokens = res.input_tokens
        output_tokens = res.output_tokens
        cost = res.cost_usd
        if budget_guard is not None and cost > budget_guard:
            raise RuntimeError(f"singola chiamata supera la guardia di budget: {cost} > {budget_guard}")

    # Salva risposta grezza (opzionale)
    if dump_dir:
        (dump_dir / "response_raw.txt").write_text(text, encoding="utf-8")


    # --- Parsing e validazione (robusto)
    parse_notes = []
    try:
        xml_block, json_block = split_two_code_blocks(text)
    except Exception as e:
        # Nessun fence: prova il recupero senza fence
        from .validators import recover_xml_json_without_fences
        xml_block, json_block = recover_xml_json_without_fences(text)
        if not xml_block or not json_block:
            if dump_dir:
                (dump_dir / "parse_error.txt").write_text(
                    f"{type(e).__name__}: {e}\n\n--- RESPONSE BEGIN ---\n{text}\n--- RESPONSE END ---\n",
                    encoding="utf-8",
                )
            return {
                "skipped": True,
                "reason": "missing_code_blocks",
                "error": "no_fences_and_recovery_failed",
            }
        else:
            parse_notes.append("recovered_without_fences")
            if dump_dir:
                (dump_dir / "parse_warning_recovered.txt").write_text(
                    "XML/JSON estratti senza fence usando fallback.\n",
                    encoding="utf-8",
                )

    # --- Validazione
    try:
        validate_xml(xml_block, set(node_library["allowed_ids"]))
        _ = parse_and_validate_json(json_block)
    except Exception as e:
        if dump_dir:
            (dump_dir / "validation_error.txt").write_text(
                f"{type(e).__name__}: {e}\n\n--- XML ---\n{xml_block}\n\n--- JSON ---\n{json_block}\n",
                encoding="utf-8",
            )
        return {
            "skipped": True,
            "reason": "validation_failed",
            "error": str(e),
        }

    # --- Persistenza
    io.subtree_xml_path.write_text(xml_block, encoding="utf-8")
    io.subtree_json_path.write_text(json_block, encoding="utf-8")

    return {
        "skipped": False,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
        "xml_path": str(io.subtree_xml_path),
        "json_path": str(io.subtree_json_path),
        "notes": parse_notes,
    }
