"""Scoring, freshness, outdated tag, the "modern" rule and diversity caps. Pure functions.

score = signal x (0.5 + 0.5 x freshness)
signal = 2.0 x min(vouches, 3) + tier weight (1=2.0, 2=1.2, 3=0.6) + 0.8 x normalised engagement
         + 0.4 if published in the last 24 months
freshness = 0.5 ** (age_years / half_life); half-life evergreen 10y, semi 4y, fast 1y.
Unknown publish date -> freshness UNKNOWN_FRESHNESS (0.6), no recency bonus, never flagged outdated.
"""
import datetime as dt
import math

HALF_LIFE = {"evergreen": 10.0, "semi": 4.0, "fast": 1.0}
TIER_WEIGHT = {1: 2.0, 2: 1.2, 3: 0.6, 0: 0.0}
UNKNOWN_FRESHNESS = 0.6
OUTDATED_BELOW = 0.4
MODERN_CUTOFF_YEAR = 2015
MODERN_MAX_FRAC = 0.10
CAP_PER_CHANNEL_NODE = 6
CAP_PER_NODE = 25
CAP_CHANNEL_FRAC = 0.10


def parse_date(s):
    try:
        return dt.date.fromisoformat(s[:10]) if s else None
    except ValueError:
        return None


def freshness(published, shelf, today=None):
    d = parse_date(published)
    if d is None:
        return UNKNOWN_FRESHNESS
    today = today or dt.date.today()
    age = max((today - d).days, 0) / 365.25
    return 0.5 ** (age / HALF_LIFE[shelf])


def is_outdated(fresh, shelf, published):
    return int(shelf != "evergreen" and parse_date(published) is not None and fresh < OUTDATED_BELOW)


def is_recent(published, today=None, months=24):
    d = parse_date(published)
    if d is None:
        return False
    today = today or dt.date.today()
    return (today - d).days <= months * 30.4375


def engagement_norm(c, views_sorted):
    """0..1. Percentile of views within the channel's candidates (>=3 data points), else log scale, else 0."""
    v = c.get("views")
    if not v:
        return 0.0
    if len(views_sorted) >= 3:
        below = sum(1 for x in views_sorted if x < v)
        return below / (len(views_sorted) - 1) if len(views_sorted) > 1 else 0.0
    return min(1.0, math.log10(v + 1) / 7.0)


def signal(vouches, tier, eng, recent):
    return 2.0 * min(vouches, 3) + TIER_WEIGHT.get(tier, 0.0) + 0.8 * eng + (0.4 if recent else 0.0)


def score(vouches, tier, eng, recent, fresh):
    return signal(vouches, tier, eng, recent) * (0.5 + 0.5 * fresh)


def apply_modern_rule(rows):
    """rows: dicts with published, shelf, tier, vouches(int), sc. Pre-2015 videos are kept only for evergreen
    nodes from tier-1 channels or with >=2 vouches, and at most 10% of the catalogue."""
    def old(r):
        d = parse_date(r.get("published"))
        return d is not None and d.year < MODERN_CUTOFF_YEAR
    keep = [r for r in rows if not old(r) or (r["shelf"] == "evergreen" and (r["tier"] == 1 or r["vouches"] >= 2))]
    while True:
        olds = [r for r in keep if old(r)]
        if len(olds) <= MODERN_MAX_FRAC * len(keep):
            break
        worst = min(olds, key=lambda r: r["sc"])
        keep.remove(worst)
    return keep


def apply_caps(rows, per_channel_node=CAP_PER_CHANNEL_NODE, per_node=CAP_PER_NODE, channel_frac=CAP_CHANNEL_FRAC):
    """rows: dicts with n (node), ck (channel key), sc. Best score wins within each cap."""
    rows = sorted(rows, key=lambda r: -r["sc"])
    seen_cn, out = {}, []
    for r in rows:
        k = (r["n"], r["ck"])
        if seen_cn.get(k, 0) >= per_channel_node:
            continue
        seen_cn[k] = seen_cn.get(k, 0) + 1
        out.append(r)
    count, out2 = {}, []
    for r in out:
        if count.get(r["n"], 0) >= per_node:
            continue
        count[r["n"]] = count.get(r["n"], 0) + 1
        out2.append(r)
    # channel share <= 10% of the final catalogue (iterate: removals shrink the catalogue)
    while True:
        cap = max(1, int(channel_frac * len(out2)))
        per = {}
        for r in out2:
            per[r["ck"]] = per.get(r["ck"], 0) + 1
        over = [ck for ck, n in per.items() if n > cap]
        if not over:
            break
        for ck in over:
            mine = [r for r in out2 if r["ck"] == ck]
            for r in sorted(mine, key=lambda r: r["sc"])[: len(mine) - cap]:
                out2.remove(r)
    return out2
