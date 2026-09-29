"""Generate a Figma-ready design file from the live event data.

Output is a PDF, printed from a purpose-built HTML page by headless Chrome.
PDF is the right carrier here: Figma imports it with real vector shapes and
*editable text runs*, which an SVG import cannot be trusted to do (a valid
looking SVG rendered its own text as invisible in testing).

Page size is written in points because Chrome multiplies CSS pixels by 0.75 on
the way to PDF, so a 1280px-wide layout needs `size: 960pt`.

    python3 make_figma.py      # writes design/uconn-events-design.pdf
"""

import datetime
import html
import json
import os
import subprocess
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "data", "uconn-events.json")
DESIGN = os.path.join(ROOT, "design")
HTML_OUT = os.path.join(DESIGN, "uconn-events-design.html")
PDF_OUT = os.path.join(DESIGN, "uconn-events-design.pdf")

CHROME = ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

# Frames are laid out at 1280 CSS px wide. Chrome scales px -> pt by 0.75,
# so the PDF page has to be declared at 0.75 of that.
PX_W = 1280
PT_PER_PX = 0.75
PAGE_PT_W = PX_W * PT_PER_PX
PAGE_PT_H = 1500                     # 2000 CSS px tall
PAGE_PX_H = PAGE_PT_H / PT_PER_PX

LIGHT = {
    "paper": "#faf9f7", "paper2": "#f2f0ec", "card": "#ffffff",
    "line": "#e7e4de", "ink": "#1c1b19", "ink2": "#4a4844",
    "ink3": "#7d7a73", "ink4": "#a8a49c", "navy": "#0a3d62",
    "navyWash": "#eaf1f7", "gold": "#a9761b", "goldWash": "#fbf2e0",
    "live": "#12704a", "liveWash": "#e6f4ec", "rose": "#a03a3a",
    "roseWash": "#fbecec", "washA": "#eaf1f7", "washB": "#fbf2e0",
}
DARK = {
    "paper": "#14161a", "paper2": "#1a1d22", "card": "#1e2127",
    "line": "#2c3038", "ink": "#ecedf0", "ink2": "#c3c7cf",
    "ink3": "#9298a2", "ink4": "#6d737d", "navy": "#7fb6de",
    "navyWash": "#1b2632", "gold": "#d8a64a", "goldWash": "#2c2415",
    "live": "#52cf9c", "liveWash": "#16301f", "rose": "#e88a8a",
    "roseWash": "#331c1c", "washA": "#1b2632", "washB": "#2c2415",
}

SANS = "Helvetica Neue, Helvetica, Arial, sans-serif"
SERIF = "Iowan Old Style, Palatino, Georgia, serif"

M = 90                               # side margin
CONTENT = PX_W - 2 * M
COL = (CONTENT - 2 * 16) / 3         # three columns with 16px gutters

pages = []


def e(t):
    return html.escape(str(t), quote=True)


def box(x, y, w, h, **style):
    """Absolutely positioned div. Keeps the print layout deterministic."""
    css = ";".join(f"{k.replace('_', '-')}:{v}" for k, v in style.items())
    return (f'<div style="position:absolute;left:{x}px;top:{y}px;'
            f'width:{w}px;height:{h}px;{css}"></div>')


def label(x, y, w, text, size=13, colour="#000", weight="400",
          family=SANS, lh=None, align="left", spacing=None, transform=None):
    css = (f"font-family:{family};font-size:{size}px;color:{colour};"
           f"font-weight:{weight};text-align:{align}")
    if lh:
        css += f";line-height:{lh}px"
    if spacing:
        css += f";letter-spacing:{spacing}px"
    if transform:
        css += f";text-transform:{transform}"
    return (f'<div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;'
            f'{css}">{e(text)}</div>')


def rule(x, y, w, colour):
    return box(x, y, w, 1, background=colour)


# ------------------------------------------------------------------ icons
def svg(x, y, size, colour, body, sw=1.7):
    return (f'<svg style="position:absolute;left:{x}px;top:{y}px" '
            f'width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{colour}" stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round">{body}</svg>')


ICON_CLOCK = '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>'
ICON_PIN = ('<path d="M12 21s6.5-6.2 6.5-11a6.5 6.5 0 0 0-13 0C5.5 14.8 12 21 '
            '12 21z"/><circle cx="12" cy="10" r="2.4"/>')
