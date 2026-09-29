"""Pull every event from the UConn calendar and enrich it from its detail page.

The list API gives times and titles. Each event page carries a schema.org
JSON-LD block with location, description, organizer and an image, so we read
that too.
"""

import concurrent.futures
import datetime
import html
import json
import re
import sys

import config
import fetch
from topics import add_topics

LD_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.S | re.I
)


def _clean(text):
    """Unescape entities and collapse whitespace."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", html.unescape(str(text))).strip()


# --------------------------------------------------------------------------
# Step 1: the list API
# --------------------------------------------------------------------------

def list_events():
    """Walk the paged JSON API and return the raw event dicts.

    The feed emits one row per occurrence, so it can list the same weekly
    event on ten different days. Each row is a real event on that day, so we
    keep them all but drop exact repeats of the same event on the same day.
    """
    first = fetch.get(f"{config.API}?per_page={config.PER_PAGE}&page=1")
    if not first:
        raise SystemExit("Could not reach the events API.")
    meta = json.loads(first)["meta"]
    pages = meta["total_pages"]
    print(f"API says {meta['total_results']} rows across {pages} pages")

    raw = json.loads(first)["data"]
    for page in range(2, pages + 1):
        body = fetch.get(f"{config.API}?per_page={config.PER_PAGE}&page={page}")
        if not body:
            print(f"  page {page} failed, skipping")
            continue
        raw.extend(json.loads(body)["data"])

    seen = set()
    out = []
    for event in raw:
        key = (event.get("id"), event.get("date_ts"))
        if key in seen:
            continue
        seen.add(key)
        out.append(event)
    if len(out) != len(raw):
        print(f"  {len(raw)} rows -> {len(out)} after dropping same-day repeats")
    return out


# --------------------------------------------------------------------------
# Step 2: the detail page JSON-LD
# --------------------------------------------------------------------------

def detail(url):
    """Return the JSON-LD dict for one event page, or {} on failure."""
    body = fetch.get(url)
    if not body:
        return {}
    match = LD_RE.search(body)
    if not match:
        return {}
    blob = match.group(1).replace("/*<![CDATA[*/", "").replace("/*]]>*/", "")
    try:
        return json.loads(blob.strip())
    except json.JSONDecodeError:
        return {}


def _place(loc):
    """Flatten schema.org's location, which may be a list or a dict."""
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    if not isinstance(loc, dict):
        return "", ""
    name = _clean(loc.get("name"))
    addr = loc.get("address") or {}
    if isinstance(addr, list):
        addr = addr[0] if addr else {}
    street = _clean(addr.get("streetAddress")) if isinstance(addr, dict) else ""
    return name, street


def enrich(event):
    """Merge one detail page into a list-API event. Runs in a worker thread."""
    data = detail(event.get("url", ""))
    if not data:
        return False
    event["description"] = _clean(data.get("description"))
    name, street = _place(data.get("location"))
    event["location"] = name
    event["address"] = street
    org = data.get("organizer") or {}
    if isinstance(org, list):
        org = org[0] if org else {}
    event["organizer"] = _clean(org.get("name")) if isinstance(org, dict) else ""
    img = data.get("image") or {}
    if isinstance(img, list):
        img = img[0] if img else {}
    event["image"] = img.get("url", "") if isinstance(img, dict) else ""
    status = data.get("eventStatus", "")
    event["cancelled"] = "Cancelled" in status
    return True


def enrich_all(events, passes=None):
    """Enrich every event, sweeping repeatedly over whatever failed.

    A 429 stops a pass early. We rest, then sweep the leftovers. Already
    cached pages cost nothing, so each pass only touches what is missing.
    """
    passes = passes or config.PASSES

    for attempt in range(passes):
        todo = [e for e in events if not e.get("_enriched")]
        if not todo:
            break
        print(f"pass {attempt + 1}/{passes}: {len(todo)} pages to fetch")
        done = 0
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=config.MAX_WORKERS
        ) as pool:
            for event, ok in zip(todo, pool.map(enrich, todo)):
                if ok:
                    event["_enriched"] = True
                    done += 1
                if fetch.BLOCKED[0]:
                    pool.shutdown(wait=False, cancel_futures=True)
                    break
        print(f"  got {done}")
        if not fetch.BLOCKED[0] and done == len(todo):
            break
        fetch.wait_out_cooldown()

    total = sum(1 for e in events if e.get("_enriched"))
    located = sum(1 for e in events if e.get("location"))
    print(f"enriched {total}/{len(events)}, {located} have a location")
    return events


