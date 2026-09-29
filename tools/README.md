# UX tooling

## The two open-source MCP servers you already have

Both are Apache-2.0, both are maintained by the browser vendors, and both were
already on the DSH shelf. Neither is Figma, and neither costs anything.

| Shelf entry | Source | What it gives an agent |
|---|---|---|
| `MCP: playwright` | microsoft/playwright-mcp | Drive a page and see it: 25 tools including `browser_take_screenshot`, `browser_snapshot` (accessibility tree), `browser_evaluate`, `browser_console_messages`, `browser_network_requests` |
| `MCP: chrome-devtools` | ChromeDevTools/chrome-devtools-mcp | Chrome DevTools protocol: performance traces, computed styles, layout metrics, console |

To use one: start a **new** session, click the **Agent mode** chip, pick the
entry. A session's tools are fixed when it starts, so an entry added midway
will not appear in that session.

Verified working by hand: the Playwright server answered on
`http://localhost:8931/mcp` and listed all 25 tools.

### What they do not cover

Neither runs an accessibility engine, and neither measures colour contrast,
tap target size, or horizontal overflow. Those are exactly the things that
make a page unpleasant to use, and they are the reason `ux-audit.mjs` exists.

## ux-audit.mjs

One command, no server, no MCP. Runs a real axe-core pass plus the
measurements above and prints a report.

```bash
cd tools
npm install                      # once, two small packages
npm run audit                    # desktop, 1280x900
npm run audit:phone              # phone, 390x844
```

Or directly, with any viewport:

```bash
node ux-audit.mjs ../index.html 1440 1000
```

It uses the Chromium already in `~/Library/Caches/ms-playwright`, so it needs
no browser download. If that cache is empty, run
`npx playwright install chromium` once.

`shot.mjs` is the companion for looking at a page rather than measuring it:

```bash
npm run shot          # ../screenshot.png at 1280x900, 2x
npm run shot:phone
```

### What it reports

- **Axe violations** across WCAG 2.0 and 2.1, level A and AA, with the failing
  selector and impact
- **Colour contrast** for every text node that has its own text, computed
  against the nearest opaque background, with the ratio and the ratio needed
- **Tap targets** under 24 by 24 pixels, which is the WCAG 2.2 minimum
- **Horizontal overflow**, the classic mobile layout break
- Document basics: title, `lang`, landmarks, images missing `alt`
- Heading order and focusable element count

### It found real bugs in this project

First run on `index.html`:

| Finding | Count | Fix |
|---|---|---|
| Contrast below AA | 1,263 elements | Darkened `--ink-3`, `--ink-4`, and `--gold`; verified each pair against every background it lands on |
| Tap targets under 24px | 12 | Gave card titles, `Details`, `Read more`, and the footer link a real hit area |
| Link relying on colour alone | 1 | Underlined the inline footer link |

Then the phone-width run found two more that the desktop run could not:

| Finding | Cause | Fix |
|---|---|---|
| 103px of horizontal scroll | Nested cards inside a grouped card default to min-content width | `min-width: 0` on cards, and a single-column nested grid |
| 55px more | A bare URL in an event title, which will not wrap | `overflow-wrap: anywhere` on card titles |

After the fixes, at both 1280 and 390 wide: **0 violations, 0 contrast
failures, 0 small targets, 0 horizontal overflow.**

### A note on judging a page by numbers

A clean report is necessary, not sufficient. The audit cannot tell you the
layout is pleasant or the wording is clear. Use it to catch what the eye
misses, then look at the page.
