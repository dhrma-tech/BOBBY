# Bobby: Python <-> TypeScript contract

Python core lives in `py/bobby/`, entry module `bobby/api.py`. Runs in Pyodide (browser) and natively (pytest). Pure functions: JSON-serialisable dict/list/str/int/float/bool/None in and out. No file, network, or clock access (dates and "today" are passed in as ISO strings). Only dependency: `python-chess` (pure Python) plus stdlib. All state is passed in and returned; TS persists it in IndexedDB.

Ownership: `py/**` = Python agent. `site/**` = frontend agent. `scripts/**`, `data/**`, root docs = data/content agent. Do not edit files you do not own.

## Engine interface (TS owns, Python never calls engines)
- `analyse(fen, {depth, multipv}) -> {lines:[{pv:[uci], cp:int|null, mate:int|null}]}` (score from side-to-move view)
- `bestMove(fen, {targetElo, movetimeMs}) -> {uci}`
Evals passed to Python are always **white-perspective**: `{cp:int|null, mate:int|null}`.

## Python API (`bobby/api.py`)
Rules
- `new_game(fen=None) -> state`
- `apply_move(fen, uci) -> state`  (raises `ValueError` on illegal)
- `legal_moves(fen) -> [uci]`
- `parse_pgn(pgn) -> {headers, moves:[{uci,san,fen_before,fen_after}], result}` ; `to_pgn(headers, moves) -> str`
- `state = {fen, turn:"w"|"b", legal_moves:[uci], san:str|None, check:bool, over:bool, result:"1-0"|"0-1"|"1/2-1/2"|"*", reason:str|None}`

Analysis
- `classify_moves(moves, player_color) -> {moves:[{ply, class:"best"|"good"|"inaccuracy"|"mistake"|"blunder", winprob_loss:float, is_player:bool}], accuracy:{w:float,b:float}, acpl:{w:float,b:float}, key_moments:[ply]}`
  - input `moves:[{ply, uci, san, fen_before, eval_before:{cp,mate}, eval_after:{cp,mate}, best_uci, best_eval:{cp,mate}}]`
- `winprob(cp, mate) -> float` (0..1, white view)

Player model
- `new_profile(level, known_rating=None, today) -> profile`  (level: "never"|"moves"|"basic"|"casual"|"club")
- `update_rating(profile, game_result) -> profile`  (Glicko-2; game_result `{score:1|0.5|0, opp_rating:int, opp_rd:int, date}`)
- `bot_target_rating(profile, offset:int) -> int`
- `update_weakness(weakness, analyzed_game) -> weakness`  (tags: fork, pin, skewer, discovered, back_rank, hanging_piece, mate_threat, endgame_k_p, endgame_rook, opening_<eco>, time_trouble, etc.)
- `benchmarks_compare(profile, game_stats, benchmarks) -> [{metric, you, typical, note}]`

Training
- `puzzles_from_mistakes(analyzed_game) -> [puzzle]`  (`puzzle = {id, fen, solution:[uci], themes:[str], source:"mistake", rating:int}`)
- `select_puzzles(puzzles, profile, theme=None, n=10) -> [puzzle]`
- `srs_new_card(item_id, today) -> card` ; `srs_review(card, grade:0..3, today) -> card` ; `due_cards(cards, today) -> [card]`  (intervals about 1, 3, 7, 30 days, ease-adjusted)
- `daily_plan(profile, weakness, cards, today) -> {items:[{kind, ref, title, minutes}]}`
- `generate_challenges(weakness, profile, today) -> [{id, title, description, kind, target, progress:0, reward}]` ; `update_challenges(challenges, analyzed_game) -> challenges`
- `check_achievements(profile, stats, achievements) -> [new_achievement]`
- `lesson_check(lesson, step_index, answer) -> {correct:bool, feedback:str, next_index:int|None}`

Stats & data
- `stats_summary(games, analyses) -> {rating_curve, accuracy_trend, blunders_per_game, phase_breakdown, opening_results, weakness_heatmap}`
- `export_all(data) -> {version, data}` ; `import_all(blob) -> data` (validate schema/version, raise `ValueError`)

Coach
- `coach_prompt(persona, facts, mode) -> {system, user}`  (persona: id of builtin or `{custom:str}`; mode: "move_explain"|"review"|"chat"|"hint"; `facts` = engine facts dict: fen, move, class, evals, best line (SAN), weakness tags, knowledge cards)
- `template_explanation(facts, mode) -> str`  (no-LLM fallback)
- `personas() -> [{id, name, tagline, style, voice:{rate,pitch,preferGender}}]`  ids: `closer`, `prodigy`, `observer`, `visionary`
- Persona rule: changes tone only. The prompt must instruct the LLM to explain only the supplied facts and never evaluate moves itself. No real-person or TV-character names or quotes.

## Data schemas (`data/`, owned by data agent; consumed by Python and TS)
- `puzzles.json`: `[{id, fen, solution:[uci], themes:[str], rating:int, popularity:int}]` (fen = position before the opponent's setup move is already applied; solution starts with the solver's move)
- `openings.json`: `[{eco, name, pgn, epd}]`
- `opening_stats.json`: `{band:{"600-800":{epd:{n,w,d,l}}}}`
- `benchmarks.json`: `{band:{acpl:{opening,middle,end}, blunder_rate, mistake_rate, inaccuracy_rate, common_themes_missed:[str]}}`
- `endgames.json`: `[{id, name, fen, goal:"win"|"draw", dtz|null, hint}]`
- `knowledge_cards.json`: `[{id, tags:[str], title, text}]`
- `lessons/*.json`: `{id, title, section, order, steps:[{type:"info"|"move"|"square"|"quiz", fen, prompt, correct:[uci or square], options:[str]|null, explanation, hint}]}`
- Rating bands: 600-800, 800-1000, 1000-1200, 1200-1400, 1400-1600, 1600-1800, 1800-2000, 2000+.

## TS bridge (site/src/bridge)
Pyodide worker loads wheel `python_chess` + local `bobby` package, exposes `call(fnName, ...args) -> Promise<json>`. Engine workers expose the engine interface above. Storage adapter persists profile, games, analysis, weakness, puzzleProgress (cards), lessonProgress, challenges, achievements, settings in Dexie.
