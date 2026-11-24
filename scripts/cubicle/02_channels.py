"""Step 2: trusted channels (tiered) -> resolve channel ids -> data/cubicle/seeds.json["channels"], ["playlists"].

Tier split: 1 = instruction-heavy channels (weight 2.0), 2 = big general/event channels (1.2).
Tier 3 (weight 0.6) is assigned later to any other channel with >= 3 vouched videos.

Resolution
  with YT_API_KEY : channels.list?forHandle (1 unit), search.list only for unresolved (100 units);
                    named playlists expanded via playlists.list + playlistItems.list.
  key-less        : ONLY from fetched evidence, each candidate verified against the channel's official RSS feed:
                    (a) /channel/UC... links found in fetched sources, (b) Wikidata property P2397 (YouTube channel ID)
                    via the public Wikidata API, (c) the legacy-username RSS endpoint ...videos.xml?user=NAME.
                    A candidate is accepted only if the feed's channel title matches the channel's known names.
  Unresolved channels are dropped and listed in REPORT.md.
"""
import json
import os

import feeds
import yt_api
import re

from common import DATA_DIR, RAW, channel_ids, dump_json, load_json, normalize, polite_get

# name, tier, handle hint (API forHandle), accepted feed titles, wikidata search terms, legacy usernames to try
TRUSTED = [
    ("Daniel Naroditsky", 1, "DanielNaroditskyGM", ["Daniel Naroditsky", "Daniel Naroditsky GM"], ["Daniel Naroditsky"], ["DanielNaroditsky", "GMNaroditsky", "naroditsky"]),
    ("John Bartholomew", 1, "JohnBartholomewChess", ["John Bartholomew"], ["John Bartholomew chess", "John Bartholomew"], ["JohnBartholomew", "ibartholomew", "chessjohn"]),
    ("Aman Hambleton", 1, "AmanHambleton", ["Aman Hambleton"], ["Aman Hambleton"], ["AmanHambleton"]),
    ("Hanging Pawns", 1, "HangingPawns", ["Hanging Pawns"], ["Hanging Pawns chess"], ["HangingPawns"]),
    ("Ben Finegold", 1, "GMBenjaminFinegold", ["Ben Finegold", "GM Ben Finegold", "GM Benjamin Finegold"], ["Ben Finegold", "Benjamin Finegold"], ["BenFinegold", "GMBenFinegold", "finegold"]),
    ("Chess Dojo", 1, "ChessDojo", ["ChessDojo", "Chess Dojo"], ["ChessDojo"], ["ChessDojo", "chessdojo"]),
    ("Remote Chess Academy", 1, "RemoteChessAcademy", ["Remote Chess Academy"], ["Remote Chess Academy"], ["RemoteChessAcademy", "remotechessacademy"]),
    ("PowerPlay Chess (Daniel King)", 1, "PowerPlayChess", ["PowerPlay Chess", "Power Play Chess", "PowerPlayChess"], ["Daniel King chess", "PowerPlay Chess"], ["PowerPlayChess", "powerplaychess"]),
    ("GothamChess", 2, "GothamChess", ["GothamChess"], ["GothamChess", "Levy Rozman"], ["GothamChess"]),
    ("agadmator", 2, "agadmator", ["agadmator's Chess Channel", "agadmator"], ["agadmator"], ["agadmator"]),
    ("Chess.com", 2, "chess", ["Chess.com", "chess.com", "Chess"], ["Chess.com"], ["chesscom", "Chesscom", "chess"]),
    ("Lichess", 2, "lichess", ["Lichess", "Lichess.org", "lichess.org"], ["Lichess"], ["lichess", "lichessorg", "LichessDotOrg"]),
    ("Saint Louis Chess Club", 2, "STLChessClub", ["Saint Louis Chess Club"], ["Saint Louis Chess Club"], ["STLChessClub"]),
    ("Hikaru (GMHikaru)", 2, "GMHikaru", ["GMHikaru", "GM Hikaru", "Hikaru"], ["Hikaru Nakamura"], ["GMHikaru", "Hikaru"]),
    ("Eric Rosen", 2, "EricRosen", ["Eric Rosen", "EricRosen"], ["Eric Rosen", "Eric Rosen chess"], ["EricRosen", "ericrosen"]),
    ("ChessNetwork", 2, "ChessNetwork", ["ChessNetwork"], ["ChessNetwork"], ["ChessNetwork"]),
    ("Chessbrah", 2, "chessbrah", ["chessbrah", "Chessbrah"], ["Chessbrah"], ["chessbrah"]),
    ("Anna Cramling", 2, "AnnaCramling", ["Anna Cramling"], ["Anna Cramling"], ["AnnaCramling"]),
    ("Magnus Carlsen", 2, "themagnuscarlsen", ["Magnus Carlsen"], ["Magnus Carlsen"], ["MagnusCarlsen", "themagnuscarlsen"]),
    ("Chessable", 2, "Chessable", ["Chessable"], ["Chessable"], ["Chessable", "chessable"]),
    ("Kingscrusher", 2, "kingscrusher", ["kingscrusher", "Kingscrusher"], ["Kingscrusher"], ["kingscrusher"]),
    ("ChessBase India", 2, "ChessBaseIndiachannel", ["ChessBase India"], ["ChessBase India"], ["ChessBaseIndia", "chessbaseindia", "ChessBaseIndiachannel"]),
    ("chess24", 2, "chess24", ["chess24"], ["chess24"], ["chess24"]),
    ("BotezLive", 2, "BotezLive", ["BotezLive"], ["Alexandra Botez", "Andrea Botez", "Botez sisters"], ["BotezLive", "botezlive"]),
    ("FIDE", 2, "FIDE", ["FIDE", "FIDE - International Chess Federation", "FIDE Chess"], ["FIDE"], ["FIDE", "fide", "FIDEchess"]),
    ("Tata Steel Chess", 2, "TataSteelChess", ["Tata Steel Chess", "Tata Steel Chess Tournament"], ["Tata Steel Chess"], ["TataSteelChess", "tatasteelchess"]),
    ("Norway Chess", 2, "NorwayChess", ["Norway Chess"], ["Norway Chess"], ["NorwayChess", "norwaychess"]),
    ("Grand Chess Tour", 2, "GrandChessTour", ["Grand Chess Tour"], ["Grand Chess Tour"], ["GrandChessTour", "grandchesstour"]),
]

