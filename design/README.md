# Figma design file

`uconn-events-design.pdf` is the design. Four pages, one screen each.

| Page | What |
|---|---|
| 1 | Main screen, light |
| 2 | Main screen, dark |
| 3 | States: expanded repeat, cancelled, past, no results |
| 4 | Foundations: colour swatches and the type scale |

## How to open it in Figma

1. Drag `uconn-events-design.pdf` onto a Figma canvas.
2. Figma turns each PDF page into a frame and keeps **text as editable text
   layers**, with the shapes as vectors.

If a dialog asks, choose to import all pages.

## Why a PDF, and not an SVG

The first attempt generated an SVG. It was valid XML, every text node was in
the file, and the browser's DOM reported the text visible with the right
coordinates and fill. It still painted as nothing but empty card outlines.

Rather than keep guessing at that, the design moved to HTML printed to PDF by
headless Chrome. That path is well trodden, and it has the property that
actually matters for a Figma handoff: the text arrives editable.

Two things worth knowing if you regenerate it:

- **Page size is declared in points.** Chrome multiplies CSS pixels by 0.75 on
  the way to PDF, so a 1280px-wide layout needs `size: 960pt`. Getting that
  wrong silently shrinks every frame by a quarter.
- **Content uses absolute positioning.** CSS layout inside a printed page is
  unpredictable, so every element is placed with `left`/`top`. That is also
  what makes the Figma frame come out tidy.

## Regenerating

```bash
cd ../scraper
python3 make_figma.py
```

It reads `data/uconn-events.json`, writes `design/uconn-events-design.html`,
then prints the PDF. Real events are used, so the mock reads like the live
page: the live cards are events actually running when you build it.

## What is in the design

The palette and type match the stylesheet exactly, and page 4 names every
value so the file doubles as a spec.

- Warm paper base, a navy accent, and muted gold used only for paid cost
- A serif for the page title and empty state, sans everywhere else
- Day headers carry the scanning: `TOMORROW` pill, day name, relative time,
  and a count, then a hairline
- Live cards get a green left rule and a drawn pulse dot
- Twelve-and-a-half pixel uppercase micro-labels for section names
- Icons are drawn SVG strokes, never a glyph font
