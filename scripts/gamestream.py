"""Parse Lichess PGN dump games (headers + movetext with [%eval] comments)."""
import math
import re

import chess

import config

TOKEN_RE = re.compile(r"(?:\d+\.+\s*)?([^\s{}]+)(?:\s*\{([^}]*)\})?")
EVAL_RE = re.compile(r"\[%eval\s+(#?-?\d+(?:\.\d+)?)\]")
RESULT_TOKENS = {"1-0", "0-1", "1/2-1/2", "*"}
CP_CLAMP = 1000
START_EVAL = 18  # centipawns, white view, approx value of the initial position


def parse_eval(comment):
    """-> white-view centipawns (mate clamped to +-CP_CLAMP) or None."""
    if not comment:
        return None
    m = EVAL_RE.search(comment)
    if not m:
        return None
    v = m.group(1)
    if v.startswith("#"):
        n = int(v[1:])
        return CP_CLAMP if n > 0 else -CP_CLAMP
    return max(-CP_CLAMP, min(CP_CLAMP, round(float(v) * 100)))


def parse_moves(movetext):
    """-> list of (san, eval_cp_white|None)."""
    out = []
    for m in TOKEN_RE.finditer(movetext):
        tok = m.group(1)
        if tok in RESULT_TOKENS or tok.startswith("$"):
            continue
        out.append((tok.rstrip("!?"), parse_eval(m.group(2))))
    return out


def win_pct(cp):
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def game_band(headers):
    """Band by mean rating of both players; None if unrated/unknown/too low."""
    try:
        w, b = int(headers["WhiteElo"]), int(headers["BlackElo"])
    except (KeyError, ValueError):
        return None
    return config.band_of((w + b) // 2)


def game_ok(headers, skip_bullet=True):
    """Rated standard game, both players rated, normal termination."""
    ev = headers.get("Event", "")
    if "Rated" not in ev:
        return False
    if skip_bullet and ("Bullet" in ev):
        return False
    if headers.get("Termination", "Normal") not in ("Normal", "Time forfeit"):
        return False
    if headers.get("Variant", "Standard") != "Standard":
        return False
    if "?" in (headers.get("WhiteElo", "?"), headers.get("BlackElo", "?")):
        return False
    return True


def result_of(headers):
    return headers.get("Result")


PIECE_VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}


def is_endgame(board):
    tot = sum(PIECE_VAL[pt] * (len(board.pieces(pt, True)) + len(board.pieces(pt, False)))
              for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN))
    return tot <= 14