ICON_HOST = ('<path d="M4 20h16M6 20V9l6-4.5L18 9v11"/>'
             '<path d="M10 20v-4h4v4"/>')
ICON_SEARCH = ('<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>')


# ------------------------------------------------------------------ chrome
def masthead(c, y=0):
    """Wash band, brand row, and the live stat line.

    The two washes are painted first and then the band is painted back over
    the lower part, which keeps them in the header without a clip path.
    Painting them after the content (the obvious order) put colour over the
    search box, because a div circle ignores the band's height.
    """
    parts = [
        box(0, y, PX_W, 600, background=c["paper"]),
    ]
    # --- washes ---
    parts += [
        f'<div style="position:absolute;left:-200px;top:{y - 330}px;'
        f'width:680px;height:680px;border-radius:50%;'
        f'background:{c["washA"]}"></div>',
        f'<div style="position:absolute;left:950px;top:{y - 350}px;'
        f'width:620px;height:620px;border-radius:50%;'
        f'background:{c["washB"]}"></div>',
    ]
    # --- paper back over everything below the band ---
    parts.append(box(0, y + 178, PX_W, 600, background=c["paper"]))
    # a translucent veil softens the very bottom edge of each wash
    parts.append(box(0, y + 120, PX_W, 58, background=c["paper"],
                     opacity=0.55))
    # --- content ---
    parts += [
        box(M, y + 40, 38, 38, background=c["navy"], border_radius="10px"),
        label(M, y + 50, 38, "UC", 15, "#ffffff", "700", SERIF,
              align="center"),
        label(M + 54, y + 45, 460, "UConn Events", 30, c["ink"], "600",
              SERIF, spacing=-0.6),
        box(PX_W - M - 108, y + 42, 108, 34, background=c["card"],
            border=f"1px solid {c['line']}", border_radius="8px"),
        label(PX_W - M - 108, y + 51, 108,
              "Light mode" if c is DARK else "Dark mode", 13.5, c["ink"],
              align="center"),
        rule(M, y + 100, CONTENT, c["line"]),
        label(M, y + 118, 90, "3:00 PM", 13, c["ink2"], "600"),
        box(M + 66, y + 123, 3, 3, background=c["ink4"], border_radius="50%"),
        label(M + 78, y + 118, 30, "19", 13, c["live"], "700"),
        label(M + 98, y + 118, 130, "live right now", 13, c["ink3"]),
        box(M + 190, y + 123, 3, 3, background=c["ink4"], border_radius="50%"),
        label(M + 202, y + 118, 40, "970", 13, c["ink"], "700"),
        label(M + 230, y + 118, 130, "still to come", 13, c["ink3"]),
        box(M + 322, y + 123, 3, 3, background=c["ink4"], border_radius="50%"),
        label(M + 334, y + 118, 50, "1000", 13, c["ink"], "700"),
        label(M + 372, y + 118, 160, "in this snapshot", 13, c["ink3"]),
        rule(0, y + 177, PX_W, c["line"]),
    ]
    return "".join(parts)


