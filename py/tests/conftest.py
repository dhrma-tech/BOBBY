import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bobby import api  # noqa: E402

# Scholar's-mate trap: Black blunders with 3...Nf6?? allowing 4.Qxf7#.
BLUNDER_PGN = """[Event "Test"]
[White "Bobby"]
[Black "Player"]
[ECO "C20"]
[Result "1-0"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0
"""

# White-perspective evals after each ply, plus engine best move/eval for each position.
EVALS = [
    ({"cp": 20}, {"cp": 35}, "e2e4", {"cp": 35}),
    ({"cp": 35}, {"cp": 30}, "e7e5", {"cp": 30}),
    ({"cp": 30}, {"cp": 20}, "g1f3", {"cp": 30}),
    ({"cp": 20}, {"cp": 25}, "g8f6", {"cp": 15}),
    ({"cp": 25}, {"cp": -20}, "g1f3", {"cp": 25}),
    ({"cp": -20}, {"mate": 1}, "g7g6", {"cp": -10}),
    ({"mate": 1}, {"mate": 0}, "h5f7", {"mate": 1}),
]


def analyzed(pgn: str = BLUNDER_PGN, color: str = "b") -> dict:
    parsed = api.parse_pgn(pgn)
    moves = []
    for i, (m, (eb, ea, best, be)) in enumerate(zip(parsed["moves"], EVALS)):
        moves.append({"ply": i + 1, "uci": m["uci"], "san": m["san"], "fen_before": m["fen_before"],
                      "fen_after": m["fen_after"], "eval_before": eb, "eval_after": ea, "best_uci": best,
                      "best_eval": be})
    return {"id": "g1", "date": "2026-11-20", "player_color": color, "moves": moves,
            "headers": parsed["headers"], "result": parsed["result"], "player_rating": 800}


@pytest.fixture
def game():
    return analyzed()
