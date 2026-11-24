"""Shared pipeline config. Pin dataset months here for reproducibility."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

PUZZLE_URL = "https://database.lichess.org/lichess_db_puzzle.csv.zst"
OPENINGS_BASE = "https://raw.githubusercontent.com/lichess-org/chess-openings/master/"
OPENINGS_FILES = ["a.tsv", "b.tsv", "c.tsv", "d.tsv", "e.tsv"]

# Pinned monthly rated standard dump used for opening stats and benchmarks.
GAMES_MONTH = "2026-10"
GAMES_URL = f"https://database.lichess.org/standard/lichess_db_standard_rated_{GAMES_MONTH}.pgn.zst"

BANDS = [(600, 800), (800, 1000), (1000, 1200), (1200, 1400),
         (1400, 1600), (1600, 1800), (1800, 2000), (2000, 9999)]
BAND_NAMES = ["600-800", "800-1000", "1000-1200", "1200-1400",
              "1400-1600", "1600-1800", "1800-2000", "2000+"]


def band_of(rating):
    """Band name for a rating, or None if below 600."""
    for (lo, hi), name in zip(BANDS, BAND_NAMES):
        if lo <= rating < hi:
            return name
    return None


STOCKFISH_DEPTH = 12  # pinned depth for puzzle validation
