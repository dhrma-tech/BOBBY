# Bobby: Final Build Plan (v1)

> **Update (2026-11-24):** the AI/LLM coach, API keys and personas were removed. The coach is now rule-based: engine facts + tactic detectors (`py/bobby/explain.py`) produce plain-language answers with board arrows. Sections below that mention the LLM, providers or personas describe the original plan; see `docs/CONTRACT.md` for the current API.

Open-source, single-user, local-first AI chess learning app. Plays you at your level, learns how you play, coaches you in a persona voice. Chess logic is always engine-grounded; the LLM only explains.

Repo: `dhrma-tech/bobby` | License: GPL-3.0 (Stockfish and Lichess-derived parts are GPL) | Design base: `dhrma-tech/Cubicle`

---

## 1. Principles
- Single user. No accounts, matchmaking, lobby, sockets, or backend for chess.
- Local-first. All data on-device (IndexedDB). Works offline after first load (PWA).
- Engine is truth. Stockfish/Maia decide moves and evals. The LLM never judges moves; it rewrites engine facts into plain language.
- Persona changes talk only, never play, difficulty, or analysis.
- Works for any level: one skippable level question on first visit.
- Same simplicity as Cubicle: no login, no accounts, no setup wall, direct access to the board, only 5 pages.
- One complete v1: everything below ships together.

## 2. Stack
Python-first, one-click access. Python runs in the browser (Pyodide in a Web Worker), so there is no server for core logic and the PWA stays offline and free to host. JS/TS is only a thin shell for what a browser requires (rendering, engine WASM, speech).

**Python (Pyodide, in-browser) owns all logic:**
- `python-chess`: rules, PGN/FEN, move legality, SAN
- Move classification, accuracy, win-probability math
- Glicko-2 rating model, weakness tagging, difficulty model
- Spaced-repetition scheduler, puzzle selection, daily plan and challenge generation
- Stats and aggregation, game history, export/import
- Coach prompt building, persona templates, no-key template explanations
- Lesson engine (reads lesson JSON, checks answers)
- Python tests (pytest) run the same code natively and in CI

**JS/TS thin shell:**
- Vite, React 18, TypeScript (strict), plain CSS, hash routing (same as Cubicle). Pure rendering and event wiring.
- Board UI: `react-chessboard` (MIT) or custom SVG
- Stockfish WASM in a Web Worker (full-strength NNUE, GPL-3.0), driven by the Python layer through a small bridge
- Voice: Web Speech API (`speechSynthesis`), output only
- Storage adapter: Python data goes to IndexedDB (Dexie) through the bridge
- LLM: bring-your-own key, `fetch` calls orchestrated from Python (`pyodide.http`) or the shell
- PWA: service worker caches Pyodide, packages, Stockfish, and puzzle data after first load

**Human-like engine (Maia), quality-first:**
- Primary: Maia weights exported to ONNX and run with `onnxruntime-web` (same weights, same quality as Python/PyTorch).
- Fallback if size or speed is a problem: tiny stateless Python FastAPI endpoint (Hugging Face Space or Fly free tier) serving Maia-3 with PyTorch. Optional; the app works without it.

**Deploy:** Vercel or Cloudflare static hosting for the PWA. No servers needed unless the Maia fallback is enabled.

**Load cost:** first visit downloads about 10-15 MB for Pyodide plus python-chess, then it's cached for instant, offline opens.

## 3. Features

### Play
- Play vs Bobby (AI) at adaptive strength; choose side, colour, or random
- Local two-player on one screen (pass-and-play, board flips optional)
- Time controls (untimed, 5+0, 10+0, 15+10, custom), takebacks toggle, 3-level hints (nudge, piece, move)
- Legal-move highlights, last-move and check highlights, premove off by default
- Resign, draw offer vs bot, autosave and resume
- PGN/FEN import and export, copy position
- Sounds, board themes, piece sets, coordinates toggle

### Learn from scratch
- Interactive course on the board: piece moves, special moves, check/mate, basic mates, tactics (fork, pin, skewer, discovered, double check, back rank), openings principles, endgames
- Lessons are original authored JSON (steps, target squares, quiz moves, coach text)
- Guided first games with live coach explanations
- Adaptive daily lesson path from weakness tags

### Coach
- Post-game review: eval graph, accuracy %, move classes (best, good, inaccuracy, mistake, blunder), key moments, "what you missed" with the engine line
- Ask-the-coach chat about any position (position FEN and engine lines passed as context)
- Explains Bobby's own moves on request
- Persona voice on all coach text; optional spoken output

### Personas (tone only)
- Harvey: confident, sharp, "I don't lose" energy
- Mike: quick-learning, precise, encouraging
- Patrick: charming, observant, theatrical
- Elon: first-principles, blunt, fast
- Custom coach: user types any tone description (own key, own input)
- Switch any time, even mid-game. Each persona has its own voice settings (rate, pitch, chosen system voice)

