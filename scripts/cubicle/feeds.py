"""YouTube's official RSS/Atom feeds (public, no key): channel_id=, user=, playlist_id=.
Each entry carries video id, title, published date, author, and (as media:community) view count and
rating votes - the only engagement signal available key-less."""
import xml.etree.ElementTree as ET

from common import polite_get

NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
      "m": "http://search.yahoo.com/mrss/"}
BASE = "https://www.youtube.com/feeds/videos.xml"


def parse_feed(xml_text):
    root = ET.fromstring(xml_text)
    title = (root.findtext("a:title", default="", namespaces=NS) or "").strip()
    cid = root.findtext("yt:channelId", default=None, namespaces=NS)
    author = root.findtext("a:author/a:name", default="", namespaces=NS)
    entries = []
    for e in root.findall("a:entry", NS):
        stats = e.find("m:group/m:community/m:statistics", NS)
        rating = e.find("m:group/m:community/m:starRating", NS)
        entries.append({
            "id": e.findtext("yt:videoId", default="", namespaces=NS),
            "title": (e.findtext("a:title", default="", namespaces=NS) or "").strip(),
            "published": (e.findtext("a:published", default="", namespaces=NS) or "")[:10],
            "channel": (e.findtext("a:author/a:name", default="", namespaces=NS) or "").strip(),
            "channel_id": ("UC" + e.findtext("yt:channelId", default="", namespaces=NS)) if e.findtext("yt:channelId", namespaces=NS) else None,
            "views": int(stats.get("views")) if stats is not None and stats.get("views") else None,
            "votes": int(rating.get("count")) if rating is not None and rating.get("count") else None,
        })
    return {"title": title, "author": author.strip(), "channel_id": cid, "entries": [x for x in entries if x["id"]]}


def fetch_feed(kind, value, cache=True):
    """kind in channel_id | user | playlist_id. Returns parsed dict or None (non-200 / unparsable)."""
    st, txt = polite_get(BASE, params={kind: value}, delay=0.8, cache=cache)
    if st != 200:
        return None
    try:
        return parse_feed(txt)
    except ET.ParseError:
        return None


def uulf_feed(channel_id, cache=True):
    """Long-form uploads feed (excludes Shorts). Falls back to UU (all uploads) -> (feed, kind)."""
    suffix = channel_id[2:]
    f = fetch_feed("playlist_id", "UULF" + suffix, cache)
    if f and f["entries"]:
        return f, "UULF"
    f = fetch_feed("playlist_id", "UU" + suffix, cache)
    if f and f["entries"]:
        return f, "UU"
    return None, None
