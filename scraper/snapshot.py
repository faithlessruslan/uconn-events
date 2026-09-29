"""Build data/uconn-events.json from the list API plus whatever is cached.

Use this for a quick preview. The full `scrape.py` run produces the same file
with every detail page filled in.
"""

import json
import os

import fetch
import scrape


def main():
    raw = scrape.list_events()
    recs = []
    for event in raw:
        # Only read pages already in the cache; never add new requests.
        if fetch.cached(event.get("url", "")):
            scrape.enrich(event)
        recs.append(scrape.normalize(event))

    recs = scrape.dedupe(recs)
    from topics import add_topics
    add_topics(recs)
    recs.sort(key=lambda r: (r["starts_ts"] or 0, r["title"]))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "data", "uconn-events.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(recs, fh, indent=1)

    have = sum(1 for r in recs if r["location"])
    print(f"wrote {out}")
    print(f"{len(recs)} events, {have} with a location")


if __name__ == "__main__":
    main()
