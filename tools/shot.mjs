/** Screenshot a page at a given viewport. Usage: node shot.mjs <page> <w> <h> <out> */
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
const CACHE = process.env.HOME + '/Library/Caches/ms-playwright';
function find() {
  for (const d of fs.readdirSync(CACHE).filter(x => x.startsWith('chromium-')).sort().reverse())
    for (const s of fs.readdirSync(path.join(CACHE, d))) {
      const p = path.join(CACHE, d, s, 'Google Chrome for Testing.app', 'Contents', 'MacOS', 'Google Chrome for Testing');
      if (fs.existsSync(p)) return p;
    }
}
const [page, w, h, out] = process.argv.slice(2);
const b = await chromium.launch({ executablePath: find() });
const p = await b.newPage({ viewport: { width: +w, height: +h }, deviceScaleFactor: 2 });
await p.goto('file://' + path.resolve(page), { waitUntil: 'load' });
await p.waitForTimeout(700);
await p.screenshot({ path: out });
await b.close();
console.log('wrote', out);
