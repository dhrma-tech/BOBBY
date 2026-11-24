"""Step 1: find and fetch public sources that link chess videos/channels -> data/cubicle/seeds.json

Every source is a distinct list/page; each video it links is one vouch. Sources that block automated
access (403/Cloudflare/captcha) are skipped and recorded as failed - never worked around.

Outputs
  data/cubicle/raw/source_links.jsonl   {source, type, dedupe, video_id, ctx}
  data/cubicle/raw/source_channels.json {UC id: [source labels]}
  data/cubicle/raw/source_playlists.json{playlist id: [source labels]}
  data/cubicle/seeds.json               sources (status, counts) + trusted channel tiers (see 02_channels.py)
"""
import json
import os
import re
import sys
from collections import defaultdict

from common import (DATA_DIR, RAW, channel_ids, dump_json, handles, load_json, playlist_ids, polite_get,
                    video_ids)

GH_QUERIES = ["awesome chess", "chess learning resources", "chess youtube channels", "chess resources list",
              "learn chess roadmap", "chess study plan", "chess improvement resources", "awesome chess youtube"]
LICHESS_PAGES = [
    ("Lichess blog: 16 best chess YouTube channels", "https://lichess.org/@/nikhildixit/blog/16-best-chess-youtube-channels/rRQeubRw"),
    ("Lichess blog: 11 best chess YouTube channels part 2", "https://lichess.org/ublog/PCJCyO2e/redirect"),
    ("Lichess blog: chess YouTuber ranking 2025", "https://lichess.org/@/TotalNoob69/blog/chess-youtuber-ranking-2025/dWDoiOOY"),
    ("Lichess forum: best chess youtuber for actual studying", "https://lichess.org/forum/general-chess-discussion/best-chess-youtuber-for-actual-studying"),
    ("Lichess forum: what youtube channel for learning", "https://lichess.org/forum/general-chess-discussion/what-youtube-channel-for-learning"),
    ("Lichess forum: recommend a youtube chess channel", "https://lichess.org/forum/general-chess-discussion/recommend-a-youtube-chess-channel"),
    ("Lichess forum: best place to learn chess from", "https://lichess.org/forum/general-chess-discussion/what-is-the-best-place-to-learn-chess-from"),
    ("Lichess forum: chess website for a beginner", "https://lichess.org/forum/general-chess-discussion/what-chess-website-would-you-recommend-to-a-beginner"),
]
WEB_PAGES = [
    ("The Daily Star: YouTube channels for your chess journey", "https://www.thedailystar.net/shout/news/youtube-channels-help-you-your-chess-journey-3275316"),
    ("Beacons: top chess youtubers", "https://beacons.ai/i/blog/chess-youtubers"),
    ("Chessable blog", "https://www.chessable.com/blog/"),
]
HN_QUERIES = ["chess youtube", "chess youtube.com", "learn chess video", "chess tactics youtube", "chess opening youtube",
              "chess endgame youtube", "chess lecture youtube", "chess grandmaster youtube", "chess course video", "chess analysis youtube"]
WIKI_QUERIES = ["chess opening", "chess grandmaster", "chess game", "chess tournament", "chess endgame", "chess player", "chess world championship"]
LESSON_PAGES = []  # extra course/syllabus pages can be appended here (label, url)

CHESS_CTX = re.compile(r"chess|gambit|sicilian|endgame|grandmaster|\bgm\b|lichess|stockfish|kasparov|carlsen|fischer", re.I)
VID_CTX = re.compile(r"(.{0,140}?)((?:https?:)?//(?:www\.|m\.)?(?:youtube(?:-nocookie)?\.com/(?:watch\?[^\s\"'<>)\]]*|embed/[^\s\"'<>)\]]*)|youtu\.be/[^\s\"'<>)\]]*))", re.S | re.I)


def contexts(text):
    out = []
    for m in VID_CTX.finditer(text):
        ctx = re.sub(r"\s+", " ", re.sub(r"<[^>]+>|[\[\]()*#>|]", " ", m.group(1))).strip()[-110:]
        for v in video_ids(m.group(2)):
            out.append((v, ctx))
    return out


