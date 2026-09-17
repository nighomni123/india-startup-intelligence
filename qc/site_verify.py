#!/usr/bin/env python3
"""site_verify.py — mechanical official-website + careers-page verification for active rows.
For each active STARTUPS row: candidate domains = (a) current website if own-domain-ish,
(b) non-aggregator hosts among that startup's SOURCES, (c) name heuristics (.com/.in).
Probe each candidate homepage; accept if company-name token appears in title/body.
Then scan accepted homepage for careers links (own-domain /careers|/jobs|/work-with-us or ATS:
lever/greenhouse/ashby/workable/breezy/jazzhr). Writes gapfill/<key>.site.json for merge.
Every accepted value is sourced to the company's own live page — no guessing."""
import csv, json, re, os, sys, urllib.request, urllib.parse, ssl, collections
from concurrent.futures import ThreadPoolExecutor

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
HDR = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
       'Accept': 'text/html,application/xhtml+xml'}
AGG = re.compile(r"(wikipedia\.org|wikimedia|businessinsider|inc42\.com|entrackr\.com|yourstory\.com|techcrunch\.com|economictimes|et\.com|moneycontrol|tracxn\.com|crunchbase\.com|pitchbook\.com|linkedin\.com|reuters\.com|bloomberg\.com|businessage|business-standard|businesstoday|forbes\.com|forbesindia|livemint|ndtv|lifestyle\.in|bbc\.|cnn\.|yahoo\.com|msn\.com|scmp|straitstimes|africaincome|businessupkeep|thenews\.com|firstpost|financialexpress|ieconomy|pib\.gov|pmmindia|ddnews|thehindu|hindutimes|deccanherald|bangaloremirror|outlookmoney|outlookindia|mint\.com|indianexpress|indiatimes|timesofindia|newsnation|cnbctv18|lensmonk|vccircle|fintechflyover|invein|thecompanycheck|companycheck\.in|sebi\.gov|myix\.co|zaubee|kavse|angelone|prowess|indiacompanies|kane\.co|kav\.com|kaveri|crowdsupply|github\.com|youtube\.com|x\.com|twitter\.com|facebook\.com|instagram\.com|archive\.org|drive\.google|docs\.google|medium\.com|substack|quora|reddit|amazon|flipkart|play\.google|apps\.apple)", re.I)
STOP = {"the","and","for","technologies","technology","solutions","services","private","limited","pvt","ltd","inc","labs","group","holdings","india","startup","ai","of","in","systems","software","company","ventures","digital","global","fintech","healthcare","one","new","app","apps","platform","networks","works","studio","studios","media","mobile"}
ATS = re.compile(r"(jobs\.lever\.co|boards\.greenhouse\.io|jobs\.ashbyhq\.com|apply\.workable\.com|[\w.-]+\.breezy\.hr|[\w.-]+\.jazzhr\.com|[\w.-]+\.jobstreet|careers\.[\w.-]+|jobs\.[\w.-]+)", re.I)

def fetch(u, timeout=14):
    try:
        req = urllib.request.Request(u, headers=HDR)
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            body = r.read(400000).decode('utf8', errors='ignore')
            return r.geturl(), body
    except Exception:
        return None, None

def name_tokens(n):
    n = re.sub(r"\(.*?\)", " ", n.lower())
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return [t for t in n.split() if t not in STOP and len(t) > 2]

def reg_domain(host):
    parts = host.lower().split('.')
    if len(parts) >= 2:
        if parts[-2] in ('co','com','org','net','gov','ac','in') and len(parts) >= 3 and parts[-1] == 'in':
            return '.'.join(parts[-3:])
        return '.'.join(parts[-2:])
    return host