### Player model
- Rating estimate (Glicko-2, high uncertainty at start, fast calibration over first games)
- Accuracy and average centipawn loss trend, by phase (opening, middlegame, endgame)
- Weakness tags: tactic motifs missed, endgame types, opening lines, time trouble, hanging pieces
- Adaptive bot strength: target = estimated rating + user offset (-200 to +200)
- Strength is explained to the user ("Bobby is playing about X")

### Training
- Puzzles from your own mistakes (positions where you blundered) with spaced repetition (1, 3, 7, 30 days)
- Themed puzzle sets from a curated subset of the Lichess puzzle database (CC0), filtered by theme and rating
- Endgame trainer: set positions vs engine with win/draw goals
- Opening trainer and explorer: names via lichess-org/chess-openings (CC0), repertoire builder from your own games
- Tricks library: interactive examples per pattern
- Daily challenges and goals generated from weakness tags ("win a game using a fork"), streaks, achievements

### Analysis
- Analysis board: eval bar, top engine lines (multi-PV), opening name, move list with classes, free exploration
- Position difficulty ("hard for your level") if Maia-3 is usable

### Stats
- Rating curve, accuracy trend, blunders per game, opening win rates, phase breakdown, weakness heatmap, time spent
- Game history with filters

### App
- Command palette (Ctrl/Cmd+K), keyboard shortcuts, focus mode (no chat/eval during a game)
- Light and dark themes, responsive to phones
- Data export and import (single JSON), full reset
- Settings: persona, voice, API key and provider, board theme, strength offset, sounds, hints, takebacks

## 4. First run (no login, no setup wall)
The app opens straight on the board, ready to play. One small dismissible card on first visit asks a single question: "What's your level?" (Never played / Know the moves / Know basic strategy / Casual ~800-1200 / Club 1200+). Skipping defaults to "Know the moves". Level seeds the rating estimate and lesson path. Persona, voice, and API key are optional and live in Settings. No accounts, no email, no tutorial screens.

## 5. Screens (hash routes, 5 pages only, same feel as Cubicle)
- `#/` **Play** (home): the board, immediately. Toggle for "vs Bobby" or "two players". Side panel: eval/hints, move list, persona coach chat drawer, daily plan and streak strip.
- `#/learn`: course lessons (one page, lesson opens inline).
- `#/train`: tabs for Puzzles, Endgames, Openings, Tricks, Challenges.
- `#/stats`: rating, accuracy, weaknesses, game history.
- `#/review/:id`: post-game review and free analysis board (analysis is this page, no separate route).
Settings, persona picker, and data export/import are a dialog opened from the command palette (Ctrl/Cmd+K) or a gear icon, not pages.

## 6. Engine layer
Common interface `Engine { setStrength, bestMove, analyse(fen, multiPV, depth) }`.
- Engine interface is defined in Python; the TS bridge implements it over the Stockfish WASM worker and the Maia ONNX worker.
- `StockfishAdapter`: WASM worker. Strength via `UCI_LimitStrength` and `UCI_Elo` for its supported range, plus Skill Level, movetime, and depth caps below that range.
- `MaiaAdapter`: human-like moves for roughly 600 to 2600 (Maia-3) or 1100 to 1900 (Maia-1/2).
- Strategy: for low and mid ratings use Maia if it runs in-browser; otherwise Stockfish with multi-PV sampling plus calibrated error injection to imitate human mistakes. Stockfish always does analysis and review.
- Move classification from win-probability drop between best line and played move; thresholds configurable.
- Accuracy % computed Lichess-style from win-probability changes.

**Feasibility to verify first (day 0):** Maia-3 license, model size, and whether it runs in-browser (for example ONNX Runtime Web or lc0 WASM). Fallback is the Stockfish strategy above. The Engine interface keeps this swappable.

## 7. Coach / LLM layer
- Provider adapters: Anthropic, OpenAI, Google, OpenRouter, plus custom OpenAI-compatible URL. Verify CORS per provider at build time (Anthropic needs the direct-browser-access header).
- Key stored on device only, never sent anywhere except the chosen provider. UI warns it is stored locally.
- Prompt = persona style block + engine facts (FEN, move, eval before and after, best line, classification, weakness tags) + strict rule: "explain only these facts; do not evaluate moves yourself."
- Persona text is original style instruction; no quotes from any show or person.
- Without a key: templated explanations from engine facts.
- Rate and cost guard: explain only on request or at key moments; cache per position and persona.

## 8. Data model (Dexie stores)
`profile` (rating, RD, level, goals) | `games` (pgn, result, bot strength, date) | `analysis` (gameId, per-move eval, class) | `weakness` (tag, count, last seen) | `puzzleProgress` (id, due date, interval, ease) | `lessonProgress` | `challenges` | `achievements` | `settings` | `personas` (custom)

## 9. Design (inherit Cubicle)
- Reuse Cubicle's tokens, fonts (Bricolage Grotesque, Instrument Sans, bundled locally), light and dark themes, quiet layout, command palette, keyboard shortcuts, PWA setup. Read tokens directly from `Cubicle/site/src` styles at build time instead of guessing.
- Board-first screens; calm, low-noise UI; no pop-ups during play (focus mode default on in games).
- Persona gets a small avatar glyph and accent only, not a themed re-skin.

