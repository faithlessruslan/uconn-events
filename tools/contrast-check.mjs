import { chromium } from 'playwright-core';
import fs from 'node:fs'; import path from 'node:path';
function find(){const C=process.env.HOME+'/Library/Caches/ms-playwright';
 for(const d of fs.readdirSync(C).filter(x=>x.startsWith('chromium-')).sort().reverse())
  for(const s of fs.readdirSync(path.join(C,d))){const p=path.join(C,d,s,'Google Chrome for Testing.app','Contents','MacOS','Google Chrome for Testing');if(fs.existsSync(p))return p;}}
const b=await chromium.launch({executablePath:find()});
const p=await b.newPage({viewport:{width:1280,height:900}});
await p.goto('file://'+path.resolve(process.argv[2]),{waitUntil:'load'});
await p.waitForTimeout(500);

const measure = async (theme) => {
  await p.evaluate((t)=>setTheme(t), theme);
  await p.waitForTimeout(200);
  return p.evaluate(() => {
    const lum = (rgb) => {
      const c = rgb.map(v => { v/=255; return v<=0.03928 ? v/12.92 : ((v+0.055)/1.055)**2.4; });
      return 0.2126*c[0]+0.7152*c[1]+0.0722*c[2];
    };
    const parse = s => s.match(/[\d.]+/g).slice(0,3).map(Number);
    const contrast = (a,b) => { const x=lum(parse(a)), y=lum(parse(b));
      return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05); };
    const seen = new Map();
    for (const card of document.querySelectorAll('.grid > article.card')) {
      const topic = card.dataset.topic;
      const label = card.querySelector('.cfoot .tag');
      if (!label || seen.has(topic)) continue;
      const fill = getComputedStyle(label).backgroundColor;
      const labelInk = getComputedStyle(label).color;
      const panel = getComputedStyle(card).backgroundColor;
      const title = getComputedStyle(card.querySelector('.ctitle')).color;
      const facts = getComputedStyle(card.querySelector('.factrow .txt')).color;
      seen.set(topic, {
        label: +contrast(labelInk, fill).toFixed(2),
        title: +contrast(title, panel).toFixed(2),
        facts: +contrast(facts, panel).toFixed(2),
      });
    }
    return Object.fromEntries(seen);
  });
};

for (const theme of ['light','dark']) {
  const r = await measure(theme);
  const rows = Object.entries(r);
  const minLabel = Math.min(...rows.map(([,v])=>v.label));
  const minTitle = Math.min(...rows.map(([,v])=>v.title));
  const minFacts = Math.min(...rows.map(([,v])=>v.facts));
  console.log(`\n${theme.toUpperCase()}  topics=${rows.length}`);
  console.log(`  worst label contrast : ${minLabel}  (needs 4.5)`);
  console.log(`  worst title contrast : ${minTitle}  (needs 4.5)`);
  console.log(`  worst facts contrast : ${minFacts}  (needs 4.5)`);
  const fails = rows.filter(([,v])=>v.label<4.5||v.title<4.5||v.facts<4.5);
  console.log(`  topics failing: ${fails.length}${fails.length?' -> '+fails.map(f=>f[0]).join(', '):''}`);
}
await b.close();
