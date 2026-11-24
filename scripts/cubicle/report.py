"""Writes data/cubicle/REPORT.md from the generated files (counts, sources, channels, shortfalls, validator)."""
import datetime as dt
from collections import Counter

from common import DATA_DIR, RAW, load_json, read_jsonl
from validate_cubicle import validate


def table(rows, head):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return "\n".join(out)


def main():
    vj = load_json(DATA_DIR / "videos.json")
    vids = vj["videos"]
    tax = load_json(DATA_DIR / "taxonomy.json")
    meta = load_json(DATA_DIR / "meta.json")
    seeds = load_json(DATA_DIR / "seeds.json")
    latest = load_json(DATA_DIR / "latest.json", {"items": []})
    gate = load_json(RAW / "gate_stats.json", {})
    step3 = load_json(RAW / "step3_stats.json", {})
    oembed_ok = {r["id"] for r in read_jsonl(RAW / "oembed.jsonl") if r["status"] == "ok"}
    errs, notes = validate(vids, tax, oembed_ok)
    sec, node = Counter(v["s"] for v in vids), Counter(v["n"] for v in vids)
    L = [f"# Cubicle build report", "", f"Built {vj['built']}. Mode: **{'key-less' if meta['keyless'] else 'API'}**.",
         f"Videos: **{len(vids)}**, channels: **{meta['channels']}**, nodes with videos: **{meta['nodes']}** of "
         f"{sum(len(s['nodes']) for s in tax['sections'])}, latest items: **{len(latest['items'])}**.", ""]
    L += ["## Validator", "", "```"] + [f"note: {n}" for n in notes] + [f"FAIL: {e}" for e in errs] + \
         ["VALID" if not errs else f"INVALID ({len(errs)} problems)", "```", ""]
    L += ["## Shortfalls", ""] + [f"- {s}" for s in meta["shortfalls"]] + [""]
    L += ["## Per section", "", table([(s["id"], s["title"], sec.get(s["id"], 0), s["floor"], "ok" if sec.get(s["id"], 0) >= s["floor"] else "BELOW")
                                      for s in tax["sections"]], ["id", "title", "videos", "floor", ""]), ""]
    L += ["## Per node", "", table([(n["id"], n["title"], node.get(n["id"], 0)) for s in tax["sections"] for n in s["nodes"]], ["node", "title", "videos"]), ""]
    L += ["## Level, kind", "", table(sorted(Counter(v["l"] for v in vids).items()), ["level", "videos"]), "",
          table(sorted(Counter(v["k"] for v in vids).items()), ["kind", "videos"]), ""]
    L += ["## Per channel", "", table(Counter(v["c"] for v in vids).most_common(), ["channel", "videos"]), ""]
    yrs = Counter((v["p"] or "unknown")[:4] for v in vids)
    L += ["## Publish year", "", table(sorted(yrs.items()), ["year", "videos"]), ""]
    dated = [v for v in vids if v["p"]]
    if dated:
        o = min(dated, key=lambda v: v["p"])
        L += [f"Oldest video: {o['p']} - {o['t']} ({o['c']})", ""]
    L += ["## Vouch distribution (sr)", "", table(sorted(Counter(v["sr"] for v in vids).items()), ["independent vouches", "videos"]), ""]
    L += ["## Gate", "", f"Candidates after oEmbed: {gate.get('candidates')}; kept: {gate.get('kept')}; oEmbed drops: {step3.get('dropped_oembed')}", "",
          table(list(gate.get("reasons", {}).items()), ["outcome", "count"]), ""]
    L += ["## Sources", "", table([(s["label"], s["type"], s["status"], s.get("videos", 0)) for s in seeds.get("sources", [])],
                                  ["source", "type", "status", "videos linked"]), ""]
    ch = seeds.get("channels", [])
    L += ["## Channels resolved", "", table([(c["name"], c["tier"], c["id"], c["how"]) for c in ch], ["channel", "tier", "id", "evidence"]), ""]
    L += ["## Channels / playlists NOT resolved (dropped)", "", table([(u["name"], u["tier"], str(u["reason"])[:140]) for u in seeds.get("unresolved_channels", [])],
                                                                    ["name", "tier", "reason"]), ""]
    L += ["## Notes", "",
          "- Freshness for an unknown publish date is 0.6 (no recency bonus, never flagged outdated).",
          "- Key-less engagement for scoring = percentile of RSS view counts within the channel; no like data.",
          "- The 'outdated' flag only applies to non-evergreen nodes with freshness < 0.4.", ""]
    (DATA_DIR / "REPORT.md").write_text("\n".join(L), encoding="utf-8")
    print("wrote REPORT.md")


if __name__ == "__main__":
    main()
