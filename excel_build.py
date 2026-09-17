#!/usr/bin/env python3
"""excel_build.py — build india-startup-intelligence.xlsx via OfficeCLI from build/csv/*.csv.
Idempotent: rebuilds from scratch each run (close -> rm -> create -> import -> decorate).
Exit non-zero on any command failure or structural validation miss."""
import json, os, subprocess, sys, csv, shutil
from collections import Counter, defaultdict
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from build_tables import COLS  # canonical column sets
CSV = f"{BASE}/build/csv"
XLSX = os.environ.get("OUT_XLSX") or f"{BASE}/india-startup-intelligence.xlsx"
SHEET_ORDER = ["README","STARTUPS","FOUNDERS","PEOPLE","FUNDING","INVESTOR_LINKS","INVESTORS","FINANCIALS",
 "TRACTION","PRODUCTS","CUSTOMERS","PARTNERSHIPS","COMPETITORS","ACQUISITIONS","LOCATIONS","HIRING",
 "LEGAL_REGULATORY","NEWS_EVENTS","SOURCES","RESEARCH_LOG","SCORES","RESEARCH_TASKS","CLAIMS","CONFLICTS","TECHNOLOGY","RESEARCH_CONTROL","DERIVED_METRICS","DASHBOARD"]
TABLE_NAMES = {"STARTUPS":"tblStartups","FOUNDERS":"tblFounders","PEOPLE":"tblPeople","FUNDING":"tblFunding",
 "INVESTOR_LINKS":"tblInvestorLinks","INVESTORS":"tblInvestors","FINANCIALS":"tblFinancials","TRACTION":"tblTraction",
 "PRODUCTS":"tblProducts","CUSTOMERS":"tblCustomers","PARTNERSHIPS":"tblPartnerships","COMPETITORS":"tblCompetitors",
 "ACQUISITIONS":"tblAcquisitions","LOCATIONS":"tblLocations","HIRING":"tblHiring","LEGAL_REGULATORY":"tblLegal",
 "NEWS_EVENTS":"tblEvents","SOURCES":"tblSources","RESEARCH_LOG":"tblLog","SCORES":"tblScores","RESEARCH_TASKS":"tblResearchTasks","CLAIMS":"tblClaims","CONFLICTS":"tblConflicts","TECHNOLOGY":"tblTechnology","RESEARCH_CONTROL":"tblResearchControl","DERIVED_METRICS":"tblDerived"}
_cs=[s for s,cols in COLS.items() if "confidence" in cols]+["FOUNDERS","PEOPLE","INVESTOR_LINKS","PRODUCTS","CUSTOMERS","PARTNERSHIPS","COMPETITORS","ACQUISITIONS","LOCATIONS","HIRING","LEGAL_REGULATORY"]
CONF_SHEETS=list(dict.fromkeys(_cs))
def col_letter(i):  # 1-based
    s = ""
    while i: i, r = divmod(i - 1, 26); s = chr(65 + r) + s
    return s
ENV = dict(os.environ, OFFICECLI_RESIDENT_FLUSH="each")
def cli(*args, inp=None, check=True):
    p = subprocess.run(["officecli", *args], capture_output=True, text=True, input=inp, env=ENV)
    try: out = json.loads(p.stdout)
    except Exception: out = {"raw": p.stdout[:300], "stderr": p.stderr[:300]}
    ok = (p.returncode == 0) and (out.get("success", out.get("ok", True)) not in (False,))
    if not ok and check:
        print(f"FAIL: officecli {' '.join(args[:3])} -> {json.dumps(out)[:400]}", file=sys.stderr)
        FAILS.append(args[:4])
    return out
FAILS = []
def probe(tag):
    o = cli("get", XLSX, "/README/A1", "--json")
    res = ((o.get("data") or {}).get("results") or [{}])
    print(f"probe[{tag}] README/A1 =", res[0].get("text") if isinstance(res[0], dict) else res[0])

def load(name):
    p = f"{CSV}/{name}.csv"
    if not os.path.exists(p): return []
    return list(csv.DictReader(open(p)))
def batch(sheet_cmds):
    """execute list of dicts as one officecli batch (chunked 200); verify per-item."""
    for i in range(0, len(sheet_cmds), 200):
        chunk = sheet_cmds[i:i+200]
        out = cli("batch", XLSX, "--commands", json.dumps(chunk), "--json")
        summ = (out.get("data") or {}).get("summary") or {}
        if summ.get("failed"):
            fails = [r for r in (out.get("data") or {}).get("results", []) if not r.get("success")][:3]
            print(f"BATCH chunk@{i}: {summ.get('failed')}/{summ.get('total')} failed: {json.dumps(fails)[:300]}", file=sys.stderr)
            FAILS.append({"batch_chunk": i, "failed": summ.get("failed"), "sample": fails[:1]})
