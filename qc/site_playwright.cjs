// site_playwright.mjs — render-verify stubborn official sites + careers pages.
// Usage: NODE_PATH=$(npm root -g) node site_playwright.mjs jobs.json mode
// mode=official : jobs=[{key,name,official?,cands[]}]  -> gapfill/<key>.site.json
// mode=careers  : jobs=[{key,name,official}]           -> gapfill/<key>.careers.json
// Never invents: only accepts a domain if the rendered page contains the company name.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const GAP = process.env.GAPDIR || 'gapfill';

const AGG = /(wikipedia|wikimedia|businessinsider|inc42|entrackr|yourstory|techcrunch|economictimes|moneycontrol|tracxn|crunchbase|pitchbook|linkedin|reuters|bloomberg|businesstoday|forbes|livemint|mint\.com|indianexpress|indiatimes|timesofindia|forbesindia|ndtv|newsnation|cnbctv18|lensmonk|vccircle|thecompanycheck|companycheck\.in|sebi\.gov|myix\.co|zaubee|github|youtube|crowdsupply|medium\.com|twitter|x\.com|facebook|instagram|amazon|flipkart|duckduckgo|bing\.com|google)/i;
const STOP = new Set(['the','and','for','technologies','technology','solutions','services','private','limited','pvt','ltd','inc','labs','group','holdings','india','startup','ai','of','in','systems','software','company','ventures','digital','global','fintech','healthcare','one','new','app','apps','platform','networks','works','studio','studios','media','mobile','manufacturing','games','capital','financial']);
function toks(name){ return name.toLowerCase().replace(/\(.*?\)/g,' ').replace(/[^a-z0-9 ]/g,' ').split(/\s+/).filter(t=>t && !STOP.has(t) && t.length>2); }
const sleep = ms => new Promise(r=>setTimeout(r,ms));

async function searchEngine(page, q){
  const engines = [
    ['https://duckduckgo.com/html/?q='+encodeURIComponent(q), 'a.result__url', null],
    ['https://www.bing.com/search?q='+encodeURIComponent(q), 'h2 a', null],
  ];
  for (const [url, sel] of engines){
    try {
      await page.goto(url, {waitUntil:'domcontentloaded', timeout:25000});
      const hrefs = await page.$$eval(sel, as => as.map(a=>a.href).filter(h=>h));
      const doms = [];
      for (const h of hrefs){
        try {
          let u = h;
          const m = u.match(/(?:url|uddg)=([^&]+)/); if (m) u = decodeURIComponent(m[1]);
          const host = new URL(u).hostname;
          if (!AGG.test(host)) doms.push('https://'+host);
        } catch {}
        if (doms.length>=4) break;
      }
      if (doms.length) return [...new Set(doms)];
    } catch {}
  }
  return [];
}

async function main(){
  const jobs = JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
  const mode = process.argv[3] || 'official';
  const browser = await chromium.launch({headless:true, args:['--no-sandbox','--disable-blink-features=AutomationControlled','--window-size=1366,900']});
  const ctx = await browser.newContext({userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36', viewport:{width:1366,height:900}, locale:'en-IN'});
  let done=0, hit=0;
  for (const job of jobs){
    const page = await ctx.newPage();
    page.setDefaultNavigationTimeout(22000);
    try {
      const tk = toks(job.name);
      if (!tk.length) continue;
      const verify = async (u) => {
        await page.goto(u, {waitUntil:'domcontentloaded'});
        await sleep(2200);
        const info = await page.evaluate(() => ({title: document.title, body: (document.body?document.body.innerText:'').slice(0,9000), href: location.href, links: [...document.querySelectorAll('a')].map(a=>a.href).slice(0,600)}));
        const probe = (info.title+' '+info.body).toLowerCase();
        return {ok: tk.slice(0,2).some(t=>probe.includes(t)), info};
      };
      if (mode === 'official'){
        let cands = [...(job.cands||[])];
        if (!cands.length){
          const t = tk[0];
          cands = [ `https://www.${t}.com`, `https://${t}.com`, `https://www.${t}.in`, `https://${t}.in` ];
        }
        const found = [...(job.cands||[]), ...await searchEngine(page, job.name + ' official website')];
        let acc = null;
        for (const c of found.slice(0,7)){
          try { const v = await verify(c); if (v.ok){ acc = v.info.href; break; } } catch {}
        }
        if (acc){
          // careers scan on the rendered official page
          let careers='';
          try { const v2 = await verify(acc); } catch {}
          const cl = await page.evaluate(()=>[...document.querySelectorAll('a')].map(a=>a.href));
          for (const h of cl){
            if (/career|jobs|join[- ]?us|work[- ]?with[- ]?us|we[- ]?are[- ]?hiring/i.test(h) && !/\/article\/|\/news/i.test(h)){
              try { const v = await verify(h); if (v.ok && /(job|career|opening|position|hire|team)/i.test(v.info.title+v.info.body.slice(0,2000))){ careers = v.info.href; break; } } catch {}
            }
          }
          const rec = {canonical_key: job.key, official_website:{v:acc, conf:'high', src:acc, note:'playwright render-verified 2026-09-15'}};
          if (careers) rec.careers_website={v:careers, conf:'high', src:acc, note:'found in rendered nav, playwright 2026-09-15'};
          fs.writeFileSync(path.join(GAP, job.key + '.site.json'), JSON.stringify(rec,null,1));
          hit++;
        }
      } else {
        let careers='';
        try {
          const v0 = await verify(job.official);
          const links = v0.info.links.concat(v0.info.links.map(h=>h.replace(/^https?:\/\/(www\.)?/,'').length?h:h));
          const cand = links.filter(h=>/career|jobs|join|work-with|we-are-hiring|life-at/i.test(h) && !/\/article\//i.test(h)).slice(0,5);
          for (const h of cand){
            try { const v = await verify(h); if (v.info && /(job|career|opening|position|role|team|life)/i.test((v.info.title||'')+(v.info.body||'').slice(0,2500))){ careers=v.info.href; break; } } catch {}
          }
          if (!careers){
            for (const p of ['/careers','/careers/','/jobs','/career','/work-with-us','/join-us','/life']){
              try { const v = await verify(job.official.replace(/\/$/,'')+p); if (v.ok && /(job|career|opening|position|role)/i.test(v.info.body.slice(0,2500))){ careers=v.info.href; break; } } catch {}
            }
          }
          if (!careers){
            const sr = await searchEngine(page, job.name + ' careers jobs site');
            for (const c of sr.slice(0,2)){
              try { const v = await verify(c + (AGG.test(c)?'':'/careers')); if (v.ok){ careers=v.info.href; break; } } catch {}
            }
          }
        } catch {}
        const rec = {canonical_key: job.key, careers_website: careers ? {v:careers, conf:'high', src:job.official, note:'playwright render 2026-09-15'} : null};
        fs.writeFileSync(path.join(GAP, job.key + '.careers.json'), JSON.stringify(rec,null,1));
        if (careers) hit++;
        done++;
        console.log(`[${done}/${jobs.length}] ${job.name}: ${careers||'not found'}`);
      }
    } catch (e){ console.log('!!', job.name, String(e).slice(0,90)); }
    finally { await page.close().catch(()=>{}); if (done % 15 === 0) await sleep(1500); }
  }
  await browser.close();
  console.log(`PW_DONE mode=${mode} hits=${hit}/${jobs.length}`);
}
main();
