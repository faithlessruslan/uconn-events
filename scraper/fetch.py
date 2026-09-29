"""Cached, gently rate-limited HTTP fetch.

UConn's calendar rate-limits hard. Measured behaviour: bursts above roughly
one request per second start returning HTTP 429, and once it trips the whole
server stays unhappy for a while. So we never retry inside a request. Instead
a failed page is left uncached and a later pass picks it up after a rest.
"""

import hashlib
import gzip
import os
import threading
import time
import urllib.error
import urllib.request

import config

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
os.makedirs(CACHE, exist_ok=True)

GAP = [0.0]          # seconds to wait before the next request
_lock = threading.Lock()
_last = [0.0]
BLOCKED = [False]    # set True the moment we see a 429


def _cache_path(url):
    return os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest() + ".txt")


def cached(url):
    return os.path.exists(_cache_path(url))


def _throttle():
    """Keep a global minimum gap between requests, even with many workers.

    The gap is measured from the *end* of the last request. Timing it from the
    start instead would make the real rate `interval + response time`, which
    measured out four times slower than intended.
    """
    with _lock:
        wait = max(config.MIN_INTERVAL, GAP[0]) - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()


def _mark_finished():
    with _lock:
        _last[0] = time.time()


def get(url, force=False):
    """Return the body of `url`, or '' if it could not be fetched.

    A '' result is never cached, so calling again later is a real retry.
    """
    path = _cache_path(url)
    if os.path.exists(path) and not force:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()

    if BLOCKED[0]:
        return ""

    _throttle()
    req = urllib.request.Request(
        url, headers={"User-Agent": config.UA, "Accept-Encoding": "gzip"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            body = raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        _mark_finished()
        if exc.code == 429:
            # Server said stop. Tell the caller and cool off.
            BLOCKED[0] = True
            GAP[0] = config.COOL_OFF
        return ""
    except (urllib.error.URLError, OSError):
        _mark_finished()
        return ""

    _mark_finished()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return body


def wait_out_cooldown():
    """Sleep off a 429 block and clear the flag. Returns True if it waited."""
    if not BLOCKED[0]:
        return False
    print(f"  rate limited, resting {config.COOL_OFF:.0f}s")
    time.sleep(config.COOL_OFF)
    BLOCKED[0] = False
    GAP[0] = 0.0
    return True
