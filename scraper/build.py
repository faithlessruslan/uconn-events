"""Build the single-file events site from data/uconn-events.json.

Everything is inlined so index.html opens straight from disk with no server.
"""

import csv
import datetime
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "data", "uconn-events.json")
OUT = os.path.join(ROOT, "index.html")
CSV_OUT = os.path.join(ROOT, "data", "uconn-events.csv")

# House rule: no emojis anywhere, including text that came from the source.
# Event descriptions occasionally carry one (a pumpkin in a Halloween listing),
# so strip them on the way out rather than shipping them.
EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # pictographs, faces, symbols, flags
    "\U00002600-\U000027BF"   # misc symbols and dingbats
    "\U0001F1E6-\U0001F1FF"   # regional indicators
    "\U00002190-\U000021FF"   # arrows (some have emoji presentation)
    "\U00002B00-\U00002BFF"   # more arrows and shapes
    "\U0000FE0F"              # variation selector
    "\U0000200D"              # zero width joiner
    "]+"
)


def strip_emoji(text):
    """Remove emoji and tidy the space they leave behind."""
    if not isinstance(text, str):
        return text
    return re.sub(r"\s{2,}", " ", EMOJI.sub("", text)).strip()


def local(ts):
    """Epoch -> 'YYYY-MM-DD HH:MM' in this machine's timezone."""
    if not ts:
        return ""
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


CSV_FIELDS = [
    ("title", "Title"),
    ("topic", "Topic"),
    ("starts", "Starts"),
    ("ends", "Ends"),
    ("all_day", "All day"),
    ("multi_day", "Multi day"),
    ("location", "Location"),
    ("address", "Address"),
    ("organizer", "Organizer"),
    ("cost", "Cost"),
    ("online", "Online"),
    ("cancelled", "Cancelled"),
    ("url", "URL"),
    ("description", "Description"),
]


def write_csv(records):
    with open(CSV_OUT, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([label for _, label in CSV_FIELDS])
        for r in records:
            writer.writerow([r.get(key, "") for key, _ in CSV_FIELDS])
    print(f"wrote {CSV_OUT} ({len(records)} rows)")


def main():
    with open(SRC, encoding="utf-8") as fh:
        records = json.load(fh)

    # The JSON keeps epoch seconds, which is what Python and most data tools
    # use. JavaScript counts milliseconds, so convert on the way into the page
    # or every timestamp lands in January 1970.
    #
    # Only the fields the panels actually draw are embedded. The full record,
    # descriptions included, stays in data/uconn-events.json and the CSV.
    WANTED = (
        "id", "title", "url", "topic",
        "starts_ts", "ends_ts", "all_day", "multi_day", "cancelled", "location",
    )

    page_records = []
    for r in records:
        r.pop("image", None)
        r["starts"] = local(r.get("starts_ts"))
        r["ends"] = local(r.get("ends_ts"))

        row = {}
        for key in WANTED:
            if key not in r:
                continue
            value = r[key]
            if value is None or value == "":
                continue
            row[key] = value * 1000 if key.endswith("_ts") else strip_emoji(value)
        page_records.append(row)

    for r in records:                       # the CSV export too
        for key in ("title", "description", "location", "organizer"):
            if key in r:
                r[key] = strip_emoji(r[key])
    write_csv(records)

    built = datetime.datetime.now().astimezone().strftime("%B %d, %Y at %I:%M %p")
    payload = json.dumps(page_records, ensure_ascii=False, separators=(",", ":"))

    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as fh:
        page = fh.read()
    page = page.replace("/*__DATA__*/null", payload)
    page = page.replace("__BUILT__", built)

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(page)
    size = os.path.getsize(OUT) / 1024
    print(f"wrote {OUT} ({len(records)} events, {size:,.0f} KB)")


if __name__ == "__main__":
    main()
