"""Re-run oEmbed on every id in videos.json / latest.json / paths.json and drop dead ones (404/401/gone).
Keeps the files consistent (paths only reference surviving ids).   python scripts/cubicle/revalidate.py"""
import importlib
import json

from common import DATA_DIR, RAW, dump_json, load_json

oembed = importlib.import_module("03_collect").oembed


def main():
    vj = load_json(DATA_DIR / "videos.json")
    lj = load_json(DATA_DIR / "latest.json", {"built": "", "items": []})
    ids = list(dict.fromkeys([v["i"] for v in vj["videos"]] + [v["i"] for v in lj["items"]]))
    dead = set()
    with (RAW / "oembed.jsonl").open("a", encoding="utf-8") as f:
        for n, i in enumerate(ids, 1):
            r = oembed(i)
            if r["status"] in ("gone", "restricted"):
                dead.add(i)
                f.write(json.dumps(r) + "\n")  # later line wins when the cache is read back as a dict
            if n % 100 == 0:
                print(f"  {n}/{len(ids)}", flush=True)
    if dead:
        # rewrite the oEmbed cache so a dead id no longer counts as verified
        rows = {}
        for l in (RAW / "oembed.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(l)
            rows[r["id"]] = r
        (RAW / "oembed.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows.values()), encoding="utf-8")
        vj["videos"] = [v for v in vj["videos"] if v["i"] not in dead]
        lj["items"] = [v for v in lj["items"] if v["i"] not in dead]
        dump_json(DATA_DIR / "videos.json", vj, compact=True)
        dump_json(DATA_DIR / "latest.json", lj, compact=True)
        pj = load_json(DATA_DIR / "paths.json", {"paths": []})
        for p in pj["paths"]:
            p["videos"] = [i for i in p["videos"] if i not in dead]
        dump_json(DATA_DIR / "paths.json", pj)
    print(f"revalidated {len(ids)} ids, dropped {len(dead)} dead")


if __name__ == "__main__":
    main()