def controls(c, y=178):
    parts = [
        box(0, y, PX_W, 116, background=c["paper"]),
        box(M, y + 14, 552, 38, background=c["card"],
            border=f"1px solid {c['line']}", border_radius="8px"),
        svg(M + 12, y + 25, 15, c["ink4"], ICON_SEARCH),
        label(M + 36, y + 23, 500, "Search a class, club, talk, or place...",
              13.5, c["ink4"]),
        box(M + 564, y + 14, 232, 38, background=c["card"],
            border=f"1px solid {c['line']}", border_radius="8px"),
        label(M + 578, y + 23, 200, "Every place", 13.5, c["ink"]),
        svg(M + 760, y + 26, 15, c["ink4"],
            '<path d="M6 9l6 6 6-6"/>', 1.8),
        box(M + 808, y + 14, 176, 38, background=c["card"],
            border=f"1px solid {c['line']}", border_radius="8px"),
        label(M + 822, y + 23, 140, "Starting soonest", 13.5, c["ink"]),
        svg(M + 944, y + 26, 15, c["ink4"],
            '<path d="M6 9l6 6 6-6"/>', 1.8),
        label(_r := PX_W - M - 260, y + 23, 260, "570 cards / 1000 events",
              13, c["ink3"], align="right"),
    ]

    # Two chip rows
    cy = y + 64
    x = M
    for text, on, n in (("All", True, "1000"), ("Live", False, "19"),
                        ("Upcoming", False, "970"), ("Past", False, "7")):
        w = 26 + len(text) * 7.4 + (28 if n else 0)
        parts.append(box(x, cy, w, 32,
                         background=c["ink"] if on else c["card"],
                         border=f"1px solid {c['ink'] if on else c['line']}",
                         border_radius="16px"))
        parts.append(label(x + 13, cy + 7, 120, text, 13.5,
                           c["paper"] if on else c["ink"],
                           "600" if on else "400"))
        if n:
            parts.append(label(x + 13 + len(text) * 7.5, cy + 9, 60, n, 11.5,
                               c["paper"] if on else c["ink4"], "500"))
        x += w + 7

    x += 16
    for text, on in (("Any date", True), ("Today", False),
                     ("Tomorrow", False), ("Next 7 days", False),
                     ("Next 30 days", False)):
        w = 26 + len(text) * 7.4
        parts.append(box(x, cy, w, 32,
                         background=c["ink"] if on else c["card"],
                         border=f"1px solid {c['ink'] if on else c['line']}",
                         border_radius="16px"))
        parts.append(label(x + 13, cy + 7, 140, text, 13.5,
                           c["paper"] if on else c["ink"],
                           "600" if on else "400"))
        x += w + 7

    parts.append(rule(0, y + 115, PX_W, c["line"]))
    return "".join(parts)


def dayhead(c, y, title, rel, count, pill=None):
    """Day label row. Text widths are estimated for the gap only, so a
    slightly wrong estimate changes spacing, not alignment."""
    parts = []
    x = M
    if pill:
        w = 22 + len(pill) * 7.8
        parts.append(box(M, y - 12, w, 20,
                         background=c["liveWash"] if pill == "TODAY"
                         else c["navyWash"], border_radius="5px"))
        parts.append(label(M, y - 8, w, pill, 10.5,
                           c["live"] if pill == "TODAY" else c["navy"],
                           "700", align="center", spacing=0.7))
        x = M + w + 12
    parts.append(label(x, y - 8, 460, title, 12.5, c["ink2"], "600",
                       spacing=0.6, transform="uppercase"))
    parts.append(label(x + len(title) * 8.6 + 14, y - 8, 260, rel, 12.5,
                       c["ink4"]))
    parts.append(label(PX_W - M - 120, y - 8, 120, str(count), 12.5,
                       c["ink4"], align="right"))
    parts.append(rule(M, y + 12, CONTENT, c["line"]))
    return "".join(parts)


