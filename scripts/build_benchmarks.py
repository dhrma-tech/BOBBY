#!/usr/bin/env python3
"""Build data/benchmarks.json from a Lichess monthly rated-standard PGN dump (.pgn.zst).

Only games carrying [%eval] on every move are used (Lichess computer analysis). Per rating band
(mean of both players), for every move: loss = drop in the mover's centipawn eval (evals clamped
to +-1000). Outputs per band:
  acpl: mean centipawn loss per phase {opening, middle, end}
  blunder_rate / mistake_rate / inaccuracy_rate: share of moves whose win-probability loss is
      >= 20 / >= 10 / >= 5 percentage points (and < the next threshold)
  common_themes_missed: top tactical themes (heuristic, see classify_theme) behind blunders
Phase: opening = ply <= 20 and not endgame; endgame = total N/B/R/Q material <= 14; else middle.
Theme labels are cheap heuristics on the reply that punished the blunder, not engine-verified.
"""
import argparse
import sys
from collections import Counter, defaultdict

import chess

import config
from common import open_text, write_json, add_common_args, download, iter_pgn_games
from gamestream import (game_ok, game_band, parse_moves, win_pct, is_endgame, START_EVAL, PIECE_VAL)

INACC, MISTAKE, BLUNDER = 5.0, 10.0, 20.0
GENERIC = {"other_tactic", "check_tactic"}  # too vague to report


def classify_theme(board_before_blunder, blunder, reply):
    """Heuristic label for how the reply punished a blunder. board is before the blunder."""
    b = board_before_blunder.copy()
    b.push(blunder)
    mover_after = b.turn  # side that will play the reply
    reply_piece = b.piece_at(reply.from_square)
    if b.is_capture(reply):
        victim = b.piece_at(reply.to_square)
        if victim is None:  # en passant
            return "hanging_piece"
        if PIECE_VAL.get(victim.piece_type, 0) >= 3 or not b.is_attacked_by(not mover_after, reply.to_square):
            return "hanging_piece"
    b.push(reply)
    if b.is_checkmate():
        back = chess.square_rank(b.king(b.turn)) in (0, 7)
        return "back_rank" if back else "mate_threat"
    if reply_piece is not None:
        hi = 0
        for sq in b.attacks(reply.to_square):
            p = b.piece_at(sq)
            if p and p.color != reply_piece.color and PIECE_VAL.get(p.piece_type, 0) > PIECE_VAL.get(reply_piece.piece_type, 0) - 1 \
                    and p.piece_type != chess.PAWN:
                hi += 1
        if hi >= 2:
            return "fork"
    if b.is_check():
        return "check_tactic"
    return "other_tactic"


def new_band():
    return {"loss": {"opening": [0, 0], "middle": [0, 0], "end": [0, 0]},
            "moves": 0, "inacc": 0, "mist": 0, "blun": 0, "games": 0, "themes": Counter()}


def process_game(movetext, acc):
    moves = parse_moves(movetext)
    # evals are absent on the final (mating) move(s); use the evaluated prefix only
    k = 0
    while k < len(moves) and moves[k][1] is not None:
        k += 1
    if k < 10 or len(moves) - k > 2:
        return False
    moves = moves[:k]
    board = chess.Board()
    prev = START_EVAL
    prev_move = None
    pending = None  # (board_before, blunder_move) awaiting the reply
    local = []
    for ply, (san, ev) in enumerate(moves, 1):
        try:
            mv = board.parse_san(san)
        except ValueError:
            return False
        white = board.turn == chess.WHITE
        before = board.copy(stack=False)
        phase = "end" if is_endgame(board) else ("opening" if ply <= 20 else "middle")
        sign = 1 if white else -1
        loss_cp = max(0, sign * (prev - ev))
        wl = win_pct(sign * prev) - win_pct(sign * ev)
        if pending is not None:
            local.append(("theme", classify_theme(pending[0], pending[1], mv)))
            pending = None
        local.append(("move", phase, loss_cp, wl))
        if wl >= BLUNDER:
            pending = (before, mv)
        board.push(mv)
        prev = ev
    for rec in local:
        if rec[0] == "theme":
            acc["themes"][rec[1]] += 1
        else:
            _, phase, loss_cp, wl = rec
            acc["loss"][phase][0] += loss_cp
            acc["loss"][phase][1] += 1
            acc["moves"] += 1
            if wl >= BLUNDER:
                acc["blun"] += 1
            elif wl >= MISTAKE:
                acc["mist"] += 1
            elif wl >= INACC:
                acc["inacc"] += 1
    acc["games"] += 1
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(ap, config.DATA / "benchmarks.json")
    ap.add_argument("--min-games", type=int, default=30, help="drop bands with fewer analysed games")
    ap.add_argument("--include-bullet", action="store_true")
    ap.add_argument("--tolerate-truncated", action="store_true")
    a = ap.parse_args()
    src = a.input or str(download(config.GAMES_URL, config.ROOT / "scripts" / ".cache" / f"games_{config.GAMES_MONTH}.pgn.zst"))
    fh = open_text(src)
    acc = {n: new_band() for n in config.BAND_NAMES}
    read = used = 0
    try:
        for headers, movetext in iter_pgn_games(fh):
            read += 1
            if a.limit and read > a.limit:
                break
            if "[%eval" not in movetext or not game_ok(headers, not a.include_bullet):
                continue
            band = game_band(headers)
            if band and process_game(movetext, acc[band]):
                used += 1
    except Exception as ex:
        if not a.tolerate_truncated:
            raise
        print(f"stream ended early ({type(ex).__name__}); keeping partial results", file=sys.stderr)
    out = {"band": {}}
    for band, s in acc.items():
        if s["games"] < a.min_games or not s["moves"]:
            continue
        r = lambda x: round(x, 4)
        out["band"][band] = {
            "acpl": {k: round(v[0] / v[1], 1) if v[1] else None for k, v in s["loss"].items()},
            "blunder_rate": r(s["blun"] / s["moves"]),
            "mistake_rate": r(s["mist"] / s["moves"]),
            "inaccuracy_rate": r(s["inacc"] / s["moves"]),
            "common_themes_missed": [t for t, _ in s["themes"].most_common() if t not in GENERIC][:5],
            "games": s["games"],
        }
    write_json(a.out, out, compact=False)
    print(f"games read {read}, analysed {used}; bands: {list(out['band'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
