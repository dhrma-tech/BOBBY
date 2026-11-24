"""Step 3: assemble candidates and verify every id.

  * source videos (step 1) with their independent vouches
  * tier 1/2 channels' long-form upload feeds (UULF; RSS key-less, API playlistItems with a key)
  * seed playlists
Every candidate id is checked against YouTube oEmbed (200 = ok; anything else dropped). With YT_API_KEY,
videos.list adds duration, publish date, views, likes, language, embeddable, live state and chapters
(persisted usage counter, 9,400 units/day, resumable). Resumable: caches in data/cubicle/raw/.

Output: data/cubicle/raw/candidates.json
"""
import concurrent.futures as cf
import importlib
import json
import threading
import time
from collections import defaultdict

import requests

import feeds
import yt_api
from common import DATA_DIR, RAW, UA, dump_json, load_json, normalize, read_jsonl

OEMBED = RAW / "oembed.jsonl"
META = RAW / "youtube_meta.json"
FEEDS_CACHE = RAW / "feeds.json"
_tl = threading.local()


def _sess():
    if not hasattr(_tl, "s"):
        _tl.s = requests.Session()
        _tl.s.headers["User-Agent"] = UA
    return _tl.s


def oembed(vid):
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
    for attempt in range(4):
        try:
            r = _sess().get(url, timeout=15)
            if r.status_code == 200:
                j = r.json()
                return {"id": vid, "status": "ok", "title": j.get("title"), "channel": j.get("author_name"),
                        "author_url": j.get("author_url")}
            if r.status_code in (401, 403):
                return {"id": vid, "status": "restricted"}
            if r.status_code in (400, 404):
                return {"id": vid, "status": "gone"}
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
        except Exception:
            time.sleep(2 * (attempt + 1))
    return {"id": vid, "status": "error"}


def verify_oembed(ids, workers=8):
    done = {r["id"]: r for r in read_jsonl(OEMBED) if r["status"] != "error"}
    todo = [i for i in dict.fromkeys(ids) if i not in done]
    print(f"oEmbed: {len(ids)} ids, {len(done)} cached, {len(todo)} to check", flush=True)
    t0, n = time.time(), 0
    with OEMBED.open("a", encoding="utf-8") as f, cf.ThreadPoolExecutor(workers) as ex:
        for r in ex.map(oembed, todo):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            done[r["id"]] = r
            n += 1
            if n % 300 == 0:
                f.flush()
                print(f"  {n}/{len(todo)}  {n / (time.time() - t0):.1f}/s", flush=True)
    return done


def main():
    seeds = load_json(DATA_DIR / "seeds.json")
    chans = seeds["channels"]
    use_api = bool(yt_api.key())
    cands = {}

    def cand(vid):
        return cands.setdefault(vid, {"id": vid, "title": None, "channel": None, "channel_id": None, "tier": 0,
                                      "vouch_keys": set(), "vouch_labels": [], "published": None, "duration": None,
                                      "views": None, "likes": None, "votes": None, "lang": None, "embeddable": None,
                                      "public": None, "live": None, "chapters": None, "from_feed": False})

    # 1. source vouches
    for r in read_jsonl(RAW / "source_links.jsonl"):
        c = cand(r["video_id"])
        c["vouch_keys"].add(r["dedupe"])
        if r["source"] not in c["vouch_labels"]:
            c["vouch_labels"].append(r["source"])

    # 2. channel upload feeds
    fcache = {}
    for ch in chans:
        if ch["tier"] not in (1, 2):
            continue
        if use_api:
            try:
                items = yt_api.channel_uploads(ch["id"], pages=2)
            except SystemExit as e:
                print("API:", e)
                items = []
            kind = "api"
        else:
            f, kind = feeds.uulf_feed(ch["id"], cache=False)
            items = f["entries"] if f else []
        fcache[ch["id"]] = {"name": ch["name"], "kind": kind, "n": len(items)}
        print(f"feed {ch['name']}: {len(items)} items ({kind})")
        for it in items:
            c = cand(it["id"])
            c.update({"from_feed": True, "feed_channel": ch["name"], "channel_id": ch["id"],
                      "published": it.get("published") or c["published"]})
            for k in ("views", "votes"):
                if it.get(k) is not None:
                    c[k] = it[k]
            c["title"] = it.get("title") or c["title"]
            c["channel"] = it.get("channel") or ch["name"]

    # 3. seed playlists
    pl_items = {}
    for pl in seeds.get("playlists", []):
        if use_api:
            items = yt_api.playlist_items(pl["id"], pages=3)
        else:
            f = feeds.fetch_feed("playlist_id", pl["id"], cache=False)
            items = f["entries"] if f else []
        pl_items[pl["id"]] = [it["id"] for it in items]
        for it in items:
            c = cand(it["id"])
            c["vouch_keys"].add("playlist:" + pl["id"])
            lbl = f"Playlist: {pl['title']}"
            if lbl not in c["vouch_labels"]:
                c["vouch_labels"].append(lbl)
            c["published"] = c["published"] or it.get("published")
            c["title"] = c["title"] or it.get("title")
            c["channel"] = c["channel"] or it.get("channel")
    dump_json(FEEDS_CACHE, fcache)
    dump_json(RAW / "playlist_items.json", pl_items)

    # 4. oEmbed check on every candidate
    ok = verify_oembed(list(cands))
    ch_mod = importlib.import_module("02_channels")
    alias = {}
    for row in ch_mod.TRUSTED:
        for a in row[3] + [row[0]]:
            alias[normalize(a)] = row[0]
    by_name = {c["name"]: c for c in chans}
    out, dropped = [], defaultdict(int)
    for vid, c in cands.items():
        o = ok.get(vid)
        if not o or o["status"] != "ok":
            dropped[(o or {}).get("status", "unchecked")] += 1
            continue
        c["title"] = o["title"] or c["title"]
        c["channel"] = o["channel"] or c["channel"]
        trusted_name = alias.get(normalize(c["channel"]))
        if trusted_name and trusted_name in by_name:
            c["tier"] = by_name[trusted_name]["tier"]
            c["channel_id"] = by_name[trusted_name]["id"]
        elif c.get("from_feed") and c.get("feed_channel") in by_name:
            c["tier"] = by_name[c["feed_channel"]]["tier"]
        c["vouches"] = len(c["vouch_keys"])
        c["vouch_keys"] = sorted(c["vouch_keys"])
        out.append(c)
    print("candidates oEmbed-ok:", len(out), "dropped:", dict(dropped))

    # 5. API enrichment
    meta = load_json(META, {}) or {}
    if use_api:
        todo = [c["id"] for c in out if c["id"] not in meta]
        print(f"API videos.list for {len(todo)} ids (used today: {yt_api.used_today()})")
        try:
            for i in range(0, len(todo), 50):
                meta.update(yt_api.videos_list(todo[i:i + 50]))
                dump_json(META, meta)
        except SystemExit as e:
            print("API:", e)
        for c in out:
            m = meta.get(c["id"])
            if m:
                c.update({k: m[k] for k in ("duration", "views", "likes", "lang", "embeddable", "public", "live", "chapters")})
                c["published"] = m["published"] or c["published"]
                c["channel_id"] = c["channel_id"] or m.get("channel_id")
    dump_json(RAW / "candidates.json", out)
    dump_json(RAW / "step3_stats.json", {"api": use_api, "dropped_oembed": dict(dropped), "ok": len(out)})


if __name__ == "__main__":
    main()
