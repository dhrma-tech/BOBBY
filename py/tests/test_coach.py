import re

import pytest

from bobby import api

FACTS = {"fen": "r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3", "move": "Nf6",
         "class": "blunder", "eval_before": {"cp": -20, "mate": None}, "eval_after": {"cp": None, "mate": 1},
         "best_line": ["g6", "Qf3", "Nf6"], "tags": ["mate_threat", "phase_opening"],
         "cards": [{"title": "f7", "text": "The f7 square is only guarded by the king early on."}]}


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
