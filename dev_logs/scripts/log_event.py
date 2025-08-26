#!/usr/bin/env python
import json, sys, datetime, pathlib

repo = pathlib.Path(__file__).resolve().parents[1]
outdir = repo / "dev_logs" / "raw"
outdir.mkdir(parents=True, exist_ok=True)
day = datetime.date.today().isoformat()
path = outdir / f"events_{day}.jsonl"

event = {
    "ts": datetime.datetime.now().isoformat(),
    "kind": sys.argv[1] if len(sys.argv) > 1 else "generic",
    "payload": " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None
}

with open(path,"a",encoding="utf-8") as f:
    f.write(json.dumps(event, ensure_ascii=False) + "\n")

print(f"[event-log] {path}")
