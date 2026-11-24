import pytest

from bobby import api


def test_puzzles_from_blunder(game):
    pz = api.puzzles_from_mistakes(game)
    assert len(pz) == 1
    p = pz[0]
    assert p["solution"] == ["g7g6"] and p["source"] == "mistake" and p["fen"] == game["moves"][5]["fen_before"]
    assert "mate_threat" in p["themes"] and isinstance(p["rating"], int)
    assert p["id"] == api.puzzles_from_mistakes(game)[0]["id"]  # deterministic


def test_puzzle_requires_best_and_uses_pv(game):
    game["moves"][5]["best_uci"] = None
    assert api.puzzles_from_mistakes(game) == []
    game["moves"][5]["best_uci"] = "g7g6"
    game["moves"][5]["best_pv"] = ["g7g6", "h5f3", "g8f6", "x"]
    assert api.puzzles_from_mistakes(game)[0]["solution"] == ["g7g6", "h5f3", "g8f6"]


def test_select_puzzles():
    ps = [{"id": str(r), "rating": r, "themes": ["fork" if r % 200 else "pin"]} for r in range(600, 2000, 100)]
    sel = api.select_puzzles(ps, {"rating": 1000}, None, 3)
    assert [p["rating"] for p in sel][0] in (1000, 1100) and len(sel) == 3
    assert all("pin" in p["themes"] for p in api.select_puzzles(ps, {"rating": 1000}, "pin", 10))


def test_srs_ladder():
    c = api.srs_new_card("p1", "2026-11-01")
    assert c["due"] == "2026-11-01"
    gaps = []
    for _ in range(4):
        c = api.srs_review(c, 2, c["due"])
        gaps.append(c["interval"])
    assert gaps == [1, 3, 7, 30]
    c = api.srs_review(c, 0, c["due"])
    assert c["interval"] == 1 and c["lapses"] == 1 and c["ease"] < 2.5
    with pytest.raises(ValueError):
        api.srs_review(c, 4, "2026-11-01")


def test_srs_ease_effects():
    base = api.srs_review(api.srs_review(api.srs_new_card("x", "2026-11-01"), 2, "2026-11-01"), 2, "2026-11-02")
    easy = api.srs_review(api.srs_review(api.srs_new_card("x", "2026-11-01"), 3, "2026-11-01"), 3, "2026-11-02")
    hard = api.srs_review(api.srs_review(api.srs_new_card("x", "2026-11-01"), 1, "2026-11-01"), 1, "2026-11-02")
    assert hard["interval"] < base["interval"] < easy["interval"]


def test_due_cards():
    cards = [api.srs_new_card("a", "2026-11-05"), api.srs_new_card("b", "2026-11-01"), api.srs_new_card("c", "2026-12-01")]
    assert [c["id"] for c in api.due_cards(cards, "2026-11-10")] == ["b", "a"]


def test_daily_plan(game):
    w = api.update_weakness(None, game)
    p = api.new_profile("moves", None, "2026-11-01")
    plan = api.daily_plan(p, w, [api.srs_new_card("a", "2026-11-01")], "2026-11-02")
    kinds = [i["kind"] for i in plan["items"]]
    assert kinds[0] == "review" and "play" in kinds and plan["minutes"] > 0
    assert api.daily_plan(p, None, [], "2026-11-02")["items"]


def test_challenges(game):
    w = api.update_weakness(None, game)
    ch = api.generate_challenges(w, {"rating": 800}, "2026-11-20")
    assert 3 <= len(ch) <= 5 and all(c["progress"] == 0 for c in ch)
    assert len({c["id"] for c in ch}) == len(ch)
    after = {c["kind"]: c for c in api.update_challenges(ch, game)}
    assert after["no_blunders"]["progress"] == 0 and not after["no_blunders"]["done"]
    assert after["play_games"]["progress"] == 1
    if "avoid_tag" in after:
        assert after["avoid_tag"]["progress"] == 0


def test_use_motif_challenge():
    fen = "r3k3/8/8/3N4/8/8/8/4K3 w - - 0 1"
    g = {"player_color": "w", "moves": [{"ply": 1, "uci": "d5c7", "fen_before": fen, "eval_before": {"cp": 500},
                                         "eval_after": {"cp": 500}, "best_uci": "d5c7", "best_eval": {"cp": 500}}]}
    ch = [{"id": "x", "kind": "use_motif", "tag": "fork", "target": 1, "progress": 0, "done": False}]
    assert api.update_challenges(ch, g)[0]["done"]


def test_achievements():
    p = api.new_profile("basic", None, "2026-11-01")
    new = api.check_achievements(p, {"games": 1, "wins": 1, "streak": 3}, [])
    ids = {a["id"] for a in new}
    assert {"first_game", "first_win", "streak_3", "rating_800"} <= ids
    assert api.check_achievements(p, {"games": 1, "wins": 1, "streak": 3}, list(ids)) == []


LESSON = {"id": "l1", "title": "Forks", "section": "tactics", "order": 1, "steps": [
    {"type": "info", "fen": None, "prompt": "Read", "correct": [], "options": None, "explanation": "Ok", "hint": None},
    {"type": "move", "fen": "r3k3/8/8/3N4/8/8/8/4K3 w - - 0 1", "prompt": "Fork", "correct": ["d5c7"],
     "options": None, "explanation": "Knight fork.", "hint": "Check the king."},
    {"type": "square", "fen": None, "prompt": "Where?", "correct": ["c7"], "options": None, "explanation": "Yes", "hint": None},
    {"type": "quiz", "fen": None, "prompt": "Q?", "correct": ["Knight"], "options": ["Bishop", "Knight"],
     "explanation": "Right", "hint": "Jumps"},
]}


def test_lesson_check():
    assert api.lesson_check(LESSON, 0, None) == {"correct": True, "feedback": "Ok", "next_index": 1}
    assert api.lesson_check(LESSON, 1, "d5c7")["correct"]
    assert api.lesson_check(LESSON, 1, "Nc7+")["correct"]  # SAN accepted
    wrong = api.lesson_check(LESSON, 1, "d5b4")
    assert not wrong["correct"] and wrong["next_index"] == 1 and "Check the king" in wrong["feedback"]
    assert api.lesson_check(LESSON, 2, "C7")["correct"]
    assert api.lesson_check(LESSON, 3, 1) == {"correct": True, "feedback": "Right", "next_index": None}
    assert not api.lesson_check(LESSON, 3, "Bishop")["correct"]
    with pytest.raises(ValueError):
        api.lesson_check(LESSON, 9, "x")
