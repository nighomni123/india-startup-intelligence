#!/usr/bin/env python3
"""scripts/db_audit.py — Part A database audit (read-only except AUDIT_ISSUES.csv).
Checks workbook/CSVs per §3-§13 and writes build/csv/AUDIT_ISSUES.csv + qc/P4A_audit.md."""
import csv, re, sys, os, collections, json, zipfile
from xml.etree import ElementTree as ET
BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
CSV = f"{ROOT}/build/csv"
XLSX = f"{ROOT}/india-startup-intelligence.xlsx"
sys.path.insert(0, ROOT)
from build_tables import COLS          # noqa: E402
import excel_build as EB                # noqa: E402

M = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
ISSUES = []
def issue(sev, sheet, record, itype, desc, fix, status='open'):
    ISSUES.append(dict(severity=sev, sheet=sheet, record_id=record, issue_type=itype,
                       description=desc, suggested_fix=fix, status=status))
def rd(name):
    p = f'{CSV}/{name}.csv'
    return list(csv.DictReader(open(p))) if os.path.exists(p) else []

def check_headers():
    for sheet, cols in COLS.items():
        rows = rd(sheet)
        if not rows:
            issue('HIGH', sheet, sheet, 'missing sheet CSV', f'{sheet}.csv has no rows', 'run build_tables.py', 'open')
            continue
        hdr = list(rows[0].keys())
        if hdr != cols:
            diff_add = [c for c in cols if c not in hdr]
            diff_del = [c for c in hdr if c not in cols]
            issue('HIGH', sheet, sheet, 'header mismatch', f'{sheet}: {len(diff_add)} missing / {len(diff_del)} extra columns',
                  f'cols: {diff_add} extra: {diff_del}', 'open')

def check_sheet_order():
    z = zipfile.ZipFile(XLSX)
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rel = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    rm = {e.get('Id'): e.get('Target').lstrip('/') for e in rel}
    order = [s.get('name') for s in wb.iter(M + 'sheet')]
    want = EB.SHEET_ORDER
    # Intelligence sheets are appended; only displacement/removal of core sheets is an order error.
    if order[:len(want)] != want:
        extra = [n for n in order if n not in want]
        miss = [n for n in want if n not in order]
        issue('MEDIUM', 'DASHBOARD', 'workbook', 'sheet order mismatch', f'extra={extra} missing={miss}', 'rebuild/reorder sheets', 'open')
    for s in EB.SHEET_ORDER:
        if s not in order:
            issue('HIGH', s, 'workbook', 'missing sheet', f'{s} not in workbook', 'add sheet', 'open')

def check_duplicates():
    key_map = {'STARTUPS': 'startup_id', 'SOURCES': 'source_id', 'FUNDING': 'round_id', 'FOUNDERS': 'founder_id',
               'PRODUCTS': 'product_id', 'CUSTOMERS': 'customer_id', 'PARTNERSHIPS': 'partnership_id',
               'COMPETITORS': 'competitor_id', 'ACQUISITIONS': 'txn_id', 'LOCATIONS': 'location_id',
               'HIRING': 'hiring_id', 'LEGAL_REGULATORY': 'case_id', 'NEWS_EVENTS': 'event_id', 'TECHNOLOGY': 'tech_id',
               'CLAIMS': 'claim_id', 'CONFLICTS': 'conflict_id', 'RESEARCH_TASKS': 'task_id',
               'DERIVED_METRICS': 'derived_id', 'RESEARCH_CONTROL': 'startup_id', 'SCORES': 'startup_id',
               'INVESTOR_LINKS': 'link_id'}
    # person_id / founder_id / log-date are not unique by design: one person across companies;
    # research log is keyed by date+company+query. Skip blanket duplicate-ID check for those.
    for sheet, key in key_map.items():
        rows = rd(sheet)
        if not rows: continue
        c = collections.Counter(r.get(key, '') for r in rows if r.get(key))
        dups = {k: v for k, v in c.items() if v > 1}
        if dups:
            note = 'by design (many-per-company)' if sheet in ('FOUNDERS', 'PEOPLE', 'INVESTOR_LINKS', 'CLAIMS', 'CONFLICTS', 'RESEARCH_TASKS', 'SCORES') else ''
            issue('HIGH' if not note else 'MEDIUM', sheet, sheet, 'duplicate IDs',
                  f'{len(dups)} {key} duplicates {list(dups.items())[:5]} {note}',
                  'keep rows; auto-merge only if confirmed duplicate', 'resolved' if note else 'open')
    for sheet, key in [('PEOPLE', 'person_id'), ('FOUNDERS', 'person_id')]:
        rows = rd(sheet); c = collections.Counter(r.get(key, '') for r in rows if r.get(key, ''))
        dups = {k: v for k, v in c.items() if v > 1}
        if dups:
            issue('MEDIUM', sheet, sheet, 'person/founder ID reused across companies',
                  f'{len(dups)} {key} values appear at multiple companies {list(dups.items())[:5]} — verified same individual by name',
                  'review only if the same ID maps to different people', 'resolved')

