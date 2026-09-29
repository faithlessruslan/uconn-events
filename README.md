# UConn Events

One local page that shows every event on the UConn calendar, grouped by day
and split into **live now**, **upcoming**, and **past**.

**Open:** `index.html` — double-click it. No server, no build step, no internet
needed after the data is fetched.

- 1,000 distinct events from 1,648 feed rows
- Light mode is the default, with a dark mode toggle in the corner
- Live count updates every 30 seconds while the page is open

## What the page does

- **Topic filter** — browse by Sports and fitness, Academic and research,
  Health and wellness, Community and service, Music and performance, and more.
  Each chip carries its own count. On a phone the row scrolls sideways
- **Happening now** — a section at the top for whatever is live this minute,
  with a pulsing marker. A week-long exhibition counts as live the whole time
  it runs, not just on day one
- **Day by day** — the rest is grouped under `Today`, `Tomorrow`, then
  `Thursday, October 1` and so on. Runs that span many days lead their
  section instead of being dropped into one arbitrary day
- **Past** — already finished, faded so your eye skips it
- **Cancelled** — pulled out into its own group
- **Search** is the primary control: one wide field for a name, topic, or place
- The place, sort, and date-window dropdowns are gone. One order only,
  soonest first, and the topic row does the browsing
- Press `/` to search, `Esc` or the Clear button to reset

## What a panel shows

A topic label, the title, when, and where. Nothing else.

Cost, host, description, and the "Details" link were deliberately removed. The
panel is a scanning aid, not a replacement for the event page: the title is
the link, so there is nothing in the panel competing with clicking through.

Every panel is exactly the same size, 186px tall, in a grid with even 14px
gutters. The title is clamped to three lines and the place to two, and the
date and place are anchored to the bottom of the panel, so a one-line title
and a three-line title produce the same shape.

## Topics

The UConn calendar has no category field. The API documents an `event_types`
field but does not return it, `/live/json/types` is an empty array, and
neither the calendar page nor an event page carries a type.

So `scraper/topics.py` derives a topic from three things that do exist:

1. the organizer, present on 993 of 1000 records
2. the calendar name in the URL path, such as
   `/jorgensen-center-for-the-performing-arts/`
3. words in the title

First rule wins, so specific rules sit above broad ones. A nutrition expo run
by Dining Services is Food, not Academic, even though a university runs it.

| Topic | Count |
|---|---|
| Sports and fitness | 386 |
| Academic and research | 264 |
| Health and wellness | 115 |
| Community and service | 66 |
| Music and performance | 35 |
| Career and jobs | 33 |
| Arts and exhibits | 30 |
| Campus life | 25 |
| Food and dining | 22 |
| Other | 24 |

`Other` is 2.4%, which is the honest residue rather than a claim of full
accuracy. A topic is a hint, not a fact.

## The look

Built to be pleasant to scan rather than merely legible.

- **Warm paper, not white.** Off-white `#faf9f7` with a soft navy and gold
  wash behind the masthead, so the header reads as a page header and not as a
  block of colour.
- **A serif for the title, sans for everything else.** The serif gives the
  page one editorial note; the body stays in the system UI font for
  readability.
- **Day headers carry the scanning.** A 1,000-event list is unusable as a flat
  grid. Breaking it into days, with `in 3 hr` under each date, is what makes
  it browsable.
- **State is colour, not traffic lights.** Live gets a green left rule and a
  pulsing dot. Past recedes to the page tone. Cancelled is struck through.
- **Cards are only as tall as their content.** `align-items: start` on the
  grid stops short cards from being stretched to match tall neighbours.

## Files

| Path | What |
|---|---|
| `index.html` | The whole site. Self-contained, data inlined. |
| `data/uconn-events.json` | Full records, including descriptions |
| `data/uconn-events.csv` | Same data as a spreadsheet |
| `design/uconn-events-design.pdf` | The Figma design file. Drag onto a Figma canvas. |
| `design/README.md` | How the design was made and how to regenerate it |
| `scraper/config.py` | Page size, worker count, rate limit |
| `scraper/fetch.py` | Cached, rate-limited HTTP with 429 backoff |
| `scraper/scrape.py` | Pulls the API and event pages, shapes the data |
| `scraper/topics.py` | Sorts events into topics from organizer, path, and title |
| `scraper/snapshot.py` | Fast preview using only already-cached pages |
| `scraper/build.py` | Turns the JSON into `index.html` and the CSV |
| `scraper/template.html` | The page itself, with data injected at build time |
| `scraper/make_figma.py` | Builds the Figma design file from the same data |
| `scraper/verify.py` | Re-checks the numbers, the invariants, and the house rules |
| `tools/ux-audit.mjs` | Accessibility and UX audit: axe-core, contrast, tap targets, overflow |
| `tools/shot.mjs` | Screenshot a page at any viewport, for looking at rather than measuring |

