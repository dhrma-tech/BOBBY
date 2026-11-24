import chess

from bobby import tactics
from bobby.phase import endgame_type, phase


def _mv(fen, uci):
    return chess.Board(fen), chess.Move.from_uci(uci)


def test_fork():
    assert tactics.is_fork(*_mv("r3k3/8/8/3N4/8/8/8/4K3 w - - 0 1", "d5c7"))
    assert not tactics.is_fork(*_mv("r3k3/8/8/3N4/8/8/8/4K3 w - - 0 1", "d5b4"))


def test_pin_and_skewer():
    assert "pin" in tactics.line_motifs(*_mv("4k3/3n4/8/8/8/8/8/4KB2 w - - 0 1", "f1b5"))
    assert "skewer" in tactics.line_motifs(*_mv("8/8/8/4k2q/8/8/8/R3K3 w - - 0 1", "a1a5"))


def test_discovered_check():
    assert tactics.is_discovered(*_mv("4k3/8/8/8/4N3/8/8/4R1K1 w - - 0 1", "e4c5"))


def test_back_rank():
    b, m = _mv("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", "a1a8")
    assert tactics.is_back_rank_mate(b, m)
    assert "back_rank" in tactics.move_motifs(b, m)
    allowed = tactics.allowed_motifs(chess.Board("r5k1/8/8/8/8/8/5PPP/6K1 b - - 0 1"))
    assert {"mate_threat", "back_rank"} <= allowed


def test_hanging_piece():
    loose = chess.Board("4k3/8/8/3n4/8/8/8/3QK3 w - - 0 1")
    assert chess.D5 in tactics.hanging_pieces(loose, chess.BLACK)
    guarded = chess.Board("4k3/8/2p5/3n4/8/8/8/3QK3 w - - 0 1")
    assert chess.D5 not in tactics.hanging_pieces(guarded, chess.BLACK)
    cheaper = chess.Board("4k3/8/2p5/3n4/4P3/8/8/4K3 w - - 0 1")  # pawn attacks defended knight
    assert chess.D5 in tactics.hanging_pieces(cheaper, chess.BLACK)


def test_phase():
    assert phase(chess.STARTING_FEN, 1) == "opening"
    assert phase("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1") == "end"
    assert endgame_type("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1") == "endgame_k_p"
    assert endgame_type("4k3/r7/8/8/8/8/4P3/4K2R w - - 0 1") == "endgame_rook"
    assert endgame_type(chess.STARTING_FEN) is None