PLAYLISTS = [  # (channel name, title substring, seed id)
    ("Daniel Naroditsky", "master class speedrun", "Master Class Speedrun"),
    ("Daniel Naroditsky", "opening theory speedrun", "Opening Theory Speedrun"),
    ("John Bartholomew", "chess fundamentals", "Chess Fundamentals"),
    ("John Bartholomew", "climbing the rating ladder", "Climbing the Rating Ladder"),
    ("Aman Hambleton", "building habits", "Building Habits"),
]
WD = "https://www.wikidata.org/w/api.php"


def wikidata_channel_ids(term):
    """Fetched evidence: Wikidata property P2397 (YouTube channel ID) of entities matching a search term."""
    st, txt = polite_get(WD, params={"action": "wbsearchentities", "search": term, "language": "en", "format": "json", "limit": 5}, delay=0.5)
    if st != 200:
        return []
    qids = [h["id"] for h in json.loads(txt).get("search", [])]
    if not qids:
        return []
    st, txt = polite_get(WD, params={"action": "wbgetentities", "ids": "|".join(qids), "props": "claims|labels",
                                     "languages": "en", "format": "json"}, delay=0.5)
    if st != 200:
        return []
    out = []
    for q, ent in json.loads(txt).get("entities", {}).items():
        for cl in (ent.get("claims", {}).get("P2397") or []):
            v = cl.get("mainsnak", {}).get("datavalue", {}).get("value")
            if isinstance(v, str) and v.startswith("UC"):
                out.append((v, f"wikidata:{q}"))
    return out


def wikipedia_channel_evidence(term):
    """English Wikipedia external links of the best-matching articles: /channel/UC.. ids and /user/NAME legacy names."""
    api = "https://en.wikipedia.org/w/api.php"
    st, txt = polite_get(api, params={"action": "query", "list": "search", "srsearch": term + " chess", "srlimit": 3,
                                      "format": "json"}, delay=0.5)
    if st != 200:
        return [], []
    titles = [h["title"] for h in json.loads(txt).get("query", {}).get("search", [])]
    ids, users = [], []
    for t in titles:
        st, txt = polite_get(api, params={"action": "query", "prop": "extlinks", "titles": t, "ellimit": "max",
                                          "format": "json"}, delay=0.5)
        if st != 200:
            continue
        for pg in json.loads(txt).get("query", {}).get("pages", {}).values():
            for l in pg.get("extlinks", []):
                u = l.get("*") or l.get("url", "")
                ids += [(c, f"wikipedia:{t}") for c in channel_ids(u)]
                m = re.search(r"youtube\.com/user/([A-Za-z0-9_.-]+)", u)
                if m:
                    users.append((m.group(1), f"wikipedia:{t}"))
    return ids, users


