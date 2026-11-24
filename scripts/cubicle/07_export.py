"""Step 7: export videos.json, meta.json and paths.json exactly per docs/cubicle-data.md (no thumbnails)."""
import datetime as dt
from collections import Counter

import yt_api
from common import DATA_DIR, RAW, dump_json, load_json

KEYS = ("i", "t", "c", "h", "n", "s", "l", "k", "sc", "f", "o", "sr", "src", "tr", "d", "p")
SECTION_ORDER_CORE = ["start", "tactics", "calc", "strategy", "endgames", "middlegame"]


def pick(videos, n, pred=lambda v: True, per_node=3):
    out, nodes = [], Counter()
    for v in videos:
        if pred(v) and nodes[v["n"]] < per_node:
            out.append(v)
            nodes[v["n"]] += 1
            if len(out) >= n:
                break
    return out


def build_paths(videos, seeds):
    by_id = {v["i"]: v for v in videos}
    paths = []
    core, titles = [], []
    order = ["Chess Fundamentals", "Building Habits", "Climbing the Rating Ladder", "Master Class Speedrun", "Opening Theory Speedrun"]
    named = {p["label"]: p for p in seeds.get("playlists", []) if p.get("how") == "api"}
    pl_items = load_json(RAW / "playlist_items.json", {}) or {}
    for lbl in order:
        p = named.get(lbl)
        if p:
            core += [i for i in pl_items.get(p["id"], []) if i in by_id]
            titles.append(lbl)
    rest = [v for v in videos if v["i"] not in set(core) and v["l"] in ("b", "i", "a") and v["s"] in SECTION_ORDER_CORE]
    sec_rank = {s: k for k, s in enumerate(SECTION_ORDER_CORE)}
    lv_rank = {"b": 0, "i": 1, "a": 2}
    extra = pick(sorted(rest, key=lambda v: (lv_rank[v["l"]], sec_rank[v["s"]], -v["sc"])), 25 - len(core) if core else 25, per_node=1)
    core += [v["i"] for v in extra]
    if len(core) >= 3:
        blurb = ("Course playlists first, then the strongest fundamentals by rank." if titles else
                 "A beginner-to-club-player route through the strongest fundamentals: start, tactics, calculation, strategy, endgames.")
        paths.append({"id": "core", "title": "Core path", "blurb": blurb, "level": "b", "videos": core})
    for l, name in (("b", "Under 1000"), ("i", "1000 to 1600"), ("a", "1600 to 2000"), ("x", "2000 and up")):
        vs = pick(videos, 20, lambda v, l=l: v["l"] == l)
        if len(vs) >= 3:
            paths.append({"id": f"band-{l}", "title": name, "blurb": f"Top picks for {name.lower()} players.", "level": l,
                          "videos": [v["i"] for v in vs]})
    # (No "Build a repertoire" path: removed at the user's request; openings stay browsable by section.)
    return paths


def compute_shortfalls(tax, videos, seeds, keyless):
    out = []
    if keyless:
        out.append("YT_API_KEY not set: durations, languages, embeddable/public flags, likes and chapters are unknown (d is null, "
                   "language is a title heuristic); the engagement bar is replaced by membership of the channel's long-form upload feed; "
                   "upload feeds expose only the latest 15 videos per channel, so older evergreen videos are missing; "
                   "named playlists cannot be searched by title.")
    un = seeds.get("unresolved_channels", [])
    names = [u["name"] for u in un if not u["name"].startswith("playlist:")]
    if names:
        out.append(f"{len(names)} trusted channels could not be resolved to a channel id from fetched evidence and were dropped: " + ", ".join(names))
    pls = [u["name"] for u in un if u["name"].startswith("playlist:")]
    if pls:
        out.append("Playlists not expanded: " + ", ".join(p.split(": ", 1)[1] for p in pls))
    if len(videos) < 500:
        out.append(f"Only {len(videos)} videos (< 500 required).")
    sec = Counter(v["s"] for v in videos)
    low = [f"{s['id']} {sec.get(s['id'], 0)}/{s['floor']}" for s in tax["sections"] if sec.get(s["id"], 0) < s["floor"]]
    if low:
        out.append("Sections below floor: " + ", ".join(low))
    empty = sum(1 for s in tax["sections"] for n in s["nodes"] if not any(v["n"] == n["id"] for v in videos))
    if empty:
        out.append(f"{empty} taxonomy nodes have no videos.")
    unk = sum(1 for v in videos if not v["p"])
    if unk:
        out.append(f"{unk} videos have an unknown publish date (freshness 0.6, counted as not-since-2021 by the validator).")
    return out


def main():
    tax = load_json(DATA_DIR / "taxonomy.json")
    scored = load_json(RAW / "scored.json", [])
    seeds = load_json(DATA_DIR / "seeds.json", {})
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    videos = [{k: r[k] for k in KEYS} for r in sorted(scored, key=lambda r: -r["sc"])]
    dump_json(DATA_DIR / "videos.json", {"built": now, "videos": videos}, compact=True)
    sections = Counter(v["s"] for v in videos)
    keyless = not yt_api.key() or not any(v["d"] for v in videos)
    shortfalls = compute_shortfalls(tax, videos, seeds, keyless)
    meta = {"built": now, "videos": len(videos), "channels": len({v["h"] or v["c"] for v in videos}),
            "nodes": len({v["n"] for v in videos}), "sections": {s["id"]: sections.get(s["id"], 0) for s in tax["sections"]},
            "keyless": keyless, "shortfalls": shortfalls}
    dump_json(DATA_DIR / "meta.json", meta)
    paths = build_paths(videos, seeds)
    dump_json(DATA_DIR / "paths.json", {"paths": paths})
    print(f"exported {len(videos)} videos, {meta['channels']} channels, {meta['nodes']} nodes, {len(paths)} paths")


if __name__ == "__main__":
    main()