# ------------------------------------------------------------------ card
def card(c, x, y, w, ev, state="soon", date_line="", rel="", grouped=0,
         expanded=False, height=None):
    """One event card. Returns (markup, height)."""
    parts = []
    pad = 17
    ix, iw = x + pad, w - 2 * pad
    cy = y + 16                       # content cursor, absolute

    if state == "live":
        parts.append(box(ix, cy + 2, 7, 7, background=c["live"],
                         border_radius="50%"))
        parts.append(label(ix + 13, cy - 2, 200, "LIVE NOW", 11, c["live"],
                           "700", spacing=0.8))
        cy += 24
    elif state == "cancel":
        parts.append(box(ix, cy - 2, 80, 19, background=c["roseWash"],
                         border_radius="5px"))
        parts.append(label(ix, cy + 1, 80, "CANCELLED", 10.5, c["rose"],
                           "700", align="center", spacing=0.5))
        cy += 24

    # Title. Wrapped by hand so the card height is knowable in advance.
    title_chars = max(int(iw / (16.5 * 0.52)), 10)
    rows = textwrap.wrap(ev["title"], title_chars)[:3]
    for r in rows:
        parts.append(label(ix, cy, iw, r, 16.5, c["ink"], "600", lh=22,
                           spacing=-0.2))
        cy += 22
    cy += 8

    parts.append(svg(ix, cy + 1, 15, c["ink4"], ICON_CLOCK, 1.6))
    bold = date_line or "All day"
    parts.append(label(ix + 21, cy, iw - 21, bold, 13.5, c["ink"], "600"))
    if rel:
        parts.append(label(ix + 21 + len(bold) * 7.1 + 8, cy, 120,
                           "- " + rel, 12.5, c["ink4"]))
    cy += 21

    if ev.get("location"):
        parts.append(svg(ix, cy + 1, 15, c["ink4"], ICON_PIN, 1.6))
        parts.append(label(ix + 21, cy, iw - 21, ev["location"], 13.5,
                           c["ink2"]))
        cy += 21

    if ev.get("organizer"):
        parts.append(svg(ix, cy + 1, 15, c["ink4"], ICON_HOST, 1.6))
        org_chars = max(int((iw - 21) / (13.5 * 0.52)), 10)
        for r in textwrap.wrap(ev["organizer"], org_chars)[:2]:
            parts.append(label(ix + 21, cy, iw - 21, r, 13.5, c["ink2"],
                               lh=19))
            cy += 19

    desc = ev.get("description", "")
    if desc:
        cy += 8
        desc_chars = max(int(iw / (13.5 * 0.52)), 10)
        for r in textwrap.wrap(desc, desc_chars)[:3]:
            parts.append(label(ix, cy, iw, r, 13.5, c["ink3"], lh=20))
            cy += 20
        if len(desc) > len("".join(textwrap.wrap(desc, desc_chars)[:3])):
            parts.append(label(ix, cy, 120, "Read more", 12.5, c["navy"]))

    # Footer tags. A tag row needs air above it or it collides with the
    # description's last line.
    cy += 22
    fx = ix
    tags = []
    if ev.get("cost"):
        low = ev["cost"].lower()
        if low in ("free", "0", "$0"):
            tags.append(("Free", c["liveWash"], c["live"]))
        elif ev["cost"][:1].isdigit():
            tags.append(("$" + ev["cost"], c["goldWash"], c["gold"]))
    if grouped > 1:
        tags.append((f"{grouped} dates", c["ink"], c["paper"]))
    if ev.get("multi_day") and state != "past":
        tags.append(("Multi-day", c["navyWash"], c["navy"]))
    if ev.get("online"):
        tags.append(("Online", c["paper2"], c["ink3"]))
    for text, bg, fg in tags:
        tw = 16 + len(text) * 6.7
        parts.append(box(fx, cy - 2, tw, 20, background=bg,
                         border_radius="5px"))
        parts.append(label(fx, cy + 2, tw, text, 11.5, fg, "600",
                           align="center"))
        fx += tw + 6
    parts.append(label(x + w - pad - 70, cy + 2, 70, "Details", 12.5,
                       c["navy"], align="right"))
    cy += 22

    if grouped > 1:
        parts.append(box(ix, cy, 152, 28, background=c["paper2"],
                         border=f"1px solid {c['line']}", border_radius="8px"))
        parts.append(label(ix, cy + 6, 152, f"Show all {grouped} dates", 12.5,
                           c["ink2"], align="center"))
        cy += 28
        if expanded:
            cy += 12
            parts.append(rule(ix, cy, iw, c["line"]))
            cy += 12
            for extra in ("Monday, October 5", "Tuesday, October 6"):
                parts.append(label(ix, cy, iw - 90, extra, 13, c["ink"], "600"))
                parts.append(label(x + w - pad - 90, cy, 90, "9am - 5pm", 13,
                                   c["ink2"], align="right"))
                cy += 24

    h = height or (cy - y + 14)

    # Card surface goes down first so it sits under the content.
    shell = [box(x, y, w, h,
                 background=c["paper2"] if state == "past" else c["card"],
                 border=f"1px solid {c['line']}", border_radius="12px")]
    if state == "live":
        shell.append(box(x, y, 3, h, background=c["live"],
                         border_radius="12px 0 0 12px"))
    if state == "past":
        shell.append(box(x, y, w, h, background=c["paper"], opacity=0.5,
                         border_radius="12px"))
    return "".join(shell + parts), h


def card_row(c, x, y, evs, dates, state="soon", grouped=None, height=None):
    heights = []
    parts = []
    for i, ev in enumerate(evs):
        mark, h = card(c, x + i * (COL + 16), y, COL, ev, state,
                       dates[i] if i < len(dates) else "",
                       rel="in 3 hr",
                       grouped=(grouped or [0] * len(evs))[i],
                       height=height)
        parts.append(mark)
        heights.append(h)
    return "".join(parts), (max(heights) if heights else 0)


# ------------------------------------------------------------------ pages
def page(c, body, height_css=2000):
    pages.append(
        f'<div class="page" style="background:{c["paper"]};'
        f'height:{height_css}px">{body}</div>')
    return height_css


