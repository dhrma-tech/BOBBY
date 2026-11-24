"""Step 4: the "best of best" gate. See gate.py for the rules.

Keep if >= 2 independent vouches, OR tier 1/2 channel AND the engagement bar (with YT_API_KEY: views >= channel
median and like ratio in the channel's top half). Key-less, engagement/duration/language are unknown: tier 1/2
videos pass as members of their channel's long-form upload feed, and title rules still apply.
Tier 3 is assigned here: any other channel with >= 3 vouched videos.
Output: data/cubicle/raw/gated.json, gate_stats.json
"""
import json
from collections import Counter, defaultdict

import yt_api
from common import DATA_DIR, RAW, dump_json, load_json
from gate import channel_stats, n_vouches, passes


def main():
    cands = load_json(RAW / "candidates.json", [])
    blocklist = load_json(DATA_DIR / "blocklist.json", {})
    keyless = not bool(yt_api.key()) or not any(c.get("duration") for c in cands)
    vouched = defaultdict(int)
    for c in cands:
        if c["tier"] == 0 and n_vouches(c) >= 1:
            vouched[c["channel"]] += 1
    for c in cands:
        if c["tier"] == 0 and vouched.get(c["channel"], 0) >= 3:
            c["tier"] = 3
    stats = channel_stats(cands)
    kept, reasons = [], Counter()
    for c in cands:
        ok, why = passes(c, stats, keyless, blocklist)
        reasons[("keep:" if ok else "drop:") + why] += 1
        if ok:
            c["gate"] = why
            kept.append(c)
    dump_json(RAW / "gated.json", kept)
    dump_json(RAW / "gate_stats.json", {"keyless": keyless, "candidates": len(cands), "kept": len(kept),
                                        "reasons": dict(reasons.most_common()),
                                        "tier3_channels": sorted(k for k, v in vouched.items() if v >= 3)})
    print(f"gate ({'key-less' if keyless else 'api'}): {len(cands)} -> {len(kept)}")
    for k, v in reasons.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
