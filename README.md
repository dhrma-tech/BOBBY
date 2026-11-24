# Bobby

Bobby is an open-source, single-user AI chess learning web app. It plays you at a strength that adapts to your rating, explains your games in plain language, and builds a daily training plan from your own mistakes. No account, no server: everything runs in your browser and your data stays in local storage.

## Features

- **Play**: versus Bobby at adaptive strength, or pass-and-play on one screen. Time controls, takebacks, three-level hints, PGN and FEN import and export.
- **Learn from scratch**: interactive lessons on the board (piece moves, special moves, check and mate, basic mates, tactics, opening principles, endgames).
- **Coach (no AI)**: plain-language explanations built from engine facts and tactic detectors, with arrows on the board. Every move in a review is explained (what it did, what it allowed, what was better), "Show me" plays the better line, and five questions work on any position: threats, pieces in danger, best move and why, who is better and why, and the plan. Answers link to the matching lesson or puzzles. Works fully offline, no keys.
- **Safety net**: optional check before you play a move that hangs a piece or allows mate in one.
- **Daily progression**: Bobby steps up or eases off each day from your recent games, and challenge targets follow your form.
- **Review**: accuracy, move classes (best to blunder), key moments, and phase breakdown for every game.
- **Train**: puzzles from your own mistakes with spaced repetition, themed puzzle sets, endgame trainer with tablebase-verified goals, opening explorer, daily challenges and achievements.
- **Stats**: rating curve, accuracy trend, weakness heatmap, and benchmarks that show how your play compares with players in your rating band.
- **PWA**: install it in one click from the browser, works offline after the first load, usable on a phone.

## Architecture

```
 Browser (installable PWA)
 +-------------------------------------------------------------+
 | site/ (Vite + React + TypeScript)                           |
 |   pages: play | review | learn | train | stats              |
 |        |                                                    |
 |   bridge/                                                   |
 |     +-- Pyodide worker ---> py/bobby (python-chess + stdlib)|
 |     |      rules, classify, glicko, srs, lessons, coach text |
 |     +-- Stockfish worker (WASM)   analysis and bot strength |
 |     +-- Maia worker (ONNX)        human-like play           |
 |     +-- Dexie (IndexedDB)         profile, games, progress  |
 |        |                                                    |
 |   static data: data/*.json  (puzzles, openings, lessons...) |
 +-------------------------------------------------------------+
        ^ built offline by
 scripts/  (pure Python pipeline: Lichess CC0 dumps, Syzygy -> data/)
```

The Python core and the TypeScript shell talk through the JSON-only interface in `docs/CONTRACT.md`. Engines are owned by TypeScript; Python never calls them.

## Repository layout

| Path | Contents |
|---|---|
| `site/` | Web app (TypeScript, React) |
| `py/` | Python core (`bobby`) and its pytest tests |
| `data/` | Shipped data assets: puzzles, openings, opening stats, benchmarks, endgames, knowledge cards, lessons |
| `scripts/` | Reproducible data pipeline and `validate_data.py` |
| `docs/` | `PLAN.md` and `CONTRACT.md` |

## Run it

```sh
# web app
cd site
npm install
npm run dev          # development server
npm run build        # production build in site/dist

# Python core tests
cd py
pip install python-chess pytest
pytest

# data: validate shipped files, or regenerate them (see scripts/README.md)
pip install python-chess zstandard
python scripts/validate_data.py
```

## Data

| File | Origin |
|---|---|
| `data/openings.json` | Real. Generated from the CC0 lichess-org/chess-openings repository. |
| `data/puzzles.json` | Real. Filtered from the CC0 Lichess puzzle database and re-checked with Stockfish 16 at depth 12. |
| `data/endgames.json` | Real. Positions and outcomes from Syzygy 3-4-5 tablebases. |
| `data/opening_stats.json`, `data/benchmarks.json` | Real, computed from the first 1.5 GB (compressed) of the 2026-10 Lichess standard rated dump, i.e. the first day or so of that month: opening stats from its first 2.5M games, benchmarks from 363k games with `[%eval]`. Rebuild from a full month for tighter numbers. |
| `data/lessons/`, `data/knowledge_cards.json` | Original text written for Bobby. |

See `scripts/README.md` for how to regenerate everything.

## License

GPL-3.0. See `LICENSE`. Third-party components and data are listed in `THIRD_PARTY_NOTICES.md`.

## Credits

- Lichess open database (CC0): puzzles, games and the chess-openings list. Thank you for publishing it.
- Stockfish, the open-source engine.
- Maia Chess, for human-like move prediction models.
- python-chess, for rules, PGN and tablebase support.
- chess.js-compatible tools on the TypeScript side.
- Syzygy tablebases by Ronald de Man.

This project is independent and is not affiliated with Lichess or any other chess site.