## How the data is fetched

Two steps.

**1. The list API.** `https://events.uconn.edu/live/json/events` returns clean
JSON, 100 rows per page, 17 pages. It gives the title, times, cost, and URL.

**2. Each event page.** The API has no location or description, so the scraper
also reads the `schema.org` JSON-LD block on every event page. That adds
location, full description, host organization, and an image.

Pages are cached in `scraper/cache/`, so a rerun is instant and free. A page
that fails is never cached, so a later pass really does retry it.

### Being polite

UConn's calendar rate-limits hard. Measured behaviour:

| Setting | Result |
|---|---|
| 4 workers, 0.2s gap | `429` within 200 pages |
| 3 workers, 1.1s gap | `429` at about 600 pages |
| 1 worker, 1.2s gap | clean, about 0.8 requests/second |
| After a block | clears in roughly 1 minute |

So the scraper uses one worker with a 1.2s gap. When it does see a `429` it
stops the pass, rests 150 seconds, then sweeps only the pages still missing.

One subtle bug worth remembering: the gap has to be measured from the end of
the last request, not its start. Timing from the start silently adds the
response time, which made the real rate four times slower than intended.

A full first build takes about 25 minutes. After that it is seconds.

## The tricky parts

Five traps in this data, all found the hard way.

**1. Timestamps are in seconds, JavaScript counts milliseconds.** The JSON
holds epoch seconds, like any Python tool. Passing `1781150400` to
`new Date()` gives January 1970, so every event showed as "Past" and cards
read "Jan 21". The build converts to milliseconds on the way into the page.
The JSON and CSV keep seconds.

**2. `repeats_end` means two different things.** For a one-off run it is
the real end: the exhibition that ran August 6 to November 5 kept its end
only there, with `date2_iso` empty. But for a recurring event it is when the
*pattern* stops, and UConn sometimes sets that to the year 2123. Using it
blindly made every annual Founders' Day event look like it ran for a century.
The scraper only widens a window when the event is not a recurrence.

**3. The feed lists a run once per day.** The same exhibition came back 38
times, each row on a different date but carrying the same full window. Left
alone, one gallery show filled a third of the screen. Rows sharing an event
id are collapsed, keeping the widest window.

**4. Recurring classes bury everything.** 1,000 events collapse into 569
cards, because group fitness, yoga, and gallery shows repeat dozens of times.
Cards sharing a title and place merge into one card with a date count and a
"Show all" button.

**5. Zero dates exist.** Some recurring events send
`repeats_start: 0000-00-00 00:00:00` as a "no bound" marker. The parser
rejects dates before the year 2000 rather than subtracting them and getting
an 8-billion-second window.

## Number checks

From the finished build:

| Metric | Value |
|---|---|
| API rows | 1,648 |
| Detail pages enriched | 1,644 of 1,648 |
| Events with a location | 1,428 |
| Distinct events after collapsing runs | 1,000 |
| Cards after grouping repeats | 553 |
| Places in the filter | 146 |
| Live at build time | 20 |
| Upcoming | 972 |
| Past | 4 |

`scraper/verify.py` re-checks the important ones, including the two bugs
that are easy to reintroduce: timestamps in seconds instead of milliseconds,
and event windows stretching for years. Run it after any build.

```bash
cd scraper && python3 verify.py
```

## Rebuilding

```bash
cd scraper
python3 -c "import scrape, json; json.dump(scrape.run(), open('../data/uconn-events.json','w'), indent=1)"
python3 build.py
python3 verify.py
```

Then refresh `index.html`.

- To pull fresh copy, delete `scraper/cache/` first.
- To rebuild only the page from data already on disk, run `python3 build.py`.
- To make a fast preview using only cached pages, run `python3 snapshot.py`
  then `python3 build.py`.

## Note on past events

The calendar only offers a rolling window: as of this build it runs from
about June 11 to November 12, 2026, with most of it ahead. The JSON API
silently ignores every date filter tried, so there is no way to ask it for
older events, and `/archive/` is a 404.

That means "Past" is nearly empty today. The section and its logic are
already in place. To build real history, keep appending snapshots to
`data/uconn-events.json` on a schedule.

## Rules followed

- `events.uconn.edu/robots.txt` only blocks `?replytocom`, so crawling is fine
- One request per second or slower, with a named user agent
- Nothing behind a login is touched
- Event text is shown as-is with a link back to the official page