## 10. Repo structure
```
bobby/
  docs/PLAN.md
  site/
    public/ (stockfish wasm, puzzles.json subset, openings.json, lessons/)
    py/ (Python core, runs in Pyodide and natively for tests)
      bobby/
        rules.py, classify.py, accuracy.py, glicko.py, weakness.py, difficulty.py
        srs.py, puzzles.py, challenges.py, stats.py, lessons.py, export.py
        coach/ (prompts.py, personas.py, templates.py, providers.py)
      tests/ (pytest)
    src/ (thin TS shell)
      bridge/ (pyodide worker, stockfish worker, maia-onnx worker, storage)
      tts.ts
      pages/ (play, review, learn, train, stats) + dialogs/ (settings, level-card)
      components/ (board, evalbar, movelist, graph, palette)
      styles/
  scripts/ (build puzzle subset from Lichess CC0 dump, build opening index)
  LICENSE (GPL-3.0), README.md
```

## 11. Licensing and content
- Repo GPL-3.0. Keep third-party notices (Stockfish GPL-3.0, chess.js BSD-2, react-chessboard MIT, Maia per its license).
- Lichess puzzle DB and openings are CC0; credit them anyway.
- No Lichess or chess.com branding or assets. No Bobby Fischer photo, likeness, or quotes.
- No named TV or real-person personas.

## 12. Acceptance checklist
- Full game vs Bobby at 3 different strengths; bot visibly weaker or stronger
- Review shows accurate classes on a known blunder test PGN
- Rating estimate moves sensibly over 10 test games; difficulty follows it
- Puzzles from own mistakes appear on spaced schedule
- Persona swap changes wording only; same engine facts in every persona
- Works offline after first load; export then import restores everything
- Works with no API key (templates) and with a valid key
- Lighthouse PWA pass; usable on a phone

## 13. Data pipeline (offline Python scripts in `scripts/`, outputs shipped as small JSON)
No LLM training and no web scraping. Quality comes from large open datasets reduced offline into compact assets, plus engine verification.

| Source (license) | Use | Shipped asset |
|---|---|---|
| Lichess games database, monthly dumps (CC0) | Rating-band benchmarks: avg centipawn loss, blunder rate by phase, opening win/draw/loss by band, typical mistake types | `benchmarks.json`, `opening_stats.json` |
| Lichess puzzle database (CC0) | Themed puzzles with ratings and popularity | `puzzles.json` (~20-30k filtered by popularity, theme, rating spread) |
| Lichess evaluations database (CC0) | Ground-truth evals to validate classification and opening lines | validation only, not shipped |
| lichess-org/chess-openings (CC0) | Opening names and ECO | `openings.json` |
| Syzygy tablebases (free) | Perfect results for endgame trainer positions, generated via `python-chess` | `endgames.json` (positions plus known outcome) |
| Maia weights (per its license) | Human-like play, trained on Lichess data by its authors | `maia.onnx` |
| Public-domain classics (for example Capablanca, Chess Fundamentals, 1921; verify status per jurisdiction) and our own original text | Lesson and knowledge-card content | `lessons/`, `knowledge_cards.json` |

Pipeline rules:
- Stream and filter dumps (rated, standard, both players rated, per rating band), never ship raw dumps.
- Validate every shipped puzzle and endgame position with Stockfish at fixed depth (and tablebase where applicable); drop anything ambiguous.
- Benchmarks let the player model say "at your rating, players usually lose X; you lose Y". This is the main use of the big data.
- Knowledge cards (tactic definitions, opening ideas, endgame rules) are short original texts retrieved by tag and injected into coach prompts, so the LLM explains with vetted content instead of guessing.
- Explicitly excluded: scraped web pages, chess.com content, paid courses, copyrighted books or video transcripts. Not needed, legally risky, and noisy.
- Scripts are pure Python, reproducible, with a pinned dataset month and a README of how to regenerate.

## 14. Claude Code kickoff prompt
"Read docs/PLAN.md. Scaffold the Vite + React + TS app from the Cubicle design base, set up Dexie schema, Engine interface with Stockfish adapter, board and local two-player play first, then proceed through the plan. Keep replies short. Ask only when blocked."

## Scroll (added 2026-11-24 as Cubicle, renamed)

A chess video library at `#/scroll` (lazy-loaded page): a 19-section syllabus of the best chess videos on YouTube, built offline by `scripts/cubicle/` (sources, oEmbed check, gate, classify, score, diversity caps, export) into `data/cubicle/*.json` (format: `docs/cubicle-data.md`). Cubicle-style card grid with timeline-frame thumbnails (never the uploader's cover), the official nocookie embed, state in IndexedDB (Dexie v4 table `cubicle`) and in export/import. Practice links connect videos to Learn and Train; weakness tags pick videos for your mistakes.
