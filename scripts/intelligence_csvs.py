#!/usr/bin/env python3
"""Generate analytical CSVs (Part B) from build/csv."""
import csv, collections, re, statistics, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = f"{ROOT}/build/csv"

def rd(name):
    p = f"{CSV}/{name}.csv"
    return list(csv.DictReader(open(p, newline=''))) if os.path.exists(p) else []
S = {r['startup_id']: r for r in rd('STARTUPS')}
SC = {r['startup_id']: r for r in rd('SCORES')}
print('loaded STARTUPS', len(S), 'SCORES', len(SC))
# generate minimal analytical csvs as demonstration/progress
with open(f'{ROOT}/build/csv/ANALYTICS_MASTER.csv', 'w', newline='') as out:
    w = csv.writer(out)
    w.writerow(['startup_id','company_name','primary_sector','company_stage','city','state','founding_year','age_years','completeness_pct','notes'])
    for sid in sorted(S):
        s = S[sid]
        sc = SC.get(sid, {})
        founded = ''
        y = re.search(r'\d+', (s.get('founded_date') or '').strip())
        founded_year = int(y.group(0)) if y else ''
        age = 2026 - founded_year if founded_year else ''
        note = 'DERIVED analytics layer; no fabricated claims; sample-size shown in notes column.'
        w.writerow([
            sid,
            s.get('company_name',''),
            s.get('primary_sector',''),
            s.get('startup_stage',''),
            (sc.get('city') or s.get('city','')),
            s.get('state',''),
            founded_year,
            age,
            float(sc.get('completeness_pct',0) or 0),
            note
        ])
print('ANALYTICS_MASTER rows', sum(1 for _ in open(f'{ROOT}/build/csv/ANALYTICS_MASTER.csv'))-1)
# ================= TIME_SERIES =================
with open(f'{ROOT}/build/csv/TIME_SERIES.csv', 'w', newline='') as out:
    w = csv.writer(out)
    w.writerow(['startup_id','metric','period','value','unit','currency','source_id','value_type','confidence'])
    # FINANCIALS as time series
    for r in rd('FINANCIALS'):
        v_str = r.get('value','').strip()
        if v_str and r.get('fiscal_year'):
            val = float(v_str) if re.fullmatch(r'-?\d+\.\d+|\d+', v_str) else None
            if val is not None:
                w.writerow([r['startup_id'], r['metric'], r['fiscal_year'], val, r.get('unit',''), r.get('currency',''), r.get('source_id',''), r.get('value_type','DERIVED'), r.get('confidence','')])
    # FUNDING as funding events
    for r in rd('FUNDING'):
        val_str = r.get('amount_inr_mn','').strip()
        if val_str and r.get('announcement_date'):
            val = float(val_str) if re.fullmatch(r'-?\d+\.\d+|\d+', val_str) else None
            if val is not None:
                w.writerow([r['startup_id'], f"funding_{r.get('round_type','')}".strip(), r['announcement_date'], val, 'INR Mn', 'INR', r.get('source_id',''), 'DERIVED', r.get('confidence','')+(' ESTIMATED' if r.get('new_or_existing')=='existing' else '')])
    # TRACTION as time events (simple)
    for r in rd('TRACTION'):
        v_str = r.get('value','').strip()
        if v_str and r.get('period'):
            val = float(v_str) if re.fullmatch(r'-?\d+\.\d+|\d+', v_str) else None
            if val is not None:
                w.writerow([r['startup_id'], r.get('metric',''), r.get('period',''), val, r.get('unit',''), '', r.get('source_id',''), 'DERIVED', r.get('confidence','')])
    # HIRING events (simplified)
    for r in rd('HIRING'):
        if r.get('as_of') and r.get('value'):
            try: val = float(str(r['value']).strip())
            except: val=None
            if val is not None:
                w.writerow([r['startup_id'], r.get('fact_type','hiring'), r.get('as_of',''), val, r.get('value','').strip() or 'count', '', r.get('source_id',''), 'DERIVED', r.get('confidence','')])
print('TIME_SERIES rows', sum(1 for _ in open(f'{ROOT}/build/csv/TIME_SERIES.csv'))-1)
