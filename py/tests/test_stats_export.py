import pytest

from bobby import api


def test_stats_summary(game):
    games = [{"id": "g1", "date": "2026-11-20", "result": "1-0", "player_color": "b", "rating_after": 780,
              "opening": {"eco": "C20", "name": "King's Pawn"}},
             {"id": "g2", "date": "2026-11-21", "result": "1/2-1/2", "player_color": "w", "rating_after": 790,
              "headers": {"ECO": "C20"}}]
    s = api.stats_summary(games, [{"game_id": "g1", "moves": game["moves"]}])
    assert [p["rating"] for p in s["rating_curve"]] == [780, 790]
    assert s["opening_results"][0] == {"eco": "C20", "name": "King's Pawn", "n": 2, "w": 0, "d": 1, "l": 1, "score": 0.25}
    assert s["blunders_per_game"][0]["blunders"] == 1
    assert s["accuracy_trend"][0]["game_id"] == "g1"
    assert s["phase_breakdown"]["opening"]["errors"] == 1
    assert s["weakness_heatmap"]["mate_threat"]["opening"] == 1
    assert api.stats_summary([], [])["rating_curve"] == []


def test_export_import():
    data = {"profile": api.new_profile("moves", None, "2026-11-01"), "games": [], "settings": {"persona": "closer"}}
    blob = api.export_all(data)
    assert blob["version"] == 1 and api.import_all(blob) == data
    for bad in [None, {}, {"version": 99, "data": {}}, {"version": 1, "data": {"games": {}}},
                {"version": 1, "data": {"nope": []}}, {"version": "1", "data": {}}]:
        with pytest.raises(ValueError):
            api.import_all(bad)
