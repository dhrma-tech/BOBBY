"""Step 5b (optional, needs ANTHROPIC_API_KEY): Claude Haiku pass over the rule-classified videos.
Per video it returns {node, level, kind, relevant}; irrelevant (not chess instruction/analysis/news) or
clickbait-only videos are dropped in step 6, node/level/kind override the rules. Title + channel only,
40 videos per request, resumable (data/cubicle/raw/llm_labels.jsonl).

  python scripts/cubicle/05b_llm_label.py --dry-run     # estimate, no API calls
  python scripts/cubicle/05b_llm_label.py               # needs ANTHROPIC_API_KEY
"""
import argparse
import json
import os
import sys
import time

import requests

from common import DATA_DIR, RAW, load_json, read_jsonl

MODEL = "claude-haiku-5-5"
TAX = load_json(DATA_DIR / "taxonomy.json")
NODE_LIST = "\n".join(f"{n['id']}: {s['title']} > {n['title']} (level {n['level']}, shelf {n['shelf']})"
                      for s in TAX["sections"] for n in s["nodes"])
SYSTEM = f"""You label YouTube videos for Cubicle, a curated, text-only library of the best chess videos.
For each input line `id | title | channel | rule_guess` return one JSON object. Output ONLY a JSON array,
one object per input, same order:
{{"id": str, "relevant": bool, "node": str, "level": "b|i|a|x", "kind": "lesson|course|gameplay|review|tips|recap|talk"}}

relevant=false when the video is not useful chess learning, analysis, gameplay-with-commentary, tournament coverage
or chess history (e.g. pure clickbait, memes, off-topic, non-English). level: b <1000, i 1000-1600, a 1600-2000, x 2000+.
kind: lesson (single teaching video), course (part of a series), gameplay (played game with live thinking),
review (annotated or reviewed game), tips (short advice list), recap (event round/day), talk (interview/documentary).
node must be one of these ids; fix the rule_guess when wrong:
{NODE_LIST}
"""
LABELS = RAW / "llm_labels.jsonl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--batch", type=int, default=40)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    rows = load_json(RAW / "classified.json", [])
    done = {r["id"] for r in read_jsonl(LABELS)}
    todo = [r for r in rows if r["id"] not in done]
    print(f"{len(todo)} videos to label in {len(todo) // a.batch + 1} requests")
    if a.dry_run:
        return
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("ANTHROPIC_API_KEY is not set: skipping the LLM pass (rule-based labels stay)")
    valid = {n["id"] for s in TAX["sections"] for n in s["nodes"]}
    with LABELS.open("a", encoding="utf-8") as f:
        for k in range(0, len(todo), a.batch):
            b = todo[k:k + a.batch]
            msg = "\n".join(f"{r['id']} | {r['title']} | {r['channel']} | {r['node']}" for r in b)
            for attempt in range(3):
                try:
                    resp = requests.post("https://api.anthropic.com/v1/messages", timeout=120,
                                         headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                                         json={"model": a.model, "max_tokens": 4000, "temperature": 0,
                                               "system": [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                                               "messages": [{"role": "user", "content": msg}]})
                    resp.raise_for_status()
                    txt = resp.json()["content"][0]["text"].strip()
                    arr = json.loads(txt[txt.index("["): txt.rindex("]") + 1])
                    ids = {r["id"] for r in b}
                    for o in arr:
                        if o.get("id") in ids and o.get("node", "") in valid | {""}:
                            f.write(json.dumps(o, ensure_ascii=False) + "\n")
                    break
                except Exception as e:  # retry
                    print("  retry", attempt, str(e)[:100])
                    time.sleep(3 * (attempt + 1))
            f.flush()
            print(f"  {k + len(b)}/{len(todo)}", flush=True)


if __name__ == "__main__":
    main()