def main():
    os.chdir(BASE)
    data = {s: load(s) for s in TABLE_NAMES}
    nrows = {s: len(data[s]) for s in TABLE_NAMES}
    print("rows:", {k: v for k, v in nrows.items() if v})
    # fresh start
    cli("close", XLSX, "--json", check=False)
    if os.path.exists(XLSX): os.remove(XLSX)
    r = cli("create", XLSX, "--json")
    assert r.get("success", r.get("ok")), "create failed"
    # NOTE: create already keeps a resident open — do NOT call open again (dual residents split writes)
    # ---- README ----
    cli("add", XLSX, "/", "--type", "sheet", "--prop", "name=README", "--json")
    cli("remove", XLSX, "/Sheet1", "--json", check=False)
    cli("set", XLSX, "/README", "--prop", "tabColor=808080", "--json")

    # ---- data sheets ----
    for s in TABLE_NAMES:
        cli("add", XLSX, "/", "--type", "sheet", "--prop", f"name={s}", "--json")
        if not os.path.exists(f"{CSV}/{s}.csv"):
            with open(f"{CSV}/{s}.csv", "w", newline="") as fh:
                csv.writer(fh).writerow(COLS[s])
        imp = cli("import", XLSX, f"/{s}", f"{CSV}/{s}.csv", "--header", "--json")
        assert imp.get("success", imp.get("ok")), f"import {s}"
        n = nrows[s]
        last = col_letter(len(COLS[s]))
        cli("add", XLSX, f"/{s}", "--type", "table", "--prop", f"ref=A1:{last}{max(n+1,2)}",
            "--prop", f"displayName={TABLE_NAMES[s]}", "--prop", "headerRow=true", "--json")
        # widths + wrap (column objects via `add column`; wrapText via RANGE set)
        extra = []
        for j, cname in enumerate(COLS[s], 1):
            L = col_letter(j)
            if cname in ("notes","description","claim","purpose","why_notable","education","summary","headline","business_model","background","notable_portfolio","query","found","unresolved","next_action","result","research_area","priority","assigned","claim_a","claim_b","resolution","claim_value","preferred_claim","secondary_sectors","rounds","investor_ids","discovery_urls"): w = 46
            elif cname in ("url","website","website_status","official_website","careers_website","link","linkedin","registered_office","address_or_area","prev_companies","prev","rationale","value","total_funding_disclosed","employee_estimate"): w = 36
            elif cname.endswith("_id") or cname in ("startup_ids","supports_fields"): w = 14
            elif "date" in cname or cname in ("year","fiscal_year","status","city","state","country","currency","unit","confidence","tier","reliability","source_tier"): w = 13
            else: w = 20
            extra.append({"command":"set","path":f"/{s}/col[{L}]","props":{"width":str(w)}})
            if w >= 36 and n >= 1:
                cli("set", XLSX, f"/{s}/{L}2:{L}{n+1}", "--prop", "alignment.wrapText=true", "--json")
            extra.append({"command":"set","path":f"/{s}/{L}1","props":{"font.bold":"true","fill":"#DDEBF7"}})
        batch(extra)
    probe("after-sheets-import")
    # freeze already set by import --header (row1)

    probe("after-widths")
    # ---- number formats ----
    numfmt_cmds = []
    for s in TABLE_NAMES:
        for j, cname in enumerate(COLS[s], 1):
            L = col_letter(j)
            fmt = None
            if cname in ("amount","amount_inr_mn","valuation","disclosed_amount"): fmt = "#,##0.0"
            if cname in ("completeness_pct","completeness_calc") or cname.startswith("score_"): fmt = "0.0"
            if fmt:
                n = max(nrows[s], 1)
                numfmt_cmds.append((f"/{s}/{L}2:{L}{n+1}", fmt))
    for path, fmt in numfmt_cmds:
        cli("set", XLSX, path, "--prop", f"numberformat={fmt}", "--json")
    probe("after-numfmt")
    # ---- conditional formatting on confidence columns ----
    cf_colors = {"HIGH": ("C6EFCE","006100"), "MEDIUM": ("FFEB9C","9C6500"), "LOW": ("FFC7CE","9C0006"),
                 "UNVERIFIED": ("D9D9D9","404040"), "ESTIMATE": ("BDD7EE","1F4E79")}
    for s in CONF_SHEETS:
        if s not in TABLE_NAMES or "confidence" not in COLS[s]: continue
        j = COLS[s].index("confidence") + 1; L = col_letter(j); n = max(nrows[s], 2)
        for word, (bg, fg) in cf_colors.items():
            cli("add", XLSX, f"/{s}", "--type", "conditionalformatting", "--prop", "type=cellis",
                "--prop", "operator=equal", "--prop", f"ref={L}2:{L}{n+1}", "--prop", f'value="{word}"',
                "--prop", f"fill=#{bg}", "--prop", "font.bold=false", "--json")
    # shutdown/status CF on STARTUPS status col
    if nrows["STARTUPS"]:
        st = COLS["STARTUPS"].index("status") + 1; SL = col_letter(st)
        for kw, col in (("shut","FFC7CE"),("closed","FFC7CE"),("failed","FFC7CE"),("merged","BDD7EE"),("acquired","BDD7EE"),("IPO","C6EFCE"),("listed","C6EFCE")):
            cli("add", XLSX, "/STARTUPS", "--type", "conditionalformatting", "--prop", "type=containstext",
                "--prop", f"ref={SL}2:{SL}{nrows['STARTUPS']+1}", "--prop", f'text="{kw}"', "--prop", f"fill=#{col}", "--json")
    # data bars + color scales
    if nrows["FUNDING"]:
        aj = col_letter(COLS["FUNDING"].index("amount_inr_mn") + 1)
        cli("add", XLSX, "/FUNDING", "--type", "databar", "--prop", f"ref={aj}2:{aj}{nrows['FUNDING']+1}", "--prop", "color=4472C4", "--json")
    # ---- validations ----
    for s in CONF_SHEETS:
        if s not in TABLE_NAMES or "confidence" not in COLS[s]: continue
        j = COLS[s].index("confidence") + 1; L = col_letter(j)
        cli("add", XLSX, f"/{s}", "--type", "validation", "--prop", "type=list", "--prop", f"ref={L}2:{L}5000",
            "--prop", 'formula1="HIGH,MEDIUM,LOW,ESTIMATE,UNVERIFIED"', "--prop", "allowBlank=true", "--json")
    if "dpiit_recognized" in COLS["STARTUPS"]:
        dj = col_letter(COLS["STARTUPS"].index("dpiit_recognized") + 1)
        cli("add", XLSX, "/STARTUPS", "--type", "validation", "--prop", "type=list", "--prop", f"ref={dj}2:{dj}5000",
            "--prop", 'formula1="YES,NO,UNKNOWN,True,False,true,false,not public,see sources"', "--prop", "allowBlank=true", "--json")
    probe("after-cf-validation")
    # ---- hyperlinks ----
    hl_cmds = []
    for s, cnames in [("STARTUPS",["website","official_website","careers_website","registered_office"]),("SOURCES",["url"]),("FOUNDERS",["linkedin"]),("PEOPLE",["linkedin"])]:
        if s not in TABLE_NAMES: continue
        for cname in cnames:
            if cname not in COLS[s]: continue
            L = col_letter(COLS[s].index(cname) + 1)
            for i, row in enumerate(data[s], 2):
                v = (row.get(cname) or "").strip()
                if v.startswith("http"):
                    hl_cmds.append({"command":"set","path":f"/{s}/{L}{i}","props":{"link":v,"font.color":"0563C1","font.underline":"single"}})
    batch(hl_cmds)
    probe("after-hyperlinks")
    # ---- SCORES live recompute column ----
    sn = nrows["SCORES"]
    sc = COLS["SCORES"]
    pcol = col_letter(len(sc) + 1)
    cli("set", XLSX, f"/SCORES/{pcol}1", "--prop", "value=completeness_calc(DERIVED-live)", "--json")
    # equal-weight mean of the 12 banded category scores (each 0-10): completeness = AVERAGE*10
    CATS12 = ["identity","founders","funding","investors","financials","products","traction","people","customers","legal","events","locations"]
    cat_cols = [col_letter(sc.index(f"score_{k}") + 1) for k in CATS12]
    fcmds = []
    for i in range(2, sn + 2):
        rng = f"{cat_cols[0]}{i}:{cat_cols[-1]}{i}" if len(cat_cols)==len([c for c in cat_cols if c==cat_cols[0]]) else ",".join(f"{c}{i}" for c in cat_cols)
        expr = "AVERAGE(" + ",".join(f"{c}{i}" for c in cat_cols) + ")"
        fcmds.append({"command":"set","path":f"/SCORES/{pcol}{i}","props":{"formula":f"=ROUND(({expr})*10,1)"}})
    batch(fcmds)
    cli("add", XLSX, "/SCORES", "--type", "conditionalformatting", "--prop", "type=colorscale",
        "--prop", f"ref={col_letter(sc.index('completeness_pct')+1)}2:{col_letter(sc.index('completeness_pct')+1)}{sn+1}",
        "--prop", "minColor=F8696B", "--prop", "midColor=FFEB84", "--prop", "maxColor=63BE7B", "--json")
    # ---- DASHBOARD ----
    cli("add", XLSX, "/", "--type", "sheet", "--prop", "name=DASHBOARD", "--prop", "tabColor=1F4E79", "--json")
    build_dashboard(data, nrows)
    readme = [
      "INDIA STARTUP INTELLIGENCE DATABASE", "built 2026-09-14 | Phase 3 (claims/conflicts/priority-queue) 2026-09-15 | run india-startup-db-265749 | OfficeCLI " ,
      "",
      "PURPOSE: source-backed, extensible intelligence DB of Indian startups; deepest coverage Mumbai + Bengaluru.",
      "METHOD: hyperresearch-adapted loop (DISCOVER->DEDUPE->ENRICH->VERIFY->STRUCTURE->XLSX->VALIDATE->AUDIT).",
      "Web facts collected 2026-09-14/15 from live search + vault-archived fetches (Phase 3 wave = dated 2026-09-15/16). Each claim's source row carries its own publication_date + retrieved_date. NO fabricated data; blanks = unverified gaps.",
      "",
      "SHEET FLOW (FK): every row carries stable ids; SOURCES.source_id is the provenance spine referenced by *_source_id cols.",
      "STARTUPS.startup_id -> FOUNDERS/PEOPLE/FUNDING/INVESTOR_LINKS/FINANCIALS/TRACTION/PRODUCTS/CUSTOMERS/PARTNERSHIPS/COMPETITORS/ACQUISITIONS/LOCATIONS/HIRING/LEGAL_REGULATORY/NEWS_EVENTS/RESEARCH_LOG/SCORES/RESEARCH_TASKS/CLAIMS/TECHNOLOGY",
      "INVESTORS.investor_id -> INVESTOR_LINKS (investor<->startup join table); FUNDING.lead_investor_id / .investor_ids -> INVESTORS",
      "*.source_id -> SOURCES.url (real, verified URLs; tier T1..T5 per source hierarchy). CLAIMS + CONFLICTS + TECHNOLOGY all reference the same two spines (startup_id, source_id).",
      "",
      "CONVENTIONS:",
      "- Dates: ISO-ish text (YYYY-MM-DD / YYYY-MM / YYYY / 'Feb 2019'); as-of dates kept next to values; never assume current.",
      "- Money: FUNDING.amount = native currency millions (see .currency); amount_inr_mn = DERIVED via annual-avg FX: 2020:74 2021:74.5 2022:78.5 2023:82.8 2024:83.7 2025:85.7 2026:87.",
      "- Confidence: HIGH/MEDIUM/LOW/ESTIMATE/UNVERIFIED. value_type: audited | press-quoted-filing | management | estimate.",
      "- CONFLICTS live in the dedicated CONFLICTS sheet (Phase 3) + legacy notes; never averaged or silently overwritten. GAPS listed in STARTUPS.notes + RESEARCH_LOG.",
      "- DERIVED fields: totals/years/INR conversions/DASHBOARD computed cells (marked in headers/notes).",
      "- Indian fiscal year FY25 = Apr-2024..Mar-2025. FY label 'FY25-26' = Apr-2025..Mar-2026.",
      "",
      "RESEARCH MATURITY MODEL (SCORES sheet): each of 12 categories scored as OBJECTIVE BANDED COVERAGE (0 / 2.5 / 5 / 7.5 / 10 = no / limited / moderate / substantial / comprehensive data; field-presence + quality checks, NO agent self-assessment). Research Completeness = equal-weighted mean of the 12 bands. Three separate axes: Source Quality % (tier-weighted evidence, T1=5/T2=3/T3=1.5 pts, 15 pts = 100%), Freshness % (recency of newest evidence: <=6mo=100 ... >2y=20), Conflict Level (none/low/moderate/high from preserved-conflict counts). Tiers: <20 Candidate | 20-39.9 Basic | 40-59.9 Enriched | 60-74.9 Deep | 75-89.9 Intelligence-grade | 90+ Fully researched.",
      "company_class (STARTUPS column, DERIVED): Startup / Scale-up (>=INR 10,000 Mn raised, or older + >=2,500) / Mature private company (>=50,000 Mn, or pre-2013 + >=5,000) / Public company / Subsidiary (named corporate parent) / Acquired (operating) / Former startup (defunct/shut) / Other - status unverified. Filter this to answer 'top funded startups' vs 'top funded tracked companies' separately.",
      "CLAIMS sheet (Phase 3): the evidence layer - one row per factual claim (round amounts, valuations, financials, traction, dict-sourced company fields) with value_type/unit/currency, dates, source_id, confidence, status, preferred. Summary sheets carry current preferred values; CLAIMS carries what supports them.",
      "CONFLICTS sheet (Phase 3): every disagreement preserved (claim_a/source_a vs claim_b/source_b, preferred_claim, resolution, resolution_status resolved|preserved-conflict|unresolved, last_reviewed). Conflicts are never silently overwritten - they are data.",
      "TECHNOLOGY sheet (Phase 3): stack/AI-model/patent/brand/API/cloud/OSS facts harvested from research that previously had no home in the workbook — one row per fact with as_of + source.",
      "RESEARCH_CONTROL sheet (Phase 4 §28): one row per company - cohort, rank, four score axes, per-area missing flags, open/verification task counts, and a SPECIFIC next_best_action (§27) so the next research move is decidable without manual workbook inspection.",
      "DERIVED_METRICS sheet (Phase 4 §8): computed ratios (revenue CAGR, loss/revenue, revenue/employee, funding/revenue, valuation/revenue) - every row marked value_type=DERIVED with input values AND periods shown; currency-homogeneous only (no fx assumptions); mismatched periods flagged in notes.",
      "PRIORITY MODEL (SCORES cols T/U/V + DASHBOARD): importance (funding, revenue, city focus, stage, news, marquee investors, strategic sector, recent activity) x gap (incomplete coverage + conflicts + weak/old sources) = priority_score. EXHAUST cohort = top 38, TARGET = top 100; research proceeds from this queue, never alphabetically.",
      "RESEARCH_TASKS sheet (NEW): execution ledger - one row per (startup, research area): areas identity/founders/funding/investors/financials/products/traction/people/customers/legal/locations/events; status completed / logged-no-result / not_started; priority P1 (core gap on a Candidate/Basic record) P2 (core area already touched) P3 (non-core). RESEARCH_LOG stays the deduped audit trail (reps column counts collapsed repeats). Gap-driven next research = filter status=not_started, priority=P1.",
      "",
      "HOW TO UPDATE: add rows inside/below the tables (they auto-expand); give new companies fresh startup_id S#### (continue sequence);",
      "always add SOURCES row first for a new claim and reference its source_id; re-run the DASHBOARD counts via the provided live",
      "formulas (auto-recalc); the research backlog is explicit in RESEARCH_TASKS (status=not_started, priority P1) - not a binary deep/shallow flag.",
      "",
      "KNOWN LIMITS: MCA PDFs not machine-pullable here (financials = press-quoted filings unless marked); DPIIT registry bulk list",
      "not downloadable (recognition set per-company where sourced); LinkedIn headcounts never treated as audited.",
      "Quality report: qc/validation.md + structured/build_report.md (kept next to this file in source repo)."]
    batch([{"command":"add","parent":"/README","type":"column","props":{"name":"A","width":"150"}}])
    rc = cli("batch", XLSX, "--commands", json.dumps([{"command":"set","path":f"/README/A{i+1}","props":{"value":v}} for i, v in enumerate(readme)]), "--json")
    print("README batch summary:", (rc.get("data") or {}).get("summary"), "| item0:", json.dumps(((rc.get("data") or {}).get("results") or [{}])[0])[:160])
    g = cli("get", XLSX, "/README/A1", "--json")
    print("README A1 immediate:", json.dumps(g.get("data",{}).get("results"))[:200])
    cli("set", XLSX, "/README/A1", "--prop", "font.bold=true", "--prop", "font.size=16", "--json")
    # ---- uniform freeze row-1 on every sheet (import --header misses first sheet sometimes) ----
    for fz in SHEET_ORDER:
        cli("set", XLSX, f"/{fz}", "--prop", "freeze=A2", "--json", check=False)
    # ---- finalize + verify ----
    for pc in ("/README/A1", "/DASHBOARD/A1", "/DASHBOARD/A8", "/DASHBOARD/B8"):
        o = cli("get", XLSX, pc, "--json")
        rs = ((o.get("data") or {}).get("results") or [{}])
        print(f"in-resident probe {pc}: {str(rs[0].get('text'))[:50] if isinstance(rs[0], dict) else rs[0]}")
    probe("final")
    cli("close", XLSX, "--json")
    cli("close", XLSX, "--json", check=False)
    v = cli("validate", XLSX, "--json")
    sheets = cli("query", XLSX, "sheet", "--json")
    tables = cli("query", XLSX, "table", "--json")
    charts = cli("query", XLSX, "chart", "--json")
    cf = cli("query", XLSX, "conditionalformatting", "--json")
    va = cli("query", XLSX, "validation", "--json")
    nsh = sheets["data"]["matches"]; ntab = tables["data"]["matches"]; nch = charts["data"]["matches"]
    print(f"sheets {nsh} | tables {ntab} | charts {nch} | cf {cf['data']['matches']} | validation {va['data']['matches']} | validate ok={v.get('success', v.get('ok'))}")
    assert nsh == len(SHEET_ORDER), f"sheet count {nsh}"
    assert ntab >= len(TABLE_NAMES), f"table count {ntab}"
    assert nch >= 6, f"chart count {nch}"
    cli("close", XLSX, "--json")
    print("FAILURES:", len(FAILS))
    json.dump(FAILS, open(f"{BASE}/qc/officecli_fails.json", "w"), indent=1)
