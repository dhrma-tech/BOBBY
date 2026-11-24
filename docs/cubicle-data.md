# Cubicle data contract

Scroll (internally "cubicle") is Bobby's library of chess videos. The Python pipeline in `scripts/cubicle/` writes these
files; `site/scripts/prepare-assets.mjs` copies `data/cubicle/*.json` (not `raw/`) into the site. The site never
reads anything else. There are no thumbnail fields: the site derives a timeline-frame thumbnail from the video id (i.ytimg.com/vi/<id>/hq1|hq2|hq3.jpg). Every `i` has passed the oEmbed check.

## data/cubicle/taxonomy.json
```json
{ "sections": [
  { "id": "start", "title": "Start here", "blurb": "...", "floor": 40,
    "nodes": [ { "id": "start-board", "title": "Board and pieces", "shelf": "evergreen",
                 "level": "b", "keywords": ["..."], "practice": "#/learn?l=board-setup" } ] } ] }
```
- `shelf`: `evergreen` | `semi` | `fast` (freshness half-life 10 / 4 / 1 years).
- `level` (node default): `b` < 1000, `i` 1000-1600, `a` 1600-2000, `x` 2000+.
- `practice`: a Bobby hash route (Learn lesson, Train tab with theme, endgame trainer, opening explorer) or null.
- `floor`: minimum videos for the section (validator).

## data/cubicle/videos.json
```json
{ "built": "2026-11-24T10:00:00Z", "videos": [ { "i": "VIDEOID", "t": "Title", "c": "Channel name",
  "h": "UC... or null", "n": "node-id", "s": "section-id", "l": "b", "k": "lesson", "sc": 7.31, "f": 0.93,
  "o": 0, "sr": 2, "src": ["label 1", "label 2"], "tr": 1, "d": 1234, "p": "2023-04-02" } ] }
```
| key | meaning |
|---|---|
| i | YouTube video id (oEmbed-verified) |
| t, c | title, channel name |
| h | channel id (UC...) or null |
| n, s | node id, section id |
| l | level `b` `i` `a` `x` |
| k | kind `lesson` `course` `gameplay` `review` `tips` `recap` `talk` |
| sc | rank score (higher first) |
| f | freshness 0..1 |
| o | 1 = "May be outdated" |
| sr | number of independent vouches (sources) |
| src | vouch source labels, shown as "Why it's here" |
| tr | channel tier 1, 2, 3, or 0 (untiered) |
| d | duration in seconds, or null when unknown (key-less) |
| p | publish date `YYYY-MM-DD`, or null when unknown |

Sorted by `sc` descending.

## data/cubicle/latest.json
Same row shape as videos (sc may be 0), last 45 days from tier 1-2 channels' long-form upload feeds:
`{ "built": "...", "items": [ ... ] }`, newest first.

## data/cubicle/paths.json
Ordered tracks: `{ "paths": [ { "id": "core", "title": "...", "blurb": "...", "level": "b", "videos": ["id", ...] } ] }`.
Every id in a path also appears in `videos.json`. The site adds rating-band and repertoire paths from videos.json
when they are not present here.

## data/cubicle/meta.json
`{ "built": "...", "videos": N, "channels": N, "nodes": N, "sections": {"start": N, ...}, "keyless": true,
   "shortfalls": ["..."] }`
