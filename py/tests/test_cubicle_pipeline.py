"""Cubicle pipeline unit tests: small fixtures, no network."""
import datetime as dt
import sys
from pathlib import Path

CUB = Path(__file__).resolve().parents[2] / "scripts" / "cubicle"
sys.path.insert(0, str(CUB))

import build_taxonomy  # noqa: E402
import classify  # noqa: E402
import gate  # noqa: E402
import scoring  # noqa: E402
import validate_cubicle  # noqa: E402

TODAY = dt.date(2026, 11, 24)


def cand(**kw):
    base = {"id": "x" * 11, "title": "How to play the Italian Game", "channel": "Chan", "channel_id": "UC1", "tier": 0,
            "vouches": 0, "published": "2024-01-01", "duration": None, "views": None, "likes": None, "votes": None,
            "lang": None, "embeddable": None, "public": None, "live": None, "chapters": None, "from_feed": False}
    base.update(kw)
    return base


# ---------- gate ----------
def test_gate_two_vouches_passes_any_channel():
    ok, why = gate.passes(cand(vouches=2), {}, keyless=True)
    assert ok and why == "vouches>=2"


def test_gate_single_vouch_untiered_fails():
    assert gate.passes(cand(vouches=1), {}, keyless=True)[0] is False


def test_gate_keyless_tier_needs_feed_membership():
    assert gate.passes(cand(tier=1), {}, keyless=True) == (False, "no-feed-no-vouches")
    assert gate.passes(cand(tier=2, from_feed=True), {}, keyless=True)[0] is True


def test_gate_api_engagement_bar():
    vids = [cand(id=f"v{i:010d}", tier=1, views=v, likes=l) for i, (v, l) in
            enumerate([(100, 1), (200, 4), (300, 30), (400, 20), (500, 50)])]
    stats = gate.channel_stats(vids)
    # views median 300, ratio median 0.05: 300/10%, 400/5%, 500/10% clear both bars
    assert all(gate.engagement_bar(vids[k], stats) for k in (2, 3, 4))
    assert not gate.engagement_bar(vids[0], stats) and not gate.engagement_bar(vids[1], stats)
    ok, why = gate.passes(vids[4], stats, keyless=False)
    assert ok and why == "tier+engagement"
    assert gate.passes(vids[0], stats, keyless=False)[0] is False


def test_gate_rules():
    assert "shorts" in gate.rule_reasons(cand(title="Fork trick #shorts"))
    assert "duration" in gate.rule_reasons(cand(duration=90))
    assert "duration" in gate.rule_reasons(cand(duration=5 * 3600))
    assert "duration" not in gate.rule_reasons(cand(duration=1500))
    assert "not-embeddable" in gate.rule_reasons(cand(embeddable=False))
    assert "non-english" in gate.rule_reasons(cand(title="Como jugar al ajedrez para principiantes"))
    assert "non-english" in gate.rule_reasons(cand(title="Шахматы для начинающих"))
    assert "non-english" in gate.rule_reasons(cand(lang="es"))
    assert "livestream-no-chapters" in gate.rule_reasons(cand(title="🔴 LIVE chess stream"))
    assert "livestream-no-chapters" not in gate.rule_reasons(cand(title="LIVE chess lesson", chapters=5))
    assert "clickbait" in gate.rule_reasons(cand(title="YOU WON'T BELIEVE WHAT HAPPENED!!!"))
    assert "clickbait" not in gate.rule_reasons(cand(title="You won't believe this opening trap - tutorial"))


def test_gate_blocklist():
    bl = {"video_ids": ["abc"], "channels": ["Spam"], "title_patterns": [r"\bre-?upload"]}
    assert gate.blocked(cand(id="abc"), bl)
    assert gate.blocked(cand(channel="spam"), bl)
    assert gate.blocked(cand(title="Najdorf 2D Reupload"), bl)
    assert not gate.blocked(cand(), bl)
    assert gate.passes(cand(vouches=3, id="abc"), {}, True, bl) == (False, "blocklist")


