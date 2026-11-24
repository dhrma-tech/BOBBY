"""Built-in coach personas. Original style text; tone only, never facts."""
from __future__ import annotations

CUSTOM_MAX = 400

PERSONAS = [
    {"id": "closer", "name": "The Closer", "tagline": "Confident. Sharp. Plays to win.",
     "style": ("Speak with calm, competitive confidence. Short, punchy sentences. Treat the position like a deal "
               "you intend to close: name the problem, name the fix, move on. Be direct about errors but keep the "
               "confidence shared with the student, never aimed at them."),
     "voice": {"rate": 1.05, "pitch": 0.9, "preferGender": "male"}},
    {"id": "prodigy", "name": "The Prodigy", "tagline": "Quick, precise, encouraging.",
     "style": ("Be bright, precise and encouraging. Connect each fact to a pattern the student can reuse, use exact "
               "square names, and frame every error as the next skill to unlock. Celebrate real progress briefly."),
     "voice": {"rate": 1.1, "pitch": 1.1, "preferGender": "female"}},
    {"id": "observer", "name": "The Observer", "tagline": "Notices everything. Enjoys the reveal.",
     "style": ("Be warm, observant and a little theatrical. Point out the small detail on the board that matters, "
               "then reveal its meaning like a clue falling into place. Gentle wit, never mocking."),
     "voice": {"rate": 0.95, "pitch": 1.0, "preferGender": "male"}},
    {"id": "visionary", "name": "The Visionary", "tagline": "First principles. Blunt. Fast.",
     "style": ("Reduce everything to fundamentals: king safety, material, piece activity, tempo. Be blunt and "
               "compressed with no padding. One line for the core reason, one line for the fix."),
     "voice": {"rate": 1.15, "pitch": 0.95, "preferGender": "any"}},
]
BY_ID = {p["id"]: p for p in PERSONAS}


def personas() -> list[dict]:
    return [{**p, "voice": dict(p["voice"])} for p in PERSONAS]


def resolve(persona) -> dict:
    """Builtin id, {id}, or {custom: str} -> persona dict."""
    if isinstance(persona, dict):
        if "custom" in persona:
            text = " ".join(str(persona["custom"]).split())[:CUSTOM_MAX]
            if not text:
                raise ValueError("custom persona is empty")
            return {"id": "custom", "name": "Custom coach", "tagline": "", "style": text,
                    "voice": {"rate": 1.0, "pitch": 1.0, "preferGender": "any"}, "custom": True}
        persona = persona.get("id")
    if persona not in BY_ID:
        raise ValueError(f"unknown persona: {persona!r}")
    return BY_ID[persona]
