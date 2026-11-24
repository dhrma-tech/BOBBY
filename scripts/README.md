# Data pipeline

Offline, reproducible Python scripts that reduce large open datasets into the small JSON files in `data/`. Raw dumps are never committed (see `.gitignore`).

Requirements: Python 3.10+, `pip install python-chess zstandard`. Optional: a `stockfish` binary for puzzle validation.

Pinned inputs live in `scripts/config.py` (`GAMES_MONTH`, URLs, rating bands, `STOCKFISH_DEPTH`). Change them in one place.

All scripts accept `--input`, `--out` and `--limit` (alias `--max-games`, stop after N input records). `--input -` reads stdin. `.zst`, `.gz` and plain files are handled in streaming mode. Without `--input` the pinned dump is downloaded to `scripts/.cache/`.

| Script | Input | Output | Notes |
|---|---|---|---|
| `build_openings.py` | `a.tsv`..`e.tsv` of lichess-org/chess-openings (dir) or downloads them | `data/openings.json` | Replays each line with python-chess to add the EPD |
| `build_puzzles.py` | `lichess_db_puzzle.csv.zst` | `data/puzzles.json` | Filters popularity >= 90, plays >= 1000, rating deviation <= 90; 100-point rating buckets with a per-theme cap; `--target 25000`. Setup move is applied so `fen` is the solver's position. `--stockfish PATH` re-checks that the first move is best at depth 12 and at least 150 cp better than the second (mates exempt). Pass an existing `puzzles.json` as `--input` to validate it only |
| `build_opening_stats.py` | monthly `lichess_db_standard_rated_YYYY-MM.pgn.zst` | `data/opening_stats.json` | Win/draw/loss (White's view) per band and opening EPD up to ply 24; `--min-n` drops rare lines |
| `build_benchmarks.py` | same monthly dump | `data/benchmarks.json` | Only games with `[%eval]` on every move. ACPL by phase, blunder/mistake/inaccuracy rates (win-probability loss >= 20 / 10 / 5 points), most frequent heuristic tactic types behind blunders |
| `build_endgames.py` | directory with Syzygy 3-4-5 `.rtbw` and `.rtbz` | `data/endgames.json` | Random positions (fixed seed) with tablebase outcome and DTZ; keeps non-trivial ones |
| `validate_data.py` | `data/` | exit code | Validates every file against `docs/CONTRACT.md`; legal FENs and answers via python-chess; optional `--syzygy DIR` and `--engine PATH` |

Both game scripts bin by the mean rating of both players, skip bullet by default (`--include-bullet`), and need both players rated, standard variant, normal termination. `--tolerate-truncated` accepts a partially downloaded `.zst`.

## Regenerate everything

```sh
pip install python-chess zstandard
python scripts/build_openings.py
python scripts/build_puzzles.py --stockfish /usr/games/stockfish --workers 4
curl -O https://database.lichess.org/standard/lichess_db_standard_rated_2026-10.pgn.zst   # about 31 GB
python scripts/build_opening_stats.py -i lichess_db_standard_rated_2026-10.pgn.zst
python scripts/build_benchmarks.py    -i lichess_db_standard_rated_2026-10.pgn.zst
# Syzygy 3-4-5: https://tablebase.lichess.ovh/tables/standard/3-4-5-wdl/ and 3-4-5-dtz/
python scripts/build_endgames.py -i path/to/syzygy
python scripts/validate_data.py --syzygy path/to/syzygy --engine /usr/games/stockfish
```

For a quick run, stream only the head of a dump: `curl -r 0-1499999999 URL -o part.pgn.zst`, then pass `--tolerate-truncated`. The head covers only the first day(s) of the month, so rates are slightly biased toward that period.

## Provenance of shipped files

See the "Data" section in the top-level README. `data/lessons/` and `data/knowledge_cards.json` are hand-authored and checked by `validate_data.py`, not generated.

## Conventions

- `puzzles.json`: `fen` is after the opponent's setup move; `solution[0]` is the solver's move.
- `endgames.json`: the side to move is the solver. `goal: "win"` means the solver wins with perfect play, `"draw"` means the solver can hold the draw. `dtz` is the tablebase distance in plies for wins, `null` for draws.
- Lessons: `quiz` steps have `options` and `correct` is a subset of `options` (move quizzes use UCI strings).
- Benchmark themes (`common_themes_missed`) are cheap heuristics, not engine-verified.
