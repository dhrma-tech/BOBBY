"""Streaming helpers shared by scripts (stdlib + zstandard + python-chess)."""
import io
import json
import re
import sys
from pathlib import Path


def open_text(path):
    """Open .zst / .gz / plain text transparently, streaming. '-' = stdin."""
    p = str(path)
    if p == "-":
        return sys.stdin
    if p.endswith(".zst"):
        import zstandard
        fh = open(p, "rb")
        reader = zstandard.ZstdDecompressor().stream_reader(fh)
        return io.TextIOWrapper(reader, encoding="utf-8", errors="replace", newline="")
    if p.endswith(".gz"):
        import gzip
        return gzip.open(p, "rt", encoding="utf-8", errors="replace", newline="")
    return open(p, "r", encoding="utf-8", errors="replace", newline="")


def write_json(path, obj, compact=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if compact:
            json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)
        else:
            json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")


HEADER_RE = re.compile(r'^\[(\w+)\s+"(.*)"\]\s*$')


def iter_pgn_games(fh):
    """Yield (headers dict, movetext str) from a PGN text stream without python-chess
    (fast path for huge dumps). Games are separated by blank line after movetext."""
    headers, movetext, in_moves = {}, [], False
    for line in fh:
        if line.startswith("["):
            if in_moves:
                yield headers, " ".join(movetext)
                headers, movetext, in_moves = {}, [], False
            m = HEADER_RE.match(line)
            if m:
                headers[m.group(1)] = m.group(2)
        elif line.strip():
            in_moves = True
            movetext.append(line.strip())
    if headers and movetext:
        yield headers, " ".join(movetext)


def epd_of(board):
    """EPD with only the en-passant square when legally capturable (python-chess epd())."""
    return board.epd()


def add_common_args(ap, default_out):
    ap.add_argument("--input", "-i", help="input file (.zst/.gz/plain) or '-' for stdin; default: download pinned dataset")
    ap.add_argument("--out", "-o", default=str(default_out), help="output path")
    ap.add_argument("--limit", "--max-games", dest="limit", type=int, default=0,
                    help="stop after N input records (0 = no limit)")


def download(url, dest):
    import urllib.request
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {url} -> {dest}", file=sys.stderr)
    urllib.request.urlretrieve(url, dest)
    return dest
