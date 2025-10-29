#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import argparse
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import Dict, List, Set, Tuple
from collections import defaultdict

# Nodi di controllo/decoratori da ignorare quando facciamo fallback su XML
CONTROL_TAGS = {
    "BehaviorTree", "root",
    "Sequence", "Fallback", "Parallel",
    "ReactiveSequence", "ReactiveFallback",
    "Inverter", "ForceSuccess", "ForceFailure",
    "Repeat", "Retry", "Timeout"
}

def load_node_specs_from_meta(meta_path: Path) -> List[Dict]:
    """
    Fonte primaria: meta.json → node_specs[].ports
    Ritorna una lista di dict: {"id": <nome_azione>, "params": [p1, p2, ...]}
    """
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    specs = meta.get("node_specs") or []
    out: List[Dict] = []
    for s in specs:
        node_id = s.get("id")
        ports = s.get("ports") or {}
        if isinstance(node_id, str):
            out.append({"id": node_id, "params": sorted([str(k) for k in ports.keys()])})
    return out

def _merge_param_names(acc: Dict[str, Set[str]], node_id: str, attrs: List[str]):
    if node_id not in acc:
        acc[node_id] = set()
    for a in attrs:
        if isinstance(a, str) and a:
            acc[node_id].add(a)

def build_specs_from_xml(xml_path: Path) -> List[Dict]:
    """
    Fallback: parsiamo bt.xml, raccogliamo tutti i tag "azione"
    (escludendo i nodi di controllo) e uniamo i nomi attributo visti.
    """
    try:
        xml_text = xml_path.read_text(encoding="utf-8")
    except Exception:
        return []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        # Tentativo di recovery su eventuali wrapper/whitespace strani
        try:
            root = ET.fromstring(xml_text.replace("\r", "").replace("\n", ""))
        except Exception:
            return []

    acc: Dict[str, Set[str]] = {}
    for elem in root.iter():
        tag = elem.tag.strip()
        if "}" in tag:  # rimuovi eventuale namespace
            tag = tag.split("}", 1)[1]
        if tag in CONTROL_TAGS:
            continue
        # Se non ha attributi, non contribuisce a definire una firma di azione
        attrs = [k for k in elem.attrib.keys()]
        if attrs:
            _merge_param_names(acc, tag, attrs)

    specs = [{"id": k, "params": sorted(list(v))} for k, v in acc.items()]
    specs.sort(key=lambda d: d["id"])
    return specs

def dedupe_specs(specs: List[Dict]) -> List[Dict]:
    """
    Deduplica per id azione, unendo i parametri (set) e ordinandoli.
    Restituisce una lista ordinata per id.
    """
    acc: Dict[str, Set[str]] = defaultdict(set)
    for s in specs:
        node_id = s.get("id")
        params = s.get("params") or []
        if isinstance(node_id, str):
            for p in params:
                if isinstance(p, str) and p:
                    acc[node_id].add(p)
    merged = [{"id": k, "params": sorted(list(v))} for k, v in acc.items()]
    merged.sort(key=lambda d: d["id"])
    return merged

def specs_to_actions_line(specs: List[Dict]) -> str:
    """
    Formatta in una singola riga:
      actions=[A1(p1,p2), A2(), ...]
    """
    parts: List[str] = []
    seen: Set[str] = set()
    for s in sorted(specs, key=lambda x: x["id"]):
        pid = s["id"]
        params = s.get("params") or []
        sig = f"{pid}(" + ",".join(params) + ")"
        if sig not in seen:
            seen.add(sig)
            parts.append(sig)
    return "actions=[" + ", ".join(parts) + "]"

def derive_actions_line(ep_dir: Path,
                        meta_filename: str = "meta.json",
                        xml_filename: str = "bt.xml") -> Tuple[str, List[Dict]]:
    """
    Calcola la riga actions=[...] per un episodio:
    - prima prova da meta.json (node_specs),
    - se vuoto, fallback su bt.xml,
    - deduplica per id e unione parametri.
    """
    meta_path = ep_dir / meta_filename
    xml_path  = ep_dir / xml_filename

    specs = load_node_specs_from_meta(meta_path)
    if not specs:
        specs = build_specs_from_xml(xml_path)

    specs = dedupe_specs(specs)  # dedup definitiva

    return specs_to_actions_line(specs), specs

def write_actions_txt_for_episode(ep_dir: Path,
                                  actions_line: str,
                                  filename: str = "actions.txt") -> Path:
    out_path = ep_dir / filename
    out_path.write_text(actions_line + "\n", encoding="utf-8")
    return out_path

def discover_episodes(root: Path) -> List[Path]:
    """
    Cerca episodi in due layout:
    1) dataset/<dataset_name>/episode_*/
    2) <root>/episode_*/
    """
    out: List[Path] = []
    any_ds = False
    for ds_dir in sorted(root.iterdir()):
        if ds_dir.is_dir():
            eps = sorted([p for p in ds_dir.glob("episode_*") if p.is_dir()])
            if eps:
                any_ds = True
                out.extend(eps)
    if any_ds:
        return out
    return sorted([p for p in root.glob("episode_*") if p.is_dir()])

def main():
    ap = argparse.ArgumentParser("Genera actions.txt e la riga actions=[...] per ogni episodio")
    ap.add_argument("--episodes_root", type=str, required=True,
                    help="Radice con i dataset che contengono episode_* (es. 'dataset')")
    ap.add_argument("--meta_filename", type=str, default="meta.json")
    ap.add_argument("--xml_filename", type=str, default="bt.xml")
    ap.add_argument("--actions_filename", type=str, default="actions.txt")
    args = ap.parse_args()

    episodes_root = Path(args.episodes_root).resolve()
    eps = discover_episodes(episodes_root)
    if not eps:
        raise SystemExit(f"Nessun episodio trovato sotto {episodes_root}")

    n_ok = 0
    for ep in eps:
        try:
            line, _ = derive_actions_line(ep, args.meta_filename, args.xml_filename)
            write_actions_txt_for_episode(ep, line, args.actions_filename)
            n_ok += 1
        except Exception as e:
            print(f"[WARN] {ep}: {e}")
    print(f"Creati {n_ok} file actions.txt")

if __name__ == "__main__":
    main()