def verify(cid, accepted):
    """Feed for channel_id must exist and its title must match one of the accepted names."""
    f = feeds.fetch_feed("channel_id", cid)
    if not f:
        return None
    names = {normalize(a) for a in accepted}
    if normalize(f["title"]) in names or normalize(f["author"]) in names:
        return f
    return ("mismatch", f["title"])


def resolve_keyless(row, src_channels):
    name, tier, handle, accepted, wd_terms, legacy = row
    tried = []
    cands = [(c, "source:" + labels[0]) for c, labels in src_channels.items()]
    wp_users = []
    for t in wd_terms:
        cands += wikidata_channel_ids(t)
        ids, users = wikipedia_channel_evidence(t)
        cands += ids
        wp_users += users
    for c, how in cands:
        r = verify(c, accepted)
        if isinstance(r, dict):
            return c, how, r
        if isinstance(r, tuple):
            tried.append(f"{c} ({how}) is '{r[1]}'")
    for u, how in [(u, "rss-user:" + u) for u in legacy] + [(u, how.replace("wikipedia", "rss-user via wikipedia")) for u, how in wp_users]:
        f = feeds.fetch_feed("user", u)
        if not f or not f["channel_id"]:
            continue
        cid = "UC" + f["channel_id"]
        if normalize(f["title"]) in {normalize(a) for a in accepted}:
            return cid, how, f
        tried.append(f"user={u} is '{f['title']}'")
    return None, "; ".join(tried[:4]) or "no evidence found", None


def resolve_api(row):
    name, tier, handle, accepted, wd_terms, legacy = row
    r = yt_api.channel_by_handle(handle)
    if r:
        return r[0], "api:forHandle"
    for cid, title in yt_api.channel_search(name):
        if normalize(title) in {normalize(a) for a in accepted}:
            return cid, "api:search"
    return None, "api: not found"


def main():
    use_api = bool(yt_api.key())
    src_channels = load_json(RAW / "source_channels.json", {}) or {}
    # only keep source UC ids that are plausibly ours (verified by feed title in resolve_keyless)
    channels, failed = [], []
    for row in TRUSTED:
        name, tier = row[0], row[1]
        if use_api:
            cid, how = resolve_api(row)
            ok = bool(cid)
        else:
            cid, how, _ = resolve_keyless(row, src_channels)
            ok = bool(cid)
        entry = {"name": name, "tier": tier, "handle": row[2], "id": cid, "how": how if ok else None}
        if ok:
            channels.append(entry)
            print(f"OK   T{tier} {name}: {cid} via {how}")
        else:
            failed.append({"name": name, "tier": tier, "reason": how})
            print(f"MISS T{tier} {name}: {how}")
    # playlists
    playlists = []
    by_name = {c["name"]: c for c in channels}
    if use_api:
        for ch, sub, label in PLAYLISTS:
            c = by_name.get(ch)
            if not c:
                continue
            for pid, title in yt_api.channel_playlists(c["id"]):
                if sub in title.lower():
                    playlists.append({"id": pid, "title": title, "label": label, "channel": ch, "how": "api"})
                    break
            else:
                failed.append({"name": f"playlist: {label}", "tier": 1, "reason": "not found by title"})
    else:
        for label in [p[2] for p in PLAYLISTS]:
            failed.append({"name": f"playlist: {label}", "tier": 1, "reason": "no playlist id in any fetched source; key-less cannot search by title"})
        for pid, labels in (load_json(RAW / "source_playlists.json", {}) or {}).items():
            f = feeds.fetch_feed("playlist_id", pid)
            if f and f["entries"] and sum("chess" in e["title"].lower() for e in f["entries"]) >= 3:
                playlists.append({"id": pid, "title": f["title"], "label": f["title"], "channel": f["author"],
                                  "how": "source:" + labels[0], "sources": labels})
                print(f"OK   playlist from source: {pid} '{f['title']}' ({len(f['entries'])} items)")
    seeds = load_json(DATA_DIR / "seeds.json", {}) or {}
    seeds["channels"] = channels
    seeds["unresolved_channels"] = failed
    seeds["playlists"] = playlists
    seeds["tier_weights"] = {"1": 2.0, "2": 1.2, "3": 0.6}
    seeds["tier_rule"] = ("tier 1 = instruction-heavy channels; tier 2 = large general/event channels; "
                          "tier 3 = any other channel with >= 3 vouched videos (assigned at scoring time)")
    dump_json(DATA_DIR / "seeds.json", seeds)
    print(f"resolved {len(channels)}/{len(TRUSTED)} channels")


if __name__ == "__main__":
    main()
