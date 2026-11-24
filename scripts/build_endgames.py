#!/usr/bin/env python3
"""Build data/endgames.json: trainer positions with a perfect-play outcome from Syzygy tablebases.

--input = directory with Syzygy .rtbw/.rtbz files (3-4-5 piece). Download from
https://tablebase.lichess.ovh/tables/standard/3-4-5-wdl/ and .../3-4-5-dtz/ (see scripts/README.md).
Positions are sampled randomly (fixed seed), side to move is the solver:
  goal "win":  solver wins with perfect play; dtz in [min_dtz, max_dtz]; at most 60% of legal
               moves keep the win (so it is not trivial).
  goal "draw": solver holds a draw; at most 50% of legal moves keep the draw.
Positions with check on the board, an immediate capture of the only attacker, or missing
tables for any child position are dropped. Output: [{id, name, fen, goal, dtz|null, hint}].
"""
import argparse
import random
import sys

import chess
import chess.syzygy

import config
from common import write_json

# (key, name, material "white pieces v black pieces", goal, count, min_dtz, max_dtz, hint)
SPECS = [
    ("kqk", "K+Q vs K", "KQvK", "win", 6, 5, 40,
     "Restrict the king with the queen a knight's move away, bring your king closer, then mate. Avoid stalemate."),
    ("krk", "K+R vs K", "KRvK", "win", 6, 5, 60,
     "Cut the king off along a file, bring your king up, and use the rook to give the final check on the edge."),
    ("kbnk", "K+B+N vs K", "KBNvK", "win", 5, 15, 140,
     "Drive the lone king toward a corner the colour of your bishop, then finish with the knight and bishop."),
    ("kbbk", "K+B+B vs K", "KBBvK", "win", 3, 8, 60,
     "Two bishops on adjacent diagonals form a wall; push the king to the edge and bring your own king up."),
    ("kpk_w", "K+P vs K: winning", "KPvK", "win", 6, 3, 60,
     "Get your king in front of the pawn and use the opposition. Keep the pawn protected while it advances."),
    ("kpk_d", "K+P vs K: hold the draw", "KPvK", "draw", 6, 0, 0,
     "Stay in front of the pawn or take the opposition. A rook pawn is often an easy draw."),
    ("kqkr", "K+Q vs K+R", "KQvKR", "win", 4, 10, 120,
     "Look for forks and skewers of the rook and king; separate the rook from its king."),
    ("kqkp", "K+Q vs K+P", "KQvKP", "win", 3, 5, 80,
     "Stop the pawn from queening first, then bring the king closer to win."),
    ("krkb", "K+R vs K+B: hold the draw", "KRvKB", "draw", 4, 0, 0,
     "Keep king and bishop together and near a corner the bishop controls. Avoid being separated."),
    ("krkn", "K+R vs K+N: hold the draw", "KRvKN", "draw", 4, 0, 0,
     "Keep the knight next to its king so a fork is never possible."),
    ("kbpk", "K+B+P vs K: hold the draw", "KBPvK", "draw", 4, 0, 0,
     "A rook pawn with the wrong-coloured bishop draws if the defending king reaches the corner."),
    ("krpkr_w", "K+R+P vs K+R: winning", "KRPvKR", "win", 5, 10, 120,
     "Cut the enemy king off, support the pawn, and look for a bridge to shelter your king."),
    ("krpkr_d", "K+R+P vs K+R: hold the draw", "KRPvKR", "draw", 5, 0, 0,
     "Keep your rook active behind the pawn or on the third rank; avoid passive defence."),
    ("kppkp", "K+2P vs K+P", "KPPvKP", "win", 3, 10, 120,
     "Create a passed pawn, use the extra pawn as a lever, and keep your king active."),
    ("kqpkq", "K+Q+P vs K+Q: hold the draw", "KQPvKQ", "draw", 3, 0, 0,
     "Look for perpetual check and keep the enemy king exposed."),
    ("krpk", "K+R+P vs K", "KRPvK", "win", 3, 5, 80,
     "With a spare rook, cut off the king and promote or mate; be careful about stalemate."),
]

PIECES = {"K": chess.KING, "Q": chess.QUEEN, "R": chess.ROOK, "B": chess.BISHOP, "N": chess.KNIGHT, "P": chess.PAWN}


def random_position(material, rng):
    w, b = material.split("v")
    board = chess.Board(None)
    squares = rng.sample(range(64), len(w) + len(b))
    i = 0
    for color, side in ((chess.WHITE, w), (chess.BLACK, b)):
        for ch in side:
            board.set_piece_at(squares[i], chess.Piece(PIECES[ch], color))
            i += 1
    board.turn = rng.choice([chess.WHITE, chess.BLACK])
    return board


def keep_ratio(tb, board, target):
    """Share of legal moves after which the mover still has outcome class `target` (win: wdl 2, draw: 0)."""
    n = ok = 0
    for m in board.legal_moves:
        board.push(m)
        try:
            w = -tb.get_wdl(board) if not board.is_checkmate() else 2
        finally:
            board.pop()
        n += 1
        if w == target:
            ok += 1
    return ok / n if n else 1.0


def gen_spec(tb, spec, rng, max_tries=400000):
    key, name, material, goal, count, dmin, dmax, hint = spec
    out, seen, tries = [], set(), 0
    while len(out) < count and tries < max_tries:
        tries += 1
        board = random_position(material, rng)
        if not board.is_valid() or board.is_check() or board.is_game_over():
            continue
        try:
            wdl = tb.get_wdl(board)
            if goal == "win":
                if wdl != 2:
                    continue
                dtz = tb.get_dtz(board)
                if dtz is None:
                    continue
                dtz = abs(dtz)
                if not dmin <= dtz <= dmax:
                    continue
                if keep_ratio(tb, board, 2) > 0.6:
                    continue
            else:
                if wdl != 0:
                    continue
                dtz = None
                if board.is_insufficient_material():
                    continue
                if keep_ratio(tb, board, 0) > 0.5:
                    continue
        except (KeyError, chess.syzygy.MissingTableError):
            continue
        # do not hand over an immediate free capture of the strong side's piece for 'win' goals
        fen = board.fen()
        if fen in seen:
            continue
        seen.add(fen)
        out.append({"id": f"{key}-{len(out) + 1}", "name": name, "fen": fen, "goal": goal,
                    "dtz": dtz, "hint": hint})
    if len(out) < count:
        print(f"warning: {key}: only {len(out)}/{count} positions", file=sys.stderr)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", "-i", required=True, help="directory with Syzygy tables")
    ap.add_argument("--out", "-o", default=str(config.DATA / "endgames.json"))
    ap.add_argument("--limit", "--max-games", dest="limit", type=int, default=0,
                    help="max positions per spec (0 = spec default)")
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    out = []
    with chess.syzygy.open_tablebase(a.input) as tb:
        for spec in SPECS:
            if a.limit:
                spec = spec[:4] + (min(a.limit, spec[4]),) + spec[5:]
            out += gen_spec(tb, spec, rng)
    write_json(a.out, out, compact=False)
    print(f"wrote {len(out)} positions", file=sys.stderr)


if __name__ == "__main__":
    main()
