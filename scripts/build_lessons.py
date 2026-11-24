"""Build the extended Learn course: writes data/lessons/<id>.json and renumbers every lesson's `order`.

Every exercise is checked while it is built (python-chess only, no engine needed):
  move(..., mode="exact")  answers must be legal (used for "play a good developing move" style steps)
  move(..., mode="mates")  answers = every legal move that gives checkmate; the intended move must be one of them
  move(..., mode="best")   a small material search (with mate detection) must rate the intended move best;
                           all equally-best moves are accepted, and the step fails if more than MAX_BEST tie
  move(..., mode="legal")  every legal move is accepted (e.g. "get out of check")
Run:  python scripts/build_lessons.py   then   python scripts/validate_data.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "lessons"
VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
MATE = 10_000
MAX_BEST = 3

SECTIONS = ["Basics", "Special moves", "Check and mate", "Basic mates", "Mating patterns", "Tactics",
            "Openings", "Strategy", "Endgames", "Good habits"]

# Final course order (existing lessons + new ones). Ids not listed keep their relative order at the section end.
COURSE = {
    "Basics": ["board-setup", "board-coordinates", "rook-moves", "bishop-moves", "queen-moves", "knight-moves",
               "king-moves", "pawn-moves", "notation", "piece-values", "captures-and-trades"],
    "Special moves": ["castling", "en-passant", "promotion"],
    "Check and mate": ["check", "escape-check", "checkmate", "stalemate", "draws"],
    "Basic mates": ["mate-king-queen", "queen-mate-patterns", "mate-king-rook", "ladder-mate"],
    "Mating patterns": ["fools-mate", "scholars-mate", "smothered-mate", "arabian-mate", "mate-in-one-drill"],
    "Tactics": ["hanging-pieces", "counting-exchanges", "fork", "pin", "skewer", "discovered-attack", "double-check",
                "back-rank-mate", "removing-defender", "tactics-mixed"],
    "Openings": ["opening-center", "opening-develop", "opening-castle", "opening-early-queen", "scholars-mate-defend",
                 "opening-principles-review", "famous-openings"],
    "Strategy": ["make-a-plan", "piece-activity", "open-files", "pawn-structure", "king-safety", "trade-when-ahead"],
    "Endgames": ["endgame-king-and-pawn", "opposition", "endgame-rule-of-square", "king-activity", "rook-behind-passer",
                 "endgame-rook-bridge", "philidor-defence"],
    "Good habits": ["checks-captures-threats", "blunder-check", "dont-stalemate", "think-like-opponent",
                    "time-management", "practice-routine"],
}

errors: list[str] = []


# ---------- verification ----------
def _material(b: chess.Board) -> int:
    s = 0
    for p in b.piece_map().values():
        s += VAL[p.piece_type] if p.color == b.turn else -VAL[p.piece_type]
    return s


def _search(b: chess.Board, depth: int, alpha: int, beta: int, ply: int) -> int:
    if b.is_checkmate():
        return -MATE + ply
    if b.is_stalemate() or b.is_insufficient_material():
        return 0
    stand = _material(b)
    if depth <= 0:  # quiescence: captures only
        if stand >= beta:
            return stand
        alpha = max(alpha, stand)
        moves = [m for m in b.legal_moves if b.is_capture(m)]
        if ply > 10:
            return stand
    else:
        moves = list(b.legal_moves)
    moves.sort(key=lambda m: (not b.is_capture(m), not b.gives_check(m)))
    best = stand if depth <= 0 else -MATE * 2
    for m in moves:
        b.push(m)
        sc = -_search(b, depth - 1, -beta, -alpha, ply + 1)
        b.pop()
        if sc > best:
            best = sc
        alpha = max(alpha, sc)
        if alpha >= beta:
            break
    return best


def best_moves(fen: str, depth: int = 3) -> tuple[list[str], dict[str, int]]:
    b = chess.Board(fen)
    scores = {}
    for m in b.legal_moves:
        b.push(m)
        scores[m.uci()] = -_search(b, depth, -MATE * 2, MATE * 2, 1)
        b.pop()
    top = max(scores.values())
    return sorted(u for u, s in scores.items() if s == top), scores


def mates(fen: str) -> list[str]:
    b = chess.Board(fen)
    out = []
    for m in b.legal_moves:
        b.push(m)
        if b.is_checkmate():
            out.append(m.uci())
        b.pop()
    return sorted(out)


def board_ok(fen: str, where: str) -> chess.Board | None:
    try:
        b = chess.Board(fen)
    except ValueError as e:
        errors.append(f"{where}: bad FEN {fen}: {e}")
        return None
    if b.status() != chess.STATUS_VALID:
        errors.append(f"{where}: invalid position {fen}: {b.status()!r}")
        return None
    return b


def to_uci(b: chess.Board, mv: str) -> str:
    try:
        m = chess.Move.from_uci(mv)
        if m in b.legal_moves:
            return mv
    except ValueError:
        pass
    return b.parse_san(mv).uci()


# ---------- step builders ----------
_cur = {"id": "?", "n": 0}


def _where() -> str:
    _cur["n"] += 1
    return f"{_cur['id']} step {_cur['n']}"


def info(fen: str, text: str) -> dict:
    board_ok(fen, _where())
    return {"type": "info", "fen": fen, "prompt": text, "correct": [], "options": None, "explanation": text,
            "hint": "Read, then continue."}


def move(fen: str, prompt: str, answer, explanation: str, hint: str, mode: str = "exact", depth: int = 3) -> dict:
    w = _where()
    b = board_ok(fen, w)
    answers = [answer] if isinstance(answer, str) else list(answer)
    correct: list[str] = []
    if b is not None:
        try:
            ucis = [to_uci(b, a) for a in answers]
        except ValueError as e:
            errors.append(f"{w}: illegal answer {answers} in {fen}: {e}")
            ucis = []
        if mode == "exact":
            correct = ucis
        elif mode == "legal":
            correct = sorted(m.uci() for m in b.legal_moves)
        elif mode == "mates":
            correct = mates(fen)
            for u in ucis:
                if u not in correct:
                    errors.append(f"{w}: {u} is not mate in {fen} (mates: {correct})")
        elif mode == "best":
            correct, scores = best_moves(fen, depth)
            for u in ucis:
                if u not in correct:
                    top = sorted(scores.items(), key=lambda kv: -kv[1])[:4]
                    errors.append(f"{w}: {u} is not best in {fen}; top {top}")
            if len(correct) > MAX_BEST:
                errors.append(f"{w}: {len(correct)} moves tie for best in {fen}: {correct}")
        else:
            raise ValueError(mode)
        if not correct:
            errors.append(f"{w}: no correct moves")
    return {"type": "move", "fen": fen, "prompt": prompt, "correct": correct, "options": None,
            "explanation": explanation, "hint": hint}


def square(fen: str, prompt: str, squares, explanation: str, hint: str) -> dict:
    w = _where()
    board_ok(fen, w)
    sq = [squares] if isinstance(squares, str) else list(squares)
    for s in sq:
        if s not in chess.SQUARE_NAMES:
            errors.append(f"{w}: bad square {s}")
    return {"type": "square", "fen": fen, "prompt": prompt, "correct": sq, "options": None,
            "explanation": explanation, "hint": hint}


def quiz(fen: str, prompt: str, options: list[str], correct, explanation: str, hint: str) -> dict:
    w = _where()
    board_ok(fen, w)
    c = [correct] if isinstance(correct, str) else list(correct)
    if not set(c) <= set(options) or len(set(options)) != len(options):
        errors.append(f"{w}: quiz answer not in options")
    return {"type": "quiz", "fen": fen, "prompt": prompt, "correct": c, "options": options,
            "explanation": explanation, "hint": hint}


LESSONS: dict[str, dict] = {}


def lesson(lid: str, title: str, section: str, steps_fn) -> None:
    _cur["id"], _cur["n"] = lid, 0
    steps = steps_fn()
    if not 4 <= len(steps) <= 8:
        errors.append(f"{lid}: {len(steps)} steps (need 4-8)")
    LESSONS[lid] = {"id": lid, "title": title, "section": section, "order": 0, "steps": steps}


START = chess.STARTING_FEN
E4E5 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
E4E5NF3NC6 = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"

# =====================================================================================================
# Basics
# =====================================================================================================
lesson("board-coordinates", "Squares and coordinates", "Basics", lambda: [
    info(START, "Every square has a name. The letter is the column (called a file, a to h, left to right for White). "
                "The number is the row (called a rank, 1 to 8, starting from White's side)."),
    square(START, "Click the square e4.", "e4", "e4: the e-file, 4th rank. It is one of the four centre squares.",
           "Find the e-file first, then count up to the 4th row."),
    square(START, "Click the square d5.", "d5", "d5 is another centre square. The centre is d4, e4, d5 and e5.",
           "d is the file just left of e. Then go up to rank 5."),
    square(START, "Where does the white king start? Click its square.", "e1",
           "The white king starts on e1, the black king on e8.", "The king stands on the e-file, on White's back rank."),
    quiz(START, "Which square does the white queen start on?", ["d1", "e1", "d8"], "d1",
         "The queen starts on her own colour: the white queen on the light square d1.",
         "Queen on her colour: white queen, light square."),
    square(START, "Click the corner square h8.", "h8", "h8 is Black's right-hand corner, where a black rook starts.",
           "The top-right corner from White's side."),
])

lesson("notation", "Reading chess moves", "Basics", lambda: [
    info(START, "Moves are written as piece letter + target square. K = king, Q = queen, R = rook, B = bishop, "
                "N = knight. Pawns have no letter: e4 means a pawn moves to e4."),
    move(START, "Play e4.", "e2e4", "e4: the pawn in front of the king moves two squares.",
         "Move the e-pawn to the e4 square."),
    move(E4E5, "Black answered e5. Now play Nf3.", "g1f3", "Nf3: the knight from g1 jumps to f3 and attacks e5.",
         "N is the knight. Which knight can reach f3?"),
    info(E4E5NF3NC6, "More symbols: x means a capture (Nxe5 = knight takes on e5), + is check, # is checkmate, "
                     "O-O is castling short (kingside) and O-O-O is castling long (queenside)."),
    quiz(E4E5NF3NC6, "What does Bxf7+ mean?",
         ["A bishop takes on f7 with check", "A bishop moves to f7 and wins", "A pawn takes on f7"],
         "A bishop takes on f7 with check", "B = bishop, x = takes, + = check.", "Read it letter by letter."),
    move(E4E5NF3NC6, "Play Bc4.", "f1c4", "Bc4: the light-squared bishop develops and aims at f7.",
         "The bishop on f1 moves along the diagonal to c4."),
])

lesson("captures-and-trades", "Captures and trades", "Basics", lambda: [
    info("4k3/8/8/3q4/8/8/3R4/4K3 w - - 0 1",
         "To capture, move your piece onto an enemy piece. It is removed from the board. Pieces that nobody "
         "protects can be taken for free."),
    move("4k3/8/8/3q4/8/8/3R4/4K3 w - - 0 1", "The black queen is unprotected. Win it.", "d2d5",
         "Rxd5: you win a queen (9 points) for nothing.", "Your rook moves straight up the d-file.", mode="best"),
    quiz("4k3/8/8/8/8/8/8/4K3 w - - 0 1", "Your knight takes a pawn, then a pawn takes your knight. What happened?",
         ["You lost 2 points", "You won 2 points", "It was an even trade"], "You lost 2 points",
         "You gave a knight (3) for a pawn (1). Always check if the piece you take is protected.",
         "Compare 3 with 1."),
    move("4k3/4p3/3n4/8/3R2b1/8/8/4K3 w - - 0 1",
         "Your rook can take the knight or the bishop. Pick the capture that really wins material.", "d4g4",
         "Rxg4 wins a free bishop. Rxd6 would lose the rook to exd6: 5 for 3.",
         "Which piece has no defender? The pawn on e7 protects d6.", mode="best"),
    info("4k3/8/8/8/8/8/8/4K3 w - - 0 1",
         "A trade is when both sides take pieces of the same value, like knight for knight. Trades are good when "
         "you are ahead in material, and to swap off the opponent's best piece."),
])

# =====================================================================================================
# Check and mate
# =====================================================================================================
lesson("escape-check", "Three ways out of check", "Check and mate", lambda: [
    info("4r1k1/8/8/8/8/8/4q3/3BK3 w - - 0 1",
         "When you are in check you must get out of it at once. There are only three ways: capture the checking "
         "piece, block the check, or move the king."),
    move("4r1k1/8/8/8/8/8/4q3/3BK3 w - - 0 1", "The queen checks your king and the king cannot take it. Capture it.",
         "d1e2", "Bxe2: capturing the checking piece is often the best way out.",
         "Your bishop on d1 touches e2 diagonally."),
    move("4k3/8/8/8/4r3/8/3B4/4K3 w - - 0 1", "The rook checks along the e-file. Block it with your bishop.",
         "d2e3", "Be3 puts a piece between the rook and your king.", "Put the bishop on the e-file between them."),
    move("4k3/8/8/8/8/8/8/r3K3 w - - 0 1", "You cannot capture or block this check. Move your king to safety.",
         "e1e2", "Any king move off the first rank escapes the rook.", "Step up off the 1st rank.", mode="legal"),
    quiz("4k3/8/8/8/8/3n4/8/4K3 w - - 0 1", "A knight gives check. Can you block a knight check?", ["Yes", "No"],
         "No", "Knights jump, so their checks cannot be blocked. Capture the knight or move the king.",
         "Is there any square between a knight and its target?"),
])

lesson("draws", "How games end in a draw", "Check and mate", lambda: [
    info("8/8/4k3/8/8/3BK3/8/8 w - - 0 1",
         "A game is drawn by stalemate, by agreement, by the same position three times (threefold repetition), "
         "after 50 moves each with no capture or pawn move, or when no one has enough pieces left to checkmate."),
    quiz("8/8/4k3/8/8/3BK3/8/8 w - - 0 1", "King and bishop against a lone king. Can White checkmate?", ["Yes", "No"],
         "No", "A single bishop (or a single knight) cannot force checkmate: the game is a draw.",
         "Try to picture a mate with only one bishop."),
    quiz("8/8/4k3/8/8/4K3/8/3R4 w - - 0 1", "King and rook against a lone king. Can White checkmate?", ["Yes", "No"],
         "Yes", "King and rook (or queen) always win against a lone king. You will learn how in Basic mates.",
         "Rooks are strong enough."),
    quiz("8/8/4k3/8/8/4K3/8/3NN3 w - - 0 1", "Two knights against a lone king. Can White force checkmate?",
         ["Yes", "No"], "No", "Surprisingly, two knights cannot force mate if the defender plays well.",
         "This is one of chess's famous exceptions."),
    quiz("8/8/4k3/8/8/4K3/8/8 w - - 0 1", "What is threefold repetition?",
         ["The same position appears three times", "The same piece moves three times", "Three checks in a row"],
         "The same position appears three times",
         "If the same position happens three times, either player can claim a draw. When you are losing, a "
         "never-ending series of checks (perpetual check) can save the game this way.", "It is about positions."),
])

# =====================================================================================================
# Basic mates
# =====================================================================================================
lesson("queen-mate-patterns", "Queen mates: the final blow", "Basic mates", lambda: [
    info("k7/8/1K6/8/8/8/8/6Q1 w - - 0 1",
         "To mate with a queen, drive the enemy king to the edge. Then your king comes close and the queen "
         "delivers the last check, with your king guarding the escape squares."),
    move("k7/8/1K6/8/8/8/8/6Q1 w - - 0 1", "Checkmate in one move.", "g1g8",
         "Qg8#: the queen covers the 8th rank and your king covers a7 and b7.", "Use the open g-file to reach the back rank.",
         mode="mates"),
    move("7k/8/6K1/8/8/8/8/1Q6 w - - 0 1", "Checkmate in one move.", "b1b8",
         "Qb8#: the queen takes the 8th rank, your king covers g7 and h7.", "The 8th rank again.", mode="mates"),
    move("3k4/8/3K4/8/8/8/8/7Q w - - 0 1", "Checkmate in one move.", "h1h8",
         "Qh8#: a check along the back rank while your king covers c7, d7 and e7.",
         "Your king already guards the 7th rank.", mode="mates"),
    quiz("k7/8/1Q6/8/8/8/8/K7 b - - 0 1", "It is Black to move. What is this position?",
         ["Stalemate", "Checkmate", "Check"], "Stalemate",
         "Black is not in check but has no legal move: stalemate, a draw. Always leave the king a square until "
         "you can give mate.", "Is the black king attacked right now?"),
])

lesson("ladder-mate", "The ladder mate with two rooks", "Basic mates", lambda: [
    info("8/8/8/4k3/8/8/R7/1R4K1 w - - 0 1",
         "Two rooks mate easily without help from the king. One rook cuts off a row, the other gives check from "
         "the next row. Step by step, like climbing a ladder, the king is pushed to the edge."),
    move("8/8/8/4k3/8/8/R7/1R4K1 w - - 0 1", "Cut the king off: put a rook on the 4th rank.", ["b1b4", "a2a4"],
         "The king is now stuck on ranks 5 to 8.", "Move a rook to the row just below the king."),
    move("8/8/8/4k3/1R6/8/R7/6K1 w - - 0 1", "Now check from the 5th rank to push the king up.", "a2a5",
         "Ra5+ forces the king to the 6th rank. Keep alternating the rooks.", "The other rook gives the check."),
    move("6k1/R7/8/8/8/8/8/1R4K1 w - - 0 1", "Finish it: checkmate in one.", "b1b8",
         "Rb8#: one rook holds the 7th rank, the other checks on the 8th.", "Check on the back rank.",
         mode="mates"),
    quiz("8/8/8/4k3/8/8/R7/1R4K1 w - - 0 1", "Why do we keep the rooks far away from the enemy king?",
         ["So the king cannot attack them", "So they look nicer", "Because rooks cannot move close"],
         "So the king cannot attack them",
         "If the king gets next to an unprotected rook it can take it. Keep the rooks at a distance.",
         "What can a king capture?"),
])

# =====================================================================================================
# Mating patterns
# =====================================================================================================
FOOL = "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq g3 0 2"
SCHOLAR_MATE = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"

lesson("fools-mate", "Fool's mate: the fastest mate", "Mating patterns", lambda: [
    info(FOOL, "Fool's mate is the shortest possible game. White pushed the f- and g-pawns and opened the line "
               "from h4 to the king. Never weaken the squares around your king early."),
    move(FOOL, "Black to move: checkmate in one.", "d8h4", "Qh4#: the king is trapped by its own pieces.",
         "The diagonal from d8 to h4 to e1 is open.", mode="mates"),
    quiz(START, "Which early pawn moves weaken White's king the most?",
         ["f3 and g4", "e4 and d4", "c4 and Nc3"], "f3 and g4",
         "The f- and g-pawns shield the king. Moving them early opens lines toward it.",
         "Look at the pawns next to the king."),
    quiz(START, "What is the main lesson of Fool's mate?",
         ["Develop pieces and keep the king safe", "Always attack with the queen", "Push all your pawns"],
         "Develop pieces and keep the king safe", "Good openings develop knights and bishops and protect the king.",
         "What went wrong for White?"),
])

lesson("scholars-mate", "Scholar's mate: the f7 attack", "Mating patterns", lambda: [
    info(SCHOLAR_MATE, "The f7 pawn is protected only by the black king at the start. A queen and bishop "
                       "attacking it together can give a quick mate. Here Black forgot to defend."),
    move(SCHOLAR_MATE, "Checkmate in one.", "h5f7", "Qxf7#: the bishop on c4 protects the queen.",
         "Take on f7 with the queen.", mode="mates"),
    square(SCHOLAR_MATE, "Click the weak square that White attacks twice.", "f7",
           "f7 (f2 for White) is the weakest square early in the game.", "It is next to the black king."),
    quiz(SCHOLAR_MATE, "Which white piece protects the queen when it lands on f7?", ["Bishop on c4", "Knight", "King"],
         "Bishop on c4", "The bishop on c4 looks straight at f7.", "Follow the diagonal from c4."),
])

lesson("smothered-mate", "Smothered mate", "Mating patterns", lambda: [
    info("6rk/6pp/8/6N1/8/8/8/6K1 w - - 0 1",
         "A smothered mate happens when the king is surrounded by its own pieces and a knight gives check. "
         "The king has nowhere to go and a knight check cannot be blocked."),
    move("6rk/6pp/8/6N1/8/8/8/6K1 w - - 0 1", "Checkmate in one with the knight.", "g5f7",
         "Nf7#: the rook and pawns block every escape square.", "Which square lets the knight check h8?",
         mode="mates"),
    move("kr6/pp6/8/1N6/8/8/8/K7 w - - 0 1", "The same idea in the other corner. Checkmate in one.", "b5c7",
         "Nc7#: smothered again.", "Find the knight check on a8.", mode="mates"),
    quiz("6rk/6pp/8/6N1/8/8/8/6K1 w - - 0 1", "Which piece usually delivers a smothered mate?",
         ["Knight", "Bishop", "Rook"], "Knight", "Only a knight can check a king that is fully surrounded.",
         "It is the piece that jumps."),
])

lesson("arabian-mate", "Rook and knight: the Arabian mate", "Mating patterns", lambda: [
    info("7k/1R6/5N2/8/8/8/8/6K1 w - - 0 1",
         "In the Arabian mate a rook checks next to the king in the corner and a knight protects the rook and "
         "covers the last escape square."),
    move("7k/1R6/5N2/8/8/8/8/6K1 w - - 0 1", "Checkmate in one.", "b7h7",
         "Rh7#: the knight on f6 protects the rook and covers g8.", "Slide the rook along the 7th rank.",
         mode="mates"),
    square("7k/7R/5N2/8/8/8/8/6K1 b - - 0 1", "Which escape square does the knight cover?", "g8",
           "The knight on f6 controls g8 and h7.", "Squares next to the black king."),
    quiz("7k/7R/5N2/8/8/8/8/6K1 b - - 0 1", "Why can't the king take the rook on h7?",
         ["The knight protects it", "Kings cannot capture", "It is not Black's move"], "The knight protects it",
         "A king can never capture a protected piece.", "Who guards h7?"),
])

lesson("mate-in-one-drill", "Mate in one: practice", "Mating patterns", lambda: [
    move("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", "Checkmate in one.", "a1a8", "Ra8#: a back-rank mate.",
         "The black king is trapped behind its pawns.", mode="mates"),
    move("rnbqkbnr/ppppp2p/8/5pp1/4P3/8/PPPP1PPP/RNBQKBNR w KQkq g6 0 3", "Checkmate in one.", "d1h5",
         "Qh5#: the same trap as Fool's mate, with colours reversed.", "The e8-h5 diagonal is open.",
         mode="mates"),
    move("6k1/5p1p/6pB/8/8/8/8/3R2K1 w - - 0 1", "Checkmate in one.", "d1d8",
         "Rd8#: the bishop on h6 covers g7.", "Use the open d-file.", mode="mates"),
    move("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1", "Checkmate in one.", "f7g7",
         "Qg7#: the queen is protected by your king.", "Put the queen right next to the king, protected.",
         mode="mates"),
    move("k7/8/2K5/8/8/8/8/1Q6 w - - 0 1", "Checkmate in one, and be careful not to stalemate.", "b1b7",
         "Qb7#. Qb6 would be stalemate: always check that you are giving check.", "The king on c6 protects b7.",
         mode="mates"),
])

# =====================================================================================================
# Tactics
# =====================================================================================================
lesson("counting-exchanges", "Counting attackers and defenders", "Tactics", lambda: [
    info("4k3/8/4p3/3n4/2P5/8/8/4K3 w - - 0 1",
         "Before you capture, count. How many of your pieces attack the target, and how many defend it? "
         "And start with your cheapest attacker."),
    move("4k3/8/4p3/3n4/2P5/8/8/4K3 w - - 0 1", "The knight is defended by a pawn. Win material anyway.",
         "c4d5", "cxd5: even if exd5 follows, you traded a pawn (1) for a knight (3).",
         "Capture with your cheapest piece.", mode="best"),
    quiz("4k3/8/4p3/3p4/8/1BN5/8/4K3 w - - 0 1",
         "Your knight and bishop attack d5, Black defends it once. Is Nxd5 a good idea?",
         ["No: after Nxd5 exd5 Bxd5 you gave a knight for two pawns", "Yes: two attackers beat one defender"],
         "No: after Nxd5 exd5 Bxd5 you gave a knight for two pawns",
         "Counting is not enough: the values matter too. A knight is worth more than two pawns.",
         "Add up what you give and what you get."),
    quiz("4k3/8/8/8/8/8/8/4K3 w - - 0 1", "Which piece should usually capture first in an exchange?",
         ["The cheapest attacker", "The queen", "The king"], "The cheapest attacker",
         "Lead with the least valuable piece so a recapture costs you as little as possible.",
         "Think about what happens if it is taken back."),
])

lesson("removing-defender", "Remove the defender", "Tactics", lambda: [
    info("6k1/8/2b5/8/3n4/4P3/8/2R3K1 w - - 0 1",
         "If a piece is only protected by one defender, capture or chase away that defender. Then the piece "
         "falls."),
    move("6k1/8/2b5/8/3n4/4P3/8/2R3K1 w - - 0 1", "The knight on d4 defends the bishop on c6. Remove it.",
         "e3d4", "exd4 wins the knight, and now the bishop on c6 is attacked by your rook too.",
         "Your pawn can capture the defender.", mode="best"),
    move("6k1/8/2b5/8/3P4/8/8/2R3K1 w - - 0 1", "Now the bishop has no defender. Take it.", "c1c6",
         "Rxc6: with its defender gone, the bishop was free.", "The rook goes straight up the c-file.",
         mode="best"),
    quiz("6k1/8/2b5/8/3n4/4P3/8/2R3K1 w - - 0 1", "What is the idea of this tactic?",
         ["Take away the piece that guards a target", "Trade queens", "Push a passed pawn"],
         "Take away the piece that guards a target", "Find the guard, remove it, then win what it guarded.",
         "Think about the job of the knight."),
])

lesson("tactics-mixed", "Tactics practice", "Tactics", lambda: [
    move("4k3/8/8/1q6/4N3/8/8/4K3 w - - 0 1", "Win the queen.", "e4d6",
         "Nd6+ is a fork: it checks the king and attacks the queen.", "Find a knight check that also hits b5.",
         mode="best"),
    move("4k3/4p3/3n4/8/3R2b1/8/8/4K3 w - - 0 1", "Win material.", "d4g4",
         "Rxg4: the bishop had no defender. Taking the knight would lose your rook to exd6.",
         "Which black piece is not protected?", mode="best"),
    move("6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1", "Find the fastest win.", "e1e8",
         "Re8# is checkmate on the back rank.", "Look for checks first.", mode="mates"),
    move("6k1/8/2b5/8/3n4/4P3/8/2R3K1 w - - 0 1", "Win a piece.", "e3d4",
         "exd4: removing the defender of c6 wins material.", "Capture the guard.", mode="best"),
    quiz("4k3/8/8/1q6/4N3/8/8/4K3 w - - 0 1", "In what order should you look for tactics?",
         ["Checks, captures, threats", "Pawn moves first", "Queen moves only"], "Checks, captures, threats",
         "Forcing moves come first: they limit what your opponent can do.", "Start with the most forcing moves."),
])

# =====================================================================================================
# Openings
# =====================================================================================================
SCHOLAR_THREAT = "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3"
SCHOLAR_QF3 = "r1bqkbnr/pppp1p1p/2n3p1/4p3/2B1P3/5Q2/PPPP1PPP/RNB1K1NR b KQkq - 1 4"
ITALIAN = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"
RUY = "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"
SICILIAN = "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2"
QGAMBIT = "rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR b KQkq c3 0 2"
AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"

lesson("scholars-mate-defend", "How to stop Scholar's mate", "Openings", lambda: [
    info(SCHOLAR_THREAT, "White's queen and bishop both aim at f7 and threaten Qxf7#. Beginners lose this way "
                         "all the time. Learn the calm defences."),
    move(SCHOLAR_THREAT, "Defend against Qxf7#.", ["g7g6", "d8e7", "d8f6"],
         "g6 blocks the queen and attacks it. Qe7 or Qf6 also guard f7.",
         "Block the queen's path, or protect f7 with your queen."),
    move(SCHOLAR_QF3, "White tries again with Qf3, aiming at f7. Defend and develop at the same time.",
         ["g8f6", "d8f6", "d8e7"], "Nf6 blocks the queen and develops a piece: the best answer.",
         "A knight on f6 blocks the f-file."),
    quiz(SCHOLAR_QF3, "Why is bringing the queen out early often bad for White?",
         ["It can be chased with tempo by developing moves", "Queens cannot move early", "It is against the rules"],
         "It can be chased with tempo by developing moves",
         "Black develops with threats against the queen and gets ahead in development.",
         "What happens when you attack the queen with a knight?"),
])

lesson("opening-principles-review", "Opening principles: review", "Openings", lambda: [
    info(E4E5NF3NC6, "The opening golden rules: control the centre, develop knights and bishops, castle early, "
                     "connect your rooks, and don't move the same piece twice without a reason."),
    move(E4E5NF3NC6, "Make a good opening move: develop a piece or fight for the centre.",
         ["f1c4", "f1b5", "b1c3", "d2d4"], "Good! Bc4, Bb5, Nc3 and d4 all follow the principles.",
         "Develop a bishop or knight, or play d4."),
    quiz(E4E5NF3NC6, "Which move breaks the opening principles?", ["h4", "Bc4", "Nc3"], "h4",
         "h4 does nothing for the centre or development, and weakens the king's side.",
         "Which move doesn't develop or fight for the centre?"),
    quiz(E4E5NF3NC6, "Which pieces should you usually develop first?", ["Knights and bishops", "Queen and rooks", "King"],
         "Knights and bishops", "Minor pieces come out first; rooks and queen join later.",
         "The minor pieces."),
    quiz(E4E5NF3NC6, "When are your rooks 'connected'?",
         ["When no pieces stand between them on the back rank", "When they are on the same file",
          "When they protect the king"], "When no pieces stand between them on the back rank",
         "After you develop your minor pieces, castle and move the queen, the rooks can see each other.",
         "Look at the back rank."),
])

lesson("famous-openings", "Famous openings", "Openings", lambda: [
    quiz(ITALIAN, "1.e4 e5 2.Nf3 Nc6 3.Bc4. Which opening is this?", ["Italian Game", "Ruy Lopez", "Sicilian Defence"],
         "Italian Game", "The Italian Game: the bishop goes to c4 and aims at f7.", "Bishop on c4."),
    quiz(RUY, "1.e4 e5 2.Nf3 Nc6 3.Bb5. Which opening is this?", ["Ruy Lopez", "Italian Game", "French Defence"],
         "Ruy Lopez", "The Ruy Lopez (Spanish Game) puts pressure on the knight that defends e5.",
         "Bishop on b5."),
    move(AFTER_E4, "Play the Sicilian Defence: answer e4 with the c-pawn.", "c7c5",
         "1...c5 is the Sicilian, the most popular reply to e4 at master level.", "Move the c-pawn two squares."),
    quiz(SICILIAN, "Why does Black play ...c5 in the Sicilian?",
         ["To fight for d4 from the side", "To attack the king", "To free the queen"], "To fight for d4 from the side",
         "c5 controls d4 without copying White's moves, leading to unbalanced games.", "Which centre square does c5 hit?"),
    quiz(QGAMBIT, "1.d4 d5 2.c4. Which opening is this?", ["Queen's Gambit", "London System", "King's Gambit"],
         "Queen's Gambit", "In the Queen's Gambit White offers the c-pawn to pull Black's d-pawn from the centre.",
         "Pawn sacrifice on the queen's side."),
    info(START, "Don't memorise long lines yet. Know the ideas of one opening with White and one answer each to "
                "1.e4 and 1.d4, and follow the principles when your opponent leaves the book."),
])

# =====================================================================================================
# Strategy
# =====================================================================================================
lesson("make-a-plan", "Making a plan", "Strategy", lambda: [
    info(E4E5NF3NC6, "When there are no tactics, make a plan. Ask: what is my worst piece? Where are the weak "
                     "squares? Which side of the board should I play on?"),
    quiz(E4E5NF3NC6, "Which question is the best start for a plan?", ["What is my worst piece?",
         "How can I move my queen?", "Which pawn can I push fastest?"], "What is my worst piece?",
         "Improving your worst piece is a simple, strong plan.", "Think about piece activity."),
    quiz(E4E5NF3NC6, "Your pieces are better on the kingside. Where should you usually play?",
         ["On the kingside", "On the queenside", "It doesn't matter"], "On the kingside",
         "Play where you are stronger: that is where attacks succeed.", "Use your strength."),
    info(E4E5NF3NC6, "A good plan is small and concrete: 'bring my knight to d5', 'double rooks on the open file', "
                     "'attack the weak pawn on c6'. Then check each move for tactics before you play it."),
])

lesson("piece-activity", "Active pieces", "Strategy", lambda: [
    info("4k3/8/8/8/8/N7/8/4K3 w - - 0 1", "Pieces are stronger in the centre where they control more squares. "
                                            "'A knight on the rim is dim': on the edge it sees only a few squares."),
    move("4k3/8/8/8/8/N7/8/4K3 w - - 0 1", "Move your knight toward the centre.", ["a3c4", "a3b5"],
         "From the centre a knight controls up to 8 squares.", "Jump toward d5 and e5."),
    quiz("4k3/8/8/3N4/8/8/8/N3K3 w - - 0 1", "Which knight is stronger?", ["The knight on d5", "The knight on a1"],
         "The knight on d5", "The d5 knight attacks 8 squares; the a1 knight only 2.", "Count the squares."),
    quiz("4k3/8/8/8/8/8/8/4K3 w - - 0 1", "Where are bishops strongest?", ["On long open diagonals",
         "Behind their own pawns", "In the corner"], "On long open diagonals",
         "A bishop blocked by its own pawns is 'bad'. Open lines make it strong.", "Think about open lines."),
])

lesson("open-files", "Rooks: open files and the 7th rank", "Strategy", lambda: [
    info("r5k1/pp3ppp/2p5/8/8/2P5/PP3PPP/R5K1 w - - 0 1",
         "Rooks need open files: files with no pawns on them. From an open file a rook can invade the enemy "
         "camp."),
    move("r5k1/pp3ppp/2p5/8/8/2P5/PP3PPP/R5K1 w - - 0 1", "Put your rook on an open file.", ["a1d1", "a1e1"],
         "The d- and e-files have no pawns: perfect for a rook.", "Find a file with no pawns at all."),
    move("6k1/pp3ppp/2p5/8/8/2P5/PP3PPP/3R2K1 w - - 0 1", "Invade: put the rook on the 7th rank.", "d1d7",
         "Rd7: the rook attacks the pawns on b7 and f7 from behind.", "Go all the way up the open file."),
    quiz("6k1/pp1R1ppp/2p5/8/8/2P5/PP3PPP/6K1 b - - 0 1", "Why is a rook on the 7th rank so strong?",
         ["It attacks pawns that cannot easily be defended", "It protects your king", "It cannot be captured"],
         "It attacks pawns that cannot easily be defended",
         "Pawns on their starting rank are attacked from the side, and the enemy king may be trapped too.",
         "Look at the pawns on the 7th rank."),
])

lesson("pawn-structure", "Pawn structure", "Strategy", lambda: [
    info("4k3/pp4pp/8/3P4/8/8/PP4PP/4K3 w - - 0 1",
         "A passed pawn has no enemy pawns in front of it on its own file or the files next to it. Nothing can "
         "stop it except pieces, so it is a big strength."),
    square("4k3/pp4pp/8/3P4/8/8/PP4PP/4K3 w - - 0 1", "Click White's passed pawn.", "d5",
           "d5 is passed: no black pawns on the c, d or e files.", "Which white pawn has a free road?"),
    quiz("4k3/pp2pppp/8/8/3P4/8/PP3PPP/4K3 w - - 0 1", "What do we call the white pawn on d4?",
         ["Isolated", "Passed", "Doubled"], "Isolated",
         "No white pawns on the c- or e-files can protect it: an isolated pawn is a target.",
         "Look at its neighbours."),
    square("4k3/pppp1ppp/8/8/8/2P5/P1P2PPP/4K3 w - - 0 1", "Click one of White's doubled pawns.", ["c2", "c3"],
           "Two pawns on the same file are doubled. They cannot protect each other.", "Two pawns on one file."),
    quiz("4k3/pp4pp/8/3P4/8/8/PP4PP/4K3 w - - 0 1", "What should you usually do with a passed pawn?",
         ["Push it, with your pieces supporting it", "Leave it at home", "Trade it for a knight"],
         "Push it, with your pieces supporting it", "'Passed pawns must be pushed', especially in the endgame.",
         "It wants to promote."),
])

lesson("king-safety", "King safety", "Strategy", lambda: [
    info("r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
         "Most games between beginners are decided by attacks on the king. Castle early, keep the pawns in front "
         "of your king, and don't leave it in the centre when lines open."),
    move("r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4", "Make your king safe.", "e1g1",
         "O-O: the king hides behind the pawns and the rook comes to the centre.", "Castle kingside."),
    quiz("r1bq1rk1/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQ1RK1 w - - 6 5",
         "After castling, which pawns should you avoid pushing without a reason?",
         ["The f, g and h pawns", "The a and b pawns", "The c and d pawns"], "The f, g and h pawns",
         "Those pawns are your king's shelter. Every push leaves holes.", "The ones in front of your king."),
    quiz("4k3/8/8/8/8/8/8/4K3 w - - 0 1", "In the endgame, with queens off the board, what should your king do?",
         ["Become active and go to the centre", "Stay in the corner", "Hide behind pawns"],
         "Become active and go to the centre", "With few pieces left, the king is a strong fighting piece.",
         "The danger is gone."),
])

lesson("trade-when-ahead", "When to trade pieces", "Strategy", lambda: [
    info("4k3/pp3ppp/8/8/8/8/PP3PPP/2R1K2R w K - 0 1",
         "When you are ahead in material, trade pieces (not pawns): the fewer pieces left, the bigger your extra "
         "material becomes. When you are behind, avoid trades and keep pieces on to make threats."),
    quiz("4k3/pp3ppp/8/8/8/8/PP3PPP/2R1K2R w K - 0 1", "You are a rook ahead. Should you offer trades?",
         ["Yes, trade pieces", "No, avoid all trades"], "Yes, trade pieces",
         "A rook up with few pieces left is an easy win.", "Simplify when ahead."),
    quiz("4k3/pp3ppp/8/8/8/8/PP3PPP/4K3 w - - 0 1", "You are a piece down. What should you avoid?",
         ["Trading pieces", "Making threats", "Keeping your queen"], "Trading pieces",
         "Every trade brings you closer to a lost endgame. Keep pieces on and look for chances.",
         "Do the opposite of the side that is ahead."),
    quiz("4k3/8/8/8/8/8/8/4K3 w - - 0 1", "Which trade is usually good for you?",
         ["Trading your bad piece for their good piece", "Trading your good piece for their bad piece"],
         "Trading your bad piece for their good piece", "Swap off your problems and their best attackers.",
         "Think about piece quality, not only points."),
])

# =====================================================================================================
# Endgames
# =====================================================================================================
lesson("opposition", "The opposition", "Endgames", lambda: [
    info("8/8/4k3/8/8/4K3/4P3/8 w - - 0 1",
         "Two kings facing each other with one square between them are 'in opposition'. The side that does NOT "
         "have to move has the opposition, and the other king must give way."),
    move("8/8/4k3/8/8/4K3/4P3/8 w - - 0 1", "Take the opposition so your king can lead the pawn.", "e3e4",
         "Ke4: the kings face each other with one square between, and Black must move aside.",
         "Put your king directly in front of the black king with one square between."),
    quiz("8/8/4k3/8/4K3/8/4P3/8 b - - 0 1", "Black to move. Who has the opposition?", ["White", "Black"], "White",
         "Black must move and give ground: White has the opposition.", "Who has to move?"),
    quiz("8/8/4k3/8/4K3/8/4P3/8 b - - 0 1", "In king and pawn endings, where should the king usually stand?",
         ["In front of its pawn", "Behind its pawn", "In the corner"], "In front of its pawn",
         "The king leads the pawn and fights for the squares in front of it.", "Lead from the front."),
])

lesson("king-activity", "The king in the endgame", "Endgames", lambda: [
    info("6k1/5ppp/8/8/8/8/5PPP/6K1 w - - 0 1",
         "In the endgame the king becomes an attacker. The side whose king reaches the centre first usually wins "
         "pawn endings."),
    move("6k1/5ppp/8/8/8/8/5PPP/6K1 w - - 0 1", "Start walking your king to the centre.", "g1f1",
         "Kf1, then Ke2 and Kd3: the king heads for the middle.", "Step toward e2."),
    quiz("8/5k2/8/8/3K4/8/8/8 w - - 0 1", "Which king is better placed for a pawn endgame?",
         ["White's, in the centre", "Black's"], "White's, in the centre",
         "A central king can reach both sides of the board quickly.", "Count steps to each side."),
    quiz("4k3/8/8/8/8/8/8/4K3 w - - 0 1", "How many points is an active king worth in the endgame, roughly?",
         ["About as much as a minor piece (3-4)", "Nothing", "As much as a queen"],
         "About as much as a minor piece (3-4)", "An active king can attack and defend like a strong piece.",
         "It is worth a lot, but not a queen."),
])

lesson("rook-behind-passer", "Rooks behind passed pawns", "Endgames", lambda: [
    info("8/8/3k4/8/P7/8/8/2R3K1 w - - 0 1",
         "Rooks belong behind passed pawns, yours or your opponent's. Behind your pawn, the rook supports it more "
         "and more as it advances."),
    move("8/8/3k4/8/P7/8/8/2R3K1 w - - 0 1", "Put your rook behind your passed a-pawn.", "c1a1",
         "Ra1: as the pawn advances, the rook's support grows.", "The rook goes to the a-file, below the pawn."),
    quiz("8/8/3k4/8/P7/8/8/R5K1 w - - 0 1", "Why is a rook in front of its own pawn usually worse?",
         ["It blocks the pawn and gets stuck", "It cannot give check", "It is easier to trade"],
         "It blocks the pawn and gets stuck", "A rook in front of its pawn becomes a passive blocker.",
         "What does the pawn need?"),
    quiz("8/8/3k4/8/P7/8/8/R5K1 w - - 0 1", "Where should a rook defend against an enemy passed pawn?",
         ["Behind it", "In front of it, far away", "Next to its own king"], "Behind it",
         "From behind, the rook attacks the pawn more as it advances.", "Same rule for both sides."),
])

lesson("philidor-defence", "Philidor: holding a rook endgame", "Endgames", lambda: [
    info("4k3/8/8/4PK2/8/8/r7/7R b - - 0 1",
         "A rook and pawn against a rook is often a draw. In the Philidor defence the defending rook guards the "
         "6th rank (its 3rd rank) so the enemy king cannot come forward."),
    move("4k3/8/8/4PK2/8/8/r7/7R b - - 0 1", "Black to move. Guard the 6th rank with your rook.", "a2a6",
         "Ra6: the white king cannot step to the 6th rank.", "Move the rook up the a-file."),
    move("4k3/8/r3P3/5K2/8/8/8/7R b - - 0 1", "The pawn moved to e6, so the king has no hiding squares in front. "
         "Now check from behind.", "a6a1", "Ra1: endless checks from behind, and the game is a draw.",
         "Drop the rook all the way down."),
    quiz("4k3/8/r3P3/5K2/8/8/8/7R b - - 0 1", "Why can Black now check from behind?",
         ["The pawn no longer shields the white king", "Rooks always check from behind", "White has no rook"],
         "The pawn no longer shields the white king", "Once the pawn is on the 6th, the king can't hide in front "
         "of it.", "What did e6 take away from White?"),
])

# =====================================================================================================
# Good habits
# =====================================================================================================
lesson("checks-captures-threats", "Checks, captures, threats", "Good habits", lambda: [
    info("6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1",
         "Every move, first look at all checks, then all captures, then all threats, for both sides. Strong "
         "players do this automatically. It finds tactics and stops blunders."),
    move("6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1", "Look at checks first. Is there a winning one?", "e1e8",
         "Re8#: looking at checks first found the mate.", "Your rook can check on the back rank.", mode="mates"),
    move("4k3/8/8/2b5/8/8/8/2R1K3 w - - 0 1", "No checks win here. Now look at captures.", "c1c5",
         "Rxc5 wins a free bishop.", "Which black piece is attacked and undefended?", mode="best"),
    quiz("4k3/8/8/2b5/8/8/8/2R1K3 w - - 0 1", "Why check your opponent's checks and captures too?",
         ["To see what they threaten before you move", "To waste time", "It's not needed"],
         "To see what they threaten before you move", "Your move must answer their threats as well.",
         "Chess has two players."),
])

lesson("blunder-check", "The blunder check", "Good habits", lambda: [
    info("4k3/8/4p3/3p4/6n1/8/8/3Q2K1 w - - 0 1",
         "Before you let go of a piece, ask: after this move, can my opponent capture something, give check or "
         "mate? This 5-second check saves more games than any opening."),
    quiz("4k3/8/4p3/3p4/6n1/8/8/3Q2K1 w - - 0 1", "Should White play Qxd5?", ["No", "Yes"], "No",
         "exd5 wins your queen: the d5 pawn is protected by e6.", "Who protects d5?"),
    move("4k3/8/4p3/3p4/6n1/8/8/3Q2K1 w - - 0 1", "Find the safe capture.", "d1g4",
         "Qxg4: the knight has no defender, so it is a free piece.", "Which black piece is unprotected?"),
    quiz("4k3/8/8/8/8/8/8/4K3 w - - 0 1", "When should you do the blunder check?", ["Before every move",
         "Only in the endgame", "Only when in check"], "Before every move",
         "Make it a habit: one quick look before every single move.", "Every time."),
])

lesson("dont-stalemate", "Winning without stalemate", "Good habits", lambda: [
    info("k7/8/2K5/8/8/8/8/1Q6 w - - 0 1",
         "When you are far ahead, the only way to throw away the win is stalemate. Before every move near the "
         "end, check that the enemy king still has a legal move or is in check."),
    quiz("k7/8/1QK5/8/8/8/8/8 b - - 0 1", "White just played Qb6. Black to move. What happened?",
         ["Stalemate: a draw", "Checkmate", "Black is in check"], "Stalemate: a draw",
         "The black king is not in check and has no legal move. Half a point thrown away!",
         "Count Black's legal moves."),
    move("k7/8/2K5/8/8/8/8/1Q6 w - - 0 1", "Give checkmate instead.", "b1b7",
         "Qb7#: check, and no escape. That is the difference from stalemate.", "Your king protects b7.",
         mode="mates"),
    quiz("k7/8/2K5/8/8/8/8/1Q6 w - - 0 1", "What is the safest habit when the enemy king is almost trapped?",
         ["Make sure it always has a square until you give mate", "Take all its squares quickly",
          "Move the queen next to it"], "Make sure it always has a square until you give mate",
         "Leave one square, bring your king closer, then mate.", "Avoid taking every square without check."),
])

lesson("think-like-opponent", "Think like your opponent", "Good habits", lambda: [
    info(E4E5NF3NC6, "After your opponent moves, ask 'why did they play that?' Every move has a purpose: an "
                     "attack, a threat, a plan. Find it before you answer."),
    quiz("r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
         "White just played Nf3. What does it attack?", ["The pawn on e5", "The king", "The knight on b8"],
         "The pawn on e5", "Nf3 attacks e5, so Black defends it with ...Nc6.", "Look at the knight's squares."),
    quiz(SCHOLAR_THREAT, "White just played Qh5. What is the threat?", ["Qxf7 checkmate", "Qxh7", "Nothing"],
         "Qxf7 checkmate", "Queen and bishop both aim at f7: a mate threat.", "Follow both pieces' lines."),
    quiz(E4E5NF3NC6, "Your opponent's move doesn't seem to do anything. What should you do?",
         ["Look again for a hidden threat, then make your plan", "Ignore it", "Copy their move"],
         "Look again for a hidden threat, then make your plan",
         "Quiet moves often prepare a tactic. If there is truly nothing, carry on with your plan.",
         "Be suspicious first."),
])

lesson("time-management", "Using your time", "Good habits", lambda: [
    info(START, "Play the opening at a steady pace, spend your time on the critical moments (captures, attacks, "
                "the moment the position changes), and never let your clock run very low."),
    quiz(START, "When should you think the longest?", ["At critical moments, like captures and attacks",
         "On the first move", "When the position is quiet and simple"],
         "At critical moments, like captures and attacks", "Invest time where one move changes the result.",
         "Where are mistakes most costly?"),
    quiz(START, "You have 30 seconds left and a winning position. What should you do?",
         ["Play simple safe moves quickly", "Look for the most beautiful move", "Offer a draw"],
         "Play simple safe moves quickly", "Under time pressure, safe and simple beats brilliant.",
         "Don't lose on time."),
    info(START, "Tip: in a 10-minute game, aim to have about half your time left after move 15. Use the time "
                "controls in New game to practise."),
])

lesson("practice-routine", "How to improve every day", "Good habits", lambda: [
    info(START, "A simple daily routine works best: 10 minutes of puzzles, one game you think about, and a quick "
                "review of that game. Bobby's daily plan in Train follows exactly this."),
    quiz(START, "What helps beginners improve fastest?", ["Tactics puzzles and reviewing your own games",
         "Memorising long opening lines", "Only playing fast games"], "Tactics puzzles and reviewing your own games",
         "Most beginner games are decided by tactics. Puzzles train your eye, reviews fix your habits.",
         "What decides most beginner games?"),
    quiz(START, "After losing a game, what should you do?", ["Review it to find the turning point",
         "Play again right away", "Forget it"], "Review it to find the turning point",
         "Every loss shows you something. Bobby turns your mistakes into puzzles for you.",
         "Learn from it."),
    info(START, "Keep your streak going in Train > Challenges, and come back to these lessons whenever a "
                "weakness shows up in your games."),
])


# ---------- write ----------
def main() -> int:
    if errors:
        print("Lesson build errors:")
        for e in errors:
            print("  -", e)
        return 1
    existing = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in OUT.glob("*.json") if p.stem != "index"}
    all_lessons = {**existing, **LESSONS}
    listed = [i for sec in SECTIONS for i in COURSE[sec]]
    missing = [i for i in listed if i not in all_lessons]
    unplaced = [i for i in all_lessons if i not in listed]
    if missing or unplaced:
        print("missing:", missing, "unplaced:", unplaced)
        return 1
    order = 1
    for sec in SECTIONS:
        for lid in COURSE[sec]:
            L = all_lessons[lid]
            L["section"], L["order"] = sec, order
            order += 1
            (OUT / f"{lid}.json").write_text(json.dumps(L, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(LESSONS)} new lessons; course has {order - 1} lessons in {len(SECTIONS)} sections")
    return 0


if __name__ == "__main__":
    sys.exit(main())
