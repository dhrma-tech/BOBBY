#!/usr/bin/env python3
"""Build data/puzzles.json from the Lichess puzzle CSV (CC0).

Input CSV columns: PuzzleId,FEN,Moves,Rating,RatingDeviation,Popularity,NbPlays,Themes,GameUrl,OpeningTags
In the dump, FEN is the position BEFORE the opponent's setup move and Moves[0] is that setup move.
Output follows docs/CONTRACT.md: fen = position AFTER the setup move (solver to move),
solution = remaining moves, starting with the solver's move.

Selection: filter by popularity / plays / rating deviation, bucket by rating (spread),
cap per primary theme inside each bucket (theme diversity), keep ~--target puzzles.
Optional validation with a pinned-depth Stockfish (--stockfish PATH).
"""
import argparse
import csv
import heapq
import sys
from collections import defaultdict
from pathlib import Path

import chess
import chess.engine

import config
from common import open_text, write_json, add_common_args, download

# Themes that describe metadata rather than the tactic; not used as primary theme.
META = {"short", "long", "veryLong", "oneMove", "advantage", "crushing", "equality",
        "opening", "middlegame", "endgame", "mate"}


def primary_theme(themes):
    for t in themes:
        if t not in META and not t.startswith("mateIn"):
            return t
    return themes[0] if themes else "none"


def select(rows, target, bucket_w, rmin, rmax):
    """rows: iterable of puzzle dicts (already filtered). Returns balanced subset."""
    nb = max(1, (rmax - rmin) // bucket_w)
    quota = max(1, target // nb)
    pools = defaultdict(list)  # bucket -> min-heap of (score, id, puzzle)
    keep = quota * 4
    for p in rows:
        b = min(nb - 1, max(0, (p["rating"] - rmin) // bucket_w))
        item = (p["popularity"], p["_plays"], p["id"], p)
        h = pools[b]
        if len(h) < keep:
            heapq.heappush(h, item)
        elif item > h[0]:
            heapq.heapreplace(h, item)
    out = []
    theme_cap = max(5, quota // 5)
    for b in sorted(pools):
        taken, per_theme = 0, defaultdict(int)
        for _, _, _, p in sorted(pools[b], reverse=True):
            pt = primary_theme(p["themes"])
            if per_theme[pt] >= theme_cap:
                continue
            per_theme[pt] += 1
            out.append(p)
            taken += 1
            if taken >= quota:
                break
    return out


_ENG = None


def _init_worker(path):
    global _ENG
    _ENG = chess.engine.SimpleEngine.popen_uci(path)


def _check(args):
    p, depth, gap_cp = args
    board = chess.Board(p["fen"])
    info = _ENG.analyse(board, chess.engine.Limit(depth=depth), multipv=2)
    if not info or "pv" not in info[0] or info[0]["pv"][0].uci() != p["solution"][0]:
        return False
    if len(info) > 1:
        s1, s2 = info[0]["score"].relative, info[1]["score"].relative
        if not s1.is_mate() and not s2.is_mate() and s1.score() - s2.score() < gap_cp:
            return False
    return True


def validate(puzzles, stockfish, depth, gap_cp=150, workers=2):
    """Keep puzzles whose first solver move is Stockfish's best at fixed depth and clearly
    better (>= gap_cp, unless a mate is involved) than the second-best move."""
    import multiprocessing as mp
    with mp.Pool(workers, _init_worker, (stockfish,)) as pool:
        flags = pool.map(_check, [(p, depth, gap_cp) for p in puzzles], chunksize=64)
    return [p for p, ok in zip(puzzles, flags) if ok]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(ap, config.DATA / "puzzles.json")
    ap.add_argument("--target", type=int, default=25000, help="approx puzzles to keep")
    ap.add_argument("--min-popularity", type=int, default=90)
    ap.add_argument("--min-plays", type=int, default=1000)
    ap.add_argument("--max-rd", type=int, default=90, help="max rating deviation")
    ap.add_argument("--rating-min", type=int, default=400)
    ap.add_argument("--rating-max", type=int, default=2800)
    ap.add_argument("--bucket", type=int, default=100)
    ap.add_argument("--stockfish", help="path to stockfish binary for pinned-depth validation")
    ap.add_argument("--workers", type=int, default=2, help="stockfish worker processes")
    ap.add_argument("--depth", type=int, default=config.STOCKFISH_DEPTH)
    a = ap.parse_args()

    src = a.input
    if src and src.endswith(".json"):  # re-validate an existing puzzles.json
        import json
        chosen = json.load(open(src, encoding="utf-8"))
        if a.limit:
            chosen = chosen[:a.limit]
        if a.stockfish:
            chosen = validate(chosen, a.stockfish, a.depth, workers=a.workers)
        print(f"validated: {len(chosen)}", file=sys.stderr)
        write_json(a.out, chosen)
        return
    if not src:
        src = str(download(config.PUZZLE_URL, config.ROOT / "scripts" / ".cache" / "lichess_db_puzzle.csv.zst"))
    fh = open_text(src)
    rd = csv.DictReader(fh)
    rows, seen = [], 0

    def gen():
        nonlocal seen
        for r in rd:
            seen += 1
            if a.limit and seen > a.limit:
                break
            try:
                rating, pop = int(r["Rating"]), int(r["Popularity"])
                plays, dev = int(r["NbPlays"]), int(r["RatingDeviation"])
            except (ValueError, KeyError):
                continue
            if pop < a.min_popularity or plays < a.min_plays or dev > a.max_rd:
                continue
            if not (a.rating_min <= rating < a.rating_max):
                continue
            moves = r["Moves"].split()
            if len(moves) < 2:
                continue
            try:
                board = chess.Board(r["FEN"])
                board.push_uci(moves[0])  # opponent's setup move
                # sanity: remaining moves must be legal in sequence
                chk = board.copy()
                for m in moves[1:]:
                    chk.push_uci(m)
            except (ValueError, AssertionError):
                continue
            yield {"id": r["PuzzleId"], "fen": board.fen(), "solution": moves[1:],
                   "themes": r["Themes"].split(), "rating": rating, "popularity": pop,
                   "_plays": plays}

    chosen = select(gen(), a.target, a.bucket, a.rating_min, a.rating_max)
    print(f"read {seen} rows, selected {len(chosen)}", file=sys.stderr)
    if a.stockfish:
        chosen = validate(chosen, a.stockfish, a.depth, workers=a.workers)
        print(f"after stockfish depth {a.depth}: {len(chosen)}", file=sys.stderr)
    for p in chosen:
        p.pop("_plays", None)
    chosen.sort(key=lambda p: (p["rating"], p["id"]))
    write_json(a.out, chosen)


if __name__ == "__main__":
    main()
