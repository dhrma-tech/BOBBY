import pytest

from bobby import api, glicko


def test_glicko_published_example():
    r, rd, vol = glicko.update(1500, 200, 0.06, [(1400, 30, 1), (1550, 100, 0), (1700, 300, 0)], tau=0.5)
    assert abs(r - 1464.06) < 0.05
    assert abs(rd - 151.52) < 0.05
    assert abs(vol - 0.05999) < 1e-4


def test_glicko_no_games_inflates():
    _, rd, _ = glicko.update(1500, 200, 0.06, [])
    assert rd > 200


@pytest.mark.parametrize("level,seed", [("never", 400), ("moves", 600), ("basic", 800), ("casual", 1000), ("club", 1400)])
def test_seeds(level, seed):
    p = api.new_profile(level, None, "2026-11-01")
    assert p["rating"] == seed and p["rd"] >= 300


def test_known_rating_and_bad_level():
    assert api.new_profile("never", 1700, "2026-11-01")["rating"] == 1700
    with pytest.raises(ValueError):
        api.new_profile("expert", None, "2026-11-01")


def test_fast_calibration():
    p = api.new_profile("moves", None, "2026-11-01")
    for d in range(1, 6):
        p = api.update_rating(p, {"score": 1, "opp_rating": 900, "opp_rd": 60, "date": f"2026-11-0{d}"})
    assert p["rating"] > 900 and p["rd"] < 200 and p["games"] == 5 and p["wins"] == 5
    assert len(p["history"]) == 6
    with pytest.raises(ValueError):
        api.update_rating(p, {"score": 2, "opp_rating": 900, "opp_rd": 60})


def test_bot_target():
    p = api.new_profile("never", None, "2026-11-01")
    assert api.bot_target_rating(p, 100) == 500
    assert api.bot_target_rating(p, -200) == 400
    assert api.bot_target_rating({"rating": 2550}, 200) == 2600


def test_weakness_from_blunder(game):
    w = api.update_weakness(None, game)
    assert w["games"] == 1
    assert "mate_threat" in w["tags"] and w["tags"]["mate_threat"]["last_seen"] == "2026-11-20"
    assert "opening_C20" in w["tags"]
    w2 = api.update_weakness(w, game)
    assert w2["tags"]["mate_threat"]["count"] == 2
    assert w2["tags"]["mate_threat"]["score"] < 2 * w["tags"]["mate_threat"]["score"]


def test_missed_mate_tag():
    fen = "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"
    g = {"player_color": "w", "moves": [{"ply": 1, "uci": "a1a2", "fen_before": fen, "eval_before": {"mate": 1},
                                         "eval_after": {"cp": 400}, "best_uci": "a1a8", "best_eval": {"mate": 1}}]}
    w = api.update_weakness(None, g)
    assert {"missed_mate", "back_rank"} <= set(w["tags"])


def test_time_trouble_tag():
    fen = "4k3/8/8/3n4/8/8/8/3QK3 b - - 0 1"
    g = {"player_color": "b", "moves": [{"ply": 1, "uci": "e8e7", "fen_before": fen, "eval_before": {"cp": 0},
                                         "eval_after": {"cp": 300}, "best_uci": "d5f6", "best_eval": {"cp": 0},
                                         "clock": 12}]}
    tags = api.update_weakness(None, g)["tags"]
    assert {"time_trouble", "hanging_piece"} <= set(tags)


def test_benchmarks():
    bm = {"800-1000": {"acpl": {"opening": 40, "middle": 80, "end": 90}, "blunder_rate": 0.05,
                       "mistake_rate": 0.08, "inaccuracy_rate": 0.1, "common_themes_missed": ["fork"]}}
    out = api.benchmarks_compare({"rating": 850}, {"acpl": {"opening": 30, "middle": 80, "end": 150},
                                                   "blunder_rate": 0.05, "themes_missed": ["fork"]}, bm)
    notes = {o["metric"]: o["note"] for o in out}
    assert "better" in notes["acpl.opening"] and "typical" in notes["acpl.middle"] and "worse" in notes["acpl.end"]
    assert "theme.fork" in notes
    assert api.benchmarks_compare({"rating": 850}, {}, {}) == []


def test_difficulty():
    fen = "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"
    hard = api.position_difficulty(fen, [{"pv": ["a1a8"], "cp": None, "mate": 1}, {"pv": ["a1a2"], "cp": 0, "mate": None}], 600)
    easy = api.position_difficulty(fen, [{"pv": ["a1a8"], "cp": 50, "mate": None}, {"pv": ["a1a2"], "cp": 45, "mate": None}], 600)
    assert hard["score"] > easy["score"] and hard["hard_for_level"]
