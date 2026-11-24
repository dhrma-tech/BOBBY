"""No-LLM fallback explanations built from engine facts."""
from __future__ import annotations

from ..plan import tag_title
from ..winprob import winprob

CLASS_TEXT = {
    "best": "is the engine's top choice",
    "good": "is a solid move, close to the engine's best",
    "inaccuracy": "is an inaccuracy: it gives away a little of your advantage",
    "mistake": "is a mistake: it hands your opponent a real chance",
    "blunder": "is a blunder: it changes the result of the game",
}


def _eval_str(ev: dict | None) -> str | None:
    if not ev:
        return None
    if ev.get("mate") is not None:
        m = ev["mate"]
        return f"mate in {abs(m)} for {'White' if m > 0 else 'Black'}" if m else "checkmate"
    if ev.get("cp") is None:
        return None
    return f"{ev['cp'] / 100:+.1f}"


def _themes(facts: dict) -> str:
    tags = [t for t in facts.get("tags") or facts.get("weakness_tags") or [] if not str(t).startswith("phase_")]
    return ", ".join(tag_title(t).lower() for t in tags[:3])


def _move(facts: dict) -> str:
    mv = facts.get("move") or "This move"
    best = facts.get("best_line") or []
    cls = facts.get("class")
    parts = [f"{mv} {CLASS_TEXT.get(cls, 'was played')}."]
    a, b = _eval_str(facts.get("eval_before")), _eval_str(facts.get("eval_after"))
    if a and b and a != b:
        parts.append(f"The evaluation went from {a} to {b}.")
    if best and cls not in ("best", None) and best[0] != mv:
        parts.append(f"The engine preferred {best[0]}" + (f", continuing {' '.join(best[1:5])}." if len(best) > 1 else "."))
    th = _themes(facts)
    if th:
        parts.append(f"Theme to watch: {th}.")
    cards = facts.get("cards") or facts.get("knowledge_cards") or []
    if cards and isinstance(cards[0], dict) and cards[0].get("text"):
        parts.append(cards[0]["text"])
    return " ".join(parts)


def _review(facts: dict) -> str:
    parts = []
    acc = facts.get("accuracy")
    if isinstance(acc, (int, float)):
        parts.append(f"Your accuracy was {acc:.0f}%.")
    counts = [f"{facts[k]} {k}" for k in ("blunders", "mistakes", "inaccuracies") if facts.get(k)]
    if counts:
        parts.append("You had " + ", ".join(counts) + ".")
    km = facts.get("key_moments") or []
    if km:
        k = km[0]
        if isinstance(k, dict) and k.get("move"):
            line = f"The biggest swing came with {k['move']}"
            parts.append(line + (f"; the engine wanted {k['best']}." if k.get("best") else "."))
        else:
            parts.append(f"There were {len(km)} key moments worth replaying.")
    th = _themes(facts)
    if th:
        parts.append(f"Practise next: {th}.")
    return " ".join(parts) or "Game saved. Open the review to step through the key moments."


def _hint(facts: dict) -> str:
    level = int(facts.get("hint_level", 1))
    best = facts.get("best_line") or []
    th = _themes(facts)
    if level <= 1 or not best:
        return f"Look for {th}." if th else "Look at checks, captures and threats first."
    san = best[0]
    piece = {"K": "king", "Q": "queen", "R": "rook", "B": "bishop", "N": "knight", "O": "king"}.get(san[0], "pawn")
    if level == 2:
        return f"Use your {piece}."
    return f"Play {san}."


def template_explanation(facts: dict, mode: str) -> str:
    if mode == "move_explain":
        return _move(facts)
    if mode == "review":
        return _review(facts)
    if mode == "hint":
        return _hint(facts)
    if mode == "chat":
        base = _move(facts) if facts.get("move") else ""
        ev = _eval_str(facts.get("eval") or facts.get("eval_after"))
        if ev and not base:
            wp = winprob((facts.get("eval") or facts.get("eval_after") or {}).get("cp"),
                         (facts.get("eval") or facts.get("eval_after") or {}).get("mate"))
            base = f"The engine rates this position {ev} (White's winning chances about {wp * 100:.0f}%)."
        return (base + " Add an API key in Settings for free-form coach answers.").strip()
    raise ValueError(f"unknown mode: {mode!r}")
