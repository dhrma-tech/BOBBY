#!/usr/bin/env python3
"""Validate every file in data/ against docs/CONTRACT.md. Exit code 1 on any error.

Usage: validate_data.py [--data DIR] [--syzygy DIR] [--engine STOCKFISH [--depth N]]
  --syzygy  also re-check endgames.json outcomes against tablebases
  --engine  also check that lesson move answers in 'Tactics'/'Basic mates' sections are
            (near-)best according to a pinned-depth Stockfish
"""
import argparse
import json
import re
import sys
from pathlib import Path

import chess
import chess.engine
import chess.syzygy

import config

BANDS = set(config.BAND_NAMES)
errors = []


def err(where, msg):
    errors.append(f"{where}: {msg}")


def load(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        err(path.name, "missing")
    except json.JSONDecodeError as e:
        err(path.name, f"bad JSON: {e}")
    return None


def fen_ok(fen, where):
    try:
        b = chess.Board(fen)
    except ValueError as e:
        err(where, f"bad FEN {fen!r}: {e}")
        return None
    st = b.status()
    if st != chess.STATUS_VALID:
        err(where, f"invalid position {fen!r}: {st!r}")
        return None
    return b


def is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def check_puzzles(d):
    if not isinstance(d, list) or not d:
        return err("puzzles.json", "expected non-empty list")
    ids = set()
    for i, p in enumerate(d):
        w = f"puzzles[{i}]"
        if set(p) != {"id", "fen", "solution", "themes", "rating", "popularity"}:
            err(w, f"keys {sorted(p)}"); continue
        if p["id"] in ids: err(w, "duplicate id")
        ids.add(p["id"])
        if not (is_int(p["rating"]) and is_int(p["popularity"])): err(w, "rating/popularity must be int")
        if not (isinstance(p["themes"], list) and all(isinstance(t, str) for t in p["themes"])): err(w, "themes")
        b = fen_ok(p["fen"], w)
        if b is None: continue
        if not p["solution"]: err(w, "empty solution")
        for u in p["solution"]:
            try:
                b.push_uci(u)
            except ValueError:
                err(w, f"illegal solution move {u}"); break


def check_openings(d):
    if not isinstance(d, list) or not d:
        return err("openings.json", "expected non-empty list")
    for i, o in enumerate(d):
        w = f"openings[{i}]"
        if set(o) != {"eco", "name", "pgn", "epd"}: err(w, f"keys {sorted(o)}"); continue
        if not re.fullmatch(r"[A-E]\d\d", o["eco"]): err(w, f"eco {o['eco']}")
        b = chess.Board()
        try:
            for tok in o["pgn"].split():
                if re.fullmatch(r"\d+\.+", tok): continue
                b.push_san(tok)
        except ValueError:
            err(w, f"pgn not replayable: {o['pgn']}"); continue
        if b.epd() != o["epd"]: err(w, "epd does not match pgn")


def check_stats(d, openings):
    if not isinstance(d, dict) or "band" not in d: return err("opening_stats.json", "expected {band:{...}}")
    epds = {o["epd"] for o in openings} if openings else None
    for band, m in d["band"].items():
        if band not in BANDS: err("opening_stats.json", f"unknown band {band}")
        for epd, s in m.items():
            w = f"opening_stats[{band}][{epd}]"
            if not (isinstance(s, dict) and set(s) == {"n", "w", "d", "l"} and all(is_int(v) and v >= 0 for v in s.values())):
                err(w, "need ints n,w,d,l"); continue
            if s["n"] != s["w"] + s["d"] + s["l"]: err(w, "n != w+d+l")
            if epds is not None and epd not in epds: err(w, "epd not in openings.json")


def check_benchmarks(d):
    if not isinstance(d, dict) or "band" not in d: return err("benchmarks.json", "expected {band:{...}}")
    for band, m in d["band"].items():
        w = f"benchmarks[{band}]"
        if band not in BANDS: err(w, "unknown band")
        for k in ("acpl", "blunder_rate", "mistake_rate", "inaccuracy_rate", "common_themes_missed"):
            if k not in m: err(w, f"missing {k}")
        if set(m.get("acpl", {})) != {"opening", "middle", "end"}: err(w, "acpl keys")
        for k, v in m.get("acpl", {}).items():
            if v is not None and not isinstance(v, (int, float)): err(w, f"acpl.{k}")
        for k in ("blunder_rate", "mistake_rate", "inaccuracy_rate"):
            if not (isinstance(m.get(k), (int, float)) and 0 <= m[k] <= 1): err(w, f"{k} not in 0..1")
        if not all(isinstance(t, str) for t in m.get("common_themes_missed", [])): err(w, "themes")


def check_endgames(d, syzygy):
    if not isinstance(d, list) or not d: return err("endgames.json", "expected non-empty list")
    tb = None
    if syzygy:
        tb = chess.syzygy.open_tablebase(syzygy)
    ids = set()
    for i, e in enumerate(d):
        w = f"endgames[{i}]"
        if set(e) != {"id", "name", "fen", "goal", "dtz", "hint"}: err(w, f"keys {sorted(e)}"); continue
        if e["id"] in ids: err(w, "duplicate id")
        ids.add(e["id"])
        if e["goal"] not in ("win", "draw"): err(w, "goal")
        if not (e["dtz"] is None or is_int(e["dtz"])): err(w, "dtz")
        if not (isinstance(e["hint"], str) and e["hint"]): err(w, "hint")
        b = fen_ok(e["fen"], w)
        if b is not None and tb is not None:
            wdl = tb.get_wdl(b)
            want = 2 if e["goal"] == "win" else 0
            if wdl != want: err(w, f"tablebase wdl {wdl} != expected {want}")
    if tb: tb.close()


def check_cards(d):
    if not isinstance(d, list) or len(d) < 40: return err("knowledge_cards.json", "need list of >= 40 cards")
    ids = set()
    for i, c in enumerate(d):
        w = f"cards[{i}]"
        if set(c) != {"id", "tags", "title", "text"}: err(w, f"keys {sorted(c)}"); continue
        if c["id"] in ids: err(w, "duplicate id")
        ids.add(c["id"])
        if not (isinstance(c["tags"], list) and c["tags"] and all(isinstance(t, str) for t in c["tags"])): err(w, "tags")
        if not (isinstance(c["title"], str) and c["title"].strip()): err(w, "title")
        if not (isinstance(c["text"], str) and 40 <= len(c["text"]) <= 600): err(w, f"text length {len(c.get('text', ''))} not in 40..600")


STEP_KEYS = {"type", "fen", "prompt", "correct", "options", "explanation", "hint"}
ENGINE_SECTIONS = {"Tactics", "Basic mates"}


def check_lessons(folder, engine, depth):
    files = sorted(folder.glob("*.json"))
    if len(files) < 25: err("lessons", f"need >= 25 lesson files, found {len(files)}")
    ids, orders, eng = set(), set(), None
    if engine:
        eng = chess.engine.SimpleEngine.popen_uci(engine)
    for f in files:
        L = load(f)
        if L is None: continue
        w = f.name
        if set(L) != {"id", "title", "section", "order", "steps"}: err(w, f"keys {sorted(L)}"); continue
        if L["id"] in ids: err(w, "duplicate id")
        ids.add(L["id"])
        if f.stem != L["id"]: err(w, "filename must equal id")
        if not is_int(L["order"]) or L["order"] in orders: err(w, "order must be unique int")
        orders.add(L["order"])
        if not (4 <= len(L["steps"]) <= 8): err(w, f"{len(L['steps'])} steps (need 4-8)")
        for j, s in enumerate(L["steps"]):
            sw = f"{w} step {j}"
            if set(s) != STEP_KEYS: err(sw, f"keys {sorted(s)}"); continue
            if s["type"] not in ("info", "move", "square", "quiz"): err(sw, "type"); continue
            for k in ("prompt", "explanation", "hint"):
                if not isinstance(s[k], str) or not s[k].strip(): err(sw, f"empty {k}")
            b = fen_ok(s["fen"], sw)
            if b is None: continue
            c, t = s["correct"], s["type"]
            if not isinstance(c, list): err(sw, "correct must be list"); continue
            if t == "info":
                if c or s["options"] is not None: err(sw, "info needs correct [] and options null")
            elif t == "move":
                if not c or s["options"] is not None: err(sw, "move needs non-empty correct, options null")
                legal = {m.uci() for m in b.legal_moves}
                for u in c:
                    if u not in legal: err(sw, f"answer {u} not legal in {s['fen']}")
                if eng and L["section"] in ENGINE_SECTIONS and all(u in legal for u in c):
                    info = eng.analyse(b, chess.engine.Limit(depth=depth))
                    best = info["score"].relative.score(mate_score=10000)
                    for u in c:
                        b.push_uci(u)
                        after = -eng.analyse(b, chess.engine.Limit(depth=depth))["score"].relative.score(mate_score=10000)
                        b.pop()
                        if after < best - 60: err(sw, f"engine: {u} scores {after} vs best {best}")
            elif t == "square":
                if not c or s["options"] is not None: err(sw, "square needs non-empty correct, options null")
                for q in c:
                    if q not in chess.SQUARE_NAMES: err(sw, f"bad square {q}")
            else:  # quiz
                o = s["options"]
                if not (isinstance(o, list) and len(o) >= 2 and all(isinstance(x, str) for x in o) and len(set(o)) == len(o)):
                    err(sw, "quiz needs >= 2 distinct string options"); continue
                if not c or not set(c) <= set(o): err(sw, "quiz correct must be non-empty subset of options")
                if all(re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", x) for x in o):
                    legal = {m.uci() for m in b.legal_moves}
                    for x in o:
                        if x not in legal: err(sw, f"quiz option {x} not legal")
    if eng: eng.quit()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(config.DATA))
    ap.add_argument("--syzygy")
    ap.add_argument("--engine")
    ap.add_argument("--depth", type=int, default=config.STOCKFISH_DEPTH)
    a = ap.parse_args()
    D = Path(a.data)
    openings = load(D / "openings.json")
    pz = load(D / "puzzles.json"); pz is not None and check_puzzles(pz)
    openings is not None and check_openings(openings)
    st = load(D / "opening_stats.json"); st is not None and check_stats(st, openings)
    bm = load(D / "benchmarks.json"); bm is not None and check_benchmarks(bm)
    eg = load(D / "endgames.json"); eg is not None and check_endgames(eg, a.syzygy)
    kc = load(D / "knowledge_cards.json"); kc is not None and check_cards(kc)
    check_lessons(D / "lessons", a.engine, a.depth)
    if errors:
        print(f"FAILED: {len(errors)} problem(s)")
        for e in errors[:100]: print(" -", e)
        sys.exit(1)
    print("OK: all data files valid")


if __name__ == "__main__":
    main()
