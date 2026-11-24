import json

import chess

from bobby import api

CONTRACT = ["new_game", "apply_move", "legal_moves", "parse_pgn", "to_pgn", "classify_moves", "winprob",
            "new_profile", "update_rating", "bot_target_rating", "update_weakness", "benchmarks_compare",
            "puzzles_from_mistakes", "select_puzzles", "srs_new_card", "srs_review", "due_cards", "daily_plan",
            "generate_challenges", "update_challenges", "check_achievements", "lesson_check", "stats_summary",
            "export_all", "import_all", "explain_move", "explain_position", "template_explanation"]


def test_all_contract_functions_exist():
    for name in CONTRACT:
        assert callable(getattr(api, name)), name
        assert name in api.__all__


def _rt(x):
    """JSON round-trip of output, and of the inputs through JSON first."""
    s = json.dumps(x)
    assert json.loads(s) == x
    return x


def test_json_roundtrip_everything(game):
    g = json.loads(json.dumps(game))
    _rt(api.new_game())
    _rt(api.apply_move(chess.STARTING_FEN, "e2e4"))
    _rt(api.legal_moves(chess.STARTING_FEN))
    parsed = _rt(api.parse_pgn(api.to_pgn({"White": "a"}, ["e2e4"])))
    _rt(api.to_pgn(parsed["headers"], parsed["moves"]))
    cls = _rt(api.classify_moves(g["moves"], "b"))
    _rt(api.winprob(10, None))
    p = _rt(api.new_profile("basic", None, "2026-11-01"))
    p = _rt(api.update_rating(p, {"score": 0.5, "opp_rating": 800, "opp_rd": 100, "date": "2026-11-02"}))
    _rt(api.bot_target_rating(p, 50))
    w = _rt(api.update_weakness(None, {**g, "classification": cls}))
    _rt(api.benchmarks_compare(p, {"blunder_rate": 0.1}, {"800-1000": {"blunder_rate": 0.05}}))
    pz = _rt(api.puzzles_from_mistakes(g))
    _rt(api.select_puzzles(pz, p, None, 5))
    c = _rt(api.srs_new_card(pz[0]["id"], "2026-11-02"))
    c = _rt(api.srs_review(c, 2, "2026-11-02"))
    _rt(api.due_cards([c], "2026-11-30"))
    _rt(api.daily_plan(p, w, [c], "2026-11-03"))
    ch = _rt(api.generate_challenges(w, p, "2026-11-03"))
    _rt(api.update_challenges(ch, g))
    _rt(api.check_achievements(p, {"games": 1}, []))
    _rt(api.lesson_check({"steps": [{"type": "info"}]}, 0, None))
    _rt(api.stats_summary([{"id": "g1", "date": "2026-11-20", "result": "1-0", "player_color": "b"}],
                          [{"game_id": "g1", "moves": g["moves"]}]))
    _rt(api.import_all(api.export_all({"games": []})))
    _rt(api.explain_move({**g["moves"][0], "class": "best"}, []))
    _rt(api.explain_position(chess.STARTING_FEN, "plan", [{"pv": ["e2e4"], "cp": 30, "mate": None}]))
    _rt(api.template_explanation({"move": "e4", "class": "best"}, "move_explain"))
    _rt(api.position_difficulty(chess.STARTING_FEN, [{"pv": ["e2e4"], "cp": 30, "mate": None}], 1000))