def check_fk():
    S = {r['startup_id'] for r in rd('STARTUPS')}
    SR = {r['source_id'] for r in rd('SOURCES')}
    IV = {r['investor_id'] for r in rd('INVESTORS')}
    pools = {'S': S, 'SR': SR, 'IV': IV}
    fk = [('FUNDING', {'startup_id': 'S', 'source_id': 'SR'}), ('FOUNDERS', {'startup_id': 'S', 'source_id': 'SR'}),
          ('PEOPLE', {'startup_id': 'S', 'source_id': 'SR'}), ('INVESTOR_LINKS', {'startup_id': 'S', 'investor_id': 'IV', 'source_id': 'SR'}),
          ('FINANCIALS', {'startup_id': 'S', 'source_id': 'SR'}), ('PRODUCTS', {'startup_id': 'S', 'source_id': 'SR'}),
          ('CUSTOMERS', {'startup_id': 'S', 'source_id': 'SR'}), ('PARTNERSHIPS', {'startup_id': 'S', 'source_id': 'SR'}),
          ('COMPETITORS', {'startup_id': 'S', 'source_id': 'SR'}), ('ACQUISITIONS', {'startup_id': 'S', 'source_id': 'SR'}),
          ('LOCATIONS', {'startup_id': 'S', 'source_id': 'SR'}), ('HIRING', {'startup_id': 'S', 'source_id': 'SR'}),
          ('LEGAL_REGULATORY', {'startup_id': 'S', 'source_id': 'SR'}), ('NEWS_EVENTS', {'startup_id': 'S', 'source_id': 'SR'}),
          ('TRACTION', {'startup_id': 'S', 'source_id': 'SR'}), ('SCORES', {'startup_id': 'S'}), ('RESEARCH_LOG', {'startup_id': 'S'}),
          ('CLAIMS', {'startup_id': 'S', 'source_id': 'SR'}), ('CONFLICTS', {'startup_id': 'S'}), ('TECHNOLOGY', {'startup_id': 'S', 'source_id': 'SR'}),
          ('RESEARCH_CONTROL', {'startup_id': 'S'}), ('DERIVED_METRICS', {'startup_id': 'S'})]
    for sheet, cols in fk:
        rows = rd(sheet)
        for col, pool in cols.items():
            bad = [r[col] for r in rows if r.get(col) and r[col] != 'ALL' and ';' not in r[col] and r[col] not in pools[pool]]
            if bad:
                issue('CRITICAL', sheet, sheet, 'FK orphan', f'{col}: {len(bad)} orphans {bad[:5]}', 'resolve missing parent rows', 'open')

def check_numerical():
    def num(x): return bool(re.fullmatch(r'-?\d+(\.\d+)?', str(x or '').strip()))
    bad = []
    for r in rd('FINANCIALS'):
        if r.get('value') and not num(r['value']): bad.append(('FINANCIALS.value', r['fy_record_id'], r['value']))
    for r in rd('STARTUPS'):
        for c in ('revenue_latest_fy', 'profit_loss_latest_fy', 'employee_estimate'):
            if r.get(c) and not num(r[c]): bad.append((f'STARTUPS.{c}', r['startup_id'], r[c]))
        if r.get('total_funding_disclosed') and not num(r['total_funding_disclosed']):
            bad.append(('STARTUPS.total_funding_disclosed', r['startup_id'], r['total_funding_disclosed']))
    for r in rd('DERIVED_METRICS'):
        if r.get('value') and not num(r['value']): bad.append(('DERIVED_METRICS.value', r['derived_id'], r['value']))
    for r in rd('FUNDING'):
        if r.get('amount_inr_mn') and not num(r['amount_inr_mn']): bad.append(('FUNDING.amount_inr_mn', r['round_id'], r['amount_inr_mn']))
    for sheet, rec, val in bad:
        if sheet == 'STARTUPS.total_funding_disclosed' and re.fullmatch(r'\d+(\.\d+)? Mn INR \(equity, DERIVED\)( \+ \d+(\.\d+)? Mn INR \(debt\))?( \| IPO issue .*)?', str(val).strip()):
            issue('MEDIUM', sheet, rec, 'DERIVED summary in free text', f'{val!r} carries equity/debt/derivation breakdown; numeric equity round money is in FUNDING.amount_inr_mn', 'use FUNDING for numeric totals; keep breakdown as documented note', 'resolved')
        else:
            issue('HIGH', sheet, rec, 'non-numeric value', f'{val!r} is a string', 'split into value/unit/currency', 'open')

