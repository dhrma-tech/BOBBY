import chess
import pytest

from bobby import api
from conftest import BLUNDER_PGN


def test_new_game_start():
    s = api.new_game()
    assert s["turn"] == "w" and len(s["legal_moves"]) == 20 and not s["over"] and s["result"] == "*"


def test_apply_move_and_illegal():
    s = api.apply_move(chess.STARTING_FEN, "e2e4")
    assert s["san"] == "e4" and s["turn"] == "b"
    with pytest.raises(ValueError):
        api.apply_move(chess.STARTING_FEN, "e2e5")
    with pytest.raises(ValueError):
        api.apply_move(chess.STARTING_FEN, "zz")
    with pytest.raises(ValueError):
        api.new_game("not a fen")


def test_mate_and_stalemate_state():
    s = api.apply_move("r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4", "h5f7")
    assert s["over"] and s["result"] == "1-0" and s["reason"] == "checkmate" and s["check"]
    st = api.new_game("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert st["over"] and st["result"] == "1/2-1/2" and st["reason"] == "stalemate"


def test_promotion_legal():
    assert "a7a8q" in api.legal_moves("8/P7/8/8/8/8/8/k6K w - - 0 1")


def test_pgn_roundtrip():
    p = api.parse_pgn(BLUNDER_PGN)
    assert p["result"] == "1-0" and len(p["moves"]) == 7 and p["moves"][-1]["san"] == "Qxf7#"
    out = api.to_pgn(p["headers"], p["moves"])
    again = api.parse_pgn(out)
    assert [m["uci"] for m in again["moves"]] == [m["uci"] for m in p["moves"]]
    assert api.to_pgn({}, ["e2e4", "e7e5"]).strip().endswith("1. e4 e5 *")


def test_pgn_errors():
    with pytest.raises(ValueError):
        api.parse_pgn("")
    with pytest.raises(ValueError):
        api.parse_pgn("1. e4 e4 *")
    with pytest.raises(ValueError):
        api.to_pgn({}, ["e2e5"])