def page_main(c, live, soon, dark=False):
    parts = [masthead(c), controls(c)]
    y = 350
    parts.append(dayhead(c, y, "Happening now", "right this minute", len(live)))
    y += 34
    mark, h = card_row(c, M, y, live[0:3], ["All day",
                                            "Thu, Aug 6 - Thu, Nov 5, all day",
                                            "Mon, Aug 31 - Wed, Sep 30, all day"],
                       "live")
    parts.append(mark)
    y += h + 16
    mark, h = card_row(c, M, y, live[3:6], ["Mon, Aug 31 - Wed, Sep 30, all day",
                                            "Mon, Sep 21 - Sun, Oct 4, all day",
                                            "Sun, Sep 27 - Thu, Oct 1, all day"],
                       "live")
    parts.append(mark)
    y += h + 30

    parts.append(dayhead(c, y, "Wednesday, September 30", "in 21 hr", 57,
                         pill="TOMORROW"))
    y += 34
    mark, h = card_row(c, M, y, soon[0:3], ["All day", "All day", "8:30am - 10:30am"],
                       "soon", grouped=[13, 0, 0])
    parts.append(mark)
    y += h + 16
    mark, h = card_row(c, M, y, soon[3:6], ["9am - 12pm", "9am - 6pm",
                                            "9:30am - 10:30am"], "soon")
    parts.append(mark)
    y += h + 40

    parts.append(dayhead(c, y, "Thursday, October 1", "in 2 days", 41))
    y += 34
    mark, h = card_row(c, M, y, soon[0:3], ["All day", "All day", "All day"],
                       "soon")
    parts.append(mark)
    return page(c, "".join(parts))


def page_states(c, live, soon):
    parts = [
        label(M, 50, 700, "States", 27, c["ink"], "600", SERIF),
        label(M, 86, 900, "Expanded repeats, cancelled, past, and no results.",
              14, c["ink2"]),
    ]
    y = 140
    parts.append(label(M, y, 400, "EXPANDED REPEAT", 12.5, c["ink2"], "600",
                       spacing=0.6))
    parts.append(rule(M, y + 20, CONTENT, c["line"]))
    y += 36
    mark, _ = card(c, M, y, COL, soon[0], "soon", "All day", "in 9 hr",
                   grouped=13, expanded=True, height=440)
    parts.append(mark)
    mark, _ = card(c, M + COL + 16, y, COL, soon[1], "soon", "9am - 5pm",
                   "in 4 hr", height=440)
    parts.append(mark)
    mark, _ = card(c, M + 2 * (COL + 16), y, COL, soon[2], "cancel",
                   "9am - 12pm", "in 18 hr", height=440)
    parts.append(mark)
    y += 476

    parts.append(label(M, y, 400, "PAST", 12.5, c["ink2"], "600",
                       spacing=0.6))
    parts.append(rule(M, y + 20, CONTENT, c["line"]))
    y += 36
    for i, ev in enumerate(soon[3:6]):
        mark, _ = card(c, M + i * (COL + 16), y, COL, ev, "past", "All day",
                       "3 days ago", height=210)
        parts.append(mark)
    y += 246

    parts.append(label(M, y, 400, "NO RESULTS", 12.5, c["ink2"], "600",
                       spacing=0.6))
    parts.append(rule(M, y + 20, CONTENT, c["line"]))
    y += 46
    parts.append(box(M, y, CONTENT, 200, background=c["card"],
                     border=f"1px solid {c['line']}", border_radius="12px"))
    parts.append(label(M, y + 62, CONTENT, "Nothing matches that", 18,
                       c["ink"], "600", SERIF, align="center"))
    parts.append(label(M, y + 92, CONTENT,
                       "Try a wider date range, or clear the search.", 13.5,
                       c["ink3"], align="center"))
    parts.append(box(PX_W / 2 - 62, y + 122, 124, 34, background=c["card"],
                     border=f"1px solid {c['line']}", border_radius="8px"))
    parts.append(label(PX_W / 2 - 62, y + 131, 124, "Reset filters", 13.5,
                       c["ink"], align="center"))
    return page(c, "".join(parts))


