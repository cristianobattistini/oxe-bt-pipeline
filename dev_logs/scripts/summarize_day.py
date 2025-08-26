#!/usr/bin/env python
import os, glob, json, datetime, pathlib
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()
repo = pathlib.Path(__file__).resolve().parents[1]
raw_dir = repo / "dev_logs" / "raw"
commit_dir = repo / "dev_logs" / "commits"
out_dir = repo / "dev_logs"
out_dir.mkdir(exist_ok=True)

day = os.environ.get("DAY", datetime.date.today().isoformat())
model = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")

# Collect logs
events = []
for p in glob.glob(str(raw_dir / f"events_{day}.jsonl")):
    with open(p, encoding="utf-8") as f:
        events += [json.loads(l) for l in f]

commits = []
for p in glob.glob(str(commit_dir / f"{day}_*.md")):
    with open(p, encoding="utf-8") as f:
        commits.append(f.read())

if not (events or commits):
    print("No logs for the day."); raise SystemExit(0)

# Prompt (in English, with Markdown structure)
prompt = f"""
You are a technical assistant. Generate a **daily engineering log** in Markdown.

### Guidelines
- Use clear Markdown headings (`#`, `##`, `###`) for structure.
- Do not invent information: summarize only what is provided.
- Keep the tone concise and professional.
- Always include the following sections:

# Daily Log {day}

## Timeline of Events
List events in chronological order, with timestamps if available.

## Commit Summary
Summarize the commits of the day with bullet points. Highlight file changes or diffs only if meaningful.

## Highlights
Summarize the most important technical progress.

## Next Steps
Suggest possible next actions based on the events and commits.

---

### Raw Data (for reference)
Events: {json.dumps(events, ensure_ascii=False)[:3000]}
Commits: {"".join(commits)[:3000]}
"""

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

resp = client.chat.completions.create(
    model=model,
    messages=[{"role":"system","content":"You produce clean daily engineering logs in Markdown."},
              {"role":"user","content":prompt}],
    temperature=0.2,
)

md = resp.choices[0].message.content
out = out_dir / f"{day}.md"
with open(out,"w",encoding="utf-8") as f: 
    f.write(md)

print(f"[daily-summary] {out}")
