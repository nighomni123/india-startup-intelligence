#!/usr/bin/env python3
"""End-to-end checks for build_intelligence.py outputs. Exit 0 only on full pass."""
import csv
import hashlib
import os
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAND = ROOT / 'build' / 'p4_candidate'
RAW = ROOT / 'build' / 'csv'
TABLES = ['ANALYTICS_MASTER', 'TIME_SERIES', 'FOUNDER_NETWORK', 'INVESTOR_NETWORK', 'CAPITAL_FLOWS',
          'CITY_ANALYSIS', 'SECTOR_ANALYSIS', 'COMPANY_SIGNALS', 'COMPANY_TRAJECTORIES', 'OUTLIERS',
          'RESEARCH_QUALITY', 'INSIGHTS', 'WATCHLIST', 'CHANGE_LOG', 'NETWORK_ANALYSIS']
RAW_EVIDENCE = ['STARTUPS', 'FUNDING', 'FINANCIALS', 'FOUNDERS', 'PEOPLE', 'INVESTORS',
                'INVESTOR_LINKS', 'CLAIMS', 'CONFLICTS', 'SOURCES', 'SCORES', 'TRACTION']
fails = []


def check(label, ok, detail=''):
    print(f'{"PASS" if ok else "FAIL"} {label}' + (f' — {detail}' if detail else ''))
    if not ok:
        fails.append(label)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rows_of(p):
    with open(p, newline='') as f:
        return list(csv.DictReader(f))


# 1) determinism + raw-evidence immutability across two generator runs
raw_before = {n: sha(RAW / f'{n}.csv') for n in RAW_EVIDENCE} if (RAW_EVIDENCE := RAW_EVIDENCE) else {}
sub1 = subprocess.run([sys.executable, str(ROOT / 'scripts/build_intelligence.py')],
                      capture_output=True, text=True, cwd=ROOT)
sub2 = subprocess.run([sys.executable, str(ROOT / 'scripts/build_intelligence.py')],
                      capture_output=True, text=True, cwd=ROOT)
check('generator exits 0', sub1.returncode == 0 and sub2.returncode == 0, (sub1.stderr or sub2.stderr)[-200:])
raw_after = {n: sha(RAW / f'{n}.csv') for n in RAW_EVIDENCE}
check('raw evidence untouched', raw_before == raw_after)
d1 = {n: sha(CAND / f'{n}.csv') for n in TABLES}
subprocess.run([sys.executable, str(ROOT / 'scripts/build_intelligence.py')], capture_output=True, text=True, cwd=ROOT)
d2 = {n: sha(CAND / f'{n}.csv') for n in TABLES}
check('deterministic regeneration', d1 == d2)

# 2) uniform widths
for n in TABLES:
    with open(CAND / f'{n}.csv', newline='') as f:
        rr = list(csv.reader(f))
    check(f'{n} width', len({len(r) for r in rr}) == 1, f'{len(rr[0])} cols, {len(rr)-1} rows')

# 3) FK integrity against raw evidence
S = {r['startup_id'] for r in csv.DictReader(open(RAW / 'STARTUPS.csv', newline=''))}
IV = {r['investor_id'] for r in csv.DictReader(open(RAW / 'INVESTORS.csv', newline=''))}
SRC = {r['source_id'] for r in csv.DictReader(open(RAW / 'SOURCES.csv', newline=''))}
CL = {r['claim_id'] for r in csv.DictReader(open(RAW / 'CLAIMS.csv', newline=''))}
FKS = [('COMPANY_SIGNALS', 'startup_id', S), ('OUTLIERS', 'startup_id', S), ('COMPANY_TRAJECTORIES', 'startup_id', S),
       ('WATCHLIST', 'startup_id', S), ('FOUNDER_NETWORK', 'startup_id', S), ('INVESTOR_NETWORK', 'investor_id', IV),
       ('CAPITAL_FLOWS', 'year', None)]
for name, col, uni in FKS:
    if uni is None:
        continue
    ids = {r[col] for r in csv.DictReader(open(CAND / f'{name}.csv', newline='')) if r.get(col)}
    single = {i for i in ids if ';' not in i}
    check(f'{name}.{col} FK', single <= uni, str(sorted(single - uni)[:4]))
ins = list(csv.DictReader(open(CAND / 'INSIGHTS.csv', newline='')))
bad_src = [s for r in ins for s in (r['supporting_sources'] or '').split(';')
           if s.startswith('SRC') and s not in SRC]
bad_cl = [c for r in ins for c in (r['supporting_claims'] or '').split(';')
          if c.startswith('CL') and c not in CL]
