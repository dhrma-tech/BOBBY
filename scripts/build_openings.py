#!/usr/bin/env python3
"""Build data/openings.json from lichess-org/chess-openings TSVs (CC0).

Each TSV: eco<TAB>name<TAB>pgn. We replay the pgn with python-chess and add the EPD
of the final position. Output: [{eco, name, pgn, epd}].
--input may be a directory containing a.tsv..e.tsv; default downloads from GitHub.
"""
import argparse
import csv
import io
import sys
import urllib.request
from pathlib import Path

import chess

import config
from common import write_json


def parse_tsv(text, limit=0):
    out = []
    for r in csv.DictReader(io.StringIO(text), delimiter="\t"):
        board = chess.Board()
        try:
            for tok in r["pgn"].split():
                if tok.endswith(".") or "." in tok and tok.rstrip(".").isdigit():
                    continue
                board.push_san(tok)
        except ValueError:
            print(f"skip unparsable: {r['eco']} {r['name']}", file=sys.stderr)
            continue
        out.append({"eco": r["eco"], "name": r["name"], "pgn": r["pgn"], "epd": board.epd()})
        if limit and len(out) >= limit:
            break
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", "-i", help="directory with a.tsv..e.tsv (default: download)")
    ap.add_argument("--out", "-o", default=str(config.DATA / "openings.json"))
    ap.add_argument("--limit", "--max-games", dest="limit", type=int, default=0)
    a = ap.parse_args()
    out = []
    for f in config.OPENINGS_FILES:
        if a.input:
            text = (Path(a.input) / f).read_text(encoding="utf-8")
        else:
            with urllib.request.urlopen(config.OPENINGS_BASE + f) as r:
                text = r.read().decode("utf-8")
        out += parse_tsv(text, a.limit - len(out) if a.limit else 0)
        if a.limit and len(out) >= a.limit:
            break
    write_json(a.out, out)
    print(f"wrote {len(out)} openings", file=sys.stderr)


if __name__ == "__main__":
    main()
