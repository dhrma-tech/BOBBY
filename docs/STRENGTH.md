# Bobby strength calibration (below 1320)

All tunable constants live in `site/src/bridge/strength.ts`. The browser engine and the calibration script both import that file.

Run the calibration with:

```
cd site && node scripts/calibrate-strength.mjs --targets 1200,800,400 --anchors 1320 --games 10 --movetime 100
```

How the script works:

- Bobby plays the fixed-strength Stockfish anchor (`UCI_LimitStrength`, `UCI_Elo` 1320, which is the floor) with alternating colours.
- Then each lower target plays the next higher one, which chains the scale below the anchor.
- Performance rating = anchor + 400·log10(s/(1−s)). Scores are clamped to 5-95%.
- Both sides use the same Stockfish 18 lite single-thread WASM build that the browser uses.

## Caveats

- Stockfish's `UCI_Elo` is calibrated at 60s+0.6s against engine pools, not humans. These runs use 50-200 ms per move.
- With 6-10 games per match, the error bars are about ±150-250 Elo. Use the numbers to check the order of the targets and to spot large miscalibration, not as precise ratings.
- In the browser, Bobby searches up to 400 ms per move. The script uses min(4×movetime, 400) ms.

## Runs (2026-11-24)

| Constants | movetime | Bobby@1200 vs SF1320 | Bobby@800 vs SF1320 | Bobby@400 vs SF1320 | Chain 800 vs 1200 | Chain 400 vs 800 |
|---|---|---|---|---|---|---|
| v1 (original) | 50 ms | 9/10 → ~1700 | 3.5/10 → ~1210 | 0.5/10 → ~810 | 0.5/10 | 1.5/10 |
| v1 | 200 ms | 6/6 → ≥1830 (bound) | 4.5/6 → ~1510 | – | – | – |
| trial: hi depth 5, skill 2, temp 110, blunder 0.08 | 100 ms | 4.5/8 → ~1360 | 2/8 → ~1130 | – | – | – |
| trial: hi depth 4, skill 1, temp 150, blunder 0.10 | 100 ms | 1/8 → ~980 | 0/8 (bound) | 1/8 | 0/8 | 0/8 |
| **v2 (shipped)**: hi depth 5, skill 2, temp 125, blunder 0.09; lo depth 1, temp 360, blunder 0.30 | 100 ms | 6/10 → ~1390 | 1/10 → ~940 | 1.5/10 → ~1020 | 2/10 → ~1150 | 1/10 → ~770 |

v1 values: lo depth 3, multipv 6, skill 0, temp 260, blunder 0.20; hi depth 9, multipv 4, skill 6, temp 45, blunder 0.03.

## Findings

- v1 was far too strong below 1320. A target of 800 outscored Stockfish at 1320, and a target of 1200 was much stronger than the 1320 setting. That left a strength jump at the boundary going the wrong way.
- v2 roughly removes the jump at the top: 1200 scores about 60% against SF 1320.
- With v2, the low end still reads too strong (400 performs around 770-1020), and 400 and 800 are not clearly separated in 10-game samples.
- Next step: run more games (40 or more per target) and push `WEAK.lo` weaker, for example with a higher `blunderProb` and `temperatureCp`. Maia (see MAIA.md) would replace this whole curve.
