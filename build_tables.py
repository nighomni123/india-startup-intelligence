#!/usr/bin/env python3
"""build_tables.py — merge universe.json + enrich/*.json into per-sheet CSVs
with global SOURCES (URL->source_id dedupe) and FK resolution.
Outputs build/csv/*.csv + structured/build_report.md. Usage: python3 build_tables.py"""
import json, csv, os, re, glob, sys
from collections import defaultdict, OrderedDict

BASE = os.path.dirname(os.path.abspath(__file__))
UNIV_PATH = f"{BASE}/structured/universe.json"
ENRICH_DIR = f"{BASE}/enrich"
CSV_DIR = f"{BASE}/build/csv"
USD_INR = {"2020":74.0,"2021":74.5,"2022":78.5,"2023":82.8,"2024":83.7,"2025":85.7,"2026":87.0}  # approx annual rates, DERIVED
FX_NOTE = "USD->INR conversion uses documented annual-average approximations (2020:74, 2021:74.5, 2022:78.5, 2023:82.8, 2024:83.7, 2025:85.7, 2026:87). Marked DERIVED in notes."

def norm_url(u):
    if not u: return ""
    u = u.strip().rstrip("/")
    u = re.split(r"[?#]", u, 1)[0] if ("utm_" in u or "?" in u) and re.match(r"https?://", u) else u
    return u

def valid_url(u): return bool(u) and u.startswith("http") and " " not in u and "." in u.split("//",1)[-1].split("/")[0]

def pub_from_url(u):
    m = re.match(r"https?://(?:www\.)?([^/]+)", u or "")
    if not m: return ""
    d = m.group(1).lower()
    table = {"economic-times":"The Economic Times","m.economictimes.com":"The Economic Times","economictimes.indiatimes.com":"The Economic Times",
     "moneycontrol.com":"Moneycontrol","yourstory.com":"YourStory","inc42.com":"Inc42","entracker.com":"Entrackr","techcrunch.com":"TechCrunch",
     "reuters.com":"Reuters","livemint.com":"Mint","business-standard.com":"Business Standard","ft.com":"Financial Times",
     "indianexpress.com":"Indian Express","timesofindia.indiatimes.com":"Times of India","forbes.com":"Forbes","forbesindia.com":"Forbes India",
     "crunchbase.com":"Crunchbase","tracxn.com":"Tracxn","pitchbook.com":"PitchBook","dealroom.co":"Dealroom","venturecapitalreach.com":"VCR",
     "startupindia.gov.in":"DPIIT/Startup India","pib.gov.in":"PIB (Govt of India)","rbi.org.in":"RBI","sebi.gov.in":"SEBI","mca.gov.in":"MCA",
     "bseindia.com":"BSE","nseindia.com":"NSE","vccircle.com":"VCCircle","dcgov.com":"DCG","businesstoday.in":"Business Today",
     "cnbctv18.com":"CNBC-TV18","mint.in":"Mint","ndtvprofit.com":"NDTV Profit","bloomberg.com":"Bloomberg","bain.com":"Bain & Co",
     "wosai-indianstartups.com":"IndianStartups News","thenewsminute.com":"The NewsMinute","deccanherald.com":"Deccan Herald",
     "newstonation.com":"News18 Nation","upstox.com":"Upstox","zerodha.com":"Zerodha","glints.com":"Glints","zigwheels":"Zigwheels"}
    return table.get(d, d)

def tier_from_url(u, given=None):
    if given and re.match(r"^T[1-5]$", str(given)): return given
    d = (re.match(r"https?://(?:www\.)?([^/]+)", u or "") or [None,""])[1].lower()
    if any(d.endswith(x) for x in (".gov.in",".nic.in")) or d in ("bseindia.com","nseindia.com","pib.gov.in"): return "T1"
    if any(x in d for x in ("crunchbase","tracxn","pitchbook","dealroom","tofler","zaakor","instafin","sensata","capitalblock","ventureintelligence","vicikings")): return "T2"
    if any(x in d for x in ("economictimes","moneycontrol","yourstory","inc42","entracker","techcrunch","reuters","livemint","business-standard","ft.com","indianexpress","forbes","bloomberg","cnbctv18","businesstoday","ndtvprofit","vccircle","dcgov","financialexpress")): return "T3"
    if any(x in d for x in ("linkedin","twitter","x.com","youtube","instagram","facebook","medium.com","substack","reddit","quora")): return "T5"
    return "T4"

def year_of(s):
    m = re.search(r"(20\d\d)", str(s or "")); return int(m.group(1)) if m else None

def inr_mn(amount_usd_mn, cy, yr):
    if cy == "INR": return round(amount_usd_mn, 2)
    r = USD_INR.get(str(yr or 2025), 86.0)
    return round(amount_usd_mn * r, 2)

def parse_money(s):
    """Return (value_in_millions, currency). Handles $, Rs/₹, crore, lakh, billion."""
    s = str(s or "").strip()
    if not s or s.lower() in ("none","nan","undisclosed","not public"): return (None, "")
    t = s.lower().replace(",", "")
    _rg = re.search(r"(?:[$]|rs\.?|inr|\u20b9)?\s*([\d.]+)\s*[-\u2013]\s*([\d.]+)\s*(b|bn|billion|m|mn|cr|crore|k)\b", t)
    if _rg:
        _u=_rg.group(3); _cur = "INR" if _u in ("cr","crore") or re.search(r"(rs|inr|\u20b9|crore)",t) else "USD"
        _v=float(_rg.group(1))
        if _u in ("b","bn","billion"): _v*=1000
        elif _u in ("cr","crore"): _v*=10
        elif _u=="k": _v/=1000 if _cur=="USD" else 100000
        return (_v, _cur)
    _inr_first = bool(re.search(r"[\d.]\s*(crore|cr|lakh|lac|lakhs|lacs)\b", t)) or bool(re.search(r"(?:rs\.?|inr|\u20b9)\s*[\d.]", t))
    if _inr_first:
        m2 = re.search(r"(?:rs\.?|inr|\u20b9)\s*([\d.]+)\s*(b|bn|billion|cr|crore|lakh|lac|k|thousand)?", t) or re.search(r"([\d.]+)\s*(crore|cr|lakh|lac|lakhs|lacs)\b", t)
        if m2:
            v = float(m2.group(1)); u = (m2.group(2) or "").strip()
            if u in ("b","bn","billion"): v *= 1000
            elif u in ("cr","crore"): v *= 10
            elif u in ("lakh","lac","lakhs","lacs"): v /= 10
            elif u in ("k","thousand"): v /= 100000
            return (v, "INR")
    m = re.search(r"[$]\s*([\d.]+)\s*(b|bn|billion|m|mn|million|cr|crore|k|thousand|l|lakh|lac)?", t)
    if m:
        v = float(m.group(1)); u = m.group(2) or ""
        if u in ("k","thousand"): v /= 1000
        if u in ("b","bn","billion"): v *= 1000
        if u in ("cr","crore"): v = v  # $x crore is rare; treat as millions
        if u in ("l","lakh","lac"): v /= 10
        return (v, "USD")
    m = re.search(r"(?:rs\.?|inr|₹)\s*([\d.]+)\s*(b|bn|billion|cr|crore|lakh|lac|k|thousand)?", t)
    if m:
        v = float(m.group(1)); u = m.group(2) or ""
        if u in ("b","bn","billion"): v *= 1000
        elif u in ("cr","crore"): v *= 10
        elif u in ("lakh","lac"): v /= 10
        return (v, "INR")
    m = re.fullmatch(r"([\d.]+)\s*(mn|m|million|bn|b|crore|cr)?", t)
    if m:
        v = float(m.group(1)); u = m.group(2) or "m"
        if u in ("b","bn","billion"): v *= 1000
        if u in ("cr","crore"): return (v*10, "INR")
        return (v, "USD")
    return (None, "")

class Reg:
    def __init__(self):
        self.urls = OrderedDict(); self.missing = []
        self.investors = OrderedDict(); self.people = OrderedDict()
        self.counts = defaultdict(int)
    def source(self, url, startup_ids, title="", publisher="", pub_date="", retrieved="", tier="", claim="", fields="", conf="", note=""):
        u = norm_url(url)
        if not valid_url(u):
            self.missing.append((startup_ids, url, claim or fields or "", title)); return ""
        if not title:
            try:
                from urllib.parse import urlparse as _up
                _pu=_up(u); _slug=[x for x in _pu.path.split("/") if x][-1] if _pu.path!="/" else ""
                title=f"auto-title: {_pu.netloc.replace('www.','')}"+(f" / {_slug[:40]}" if _slug else "")
            except Exception: title="auto-title (untitled source)"
        if u in self.urls:
            r = self.urls[u]
            for s in ([startup_ids] if isinstance(startup_ids, str) else startup_ids):
                if s and s not in r["startup_ids"]: r["startup_ids"].append(s)
            return r["source_id"]
        sid = f"SRC{len(self.urls)+1:05d}"
        self.urls[u] = {"source_id": sid, "url": u, "startup_ids": list(startup_ids if not isinstance(startup_ids, str) else [startup_ids]),
                        "title": title or "", "publisher": publisher or pub_from_url(u), "publication_date": pub_date,
                        "retrieved_date": retrieved or "2026-09-14", "tier": tier or tier_from_url(u), "claim": claim,
                        "fields": fields, "conf": conf, "note": note}
        return sid
    def investor(self, name):
        if isinstance(name, dict): name = name.get("v") or name.get("name") or ""
        name = str(name)
        n = re.sub(r"\s+(llp|l\.l\.c|ltd|inc|lp|fund i{1,3}|one|two)\b\.?$", "", (name or "").strip(), flags=re.I)
        k = re.sub(r"[^a-z0-9&]", "", n.lower())
        if not k: return ""
        if k not in self.investors:
            self.investors[k] = {"investor_id": f"INV{len(self.investors)+1:04d}", "name": n}
        return self.investors[k]["investor_id"]
    def person(self, name):
        if isinstance(name, dict): name = name.get("v") or name.get("name") or ""
        k = re.sub(r"[^a-z ]", "", (str(name) or "").lower()).strip()
        if len(k) < 3: return ""
        if k not in self.people:
            self.people[k] = {"person_id": f"P{len(self.people)+1:04d}", "name": name.strip()}
        return self.people[k]["person_id"]

def g(o, *keys, default=""):
    for k in keys:
        v = o.get(k)
        if v not in (None, "", []): return v
        v = (o.get("company") or {}) if k == "company" else None
    for k in keys:
        if isinstance(o.get(k), dict):
            v = o[k].get("v", o[k])
            if v not in (None, "", []): return v
    return default

def gv(o, key):
    """value/conf/src from possibly-dict field"""
    v = o.get(key)
    if isinstance(v, dict):
        return v.get("v",""), v.get("conf",""), v.get("src","")
    return (v if v is not None else ""), "", ""

def parse_list(v):
    """handles real lists, stringified python lists, comma/semicolon strings."""
    if not v: return []
    if isinstance(v, list): return [str(x).strip() for x in v if x]
    s = str(v).strip()
    if s.startswith("[") and s.endswith("]"):
        try:
            import ast
            r = ast.literal_eval(s)
            if isinstance(r, list): return [str(x).strip() for x in r if x]
        except Exception: pass
    return [x.strip().strip("'\"") for x in re.split(r"[,;]", s) if x.strip().strip("'\"") not in ("", "None")]

