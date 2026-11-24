"""Step 6: score, freshness, outdated tag, modern rule, diversity caps (formulas in scoring.py).
Merges optional LLM labels (drop relevant=false, override node/level/kind). Output: raw/scored.json
"""
import datetime as dt
from collections import Counter

import scoring
from common import DATA_DIR, RAW, dump_json, load_json, read_jsonl
from gate import channel_stats, n_vouches


def merge_llm(rows, node_meta):
    labels = {r["id"]: r for r in read_jsonl(RAW / "llm_labels.jsonl")}
    out, dropped = [], 0
    for c in rows:
        x = labels.get(c["id"])
        if x:
            if x.get("relevant") is False:
                dropped += 1
                continue
            if x.get("node") in node_meta:
                c["node"], c["section"] = x["node"], node_meta[x["node"]]["section"]
            if x.get("level") in ("b", "i", "a", "x"):
                c["level"] = x["level"]
            if x.get("kind") in ("lesson", "course", "gameplay", "review", "tips", "recap", "talk"):
                c["kind"] = x["kind"]
            c["llm"] = 1
        out.append(c)
    return out, dropped


def build_scored(rows, node_meta, stats, today=None):
    out = []
    for c in rows:
        node = node_meta[c["node"]]
        shelf = node["shelf"]
        fresh = scoring.freshness(c.get("published"), shelf, today)
        ck = c.get("channel_id") or c.get("channel")
        eng = scoring.engagement_norm(c, stats.get(ck, {}).get("views_sorted", []))
        v = n_vouches(c)
        recent = scoring.is_recent(c.get("published"), today)
        sc = scoring.score(v, c.get("tier", 0), eng, recent, fresh)
        out.append({"i": c["id"], "t": c["title"], "c": c["channel"], "h": c.get("channel_id"), "n": c["node"],
                    "s": c["section"], "l": c["level"], "k": c["kind"], "sc": round(sc, 2), "f": round(fresh, 2),
                    "o": scoring.is_outdated(fresh, shelf, c.get("published")), "sr": v,
                    "src": c.get("vouch_labels", [])[:3], "tr": c.get("tier", 0), "d": c.get("duration"),
                    "p": c.get("published"), "shelf": shelf, "ck": ck, "published": c.get("published"),
                    "tier": c.get("tier", 0), "vouches": v})
    return out


def main():
    tax = load_json(DATA_DIR / "taxonomy.json")
    node_meta = {n["id"]: {**n, "section": s["id"]} for s in tax["sections"] for n in s["nodes"]}
    rows = load_json(RAW / "classified.json", [])
    rows, llm_dropped = merge_llm(rows, node_meta)
    stats = channel_stats(load_json(RAW / "candidates.json", []))
    scored = build_scored(rows, node_meta, stats)
    n0 = len(scored)
    scored = scoring.apply_modern_rule(scored)
    n1 = len(scored)
    scored = scoring.apply_caps(scored)
    for r in scored:
        r["o"] = int(r["o"])
    dump_json(RAW / "scored.json", scored)
    dump_json(RAW / "score_stats.json", {"classified": n0, "after_modern_rule": n1, "after_caps": len(scored),
                                         "llm_dropped": llm_dropped, "built": dt.datetime.now(dt.timezone.utc).isoformat()})
    print(f"scored {n0} -> modern rule {n1} -> caps {len(scored)} (llm dropped {llm_dropped})")
    print("channels:", len({r['ck'] for r in scored}), " top:", Counter(r["c"] for r in scored).most_common(5))


if __name__ == "__main__":
    main()
