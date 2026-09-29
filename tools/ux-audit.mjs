/**
 * UX and accessibility audit for a local page.
 *
 * This is the piece the open-source MCP servers do not cover. Playwright MCP
 * can drive a page and Chrome DevTools MCP can profile it, but neither runs
 * a real accessibility engine or measures colour contrast, tap target size,
 * and horizontal overflow in one pass. This does, and it needs no server.
 *
 *   node audit.mjs /path/to/page.html [width] [height]
 */

import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';

const target = process.argv[2];
const W = Number(process.argv[3] || 1280);
const H = Number(process.argv[4] || 900);

if (!target) {
  console.error('usage: node audit.mjs <file-or-url> [width] [height]');
  process.exit(1);
}

const url = /^https?:/.test(target) ? target : 'file://' + path.resolve(target);
const axeSource = fs.readFileSync(
  path.join(process.cwd(), 'node_modules', 'axe-core', 'axe.min.js'), 'utf8');

// Chromium lives in the shared Playwright cache, not beside this script.
const CACHE = process.env.HOME + '/Library/Caches/ms-playwright';
function findChromium() {
  if (!fs.existsSync(CACHE)) return null;
  for (const dir of fs.readdirSync(CACHE).filter(d => d.startsWith('chromium-')).sort().reverse()) {
    for (const sub of fs.readdirSync(path.join(CACHE, dir))) {
      const p = path.join(CACHE, dir, sub, 'Google Chrome for Testing.app',
                         'Contents', 'MacOS', 'Google Chrome for Testing');
      if (fs.existsSync(p)) return p;
    }
  }
  return null;
}
const executablePath = findChromium();
if (!executablePath) {
  console.error('no chromium under', CACHE, '- run: npx playwright install chromium');
  process.exit(1);
}

const browser = await chromium.launch({ executablePath });
const page = await browser.newPage({ viewport: { width: W, height: H } });
await page.goto(url, { waitUntil: 'load' });
await page.waitForTimeout(600);

// ---------------------------------------------------------------- axe
await page.addScriptTag({ content: axeSource });
const axe = await page.evaluate(async () =>
  await window.axe.run(document, {
    runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'],
  }));

// ---------------------------------------------------------------- measures
const measures = await page.evaluate(() => {
  const out = {
    overflowX: document.documentElement.scrollWidth - window.innerWidth,
    smallText: [], tinyTargets: [], headings: [], imagesNoAlt: 0,
    focusables: 0, skipLink: false, lang: document.documentElement.lang || '',
    title: document.title || '', landmarks: 0,
  };

  const lum = (c) => {
    const [r, g, b] = c.map(v => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const parse = (s) => {
    const m = s.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/);
    return m ? { rgb: [+m[1], +m[2], +m[3]], a: m[4] === undefined ? 1 : +m[4] } : null;
  };
  const bgOf = (el) => {
    let n = el;
    while (n && n !== document.documentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (c && c.a > 0.5) return c.rgb;
      n = n.parentElement;
    }
    return [255, 255, 255];
  };

  document.querySelectorAll('*').forEach((el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) return;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) return;

    const text = (el.textContent || '').trim();
    const ownText = Array.from(el.childNodes)
      .filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join('').trim();

    if (ownText) {
      const size = parseFloat(cs.fontSize);
      const fg = parse(cs.color);
      if (fg) {
        const bg = bgOf(el);
        const l1 = lum(fg.rgb), l2 = lum(bg);
        const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
        const bold = parseInt(cs.fontWeight, 10) >= 700;
        const large = size >= 24 || (size >= 18.66 && bold);
        const need = large ? 3 : 4.5;
        if (ratio < need && el.offsetParent !== null) {
          out.smallText.push({
            text: ownText.slice(0, 42), size, ratio: +ratio.toFixed(2),
            need, colour: cs.color, selector: el.tagName.toLowerCase() +
              (el.className ? '.' + String(el.className).split(' ')[0] : ''),
          });
        }
      }
    }

    const interactive = el.matches('a[href], button, input, select, textarea, [role="button"], [tabindex]:not([tabindex="-1"])');
    if (interactive) {
      out.focusables++;
      if (r.width < 24 || r.height < 24) {
        out.tinyTargets.push({
          tag: el.tagName.toLowerCase(),
          text: (text || el.getAttribute('aria-label') || '').slice(0, 30),
          w: Math.round(r.width), h: Math.round(r.height),
        });
      }
    }
  });

  document.querySelectorAll('h1,h2,h3,h4,h5,h6').forEach((h) => {
    out.headings.push(h.tagName + ' ' + (h.textContent || '').trim().slice(0, 40));
  });
  document.querySelectorAll('img:not([alt])').forEach(() => out.imagesNoAlt++);
  document.querySelectorAll('main, nav, header, footer, [role="main"]').forEach(() => out.landmarks++);
  out.skipLink = !!document.querySelector('a[href^="#"]:first-of-type');

  // de-duplicate contrast findings by selector + colour
  const seen = new Set();
  out.smallText = out.smallText.filter((f) => {
    const k = f.selector + f.colour + f.size;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  }).slice(0, 12);

  const seenT = new Set();
  out.tinyTargets = out.tinyTargets.filter((t) => {
    const k = t.tag + t.w + t.h;
    if (seenT.has(k)) return false;
    seenT.add(k);
    return true;
  }).slice(0, 12);

  return out;
});

// ---------------------------------------------------------------- report
const v = axe.violations;
const line = (s) => console.log(s);
line(`\nUX audit  ${url}`);
line(`viewport ${W}x${H}`);
line('='.repeat(58));

line(`\nAxe violations: ${v.length}`);
for (const item of v) {
  line(`  [${item.impact || 'n/a'}] ${item.id}  x${item.nodes.length}`);
  line(`      ${item.help}`);
  line(`      e.g. ${item.nodes[0].target.join(' ')}`);
}

line(`\nDocument`);
line(`  title:      ${measures.title || '(none)'}`);
line(`  lang:       ${measures.lang || '(missing)'}`);
line(`  landmarks:  ${measures.landmarks}`);
line(`  images missing alt: ${measures.imagesNoAlt}`);

line(`\nLayout`);
line(`  horizontal overflow: ${measures.overflowX}px ${measures.overflowX > 0 ? '<-- BAD' : ''}`);

line(`\nContrast below WCAG AA (${measures.smallText.length} shown)`);
for (const f of measures.smallText) {
  line(`  ${f.ratio}:1 need ${f.need}  ${f.size}px  ${f.selector}`);
  line(`      "${f.text}"`);
}

line(`\nTap targets under 24px (${measures.tinyTargets.length} shown)`);
for (const t of measures.tinyTargets) {
  line(`  ${t.w}x${t.h}  ${t.tag}  "${t.text}"`);
}

line(`\nHeading order`);
line('  ' + measures.headings.slice(0, 14).join('\n  '));

line(`\nFocusable elements: ${measures.focusables}`);
line(`\nPage height: ${await page.evaluate(() => document.body.scrollHeight)}px`);

await browser.close();