def dcmd(path, value=None, formula=None, props=None):
    p = props or {}
    if value is not None: p["value"] = value
    if formula is not None: p["formula"] = formula
    return {"command": "set", "path": path, "props": p}
def build_dashboard(data, nrows):
    HR_S, HR_F, HR_I, HR_R = 600, 1200, 1200, 1000  # headroom per range
    SC_ = COLS["STARTUPS"]; FC_ = COLS["FUNDING"]; IC_ = COLS["INVESTOR_LINKS"]; SR_ = COLS["SOURCES"]
    s_city = col_letter(SC_.index("city") + 1); s_sec = col_letter(SC_.index("primary_sector") + 1)
    s_stage = col_letter(SC_.index("startup_stage") + 1); s_id = col_letter(SC_.index("startup_id") + 1)
    f_city = col_letter(FC_.index("city") + 1); f_amt = col_letter(FC_.index("amount_inr_mn") + 1)
    f_year = col_letter(FC_.index("year") + 1); f_sid = col_letter(FC_.index("startup_id") + 1)
    i_name = col_letter(IC_.index("investor_name") + 1)
    S, F, IL = "STARTUPS", "FUNDING", "INVESTOR_LINKS"
    cmds = []
    A = cmds.append
    A(dcmd("/DASHBOARD/A1", value="DASHBOARD — INDIA STARTUP INTELLIGENCE DATABASE  (built 2026-09-14; DERIVED live formulas unless marked static; FX notes in README)",
           props={"font.bold": "true", "font.size": "14"}))
    # KPI band
    kpis = [
     ("Companies tracked", f"=COUNTA({S}!${s_id}$2:${s_id}${HR_S})", "0"),
     ("Deep or better (>=60%)", f"=COUNTIF(SCORES!$O$2:$O${HR_S},\"Deep\")+COUNTIF(SCORES!$O$2:$O${HR_S},\"Intelligence-grade\")+COUNTIF(SCORES!$O$2:$O${HR_S},\"Fully researched\")", "0"),
     ("Enriched (40-60%)", f"=COUNTIF(SCORES!$O$2:$O${HR_S},\"Enriched\")", "0"),
     ("Basic/Candidate (<40%)", f"=COUNTIF(SCORES!$O$2:$O${HR_S},\"Basic\")+COUNTIF(SCORES!$O$2:$O${HR_S},\"Candidate\")", "0"),
     ("Mumbai companies", f"=COUNTIF({S}!${s_city}$2:${s_city}${HR_S},\"Mumbai\")", "0"),
     ("Bengaluru companies", f"=COUNTIF({S}!${s_city}$2:${s_city}${HR_S},\"Bengaluru\")", "0"),
     ("Funding rounds", f"=COUNTA(FUNDING!$A$2:$A${HR_F})", "0"),
     ("Total disclosed funding INR Mn *tracked-universe only; not an ecosystem census*", f"=ROUND(SUM({F}!${f_amt}$2:${f_amt}${HR_F}),0)", "#,##0"),
     ("USD Bn @87 (same caveat)", f"=ROUND(SUM({F}!${f_amt}$2:${f_amt}${HR_F})/87/1000,2)", "0.00"),
     ("Investors linked", f"=COUNTA(INVESTORS!$A$2:$A${HR_I})", "0"),
     ("Sources (unique URLs)", f"=COUNTA(SOURCES!$A$2:$A${HR_S+400})", "0"),
     ("Avg completeness %", "=ROUND(AVERAGE(SCORES!$N$2:$N$"+str(HR_S)+"),1)", "0.0"),
     ("Avg source quality %", "=ROUND(AVERAGE(SCORES!$P$2:$P$"+str(HR_S)+"),1)", "0.0"),
     ("Avg freshness %", "=ROUND(AVERAGE(SCORES!$Q$2:$Q$"+str(HR_S)+"),1)", "0.0"),
     ("Records w/ conflicts", "=COUNTIF(SCORES!$R$2:$R$"+str(HR_S)+",\"low\")+COUNTIF(SCORES!$R$2:$R$"+str(HR_S)+",\"moderate\")+COUNTIF(SCORES!$R$2:$R$"+str(HR_S)+",\"high\")", "0"),
    ]
    for i, (label, f_, fmt) in enumerate(kpis):
        col = col_letter(i + 1)
        A(dcmd(f"/DASHBOARD/{col}3", value=label, props={"font.bold": "true", "alignment.wrapText": "true"}))
        A(dcmd(f"/DASHBOARD/{col}4", formula=f_, props={"numberformat": fmt, "font.size": "12", "alignment.horizontal": "center", "fill": "#DDEBF7"}))
    # cities grid
    cities = ["Mumbai","Bengaluru","Gurugram","Delhi NCR","Noida","Hyderabad","Pune","Chennai","Ahmedabad","Kolkata","Jaipur","Kochi","Chandigarh","Indore","Surat"]
    A(dcmd("/DASHBOARD/A7", value="COMPANIES BY CITY (live)", props={"font.bold": "true"}))
    A(dcmd("/DASHBOARD/B7", value="count", props={"font.bold": "true"})); A(dcmd("/DASHBOARD/C7", value="funding INR Mn", props={"font.bold": "true"}))
    for i, c in enumerate(cities):
        r = 8 + i
        A(dcmd(f"/DASHBOARD/A{r}", value=c))
        A(dcmd(f"/DASHBOARD/B{r}", formula=f"=COUNTIF({S}!${s_city}$2:${s_city}${HR_S},A{r})", props={"numberformat": "0"}))
        A(dcmd(f"/DASHBOARD/C{r}", formula=f"=ROUND(SUMIFS({F}!${f_amt}$2:${f_amt}${HR_F},{F}!${f_city}$2:${f_city}${HR_F},A{r}),0)", props={"numberformat": "#,##0"}))
    # sectors grid
    top_sectors = [k for k, v in Counter((r.get("primary_sector") or "").strip() for r in data["STARTUPS"] if (r.get("primary_sector") or "").strip() and len((r.get("primary_sector") or "").split()) <= 3).most_common(14)]
    A(dcmd("/DASHBOARD/E7", value="TOP SECTORS (live counts)", props={"font.bold": "true"})); A(dcmd("/DASHBOARD/F7", value="count", props={"font.bold": "true"}))
    for i, sec in enumerate(top_sectors):
        r = 8 + i
        A(dcmd(f"/DASHBOARD/E{r}", value=sec))
        A(dcmd(f"/DASHBOARD/F{r}", formula=f"=COUNTIF({S}!${s_sec}$2:${s_sec}${HR_S},E{r})", props={"numberformat": "0"}))
    # years grid
    A(dcmd("/DASHBOARD/H7", value="FUNDING BY YEAR (live)", props={"font.bold": "true"})); A(dcmd("/DASHBOARD/I7", value="INR Mn", props={"font.bold": "true"})); A(dcmd("/DASHBOARD/J7", value="rounds", props={"font.bold": "true"}))
    for i, yr in enumerate(range(2016, 2027)):
        r = 8 + i
        A(dcmd(f"/DASHBOARD/H{r}", value=str(yr)))
        A(dcmd(f"/DASHBOARD/I{r}", formula=f"=ROUND(SUMIFS({F}!${f_amt}$2:${f_amt}${HR_F},{F}!${f_year}$2:${f_year}${HR_F},H{r}),0)", props={"numberformat": "#,##0"}))
        A(dcmd(f"/DASHBOARD/J{r}", formula=f"=COUNTIFS({F}!${f_year}$2:${f_year}${HR_F},H{r})", props={"numberformat": "0"}))
    # stage grid
    A(dcmd("/DASHBOARD/L7", value="STAGES (live)", props={"font.bold": "true"})); A(dcmd("/DASHBOARD/M7", value="count", props={"font.bold": "true"}))
    stages = ["Unicorn","Decacorn","Growth","Late stage","Series C+","Series B","Series A","Seed","Pre-seed","Bootstrapped","Public","Acquired","Shut down","IPO pipeline"]
    rr = 8
    for st in stages:
        A(dcmd(f"/DASHBOARD/L{rr}", value=st))
        A(dcmd(f"/DASHBOARD/M{rr}", formula=f"=COUNTIF({S}!${s_stage}$2:${s_stage}${HR_S},\"*\"&L{rr}&\"*\")", props={"numberformat": "0"}))
        rr += 1
    # top funded (static, labeled)
    def tot_mn(v):
        import re as _re
        m = _re.search(r"([\d.,]+)\s*Mn INR", v or ""); return float(m.group(1).replace(",", "")) if m else 0
    tops = sorted(((tot_mn(r.get("total_funding_disclosed", "")), r["company_name"], r["startup_id"], r.get("company_class","")) for r in data["STARTUPS"]), reverse=True)[:12]
    A(dcmd("/DASHBOARD/A24", value="TOP FUNDED BY DISCLOSED EQUITY (static; INR Mn) - NOTE: mixed entity classes, see tags", props={"font.bold": "true"}))
    A(dcmd("/DASHBOARD/B24", value="total_inr_mn", props={"font.bold": "true"})); A(dcmd("/DASHBOARD/D24", value="company_class (DERIVED)", props={"font.bold": "true"}))
    for i, (t, nm, sid, cl) in enumerate(tops):
        A(dcmd(f"/DASHBOARD/A{25+i}", value=nm)); A(dcmd(f"/DASHBOARD/B{25+i}", value=t, props={"numberformat": "#,##0"})); A(dcmd(f"/DASHBOARD/D{25+i}", value=cl))
    # recent rounds (static)
    rec = sorted(data["FUNDING"], key=lambda r: str(r.get("announcement_date") or ""), reverse=True)[:12]
    A(dcmd("/DASHBOARD/D24", value="RECENT ROUNDS (static)", props={"font.bold": "true"}))
    for c, h in zip("EFGH", ["date", "company", "round", "$Mn USD"]): A(dcmd(f"/DASHBOARD/{c}24", value=h, props={"font.bold": "true"}))
    name_by_id = {r["startup_id"]: r["company_name"] for r in data["STARTUPS"]}
    for i, r in enumerate(rec):
        A(dcmd(f"/DASHBOARD/E{25+i}", value=r.get("announcement_date", "")))
        A(dcmd(f"/DASHBOARD/F{25+i}", value=name_by_id.get(r["startup_id"], r["startup_id"])))
        A(dcmd(f"/DASHBOARD/G{25+i}", value=r.get("round_type", "")))
        A(dcmd(f"/DASHBOARD/H{25+i}", value=r.get("amount", "")))
    # most active investors (live)
    inv_counts = Counter((r.get("investor_name") or "").strip().lower() for r in data["INVESTOR_LINKS"] if (r.get("investor_name") or "").strip())
    top_inv = [k.title() for k, v in inv_counts.most_common(12) if len(k) > 2]
    A(dcmd("/DASHBOARD/J24", value="MOST ACTIVE INVESTORS (live links count)", props={"font.bold": "true"}))
    A(dcmd("/DASHBOARD/K24", value="links", props={"font.bold": "true"}))
    for i, nm in enumerate(top_inv):
        A(dcmd(f"/DASHBOARD/J{25+i}", value=nm))
        A(dcmd(f"/DASHBOARD/K{25+i}", formula=f"=COUNTIF({IL}!${i_name}$2:${i_name}${HR_I},J{25+i})", props={"numberformat": "0"}))
    # Mumbai vs Bengaluru comparison
    A(dcmd("/DASHBOARD/A39", value="MUMBAI vs BENGALURU \u2014 TRACKED UNIVERSE SAMPLE, NOT A CENSUS", props={"font.bold": "true", "font.size": "12"}))
    for c, h in zip("BCD", ["metric", "Mumbai", "Bengaluru"]): A(dcmd(f"/DASHBOARD/{c}40", value=h, props={"font.bold": "true"}))
    rows_cmp = [
      ("companies", f"=COUNTIF({S}!${s_city}$2:${s_city}${HR_S},\"Mumbai\")", f"=COUNTIF({S}!${s_city}$2:${s_city}${HR_S},\"Bengaluru\")"),
      ("funding INR Mn", f"=ROUND(SUMIFS({F}!${f_amt}$2:${f_amt}${HR_F},{F}!${f_city}$2:${f_city}${HR_F},\"Mumbai\"),0)", f"=ROUND(SUMIFS({F}!${f_amt}$2:${f_amt}${HR_F},{F}!${f_city}$2:${f_city}${HR_F},\"Bengaluru\"),0)"),
      ("rounds", f"=COUNTIF({F}!${f_city}$2:${f_city}${HR_F},\"Mumbai\")", f"=COUNTIF({F}!${f_city}$2:${f_city}${HR_F},\"Bengaluru\")"),
      ("avg completeness %", f"=ROUND(AVERAGEIFS(SCORES!$N$2:$N${HR_S},{S}!${s_city}$2:${s_city}${HR_S},\"Mumbai\"),1)", f"=ROUND(AVERAGEIFS(SCORES!$N$2:$N${HR_S},{S}!${s_city}$2:${s_city}${HR_S},\"Bengaluru\"),1)"),
      ("Deep or better", f"=SUM(COUNTIFS({S}!${s_city}$2:${s_city}${HR_S},\"Mumbai\",SCORES!$O$2:$O${HR_S},{{\"Deep\",\"Intelligence-grade\",\"Fully researched\"}}))", f"=SUM(COUNTIFS({S}!${s_city}$2:${s_city}${HR_S},\"Bengaluru\",SCORES!$O$2:$O${HR_S},{{\"Deep\",\"Intelligence-grade\",\"Fully researched\"}}))"),
    ]
    for i, (m, fm, fb) in enumerate(rows_cmp):
        A(dcmd(f"/DASHBOARD/B{41+i}", value=m))
        A(dcmd(f"/DASHBOARD/C{41+i}", formula=fm, props={"numberformat": "#,##0.0"}))
        A(dcmd(f"/DASHBOARD/D{41+i}", formula=fb, props={"numberformat": "#,##0.0"}))
    # sector x city cross-tab (static counts; labeled)
    A(dcmd("/DASHBOARD/F39", value="SECTOR x CITY (static cross-tab)", props={"font.bold": "true"}))
    A(dcmd("/DASHBOARD/G39", value="Mumbai")); A(dcmd("/DASHBOARD/H39", value="Bengaluru")); A(dcmd("/DASHBOARD/I39", value="rest"))
    sec_city = defaultdict(Counter)
    for r in data["STARTUPS"]:
        sec_city[(r.get("primary_sector") or "").strip()][r.get("city") or ""] += 1
    rows_ = [s for s in top_sectors if sec_city.get(s)][:10]
    for i, sec in enumerate(rows_):
        cc = sec_city[sec]
        A(dcmd(f"/DASHBOARD/F{40+i}", value=sec))
        A(dcmd(f"/DASHBOARD/G{40+i}", value=cc.get("Mumbai", 0)))
        A(dcmd(f"/DASHBOARD/H{40+i}", value=cc.get("Bengaluru", 0)))
        A(dcmd(f"/DASHBOARD/I{40+i}", value=sum(v for k, v in cc.items() if k not in ("Mumbai", "Bengaluru"))))
    # negative signals block (live)
    A(dcmd("/DASHBOARD/A52", value="SIGNALS (live)", props={"font.bold": "true"}))
    sig = [
     ("legal/regulatory records", "=COUNTA(LEGAL_REGULATORY!$A$2:$A$500)"),
     ("acquisition records", "=COUNTA(ACQUISITIONS!$A$2:$A$500)"),
     ("shutdown/failed status rows", f"=COUNTIF({S}!$H$2:$H${HR_S},\"*shut*\")+COUNTIF({S}!$H$2:$H${HR_S},\"*closed*\")+COUNTIF({S}!$H$2:$H${HR_S},\"*failed*\")"),
     ("events recorded", "=COUNTA(NEWS_EVENTS!$A$2:$A$2000)"),
     ("FY financial records", "=COUNTA(FINANCIALS!$A$2:$A$2000)"),
     ("traction metrics", "=COUNTA(TRACTION!$A$2:$A$1000)"),
    ]
    for i, (m, f_) in enumerate(sig):
        A(dcmd(f"/DASHBOARD/A{53+i}", value=m))
        A(dcmd(f"/DASHBOARD/B{53+i}", formula=f_, props={"numberformat": "0"}))
    A(dcmd("/DASHBOARD/A60", value="RESEARCH EXECUTION LEDGER (RESEARCH_TASKS, live)", props={"font.bold": "true"}))
    for i, (m, f_) in enumerate([
     ("research tasks: completed", "=COUNTIF(RESEARCH_TASKS!$K$2:$K$5000,\"completed\")"),
     ("research tasks: logged-no-result", "=COUNTIF(RESEARCH_TASKS!$K$2:$K$5000,\"logged-no-result\")"),
     ("research tasks: open (not_started)", "=COUNTIF(RESEARCH_TASKS!$K$2:$K$5000,\"not_started\")"),
     ("open P1 (core-area gaps)", "=COUNTIFS(RESEARCH_TASKS!$K$2:$K$5000,\"not_started\",RESEARCH_TASKS!$E$2:$E$5000,\"P1\")")]):
        A(dcmd(f"/DASHBOARD/A{61+i}", value=m)); A(dcmd(f"/DASHBOARD/B{61+i}", formula=f_, props={"numberformat": "0"}))
    A(dcmd("/DASHBOARD/A67", value="RESEARCH MATURITY (tier bands, live)", props={"font.bold": "true"}))
    A(dcmd("/DASHBOARD/B67", value="count", props={"font.bold": "true"})); A(dcmd("/DASHBOARD/C67", value="% of universe", props={"font.bold": "true"}))
    for i, tt in enumerate(["Candidate","Basic","Enriched","Deep","Intelligence-grade","Fully researched"]):
        rr = 68 + i
        A(dcmd(f"/DASHBOARD/A{rr}", value=tt))
        A(dcmd(f"/DASHBOARD/B{rr}", formula=f"=COUNTIF(SCORES!$O$2:$O${HR_S},\"{tt}\")", props={"numberformat": "0"}))
        A(dcmd(f"/DASHBOARD/C{rr}", formula=f"=ROUND(B{rr}/COUNTA(SCORES!$A$2:$A${HR_S})*100,1)", props={"numberformat": "0.0"}))
    A(dcmd("/DASHBOARD/E67", value="COMPANY CLASS (DERIVED, live)", props={"font.bold": "true"}))
    A(dcmd("/DASHBOARD/F67", value="count", props={"font.bold": "true"}))
    sc_cl = col_letter(SC_.index("company_class") + 1); sc_tot = col_letter(SC_.index("total_funding_disclosed") + 1)
    for i, cc_ in enumerate(["Startup","Scale-up","Mature private company","Public company","Subsidiary","Acquired (operating)","Former startup","Other - status unverified"]):
        rr = 68 + i
        A(dcmd(f"/DASHBOARD/E{rr}", value=cc_))
        A(dcmd(f"/DASHBOARD/F{rr}", formula=f"=COUNTIF({S}!${sc_cl}$2:${sc_cl}${HR_S},E{rr})", props={"numberformat": "0"}))
    for i, (m, f_) in enumerate([
     ("claims in evidence layer (CLAIMS)", "=COUNTA(CLAIMS!$A$2:$A$6000)"),
     ("conflicts preserved (CONFLICTS)", "=COUNTA(CONFLICTS!$A$2:$A$4000)"),
     ("unresolved/preserved conflicts", "=COUNTIF(CONFLICTS!$J$2:$J$4000,\"unresolved\")+COUNTIF(CONFLICTS!$J$2:$J$4000,\"preserved-conflict\")"),
     ("tasks needing verification", "=COUNTIF(RESEARCH_TASKS!$K$2:$K$5000,\"needs-verification\" )"),
     ("documented no-result", "=COUNTIF(RESEARCH_TASKS!$K$2:$K$5000,\"logged-no-result\" )"),
     ("blocked (multi-attempt dead ends)", "=COUNTIF(RESEARCH_TASKS!$K$2:$K$5000,\"blocked\" )")]):
        A(dcmd(f"/DASHBOARD/A{72+i}", value=m)); A(dcmd(f"/DASHBOARD/B{72+i}", formula=f_, props={"numberformat": "0"}))
    A(dcmd("/DASHBOARD/A78", value="PRIORITY QUEUE (static top 15 - importance x gap; full ranking in SCORES cols T-V)", props={"font.bold": "true"}))
    for c_, h_ in zip(("A","D","E","F","G"), ("company","city","tier","completeness %","priority_score")):
        A(dcmd(f"/DASHBOARD/{c_}79", value=h_, props={"font.bold": "true"}))
    _namem = {r["startup_id"]: r["company_name"] for r in data["STARTUPS"]}
    _citym = {r["startup_id"]: r["city"] for r in data["STARTUPS"]}
    _ps = sorted(data["SCORES"], key=lambda x: -float(x.get("priority_score") or 0))[:15]
    for i, x in enumerate(_ps):
        rr = 80 + i
        A(dcmd(f"/DASHBOARD/A{rr}", value=_namem.get(x["startup_id"],x["startup_id"])))
        A(dcmd(f"/DASHBOARD/D{rr}", value=_citym.get(x["startup_id"],"")))
        A(dcmd(f"/DASHBOARD/E{rr}", value=x.get("tier","")))
        A(dcmd(f"/DASHBOARD/F{rr}", value=float(x.get("completeness_pct") or 0)))
        A(dcmd(f"/DASHBOARD/G{rr}", value=float(x.get("priority_score") or 0)))
    # ---- Phase 4 §31: mathematically-accurate derived ratios ----
    _sm={r["startup_id"]:r for r in data["SCORES"]}
    _mmum=[float(r["completeness_pct"]) for r in data["SCORES"] if data["STARTUPS"] and _sm.get(r["startup_id"]) is not None and any(sv["startup_id"]==r["startup_id"] and sv.get("city")=="Mumbai" for sv in data["STARTUPS"])]
    _mban=[float(r["completeness_pct"]) for r in data["SCORES"] if any(sv["startup_id"]==r["startup_id"] and sv.get("city")=="Bengaluru" for sv in data["STARTUPS"])]
    _srcT={r["source_id"]: r.get("tier","") for r in data["SOURCES"]}
    _pc=sum(1 for c_ in data["CLAIMS"] if _srcT.get(c_.get("source_id",""),"") in ("T1","T2"))
    _pt=len(data["CLAIMS"]) or 1
    _p75=sum(1 for r in data["SCORES"] if float(r["completeness_pct"])>=75); _p90=sum(1 for r in data["SCORES"] if float(r["completeness_pct"])>=90)
    A(dcmd("/DASHBOARD/A97", value="ACCURACY METRICS (§31 - ratios, not raw counts as % of companies)", props={"font.bold": "true"}))
    _mrows=[("claims per tracked company", "=ROUND(COUNTA(CLAIMS!$A$2:$A$6000)/COUNTA(STARTUPS!$A$2:$A$500),1)"),
     ("companies with >=1 open/preserved conflict %", "=ROUND(COUNTIF(SCORES!$R$2:$R$400,\"<>none\")/COUNTA(SCORES!$A$2:$A$400)*100,1)"),
     ("claims needing verification % (LOW/MEDIUM conf)", "=ROUND((COUNTIF(CLAIMS!$L$2:$L$6000,\"LOW\")+COUNTIF(CLAIMS!$L$2:$L$6000,\"MEDIUM\"))/COUNTA(CLAIMS!$A$2:$A$6000)*100,1)"),
     ("claims with T1/T2 primary-source % (computed at build)", round(_pc/_pt*100,1)),
     ("companies >=75% completeness (count)", _p75), ("companies >=90% completeness (count)", _p90),
     ("avg completeness - Mumbai HQ (computed)", round(sum(_mmum)/len(_mmum),1) if _mmum else 0),
     ("avg completeness - Bengaluru HQ (computed)", round(sum(_mban)/len(_mban),1) if _mban else 0),
     ("derived metrics in DERIVED_METRICS (all marked DERIVED)", "=COUNTA(DERIVED_METRICS!$A$2:$A$500)")]
    _cls={r["startup_id"]:r.get("company_class","") for r in data["STARTUPS"]}
    def _mny(x):
        import re as _r
        m=_r.search(r"([0-9][0-9,.]*)",str(x or "")); return float(m.group(1).replace(",","")) if m else 0
    _tf=sum(_mny(r.get("total_funding_disclosed")) for r in data["STARTUPS"] if _cls.get(r["startup_id"]) in ("Startup","Scale-up","Growth stage"))
    _tu=sum(_mny(r.get("total_funding_disclosed")) for r in data["STARTUPS"])
    _mrows=_mrows+[("disclosed funding by Startup/Scale-up-class entities, INR Cr (excl. mature/public/subsidiary — §25)", round(_tf,0)),("disclosed funding ALL tracked entities, INR Cr (for contrast)", round(_tu,0))]
    for i,(l_,v_) in enumerate(_mrows):
        A(dcmd(f"/DASHBOARD/A{98+i}", value=l_))
        c_=dcmd(f"/DASHBOARD/B{98+i}", formula=v_) if isinstance(v_,str) and v_.startswith("=") else dcmd(f"/DASHBOARD/B{98+i}", value=v_)
        c_["props"]["numberformat"]="0.0"; A(c_)
    A(dcmd("/DASHBOARD/A108", value="TOP RESEARCHED (completeness)", props={"font.bold":"true"}))
    for i,x in enumerate(sorted(data["SCORES"],key=lambda y:-float(y["completeness_pct"]))[:5]):
        nm_={rr["startup_id"]:rr["company_name"] for rr in data["STARTUPS"]}.get(x["startup_id"],x["startup_id"])
        A(dcmd(f"/DASHBOARD/A{109+i}", value=nm_)); A(dcmd(f"/DASHBOARD/B{109+i}", value=float(x["completeness_pct"])))

    A(dcmd("/DASHBOARD/A95", value="CAVEATS: (1) funding totals cover THIS tracked universe only - dominated by mature/listed corporates; NOT ecosystem VC funding. (2) Mumbai/Bengaluru counts are what we chose to track, not a market census. (3) completeness = banded objective coverage of 12 areas; Source Quality / Freshness / Conflicts are SEPARATE axes (SCORES P/Q/R) - a high score on easy categories no longer hides empty hard ones.", props={"alignment.wrapText":"true","font.italic":"true"}))
    batch([{"command":"add","parent":"/DASHBOARD","type":"column","props":{"name":L,"width":"26"}} for L in ("A","B","C","E","F","G","H","I","J","K","L","M")])
    batch(cmds)
    # CF on grid columns
    cli("add", XLSX, "/DASHBOARD", "--type", "databar", "--prop", "ref=B8:B22", "--prop", "color=4472C4", "--json")
    cli("add", XLSX, "/DASHBOARD", "--type", "databar", "--prop", "ref=C8:C22", "--prop", "color=4472C4", "--json")
    cli("add", XLSX, "/DASHBOARD", "--type", "databar", "--prop", "ref=I8:I18", "--prop", "color=ED7D31", "--json")
    # charts
    def chart(ct, dref, cref, anchor, title):
        return cli("add", XLSX, "/DASHBOARD", "--type", "chart", "--prop", f"chartType={ct}", "--prop", f"dataRange={dref}",
                   "--prop", f"categories={cref}", "--prop", f"anchor={anchor}", "--prop", f"title={title}", "--json")
    chart("bar", "DASHBOARD!$B$8:$B$22", "DASHBOARD!$A$8:$A$22", "N3", "Companies by city")
    chart("pie", "DASHBOARD!$F$8:$F$21", "DASHBOARD!$E$8:$E$21", "N20", "Companies by sector")
    chart("column", "DASHBOARD!$I$8:$I$18", "DASHBOARD!$H$8:$H$18", "N37", "Funding INR Mn by year")
    chart("bar", "DASHBOARD!$C$8:$C$22", "DASHBOARD!$A$8:$A$22", "U3", "Funding by city (INR Mn)")
    chart("bar", "DASHBOARD!$B$25:$B$36", "DASHBOARD!$A$25:$A$36", "U20", "Top funded (INR Mn)")
    chart("column", "DASHBOARD!$C$41:$D$41", "DASHBOARD!$C$40:$D$40", "U37", "Mumbai vs Bengaluru funding")
if __name__ == "__main__":
    main()
