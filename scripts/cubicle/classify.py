"""Rule-based classification: title (+ channel) -> one node, one level, one kind.

Keyword syntax from taxonomy.json: a plain keyword matches as a whole word/phrase (plural tolerant:
s/es/ed/ing); `stem*` matches any word starting with stem. Score of a node = sum over matched keywords of
(1 + 0.6 * extra words) so multi-word keywords beat single generic ones; ties go to the earlier node.
"""
import re

KINDS = ("lesson", "course", "gameplay", "review", "tips", "recap", "talk")
SECTION_KIND = {"analysis": "review", "gameplay": "gameplay", "news": "recap", "legends": "talk"}


def _compile(kw):
    kw = kw.strip().lower()
    if kw.endswith("*"):
        return re.compile(r"(?<![a-z0-9])" + re.escape(kw[:-1]), re.I)
    return re.compile(r"(?<![a-z0-9])" + re.escape(kw) + r"(?:s|es|ed|ing)?(?![a-z0-9])", re.I)


class Classifier:
    def __init__(self, taxonomy):
        self.nodes = []  # (node_dict, section_id, [(regex, weight)])
        self.section_of = {}
        for s in taxonomy["sections"]:
            for n in s["nodes"]:
                pats = [(_compile(k), 1 + 0.6 * (len(re.findall(r"[a-z0-9]+", k)) - 1)) for k in n.get("keywords", [])]
                self.nodes.append((n, s["id"], pats))
                self.section_of[n["id"]] = s["id"]
        self.node = {n["id"]: n for n, _, _ in self.nodes}

    def match(self, title):
        best = None
        for n, sid, pats in self.nodes:
            sc = sum(w for rx, w in pats if rx.search(title))
            if sc > 0 and (best is None or sc > best[0]):
                best = (sc, n["id"], sid)
        return best

    def classify(self, title, channel=""):
        title = title or ""
        m = self.match(title)
        if not m:
            m2 = _fallback(title)
            if not m2:
                return None
            nid = m2
            if nid not in self.node:
                return None
            sc, sid = 0.5, self.section_of[nid]
        else:
            sc, nid, sid = m
        node = self.node[nid]
        return {"node": nid, "section": sid, "match": round(sc, 2),
                "level": infer_level(title, node["level"]), "kind": infer_kind(title, sid)}


def _fallback(title):
    """Titles with no keyword hit: 'A vs B' game videos and speed formats are still clearly gameplay/analysis."""
    t = title.lower()
    if re.search(r"\b(blitz|bullet)\b", t):
        return "gp-blitz" if "blitz" in t else "gp-bullet"
    if re.search(r"\bvs\.?\b|\bversus\b", t):
        return "an-modern"
    return None


_LV_RULES = [
    (re.compile(r"\b(absolute |complete )?beginners?\b|for beginners|chess basics|learn chess|how to play chess|under 1000|below 1000", re.I), "b"),
    (re.compile(r"\b(advanced|master ?class|masters?|grandmasters?|2[0-9]{3}\+|2000\+|super gm|gm level|elite)\b", re.I), "a"),
    (re.compile(r"\b(intermediate|club player)\b", re.I), "i"),
]


def infer_level(title, default):
    m = re.search(r"\b(?:under|below|sub|<)\s*(\d{3,4})\b", title, re.I) or re.search(r"\b(\d{3,4})\s*(?:elo|rated|rating)\b", title, re.I)
    if m:
        r = int(m.group(1))
        return "b" if r <= 1000 else "i" if r <= 1600 else "a" if r <= 2000 else "x"
    for rx, lv in _LV_RULES:
        if rx.search(title):
            return lv
    return default


def infer_kind(title, section):
    t = title.lower()
    if re.search(r"documentary|interview|podcast|biography|\bstory of\b|\btalks?\b|q&a|\bama\b|sits down", t):
        return "talk"
    if section == "news" or re.search(r"\bround \d|\bday \d|recap|highlights|wrap[- ]up|\bresults\b", t):
        return "recap"
    if section == "gameplay":
        return "gameplay"
    if re.search(r"\bvs\.?\b|\bversus\b", t) and section in ("analysis",):
        return "review"
    if re.search(r"full course|\bcourse\b|masterclass|master class|\bepisode\b|\bepisode\b|\bpart \d|\bchapter\b|\bseries\b|complete guide|\blesson \d", t):
        return "course"
    if re.search(r"\btips?\b|mistakes?|tricks?|\bways to\b|\b\d+ (things|rules|secrets|habits|steps|tricks|tips)\b|\bnever\b|\bstop\b", t):
        return "tips"
    if re.search(r"\breview|analy[sz]ing|reacts?\b|reaction|\bgm analy", t):
        return "review"
    if re.search(r"\bhow to\b|\blearn|explained|guide|intro|tutorial|\blesson|basics|understand|principles|\bwhy\b|\bwhat is\b", t):
        return "lesson"
    return SECTION_KIND.get(section, "lesson")
