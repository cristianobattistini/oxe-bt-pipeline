# bt_local_gen/preview.py
import argparse
import json
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from lxml import etree

# Importa utilità dal tuo pacchetto
from .pipeline import load_node_library
from .validators import split_two_code_blocks, validate_xml, parse_and_validate_json


# ----------------- fallback extractor (senza fence) -----------------

def _find_balanced_segment(s: str, start_pat: str, end_pat: str) -> Optional[str]:
    import re
    start_re = re.compile(start_pat, re.IGNORECASE | re.DOTALL)
    end_re = re.compile(end_pat, re.IGNORECASE | re.DOTALL)

    m = start_re.search(s)
    if not m:
        return None
    start_idx = m.start()

    opens = list(start_re.finditer(s, start_idx))
    ends = list(end_re.finditer(s, start_idx))
    if not opens or not ends:
        return None

    depth = 0
    i_open, i_end = 0, 0
    pos = start_idx
    while i_open < len(opens) or i_end < len(ends):
        next_open = opens[i_open].start() if i_open < len(opens) else None
        next_end = ends[i_end].start() if i_end < len(ends) else None

        if next_end is None or (next_open is not None and next_open < next_end):
            depth += 1
            pos = opens[i_open].end()
            i_open += 1
        else:
            depth -= 1
            pos = ends[i_end].end()
            i_end += 1
            if depth == 0:
                return s[start_idx:pos]
    return None


def _extract_xml_loose(text: str) -> Optional[str]:
    seg = _find_balanced_segment(
        text,
        r"<\s*BehaviorTree\b",
        r"</\s*BehaviorTree\s*>",
    )
    if not seg:
        return None
    try:
        etree.fromstring(seg.encode("utf-8"))
        return seg.strip()
    except Exception:
        return None


def _extract_first_json_loose(text: str) -> Optional[str]:
    n = len(text)
    i = 0
    while i < n:
        if text[i] == "{":
            depth = 0
            j = i
            while j < n:
                ch = text[j]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[i:j+1]
                        try:
                            json.loads(candidate)
                            return candidate.strip()
                        except Exception:
                            break
                j += 1
        i += 1
    return None


def recover_without_fences(text: str) -> Tuple[Optional[str], Optional[str]]:
    return _extract_xml_loose(text or ""), _extract_first_json_loose(text or "")


# ----------------- main logic -----------------

def main():
    ap = argparse.ArgumentParser(
        description="Preview/validate una response grezza (anche senza fence) prima di eseguire la pipeline."
    )
    ap.add_argument("--response", required=True, help="Path a response_raw.txt")
    ap.add_argument("--node-library", required=True, help="Path a node_library.json")
    ap.add_argument("--out-dir", type=str, default="", help="Se settato, salva subtree_.xml/json qui")
    ap.add_argument("--no-validate", action="store_true", help="Non validare contro NODE_LIBRARY (solo estrazione)")
    args = ap.parse_args()

    raw_path = Path(args.response)
    nl_path = Path(args.node_library)
    out_dir = Path(args.out_dir) if args.out_dir else None

    if not raw_path.exists():
        raise SystemExit(f"File non trovato: {raw_path}")
    if not nl_path.exists():
        raise SystemExit(f"node_library non trovata: {nl_path}")

    text = raw_path.read_text(encoding="utf-8")
    node_library = load_node_library(nl_path)

    # 1) prova con i fence
    xml_block = json_block = None
    try:
        xml_block, json_block = split_two_code_blocks(text)
        method = "fences"
    except Exception:
        # 2) fallback senza fence
        xml_block, json_block = recover_without_fences(text)
        method = "recovered_without_fences" if (xml_block and json_block) else "failed"

    if not xml_block or not json_block:
        print("[ERRORE] impossibile estrarre entrambi i blocchi (XML/JSON).")
        print("Suggerimenti:")
        print("- verifica il prompt: chiedi esplicitamente due fenced block separati con ```xml e ```json.")
        print("- verifica che la risposta non sia stata troncata.")
        return

    print(f"[OK] Estrazione: {method}")
    print(f"  - XML chars:  {len(xml_block)}")
    print(f"  - JSON chars: {len(json_block)}")

    if not args.no_validate:
        # Validazione
        try:
            validate_xml(xml_block, set(node_library["allowed_ids"]))
            _ = parse_and_validate_json(json_block)
            print("[OK] Validazione XML/JSON superata.")
        except Exception as e:
            print("[ERRORE] Validazione fallita:")
            print(f"  {type(e).__name__}: {e}")
            # Anche in caso di validazione fallita, puoi salvare i blocchi per ispezione
            if out_dir:
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "subtree_.xml").write_text(xml_block, encoding="utf-8")
                (out_dir / "subtree_.json").write_text(json_block, encoding="utf-8")
                print(f"[INFO] Blocchi salvati in: {out_dir}")
            return

    # Scrittura opzionale dei file destinazione
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "subtree_.xml").write_text(xml_block, encoding="utf-8")
        (out_dir / "subtree_.json").write_text(json_block, encoding="utf-8")
        print(f"[OK] File scritti in: {out_dir}")


if __name__ == "__main__":
    main()
