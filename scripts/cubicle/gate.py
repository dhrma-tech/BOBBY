"""The "best of best" gate. Pure functions over candidate dicts (no network).

Candidate keys used: id, title, channel, channel_id, tier (0-3), vouches (list of independent vouch labels),
published, duration (sec|None), views, likes, votes, lang, embeddable, public, live, chapters, from_feed.
"""
import re
import statistics

MIN_DUR, MAX_DUR = 4 * 60, 240 * 60

SHORTS = re.compile(r"#shorts?\b|\(shorts?\)|\bshorts?\b\s*$|\byoutube shorts\b", re.I)
LIVE = re.compile(r"🔴|\blive\b|\blivestream\b|\bstreaming now\b|\blive stream\b|\bstream (vod|highlights|replay)\b|\bday \d+ live\b|\bvod\b", re.I)
CLICKBAIT = re.compile(r"you won'?t believe|gone wrong|\bshocking\b|\binsane!{2,}|!{3,}|\bwhat happens next\b|\bexposed\b|\bdestroyed? (his|her|their)\b|\bmust see\b", re.I)
INSTRUCTION = re.compile(r"how to|learn|lesson|tutorial|explained|guide|tips|mistakes|course|principles|basics|strategy|tactics|endgame|opening|improve|analysis|masterclass|speedrun", re.I)
_NONLATIN = re.compile(r"[Ѐ-ӿ؀-ۿऀ-ॿ฀-๿぀-ヿ一-鿿가-힯]")
_FOREIGN_WORDS = re.compile(r"\b(el|la|los|las|una|como|para|por|con|partida|ajedrez|apertura|jugada|aprende|"
                            r"xadrez|abertura|jogada|com|um|uma|échecs|partie|ouverture|comment|schach|eröffnung|spiel|"
                            r"scacchi|apertura|шахматы|satranç|catur|şah)\b", re.I)


def is_shorts(title):
    return bool(SHORTS.search(title or ""))


def is_livestream_title(title):
    return bool(LIVE.search(title or ""))


def is_non_english(title, lang=None):
    if lang and not str(lang).lower().startswith("en"):
        return True
    t = title or ""
    if _NONLATIN.search(t):
        return True
    return len(_FOREIGN_WORDS.findall(t)) >= 2


def is_clickbait(title, llm_relevant=None):
    t = title or ""
    letters = [c for c in t if c.isalpha()]
    caps = sum(c.isupper() for c in letters) / len(letters) if len(letters) > 12 else 0
    hit = bool(CLICKBAIT.search(t)) or caps > 0.8
    return hit and not INSTRUCTION.search(t)


def blocked(c, blocklist):
    bl = blocklist or {}
    if c["id"] in set(bl.get("video_ids", [])):
        return True
    ch = (c.get("channel") or "").lower()
    if ch and ch in {x.lower() for x in bl.get("channels", [])}:
        return True
    t = c.get("title") or ""
    return any(re.search(p, t, re.I) for p in bl.get("title_patterns", []))


def channel_stats(cands):
    """Per channel: median views and median like-ratio over its candidates (needs >= 3 data points)."""
    by = {}
    for c in cands:
        by.setdefault(c.get("channel_id") or c.get("channel"), []).append(c)
    out = {}
    for k, vs in by.items():
        views = [v["views"] for v in vs if v.get("views")]
        ratios = [ratio(v) for v in vs if ratio(v) is not None]
        out[k] = {"views_median": statistics.median(views) if len(views) >= 3 else None,
                  "ratio_median": statistics.median(ratios) if len(ratios) >= 3 else None,
                  "views_sorted": sorted(views)}
    return out


def ratio(c):
    """Like ratio (likes/views) with the API; keyless fallback is rating votes/views from the RSS feed."""
    v = c.get("views")
    if not v:
        return None
    n = c.get("likes") if c.get("likes") is not None else c.get("votes")
    return None if n is None else n / v


def engagement_bar(c, stats):
    s = stats.get(c.get("channel_id") or c.get("channel"), {})
    if not c.get("views") or s.get("views_median") is None:
        return False
    if c["views"] < s["views_median"]:
        return False
    r = ratio(c)
    return r is not None and s.get("ratio_median") is not None and r >= s["ratio_median"]


def rule_reasons(c, blocklist=None):
    """Hard rejections that apply to every candidate regardless of vouches."""
    r = []
    if is_shorts(c.get("title")):
        r.append("shorts")
    if c.get("embeddable") is False:
        r.append("not-embeddable")
    if c.get("public") is False:
        r.append("not-public")
    if c.get("live") in ("live", "upcoming"):
        r.append("live-now")
    d = c.get("duration")
    if d is not None and not (MIN_DUR <= d <= MAX_DUR):
        r.append("duration")
    if is_non_english(c.get("title"), c.get("lang")):
        r.append("non-english")
    if is_livestream_title(c.get("title")) and not (c.get("chapters") or 0) > 0:
        r.append("livestream-no-chapters")
    if is_clickbait(c.get("title")):
        r.append("clickbait")
    if blocklist is not None and blocked(c, blocklist):
        r.append("blocklist")
    return r


def passes(c, stats, keyless, blocklist=None):
    """Returns (keep: bool, reason: str). keep if >=2 independent vouches, or tier 1/2 AND engagement bar
    (key-less: tier 1/2 AND member of the channel's long-form upload feed - engagement is unknown there)."""
    bad = rule_reasons(c, blocklist)
    if bad:
        return False, bad[0]
    if n_vouches(c) >= 2:
        return True, "vouches>=2"
    if c.get("tier") in (1, 2):
        if keyless:
            return (True, "tier-feed") if c.get("from_feed") else (False, "no-feed-no-vouches")
        return (True, "tier+engagement") if engagement_bar(c, stats) else (False, "below-engagement-bar")
    return False, "insufficient-signal"


def n_vouches(c):
    v = c.get("vouches", 0)
    return len(v) if isinstance(v, (list, tuple, set)) else int(v or 0)