class Collector:
    def __init__(self):
        self.rows, self.channels, self.playlists, self.sources = [], defaultdict(set), defaultdict(set), []

    def add_page(self, label, typ, url, text, *, chess_only=False):
        vs = contexts(text)
        if chess_only:
            vs = [(v, c) for v, c in vs if CHESS_CTX.search(c) or CHESS_CTX.search(text[:2000])]
        for v, ctx in vs:
            self.rows.append({"source": label, "type": typ, "dedupe": label, "video_id": v, "ctx": ctx})
        chs, pls = channel_ids(text), playlist_ids(text)
        for c in chs:
            self.channels[c].add(label)
        for p in pls:
            self.playlists[p].add(label)
        hs = handles(text)
        n = len({v for v, _ in vs})
        self.sources.append({"label": label, "type": typ, "url": url, "status": "ok", "videos": n,
                             "channel_ids": len(chs), "handles": len(hs), "playlists": len(pls)})
        print(f"OK   {label}: {n} videos, {len(chs)} channel ids, {len(hs)} handles, {len(pls)} playlists")

    def fail(self, label, typ, url, status):
        self.sources.append({"label": label, "type": typ, "url": url, "status": f"skipped ({status})", "videos": 0})
        print(f"SKIP {label}: HTTP {status}")


def github(c):
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    auth = {"Authorization": f"Bearer {tok}"} if tok else {}
    repos = {}
    for q in GH_QUERIES:
        st, txt = polite_get("https://api.github.com/search/repositories",
                             params={"q": q, "sort": "stars", "per_page": 10}, headers=auth, delay=2.0)
        if st != 200:
            print("  github search failed", q, st)
            continue
        for r in json.loads(txt).get("items", []):
            repos[r["full_name"]] = r["stargazers_count"]
    print(f"{len(repos)} candidate repos")
    for name, stars in sorted(repos.items(), key=lambda kv: -kv[1]):
        st, txt = polite_get(f"https://api.github.com/repos/{name}/readme",
                             headers={"Accept": "application/vnd.github.raw", **auth}, delay=1.0)
        if st != 200:
            continue
        if "chess" not in name.lower() or "tafl" in name.lower() or not (video_ids(txt) or channel_ids(txt) or handles(txt)):
            continue  # no YouTube content -> not a source
        c.add_page(f"GitHub list: {name}", "github", f"https://github.com/{name}", txt)


def lichess_video_library(c, max_pages=150):
    """lichess.org/video is Lichess's curated video library (page N lists 12 videos, ids are YouTube ids).
    Tag-filtered URLs are behind a Cloudflare challenge: skipped, not bypassed."""
    seen_pages, rows = 0, 0
    for p in range(1, max_pages + 1):
        st, txt = polite_get("https://lichess.org/video", params={"page": p}, delay=1.0)
        if st != 200:
            print("  lichess video page", p, "->", st)
            break
        ids = list(dict.fromkeys(re.findall(r'href="/video/([A-Za-z0-9_-]{11})[?"]', txt)))
        if not ids:
            break
        seen_pages += 1
        for v in ids:
            c.rows.append({"source": "Lichess video library", "type": "lichess", "dedupe": "Lichess video library",
                           "video_id": v, "ctx": ""})
            rows += 1
    status = "ok" if rows else "skipped (blocked or empty)"
    c.sources.append({"label": "Lichess video library", "type": "lichess", "url": "https://lichess.org/video",
                      "status": status, "videos": rows, "pages": seen_pages})
    print(f"{'OK  ' if rows else 'SKIP'} Lichess video library: {rows} videos in {seen_pages} pages")


