#!/usr/bin/env python3
"""validate_db.py — audit sheet CSVs before/after Excel build (AS stopping rules).
Checks: dup IDs, FK integrity, URL validity, date sanity, confidence enums,
duplicate funding rounds, empty required, city classification sanity, score bounds.
Writes india-startup-db/qc/validation.md ; exit 1 on FAIL-level findings."""
import csv, re, sys, os
from collections import Counter, defaultdict
BASE = os.path.dirname(os.path.abspath(__file__))
CSV_DIR = sys.argv[1] if len(sys.argv) > 1 else f"{BASE}/build/csv"
CONF = {"HIGH","MEDIUM","LOW","ESTIMATE","UNVERIFIED","", "high","medium","low","estimate","unverified"}
issues, warns = [], []
def rd(name):
    p = f"{CSV_DIR}/{name}.csv"
    if not os.path.exists(p): issues.append(f"MISSING SHEET CSV: {name}"); return []
    return list(csv.DictReader(open(p)))
S   = rd("STARTUPS"); F = rd("FUNDING"); SR = rd("SOURCES"); FD = rd("FOUNDERS")
P   = rd("PEOPLE"); IL = rd("INVESTOR_LINKS"); IV = rd("INVESTORS"); FIN = rd("FINANCIALS")
RC = rd("RESEARCH_CONTROL"); DM = rd("DERIVED_METRICS")
SC  = rd("SCORES"); CL = rd("CLAIMS"); CN = rd("CONFLICTS"); RT = rd("RESEARCH_TASKS"); PR = rd("PRODUCTS"); CU = rd("CUSTOMERS"); PA = rd("PARTNERSHIPS")
CO = rd("COMPETITORS"); AC = rd("ACQUISITIONS"); LO = rd("LOCATIONS"); HI = rd("HIRING")
LE = rd("LEGAL_REGULATORY"); NE = rd("NEWS_EVENTS"); RL = rd("RESEARCH_LOG"); TR = rd("TRACTION")
sids = [r["startup_id"] for r in S]
dup = [k for k, v in Counter(sids).items() if v > 1]
if dup: issues.append(f"duplicate startup_ids: {dup}")
sid_set = set(sids)
src_ids = {r["source_id"] for r in SR}
for nm, rows, fkcols in [("FUNDING",F,{"startup_id":"S","source_id":"SR"}),("FOUNDERS",FD,{"startup_id":"S","source_id":"SR"}),
    ("PEOPLE",P,{"startup_id":"S","source_id":"SR"}),("INVESTOR_LINKS",IL,{"startup_id":"S","investor_id":"IV","source_id":"SR"}),
    ("FINANCIALS",FIN,{"startup_id":"S","source_id":"SR"}),("PRODUCTS",PR,{"startup_id":"S","source_id":"SR"}),
    ("CUSTOMERS",CU,{"startup_id":"S","source_id":"SR"}),("PARTNERSHIPS",PA,{"startup_id":"S","source_id":"SR"}),
    ("COMPETITORS",CO,{"startup_id":"S","source_id":"SR"}),("ACQUISITIONS",AC,{"startup_id":"S","source_id":"SR"}),
    ("LOCATIONS",LO,{"startup_id":"S","source_id":"SR"}),("HIRING",HI,{"startup_id":"S","source_id":"SR"}),
    ("LEGAL_REGULATORY",LE,{"startup_id":"S","source_id":"SR"}),("NEWS_EVENTS",NE,{"startup_id":"S","source_id":"SR"}),
    ("TRACTION",TR,{"startup_id":"S","source_id":"SR"}),("SCORES",SC,{"startup_id":"S"}),("RESEARCH_LOG",RL,{"startup_id":"S"}),
    ("CLAIMS",CL,{"startup_id":"S","source_id":"SR"}),("RESEARCH_TASKS",RT,{"startup_id":"S"}),("CONFLICTS",CN,{"startup_id":"S"}),
    ("RESEARCH_CONTROL",RC,{"startup_id":"S"}),("DERIVED_METRICS",DM,{"startup_id":"S"})]:
    pools = {"S": sid_set, "SR": src_ids, "IV": {r["investor_id"] for r in IV}}
    for col, pool in fkcols.items():
        if col not in (rows[0] if rows else {}): continue

        bad = [r.get(col,"") for r in rows if r.get(col,"") and r[col] not in pools[pool] and not (col=="startup_id" and r[col]=="ALL") and ";" not in r[col]]
        if bad: issues.append(f"FK orphan {nm}.{col}: {bad[:5]} ({len(bad)})")

