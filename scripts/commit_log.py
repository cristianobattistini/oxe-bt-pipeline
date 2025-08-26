#!/usr/bin/env python
import subprocess as sp, pathlib, datetime

repo = pathlib.Path(__file__).resolve().parents[1]
outdir = repo / "dev_logs" / "commits"
outdir.mkdir(parents=True, exist_ok=True)

def sh(*args): return sp.check_output(args).decode("utf-8", "replace").strip()

commit = sh("git","rev-parse","HEAD")
short  = sh("git","rev-parse","--short","HEAD")
msg    = sh("git","log","-1","--pretty=%s")
author = sh("git","log","-1","--pretty=%an <%ae>")
date   = sh("git","log","-1","--pretty=%ad","--date=iso")
diff   = sh("git","show","--patch","--stat","-1","--no-color")

fn = outdir / f"{datetime.date.today().isoformat()}_{short}.md"
with open(fn,"w",encoding="utf-8") as f:
    f.write(f"# Commit {short}\n\n- Hash: `{commit}`\n- Author: {author}\n- Date: {date}\n- Message: {msg}\n\n")
    f.write("## Diff\n\n```diff\n"); f.write(diff); f.write("\n```\n")

print(f"[commit-log] {fn}")
