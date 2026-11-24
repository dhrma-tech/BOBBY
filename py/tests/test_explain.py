import chess
import pytest

from bobby import api

from conftest import analyzed

# After 3.Qh5 (Scholar's mate try), Black to move: Qxf7# is threatened.
SCHOLAR = "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3"


def test_explain_blunder_says_what_it_allowed_and_what_was_better():
    m = analyzed()["moves"][5]  # 3...Nf6?? by Black (the player)
    r = api.explain_move({**m, "class": "blunder"}, ["h5f7"])
    t = r["text"]
    assert "blunder" in t and "checkmate you with Qxf7#" in t
    assert "Better was g6" in t and "stops their checkmate threat" in t
    kinds = [a[2] for a in r["viz"]["arrows"]]
    assert kinds == ["played", "threat", "best"]
    assert r["viz"]["line"]["fen"] == m["fen_before"] and r["viz"]["line"]["moves"][0] == "g7g6"
    assert "mate_threat" in r["tags"]


def test_explain_good_move_and_mate():
    m = analyzed(color="w")["moves"][6]  # 4.Qxf7#
    assert api.explain_move({**m, "class": "best"}, [])["text"].startswith("Checkmate!")
    first = analyzed(color="w")["moves"][0]
    t = api.explain_move({**first, "class": "best"}, [])["text"]
    assert t.startswith("Great move!") and "pawn to e4" in t


@pytest.mark.parametrize("q", ["threats", "danger", "best", "better", "plan"])
def test_every_question_answers(q):
    r = api.explain_position(SCHOLAR, q, [{"pv": ["g7g6", "h5f3"], "cp": -10, "mate": None}])
    assert r["text"] and set(r["viz"]) == {"arrows", "squares", "line"}


def test_threats_and_best_are_specific():
    t = api.explain_position(SCHOLAR, "threats", [])
    assert "checkmate with Qxf7#" in t["text"] and t["viz"]["arrows"][0][:2] == ["h5", "f7"]
    b = api.explain_position(SCHOLAR, "best", [{"pv": ["g7g6"], "cp": -10, "mate": None}])
    assert "Best move: g6" in b["text"] and "stops their checkmate threat" in b["text"]
    assert b["viz"]["line"]["moves"] == ["g7g6"]


def test_danger_and_saving_a_piece():
    # White queen on d4 attacked by the e5 pawn.
    fen = "rnbqkbnr/pppp1ppp/8/4p3/3Q4/8/PPP1PPPP/RNB1KBNR w KQkq - 0 3"
    d = api.explain_position(fen, "danger", [])
    assert "queen on d4 is in danger" in d["text"] and d["viz"]["squares"]["d4"] == "danger"
    b = api.explain_position(fen, "best", [{"pv": ["d4e3"], "cp": 30, "mate": None}])
    assert "saves your queen on d4" in b["text"]


def test_bad_question():
    with pytest.raises(ValueError):
        api.explain_position(chess.STARTING_FEN, "poem", [])
