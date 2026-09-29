"""Sort events into topics.

The UConn calendar has no category field. The API offers `event_types`, the
documented `response_fields` parameter does not return it, `/live/json/types`
is an empty array, and neither the calendar page nor an event page carries a
type. So topics are derived from three things that do exist:

  1. the organizer, when the feed provides one (993 of 1000 records)
  2. the calendar in the URL path, e.g. /jorgensen-center-for-the-performing-arts/
  3. words in the title

Order matters. The first rule that matches wins, so specific rules sit above
broad ones: a "Nutrition Expo" run by Dining Services is Food, not Academic,
even though a university runs it.

Everything is checked case-insensitively against one combined haystack.
"""

import re

# (topic, [substrings that must appear in organizer + path + title])
RULES = [
    ("Sports and fitness", [
        "uconn recreation", "athletics", "huskies", "intramural",
        "group fitness", "yoga", "spin", "zumba", "pilates", "crossfit",
        "swim", "aquatic", "climbing", "rowing", "club sport", "5k",
        "fun run", "walking challenge", "basketball", "soccer", "hockey",
        "volleyball", "softball", "baseball", "tennis", "track and field",
    ]),
    ("Music and performance", [
        "jorgensen", "von der mehden", "recital", "concert", "symphony",
        "orchestra", "chorale", "choir", "ensemble", "jazz", "opera",
        "performing arts", "theater", "theatre", "dance", "cabaret",
        "musical", "philharmonic",
    ]),
    ("Arts and exhibits", [
        "gallery", "exhibition", "exhibit", "benton", "museum", "art ",
        "sculpture", "painting", "photography", "makerspace", "ceramics",
        "ballroom", "dodd center", "archives",
    ]),
    ("Food and dining", [
        "dining", "food", "menu", "meal", "lunch", "breakfast", "dinner",
        "nutrition", "cooking", "culinary", "coffee", "farmers market",
        "food pantry", "taste", "chef",
    ]),
    ("Health and wellness", [
        "student health", "wellness", "counseling", "mental health",
        "medical", "flu shot", "vaccine", "clinic", "therapy", "therapy dog",
        "pet therapy", "recovery", "mindfulness", "meditation", "sleep",
        "recreation center", "covid", "blood drive", "first aid", "cpr",
        "sexual health", "disability",
    ]),
    ("Career and jobs", [
        "career", "internship", "resume", "job", "employer", "recruiter",
        "networking", "interview", "co-op", "fellowship", "hiring",
        "entrepreneurship", "innovation zone",
    ]),
    ("Academic and research", [
        "department", "school of", "college of", "law school", "school of law",
        "law library", "seminar", "colloquium", "lecture", "research",
        "thesis", "dissertation", "defense", "symposium", "conference",
        "workshop", "library", "libraries", "cetl", "teaching", "advising",
        "academic", "honors", "provost", "faculty", "course", "exam",
        "study", "tutoring", "writing", "laboratory", "lab", "institute",
        "center for", "science", "mathematics", "physics", "chemistry",
        "biology", "engineering", "economics", "history", "philosophy",
        "psychology", "sociology", "graduate school", "registrar",
        "enrollment", "sea grant", "seagrant", "learning communities",
        "campus forum", "jd application", "panel", "lecture series",
        "poetry", "brainstorming", "preparedness", "resilience",
    ]),
    ("Community and service", [
        "extension", "4-h", "volunteer", "community", "outreach", "service",
        "veterans", "military", "rainbow center", "cultural center",
        "international", "global", "sustainability", "food share",
        "fundraiser", "donation", "drive", "worship", "faith", "pride",
    ]),
    ("Campus life", [
        "student union", "subog", "fraternity", "sorority", "greek",
        "club", "student activities", "orientation", "welcome", "homecoming",
        "residence", "housing", "commuter", "first year", "transfer",
        "student government", "usg", "social", "mixer", "game night",
        "movie", "film", "bingo", "karaoke", "trivia",
    ]),
]

OTHER = "Other"

COMPILED = [(topic, [s.lower() for s in keys]) for topic, keys in RULES]

# Topic order for the filter chips: the big and broad ones first, so a reader
# meets them in a sensible order rather than by raw count.
TOPIC_ORDER = [
    "Academic and research",
    "Sports and fitness",
    "Music and performance",
    "Arts and exhibits",
    "Food and dining",
    "Health and wellness",
    "Career and jobs",
    "Campus life",
    "Community and service",
    OTHER,
]


def calendar_of(url):
    """The calendar name in an event URL, which is a useful topic hint."""
    m = re.match(r"https?://events\.uconn\.edu/([^/]+)/", url or "")
    return "" if not m else m.group(1).replace("-", " ")


def classify(record):
    """Return one topic for a record. Never raises, never returns empty."""
    hay = " ".join([
        record.get("organizer") or "",
        calendar_of(record.get("url")),
        record.get("title") or "",
    ]).lower()
    # A generic calendar path like /live/ or /event/ carries no signal.
    hay = hay.replace("live ", " ")
    for topic, keys in COMPILED:
        for key in keys:
            if key in hay:
                return topic
    return OTHER


def add_topics(records):
    for r in records:
        r["topic"] = classify(r)
    return records
