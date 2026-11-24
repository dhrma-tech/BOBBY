"""YouTube Data API v3 helpers (only used when YT_API_KEY is set). Quota counter persists per UTC day in
data/cubicle/raw/api_usage.json so a run can stop at the 9,400-unit budget and resume the next day."""
import datetime as dt
import os
import re
import time

import requests

from common import RAW, UA, dump_json, load_json

API = "https://www.googleapis.com/youtube/v3"
BUDGET = 9400
COST = {"search": 100}
USAGE = RAW / "api_usage.json"


class QuotaStop(SystemExit):
    pass


def key():
    return os.environ.get("YT_API_KEY")


def used_today():
    u = load_json(USAGE, {}) or {}
    return int(u.get(dt.datetime.now(dt.timezone.utc).date().isoformat(), 0))


def _add(units):
    u = load_json(USAGE, {}) or {}
    d = dt.datetime.now(dt.timezone.utc).date().isoformat()
    u = {d: int(u.get(d, 0)) + units}  # keep only today
    dump_json(USAGE, u)


def call(ep, **params):
    cost = COST.get(ep, 1)
    if used_today() + cost > BUDGET:
        raise QuotaStop(f"quota budget {BUDGET} units reached for today; rerun tomorrow (resumable)")
    for attempt in range(4):
        r = requests.get(f"{API}/{ep}", params={**params, "key": key()}, headers={"User-Agent": UA}, timeout=30)
        if r.status_code == 200:
            _add(cost)
            return r.json()
        if r.status_code in (403, 429) and "quota" in r.text.lower():
            raise QuotaStop("YouTube quota exhausted; rerun tomorrow (resumable)")
        if r.status_code in (400, 404):
            return None
        time.sleep(2 * (attempt + 1))
    return None


def iso_dur(s):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def channel_by_handle(handle):
    j = call("channels", part="id,snippet", forHandle=handle.lstrip("@"))
    items = (j or {}).get("items") or []
    return (items[0]["id"], items[0]["snippet"]["title"]) if items else None


def channel_search(q):
    j = call("search", part="snippet", type="channel", q=q, maxResults=3)
    items = (j or {}).get("items") or []
    return [(i["snippet"]["channelId"], i["snippet"]["title"]) for i in items]


def channel_playlists(channel_id):
    out, tok = [], None
    for _ in range(4):
        j = call("playlists", part="snippet", channelId=channel_id, maxResults=50, **({"pageToken": tok} if tok else {}))
        if not j:
            break
        out += [(i["id"], i["snippet"]["title"]) for i in j.get("items", [])]
        tok = j.get("nextPageToken")
        if not tok:
            break
    return out


def playlist_items(pl, pages=4):
    tok, out = None, []
    for _ in range(pages):
        j = call("playlistItems", part="snippet,contentDetails", playlistId=pl, maxResults=50,
                 **({"pageToken": tok} if tok else {}))
        if not j:
            break
        for it in j.get("items", []):
            sn = it["snippet"]
            out.append({"id": it["contentDetails"]["videoId"], "title": sn.get("title"),
                        "channel": sn.get("videoOwnerChannelTitle"), "channel_id": sn.get("videoOwnerChannelId"),
                        "published": (it["contentDetails"].get("videoPublishedAt") or sn.get("publishedAt") or "")[:10]})
        tok = j.get("nextPageToken")
        if not tok:
            break
    return out


def channel_uploads(channel_id, pages=2):
    """Long-form uploads playlist (UULF) falls back to all uploads (UU)."""
    for prefix in ("UULF", "UU"):
        items = playlist_items(prefix + channel_id[2:], pages)
        if items:
            return items
    return []


def videos_list(ids):
    """videos.list for up to 50 ids -> dict id -> meta (1 unit per call)."""
    j = call("videos", part="snippet,contentDetails,statistics,status", id=",".join(ids))
    out = {}
    for v in (j or {}).get("items", []):
        sn, cd, st, ss = v["snippet"], v["contentDetails"], v.get("statistics", {}), v.get("status", {})
        desc = sn.get("description") or ""
        chapters = len(re.findall(r"(?m)^\s*\(?\d{1,2}:\d{2}(?::\d{2})?\)?\s", desc))
        out[v["id"]] = {
            "duration": iso_dur(cd.get("duration")), "published": (sn.get("publishedAt") or "")[:10],
            "views": int(st.get("viewCount", 0) or 0), "likes": int(st["likeCount"]) if "likeCount" in st else None,
            "lang": sn.get("defaultAudioLanguage") or sn.get("defaultLanguage"),
            "embeddable": bool(ss.get("embeddable", True)), "public": ss.get("privacyStatus", "public") == "public",
            "live": sn.get("liveBroadcastContent", "none"), "chapters": chapters,
            "title": sn.get("title"), "channel": sn.get("channelTitle"), "channel_id": sn.get("channelId"),
        }
    return out