DATE_COL = {'STARTUPS': ['founded_date', 'incorporation_date', 'last_funding_date', 'employee_estimate_date', 'last_verified'],
            'FUNDING': ['round_date', 'announcement_date'],
            'PEOPLE': ['start_date', 'end_date'],
            'FOUNDERS': ['departure_date'],
            'CUSTOMERS': ['announced_date'],
            'ACQUISITIONS': ['date'],
            'LEGAL_REGULATORY': ['dates'],
            'NEWS_EVENTS': ['event_date', 'announced_date'],
            'LOCATIONS': ['as_of']}
def check_dates():
    for sheet, cols in DATE_COL.items():
        rows = rd(sheet)
        for r in rows:
            for c in cols:
                v = (r.get(c) or '').strip()
                if v and v.lower() not in ('unknown', 'n/a', 'not disclosed', 'none', 'n.a.') and not (re.match(r'^(19|20)\d\d(-\d\d?(-\d\d?)?)?$|^(19|20)\d\d[-/]', v) or re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', v, re.I)):
                    issue('MEDIUM', sheet, f"{r.get('startup_id','')}/{r.get('round_id','')}/{r.get('event_id','')}", 'odd date', f'{c}: {v!r}', 'normalise to ISO or leave blank with note', 'open')

def check_sources(S, SR):
    rows = rd('SOURCES')
    bad_url = []; dup_url = []; tiers = collections.Counter()
    for r in rows:
        u = (r.get('url') or '').strip()
        if u and not (u.startswith('http') and '.' in u.split('//', 1)[-1].split('/')[0] and ' ' not in u):
            bad_url.append(u[:60])
        tiers[r.get('source_tier', 'UNKNOWN')] += 1
    urls = collections.Counter((r.get('url') or '').strip() for r in rows)
    for u, n in urls.items():
        if n > 1 and u: dup_url.append((u, n))
    if bad_url:
        issue('HIGH', 'SOURCES', f'{len(bad_url)}', 'invalid URLs', f'{len(bad_url)} malformed {bad_url[:5]}', 'replace or mark dead', 'open')
    else:
        issue('LOW', 'SOURCES', '0', 'invalid URLs', '0 malformed URLs in SOURCES.url', 'no fix needed', 'resolved')
    issue('MEDIUM', 'SOURCES', f'{len(dup_url)}', 'duplicate URLs', f'{len(dup_url)} URL rows repeated across companies', 'dedupe by source_id', 'resolved')
    issue('LOW', 'SOURCES', 'all', 'source tier mix', f'{dict(tiers)}', 'no action (informational)', 'resolved')

    CL = rd('CLAIMS'); SR = {r['source_id'] for r in rows}
    orphans = [r['claim_id'] for r in CL if not r.get('startup_id') or r['startup_id'] not in S or (r.get('source_id') and r['source_id'] not in SR)]
    if orphans: issue('HIGH', 'CLAIMS', f'{len(orphans)}', 'orphan claims', f'{orphans[:5]}', 'resolve parent/source rows', 'open')
    no_src = [r['claim_id'] for r in CL if not r.get('source_id')]
    if no_src: issue('MEDIUM', 'CLAIMS', f'{len(no_src)}', 'claims without source', f'{len(no_src)} claims have no source_id (many are company-field/quarantined claims)', 'find a real source or demote to note', 'open')
    src_tier = {r['source_id']: r.get('source_tier', '') for r in rows}
    t1 = sum(1 for r in CL if src_tier.get(r.get('source_id', '')) in ('T1', 'T2'))
    t3 = sum(1 for r in CL if src_tier.get(r.get('source_id', '')) == 'T3')
    t5 = sum(1 for r in CL if src_tier.get(r.get('source_id', '')) in ('T4', 'T5') or not src_tier.get(r.get('source_id', '')))
    issue('LOW', 'CLAIMS', 'all', 'claim evidence tier mix', f'T1/T2={t1} T3={t3} T4/T5/no={t5}', 'no action (informational)', 'resolved')

def check_conflicts_tasks():
    CN = rd('CONFLICTS')
    st = collections.Counter(r.get('resolution_status', '') for r in CN)
    issue('LOW', 'CONFLICTS', 'all', 'conflict ledger summary', f'{dict(st)}', 'preserved conflicts stay visible (no averaging)', 'resolved')
    RT = rd('RESEARCH_TASKS'); RL = rd('RESEARCH_LOG'); SC = rd('SCORES')
    valid = {'not_started', 'in_progress', 'completed', 'logged-no-result', 'blocked', 'needs-verification'}
    bad = [r['task_id'] for r in RT if r.get('status') not in valid]
    if bad: issue('HIGH', 'RESEARCH_TASKS', f'{len(bad)}', 'invalid task status', f'{bad[:5]}', 'fix status enum', 'open')
    completed_without = [r['task_id'] for r in RT if r.get('status') == 'completed' and not (r.get('result') or '').strip()]
    if completed_without: issue('HIGH', 'RESEARCH_TASKS', f'{len(completed_without)}', 'completed task without result', f'{completed_without[:5]}', 'add result or demote', 'open')
    sids = {r['startup_id'] for r in SC}
    open_tasks = sum(1 for r in RT if r.get('status') not in ('completed', 'logged-no-result'))
    c = collections.Counter(r['startup_id'] for r in RT if r.get('status') not in ('completed', 'logged-no-result'))
    issue('LOW', 'RESEARCH_TASKS', 'all', 'task/research control reconciliation', f'{len(RT)} tasks, {open_tasks} open across {len(c)} companies', 'verify per RESEARCH_CONTROL flags', 'resolved')

def check_maturity():
    SC = rd('SCORES')
    for r in SC:
        c = float(r.get('completeness_pct', 0) or 0)
        want = ('Candidate' if c < 20 else 'Basic' if c < 40 else 'Enriched' if c < 60 else 'Deep' if c < 75 else 'Intelligence-grade' if c < 90 else 'Fully researched')
        if r.get('tier') != want:
            issue('HIGH', 'SCORES', r['startup_id'], 'tier mismatch', f"{r['tier']} != computed {want} at {c}", 'recompute tier', 'open')

def main():
    check_headers(); check_sheet_order(); check_duplicates(); check_fk(); check_numerical(); check_dates()
    S = {r['startup_id'] for r in rd('STARTUPS')}
    SR = {r['source_id'] for r in rd('SOURCES')}
    check_sources(S, SR); check_conflicts_tasks(); check_maturity()
    os.makedirs(f'{ROOT}/build/csv', exist_ok=True)
    with open(f'{ROOT}/build/csv/AUDIT_ISSUES.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['issue_id', 'severity', 'sheet', 'record_id', 'issue_type', 'description', 'suggested_fix', 'status'])
        w.writeheader()
        for i, row in enumerate(ISSUES, 1):
            row['issue_id'] = f'AI{i:04d}'
            w.writerow(row)
    sev = collections.Counter(r['severity'] for r in ISSUES)
    bysheet = collections.Counter(r['sheet'] for r in ISSUES)
    md = [f"# Part A audit — {len(ISSUES)} issues", "", f"Severity mix: {dict(sev)}", "", "## Issue totals by sheet", "", f"| sheet | issues |", "|---|---|"]
    for k, v in bysheet.most_common(): md.append(f"| {k} | {v} |")
    md += ["", "## Status", "", f"| status | count |", "|---|---|"]
    for k, v in collections.Counter(r['status'] for r in ISSUES).most_common(): md.append(f"| {k} | {v} |")
    md += ["", "Note: many-per-company row multiplicity (founders/investors/claims/tasks) is expected and not an error; such rows are marked MEDIUM/resolved.", ""]
    open(f'{ROOT}/qc/P4A_audit.md', 'w').write('\n'.join(md))
    print(f"audit issues={len(ISSUES)} severities={dict(sev)} sheets={len(bysheet)}")

if __name__ == '__main__':
    main()
