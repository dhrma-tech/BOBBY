#!/usr/bin/env python3
"""Build data/opening_stats.json: per rating band, per opening EPD, win/draw/loss counts.

Streams a monthly Lichess rated-standard PGN dump (.pgn.zst). Band = band of the mean
rating of both players. For every game, each position reached within --max-ply that matches
an EPD in openings.json is counted once. Positions with n < --min-n are dropped.
Output: {"band": {"600-800": {epd: {n, w, d, l}}}}   (w/d/l from White's point of view)
Does not need [%eval] annotations.
"""
import argparse
import json
import sys
from collections import defaultdict

import chess

import config
from common import open_text, write_json, add_common_args, download, iter_pgn_games
from gamestream import game_ok, game_band, parse_moves


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(ap, config.DATA / "opening_stats.json")
    ap.add_argument("--openings", default=str(config.DATA / "openings.json"))
    ap.add_argument("--max-ply", type=int, default=24)
    ap.add_argument("--min-n", type=int, default=20)
    ap.add_argument("--include-bullet", action="store_true")
    ap.add_argument("--tolerate-truncated", action="store_true", help="accept a truncated .zst (partial download)")
    a = ap.parse_args()

    # map python-chess transposition key -> EPD string (cheaper than building an EPD every ply)
    key_epd = {}
    for o in json.load(open(a.openings, encoding="utf-8")):
        key_epd[chess.Board(o["epd"] + " 0 1")._transposition_key()] = o["epd"]
    src = a.input or str(download(config.GAMES_URL, config.ROOT / "scripts" / ".cache" / f"games_{config.GAMES_MONTH}.pgn.zst"))
    fh = open_text(src)
    stats = {n: defaultdict(lambda: [0, 0, 0, 0]) for n in config.BAND_NAMES}
    games = used = 0
    try:
        for headers, movetext in iter_pgn_games(fh):
            games += 1
            if a.limit and games > a.limit:
                break
            if not game_ok(headers, not a.include_bullet):
                continue
            band, res = game_band(headers), headers.get("Result")
            if band is None or res not in ("1-0", "0-1", "1/2-1/2"):
                continue
            idx = 1 if res == "1-0" else 3 if res == "0-1" else 2
            board = chess.Board()
            seen = set()
            ok = True
            for san, _ in parse_moves(movetext)[:a.max_ply]:
                try:
                    board.push_san(san)
                except ValueError:
                    ok = False
                    break
                e = key_epd.get(board._transposition_key())
                if e is not None and e not in seen:
                    seen.add(e)
                    s = stats[band][e]
                    s[0] += 1
                    s[idx] += 1
            if ok:
                used += 1
    except Exception as ex:  # truncated zst
        if not a.tolerate_truncated:
            raise
        print(f"stream ended early ({type(ex).__name__}); keeping partial results", file=sys.stderr)
    out = {"band": {}}
    for band in config.BAND_NAMES:
        out["band"][band] = {e: {"n": s[0], "w": s[1], "d": s[2], "l": s[3]}
                             for e, s in stats[band].items() if s[0] >= a.min_n}
    write_json(a.out, out)
    print(f"games read {games}, used {used}; positions per band: "
          + ", ".join(f"{b}:{len(v)}" for b, v in out["band"].items()), file=sys.stderr)


if __name__ == "__main__":
    main()
