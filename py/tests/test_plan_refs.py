import json, pathlib
from bobby import api
from bobby.plan import BEGINNER_LESSONS, TAG_LESSON

LESSON_IDS = {p.stem for p in (pathlib.Path(__file__).parents[2] / "data" / "lessons").glob("*.json")}


def test_plan_lesson_refs_exist():
    for ref in list(BEGINNER_LESSONS.values()) + list(TAG_LESSON.values()):
        assert ref in LESSON_IDS, ref