# ---------- scoring / freshness ----------
def test_freshness_half_lives():
    one_year = dt.date(2025, 11, 24)
    assert abs(scoring.freshness("2025-11-24", "fast", TODAY) - 0.5 ** (365 / 365.25)) < 1e-3
    assert abs(scoring.freshness("2016-11-24", "evergreen", TODAY) - 0.5 ** (10.0 / 10.0)) < 0.01
    assert abs(scoring.freshness("2022-11-24", "semi", TODAY) - 0.5) < 0.01
    assert scoring.freshness(one_year.isoformat(), "evergreen", TODAY) > scoring.freshness(one_year.isoformat(), "fast", TODAY)


def test_unknown_date_freshness_is_0_6():
    assert scoring.freshness(None, "fast", TODAY) == 0.6
    assert scoring.is_outdated(0.6, "fast", None) == 0
    assert scoring.is_recent(None, TODAY) is False


def test_outdated_tag():
    f_old = scoring.freshness("2022-01-01", "fast", TODAY)
    assert f_old < 0.4 and scoring.is_outdated(f_old, "fast", "2022-01-01") == 1
    assert scoring.is_outdated(f_old, "evergreen", "2022-01-01") == 0  # never for evergreen
    assert scoring.is_outdated(0.9, "fast", "2026-10-01") == 0


def test_score_formula():
    # 2 vouches, tier 1, engagement 0.5, recent, fresh 0.8
    sig = 2.0 * 2 + 2.0 + 0.8 * 0.5 + 0.4
    assert abs(scoring.signal(2, 1, 0.5, True) - sig) < 1e-9
    assert abs(scoring.score(2, 1, 0.5, True, 0.8) - sig * (0.5 + 0.5 * 0.8)) < 1e-9
    assert scoring.signal(9, 0, 0, False) == 6.0  # vouches capped at 3
    assert scoring.TIER_WEIGHT == {1: 2.0, 2: 1.2, 3: 0.6, 0: 0.0}


def test_engagement_norm_percentile():
    views = [10, 20, 30, 40]
    assert scoring.engagement_norm({"views": 40}, views) == 1.0
    assert scoring.engagement_norm({"views": 10}, views) == 0.0
    assert scoring.engagement_norm({"views": None}, views) == 0.0


def row(i, n="a", ck="c1", sc=1.0, pub="2024-01-01", shelf="evergreen", tier=0, vouches=0):
    return {"i": i, "n": n, "ck": ck, "sc": sc, "published": pub, "shelf": shelf, "tier": tier, "vouches": vouches}


def test_modern_rule_eligibility():
    rows = [row("old-e-t1", pub="2010-01-01", tier=1), row("old-e-v2", pub="2010-01-01", vouches=2),
            row("old-e-none", pub="2010-01-01"), row("old-semi-t1", pub="2010-01-01", shelf="semi", tier=1)]
    rows += [row(f"new{i}", pub="2024-05-05") for i in range(40)]
    ids = {r["i"] for r in scoring.apply_modern_rule(rows)}
    assert "old-e-t1" in ids and "old-e-v2" in ids
    assert "old-e-none" not in ids and "old-semi-t1" not in ids


def test_modern_rule_ten_percent_cap():
    old = [row(f"o{i}", pub="2005-01-01", tier=1, sc=10 - i * 0.1) for i in range(10)]
    new = [row(f"n{i}", pub="2024-01-01") for i in range(40)]
    kept = scoring.apply_modern_rule(old + new)
    n_old = sum(1 for r in kept if r["i"].startswith("o"))
    assert n_old <= 0.10 * len(kept)
    assert n_old >= 4 and "o0" in {r["i"] for r in kept}  # best-scoring old ones survive


def test_caps_per_channel_node_and_node():
    rows = [row(f"a{i}", n="n1", ck="c1", sc=10 - i * 0.01) for i in range(10)]
    rows += [row(f"b{i}", n="n1", ck=f"c{i + 2}", sc=1 - i * 0.01) for i in range(40)]
    out = scoring.apply_caps(rows, per_channel_node=6, per_node=25, channel_frac=1.0)
    assert sum(1 for r in out if r["ck"] == "c1") == 6
    assert len(out) == 25
    assert {r["i"] for r in out if r["ck"] == "c1"} == {f"a{i}" for i in range(6)}  # best kept