# --------------------------------------------------------------------------
# Step 3: shape it
# --------------------------------------------------------------------------

UTC_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})$")


def utc_ts(value):
    """Parse the API's UTC strings ('2026-11-05 05:00:00') into an epoch int.

    Returns None for the zero dates the API uses as 'no bound' sentinels
    (it literally sends 0000-00-00 00:00:00 on some recurring events).
    """
    if not value:
        return None
    match = UTC_RE.match(str(value).strip())
    if not match:
        return None
    y, mo, d, h, mi, s = (int(g) for g in match.groups())
    if y < 2000 or not (1 <= mo <= 12) or not (1 <= d <= 31):
        return None
    try:
        return int(datetime.datetime(y, mo, d, h, mi, s,
                                     tzinfo=datetime.timezone.utc).timestamp())
    except ValueError:
        return None


def normalize(e):
    """Turn a raw event into the flat record the site consumes.

    Timing is the subtle part, because `repeats_*` means two different things:

    * `repeats: "yearly"` / `"weekly"` -> the event recurs. `date_ts` is this
      one occurrence and `repeats_end` is when the *pattern* stops (sometimes
      the year 2123). The event itself lasts one day, so the pattern end must
      be ignored or every annual event looks like it runs for a century.

    * `repeats` empty -> the event is one continuous run. Then the real end
      lives in `repeats_end`, not in `date2_ts`. This is the case for a
      months-long exhibition.

    So: a run is only widened when it is not a recurrence.
    """
    all_day = bool(e.get("is_all_day"))
    occ = e.get("date_ts")
    occ_end = e.get("date2_ts")
    recurs = bool(_clean(e.get("repeats")))

    run_start = utc_ts(e.get("repeats_start"))
    run_end = utc_ts(e.get("repeats_end"))

    starts = occ
    ends = occ_end

    if not recurs and run_start and run_end:
        # One continuous run. Ignore near-zero-length bounds.
        if run_end - run_start >= 3600:
            starts = min(x for x in (occ, run_start) if x)
            ends = run_end

    return {
        "id": e.get("id"),
        "title": _clean(e.get("title")),
        "url": e.get("url", ""),
        "starts_ts": starts,
        "ends_ts": ends,
        "occurrence_ts": occ,
        "all_day": all_day,
        "multi_day": bool(starts and ends and (ends - starts) >= 86400),
        "repeats": _clean(e.get("repeats")),
        "date_label": _clean(e.get("date")),
        "time_label": _clean(e.get("date_time")),
        "cost": _clean(e.get("cost")),
        "location": e.get("location", ""),
        "address": e.get("address", ""),
        "organizer": e.get("organizer", ""),
        "description": e.get("description", ""),
        "image": e.get("image", ""),
        "online": bool(e.get("is_online")),
        "online_url": e.get("online_url") or "",
        "cancelled": bool(e.get("cancelled") or e.get("is_canceled")),
    }


def dedupe(records):
    """Collapse rows that share an event id.

    The feed lists a long run once per day it happens: the same exhibition
    came back 38 times, each row anchored on a different date but describing
    the same run. Every row carries the run's real window, so keep the
    widest one and drop the rest.
    """
    best = {}
    for r in records:
        key = r.get("id")
        span = (r.get("ends_ts") or 0) - (r.get("starts_ts") or 0)
        if key not in best:
            best[key] = (span, r)
        elif span > best[key][0]:
            best[key] = (span, r)
    out = [r for _, r in best.values()]
    if len(out) != len(records):
        print(f"collapsed {len(records)} rows into {len(out)} events")
    return out


def run():
    raw = list_events()
    raw = enrich_all(raw)
    records = [normalize(e) for e in raw]
    before = len(records)
    records = dedupe(records)
    if before != len(records):
        print(f"dropped {before - len(records)} duplicate occurrences")
    add_topics(records)
    counts = {}
    for r in records:
        counts[r["topic"]] = counts.get(r["topic"], 0) + 1
    top = ", ".join(f"{t} {n}" for t, n in
                    sorted(counts.items(), key=lambda x: -x[1]))
    print(f"topics: {top}")
    records.sort(key=lambda r: (r["starts_ts"] or 0, r["title"]))
    return records


if __name__ == "__main__":
    out = run()
    json.dump(out, sys.stdout, indent=1)