def page_tokens(c):
    parts = [
        label(M, 50, 700, "Foundations", 27, c["ink"], "600", SERIF),
        label(M, 86, 900, "Colour and type, named to match the stylesheet.",
              14, c["ink2"]),
    ]
    y = 140
    parts.append(label(M, y, 400, "COLOUR", 12.5, c["ink2"], "600",
                       spacing=0.6))
    parts.append(rule(M, y + 20, CONTENT, c["line"]))
    y += 40
    names = [
        ("paper", "Page background"), ("card", "Card surface"),
        ("line", "Hairline rules"), ("ink", "Primary text"),
        ("ink3", "Secondary text"), ("navy", "Links and accents"),
        ("live", "Live state"), ("gold", "Paid cost"),
        ("rose", "Cancelled"),
    ]
    for i, (key, desc) in enumerate(names):
        cx = M + (i % 3) * 240
        cy = y + (i // 3) * 84
        parts.append(box(cx, cy, 48, 48, background=LIGHT[key],
                         border=f"1px solid {c['line']}",
                         border_radius="10px"))
        parts.append(box(cx + 24, cy, 24, 48, background=DARK[key],
                         border_radius="0 10px 10px 0"))
        parts.append(label(cx + 62, cy + 6, 160, key, 13.5, c["ink"], "600"))
        parts.append(label(cx + 62, cy + 26, 160, desc, 12, c["ink3"]))
    y += 3 * 84 + 40

    parts.append(label(M, y, 400, "TYPE", 12.5, c["ink2"], "600",
                       spacing=0.6))
    parts.append(rule(M, y + 20, CONTENT, c["line"]))
    y += 44
    rows = [
        ("Page title", 30, "600", SERIF),
        ("Day header", 12.5, "600", SANS),
        ("Card title", 16.5, "600", SANS),
        ("Body", 13.5, "400", SANS),
        ("Meta", 12.5, "400", SANS),
    ]
    for name, size, weight, fam in rows:
        parts.append(label(M, y, 520, "UConn Events", size, c["ink"], weight,
                           fam))
        fam_name = "serif" if fam == SERIF else "sans"
        parts.append(label(M + 560, y + (size - 12) / 2, 220,
                           f"{size}px / {weight} / {fam_name}", 12, c["ink4"]))
        parts.append(label(M + 800, y + (size - 12) / 2, 220, name, 12,
                           c["ink3"]))
        y += size + 30
    return page(c, "".join(parts))


# ------------------------------------------------------------------ main
def pick(data):
    now = int(datetime.datetime.now().timestamp())

    def alive(ev):
        s = ev.get("starts_ts") or 0
        return s <= now < (ev.get("ends_ts") or s)

    live = [x for x in data if alive(x) and not x.get("cancelled")
            and x.get("location")]
    live.sort(key=lambda x: -(len(x.get("description") or "")))
    soon = [x for x in data if (x.get("starts_ts") or 0) > now
            and not x.get("cancelled") and x.get("location")
            and x.get("description")]
    soon.sort(key=lambda x: x["starts_ts"])
    return live[:6], soon[:6]


def main():
    with open(SRC, encoding="utf-8") as fh:
        data = json.load(fh)
    live, soon = pick(data)
    print(f"using {len(live)} live and {len(soon)} upcoming events")

    page_main(LIGHT, live, soon)
    page_main(DARK, live, soon, dark=True)
    page_states(LIGHT, live, soon)
    page_tokens(LIGHT)

    doc = (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        "<title>UConn Events - design</title><style>"
        f"@page {{ size: {PAGE_PT_W}pt {PAGE_PT_H}pt; margin: 0 }}"
        "html,body{margin:0;padding:0;background:#fff}"
        ".page{position:relative;width:1280px;height:2000px;overflow:hidden;"
        "page-break-after:always}"
        ".page:last-child{page-break-after:auto}"
        "*{-webkit-font-smoothing:antialiased}"
        "</style></head><body>" + "".join(pages) + "</body></html>"
    )
    os.makedirs(DESIGN, exist_ok=True)
    with open(HTML_OUT, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"wrote {HTML_OUT}")

    cmd = [CHROME, "--headless", "--disable-gpu", "--no-sandbox",
           f"--print-to-pdf={PDF_OUT}", "--no-pdf-header-footer",
           "--print-to-pdf-no-header", f"file://{HTML_OUT}"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not os.path.exists(PDF_OUT):
        raise SystemExit(f"Chrome failed to print: {proc.stderr[-800:]}")
    print(f"wrote {PDF_OUT} ({os.path.getsize(PDF_OUT) / 1024:,.0f} KB)")


if __name__ == "__main__":
    main()