def candidates(row, src_hosts):
    cands, w = [], row['website'].strip()
    if w and not AGG.search(w):
        cands.append(w if w.startswith('http') else 'https://' + w)
    for h in src_hosts:
        if not AGG.search(h):
            cands.append('https://' + h)
    toks = name_tokens(row['company_name'])
    core = ''.join(toks[:2])
    if core:
        cands += [f"https://{core}.com", f"https://{core}.in"]
    seen, out = set(), []
    for c in cands:
        try:
            host = urllib.parse.urlparse(c).netloc
        except Exception:
            continue
        if host and host not in seen:
            seen.add(host); out.append(c)
    return out[:6]

def verify(row, src_hosts):
    key, toks = row['company_name'], name_tokens(row['company_name'])
    if not toks:
        return None
    for cand in candidates(row, src_hosts):
        fu, body = fetch(cand)
        if not body or len(body) < 500:
            continue
        probe = (re.search(r"<title[^>]*>(.{0,300}?)</title>", body, re.I | re.S) or [None, ''])[1]
        probe = probe.lower() + ' ' + body[:6000].lower()
        if not any(t in probe for t in toks[:2]):
            continue
        host = re.sub(r':\d+$','',urllib.parse.urlparse(fu).netloc)
        off = f"https://{host}"
        careers = ''
        for m in re.finditer(r'href=["\']([^"\'#]+)["\']', body, re.I):
            h = m.group(1)
            hl = h.lower()
            if re.search(r"(career|jobs|join[- ]?us|work[- ]?with[- ]?us|we[- ]?are[- ]?hiring|openings?)", hl):
                absu = urllib.parse.urljoin(fu, h)
                ah = urllib.parse.urlparse(absu).netloc
                pu = urllib.parse.urlparse(absu)
                if '/article/' in pu.path or '/news' in pu.path or len(pu.path.strip('/').split('/')) > 3: continue
                if ATS.search(ah) or reg_domain(ah) == reg_domain(host):
                    ok, cb = fetch(absu, timeout=10)
                    if ok and cb and len(cb) > 400 and not re.search(r"<title[^>]*>[^<]*(article|news|story)[^<]*</title>", cb[:3000], re.I):
                        careers = absu; break
        return {"canonical_key": row['_key'], "official_website": {"v": off, "conf": "high", "src": off, "note": "verified live 2026-09-15: name match on own homepage"},
                "careers_website": ({"v": careers, "conf": "high", "src": off, "note": "careers link found on official homepage, probed live"} if careers else None)}
    return None

def main():
    rows = list(csv.DictReader(open('build/csv/STARTUPS.csv')))
    u = {x['startup_id']: x['canonical_key'] for x in json.load(open('structured/universe.json'))['universe']}
    srccol = 'startup_ids'
    hosts = collections.defaultdict(list)
    for s in csv.DictReader(open('build/csv/SOURCES.csv')):
        try:
            h = urllib.parse.urlparse(s['url']).netloc
        except Exception:
            continue
        for sid in re.split(r"[;,]\s*", s.get(srccol) or ''):
            if h and h not in hosts[sid]:
                hosts[sid].append(h)
    todo = []
    for r in rows:
        st = r['status'].lower()
        if any(k in st for k in ('defunct', 'shut', 'insolvent', 'liquidat', 'merged into', 'acquired—')):
            continue
        r['_key'] = u.get(r['startup_id'], '')
        out = f"gapfill/{r['_key']}.site.json"
        if os.path.exists(out):
            continue
        todo.append(r)
    print(f"{len(todo)} active rows to verify", flush=True)
    done = 0
    with ThreadPoolExecutor(12) as ex:
        for r, res in zip(todo, ex.map(lambda x: verify(x, hosts.get(x['startup_id'], [])), todo)):
            if res:
                json.dump(res, open(f"gapfill/{r['_key']}.site.json", 'w'), ensure_ascii=False, indent=1)
                done += 1
            if (done + 1) % 25 == 0:
                print(f"{done} verified so far", flush=True)
    print(f"DONE verified={done}/{len(todo)}")

if __name__ == '__main__':
    main()