def test_caps_channel_share():
    rows = []
    for k in range(12):  # 12 nodes x 5 videos from channel c1, plus 140 other channels
        rows += [row(f"x{k}_{j}", n=f"n{k}", ck="c1", sc=5.0) for j in range(1)]
    rows += [row(f"y{i}", n=f"m{i % 20}", ck=f"o{i}", sc=1.0) for i in range(88)]
    out = scoring.apply_caps(rows, channel_frac=0.10)
    n_c1 = sum(1 for r in out if r["ck"] == "c1")
    assert n_c1 <= max(1, int(0.10 * len(out)))


# ---------- classification ----------
def clf():
    sections, _ = build_taxonomy.build()
    return classify.Classifier({"sections": sections})


def test_taxonomy_shape():
    sections, n = build_taxonomy.build()
    assert [s["id"] for s in sections] == ["start", "tactics", "calc", "strategy", "open-e4", "open-d4", "open-flank", "def-e4",
                                           "def-d4", "gambits", "open-study", "middlegame", "endgames", "analysis", "gameplay",
                                           "news", "improve", "speed", "legends"]
    assert {s["id"]: s["floor"] for s in sections}["tactics"] == 70
    ids = [x["id"] for s in sections for x in s["nodes"]]
    assert len(ids) == len(set(ids)) == n
    for s in sections:
        for x in s["nodes"]:
            assert x["shelf"] in ("evergreen", "semi", "fast") and x["level"] in "biax"
            assert x["practice"].startswith("#/")


def test_classify_nodes():
    c = clf()
    assert c.classify("Knight Forks Explained for Beginners")["node"] == "tac-fork"
    assert c.classify("The Lucena Position - Rook Endgame Technique")["node"] == "end-rook"
    assert c.classify("Sicilian Najdorf: Complete Guide")["node"] == "de-najdorf"
    assert c.classify("How to Play the London System")["node"] == "od-london"
    assert c.classify("Opposition and Triangulation in Pawn Endings")["node"] == "end-pawn"
    assert c.classify("Smith-Morra Gambit traps")["node"] == "gam-morra"
    assert c.classify("zzz qqq nothing relevant") is None


def test_classify_level_and_kind():
    c = clf()
    r = c.classify("Chess Openings for Beginners: 5 Mistakes to Avoid")
    assert r["level"] == "b" and r["kind"] == "tips"
    assert c.classify("Mastering the Najdorf | 2200 ELO")["level"] == "x"
    assert classify.infer_kind("Magnus Carlsen documentary", "legends") == "talk"
    assert classify.infer_kind("Round 5 highlights", "news") == "recap"
    assert classify.infer_kind("Full Course: Endgames Part 3", "endgames") == "course"
    assert classify.infer_kind("Blitz with commentary", "gameplay") == "gameplay"


def test_practice_routes_reference_existing_lessons():
    sections, _ = build_taxonomy.build()
    lessons = {p.stem for p in (CUB.parents[1] / "data" / "lessons").glob("*.json")}
    for s in sections:
        for x in s["nodes"]:
            if x["practice"].startswith("#/learn?l="):
                assert x["practice"].split("=", 1)[1] in lessons


# ---------- validator ----------
def test_validator_flags_problems():
    tax = {"sections": [{"id": "s1", "floor": 2, "nodes": [{"id": "n1"}, {"id": "n2"}]}]}
    v = {"i": "a" * 11, "t": "t", "c": "c", "h": None, "n": "n1", "s": "s1", "l": "b", "k": "lesson", "sc": 1, "f": 1, "o": 0,
         "sr": 0, "src": [], "tr": 0, "d": None, "p": None}
    errs, notes = validate_cubicle.validate([v, dict(v)], tax, {"a" * 11})
    text = " | ".join(errs)
    assert "duplicate" in text and "< 500" in text and "empty nodes" in text and "since 2021" in text
    errs2, _ = validate_cubicle.validate([dict(v, i="b" * 11, thumb="x")], tax, {"a" * 11})
    assert any("oEmbed" in e for e in errs2) and any("unexpected keys" in e for e in errs2)
