"""Settings for the UConn events scraper."""

BASE = "https://events.uconn.edu"
API = BASE + "/live/json/events"

# 100 is the API's max page size.
PER_PAGE = 100

# Be a good citizen. Measured: three workers at a 1.1s gap tripped a 429
# within about 600 pages. One worker at 1.2s has stayed clean.
MAX_WORKERS = 1
MIN_INTERVAL = 1.2

# How long to rest after a 429. The block cleared in about a minute when
# tested by hand, so give it real room and back off further if it repeats.
COOL_OFF = 150.0

# How many sweeps to make over pages that failed.
PASSES = 8

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36 UConnEventsIndex/1.0")
