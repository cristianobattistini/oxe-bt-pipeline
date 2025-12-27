import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List
from xml.etree import ElementTree as ET


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Report common XML/data issues from rich trace JSONL.")
    ap.add_argument("--input", required=True, help="Path to rich JSONL (with trace.final_xml).")
    return ap.parse_args()


def _count_release(xml: str) -> int:
    return len(re.findall(r'<\s*Action\b[^>]*\bID\s*=\s*"RELEASE"', xml))


def main() -> int:
    args = parse_args()
    path = Path(args.input)
    if not path.exists():
        print(f"[ERROR] missing input: {path}")
        return 1

    verdicts = Counter()
    issues = Counter()
    total = 0

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            rec = json.loads(line)
            verdicts[rec.get("verdict", "<missing>")] += 1
            xml = ((rec.get("trace") or {}).get("final_xml")) or ""
            if not xml:
                issues["missing_final_xml"] += 1
                continue

            try:
                root = ET.fromstring(xml)
            except ET.ParseError:
                issues["xml_parse_error"] += 1
                continue

            first_bt = root.find("BehaviorTree")
            if first_bt is not None:
                main_exec = root.get("main_tree_to_execute")
                first_id = first_bt.get("ID")
                if main_exec != first_id:
                    issues["main_tree_to_execute_mismatch"] += 1

            for bt in root.findall("BehaviorTree"):
                if len(list(bt)) != 1:
                    issues["behavior_tree_multiple_roots"] += 1
                    break

            if _count_release(xml) > 1:
                issues["duplicate_release"] += 1

    print("[REPORT]")
    print("total", total)
    print("verdicts", dict(verdicts))
    print("issues", dict(issues))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

