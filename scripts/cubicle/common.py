"""Shared helpers for the Cubicle pipeline (metadata only: ids, titles, channels, dates)."""
import datetime as dt
import hashlib
import html
import json
import pathlib
import re
import threading
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "cubicle"
RAW = DATA_DIR / "raw"
HTTP_CACHE = RAW / "http"
for _p in (DATA_DIR, RAW, HTTP_CACHE):
    _p.mkdir(parents=True, exist_ok=True)

UA = "bobby-cubicle-pipeline/1.0 (+https://github.com/dhrma-tech/BOBBY)"
TIER_WEIGHT = {1: 2.0, 2: 1.2, 3: 0.6, 0: 0.0}

_VID = re.compile(
    r"(?:youtube(?:-nocookie)?\.com/(?:watch\?(?:[^\s\"'<>]*?[&;])?v=|embed/|shorts/|live/|v/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])", re.I)
_PL = re.compile(r"youtube\.com/(?:playlist|watch)\?(?:[^\s\"'<>]*?[&;])?list=([A-Za-z0-9_-]{13,})", re.I)
_CH = re.compile(r"youtube\.com/channel/(UC[A-Za-z0-9_-]{22})(?![A-Za-z0-9_-])", re.I)
_HANDLE = re.compile(r"youtube\.com/@([A-Za-z0-9_.-]+)", re.I)

_lock = threading.Lock()
_last = {}


def video_ids(text):
    s = html.unescape(text or "")
    return list(dict.fromkeys(m.group(1) for m in _VID.finditer(s)))


def playlist_ids(text):
    s = html.unescape(text or "")
    return list(dict.fromkeys(m.group(1) for m in _PL.finditer(s)))


def channel_ids(text):
    s = html.unescape(text or "")
    return list(dict.fromkeys(m.group(1) for m in _CH.finditer(s)))


def handles(text):
    s = html.unescape(text or "")
    return list(dict.fromkeys(m.group(1) for m in _HANDLE.finditer(s)))


def load_json(path, default=None):
    path = pathlib.Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def dump_json(path, obj, compact=False):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    else:
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def read_jsonl(path):
    path = pathlib.Path(path)
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def polite_get(url, *, params=None, headers=None, cache=True, delay=0.6, timeout=30, accept_codes=(200,)):
    """GET with a per-host delay and an on-disk cache of 200 bodies. Returns (status, text).
    Never works around blocks: a 403/429/challenge page is returned as-is for the caller to skip."""
    key = hashlib.sha1((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
    f = HTTP_CACHE / f"{key}.txt"
    if cache and f.exists():
        return 200, f.read_text(encoding="utf-8")
    host = re.sub(r"^https?://([^/]+).*", r"\1", url)
    with _lock:
        wait = delay - (time.time() - _last.get(host, 0))
        _last[host] = time.time() + max(wait, 0)
    if wait > 0:
        time.sleep(wait)
    h = {"User-Agent": UA}
    h.update(headers or {})
    try:
        r = requests.get(url, params=params, headers=h, timeout=timeout)
    except Exception as e:  # network error
        return 0, str(e)[:100]
    text = r.text
    if r.status_code in accept_codes and not _is_challenge(text):
        if cache:
            f.write_text(text, encoding="utf-8")
        return r.status_code, text
    return (403 if _is_challenge(text) else r.status_code), text[:200]


def _is_challenge(text):
    head = (text or "")[:600].lower()
    return "just a moment..." in head or "cf-chl" in head or "captcha" in head[:300]


def normalize(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())