# Phase 4 checks (one-row-per-company, cohort enum, derived purity)
import collections as _C, re as _re
_d = {k for k,c in _C.Counter(r["startup_id"] for r in RC).items() if c>1}
if _d: issues.append(f"RESEARCH_CONTROL dup rows: {list(_d)[:5]}")
_badc = [r["cohort"] for r in RC if r.get("cohort") not in ("","EXHAUST","TARGET")]
if _badc: issues.append(f"RESEARCH_CONTROL bad cohort: {_badc[:3]}")
_nnb = [r["derived_id"] for r in DM if r.get("value_type") != "DERIVED" or not str(r.get("value","")).strip()]
if _nnb: issues.append(f"DERIVED_METRICS bad rows: {len(_nnb)}")
_nnum = [r["derived_id"] for r in DM if str(r.get("value","")).strip() and not _re.fullmatch(r"-?\d+(\.\d+)?", str(r["value"]).strip())]
if _nnum: issues.append(f"DERIVED_METRICS non-numeric: {_nnum[:3]}")

# URLs
bad_urls = [r["url"] for r in SR if not re.match(r"^https?://[^\s]+\.[^\s]{2,}", r["url"] or "")]
if bad_urls: issues.append(f"malformed source urls ({len(bad_urls)}): {bad_urls[:5]}")
empty_src = [r for r in SR if not (r.get("title") or "").strip()]
if empty_src: warns.append(f"{len(empty_src)} sources lack titles")
# dup round ids; dup round content
for k, v in Counter(r["round_id"] for r in F).items():
    if v > 1: issues.append(f"duplicate round_id {k}")
seen = defaultdict(list)
for r in F:
    key = (r["startup_id"], r["round_type"].lower(), r["amount"], (r["announcement_date"] or "")[:7])
    seen[key].append(r["round_id"])
for k, v in seen.items():
    if len(v) > 1 and k[2]: warns.append(f"possible duplicate round {k}: {v}")
# confidence enums
for nm, rows in [("STARTUPS",S),("FUNDING",F),("FINANCIALS",FIN),("NEWS_EVENTS",NE)]:
    for r in rows:
        c = r.get("confidence","")
        if c and c.upper() not in CONF: warns.append(f"{nm} bad confidence '{c}' ({r.get('startup_id','?')})")
# dates
for nm, rows, cols in [("STARTUPS",S,["founded_date","incorporation_date","last_funding_date","employee_estimate_date","last_verified"]),
                       ("FUNDING",F,["round_date","announcement_date"])]:
    for r in rows:
        for col in cols:
            v = (r.get(col) or "").strip()
            if v and not re.match(r"^(19|20)\d\d(-\d\d?(-\d\d?)?)?$|^(19|20)\d\d[-/]", v) and not re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", v, re.I):
                warns.append(f"{nm} odd date '{v}' in {col} ({r.get('startup_id','?')})")
# city classification
BADCITY = re.compile(r"\b(dubai|singapore|london|san francisco|new york|us|usa|uk)\b", re.I)
for r in S:
    _badc=BADCITY.search(r.get("city","") or "")
    _ok=_badc and ("entity-match risk" in str(r.get("notes","")).lower() or not str(r.get("country","")).strip().startswith("India"))
    if _badc and not _ok: warns.append(f"non-India city value {r['startup_id']}: {r['city']}")
# required fields
for r in S:
    if not (r.get("company_name") or "").strip(): issues.append(f"empty company_name {r['startup_id']}")
    if not (r.get("city") or "").strip(): warns.append(f"missing city {r['startup_id']}")
# scores bounds
for r in SC:
    try:
        v = float(r.get("completeness_pct","0"))
        if not (0 <= v <= 100): issues.append(f"score out of range {r['startup_id']}: {v}")
    except ValueError: issues.append(f"non-numeric score {r['startup_id']}: {r.get('completeness_pct')}")