def hacker_news(c):
    seen, n_comments = set(), 0
    for q in HN_QUERIES:
        for page in range(0, 5):
            st, txt = polite_get("https://hn.algolia.com/api/v1/search",
                                 params={"query": q, "tags": "comment", "hitsPerPage": 100, "page": page}, delay=1.0)
            if st != 200:
                break
            hits = json.loads(txt).get("hits", [])
            if not hits:
                break
            for h in hits:
                oid = h.get("objectID")
                if oid in seen:
                    continue
                seen.add(oid)
                body = h.get("comment_text") or ""
                ids = video_ids(body)
                if not ids or len(ids) > 12:
                    continue
                plain = re.sub(r"<[^>]+>", " ", body)
                if not CHESS_CTX.search(plain) and not CHESS_CTX.search(h.get("story_title") or ""):
                    continue
                n_comments += 1
                ctx = re.sub(r"\s+", " ", re.sub(r"https?://\S+", "", plain)).strip()[:110]
                for v in ids:
                    c.rows.append({"source": "Hacker News", "type": "hn", "dedupe": "hn:" + str(h.get("author")),
                                   "video_id": v, "ctx": ctx, "item": oid})
    n = len({r["video_id"] for r in c.rows if r["type"] == "hn"})
    c.sources.append({"label": "Hacker News (Algolia API)", "type": "hn", "url": "https://hn.algolia.com/api/v1/search",
                      "status": "ok" if n else "skipped (no hits)", "videos": n, "comments": n_comments})
    print(f"OK   Hacker News: {n_comments} chess comments with video links, {n} videos")


def wikipedia(c):
    api = "https://en.wikipedia.org/w/api.php"
    pages = {}
    for q in WIKI_QUERIES:
        cont = {}
        for _ in range(8):
            params = {"action": "query", "format": "json", "generator": "search", "gsrsearch": q, "gsrnamespace": 0,
                      "gsrlimit": 50, "prop": "extlinks", "ellimit": "max", **cont}
            st, txt = polite_get(api, params=params, delay=1.0)
            if st != 200:
                break
            j = json.loads(txt)
            for pg in (j.get("query") or {}).get("pages", {}).values():
                pages.setdefault(pg["title"], set()).update(l.get("*") or l.get("url", "") for l in pg.get("extlinks", []))
            if "continue" not in j:
                break
            cont = {k: v for k, v in j["continue"].items()}
            if len(pages) > 400:
                break
    n_pages = 0
    for title, links in pages.items():
        blob = "\n".join(links)
        ids = video_ids(blob)
        if not ids or len(ids) > 25:
            continue
        n_pages += 1
        label = f"Wikipedia: {title}"
        for v in ids:
            c.rows.append({"source": label, "type": "wikipedia", "dedupe": label, "video_id": v, "ctx": title})
        for ch in channel_ids(blob):
            c.channels[ch].add(label)
    total = len({r["video_id"] for r in c.rows if r["type"] == "wikipedia"})
    c.sources.append({"label": "Wikipedia chess articles (MediaWiki API)", "type": "wikipedia", "url": api,
                      "status": "ok" if total else "skipped (no hits)", "videos": total, "articles_with_videos": n_pages})
    print(f"OK   Wikipedia: {n_pages} articles linking videos, {total} videos")


def main():
    c = Collector()
    github(c)
    for label, url in LICHESS_PAGES:
        st, txt = polite_get(url, delay=1.0)
        c.add_page(label, "lichess", url, txt) if st == 200 else c.fail(label, "lichess", url, st)
    lichess_video_library(c)
    for label, url in WEB_PAGES + LESSON_PAGES:
        st, txt = polite_get(url, delay=1.0)
        c.add_page(label, "web", url, txt) if st == 200 else c.fail(label, "web", url, st)
    hacker_news(c)
    wikipedia(c)
    with open(RAW / "source_links.jsonl", "w", encoding="utf-8") as f:
        for r in c.rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    dump_json(RAW / "source_channels.json", {k: sorted(v) for k, v in c.channels.items()})
    dump_json(RAW / "source_playlists.json", {k: sorted(v) for k, v in c.playlists.items()})
    seeds = load_json(DATA_DIR / "seeds.json", {}) or {}
    seeds["sources"] = c.sources
    seeds["built_sources"] = True
    dump_json(DATA_DIR / "seeds.json", seeds)
    ok = [s for s in c.sources if s["status"] == "ok"]
    print(f"sources ok {len(ok)}/{len(c.sources)}; video rows {len(c.rows)}; unique videos {len({r['video_id'] for r in c.rows})}")


if __name__ == "__main__":
    main()
