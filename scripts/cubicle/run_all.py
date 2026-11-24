"""Run the whole Cubicle pipeline (resumable; raw caches live in data/cubicle/raw/).

  python scripts/cubicle/run_all.py            # key-less (public RSS / oEmbed / Wikidata / HN / Lichess / GitHub)
  python scripts/cubicle/run_all.py --api      # requires env YT_API_KEY (durations, dates, views, likes, playlists)
  python scripts/cubicle/run_all.py --llm      # requires env ANTHROPIC_API_KEY (Claude Haiku labelling pass)
  python scripts/cubicle/run_all.py --from 4   # restart from a step number
"""
import argparse
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
STEPS = [("1", "01_sources.py"), ("t", "build_taxonomy.py"), ("2", "02_channels.py"), ("3", "03_collect.py"),
         ("4", "04_gate.py"), ("5", "05_classify.py"), ("5b", "05b_llm_label.py"), ("6", "06_score.py"),
         ("7", "07_export.py"), ("8", "08_latest.py"), ("v", "validate_cubicle.py"), ("r", "report.py")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", action="store_true")
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--from", dest="start", default="1")
    a = ap.parse_args()
    if a.api and not os.environ.get("YT_API_KEY"):
        sys.exit("--api needs env YT_API_KEY (export YT_API_KEY=...)")
    if a.llm and not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("--llm needs env ANTHROPIC_API_KEY")
    env = dict(os.environ)
    if not a.api:
        env.pop("YT_API_KEY", None)
    order = [s for s, _ in STEPS]
    first = order.index(a.start) if a.start in order else 0
    rc = 0
    for step, script in STEPS[first:]:
        if step == "5b" and not a.llm:
            print("-- skip 05b (no --llm)")
            continue
        print(f"\n=== {script}", flush=True)
        r = subprocess.run([sys.executable, str(HERE / script)], env=env, cwd=HERE)
        if r.returncode != 0:
            if step == "v":
                rc = r.returncode  # validator failure is reported, report.py still runs
                continue
            sys.exit(r.returncode)
    sys.exit(rc)


if __name__ == "__main__":
    main()
