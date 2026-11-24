import pytest

from bobby import api, classify
from bobby.accuracy import move_accuracy


def test_winprob():
    assert api.winprob(0, None) == 0.5
    assert api.winprob(None, 3) == 1.0 and api.winprob(None, -2) == 0.0
    assert api.winprob(300, None) > 0.7 and api.winprob(-300, None) < 0.3
    assert api.winprob(5000, None) == api.winprob(1000, None)
    assert abs(api.winprob(200, None) + api.winprob(-200, None) - 1) < 1e-9


def _m(ply, before, after, best=None, uci="a", best_uci="b"):
    return {"ply": ply, "uci": uci, "eval_before": {"cp": before}, "eval_after": {"cp": after},
            "best_uci": best_uci, "best_eval": {"cp": before if best is None else best}}


@pytest.mark.parametrize("after,label", [(0, "best"), (-30, "good"), (-70, "inaccuracy"),
                                         (-130, "mistake"), (-300, "blunder")])
def test_thresholds(after, label):
    r = api.classify_moves([_m(1, 0, after)], "w")
    assert r["moves"][0]["class"] == label


def test_black_perspective_and_best():
    # Black move: eval going up for White is bad for Black.
    r = api.classify_moves([_m(1, 0, 0), _m(2, 0, 300)], "b")
    assert r["moves"][1]["class"] == "blunder" and r["moves"][1]["is_player"]
    assert not r["moves"][0]["is_player"]
    r = api.classify_moves([_m(1, 0, -10, uci="e2e4", best_uci="e2e4")], "w")
    assert r["moves"][0]["class"] == "best"


def test_configurable_thresholds():
    assert classify.label(0.06) == "inaccuracy"
    assert classify.label(0.06, thresholds={"inaccuracy": 0.08}) == "good"


def test_blunder_game(game):
    r = api.classify_moves(game["moves"], "b")
    nf6 = r["moves"][5]
    assert nf6["class"] == "blunder" and nf6["is_player"] and nf6["winprob_loss"] > 0.4
    assert 6 in r["key_moments"]
    assert r["acpl"]["b"] > r["acpl"]["w"]
    assert r["accuracy"]["w"] > r["accuracy"]["b"]
    assert 0 <= r["accuracy"]["b"] <= 100
    assert r["moves"][6]["class"] == "best"  # Qxf7# delivered mate


def test_move_accuracy_bounds():
    assert move_accuracy(0.5, 0.5) == 100.0
    assert move_accuracy(1.0, 0.0) == 0.0
    assert 0 < move_accuracy(0.6, 0.5) < 100


def test_empty_game():
    r = api.classify_moves([], "w")
    assert r["moves"] == [] and r["accuracy"] == {"w": 0.0, "b": 0.0}
