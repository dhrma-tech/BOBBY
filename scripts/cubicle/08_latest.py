"""Step 9 (the "latest shelf"; no API key needed): tier 1/2 channels' long-form upload feeds
(https://www.youtube.com/feeds/videos.xml?playlist_id=UULF<channelId minus "UC">; falls back to UU... and drops
#shorts titles), last 45 days, oEmbed-verified, classified to node + kind -> data/cubicle/latest.json (newest first).
Run daily by docs/cubicle-latest-workflow.yml.   python scripts/cubicle/08_latest.py [--days 45]
"""
import argparse
import datetime as dt
import importlib

import feeds
import scoring
import yt_api
from classify import Classifier
from common import DATA_DIR, RAW, dump_json, load_json
from gate import is_non_english, is_shorts, blocked

verify_oembed = importlib.import_module("03_collect").verify_oembed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=45)
    a = ap.parse_args()
    seeds = load_json(DATA_DIR / "seeds.json", {})
    tax = load_json(DATA_DIR / "taxonomy.json")
    blocklist = load_json(DATA_DIR / "blocklist.json", {})
    clf = Classifier(tax)
    node_meta = {n["id"]: n for s in tax["sections"] for n in s["nodes"]}
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = (now - dt.timedelta(days=a.days)).date()
    cands = {}
    for ch in seeds.get("channels", []):
        if ch["tier"] not in (1, 2):
            continue
        if yt_api.key():
            items = yt_api.channel_uploads(ch["id"], pages=1)
        else:
            f, _ = feeds.uulf_feed(ch["id"], cache=False)
            items = f["entries"] if f else []
        for it in items:
            d = scoring.parse_date(it.get("published"))
            if d is None or d < cutoff or is_shorts(it["title"]) or is_non_english(it["title"]):
                continue
            if blocked({"id": it["id"], "title": it["title"], "channel": it.get("channel")}, blocklist):
                continue
            cands[it["id"]] = {**it, "tier": ch["tier"], "channel_id": ch["id"], "channel": it.get("channel") or ch["name"]}
    ok = verify_oembed(list(cands))
    items, unclassified = [], 0
    for vid, c in cands.items():
        if ok.get(vid, {}).get("status") != "ok":
            continue
        r = clf.classify(c["title"], c["channel"])
        if not r:
            unclassified += 1
            continue
        shelf = node_meta[r["node"]]["shelf"]
        fresh = scoring.freshness(c["published"], shelf)
        items.append({"i": vid, "t": ok[vid]["title"] or c["title"], "c": ok[vid]["channel"] or c["channel"], "h": c["channel_id"],
                      "n": r["node"], "s": r["section"], "l": r["level"], "k": r["kind"], "sc": 0, "f": round(fresh, 2),
                      "o": 0, "sr": 0, "src": [], "tr": c["tier"], "d": None, "p": c["published"]})
    items.sort(key=lambda x: x["p"], reverse=True)
    dump_json(DATA_DIR / "latest.json", {"built": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "items": items}, compact=True)
    print(f"latest: {len(items)} items from {len({i['h'] for i in items})} channels ({unclassified} unclassified skipped)")


if __name__ == "__main__":
    main()
