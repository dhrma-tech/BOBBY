"""Step 5: classify each gated video to one node, one level, one kind with keyword rules (classify.py).
Videos with no node match are dropped as unclassified (counted). The optional Claude pass is 05b_llm_label.py.
Output: data/cubicle/raw/classified.json
"""
from collections import Counter

from classify import Classifier
from common import DATA_DIR, RAW, dump_json, load_json


def main():
    tax = load_json(DATA_DIR / "taxonomy.json")
    clf = Classifier(tax)
    rows, unclassified = [], []
    for c in load_json(RAW / "gated.json", []):
        r = clf.classify(c["title"], c["channel"])
        if not r:
            unclassified.append(c["id"])
            continue
        c.update({"node": r["node"], "section": r["section"], "level": r["level"], "kind": r["kind"],
                  "match": r["match"], "llm": 0})
        rows.append(c)
    dump_json(RAW / "classified.json", rows)
    dump_json(RAW / "unclassified.json", unclassified)
    print(f"classified {len(rows)}, unclassified {len(unclassified)}")
    print("by section:", dict(Counter(r["section"] for r in rows).most_common()))


if __name__ == "__main__":
    main()
