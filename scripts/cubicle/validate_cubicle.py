"""Validator: exits 1 if the catalogue is not good enough to ship. Thresholds are NOT lowered key-less.

Fails when: < 500 videos; any taxonomy node empty; any section below its floor (openings sections 5-11 also
combined < 140); duplicate ids; any id not in the oEmbed-verified cache; < 25 channels; < 60% published since
2021 (unknown dates count as NOT since 2021); any thumbnail-like key.   python scripts/cubicle/validate_cubicle.py
"""
import sys

from common import DATA_DIR, RAW, load_json, read_jsonl

OPEN_SECTIONS = ["open-e4", "open-d4", "open-flank", "def-e4", "def-d4", "gambits", "open-study"]
MIN_VIDEOS, MIN_CHANNELS, OPEN_COMBINED, SINCE, SINCE_FRAC = 500, 25, 140, 2021, 0.60
ALLOWED = set("i t c h n s l k sc f o sr src tr d p".split())


def validate(videos, tax, oembed_ok):
    errs, notes = [], []
    n = len(videos)
    if n < MIN_VIDEOS:
        errs.append(f"only {n} videos (< {MIN_VIDEOS})")
    ids = [v["i"] for v in videos]
    dup = len(ids) - len(set(ids))
    if dup:
        errs.append(f"{dup} duplicate ids")
    bad = [i for i in ids if i not in oembed_ok]
    if bad:
        errs.append(f"{len(bad)} ids not in the oEmbed-verified cache (e.g. {bad[:3]})")
    extra = {k for v in videos for k in v} - ALLOWED
    if extra:
        errs.append(f"unexpected keys (thumbnails or other): {sorted(extra)}")
    by_node, by_sec = {}, {}
    for v in videos:
        by_node[v["n"]] = by_node.get(v["n"], 0) + 1
        by_sec[v["s"]] = by_sec.get(v["s"], 0) + 1
    empty = [nd["id"] for s in tax["sections"] for nd in s["nodes"] if not by_node.get(nd["id"])]
    if empty:
        errs.append(f"{len(empty)} empty nodes (of {sum(len(s['nodes']) for s in tax['sections'])})")
    for s in tax["sections"]:
        if by_sec.get(s["id"], 0) < s["floor"]:
            errs.append(f"section {s['id']}: {by_sec.get(s['id'], 0)} < floor {s['floor']}")
    comb = sum(by_sec.get(s, 0) for s in OPEN_SECTIONS)
    if comb < OPEN_COMBINED:
        errs.append(f"openings sections combined {comb} < {OPEN_COMBINED}")
    chans = len({v["h"] or v["c"] for v in videos})
    if chans < MIN_CHANNELS:
        errs.append(f"{chans} channels (< {MIN_CHANNELS})")
    since = sum(1 for v in videos if v.get("p") and int(v["p"][:4]) >= SINCE)
    unknown = sum(1 for v in videos if not v.get("p"))
    frac = since / n if n else 0
    notes.append(f"published since {SINCE}: {since}/{n} = {frac:.0%} (unknown dates counted as not-since-{SINCE}: {unknown})")
    if frac < SINCE_FRAC:
        errs.append(f"only {frac:.0%} published since {SINCE} (< {SINCE_FRAC:.0%})")
    return errs, notes


def main():
    vj = load_json(DATA_DIR / "videos.json")
    tax = load_json(DATA_DIR / "taxonomy.json")
    if not vj or not tax:
        print("FAIL: videos.json or taxonomy.json missing")
        sys.exit(1)
    ok = {r["id"] for r in read_jsonl(RAW / "oembed.jsonl") if r["status"] == "ok"}
    errs, notes = validate(vj["videos"], tax, ok)
    lj = load_json(DATA_DIR / "latest.json")
    if lj:
        bad = [i["i"] for i in lj["items"] if i["i"] not in ok]
        if bad:
            errs.append(f"latest.json has {len(bad)} ids not oEmbed-verified")
    for n in notes:
        print("note:", n)
    for e in errs:
        print("FAIL:", e)
    print("VALID" if not errs else f"INVALID ({len(errs)} problems)")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
