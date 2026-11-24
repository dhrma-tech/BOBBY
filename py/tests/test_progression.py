from bobby import api
from bobby.challenges import update_challenges

from conftest import analyzed

PROFILE = {"rating": 800.0, "rd": 200.0, "level": "moves"}


def _lost_games(n):
    # The fixture game: Black (the player) blunders and gets mated.
    return [{**analyzed(), "id": f"g{i}", "date": f"2026-11-{10 + i:02d}"} for i in range(n)]


def _won_games(n):
    # Same game seen from White's side: the player wins.
    return [{**analyzed(color="w"), "id": f"w{i}", "date": f"2026-11-{10 + i:02d}"} for i in range(n)]


def test_recent_form_empty_and_basic():
    assert api.progress_report([], None)["recent_games"] == 0
    rep = api.progress_report(_lost_games(3), None)
    f = rep["form"]
    assert f["games"] == 3 and f["losses"] == 3 and f["blunders_per_game"] >= 1
    assert f["weakest_phase"] in ("opening", "middlegame", "endgame")


def test_progression_once_per_day_and_defaults():
    p = api.daily_progression(PROFILE, [], None, None, "2026-11-24")
    assert p["offset"] == 0 and p["accuracy_target"] == 70 and p["date"] == "2026-11-24"
    assert api.daily_progression(PROFILE, _won_games(5), p, None, "2026-11-24") is p  # same day: unchanged


def test_progression_steps_up_after_goals_met_and_down_after_losing_run():
    prev = {"date": "2026-11-23", "offset": 0, "tier": 1}
    done = [{"done": True}, {"done": True}, {"done": False}]
    up = api.daily_progression(PROFILE, _won_games(4), prev, done, "2026-11-24")
    assert up["step"] == 50 and up["offset"] == 50 and up["tier"] == 2
    down = api.daily_progression(PROFILE, _lost_games(4), prev, [{"done": False}], "2026-11-24")
    assert down["step"] == -50 and down["offset"] == -50
    capped = api.daily_progression(PROFILE, _won_games(4), {"date": "x", "offset": 400}, done, "2026-11-24")
    assert capped["offset"] == 400 and capped["step"] == 0


def test_challenges_follow_progression():
    prog = {"accuracy_target": 75, "blunder_cap": 2, "step": 50, "offset": 50, "base_rating": 800}
    ch = api.generate_challenges(None, PROFILE, "2026-11-24", prog)
    kinds = {c["kind"]: c for c in ch}
    assert kinds["accuracy"]["target"] == 75
    assert kinds["max_blunders"]["target"] == 2
    assert "850" in kinds["win_game"]["title"]
    # old call shape still works
    assert api.generate_challenges(None, PROFILE, "2026-11-24")


def test_new_challenge_kinds_progress():
    prog = {"blunder_cap": 1, "step": 50, "offset": 50, "base_rating": 800}
    ch = [c for c in api.generate_challenges(None, PROFILE, "2026-11-24", prog) if c["kind"] in ("max_blunders", "win_game")]
    lost = update_challenges(ch, analyzed())          # player is Black, loses, 1 blunder
    by = {c["kind"]: c for c in lost}
    assert by["max_blunders"]["done"] and not by["win_game"]["done"]
    won = update_challenges(ch, analyzed(color="w"))
    assert {c["kind"]: c for c in won}["win_game"]["done"]


def test_progress_template_plain_words():
    prog = api.daily_progression(PROFILE, _lost_games(3), None, None, "2026-11-24")
    facts = api.progress_report(_lost_games(3), None, prog)
    t = api.template_explanation(facts, "progress")
    assert "Last 3 games" in t and "Habit to build" in t and "Today Bobby plays at about" in t
