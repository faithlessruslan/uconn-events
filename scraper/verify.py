"""Sanity-check the built snapshot.

Run after a build to confirm the numbers in the README still hold, and to
catch the timing regressions that are easy to reintroduce.

    python3 verify.py
"""

import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
JSON_PATH = os.path.join(ROOT, "data", "uconn-events.json")
HTML_PATH = os.path.join(ROOT, "index.html")
CSV_PATH = os.path.join(ROOT, "data", "uconn-events.csv")
TEMPLATE_PATH = os.path.join(HERE, "template.html")

# House rule: no emojis, including emoji used as icons. A glyph font renders
# U+23F0 and friends in full colour, which is both off-style and against the
# rule, so the check covers the range rather than a hand-written list.
EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002B00-\U00002BFF"
    "\U0000FE0F"
    "]"
)

failures = []


_UNSET = object()


def check(label, got, want=_UNSET, ok=None):
    if ok is None:
        ok = got == want
        extra = f" (want {want})"
    else:
        extra = ""
    mark = "ok  " if ok else "FAIL"
    print(f"  [{mark}] {label}: {got}{extra}")
    if not ok:
        failures.append(label)


def main():
    with open(JSON_PATH, encoding="utf-8") as fh:
        data = json.load(fh)

    now = int(datetime.datetime.now().timestamp())

    print("data/uconn-events.json")
    check("records", len(data), ok=len(data) > 500)
    check("every record has a start", sum(1 for r in data if r.get("starts_ts")),
          len(data))
    check("every record has a title", sum(1 for r in data if r.get("title")),
          len(data))

    # No event should stretch for years. The sentinel-date bug produced
    # windows ending in 2123, so guard the width directly.
    widest = max((r["ends_ts"] - r["starts_ts"]) for r in data
                 if r.get("starts_ts") and r.get("ends_ts"))
    check("widest window (days)", round(widest / 86400, 1), ok=widest < 400 * 86400)

    earliest = min(r["starts_ts"] for r in data)
    latest = max(r["starts_ts"] for r in data)
    check("earliest start year", datetime.datetime.fromtimestamp(earliest).year,
          ok=datetime.datetime.fromtimestamp(earliest).year >= 2020)
    check("latest start within 2 years",
          (latest - now) < 2 * 365 * 86400, ok=True)

    ids = [r["id"] for r in data]
    check("no duplicate ids", len(ids) - len(set(ids)), 0)

    print("\nindex.html")
    with open(HTML_PATH, encoding="utf-8") as fh:
        page = fh.read()

    match = re.search(
        r'<script id="event-data" type="application/json">(.*?)</script>',
        page, re.S)
    check("embedded data block present", bool(match), ok=bool(match))

    embedded = json.loads(match.group(1))
    check("embedded count matches json", len(embedded), len(data))

    # The whole page breaks if these are seconds instead of milliseconds.
    stamps = [r.get("starts_ts", 0) for r in embedded]
    check("timestamps are milliseconds", min(stamps), ok=min(stamps) > 10 ** 12)

    check("light is the default theme",
          'data-theme="light"' in page, True)
    check("no leftover placeholders",
          ("/*__DATA__*/" in page) or ("__BUILT__" in page), False)

    print("\nhouse rules")
    for label, path in (("index.html", HTML_PATH),
                        ("uconn-events.csv", CSV_PATH),
                        ("template.html", TEMPLATE_PATH)):
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        hits = EMOJI.findall(body)
        check(f"no emoji in {label}", len(hits), 0)
        if hits:
            for ch in sorted(set(hits)):
                print(f"         found {ch!r} U+{ord(ch):04X}")

    check("no emoji entities in the template",
          bool(re.search(r"&#1[0-9]{5};", open(TEMPLATE_PATH, encoding="utf-8").read())),
          False)
    return finish()


def finish():
    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        raise SystemExit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()