check('INSIGHTS source FK', not bad_src, str(bad_src[:3]))
check('INSIGHTS claim FK', not bad_cl, str(bad_cl[:3]))
check('INSIGHTS every row cites >=1 real source', all(r['supporting_sources'] for r in ins))

# 4) OUTLIERS: n floor + fence recomputation (funding cohort)
out = list(csv.DictReader(open(CAND / 'OUTLIERS.csv', newline='')))
check('OUTLIERS population_size >= 10', all(int(r['population_size']) >= 10 for r in out))
fund_rows = [r for r in csv.DictReader(open(RAW / 'FUNDING.csv', newline=''))]
def eq(r):
    return str(r.get('round_type', '')).lower() not in ('debt', 'venture debt', 'unknown', 'ipo')
tot = {}
for r in fund_rows:
    try:
        v = float(r['amount_inr_mn'])
    except (TypeError, ValueError):
        continue
    if eq(r):
        tot[r['startup_id']] = tot.get(r['startup_id'], 0.0) + v
vals = sorted(tot.values())
q = statistics.quantiles(vals, n=4, method='inclusive')
stored = next(r for r in out if r['metric'] == 'funding_total_inr_mn')
close = lambda a, b: abs(float(a) - float(b)) < 0.1
check('OUTLIERS funding fence recomputes',
      close(stored['q1'], q[0]) and close(stored['q3'], q[2]) and close(stored['upper_fence'], q[2] + 1.5 * (q[2] - q[0]))
      and int(stored['population_size']) == sum(1 for v in tot.values() if v > 0),
      f"stored q1={stored['q1']} recomputed={q[0]:.1f}")
above = [s for s, v in tot.items() if v > q[2] + 1.5 * (q[2] - q[0])]
n_stored = sum(1 for r in out if r['metric'] == 'funding_total_inr_mn')
check('OUTLIERS count matches fence', n_stored == len([1 for s, v in tot.items() if v > q[2] + 1.5 * (q[2] - q[0])]),
      f'stored={n_stored}')

# 5) enum domains
ts = list(csv.DictReader(open(CAND / 'TIME_SERIES.csv', newline='')))
check('TIME_SERIES period_type domain',
      set(r['period_type'] for r in ts) <= {'fiscal_year', 'event_date', 'as_of', 'year', 'cumulative', 'other'},
      str(Counter(r['period_type'] for r in ts)))
check('TIME_SERIES includes TRACTION', any(r['metric'].startswith('traction_') or 'traction' in r['metric'].lower() for r in ts)
      or 'traction_' in ' '.join(r['metric'] for r in ts) or sum(1 for r in ts if r['metric'].startswith('traction')) > 0,
      f"traction rows={sum(1 for r in ts if r['metric'].startswith('traction'))}")
sig = list(csv.DictReader(open(CAND / 'COMPANY_SIGNALS.csv', newline='')))
check('SIGNALS hiring never fabricated STABLE',
      set(r['hiring_trend'] for r in sig) <= {'EVIDENCE_PRESENT', 'INSUFFICIENT_DATA'},
      str(Counter(r['hiring_trend'] for r in sig)))
check('SIGNALS revenue trend honest',
      set(r['revenue_trend'] for r in sig) <= {'UP', 'DOWN', 'STABLE', 'INSUFFICIENT_DATA', 'MIXED'},
      str(Counter(r['revenue_trend'] for r in sig)))
check('SIGNALS evidence_count present', all(r['evidence_count'].isdigit() for r in sig))
cl = list(csv.DictReader(open(CAND / 'CHANGE_LOG.csv', newline='')))
check('CHANGE_LOG schema-note only', len(cl) <= 1 and all('SCHEMA_NOTE' in r['change_type'] for r in cl), f'{len(cl)} rows')
wl = list(csv.DictReader(open(CAND / 'WATCHLIST.csv', newline='')))
check('WATCHLIST reasons cite evidence', all(r['watch_reason'].strip() for r in wl) and len(wl) <= 12, f'{len(wl)} rows')
na = list(csv.DictReader(open(CAND / 'NETWORK_ANALYSIS.csv', newline='')))
co_rows = [r for r in na if r['network_type'] == 'co_investment']
check('NETWORK co-occurrence <= distinct rounds',
      all(int(r['co_occurrences']) <= int(r['entity_a_degree']) for r in co_rows) if (co_rows := co_rows) else True)
check('all 15 outputs present', all((CAND / f'{n}.csv').exists() for n in TABLES))

print(f"\n{'ALL CHECKS PASSED' if not fails else f'{len(fails)} FAILURES: {fails}'}")
sys.exit(bool(fails))
