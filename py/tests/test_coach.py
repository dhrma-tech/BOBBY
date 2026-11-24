import re

import pytest

from bobby import api

FACTS = {"fen": "r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3", "move": "Nf6",
         "class": "blunder", "eval_before": {"cp": -20, "mate": None}, "eval_after": {"cp": None, "mate": 1},
         "best_line": ["g6", "Qf3", "Nf6"], "tags": ["mate_threat", "phase_opening"],
         "cards": [{"title": "f7", "text": "The f7 square is only guarded by the king early on."}]}


def test_personas():
    ps = api.personas()
    assert [p["id"] for p in ps] == ["closer", "prodigy", "observer", "visionary"]
    for p in ps:
        assert p["name"] and p["tagline"] and p["style"]
        assert set(p["voice"]) == {"rate", "pitch", "preferGender"}


@pytest.mark.parametrize("mode", ["move_explain", "review", "chat", "hint"])
@pytest.mark.parametrize("persona", ["closer", "prodigy", "observer", "visionary", {"custom": "pirate, cheerful"}])
def test_prompt_grounding(persona, mode):
    pr = api.coach_prompt(persona, FACTS, mode)
    s = pr["system"]
    assert "ONLY the engine facts" in s and "Never evaluate" in s
    assert "Nf6" in pr["user"] and "FACTS" in pr["user"]


def test_prompt_errors():
    with pytest.raises(ValueError):
        api.coach_prompt("nobody", FACTS, "review")
    with pytest.raises(ValueError):
        api.coach_prompt("closer", FACTS, "poem")
    with pytest.raises(ValueError):
        api.coach_prompt({"custom": "   "}, FACTS, "chat")


def test_custom_is_fenced_and_capped():
    pr = api.coach_prompt({"custom": "x" * 1000}, FACTS, "chat")
    assert "<<<" in pr["system"] and "x" * 401 not in pr["system"]


def test_templates():
    t = api.template_explanation(FACTS, "move_explain")
    assert "Nf6" in t and "blunder" in t and "g6" in t and "mate threats" in t
    r = api.template_explanation({"accuracy": 71.4, "blunders": 1, "key_moments": [{"move": "Nf6", "best": "g6"}],
                                  "tags": ["fork"]}, "review")
    assert "71%" in r and "Nf6" in r and "forks" in r
    assert api.template_explanation({**FACTS, "hint_level": 1}, "hint").startswith("Look for")
    assert api.template_explanation({**FACTS, "hint_level": 2}, "hint") == "Use your pawn."
    assert api.template_explanation({**FACTS, "hint_level": 3}, "hint") == "Play g6."
    assert "engine rates" in api.template_explanation({"eval": {"cp": 120}}, "chat")
    assert api.template_explanation({}, "review")
    with pytest.raises(ValueError):
        api.template_explanation(FACTS, "poem")


def test_no_real_or_tv_names():
    import pathlib
    banned = re.compile(r"\b(harvey|specter|beth|harmon|sherlock|holmes|musk|elon|carlsen|kasparov|fischer|"
                        r"suits|queen'?s gambit|stark|jarvis)\b", re.I)
    root = pathlib.Path(api.__file__).parent
    for f in root.rglob("*.py"):
        assert not banned.search(f.read_text()), f