def main():
    univ = json.load(open(UNIV_PATH))["universe"]
    U = {u["startup_id"]: u for u in univ}
    enr = {}
    by_slug = {}
    for u_ in univ: by_slug.setdefault(u_["canonical_key"], u_["startup_id"])
    for f in sorted(glob.glob(f"{ENRICH_DIR}/*.json")):
        try:
            d = json.load(open(f)); slug = (d.get("canonical_key") or os.path.basename(f).split(".")[0]).replace("_"," ")
            sid = by_slug.get(slug) or (slug if slug in U else None)
            if sid in U: enr[sid] = d
            else: print(f"!! orphan enrich file {f} (key {slug} not in universe)")
        except Exception as e:
            print(f"!! bad json {f}: {e}")
    R = Reg()
    # cross-field sanity: registry CIN state-code vs enriched city (aggregator pages mix entities)
    STCODE={"MH":"Maharashtra","KA":"Karnataka","DL":"Delhi","HR":"Haryana","TG":"Telangana","GJ":"Gujarat","TN":"Tamil Nadu","UP":"Uttar Pradesh","WB":"West Bengal","AS":"Assam","UK":"Uttarakhand","MP":"Madhya Pradesh","RJ":"Rajasthan","PB":"Punjab","KL":"Kerala","CH":"Chandigarh","GA":"Goa"}
    CISTATE={"Maharashtra":"MH","Karnataka":"KA","Delhi":"DL","Haryana":"HR","Telangana":"TG","Gujarat":"GJ","Tamil Nadu":"TN","Uttar Pradesh":"UP","West Bengal":"WB","Assam":"AS","Punjab":"PB","Kerala":"KL","Madhya Pradesh":"MP","Rajasthan":"RJ","Uttarakhand":"UK","Goa":"GA","Chandigarh":"CH"}
    CITYST={"Mumbai":"MH","Pune":"MH","Nagpur":"MH","Bengaluru":"KA","Mysuru":"KA","Delhi":"DL","New Delhi":"DL","Gurugram":"HR","Noida":"UP","Hyderabad":"TG","Ahmedabad":"GJ","Chennai":"TN","Kolkata":"WB","Puducherry":"PY"}
    URLAUDIT = {}
    import csv as _c2
    _p2 = f"{BASE}/qc/url_audit.csv"
    if os.path.exists(_p2):
        URLAUDIT = {r["url"]: r["outcome"] for r in _c2.DictReader(open(_p2))}
    CORRECTED = {}
    for _sid, _d in enr.items():
        _cc = (_d.get("company") or {}).get("city")
        if isinstance(_cc, dict): _cc = _cc.get("v")
        if _cc and _sid in U: CORRECTED[U[_sid]["canonical_key"]] = _cc
    print(f"universe {len(U)} | enriched {len(enr)} | city-corrected {len(CORRECTED)}")
    os.makedirs(CSV_DIR, exist_ok=True)

    _LOGDEDUP = {}
    startups_rows, founders_rows, people_rows, funding_rows = [], [], [], []
    inv_link_rows, fin_rows, prod_rows, cust_rows, part_rows, comp_rows = [], [], [], [], [], []
    acq_rows, loc_rows, hire_rows, legal_rows, event_rows, log_rows, score_rows, trk_rows = [], [], [], [], [], [], [], []
    claims_rows, conflicts_rows = [], []
    _FSEEEN, _PSEEEN, _CNSEEN = set(), set(), set()
    tech_rows = []
    seen_rounds = defaultdict(set); dup_rounds = []

    for sid, u in sorted(U.items()):
        d = enr.get(sid)
        conf = "MEDIUM"; last_ver = "2026-09-14"
        row = {c: "" for c in COLS["STARTUPS"]}
        row.update({"startup_id": sid, "company_name": u["company_name"], "city": u["city"], "state": u["state"],
                    "country": "India", "public_private": "Private"})
        prim_src = ""
        if d:
            c = d.get("company") or {}
            # fallback: company website from its own sources[] when host root matches name/canonical key
            _cw = c.get("website"); _cw = (_cw.get("v","") if isinstance(_cw,dict) else str(_cw or ""))
            if not _cw.strip():
                import re as _re
                _namekey=_re.sub(r"[^a-z0-9]","",(d.get("canonical_key") or "").lower())
                for _s in (d.get("sources") or []):
                    _u=_s.get("url") if isinstance(_s,dict) else _s
                    if not _u or not str(_u).startswith("http"): continue
                    try:
                        from urllib.parse import urlparse
                        _h=urlparse(str(_u)).netloc.lower().replace("www.","")
                    except Exception: continue
                    _root=_re.sub(r"[^a-z0-9]","",(_h.split(".")[0] if _h.count(".")<2 else ".".join(_h.split(".")[:-1])).lower())
                    if len(_root)>=4 and (_root==_namekey or _namekey.startswith(_root) or _root.startswith(_namekey)):
                        c["website"]=f"https://{_h}"; break
            _ow_ = c.get("official_website"); _ow_ = (_ow_.get("v","") if isinstance(_ow_,dict) else str(_ow_ or ""))
            _cwv_ = c.get("careers_website"); _cwv_ = (_cwv_.get("v","") if isinstance(_cwv_,dict) else str(_cwv_ or ""))
            _AGGB = re.compile(r"(wikipedia|wikimedia|businessinsider|inc42|entrackr|yourstory|techcrunch|economictimes|moneycontrol|tracxn|crunchbase|pitchbook|linkedin|reuters|bloomberg|businesstoday|forbes|livemint|forbesindia|ndtv|newsnation|cnbctv18|lensmonk|vccircle|thecompanycheck|companycheck\.in|github|youtube|crowdsupply|medium\.com|twitter|x\.com|facebook|instagram)", re.I)
            _wb_ = str(row.get("website") or "")
            row["official_website"] = _ow_ or (_wb_ if _wb_ and not _AGGB.search(_wb_) else "")
            row["careers_website"] = _cwv_
            if row["official_website"]: row["website"] = row["official_website"]
            for src in d.get("sources") or []:
                if isinstance(src, str): src = {"url": src}
                su = src.get("url") or src.get("source_url") or ""
                R.source(su, sid, title=src.get("title") or src.get("source_title") or "",
                         publisher=src.get("publisher") or "", pub_date=src.get("publication_date") or src.get("date") or "",
                         retrieved=src.get("retrieved_date") or "", tier=tier_from_url(su, src.get("source_tier") or src.get("tier") or ""),
                         claim=str(src.get("claim") or src.get("claim_supported") or "")[:160],
                         fields=str(src.get("fields_supported") or src.get("supports_fields") or "company")[:80],
                         conf=src.get("confidence") or "")
            for kk, fld in [("legal_name","legal_name"),("brand_name","company_name"),("website","website"),("founded_date","founded_date"),
                            ("incorporation_date","incorporation_date"),("status","status"),("stage","startup_stage"),
                            ("primary_sector","primary_sector"),("secondary_sectors","secondary_sectors"),("business_model","business_model"),
                            ("customer_type","customer_type"),("hq_type","hq_type"),("registered_office","registered_office"),
                            ("employee_estimate","employee_estimate"),("employee_estimate_date","employee_estimate_date"),
                            ("dpiit","dpiit_recognized"),("dpiit_recognized","dpiit_recognized"),("cin","cin"),
                            ("parent_company","parent_company"),("subsidiary_of","subsidiary_of"),
                            ("startup_stage","startup_stage"),("public_private","public_private"),("state","state"),("country","country"),("website_status","website_status"),("notes","notes")]:
                v, cf, src = gv(c, kk)
                if v:
                    row[fld] = str(v)[:300]
                    if cf: conf = cf if cf != "LOW" else conf
                    if src and not prim_src: prim_src = R.source(src, sid, claim=f"company.{kk}")
            # funding
            for r in d.get("funding_rounds") or []:
                if not isinstance(r, dict): continue
                rt = str(r.get("round_type") or r.get("type") or "").strip() or "Unknown"
                amt_raw = r.get("amount") or r.get("amount_usd_mn") or r.get("amount_inr") or ""
                cur_given = str(r.get("currency","")).upper()
                if cur_given in ("USD","INR") and re.fullmatch(r"[\d.]+", str(amt_raw).strip()):
                    v, cy = float(amt_raw), cur_given
                    if v > 25000: v = v / 1e6  # agent gave absolute units; normalize to millions
                else:
                    v, cy = parse_money(amt_raw)
                    if not cy:
                        if cur_given in ("USD","INR"): cy = cur_given
                        elif re.search(r"(\bcr\b|₹|\brs\b)", str(amt_raw), re.I): cy = "INR"
                adate = str(r.get("announced_date") or r.get("round_date") or r.get("date") or "")
                key = (rt.lower(), round(v,1) if v else "", (year_of(adate) or ""))
                if v and key in seen_rounds[sid]:
                    dup_rounds.append((sid, rt, v)); continue
                if v: seen_rounds[sid].add(key)
                src = R.source(r.get("source_url") or r.get("source"), sid, title=r.get("source_title",""),
                               pub_date=r.get("source_date",""), tier=tier_from_url(r.get("source_url",""), r.get("tier","")),
                               claim=str(r.get("purpose",""))[:160], fields="FUNDING", conf=r.get("confidence",""))
                yr = year_of(adate)
                val_raw = r.get("valuation") or r.get("valuation_usd_mn") or ""
                vcy_given = str(r.get("valuation_currency") or r.get("currency") or "").upper()
                if vcy_given in ("USD","INR") and re.fullmatch(r"[\d.,]+", str(val_raw).strip()):
                    vval, vcy = float(str(val_raw).replace(",","")), vcy_given
                else:
                    vval, vcy = parse_money(val_raw)
                    if not vcy:
                        if re.search(r"(\bcr\b|₹|\brs\b)", str(val_raw), re.I): vcy = "INR"
                        elif vcy_given in ("USD","INR"): vcy = vcy_given
                if vval and vval > 25000 and vcy == "USD": vval = None  # implausible absolute dollars w/o unit context
                _vrng = re.search(r"[\d.]+\s*[-\u2013]\s*[\d.]+\s*(?:b|bn|billion|m|mn|cr|crore)", str(val_raw), re.I)
                if _vrng and vval: r = dict(r); r["notes"] = (str(r.get("notes","")).strip()+" | ").lstrip("| ") + f"valuation range per source: {str(val_raw).strip()[:30]} (low end stored)"
                lead = parse_list(r.get("lead_investors") or r.get("leads"))
                all_inv = parse_list(r.get("all_investors") or r.get("investors"))
                lead_ids = ";".join(filter(None, [R.investor(x) for x in lead]))
                inv_ids = ";".join(filter(None, [R.investor(x) for x in all_inv]))
                funding_rows.append({"round_id": f"R{len(funding_rows)+1:05d}", "startup_id": sid, "city": CORRECTED.get(u["canonical_key"], u["city"]), "round_date": str(r.get("round_date","")),
                    "announcement_date": adate, "year": yr or "",
                    "fiscal_year": f"FY{(str(yr)[2:] if yr else '')}-{'' if not yr else str((int(str(yr)[2:])+1)%100).zfill(2)}" if yr else "",
                    "round_type": rt, "amount": v if v is not None else "", "currency": cy or "USD", "amount_inr_mn": inr_mn(v, cy, yr) if v else "",
                    "valuation": vval if vval else "", "valuation_currency": vcy if vval else "", "valuation_type": str(r.get("valuation_type","")),
                    "lead_investor_id": lead_ids, "investor_ids": inv_ids, "investor_count": len([i for i in inv_ids.split(";") if i]) + len([i for i in lead_ids.split(";") if i]),
                    "new_or_existing": str(r.get("new_or_existing","")), "purpose": str(r.get("purpose",""))[:180],
                    "source_id": src, "confidence": r.get("confidence",""), "notes": str(r.get("notes",""))[:240]})
                for x in all_inv + lead:
                    inv_link_rows.append({"link_id": f"IL{len(inv_link_rows)+1:05d}", "startup_id": sid, "investor_id": R.investor(x),
                        "investor_name": x, "round_type": rt, "round_date": adate, "lead": "lead" if x in lead else "",
                        "disclosed_amount": v if v else "", "source_id": src, "confidence": r.get("confidence","")})
            # founders / people  (write-time dedupe: case/space-insensitive name+role identity)
            def _nk(v): import re as _r; return _r.sub(r"\\s+"," ",_r.sub(r"[^a-z ]","",(str(v).lower()))).strip()
            for p in d.get("founders") or []:
                _fk=(sid,_nk(g(p,"name")))
                if _fk in _FSEEEN: continue
                _FSEEEN.add(_fk)
                pid = R.person(g(p,"name"))
                fsrc = R.source(p.get("source_url",""), sid, claim=f"founder {g(p,'name')}", fields="FOUNDERS")
                founders_rows.append({"founder_id": f"FDR{len(founders_rows)+1:04d}", "startup_id": sid, "person_id": pid,
                    "name": g(p,"name"), "role_title": g(p,"role","role_title","title"), "founder_type": g(p,"type","founder_type"),
                    "active": g(p,"still_active","active"), "departure_date": g(p,"departure_date"), "education": str(g(p,"education","background"))[:180],
                    "prev_companies": str(g(p,"prev_companies","previous"))[:180], "linkedin": g(p,"linkedin"), "location": g(p,"location"),
                    "source_id": fsrc, "confidence": g(p,"confidence")})
            for p in d.get("people") or []:
                _pk=(sid,_nk(g(p,"name")),_nk(g(p,"position","role")))
                if _pk in _PSEEEN: continue
                _PSEEEN.add(_pk)
                pid = R.person(g(p,"name"))
                people_rows.append({"person_id": pid, "startup_id": sid, "name": g(p,"name"), "position": g(p,"position","role"),
                    "start_date": g(p,"start","start_date"), "end_date": g(p,"end","end_date"), "prev": g(p,"prev","prev_employer"),
                    "linkedin": g(p,"linkedin"), "source_id": R.source(p.get("source_url",""), sid, claim=f"person {g(p,'name')}", fields="PEOPLE"),
                    "confidence": g(p,"confidence")})
            # investors meta + links typed
            for x in d.get("investor_links") or []:
                src = R.source(x.get("source_url",""), sid, claim="investor link", fields="INVESTORS")
                inv_link_rows.append({"link_id": f"IL{len(inv_link_rows)+1:05d}", "startup_id": sid, "investor_id": R.investor(g(x,"investor","name")),
                    "investor_name": g(x,"investor","name"), "investor_type": g(x,"investor_type"), "first_seen": g(x,"first_seen","first_investment"),
                    "rounds": str(g(x,"rounds")), "lead": str(g(x,"lead")), "amount": g(x,"amount"), "board_seat": g(x,"board_seat"),
                    "status": g(x,"status"), "source_id": src, "confidence": g(x,"confidence")})
            for im in d.get("investors_meta") or []:
                iid = R.investor(g(im,"investor","name"))
                for iv in R.investors.values():
                    if iv["investor_id"] == iid:
                        iv["type"] = iv.get("type") or g(im,"type"); iv["geography"] = iv.get("geography") or g(im,"hq","geography")
                        iv["india_presence"] = iv.get("india_presence") or g(im,"india_office","india_presence")
                        iv["notes"] = (iv.get("notes","") + " | " + g(im,"notes")).strip(" |")[:200]
            # financials
            # normalize messy financial values in place -> numeric value + unit + currency (Phase 3 §8)
            def _norm_fin(r_):
                if not isinstance(r_, dict): return
                v_ = r_.get("value")
                if isinstance(v_, (int, float)): return
                sv_ = str(v_ or "").strip()
                if not sv_: return
                mm_ = re.match(r"^(?:rs\.?|inr|\u20b9)?\s*([\d,.]+)\s*(crore|cr|lakh|lac|million|mn|billion|bn|k)?", sv_, re.I)
                if mm_:
                    try: r_["value"] = float(mm_.group(1).replace(",",""))
                    except ValueError: return
                    u_ = (mm_.group(2) or "").lower()
                    if u_ in ("crore","cr"): r_["unit"] = "crore"
                    elif u_ in ("lakh","lac"): r_["unit"] = "lakh"
                    elif u_ in ("million","mn"): r_["unit"] = "million"
                    elif u_ in ("billion","bn"): r_["unit"] = "billion"
                    if re.search(r"(rs\.?|inr|\u20b9)", sv_, re.I): r_["currency"] = "INR"
                    elif "$" in sv_: r_["currency"] = "USD"
                    mx_ = re.search(r"\(?~?\$([\d,.]+)\s*(m|b|bn|billion|million)", sv_, re.I)
                    if mx_: r_["notes"] = (str(r_.get("notes","")).strip()+" | ").lstrip("| ") + f"USD approx ${mx_.group(1)}{(mx_.group(2) or '').lower()} per source"
                    my_ = re.search(r"\((\d{4})\)", sv_)
                    if my_: r_["notes"] = (str(r_.get("notes","")).strip()+" | ").lstrip("| ") + f"year stated in source value: {my_.group(1)}"
                else:
                    r_["value"] = None
                    r_["notes"] = (str(r_.get("notes","")).strip()+" | ").lstrip("| ") + f"unparseable value text preserved: {sv_[:60]}"
            for _fr_ in (d.get("financials") or []): _norm_fin(_fr_)
            for fr in d.get("financials") or []:
                if not isinstance(fr, dict): continue
                src = R.source(fr.get("source_url",""), sid, title=fr.get("source_title",""), pub_date=fr.get("source_date",""),
                               claim="financials", fields="FINANCIALS", conf=fr.get("confidence",""))
                fy = str(fr.get("fiscal_year","")).upper().replace("FY", "FY")
                if fy and not re.search(r"FY\d{2}", fy):  # no FY token (bare years/UNKNOWN/etc): Phase 3 §8
                    fr = dict(fr); fr["period"] = str(fr.get("period") or "") or f"calendar year {fy}"
                    fr["notes"] = (str(fr.get("notes","")).strip()+" | ").lstrip("| ") + f"calendar-year source stated as {fy}; no FY mapping inferred"
                    fy = ""
                fin_rows.append({"fy_record_id": f"FIN{len(fin_rows)+1:05d}", "startup_id": sid, "fiscal_year": fy,
                    "period": str(fr.get("period","")), "metric": str(fr.get("metric","")).lower(), "value": fr.get("value",""),
                    "unit": fr.get("unit",""), "currency": fr.get("currency","INR"), "value_type": fr.get("value_type") or fr.get("tier") or "",
                    "basis": fr.get("basis",""), "consolidated": fr.get("consolidated",""), "filing_date": fr.get("filing_date",""),
                    "source_id": src, "confidence": fr.get("confidence",""), "notes": str(fr.get("notes",""))[:160]})
            for list_key, sheet in [("products","PRODUCTS"),("customers","CUSTOMERS"),("partnerships","PARTNERSHIPS"),("competitors","COMPETITORS"),("acquisitions","ACQUISITIONS"),("locations","LOCATIONS"),("hiring","HIRING"),("legal","LEGAL_REGULATORY"),("events","NEWS_EVENTS"),("traction","TRACTION")]:
                for x in d.get(list_key) or []:
                    if not isinstance(x, dict): continue
                    src = R.source(x.get("source_url",""), sid, claim=str(x.get("name") or x.get("headline") or x.get("type") or sheet)[:120], fields=sheet, conf=x.get("confidence",""))
                    pid_prefix = {"PRODUCTS":"PRD","CUSTOMERS":"CUS","PARTNERSHIPS":"PRT","COMPETITORS":"CMP","ACQUISITIONS":"TXN","LOCATIONS":"LOC","HIRING":"HIRE","LEGAL_REGULATORY":"LGL","NEWS_EVENTS":"EVT","TRACTION":"MET"}[sheet]
                    base = {"startup_id": sid, "source_id": src, "confidence": x.get("confidence","")}
                    if sheet == "PRODUCTS": prod_rows.append({"product_id": f"{pid_prefix}{len(prod_rows)+1:04d}", **base, "name": g(x,"name","product_name"), "category": g(x,"category"), "description": str(g(x,"description"))[:220], "b2b_b2c": g(x,"b2b_b2c","target_customer"), "pricing_model": g(x,"pricing_model","pricing"), "launch_date": g(x,"launch_date"), "status": g(x,"status"), "notes": g(x,"notes")})
                    elif sheet == "CUSTOMERS": cust_rows.append({"customer_id": f"{pid_prefix}{len(cust_rows)+1:04d}", **base, "name": g(x,"name","customer_name","customer"), "type": g(x,"type","customer_type"), "geography": g(x,"geography"), "announced_date": g(x,"announced_date","date"), "status": g(x,"status"), "notes": g(x,"notes","relationship")})
                    elif sheet == "PARTNERSHIPS": part_rows.append({"partnership_id": f"{pid_prefix}{len(part_rows)+1:04d}", **base, "partner": g(x,"partner","name"), "type": g(x,"type"), "announced_date": g(x,"announced_date","date"), "purpose": str(g(x,"purpose","description"))[:180], "duration": g(x,"duration"), "status": g(x,"status"), "notes": g(x,"notes")})
                    elif sheet == "COMPETITORS": comp_rows.append({"competitor_id": f"{pid_prefix}{len(comp_rows)+1:04d}", **base, "competitor": g(x,"name","competitor"), "category": g(x,"category"), "basis": g(x,"basis","why"), "geography": g(x,"geography"), "notes": str(g(x,"notes","overlap"))[:160]})
                    elif sheet == "ACQUISITIONS": acq_rows.append({"txn_id": f"{pid_prefix}{len(acq_rows)+1:04d}", **base, "direction": g(x,"direction"), "type": g(x,"type","deal_type"), "target_or_buyer": g(x,"target","buyer","name"), "counterparty": g(x,"counterparty","seller"), "date": g(x,"date","transaction_date"), "value": str(g(x,"value")), "disclosed": g(x,"disclosed"), "rationale": str(g(x,"rationale"))[:180], "notes": g(x,"notes")})
                    elif sheet == "LOCATIONS": loc_rows.append({"location_id": f"{pid_prefix}{len(loc_rows)+1:04d}", **base, "type": g(x,"type"), "address_or_area": g(x,"address_or_area","address"), "city": g(x,"city"), "state": g(x,"state"), "neighborhood": g(x,"neighborhood_if_mblr","neighborhood"), "as_of": g(x,"as_of","date"), "notes": g(x,"notes")})
                    elif sheet == "HIRING": hire_rows.append({"hiring_id": f"{pid_prefix}{len(hire_rows)+1:04d}", **base, "fact_type": g(x,"fact_type","type"), "value": str(g(x,"value")), "as_of": g(x,"as_of","date"), "notes": str(g(x,"notes"))[:160]})
                    elif sheet == "LEGAL_REGULATORY": legal_rows.append({"case_id": f"{pid_prefix}{len(legal_rows)+1:04d}", **base, "type": g(x,"type"), "regulator": g(x,"regulator"), "jurisdiction": g(x,"jurisdiction"), "summary": str(g(x,"summary"))[:240], "dates": g(x,"dates","date"), "status": g(x,"status"), "notes": g(x,"notes")})
                    elif sheet == "NEWS_EVENTS": event_rows.append({"event_id": f"{pid_prefix}{len(event_rows)+1:05d}", **base, "event_date": g(x,"date","event_date"), "announced_date": g(x,"announced_date"), "type": g(x,"type","event_type"), "headline": str(g(x,"headline"))[:180], "description": str(g(x,"description"))[:240]})
                    elif sheet == "TRACTION": trk_rows.append({"metric_id": f"{pid_prefix}{len(trk_rows)+1:05d}", **base, "metric": g(x,"metric"), "value": str(g(x,"value")), "unit": g(x,"unit"), "period": g(x,"period","as_of"), "as_of": g(x,"as_of"), "company_reported": g(x,"company_reported"), "notes": g(x,"notes")})
            for x in d.get("conflicts") or []:
                R.source(x.get("url_a") or "", sid, claim=str(x.get("claim_a",""))[:120], fields="conflict", note="conflict A")
                R.source(x.get("url_b") or "", sid, claim=str(x.get("claim_b",""))[:120], fields="conflict", note="conflict B")
                row["notes"] = (str(row["notes"]) + f" | CONFLICT[{g(x,'field')}]: {str(g(x,'resolution'))[:80]}").strip(" |")
            for x in d.get("research_log") or []:
                _lg = {"date": str(g(x,"date") or "2026-09-14")[:10], "startup_id": sid, "company": u["company_name"], "query": str(g(x,"query"))[:180],
                                 "found": str(g(x,"found"))[:200], "unresolved": str(g(x,"unresolved"))[:160], "next_action": str(g(x,"next_action"))[:160],
                                 "agent": str(g(x,"agent") or g(x,"lane") or "subagent"), "status": str(g(x,"status") or "logged")}
                _dk = (_lg["startup_id"], _lg["query"].lower()[:70], _lg["date"])
                if _dk in _LOGDEDUP:
                    _LOGDEDUP[_dk]["reps"] += 1
                    if _lg["found"]: _LOGDEDUP[_dk]["found"] = _lg["found"]
                    if _lg["status"] != "logged": _LOGDEDUP[_dk]["status"] = _lg["status"]
                else:
                    _lg["reps"] = 1; _LOGDEDUP[_dk] = _lg; log_rows.append(_lg)
            gaps = d.get("gaps") or []
            if gaps: row["notes"] = (str(row["notes"]) + " | GAPS: " + "; ".join(str(x) for x in gaps)[:240]).strip(" |")
            # TECHNOLOGY: ip_tech_ai payloads (Phase 3 §4 technology coverage) were previously dropped
            _ipt = d.get("ip_tech_ai") or []
            _ipt = _ipt if isinstance(_ipt, list) else [_ipt]
            _META = ("source_url","src","confidence","conf","asof","as_of","date","tier","url","notes","canonical_key")
            for _tx in _ipt:
                if not isinstance(_tx, dict): continue
                _tsu = str(_tx.get("source_url") or _tx.get("src") or "")
                _tconf = str(_tx.get("confidence") or _tx.get("conf") or "MEDIUM")
                _tas = str(_tx.get("asof") or _tx.get("as_of") or "")[:10]
                _tnote = str(_tx.get("notes") or "")[:120]
                _tsrc = R.source(_tsu, sid, claim="tech fact", fields="TECHNOLOGY") if _tsu.startswith("http") and valid_url(norm_url(_tsu)) else ""
                for _tk, _tv in _tx.items():
                    if str(_tk).lower().strip() in _META: continue
                    _tvs = (str(_tv.get("v") if isinstance(_tv,dict) else _tv) or "").strip()
                    if not _tvs or _tvs.upper() in ("UNKNOWN","N/A","NA","UNDISCLOSED","NONE","SEE SOURCES","NOT PUBLIC","TBD","-","MEDIUM","HIGH","LOW","ESTIMATE","UNVERIFIED"): continue
                    _cat = {"stack":"stack","patents":"patent","patent":"patent","trademarks":"brand","trademark":"brand","ai_notes":"ai","ai":"ai","ai_models":"ai-model","models":"ai-model","tech":"stack","technology":"stack","api":"api","apis":"api","cloud":"cloud","infrastructure":"infrastructure","oss":"open-source","open_source":"open-source","github":"open-source","proprietary":"proprietary","ip":"ip","platform":"platform","engines":"ai-model"}.get(str(_tk).lower().strip(),"other")
                    _curl = _tvs if _tvs.startswith("http") else _tsu
                    claims_desc = _tvs[:220] if not _tvs.startswith("http") else "linked resource"
                    tech_rows.append({"tech_id": f"TEC{len(tech_rows)+1:04d}","startup_id": sid,"entity": u["company_name"],"category": _cat,"name": str(_tk),"description": claims_desc,"url": _curl[:160],"as_of": _tas,"source_id": _tsrc,"confidence": _tconf,"notes": _tnote})
            # CLAIMS: dict-shaped company fields are explicit evidence claims (Phase 3 §6)
            _ent = str(c.get("company_name") or u["company_name"])
            for _cf, _cv in c.items():
                if isinstance(_cv, dict) and str(_cv.get("v") or "").strip():
                    _su = str(_cv.get("src") or "")
                    _csr = R.source(_su, sid, claim=str(_cf)+" claim", fields="CLAIMS", conf=_cv.get("conf","")) if _su.startswith("http") and valid_url(norm_url(_su)) else ""
                    claims_rows.append({"claim_id": f"CL{len(claims_rows)+1:05d}","startup_id": sid,"entity": _ent,"field": str(_cf),"claim_value": str(_cv.get("v"))[:200],"value_type": "company-field","unit": "","currency": "","date_from": str(_cv.get("asof") or _cv.get("date") or "")[:10],"date_to": "","source_id": _csr,"confidence": str(_cv.get("conf") or "MEDIUM"),"status": "current","preferred": "yes","notes": str(_cv.get("note") or "")[:140]})
            # CONFLICTS: preserve every recorded disagreement (Phase 3 §7)
            for _cf_ in (d.get("conflicts") or []):
                if not isinstance(_cf_, dict): _cf_ = {"field": "general", "claim_a": str(_cf_)}
                _ck=(sid,str(_cf_.get("field") or "").lower()[:40],str(_cf_.get("claim_a") or "")[:50].lower(),str(_cf_.get("claim_b") or "")[:50].lower())
                if _ck in _CNSEEN: continue
                _CNSEEN.add(_ck)
                _ua = str(_cf_.get("url_a") or ""); _ub = str(_cf_.get("url_b") or "")
                _sa = R.source(_ua, sid, claim="conflict side A", fields="CONFLICTS") if _ua.startswith("http") and valid_url(norm_url(_ua)) else _ua[:60]
                _sb = R.source(_ub, sid, claim="conflict side B", fields="CONFLICTS") if _ub.startswith("http") and valid_url(norm_url(_ub)) else _ub[:60]
                _resl = str(_cf_.get("resolution") or ""); _rv = str(_cf_.get("resolved_value") or "")
                _rl = _resl.lower()
                _rs = "resolved" if _rv and _resl and not any(k in _rl for k in ("unresolv","preserve","both","open")) else ("preserved-conflict" if _resl or _rv else "unresolved")
                conflicts_rows.append({"conflict_id": f"CF{len(conflicts_rows)+1:05d}","startup_id": sid,"field": str(_cf_.get("field") or _cf_.get("note") or "general")[:90],"claim_a": str(_cf_.get("claim_a") or _cf_.get("note") or "")[:230],"source_a": _sa,"claim_b": str(_cf_.get("claim_b") or "")[:230],"source_b": _sb,"preferred_claim": (_rv[:200] if _rv else "unresolved - both preserved"),"resolution": _resl[:240],"resolution_status": _rs,"last_reviewed": str(_cf_.get("reviewed") or "2026-09-15")[:10]})
            # aggregates
            tot_eq = sum(fr["amount_inr_mn"] for fr in funding_rows if fr["startup_id"] == sid and str(fr["round_type"]).lower() not in ("debt","venture debt","unknown","ipo") and isinstance(fr["amount_inr_mn"], float))
            tot_debt = sum(fr["amount_inr_mn"] for fr in funding_rows if fr["startup_id"] == sid and "debt" in str(fr["round_type"]).lower() and isinstance(fr["amount_inr_mn"], float))
            dated = [fr for fr in funding_rows if fr["startup_id"] == sid and fr["announcement_date"]]
            if tot_eq:
                row["total_funding_disclosed"] = f"{round(tot_eq,1)} Mn INR (equity, DERIVED)"
            if tot_debt: row["total_funding_disclosed"] = str(row["total_funding_disclosed"]) + f" + {round(tot_debt,1)} Mn INR (debt)"
            for fr in funding_rows:
                if fr["startup_id"]==sid and str(fr["round_type"]).lower()=="ipo":
                    row["total_funding_disclosed"] = str(row["total_funding_disclosed"]) + f' | IPO issue {fr["amount"]} {fr["currency"]}Mn (excluded from private equity total)'

            if dated:
                last = max(dated, key=lambda x: str(x["announcement_date"]))
                row["last_funding_date"] = last["announcement_date"]; row["last_funding_round"] = str(last["round_type"])
            # latest revenue/PAT from financials
            for mkey, col, ycol in [("revenue","revenue_latest_fy","revenue_latest_fy_period"),("net profit","profit_loss_latest_fy","profit_loss_latest_fy_period"),("pat","profit_loss_latest_fy","profit_loss_latest_fy_period"),("profit after tax","profit_loss_latest_fy","profit_loss_latest_fy_period"),("loss","profit_loss_latest_fy","profit_loss_latest_fy_period"),("net loss","profit_loss_latest_fy","profit_loss_latest_fy_period")]:
                for fr in sorted([x for x in fin_rows if x["startup_id"]==sid and mkey in str(x["metric"])], key=lambda x: str(x["fiscal_year"])):
                    if fr["value"] != "":
                        row[col] = fr["value"]; row[ycol] = f"{fr['fiscal_year']} {fr.get('unit','')} {fr.get('currency','')}".strip(); row["revenue_latest_fy_year"] = fr["fiscal_year"]
            v, cf, src = gv(c, "last_known_valuation")
            if v: row["last_known_valuation"] = str(v)[:60]
            _city = c.get("city"); _city = (_city.get("v","") if isinstance(_city,dict) else str(_city or ""))
            if _city:
                row["city"] = _city
                _st={"Mumbai":"Maharashtra","Bengaluru":"Karnataka","Pune":"Maharashtra","Gurugram":"Haryana","Noida":"Uttar Pradesh","Delhi":"Delhi","Delhi NCR":"Delhi","Hyderabad":"Telangana","Chennai":"Tamil Nadu","Ahmedabad":"Gujarat","Kolkata":"West Bengal","Indore":"Madhya Pradesh","Mysuru":"Karnataka","Northbrook":"Illinois, USA","San Francisco":"California, USA","SF":"California, USA"}
                row["state"] = _st.get(_city, u["state"] if _city==u["city"] else "")
                if _city != u["city"] and u["city"] in ("Mumbai","Bengaluru"):
                    row["notes"] = (row.get("notes","")+" | ").lstrip(" | ")+f"City corrected from discovery seed ({u['city']}) to {_city} per enrichment."
            ps = c.get("parent/subsidiary") or c.get("parent_subsidiary")
            if ps: row["notes"] = (str(row["notes"]) + f" | PARENT/SUBSIDIARY: {str(ps)[:180]}").strip(" |")
            if not row.get("total_funding_disclosed") and c.get("total_funding_disclosed"):
                row["total_funding_disclosed"] = f"as-stated(enrich): {str(c['total_funding_disclosed'])[:120]}"
            for kk3 in ("last_funding_date","last_funding_round"):
                if not row.get(kk3) and c.get(kk3): row[kk3]=str(c[kk3])[:80]
            _cin = str(row.get("cin") or "")
            if len(_cin) >= 4 and _cin[2:4].isalpha():
                _st2 = _cin[2:4].upper()
                _expect = CITYST.get(row.get("city",""), CISTATE.get(row.get("state",""), ""))
                if _expect and _st2 != _expect and _st2 in STCODE:
                    row["cin"] = _cin + f" [STATE-CODE {STCODE[_st2]} MISMATCH vs city {row['city']} — verify entity]"
                    row["notes"] = (str(row["notes"]) + " | CIN state-code mismatch: aggregator page may list a sister entity.").strip(" |")
            conf = g(c, "confidence") or conf
        else:
            # shallow row from discovery
            if u["discovery_urls"]: prim_src = R.source(u["discovery_urls"][0], sid, title=u.get("why_notable",""), fields="STARTUPS", conf="LOW")
            row["primary_sector"] = u["sector_guess"].split("|")[0].strip()[:60]
            row["startup_stage"] = u["stage_guess"][:60]; row["status"] = (u["status_hint"] or "Active (reported)")[:80]
            if u["funding_musd_hint"]: row["total_funding_disclosed"] = f"~{round(inr_mn(u['funding_musd_hint'],'USD',year_of(u.get('recency','')) or 2025),1)} Mn INR (hint, UNVERIFIED)"
            row["confidence"] = "UNVERIFIED"; row["notes"] = (row["notes"] or "") + " Shallow candidate: discovery-layer only."
        row.setdefault("confidence", conf); row["confidence"] = row["confidence"] or conf
        row["last_verified"] = last_ver; row["primary_source_id"] = prim_src or (row.get("primary_source_id") or "")
        import re as _re2
        if not row.get("aliases","").strip():
            _nm=str(row["company_name"]).lower()
            _an=[]
            for x in (u.get("all_names") or []):
                base=_re2.sub(r"\s*\([^)]*\)","",str(x)).strip()
                alts={str(x).lower(),base.lower()}
                if not alts- {_nm, u.get("canonical_key","").lower(), ""}: continue
                if base and base.lower()!=_nm and base.lower() not in _nm: _an.append(base)
            if _an: row["aliases"]=_re2.sub(r"\s+"," ","; ".join(dict.fromkeys(_an)))[:100].strip(" ;")
        _mm = _re2.search(r"\(([^)]{2,40})\)", row["company_name"])
        if _mm:
            row["aliases"] = (_mm.group(1).strip() + ("; " + row["aliases"] if row.get("aliases") else ""))[:100]
        if not (row.get("parent_company","").strip() or row.get("subsidiary_of","").strip()):
            _nb=(str(row.get("notes",""))+" "+str(row.get("status",""))).lower()
            _m=re.search(r"(?:subsidiary of|owned by)\s+([a-z0-9][\w &.'\-]{2,45}?)(?=[,;\)]|\s\||$|\s(?:\(|pvt|ltd|limited))",_nb)
            if _m: row["parent_company"]=_m.group(1).strip().title(); row["subsidiary_of"]=row["parent_company"]
            if row.get("parent_company"):
                _pc=re.split(r"\s+(?:Since|Sep|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Oct|Nov|Dec|Acquirer|Announced|Deal|Stake|Roughly|Approx)[\w .\-]*$", str(row["parent_company"]), flags=re.I)[0].strip()
                _pc={"Nxp Semiconductors":"NXP Semiconductors","Eternal":"Eternal Ltd (Blinkit parent)","Marico":"Marico Ltd","Adobe":"Adobe Inc.","Udaan":"Udaan","Meesho":"Meesho","Pine Labs":"Pine Labs","Up Grad":"upGrad"}.get(_pc,_pc)
                row["parent_company"]=_pc; row["subsidiary_of"]=_pc
            else:
                _m=re.search(r"(?:acquired by|bought by)\s+([a-z0-9][\w &.'\-]{2,45}?)(?=[,;\)]|\s\||$|\s(?:\(|pvt|ltd|limited))",_nb)
                if _m: row["parent_company"]=_m.group(1).strip().title(); row["subsidiary_of"]=row["parent_company"]
            if row.get("parent_company"):
                _pc=re.split(r"\s+(?:Since|Sep|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Oct|Nov|Dec|Acquirer|Announced|Deal|Stake|Roughly|Approx)[\w .\-]*$", str(row["parent_company"]), flags=re.I)[0].strip()
                _pc={"Nxp Semiconductors":"NXP Semiconductors","Eternal":"Eternal Ltd (Blinkit parent)","Marico":"Marico Ltd","Adobe":"Adobe Inc.","Udaan":"Udaan","Meesho":"Meesho","Pine Labs":"Pine Labs"}.get(_pc,_pc)
                row["parent_company"]=_pc; row["subsidiary_of"]=_pc
        _w = (row.get("website") or "").strip()
        if _w:
            _o = URLAUDIT.get(norm_url(_w)) or URLAUDIT.get(_w)
            if _o: row["website_status"] = {"OK":"live","DEAD":"dead-404","BOTBLOCKED":"reachable(bot-blocked)"}.get(_o.split(":")[0], "unchecked:"+_o) + " @2026-09-14"
            elif row.get("website"): row["website_status"] = "unchecked (not in linkcheck set)"
        startups_rows.append(row)
        # scores
        score_rows.append(score_company(sid, u, d, R, funding_rows, fin_rows, founders_rows, sources_used(sid, R)))

    _IOVR = {}
    _ip = f"{BASE}/structured/investor_meta_overrides.json"
    if os.path.exists(_ip):
        import re as _ri
        _IOVR = { _ri.sub(r"[^a-z0-9]+"," ",str(k).lower()).strip(): v for k,v in json.load(open(_ip)).items() }
    def _iof(iv, key):
        _k=re.sub(r"[^a-z0-9]+"," ",str(iv["name"]).lower()).strip()
        _ov=_IOVR.get(_k)
        if _ov is None and len(_k)>=7:
            for ok_ in _IOVR:
                if ok_.startswith(_k) or _k.startswith(ok_): _ov=_IOVR[ok_]; break
        _ov=_ov or {}
        return iv.get(key) or _ov.get(key) or (_ov.get("hq_geography") if key=="geography" else "") or (_ov.get("source_url") if key=="_src" else "")
    inv_rows = [{"investor_id": iv["investor_id"], "name": iv["name"], "type": _iof(iv,"type"), "geography": _iof(iv,"geography"),
                 "fund_vintage": iv.get("fund_vintage",""), "notable_portfolio": iv.get("notable_portfolio",""), "india_presence": iv.get("india_presence",""),
                 "partner_if_public": iv.get("partner_if_public","")} for iv in sorted(R.investors.values(), key=lambda x: x["investor_id"])]
    src_rows = [{"source_id": s["source_id"], "startup_ids": ";".join(s["startup_ids"]), "url": s["url"], "title": str(s["title"])[:180],
                 "publisher": s["publisher"], "publication_date": s["publication_date"], "retrieved_date": s["retrieved_date"], "source_tier": s["tier"],
                 "source_type": "web", "claim": str(s["claim"])[:160], "supports_fields": s["fields"], "reliability": s["tier"], "confidence": s["conf"] or "MEDIUM", "notes": s["note"]}
                for s in R.urls.values()]
    log_rows = [log_entry("2026-09-14", "ALL", "(universe construction)",
      "Discovery waves: hubs+unicorns / sector lists / events+recency (web_search via subagent_opencode)",
      "379 deduped candidates (d1 139, d2 174, d3 120 rows pre-dedupe); Mumbai 64, Bengaluru 155",
      "DPIIT full registry not bulk-downloadable; aggregates captured in SOURCES meta notes",
      "Deep-enrich top-priority shortlist", "orchestrator", "done"),
     log_entry("2026-09-14", "ALL", "(enrichment waves)",
      "Pilot + 3 deep waves (58 cos) + lite wave (24 cos) via subagent_opencode, tinyfish fallback lane",
      "83 enriched JSONs; 251 funding rounds; 114 conflicts preserved; seed corrections Zepto/Darwinbox/Gupshup/Sarvam/MoEngage/Moglix/BrowserStack",
      "429 rate-limits handled via serialisation + fallback; 2 parallel-wave losses recovered by checkpoint protocol",
      "Final workbook build + link-liveness audit", "orchestrator", "done"),
     log_entry("2026-09-14", "ALL", "(QC layer)",
      "validate_db (FK/dup/format/caps) + URL liveness probe over all SOURCES + OOXML hyperlink/table/chart persistence audit",
      "0 validator ISSUES; 610/751 urls LIVE; 124 bot-blocked(vault-captured); 10 DEAD downgraded LOW; 6 charts cached; rels verified",
      "MCA audited filings + CINs remain the structural gap ceiling (no machine source); 284 shallow rows are the queued backlog",
      "Extensible: add SOURCES row -> reference source_id -> tables auto-expand", "orchestrator", "done")] + log_rows

    S = SHEETS
    def normconf(v):
        t=str(v or "").strip().lower().rstrip(".")
        if t in ("","0","none","null"): return ""
        m={"high":"HIGH","h":"HIGH","medium":"MEDIUM","med":"MEDIUM","medium-high":"MEDIUM","medium high":"MEDIUM","mid":"MEDIUM","low":"LOW","l":"LOW","unverified":"UNVERIFIED","confidential":"N/A"}
        if t in m: return m[t]
        try:
            f=float(t)
            if 0<f<=1: return "HIGH" if f>=0.85 else ("MEDIUM" if f>=0.5 else "LOW")
        except Exception: pass
        return "HIGH" if "high" in t and "medium" not in t else ("LOW" if "low" in t else "MEDIUM")
    import datetime as _dt
    def isofix(v):
        t=str(v or "").strip()
        if not t: return t
        t=re.sub(r"\s*\(.*?\)\s*","",t).strip()          # strip parentheticals
        for fmt in ("%Y-%m-%d","%d-%m-%Y","%d/%m/%Y","%m/%d/%Y","%d %b %Y","%d %B %Y","%b %d, %Y","%B %d, %Y","%Y-%m","%Y"):
            try: return _dt.datetime.strptime(t,fmt).strftime("%Y-%m-%d" if fmt!="%Y" else "%Y")
            except Exception: pass
        m=re.match(r"^(\d{4})[-/](\d{1,2})$",t)
        if m: return f"{m.group(1)}-{int(m.group(2)):02d}-01"
        if t.lower() in ("unknown","n/a","na","tbd","undisclosed","none","-"): return ""
        m=re.search(r"(\d{4}-\d{2}-\d{2})",t)
        if m: return m.group(1)
        m=re.match(r"^(19|20)\d{2}\b",t)
        if m: return t[:4]
        return t
    def dump(name, rows):
        DATEF={"founded_date","incorporation_date","last_funding_date","employee_estimate_date"}
        for r in rows:
            if not isinstance(r,dict): continue
            if "confidence" in r: r["confidence"]=normconf(r["confidence"])
            if name=="STARTUPS" and r.get("city"):
                _ct=str(r["city"])
                if "(" in _ct or ";" in _ct:
                    _pure=re.split(r"\s*\(|\s*;\s*",_ct)[0].strip()
                    _extra=_ct[len(_pure):].strip(" (;")
                    if _extra: r["notes"]=(str(r.get("notes",""))+f" | HQ/domicile detail: {_extra[:140]}").strip(" |")
                    r["city"]=_pure
            if name in ("STARTUPS","FUNDING"):
                _df = DATEF | {"announcement_date","round_date","closes_by_date"} if name=="FUNDING" else DATEF
                for k in r:
                    if k in _df:
                        orig=str(r[k] or ""); fixed=isofix(orig)
                        if fixed and not re.fullmatch(r"(\d{4}|\d{4}-\d{2}|\d{4}-\d{2}-\d{2})",fixed):
                            r["notes"]=(str(r.get("notes",""))+f" | {k} stated loosely: {orig[:60]}").strip(" |"); fixed=""
                        r[k]=fixed
        cols = COLS.get(name) or (list(rows[0].keys()) if rows and rows[0] else [])
        with open(f"{CSV_DIR}/{name}.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader()
            for r in rows: w.writerow({k: r.get(k, "") for k in cols})
    # DERIVED: company_class
    def _numf(x):
        try: return float(x)
        except Exception: return 0.0
    _known = {"WhatsApp":"Subsidiary"}
    for row in startups_rows:
        stt = str(row.get("status","")).lower(); pp = str(row.get("public_private","")).lower()
        parent = str(row.get("parent_company","")).strip()
        tot = _numf((re.sub(r"[^0-9.]","",str(row.get("total_funding_disclosed",""))) or "0"))
        inc_y = ""
        m2 = re.search(r"(20\d\d)", str(row.get("incorporation_date") or row.get("founded_date") or ""))
        if m2: inc_y = m2.group(1)
        cls = "Startup"
        if any(k in stt for k in ("defunct","shut","insolvent","liquidat","collapsed","merged into","acquired by")): cls = "Former startup" if any(k in stt for k in ("defunct","shut","insolvent","liquidat","collapsed")) else "Acquired (operating)"
        elif "listed" in pp or pp.startswith("public") or any(k in stt for k in ("ipo complete","publicly listed","listed on nse","listed on bse")): cls = "Public company"
        elif parent: cls = "Subsidiary"
        elif tot >= 50000 or (inc_y and int(inc_y) <= 2012 and tot >= 5000): cls = "Mature private company"
        elif tot >= 10000 or (inc_y and int(inc_y) <= 2016 and tot >= 2500): cls = "Scale-up"
        elif not stt.strip() or stt.strip().lower() in ("unknown","tbd"): cls = "Other - status unverified"
        cls = _known.get(row.get("company_name",""), cls)
        row["company_class"] = cls  # column is DERIVED (see README/SPEC)
    # DERIVED: new_or_existing by investor-repeat chronology per startup
    _by_s=defaultdict(list)
    for fr in funding_rows: _by_s[fr["startup_id"]].append(fr)
    for _sid,_rs in _by_s.items():
        _rs.sort(key=lambda x:str(x.get("round_date") or x.get("announcement_date") or "0000"))
        _seen=set()
        for _i,_fr in enumerate(_rs):
            if str(_fr.get("new_or_existing","")).strip(): continue
            _ids={a for a in re.split(r"[;,]\s*",str(_fr.get("investor_ids") or "")) if a}
            if _i==0: _fr["new_or_existing"]="initial (DERIVED)"
            elif _ids and _ids<=_seen: _fr["new_or_existing"]="all-follow-on (DERIVED)"
            elif _ids & _seen: _fr["new_or_existing"]="mixed (DERIVED)"
            elif _ids: _fr["new_or_existing"]="all-new-investors (DERIVED)"
            else: _fr["new_or_existing"]="unknown"
            _seen|=_ids
    name_by = {r["startup_id"]: r["company_name"] for r in startups_rows}
    for fr in funding_rows:
        _v = fr.get("amount")
        if _v not in ("", None):
            claims_rows.append({"claim_id": f"CL{len(claims_rows)+1:05d}","startup_id": fr["startup_id"],"entity": f'{name_by.get(fr["startup_id"],"")} {fr["round_type"]}',"field": "round_amount","claim_value": str(_v),"value_type": "money","unit": "million","currency": fr.get("currency",""),"date_from": str(fr.get("round_date") or fr.get("announcement_date") or "")[:10],"date_to": "","source_id": fr.get("source_id",""),"confidence": fr.get("confidence",""),"status": "current","preferred": "yes","notes": fr.get("purpose","")[:140]})
        if fr.get("valuation") not in ("", None):
            claims_rows.append({"claim_id": f"CL{len(claims_rows)+1:05d}","startup_id": fr["startup_id"],"entity": f'{name_by.get(fr["startup_id"],"")} {fr["round_type"]}',"field": "valuation","claim_value": str(fr["valuation"]),"value_type": "money","unit": "million","currency": fr.get("valuation_currency",""),"date_from": str(fr.get("round_date") or fr.get("announcement_date") or "")[:10],"date_to": "","source_id": fr.get("source_id",""),"confidence": fr.get("confidence",""),"status": "current","preferred": "yes","notes": str(fr.get("valuation_type","") or "")[:140]})
    for xr in fin_rows:
        if xr.get("value") in ("", None): continue
        claims_rows.append({"claim_id": f"CL{len(claims_rows)+1:05d}","startup_id": xr["startup_id"],"entity": name_by.get(xr["startup_id"],""),"field": str(xr.get("metric","")), "claim_value": str(xr["value"]),"value_type": str(xr.get("value_type") or "financial"),"unit": str(xr.get("unit","")),"currency": str(xr.get("currency","")),"date_from": "","date_to": "","source_id": xr.get("source_id",""),"confidence": xr.get("confidence",""),"status": "current","preferred": "yes","notes": f'FY {xr.get("fiscal_year","")} | basis {xr.get("basis","")} | cons {xr.get("consolidated","")}'[:140]})
    for xr in trk_rows:
        if xr.get("value") in ("", None): continue
        claims_rows.append({"claim_id": f"CL{len(claims_rows)+1:05d}","startup_id": xr["startup_id"],"entity": name_by.get(xr["startup_id"],""),"field": f"traction:{str(xr.get('metric',''))[:40]}","claim_value": str(xr["value"]),"value_type": "traction-metric","unit": str(xr.get("unit","")),"currency": str(xr.get("currency","") or ""),"date_from": str(xr.get("as_of") or "")[:10],"date_to": "","source_id": xr.get("source_id",""),"confidence": xr.get("confidence",""),"status": "current","preferred": "yes","notes": str(xr.get("period","") or "")[:140]})
    # RESEARCH_TASKS ledger: one row per (startup, research_area) task, from logs + gaps + coverage
    AREAS = ["identity","founders","funding","investors","financials","products","traction","people","customers","legal","locations","events"]
    KW = {"identity":["identity","legal","cin","incorporat","city","hq","status","website","profile","seed falsif"],
          "founders":["founder","co-founder","ceo","promoter"],
          "funding":["funding","round","series","raise","valuation","invest"],
          "investors":["investor","fund back","lead","backers"],
          "financials":["revenue","financial","profit","fy2","mca","audit"],
          "products":["product","launch","platform","app"],
          "traction":["user","gmv","arr","traction","customers count"],
          "people":["exec","hire","cxo","cto","cfo","team"],
          "customers":["customer","enterprise","client","logo"],
          "legal":["legal","lawsuit","regulatory","sebi","compliance"],
          "locations":["office","location","headquarter","facility","plant"],
          "events":["acquisition","acqui","partnership","event","expansion","ipo"]}
    def area_of(text):
        tl = str(text).lower(); out = []
        for a_, ks in KW.items():
            if any(k in tl for k in ks): out.append(a_)
        return out or ["identity"]
    score_by = {r["startup_id"]: r for r in score_rows}
    # ---- Phase 3 priority queue: importance x gap (never alphabetical/id order) ----
    import math as _math
    from collections import Counter as _Counter
    _news = _Counter(x["startup_id"] for x in event_rows)
    _MARQUEE = ["sequoia","greenoaks","tiger global","insight partners","founders fund","matrix partners","westbridge","newlight","softbank","a16z","andreesen","bond capital","peakxv","multiples","chirataei","mohr","temasek","gic ","nvidia capital","salesforce ventures","visa ","mastercard ","advent ","helion"]
    _il_names = defaultdict(set)
    for x in inv_link_rows:
        _il_names[x["startup_id"]].add(str(x.get("investor_name","")).lower())
    _sect_strategic = ("fintech","ai","deep tech","defence","semiconductor","climate","energy","healthtech","saas","cyber")
    def _tonum(x):
        try: return float(x)
        except Exception: return 0.0
    prio = {}
    for r in startups_rows:
        sid_ = r["startup_id"]; sr = score_by.get(sid_, {})
        fund_mn = _tonum((re.sub(r"[^0-9.]","",str(r.get("total_funding_disclosed",""))) or "0").split("Mn")[0][:10]) if r.get("total_funding_disclosed") else 0
        rev_cr = _tonum(r.get("revenue_latest_fy","")) if re.match(r"^[\d.-]+$", str(r.get("revenue_latest_fy",""))) else 0
        imp = min(40, _math.log10(max(1,fund_mn))*10) + min(20, _math.log10(max(1,rev_cr))*6.7)
        if r.get("city") in ("Mumbai","Bengaluru"): imp += 15
        _stg = str(r.get("startup_stage",""))
        imp += {"Decacorn":18,"Unicorn":15,"Growth":12,"Late stage":10,"Series C+":8,"Series B":6,"Series A":4,"Seed":2,"Pre-seed":1}.get(_stg,0)
        imp += min(10, _news.get(sid_,0)*2)
        if any(any(m in nm for m in _MARQUEE) for nm in _il_names.get(sid_,())): imp += 8
        if any(k in str(r.get("primary_sector","")).lower() for k in _sect_strategic): imp += 5
        if str(r.get("last_funding_date","")) >= "2025-03-01": imp += 5
        if r.get("company_class") == "Former startup": imp *= 0.2
        imp = min(100, imp)
        comp_ = _tonum(sr.get("completeness_pct", 0))
        gap = (100 - comp_)
        gap += {"low":8,"moderate":16,"high":24}.get(str(sr.get("conflict_level","")),0)
        if _tonum(sr.get("source_quality_pct",100)) < 40: gap += 12
        if _tonum(sr.get("freshness_pct",100)) <= 40: gap += 10
        prio[sid_] = {"importance": round(imp,1), "gap": round(gap,0), "priority_score": round(imp*gap/100,1)}
    _order = sorted(prio, key=lambda k: -prio[k]["priority_score"])
    _exhaust = set(_order[:38]); _target = set(_order[:100])
    for i, sid_ in enumerate(_order, 1):
        sr = score_by.get(sid_)
        if sr is None: continue
        sr["priority_score"] = prio[sid_]["priority_score"]; sr["priority_rank"] = i
        sr["cohort"] = "EXHAUST" if sid_ in _exhaust else ("TARGET" if sid_ in _target else "")
    json.dump({"exhaust":[list(_exhaust)][0],"target":[x for x in _order[:100] if x not in _exhaust],"scores":{k:prio[k] for k in _order[:100]}}, open("structured/priority_cohort.json","w"), indent=1)
    tasks_rows = []
    agg = {}
    for lg in log_rows:
        sid_ = lg["startup_id"]
        if sid_ not in U: continue
        for ar in area_of(lg["query"]):
            t = agg.setdefault((sid_, ar), {"started": lg["date"], "completed": "", "logs": 0, "reps": 0, "result": "", "next_action": "", "agent": lg.get("agent","")})
            t["started"] = min(t["started"], lg["date"]); t["completed"] = max(t["completed"], lg["date"])
            t["logs"] += 1; t["reps"] += int(lg.get("reps") or 1)
            if lg["found"]: t["result"] = lg["found"][:160]
            if lg["next_action"]: t["next_action"] = lg["next_action"][:120]
    u2 = {sid: u for sid, u in U.items()}
    gaps_by_sid = {r["startup_id"]: r.get("notes","") for r in startups_rows}
    ti = 0
    final_tasks = []
    for (sid_, ar), t in sorted(agg.items()):
        ti += 1
        sr = score_by.get(sid_, {})
        band = float(sr.get("score_" + ar, 0))
        _cf_ = str(sr.get("conflict_level","none")); _fr_ = float(sr.get("freshness_pct",0) or 0)
        status = ("blocked" if band == 0 and int(t.get("reps") or 1) >= 2 else "logged-no-result" if band == 0 else ("needs-verification" if (_cf_ in ("moderate","high") or _fr_ <= 40) else "completed"))
        if status in ("completed","needs-verification") and not t["result"]: t["result"] = "evidence present in data tables (see CLAIMS source_id)"
        if status == "blocked": t["next_action"] = "dead end: >=2 attempts w/o result; revisit only if new sources exist"
        _prio_ = "P1" if sid_ in _exhaust else ("P2" if sid_ in _target else "P3")
        final_tasks.append({"task_id": f"RT{ti:04d}","startup_id": sid_,"company": u2[sid_]["company_name"],"research_area": ar,"priority": _prio_,"assigned": t["agent"] or "subagent","started": t["started"],"completed": t["completed"],"result": t["result"],"next_action": "","status": status,"log_events": t["reps"]})
    st_by = {r["startup_id"]: r for r in startups_rows}
    import glob as _glob
    _ACTIVE_P3 = {os.path.basename(f)[:-8].lower() for f in _glob.glob("gapfill/*.p3.json")}
    for sr in score_rows:
        sid_ = sr["startup_id"]
        _in_cohort = sid_ in _exhaust or sid_ in _target
        if sr["tier"] not in ("Candidate","Basic") and not _in_cohort: continue
        for ar in AREAS:
            _b0 = float(sr.get("score_" + ar, 0)) == 0
            if (sid_, ar) in agg and not (_in_cohort and _b0): continue
            if (sid_, ar) in agg and _in_cohort and _b0 and any(ft_["startup_id"]==sid_ and ft_["research_area"]==ar for ft_ in final_tasks): continue
            if not _b0 and (sid_, ar) in agg: continue
            ti += 1
            _cls = st_by.get(sid_,{}).get("company_class","")
            if _cls == "Former startup": _p_ = "P4"
            elif sid_ in _exhaust: _p_ = "P1"
            elif sid_ in _target: _p_ = "P2"
            else: _p_ = "P1" if ar in ("identity","funding","founders","financials") else "P3"
            _key_ = str(u2[sid_].get("canonical_key","")).lower().strip()
            _live_ = _key_ in _ACTIVE_P3
            final_tasks.append({"task_id": f"RT{ti:04d}","startup_id": sid_,"company": u2[sid_]["company_name"],"research_area": ar,"priority": _p_,"assigned": "p3-agent(wave)" if _live_ else "unassigned","started": "2026-09-15" if _live_ else "","completed": "","result": "","next_action": ("LIVE: p3 payload pending merge" if _live_ else f"gap: {ar} at coverage 0 for {sr['tier']} record ({_cls or 'class?'}; priority {prio.get(sid_,{}).get('priority_score','?')} score)"),"status": "in_progress" if _live_ else "not_started","log_events": 0})
    # ================= Phase 4: §28 RESEARCH_CONTROL + §27 next_best_action + §8 DERIVED_METRICS =================
    def _fy_num(x):
        m=re.search(r"FY\s?(\d{2})$", str(x).strip()) or re.search(r"FY(\d{4})", str(x))
        return int(m.group(1)) if m else None
    _fin_fy = defaultdict(set); _rev = defaultdict(dict); _pat = defaultdict(dict)
    for fr_ in fin_rows:
        n_ = _fy_num(fr_.get("fiscal_year"))
        if n_ is None: continue
        _fin_fy[fr_["startup_id"]].add(n_)
        met = str(fr_.get("metric","")).lower(); v_ = _tonum(fr_.get("value"))
        cur = str(fr_.get("currency","INR")).upper(); un_ = str(fr_.get("unit","")).lower()
        if not v_ or cur != "INR": continue
        if "crore" not in un_ and un_ not in ("cr",""): continue
        if ("revenue" in met or met in ("total income","turnover","gross income")) and "per" not in met and n_ not in _rev[fr_["startup_id"]]: _rev[fr_["startup_id"]][n_] = v_
        if any(k in met for k in ("net profit","pat","profit after tax","net loss","loss for the year","net income")) and n_ not in _pat[fr_["startup_id"]]: _pat[fr_["startup_id"]][n_] = v_
    _emp = {}
    for tr_ in trk_rows:
        if str(tr_.get("metric","")).lower() in ("employees","headcount","team size") and _tonum(tr_.get("value")):
            sd_=tr_["startup_id"]
            if sd_ not in _emp or str(tr_.get("as_of","")) > str(_emp[sd_].get("as_of","")): _emp[sd_] = tr_
    _fund_cr = defaultdict(float); _fund_fx_bad = set()
    for rd_ in funding_rows:
        v_ = _tonum(rd_.get("amount")); cur = str(rd_.get("currency","")).upper(); un_ = str(rd_.get("unit","")).lower()
        if not v_: continue
        if cur == "INR" and un_ in ("crore","cr",""): _fund_cr[rd_["startup_id"]] += v_
        elif cur: _fund_fx_bad.add(rd_["startup_id"])
    _val_cr = {}; _val_fy = {}
    for rd_ in funding_rows:
        v_ = _tonum(rd_.get("valuation")); cur = str(rd_.get("currency","")).upper(); un_ = str(rd_.get("unit","")).lower()
        d_ = str(rd_.get("date",""))
        if v_ and cur == "INR" and un_ in ("crore","cr","") and str(rd_.get("valuation_type","")).lower() in ("post-money","pre-money",""):
            sd_=rd_["startup_id"]
            if sd_ not in _val_cr or d_ > _val_fy.get(sd_,""): _val_cr[sd_] = v_; _val_fy[sd_] = d_
    _techn = defaultdict(int)
    for tx_ in tech_rows: _techn[tx_["startup_id"]] += 1
    _SR = {x.get("source_id",""): str(x.get("retrieved_date",""))[:10] for x in src_rows}
    _cf_by = defaultdict(list)
    for cr_ in conflicts_rows: _cf_by[cr_["startup_id"]].append(cr_)
    _tk_by = defaultdict(list)
    for ft_ in final_tasks: _tk_by[ft_["startup_id"]].append(ft_)
    _srcmax = defaultdict(str)
    _fy_want = lambda sid_: next((f"FY{y:02d}" for y in (26, 25, 24, 23) if y not in _fin_fy.get(sid_,())), "")
    def _nba(sid_, sr_):
        """§27: most valuable SPECIFIC next action, in decision order."""
        coh_ = sr_.get("cohort","")
        if not coh_: return ""
        for cf_ in _cf_by.get(sid_, []):
            if cf_.get("resolution_status") != "resolved" and re.search(r"found|ceo|leadership|name", str(cf_.get("field","")), re.I):
                return f"resolve {cf_['field']} conflict: '{str(cf_.get('claim_a',''))[:36]}' vs '{str(cf_.get('claim_b',''))[:36]}' (primary source, then prefer)"
        for tk_ in _tk_by.get(sid_, []):
            if tk_.get("status") not in ("not_started","blocked","logged-no-result"): continue
            ar_ = tk_["research_area"]
            if ar_=="identity": return "establish legal entity + CIN + incorporation date + status via MCA"
            if ar_=="founders": return "verify founder identities/roles via MCA directors + primary press (2 independent sources)"
            if ar_=="funding": return "reconstruct funding history (dates, amounts, instruments, valuations, leads)"
            if ar_=="financials":
                w_=_fy_want(sid_); return f"obtain {w_} statutory financials (revenue/PAT) from MCA filing" if w_ else "complete FY financial table (add missing metric rows: EBITDA/PAT/cash)"
            if ar_=="traction": return "add dated operating metrics (users/GMV/ARR/units with measurement period + source)"
            if ar_=="people": return "map current leadership (CEO/CFO/CTO + join dates) and 2024-26 changes"
            if ar_=="products": return "document product portfolio w/ launch/discontinuation status (company source first)"
            if ar_=="customers": return "identify evidence-backed named customers/partners (no logo inference)"
            if ar_=="legal": return "research regulatory history (RBI/SEBI/CCI/courts): notices, rulings, settlements — statused precisely"
            if ar_=="locations": return "verify current HQ (address/neighborhood) + major offices vs registered office"
            if ar_=="events": return "build 2023-26 event timeline (raises, launches, exits, IPO steps) with dates"
            if ar_=="investors": return "complete investor register per round (lead vs participating) w/ round links"
        if _techn.get(sid_,0)==0 and "ai" not in ("",): 
            if sr_.get("cohort")=="EXHAUST": return "investigate technology footprint (§12: stack, AI, patents, engineering hubs)"
        if _tonum(sr_.get("source_quality_pct",100)) < 50: return "upgrade 3-5 load-bearing claims to primary sources (§17 ladder)"
        if _tonum(sr_.get("freshness_pct",100)) <= 40: return "re-verify volatile fields (leadership, headcount, valuation) — evidence >18mo old"
        for cf_ in _cf_by.get(sid_, []):
            if cf_.get("resolution_status") != "resolved":
                return f"resolve open conflict: {cf_['field']} ('{str(cf_.get('claim_a',''))[:30]}' vs '{str(cf_.get('claim_b',''))[:30]}')"
        if float(sr_.get("completeness_pct",0)) < 85 and sr_.get("cohort")=="EXHAUST": return "close remaining zero-coverage areas toward 85% EXHAUST floor"
        return "maintain: quarterly monitor; no material gap identified"
    control_rows = []
    for sr_ in score_rows:
        sid_ = sr_["startup_id"]; st_ = st_by.get(sid_, {})
        tks = _tk_by.get(sid_, [])
        opens = [t_ for t_ in tks if t_["status"] in ("not_started","logged-no-result","blocked")]
        row_ = {"startup_id": sid_, "company": sr_["company_name"], "city": st_.get("city",""),
                "company_class": st_.get("company_class",""), "cohort": sr_.get("cohort",""),
                "priority_rank": sr_.get("priority_rank",""), "completeness_pct": sr_.get("completeness_pct",""),
                "source_quality_pct": sr_.get("source_quality_pct",""), "freshness_pct": sr_.get("freshness_pct",""),
                "conflict_level": sr_.get("conflict_level",""), "open_tasks": len(opens),
                "open_P1": sum(1 for t_ in opens if t_["priority"]=="P1"),
                "verification_tasks": sum(1 for t_ in tks if t_["status"]=="needs-verification"),
                "unresolved_conflicts": sum(1 for c_ in _cf_by.get(sid_,[]) if c_.get("resolution_status")!="resolved")}
        for ar_ in AREAS:
            row_[ar_+"_missing"] = "1" if float(sr_.get("score_"+ar_,0) or 0)==0 else ""
        row_["technology_missing"] = "1" if _techn.get(sid_,0)==0 else ""
        _lg_ = [lg_["date"] for lg_ in log_rows if lg_["startup_id"]==sid_]
        row_["last_researched"] = max(_lg_) if _lg_ else ""
        _rv_ = [c_.get("last_reviewed","") for c_ in _cf_by.get(sid_,[]) if c_.get("last_reviewed")]
        _hv_ = [(_SR[q.get("source_id","")]) for q in claims_rows if q.get("startup_id")==sid_ and str(q.get("confidence","")).upper()=="HIGH" and _SR.get(q.get("source_id",""))]
        row_["last_verified"] = max([x for x in (_rv_ + _hv_) if x]) if (_rv_ or _hv_) else (max(_lg_) if _lg_ else "")
        row_["next_best_action"] = _nba(sid_, sr_)
        control_rows.append(row_)
    dump("RESEARCH_CONTROL", control_rows)
    # ---- §8 DERIVED metrics: explicitly marked, periods shown, currency-homogeneous only ----
    derived_rows = []; di_ = 0
    def _dput(sid_, met, val, unit, pf, pt, inputs, formula, note=""):
        nonlocal di_
        di_ += 1
        derived_rows.append({"derived_id": f"D{di_:04d}","startup_id": sid_,"metric": met,"value": round(float(val),2),
            "unit": unit,"period_from": pf,"period_to": pt,"inputs": inputs[:200],"formula": formula,
            "value_type": "DERIVED","notes": note})
    for sid_, yrs in _rev.items():
        ys = sorted(yrs)
        if len(ys) >= 2 and yrs[ys[0]] > 0 and yrs[ys[-1]] > 0 and ys[-1]-ys[0] >= 1:
            n_ = ys[-1]-ys[0]; v1, v2 = yrs[ys[0]], yrs[ys[-1]]
            _dput(sid_, "revenue_cagr", ((v2/v1)**(1/n_)-1)*100, "%/yr", f"FY{ys[0]:02d}", f"FY{ys[-1]:02d}",
                  f"FY{ys[0]:02d} ₹{v1:,.1f} Cr → FY{ys[-1]:02d} ₹{v2:,.1f} Cr", f"((v2/v1)^(1/{n_}))-1 ×100",
                  "INR crore standalone-series; intermediate FYs may exist unlisted")
        yl = ys[-1]; pats_ = _pat.get(sid_, {})
        if yl in pats_ and yrs[yl] and pats_[yl] < 0:
            _dput(sid_, "loss_to_revenue", abs(pats_[yl])/yrs[yl]*100, "%", f"FY{yl:02d}", f"FY{yl:02d}",
                  f"FY{yl:02d} PAT ₹{pats_[yl]:,.1f} Cr / revenue ₹{yrs[yl]:,.1f} Cr", "|PAT|/revenue ×100")
        if sid_ in _emp and yrs.get(ys[-1]):
            e_ = _tonum(_emp[sid_].get("value"))
            if e_ >= 5:
                _dput(sid_, "revenue_per_employee", yrs[ys[-1]]*1e7/e_, "INR/yr", f"FY{ys[-1]:02d}", f"FY{ys[-1]:02d}",
                      f"FY{ys[-1]:02d} rev ₹{yrs[ys[-1]]:,.1f} Cr / {_emp[sid_].get('metric','employees')}={e_:,.0f} (as_of {_emp[sid_].get('as_of','') or _emp[sid_].get('period','') or '?'})",
                      "rev×1e7/headcount", "PERIODS MAY NOT ALIGN (headcount is point-in-time) — indicative only")
        if sid_ in _fund_cr and _fund_cr[sid_] > 0 and yrs.get(ys[-1]) and sid_ not in _fund_fx_bad:
            _dput(sid_, "funding_to_revenue", _fund_cr[sid_]/yrs[ys[-1]], "x", f"FY{ys[-1]:02d}", f"FY{ys[-1]:02d}",
                  f"cumulative disclosed equity ₹{_fund_cr[sid_]:,.0f} Cr / FY{ys[-1]:02d} revenue ₹{yrs[ys[-1]]:,.1f} Cr", "cumFunding/revenue",
                  "INR rounds only (USD/mixed excluded to avoid fx assumptions)")
        if sid_ in _val_cr and yrs.get(ys[-1]):
            _dput(sid_, "valuation_to_revenue", _val_cr[sid_]/yrs[ys[-1]], "x", f"FY{ys[-1]:02d}", f"FY{ys[-1]:02d}",
                  f"latest disclosed valuation ₹{_val_cr[sid_]:,.0f} Cr ({_val_fy.get(sid_,'')[:10]}) / FY{ys[-1]:02d} rev ₹{yrs[ys[-1]]:,.1f} Cr", "valuation/revenue",
                  "valuation date vs FY period shown in inputs — check alignment")
    dump("DERIVED_METRICS", derived_rows)

    dump("RESEARCH_TASKS", final_tasks); dump("CLAIMS", claims_rows); dump("TECHNOLOGY", tech_rows); dump("CONFLICTS", conflicts_rows);
    dump("STARTUPS", startups_rows); dump("FOUNDERS", founders_rows); dump("PEOPLE", people_rows); dump("FUNDING", funding_rows)
    dump("INVESTORS", inv_rows); dump("INVESTOR_LINKS", inv_link_rows); dump("FINANCIALS", fin_rows)
    dump("PRODUCTS", prod_rows); dump("CUSTOMERS", cust_rows); dump("PARTNERSHIPS", part_rows)
    dump("COMPETITORS", comp_rows); dump("ACQUISITIONS", acq_rows); dump("LOCATIONS", loc_rows)
    dump("HIRING", hire_rows); dump("LEGAL_REGULATORY", legal_rows); dump("NEWS_EVENTS", event_rows)
    # annotate SOURCES with link-liveness audit (qc/url_audit.csv)
    import csv as _csv
    _ua_path = f"{BASE}/qc/url_audit.csv"
    if os.path.exists(_ua_path):
        _ua = {r["url"]: r["outcome"] for r in _csv.DictReader(open(_ua_path))}
        _dead = 0
        for r_ in src_rows:
            o = _ua.get(r_["url"])
            if o:
                tag = {"OK":"linkcheck 2026-09-14: LIVE"}.get(o) or ("linkcheck 2026-09-14: DEAD("+o+")" if o.startswith("DEAD") else "linkcheck 2026-09-14: "+o)
                r_["notes"] = (r_["notes"]+"; " if r_["notes"] else "") + tag
                if o.startswith("DEAD"):
                    r_["confidence"] = "LOW"; _dead += 1
        _ap = f"{BASE}/qc/dead_url_archives.json"
        if os.path.exists(_ap):
            _raw=json.load(open(_ap))
            _amap={}
            if isinstance(_raw,dict): _amap={k:(v.get("archive") if isinstance(v,dict) else str(v)) for k,v in _raw.items()}
            else:
                for x_ in _raw:
                    if isinstance(x_,dict) and x_.get("url"): _amap[x_["url"]]=x_.get("archive","")
            for uu,av in _amap.items():
                if not av: continue
                for r_ in src_rows:
                    if r_["url"] == uu and "ARCHIVE" not in (r_["notes"] or ""):
                        r_["notes"] = (str(r_["notes"]) + "; " if r_["notes"] else "") + "ARCHIVED COPY: " + av
        print(f"linkcheck annotated; DEAD downgraded: {_dead}")
    dump("TRACTION", trk_rows); dump("SOURCES", src_rows); dump("RESEARCH_LOG", log_rows); dump("SCORES", score_rows)

    rep = ["# Build report", "",
      f"- STARTUPS {len(startups_rows)} (enriched {len(enr)}, shallow {len(startups_rows)-len(enr)})",
      f"- FUNDING {len(funding_rows)} rounds; skipped duplicate round keys: {len(dup_rounds)} {dup_rounds[:5]}",
      f"- FOUNDERS {len(founders_rows)} | PEOPLE {len(people_rows)} | INVESTORS {len(inv_rows)} | INVESTOR_LINKS {len(inv_link_rows)}",
      f"- FINANCIALS {len(fin_rows)} | PRODUCTS {len(prod_rows)} | CUSTOMERS {len(cust_rows)} | PARTNERSHIPS {len(part_rows)} | COMPETITORS {len(comp_rows)}",
      f"- ACQUISITIONS {len(acq_rows)} | LOCATIONS {len(loc_rows)} | HIRING {len(hire_rows)} | LEGAL {len(legal_rows)} | EVENTS {len(event_rows)} | TRACTION {len(trk_rows)}",
      f"- SOURCES {len(src_rows)} unique URLs | invalid/missing URLs quarantined: {len(R.missing)}",
      f"- RESEARCH_LOG {len(log_rows)} | FX: {FX_NOTE}", "", "## Quarantined (no usable URL)",]
    rep += [f"- {s} :: {str(u)[:60]} :: {str(c)[:80]}" for s, u, c, t in R.missing[:80]]
    with open(f"{BASE}/structured/quarantined.csv", "w", newline="") as fh:
        w_ = csv.writer(fh); w_.writerow(["startup_id", "raw_url_field", "claim_or_fields", "title"])
        for s_, u_, c_, t_ in R.missing: w_.writerow([s_, str(u_)[:120], str(c_)[:200], str(t_)[:120]])
    open(f"{BASE}/structured/build_report.md", "w").write("\n".join(rep))
    print("\n".join(rep[:12]))

def sources_used(sid, R):
    return sum(1 for s in R.urls.values() if sid in s["startup_ids"])

def log_entry(date, sid, company, query, found, unresolved, nxt, agent, status):
    return {"date": date, "startup_id": sid, "company": company, "query": query, "found": found, "unresolved": unresolved, "next_action": nxt, "agent": agent, "status": status}

def score_company(sid, u, d, R, funding_rows, fin_rows, founders_rows, n_src):
    """Objective banded-coverage scoring. Axes: completeness (12 cats, equal weight),
    source quality, freshness, conflict level. No agent self-assessment blend."""
    CATS = ["identity","founders","funding","investors","financials","products","traction","people","customers","legal","events","locations"]
    def band(x):
        x = max(0.0, min(1.0, x))
        return 0.0 if x < 0.10 else 0.25 if x < 0.35 else 0.50 if x < 0.60 else 0.75 if x < 0.85 else 1.00
    def gv2(dd, *ks):
        for k in ks:
            v = dd.get(k)
            if isinstance(v, dict): v = v.get("v")
            if str(v or "").strip(): return v
        return ""
    raw = {k: 0.0 for k in CATS}
    c = (d or {}).get("company") or {}
    def has(k): return bool(str(gv2(c, k) or "").strip())
    _off = gv2(c, "official_website") or (gv2(c, "website") if not re.search(r"wikipedia|techcrunch|inc42|entrackr|businessinsider|yourstory", str(gv2(c, "website"))) else "")
    _ids = [has("legal_name"), has("cin"), has("incorporation_date") or has("founded_date"), bool(str(_off).strip()),
            has("city"), has("state"), has("primary_sector"), has("business_model"),
            len(str(c.get("description") or "")) > 80, has("startup_stage") and has("public_private")]
    raw["identity"] = sum(1 for x in _ids if x)/10
    if not d:
        B = {k: 0.0 for k in CATS}
        B["identity"] = band(sum([bool(u.get("city")), bool(u.get("sector_guess")), bool(u.get("discovery_urls")), 1])/4 * 0.4)
        comp = round(100*sum(B.values())/len(CATS), 1)
    else:
        fd = [f for f in (d.get("founders") or []) if isinstance(f, dict)]
        fr = [r for r in (d.get("funding_rounds") or []) if isinstance(r, dict)]
        il = [x for x in (d.get("investor_links") or []) if isinstance(x, dict)]
        fx = [x for x in (d.get("financials") or []) if isinstance(x, dict)]
        pr = [x for x in (d.get("products") or []) if isinstance(x, dict)]
        tr = [x for x in (d.get("traction") or []) if isinstance(x, dict)]
        pp = [x for x in (d.get("people") or []) if isinstance(x, dict)]
        cu = [x for x in (d.get("customers") or []) if isinstance(x, dict)]
        lg = [x for x in (d.get("legal") or []) if isinstance(x, dict)]
        ev = [x for x in (d.get("events") or []) if isinstance(x, dict)]
        lo = [x for x in (d.get("locations") or []) if isinstance(x, dict)]
        raw["founders"] = (min(1,len(fd)/2)*0.4 + (0.25 if fd and all(gv2(f,"role","role_title","title") for f in fd) else 0) + (0.2 if fd and any(gv2(f,"background","education","prev_companies") for f in fd) else 0) + (0.15 if fd and any(gv2(f,"still_active","active") for f in fd) else 0))
        raw["funding"] = ((min(1,len(fr)/4)*0.4 if fr else 0) + (0.2 if fr and all(gv2(r,"round_date","announcement_date") for r in fr) else 0) + (0.2 if any(gv2(r,"valuation") for r in fr) else 0) + (0.2 if any(gv2(r,"lead_investors","leads") for r in fr) else 0))
        raw["investors"] = (min(1,len(il)/4)*0.4 + (0.3 if fr and sum(1 for r in fr if str(gv2(r,"all_investors","investors")).strip()) >= max(1,min(2,len(fr)))/2 else 0) + (0.3 if any(str(gv2(x,"investor_type","type")).strip() for x in il) else 0))
        raw["financials"] = (min(1,len(fx)/3)*0.5 + (0.2 if fx and all(gv2(r,"fiscal_year","year") for r in fx) else 0) + (0.15 if any(gv2(r,"net_profit","profit_loss") for r in fx) else 0) + (0.15 if fx and all(str(r.get("source_url","")).startswith("http") for r in fx) else 0))
        raw["products"] = (min(1,len(pr)/2)*0.5 + (0.3 if any(len(str(r.get("description") or ""))>60 for r in pr) else 0) + (0.2 if any(gv2(r,"pricing_model","pricing") for r in pr) else 0))
        raw["traction"] = min(1,len(tr)/4)*0.6 + (0.4 if tr and any(gv2(r,"date","as_of") for r in tr) else 0)
        raw["people"] = min(1,len(pp)/2)*0.6 + (0.4 if pp and any(gv2(r,"role","title") for r in pp) else 0)
        raw["customers"] = min(1,len(cu)/3)*0.7 + (0.3 if any(len(str(gv2(r,"name") or ""))>2 for r in cu) else 0)
        raw["legal"] = min(1,len(lg)/2)*0.5 + (0.3 if lg and any(gv2(r,"date") for r in lg) else 0) + (0.2 if has("cin") else 0)
        raw["events"] = min(1,len(ev)/3)*0.6 + (0.4 if ev and all(gv2(r,"date") for r in ev[:3]) else 0)
        raw["locations"] = (0.5 if has("city") else 0) + (0.25 if len(lo)>=2 else 0) + (0.25 if has("registered_office") else 0)
        B = {k: band(raw[k]) for k in CATS}
        comp = round(100*sum(B.values())/len(CATS), 1)
    # ---- axes ----
    tms = []
    srcs = (d or {}).get("sources") or u.get("discovery_urls") or []
    for s_ in srcs:
        su = s_.get("url") if isinstance(s_, dict) else s_
        t_ = (s_.get("tier") if isinstance(s_, dict) else "") or tier_from_url(su or "")
        tms.append(t_)
    pts = sum({"T1":5,"T2":3,"T3":1.5,"T4":1,"T5":0.5}.get(t, 1) for t in tms)
    sq = round(min(100.0, pts/15*100), 1)
    _ds = []
    for e in (d or {}).get("research_log") or []:
        if isinstance(e, dict): _ds.append(str(e.get("date") or "")[:10])
    for r in (d or {}).get("funding_rounds") or []:
        if isinstance(r, dict): _ds.append(str(r.get("round_date") or r.get("announcement_date") or "")[:10])
    for s_ in srcs:
        if isinstance(s_, dict): _ds.append(str(s_.get("asof") or s_.get("date") or s_.get("retrieved_date") or "")[:10])
    best = None
    for x in _ds:
        m2 = re.match(r"(\d{4})-(\d{2})", x)
        if m2:
            v = int(m2.group(1)) + int(m2.group(2))/12
            best = v if best is None or v > best else best
    _age = (2026.70 - best) if best else 99
    fresh = 100 if _age <= 0.5 else 80 if _age <= 1 else 60 if _age <= 1.5 else 40 if _age <= 2 else 20 if _age < 90 else 0
    ncf = len((d or {}).get("conflicts") or [])
    conflict = "none" if ncf == 0 else "low" if ncf == 1 else "moderate" if ncf <= 3 else "high"
    tier = ("Candidate" if comp < 20 else "Basic" if comp < 40 else "Enriched" if comp < 60 else "Deep" if comp < 75 else "Intelligence-grade" if comp < 90 else "Fully researched")
    srow = {"startup_id": sid, "company_name": u["company_name"] if isinstance(u, dict) else ""}
    for k in CATS: srow["score_" + k] = round(B[k] * 10, 1)
    srow["completeness_pct"] = comp; srow["tier"] = tier
    srow["source_quality_pct"] = sq; srow["freshness_pct"] = fresh; srow["conflict_level"] = conflict
    srow["score_sources"] = sq
    return srow

SHEETS = {"STARTUPS": {}}
COLS = {
 "STARTUPS": ["startup_id","company_name","legal_name","aliases","website","founded_date","incorporation_date","status","startup_stage",
  "primary_sector","secondary_sectors","business_model","customer_type","city","state","country","hq_type","registered_office",
  "employee_estimate","employee_estimate_date","total_funding_disclosed","last_funding_date","last_funding_round","last_known_valuation",
  "revenue_latest_fy","revenue_latest_fy_year","revenue_latest_fy_period","profit_loss_latest_fy","profit_loss_latest_fy_period","dpiit_recognized","cin","parent_company","subsidiary_of",
  "public_private","website_status","official_website","careers_website","last_verified","confidence","primary_source_id","notes","company_class"],
 "FOUNDERS": ["founder_id","startup_id","person_id","name","role_title","founder_type","active","departure_date","education","prev_companies","linkedin","location","source_id","confidence"],
 "PEOPLE": ["person_id","startup_id","name","position","start_date","end_date","prev","linkedin","source_id","confidence"],
 "FUNDING": ["round_id","startup_id","city","round_date","announcement_date","year","fiscal_year","round_type","amount","currency","amount_inr_mn","valuation","valuation_currency","valuation_type","lead_investor_id","investor_ids","investor_count","new_or_existing","purpose","source_id","confidence","notes"],
 "INVESTORS": ["investor_id","name","type","geography","fund_vintage","notable_portfolio","india_presence","partner_if_public","notes"],
 "INVESTOR_LINKS": ["link_id","startup_id","investor_id","investor_name","investor_type","round_type","round_date","first_seen","rounds","lead","disclosed_amount","amount","board_seat","status","source_id","confidence"],
 "FINANCIALS": ["fy_record_id","startup_id","fiscal_year","period","metric","value","unit","currency","value_type","basis","consolidated","filing_date","source_id","confidence","notes"],
 "TRACTION": ["metric_id","startup_id","metric","value","unit","period","as_of","company_reported","source_id","confidence","notes"],
 "PRODUCTS": ["product_id","startup_id","name","category","description","b2b_b2c","pricing_model","launch_date","status","source_id","confidence","notes"],
 "CUSTOMERS": ["customer_id","startup_id","name","type","geography","announced_date","status","source_id","confidence","notes"],
 "PARTNERSHIPS": ["partnership_id","startup_id","partner","type","announced_date","purpose","duration","status","source_id","confidence","notes"],
 "COMPETITORS": ["competitor_id","startup_id","competitor","category","basis","geography","source_id","confidence","notes"],
 "ACQUISITIONS": ["txn_id","startup_id","direction","type","target_or_buyer","counterparty","date","value","disclosed","rationale","source_id","confidence","notes"],
 "LOCATIONS": ["location_id","startup_id","type","address_or_area","city","state","neighborhood","as_of","source_id","confidence","notes"],
 "HIRING": ["hiring_id","startup_id","fact_type","value","as_of","source_id","confidence","notes"],
 "LEGAL_REGULATORY": ["case_id","startup_id","type","regulator","jurisdiction","summary","dates","status","source_id","confidence","notes"],
 "NEWS_EVENTS": ["event_id","startup_id","event_date","announced_date","type","headline","description","source_id","confidence"],
 "SOURCES": ["source_id","startup_ids","url","title","publisher","publication_date","retrieved_date","source_tier","source_type","claim","supports_fields","reliability","confidence","notes"],
 "RESEARCH_LOG": ["date","startup_id","company","query","found","unresolved","next_action","agent","status","reps"],
 "CLAIMS": ["claim_id","startup_id","entity","field","claim_value","value_type","unit","currency","date_from","date_to","source_id","confidence","status","preferred","notes"],
 "TECHNOLOGY": ["tech_id","startup_id","entity","category","name","description","url","as_of","source_id","confidence","notes"],
 "CONFLICTS": ["conflict_id","startup_id","field","claim_a","source_a","claim_b","source_b","preferred_claim","resolution","resolution_status","last_reviewed"],
 "RESEARCH_TASKS": ["task_id","startup_id","company","research_area","priority","assigned","started","completed","result","next_action","status","log_events"],
 "RESEARCH_CONTROL": ["startup_id","company","city","company_class","cohort","priority_rank","completeness_pct","source_quality_pct","freshness_pct","conflict_level","open_tasks","open_P1","verification_tasks","unresolved_conflicts","identity_missing","founders_missing","funding_missing","investors_missing","financials_missing","products_missing","traction_missing","people_missing","customers_missing","legal_missing","locations_missing","events_missing","technology_missing","next_best_action","last_researched","last_verified"],
 "DERIVED_METRICS": ["derived_id","startup_id","metric","value","unit","period_from","period_to","inputs","formula","value_type","notes"],
 "SCORES": ["startup_id","company_name","score_identity","score_founders","score_funding","score_investors","score_financials","score_products","score_traction","score_people","score_customers","score_legal","score_events","completeness_pct","tier","source_quality_pct","freshness_pct","conflict_level","score_locations","priority_score","priority_rank","cohort"],
}

if __name__ == "__main__":
    main()