# funding amount sanity
for r in F:
    try:
        a = float(r.get("amount") or 0); cy = (r.get("currency") or "USD").upper()
        cap = 500000 if cy == "INR" else 50000
        if a < 0 or a > cap: issues.append(f"implausible funding amount {r['round_id']} {r['startup_id']}: {r.get('amount')} {cy}")
    except ValueError:
        if r.get("amount"): warns.append(f"non-numeric amount {r['round_id']}: {r.get('amount')}")
# Phase 3: CLAIMS / CONFLICTS integrity
for nm, rows, idcol in [("CLAIMS",CL,"claim_id"),("CONFLICTS",CN,"conflict_id"),("RESEARCH_TASKS",RT,"task_id")]:
    d_ = [k for k,v in Counter(r[idcol] for r in rows).items() if v>1]
    if d_: issues.append(f"duplicate {nm}.{idcol}: {d_[:5]}")
if CL:
    _bad_status = {r.get("status","") for r in CL} - {"current","candidate","superseded",""}
    if _bad_status: warns.append(f"CLAIMS unusual status values: {list(_bad_status)[:5]}")
if CN:
    _rs = {r.get("resolution_status","") for r in CN} - {"resolved","preserved-conflict","unresolved",""}
    if _rs: warns.append(f"CONFLICTS unusual resolution_status: {list(_rs)[:5]}")
    unresolved = sum(1 for r in CN if r.get("resolution_status")=="unresolved")
    warns.append(f"CONFLICTS: {len(CN)} total, {unresolved} unresolved (preserved, not dropped)")
if RT:
    _ts = {r.get("status","") for r in RT} - {"not_started","in_progress","completed","logged-no-result","blocked","needs-verification",""}
    if _ts: warns.append(f"RESEARCH_TASKS unusual status: {list(_ts)[:5]}")
    for r in RT:
        if r.get("status")=="completed" and not (r.get("result") or "").strip():
            warns.append(f"completed task without result: {r.get('task_id')} {r.get('startup_id')}"); break
# numeric purity (Phase 3 #8): FINANCIALS.value & STARTUPS latest-fy must be plain numbers if present
def _num_ok(x):
    x=str(x).strip()
    if not x: return True
    try: float(x); return True
    except ValueError: return False
for r in FIN:
    if r.get("value") and not _num_ok(r["value"]): issues.append(f"FINANCIALS.value non-numeric {r.get('fy_record_id')}: {r['value'][:24]}")
for r in S:
    for col in ("revenue_latest_fy","profit_loss_latest_fy"):
        if r.get(col) and not _num_ok(r[col]): issues.append(f"STARTUPS.{col} non-numeric {r['startup_id']}: {r[col][:24]}")
# coverage stats
city_c = Counter(r["city"] for r in S if r.get("city"))
enriched = sum(1 for r in S if "Shallow" not in (r.get("notes") or ""))
rep = [f"# Validation report — {os.environ.get('STAGE','pre-excel')}", "",
 f"STARTUPS {len(S)} (enriched {enriched} / shallow {len(S)-enriched}) | FUNDING {len(F)} | SOURCES {len(SR)} | FOUNDERS {len(FD)} | PEOPLE {len(P)} | INVESTORS {len(IV)} | ILINKS {len(IL)} | FINANCIALS {len(FIN)} | PRODUCTS {len(PR)} | CUSTOMERS {len(CU)} | PARTNER {len(PA)} | COMPETITORS {len(CO)} | ACQ {len(AC)} | LOC {len(LO)} | HIRING {len(HI)} | LEGAL {len(LE)} | EVENTS {len(NE)} | TRACTION {len(TR)} | LOG {len(RL)} | SCORES {len(SC)}",
 f"Cities: {city_c.most_common(10)}", "", f"## ISSUES ({len(issues)})"] + [f"- {i}" for i in issues[:60]] + ["", f"## WARNINGS ({len(warns)})"] + [f"- {w}" for w in warns[:80]]
open(f"{BASE}/qc/validation.md", "w").write("\n".join(rep))
print("\n".join(rep[:16]))
sys.exit(1 if issues else 0)
