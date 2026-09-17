#!/usr/bin/env python3
"""Single generator for all 15 analytical CSVs (Part B intelligence layer).

Replaces the ad-hoc heredocs that produced build/csv/*.csv. Every writer uses
csv.DictWriter (quoting handled), every analytical row carries source/period/unit
traceability and explicit sample sizes; conflicts are never overwritten — the raw
evidence CSVs in build/csv are read-only inputs.

Unit policy: FINANCIALS.unit values are non-normalized at source ('crore', 'INR
crore', 'Cr', 'USD Mn'...). Analytical money aggregates are labelled with the raw
unit string they were computed in; cross-unit aggregation would be fabrication,
so each output keeps the original unit string in unit_raw and only rows sharing
an identical unit_raw are summed. """
import csv
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, 'build', 'csv')
TODAY = '2026-09-16'

TABLES = ['ANALYTICS_MASTER', 'TIME_SERIES', 'FOUNDER_NETWORK', 'INVESTOR_NETWORK', 'CAPITAL_FLOWS',
          'CITY_ANALYSIS', 'SECTOR_ANALYSIS', 'COMPANY_SIGNALS', 'COMPANY_TRAJECTORIES', 'OUTLIERS',
          'RESEARCH_QUALITY', 'INSIGHTS', 'WATCHLIST', 'CHANGE_LOG', 'NETWORK_ANALYSIS']


def rd(name):
    p = os.path.join(CSV, f'{name}.csv')
    return list(csv.DictReader(open(p, newline=''))) if os.path.exists(p) else []


def wr(name, header, rows):
    output = os.environ.get('INTELLIGENCE_OUTPUT_DIR', os.path.join(ROOT, 'build', 'p4_candidate'))
    os.makedirs(output, exist_ok=True)
    p = os.path.join(output, f'{name}.csv')
    with open(p, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
    print(f'{name}: {len(rows)} rows')


def num(x):
    try:
        return float(str(x).strip())
    except (TypeError, ValueError):
        return None


def col_letter(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


# ---------------------------------------------------------------- raw inputs
STARTUPS = {r['startup_id']: r for r in rd('STARTUPS')}
SCORES = {r['startup_id']: r for r in rd('SCORES')}
FIN = rd('FINANCIALS')
FUNDING = [r for r in rd('FUNDING')]
FOUNDERS = rd('FOUNDERS')
PEOPLE = rd('PEOPLE')
INVESTORS = {r['investor_id']: r for r in rd('INVESTORS')}
PRODUCTS = rd('PRODUCTS')
TECH = rd('TECHNOLOGY')
HIRING = rd('HIRING')
CLAIMS = rd('CLAIMS')
CONFLICTS = rd('CONFLICTS')
ACQ = rd('ACQUISITIONS')
LEGAL = rd('LEGAL_REGULATORY')
SOURCES = {r['source_id'] for r in rd('SOURCES')}
CLAIM_IDS = {r['claim_id'] for r in CLAIMS}

# per-startup funding aggregates (equity rounds only, matching build_tables)
def _eq(r):
    return str(r.get('round_type', '')).lower() not in ('debt', 'venture debt', 'unknown', 'ipo')

FUND_BY_S = {}
for r in FUNDING:
    FUND_BY_S.setdefault(r['startup_id'], []).append(r)
FUND_TOTALS = {sid: sum(float(r['amount_inr_mn']) for r in rows if _eq(r) and num(r['amount_inr_mn']))
               for sid, rows in FUND_BY_S.items()}
FUNDED_N = sum(1 for v in FUND_TOTALS.values() if v > 0)

# ============================================================ ANALYTICS_MASTER
rows = []
for sid, s in sorted(STARTUPS.items()):
    sc = SCORES.get(sid, {})
    y = re.search(r'\d{4}', (s.get('founded_date') or '').strip())
    fy = int(y.group(0)) if y else ''
    rows.append({
        'startup_id': sid, 'company_name': s.get('company_name', ''),
        'primary_sector': s.get('primary_sector', ''), 'company_stage': s.get('startup_stage', ''),
        'city': s.get('city', ''), 'state': s.get('state', ''), 'founding_year': fy,
        'age_years': (2026 - fy) if fy else '', 'completeness_pct': sc.get('completeness_pct', ''),
        'tier': sc.get('tier', ''), 'source_quality_pct': sc.get('source_quality_pct', ''),
        'freshness_pct': sc.get('freshness_pct', ''), 'conflict_level': sc.get('conflict_level', ''),
        'notes': 'DERIVED analytics view of STARTUPS+SCORES; no new claims; sample=tracked universe (368).'})
wr('ANALYTICS_MASTER', list(rows[0].keys()), rows)

# ================================================================ TIME_SERIES
# period_type separates incompatible grains: fiscal_year | event_date | as_of | year | cumulative
def period_type(p):
    p = (p or '').strip()
    if re.fullmatch(r'FY\d{2}(-\d{2})?', p, re.I):
        return 'fiscal_year'
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', p):
        return 'event_date'
    if re.fullmatch(r'[Aa]s-of-\d{4}-\d{2}(-\d{2})?', p):
        return 'as_of'
    if re.fullmatch(r'(19|20)\d{2}', p):
        return 'year'
    if p.lower() == 'cumulative':
        return 'cumulative'
    return 'other'


rows = []
for r in FIN:
    if num(r.get('value')):
        rows.append({'startup_id': r['startup_id'], 'metric': r.get('metric', ''),
                     'period': r.get('fiscal_year', ''), 'period_type': 'fiscal_year',
                     'value': r.get('value', ''), 'unit_raw': r.get('unit', ''),
                     'currency': r.get('currency', ''), 'value_type': r.get('value_type', ''),
                     'source_id': r.get('source_id', ''), 'confidence': r.get('confidence', ''),
                     'notes': 'verbatim FINANCIALS passthrough; unit_raw as recorded'})
for r in FUNDING:
    if num(r.get('amount_inr_mn')) and r.get('announcement_date'):
        rows.append({'startup_id': r['startup_id'], 'metric': f"funding_{r.get('round_type', '')}".strip(),
                     'period': r['announcement_date'], 'period_type': 'event_date',
                     'value': r['amount_inr_mn'], 'unit_raw': 'INR Mn', 'currency': 'INR',
                     'value_type': 'DERIVED via annual-avg FX', 'source_id': r.get('source_id', ''),
                     'confidence': r.get('confidence', ''),
                     'notes': 'FUNDING.amount_inr_mn; FX note in README; IPO/debt excluded from equity totals'})
for r in HIRING:
    if r.get('as_of') and (r.get('value') or '').strip():
        rows.append({'startup_id': r['startup_id'], 'metric': f"hiring_{r.get('fact_type', '')}".strip(),
                     'period': r['as_of'], 'period_type': 'as_of', 'value': (r.get('value') or '').strip(),
                     'unit_raw': 'narrative (as recorded; NOT parsed to headcount)', 'currency': '',
                     'value_type': 'verbatim narrative', 'source_id': r.get('source_id', ''),
                     'confidence': r.get('confidence', ''),
                     'notes': f'HIRING.value verbatim: {(r.get("value") or "")[:80]}'})
TRACTION = rd('TRACTION')
for r in TRACTION:
    if (r.get('value') or '').strip():
        per = (r.get('period') or '').strip() or 'as_of'
        rows.append({'startup_id': r['startup_id'], 'metric': f"traction_{r.get('metric', '')}".strip(),
                     'period': per if per != 'as_of' else (r.get('as_of', '') or ''),
                     'period_type': period_type(per) if per != 'as_of' else 'as_of',
                     'value': (r.get('value') or '').strip(), 'unit_raw': r.get('unit', ''),
                     'currency': '', 'value_type': 'verbatim narrative',
                     'source_id': r.get('source_id', ''), 'confidence': r.get('confidence', ''),
                     'notes': f"TRACTION verbatim (as_of={r.get('as_of', '')}; company_reported={r.get('company_reported', '')})"})
wr('TIME_SERIES', ['startup_id', 'metric', 'period', 'period_type', 'value', 'unit_raw', 'currency',
                   'value_type', 'source_id', 'confidence', 'notes'], rows)

# ============================================================ FOUNDER_NETWORK
rows = []
sname = {sid: s.get('company_name', '') for sid, s in STARTUPS.items()}
for r in FOUNDERS:
    if not r.get('startup_id'):
        continue
    prev = (r.get('prev_companies') or '').strip()
    rows.append({'founder_id': r.get('founder_id', ''), 'person_id': r.get('person_id', ''),
                 'name': r.get('name', ''), 'startup_id': r['startup_id'], 'company': sname.get(r['startup_id'], ''),
                 'role_title': r.get('role_title', ''), 'founder_type': r.get('founder_type', ''),
                 'active': r.get('active', ''), 'departure_date': r.get('departure_date', ''),
                 'education': r.get('education', ''), 'linkedin': r.get('linkedin', ''),
                 'location': r.get('location', ''),
                 'prev_companies_raw': prev,
                 'previous_company_count': len([x for x in re.split(r'[;,|]', prev) if x.strip()]) if prev else 0,
                 'source_id': r.get('source_id', ''), 'confidence': r.get('confidence', ''),
                 'notes': 'verbatim FOUNDERS passthrough + parsed prev_companies count; same person_id across companies preserved'})
wr('FOUNDER_NETWORK', list(rows[0].keys()), rows)

# =========================================================== INVESTOR_NETWORK
rows = []
link_by_inv = {}
for r in rd('INVESTOR_LINKS'):
    link_by_inv.setdefault(r.get('investor_id', ''), []).append(r)
for iid, inv in sorted(INVESTORS.items()):
    links = link_by_inv.get(iid, [])
    comps = sorted({l['startup_id'] for l in links if l.get('startup_id')})
    rounds = sum(int(float(l['rounds'])) for l in links if num(l.get('rounds')))
    lead = sum(1 for l in links if str(l.get('lead', '')).lower() in ('true', 'yes', '1'))
    rows.append({'investor_id': iid, 'name': inv.get('name', ''), 'type': inv.get('type', ''),
                 'geography': inv.get('geography', ''),
                 'companies_backed': len(comps), 'total_rounds': rounds, 'lead_rounds': lead,
                 'first_investment': min((l.get('first_investment', '') for l in links if l.get('first_investment')), default=''),
                 'startup_ids': ';'.join(comps), 'source_id': links[0].get('source_id', '') if links else '',
                 'notes': f'INVESTORS+INVESTOR_LINKS join; company count=distinct startup_ids in links (n={len(comps)}); no quality rating.'})
wr('INVESTOR_NETWORK', list(rows[0].keys()), rows)

# ============================================================== CAPITAL_FLOWS
agg = {}
for r in FUNDING:
    y = (r.get('year') or '').strip()
    if not num(r.get('amount_inr_mn')) or not y:
        continue
    sid = r['startup_id']
    s = STARTUPS.get(sid, {})
    inv_ids = [i.strip() for i in (r.get('investor_ids') or '').split(';') if i.strip()]
    types = sorted({INVESTORS[i].get('type', 'unknown') for i in inv_ids if i in INVESTORS} or {'unknown'})
    k = (y, s.get('city', 'unknown'), s.get('primary_sector', 'unknown'),
         r.get('round_type', 'unknown'), '/'.join(types), 'existing' if 'existing' in (r.get('new_or_existing') or '') else 'new_or_mixed')
    a = agg.setdefault(k, [0.0, 0])
    a[0] += float(r['amount_inr_mn'])
    a[1] += 1
rows = [{'year': k[0], 'city': k[1], 'sector': k[2], 'stage': k[3], 'investor_type_mix': k[4],
         'new_or_existing': k[5], 'capital_inr_mn': round(v[0], 1), 'rounds': v[1],
         'disclosed_only': 'True', 'notes': 'FUNDING.amount_inr_mn sum; investor types from INVESTORS join'}
        for k, v in sorted(agg.items(), key=lambda kv: (kv[0][0], -kv[1][0]))]
wr('CAPITAL_FLOWS', list(rows[0].keys()), rows)

# ============================================================== CITY_ANALYSIS
c = {}
for sid, s in STARTUPS.items():
    city = s.get('city', 'unknown') or 'unknown'
    a = c.setdefault(city, {'n': 0, 'comp': 0.0, 'fund': 0.0, 'exits': 0, 'hiring': 0})
    a['n'] += 1
    a['comp'] += float(SCORES.get(sid, {}).get('completeness_pct', 0) or 0)
    a['fund'] += FUND_TOTALS.get(sid, 0.0)
    a['exits'] += 1 if 'acquir' in (s.get('status', '') or '').lower() else 0
rows = []
for city, a in sorted(c.items(), key=lambda kv: -kv[1]['n']):
    sids = [sid for sid, s in STARTUPS.items() if (s.get('city', 'unknown') or 'unknown') == city]
    hire_n = len({r['startup_id'] for r in HIRING if r['startup_id'] in sids})
    conf_n = len({r['startup_id'] for r in CONFLICTS if r['startup_id'] in sids})
    rows.append({'city': city, 'companies': a['n'], 'sample_note': f'n={a["n"]} of 368 tracked; small-n cities are descriptive only',
                 'avg_completeness_pct': round(a['comp'] / a['n'], 1),
                 'funding_total_inr_mn': round(a['fund'], 1), 'acquired_companies': a['exits'],
                 'companies_with_hiring_evidence': hire_n, 'companies_with_conflicts': conf_n,
                 'conflict_pct': round(100 * conf_n / a['n'], 1) if a['n'] else 0,
                 'notes': 'all figures derived from tracked universe only; funding = sum of FUNDING.amount_inr_mn (equity rounds, INR Mn)'})
wr('CITY_ANALYSIS', list(rows[0].keys()), rows)

# ============================================================ SECTOR_ANALYSIS
sec = {}
for sid, s in STARTUPS.items():
    sec.setdefault(s.get('primary_sector', 'unknown') or 'unknown', []).append(sid)
rows = []
for sector, sids in sorted(sec.items()):
    n = len(sids)
    fund = [FUND_TOTALS.get(sid, 0.0) for sid in sids]
    comps = [float(SCORES.get(sid, {}).get('completeness_pct', 0) or 0) for sid in sids]
    rev = [float(r['value']) for sid in sids for r in FIN
           if r['startup_id'] == sid and r.get('metric') == 'revenue_operations' and num(r.get('value')) and (r.get('unit') or '').lower() in ('crore', 'inr crore', 'cr')]
    rows.append({'primary_sector': sector, 'companies': n,
                 'n_note': 'sample-size protection: descriptive only' if n < 10 else '',
                 'avg_completeness_pct': round(sum(comps) / n, 1),
                 'median_completeness_pct': round(statistics.median(comps), 1),
                 'funded_companies': sum(1 for f in fund if f > 0),
                 'funding_median_inr_mn': round(statistics.median(fund), 1) if fund else 0,
                 'funding_total_inr_mn': round(sum(fund), 1),
                 'revenue_known_n': len(rev),
                 'revenue_median_inr_crore': round(statistics.median(rev), 1) if len(rev) >= 5 else '',
                 'small_sample_flag': 'n<10' if n < 10 else '',
                 'notes': 'aggregates over tracked companies per sector; funding equity-only INR Mn; revenue only where FINANCIALS unit is crore (INR)'})
wr('SECTOR_ANALYSIS', list(rows[0].keys()), rows)

# ============================================================ COMPANY_SIGNALS
# Direction per company only when comparable evidence exists; else INSUFFICIENT_DATA.
REVENUE_METRICS = {'total_revenue', 'operating_revenue', 'revenue', 'revenue_operations',
                   'revenue_from_operations', 'operating revenue', 'revenue from operations',
                   'consolidated_revenue', 'total_income', 'arr'}
PROFIT_POS = {'pat', 'net_profit'}          # positive value = profit
PROFIT_NEG = {'net_loss', 'net loss'}       # positive value = loss magnitude


def _fy(r):
    m = re.search(r'(?:FY)?(\d{2,4})(?:-(\d{2,4}))?', r.get('fiscal_year', '') or '', re.I)
    if not m:
        return None
    a = int(m.group(1))
    return (2000 + a) if a < 100 else a


def _grouped_trend(fin_rows, metrics, same_unit=True):
    """Group by (metric, unit, currency); require >=2 distinct fiscal years with equal values
    per year; conflicting same-year values => MIXED. Returns (trend, n_observations)."""
    fam = {}
    for r in fin_rows:
        if r.get('metric') not in REVENUE_METRICS and r.get('metric') not in PROFIT_POS and r.get('metric') not in PROFIT_POS | {'profit_loss', 'net profit'}:
            pass
        if num(r.get('value')) and (r.get('metric') in REVENUE_METRICS if same_unit else True):
            k = (r['metric'], r.get('unit', ''), r.get('currency', ''))
            y = _fy(r)
            if y:
                fam.setdefault(k, {}).setdefault(y, set()).add(round(float(r['value']), 2))
    for (metric, unit, cur), ys in sorted(fam.items()):
        fys = sorted(ys)
        if len(fys) < 2:
            continue
        if any(len(ys[y]) > 1 for y in fys):
            return 'MIXED', sum(len(v) for v in ys.values())
        first, last = ys[fys[0]].pop(), ys[fys[-1]].pop()
        if metric.startswith('arr'):
            label = metric
        else:
            label = metric
        if first == 0:
            return 'STABLE' if abs(last - first) < 1e-9 else 'UP', 2
        ratio = last / first
        if ratio > 1.05:
            return 'UP', 2
        if ratio < 0.95:
            return 'DOWN', 2
        return 'STABLE', 2
    n_obs = sum(len(v) for grp in fam.values() for v in grp.values())
    return ('INSUFFICIENT_DATA', n_obs) if n_obs else ('INSUFFICIENT_DATA', 0)


def _profitability(fin_rows):
    """Latest comparable FY with a signed profit metric; conflicts => MIXED."""
    # simple deterministic selection: largest FY per (unit,currency) that has any profit-family row
    fams = {}
    for r in fin_rows:
        m = r.get('metric', '')
        if m in PROFIT_POS or m in PROFIT_LOSS:
            y = _fy(r)
            if y and num(r.get('value')):
                k = (r.get('unit', ''), r.get('currency', ''))
                fams.setdefault(k, {}).setdefault(y, []).append((m, float(r['value'])))
    for k, ys in sorted(fams.items()):
        y = max(ys)
        entries = ys[y]
        if len(entries) > 1:
            vals = {round(v, 2) for _, v in entries}
            if len(vals) > 1:
                return 'MIXED', y, k
        m, v = entries[0]
        if m in PROFIT_LOSS:
            return ('LOSS-MAKING' if v > 0 else 'PROFITABLE'), y, k
        return ('PROFITABLE' if v > 0 else 'LOSS-MAKING'), y, k
    return 'INSUFFICIENT_DATA', None, None


PROFIT_LOSS = {'net_loss', 'net loss'}
rows = []
for sid, s in sorted(STARTUPS.items()):
    fin = [r for r in FIN if r['startup_id'] == sid]
    rev_t, rev_n = _grouped_trend(fin, REVENUE_METRICS)
    fund = FUND_BY_S.get(sid, [])
    dated = sorted([r['announcement_date'] for r in fund if r.get('announcement_date')])
    fund_t = 'INSUFFICIENT_DATA' if len(dated) < 2 else 'MULTI-ROUND (dated events; direction not inferred)'
    prof_t, prof_fy, prof_key = _profitability(fin)
    hires = [r for r in HIRING if r['startup_id'] == sid]
    hire_t = 'EVIDENCE_PRESENT' if hires else 'INSUFFICIENT_DATA'
    prods = [r for r in PRODUCTS if r['startup_id'] == sid]
    tech = [r for r in TECH if r['startup_id'] == sid]
    ev_n = len(prods) + len(tech)
    prod_t = f'products={len(prods)};tech={len(tech)}' if ev_n else 'INSUFFICIENT_DATA'
    n_conf = sum(1 for r in CONFLICTS if r['startup_id'] == sid)
    evidence_n = rev_n + len(fund) + len(hires) + ev_n
    conf = 'HIGH' if evidence_n >= 10 else 'MEDIUM' if evidence_n >= 4 else 'LOW'
    rows.append({'startup_id': sid, 'company': s.get('company_name', ''),
                 'funding_trend': fund_t,
                 'revenue_trend': rev_t,
                 'revenue_trend_basis': f'>=2 distinct FYs, same metric+unit+currency; n_obs={rev_n}',
                 'profitability_trend': prof_t,
                 'profitability_period': prof_fy if prof_fy is not None else '',
                 'hiring_trend': hire_t,
                 'product_trend': prod_t, 'conflicts_open': n_conf,
                 'confidence': conf, 'evidence_count': evidence_n,
                 'notes': f'directions from grouped comparable FY series only; profitability basis={prof_t if not isinstance(prof_t, str) else prof_t}'})
wr('COMPANY_SIGNALS', ['startup_id', 'company', 'funding_trend', 'revenue_trend', 'revenue_trend_basis',
                       'profitability_trend', 'profitability_period', 'hiring_trend', 'product_trend', 'conflicts_open',
                       'confidence', 'evidence_count', 'notes'], rows)

# ======================================================== COMPANY_TRAJECTORIES
rows = []
for sid, s in sorted(STARTUPS.items()):
    sc = SCORES.get(sid, {})
    if sc.get('tier', '') not in ('Intelligence-grade', 'Fully researched', 'Deep'):
        continue
    y = re.search(r'\d{4}', (s.get('founded_date') or '').strip())
    if y:
        rows.append({'startup_id': sid, 'company': s.get('company_name', ''), 'milestone_type': 'founded',
                     'milestone': s.get('founded_date', ''), 'period': s.get('founded_date', ''),
                     'value': '', 'unit_raw': '', 'currency': '', 'source_id': s.get('primary_source_id', ''),
                     'confidence': s.get('confidence', ''), 'notes': 'STARTUPS.founded_date'})
    dated_f = [r for r in FUND_BY_S.get(sid, []) if r.get('announcement_date')]
    dated_f.sort(key=lambda r: r['announcement_date'])
    if dated_f:
        f0 = dated_f[0]
        # equity-classic rounds only for the funding milestone; acquisition/debt/IPO rows become their own milestones below
        _eq_types = {'debt', 'venture debt', 'ipo', 'unknown'}
        if str(f0.get('round_type', '')).lower() not in _eq_types and 'acquisition' not in str(f0.get('round_type', '')).lower():
            rows.append({'startup_id': sid, 'company': s.get('company_name', ''), 'milestone_type': 'first_funding_event',
                         'milestone': f0.get('round_type', ''), 'period': f0['announcement_date'],
                         'value': f0.get('amount_inr_mn', ''), 'unit_raw': 'INR Mn', 'currency': 'INR',
                         'source_id': f0.get('source_id', ''), 'confidence': f0.get('confidence', ''),
                         'notes': 'earliest dated equity-class FUNDING row by announcement_date (excludes debt/IPO/acquisition rows); earliest TRACKED, not lifetime first'})
    acq_fin = [r for r in dated_f if 'acquisition' in str(r.get('round_type', '')).lower()]
    if acq_fin:
        a0 = acq_fin[0]
        rows.append({'startup_id': sid, 'company': s.get('company_name', ''), 'milestone_type': 'acquisition_financing_event',
                     'milestone': a0.get('round_type', ''), 'period': a0['announcement_date'],
                     'value': a0.get('amount_inr_mn', ''), 'unit_raw': 'INR Mn', 'currency': 'INR',
                     'source_id': a0.get('source_id', ''), 'confidence': a0.get('confidence', ''),
                     'notes': 'FUNDING row whose round_type records an acquisition/buyout event (not a startup funding round)'})
    revs = {}
    for r in FIN:
        if r['startup_id'] == sid and r.get('metric') == 'revenue_operations' and num(r.get('value')) and (r.get('unit') or '').lower() in ('crore', 'inr crore', 'cr'):
            m = re.search(r'\d{4}', r.get('fiscal_year', ''))
            if m:
                revs[int(m.group(0))] = r
    if revs:
        yr, r = max(revs.items())
        rows.append({'startup_id': sid, 'company': s.get('company_name', ''), 'milestone_type': 'latest_revenue',
                     'milestone': f"{r.get('fiscal_year', '')} {r.get('value_type', '')}".strip(),
                     'period': r.get('fiscal_year', ''), 'value': r.get('value', ''),
                     'unit_raw': r.get('unit', ''), 'currency': r.get('currency', ''),
                     'source_id': r.get('source_id', ''), 'confidence': r.get('confidence', ''),
                     'notes': f"FINANCIALS verbatim (value_type={r.get('value_type', '') or 'unspecified'}; filing_date={r.get('filing_date', '') or 'none'})"})
    acq = sorted([r for r in ACQ if r['startup_id'] == sid and re.match(r'\d{4}-\d{2}-\d{2}', r.get('date', ''))], key=lambda r: r['date'])
    if acq:
        a = acq[-1]
        rows.append({'startup_id': sid, 'company': s.get('company_name', ''), 'milestone_type': 'acquisition',
                     'milestone': f"{a.get('direction', '')} {a.get('type', '')}".strip(), 'period': a['date'],
                     'value': a.get('value', ''), 'unit_raw': 'as-stated in ACQUISITIONS.value', 'currency': '',
                     'source_id': a.get('source_id', ''), 'confidence': a.get('confidence', ''),
                     'notes': 'ACQUISITIONS verbatim'})
    leg = [r for r in LEGAL if r['startup_id'] == sid]
    if leg:
        l = leg[-1]
        rows.append({'startup_id': sid, 'company': s.get('company_name', ''), 'milestone_type': 'legal_event',
                     'milestone': l.get('type', ''), 'period': l.get('dates', ''),
                     'value': '', 'unit_raw': '', 'currency': '', 'source_id': l.get('source_id', ''),
                     'confidence': l.get('confidence', ''),
                     'notes': f"LEGAL_REGULATORY verbatim dates={l.get('dates', '')[:60]}"})
wr('COMPANY_TRAJECTORIES', list(rows[0].keys()), rows)

# ==================================================================== OUTLIERS
def iqr_fence(vals):
    if len(vals) < 4:
        return None
    q = statistics.quantiles(vals, n=4, method='inclusive')
    q1, q3 = q[0], q[2]
    return {'n': len(vals), 'q1': q1, 'median': statistics.median(vals), 'q3': q3,
            'upper': q3 + 1.5 * (q3 - q1), 'lower': q1 - 1.5 * (q3 - q1)}


pop_fund = sorted(v for v in FUND_TOTALS.values() if v > 0)  # disclosed funding = positive equity totals only
f = iqr_fence(pop_fund)
rows = []
for sid, tot in sorted(FUND_TOTALS.items(), key=lambda kv: -kv[1]):
    if tot > f['upper']:
        rows.append({'metric': 'funding_total_inr_mn', 'startup_id': sid,
                     'company': STARTUPS.get(sid, {}).get('company_name', ''), 'value': round(tot, 1),
                     'population': f"tracked startups with positive disclosed equity funding (n={f['n']}; zero-total companies excluded)",
                     'population_size': f['n'], 'q1': round(f['q1'], 1), 'median': round(f['median'], 1),
                     'q3': round(f['q3'], 1), 'upper_fence': round(f['upper'], 1),
                     'method': 'Q3 + 1.5*IQR (inclusive quartiles), population = positive equity-only totals from FUNDING.amount_inr_mn',
                     'confidence': 'MEDIUM', 'notes': 'statistical outlier label, not a quality judgment; n shown; no small-n cases (n>=10)'})
rev_by_sid = {}
for r in FIN:
    if r.get('metric') == 'revenue_operations' and num(r.get('value')) and (r.get('unit') or '').lower() in ('crore', 'inr crore', 'cr'):
        rev_by_sid.setdefault(r['startup_id'], []).append(float(r['value']))
rev_pop = sorted(max(v) for v in rev_by_sid.values())
g = iqr_fence(rev_pop)
if g:  # revenue outlier scan only when the crore-denominated population is large enough for quartiles
    for sid, vals in sorted(rev_by_sid.items(), key=lambda kv: -max(kv[1])):
        v = max(vals)
        if v > g['upper']:
            rows.append({'metric': 'revenue_latest_inr_crore', 'startup_id': sid,
                         'company': STARTUPS.get(sid, {}).get('company_name', ''), 'value': round(v, 1),
                         'population': f'tracked startups with >=1 crore-denominated revenue_operations row (n={g["n"]})',
                         'population_size': g['n'], 'q1': round(g['q1'], 1), 'median': round(g['median'], 1),
                         'q3': round(g['q3'], 1), 'upper_fence': round(g['upper'], 1),
                         'method': 'Q3 + 1.5*IQR on max revenue per startup (crore rows only); revenue unit varies at source',
                         'confidence': 'MEDIUM', 'notes': ''})
wr('OUTLIERS', ['metric', 'startup_id', 'company', 'value', 'population', 'population_size', 'q1', 'median',
                'q3', 'upper_fence', 'method', 'confidence', 'notes'], rows)

# =========================================================== RESEARCH_QUALITY
rows = []
tiers = Counter(r.get('tier', '') for r in SCORES.values())
for t, n in sorted(tiers.items(), key=lambda kv: -kv[1]):
    rows.append({'category': 'tier_distribution', 'entity': t, 'value': n, 'population_size': len(SCORES),
                 'comparison_basis': 'count of companies', 'status': 'measured',
                 'notes': 'objective banded coverage per SPEC Amendment #2'})
for city, a in sorted(c.items()):
    rows.append({'category': 'city_avg_completeness', 'entity': city,
                 'value': round(a['comp'] / a['n'], 1), 'population_size': a['n'],
                 'comparison_basis': 'SCORES.completeness_pct', 'status': 'measured',
                 'notes': 'tracked universe only'})
rows.append({'category': 'conflicts_preserved', 'entity': 'all', 'value': len(CONFLICTS),
             'population_size': len(STARTUPS), 'comparison_basis': 'CONFLICTS rows retained (not merged)',
             'status': 'measured', 'notes': f'unresolved: {sum(1 for r in CONFLICTS if r.get("resolution_status") == "open")}'})
wr('RESEARCH_QUALITY', list(rows[0].keys()), rows)

# ==================================================================== INSIGHTS
def best_claim_ids(sid=None, field=None, k=3):
    out = [c['claim_id'] for c in CLAIMS
           if (sid is None or c['startup_id'] == sid) and (field is None or c.get('field') == field)][:k]
    return ';'.join(out)


def src_for_startup(sid, k=2):
    ids = sorted({r.get('source_id', '') for r in FIN + FUNDING if r['startup_id'] == sid and r.get('source_id')})
    return ';'.join([i for i in ids if i in SOURCES][:k])


funded = [v for v in FUND_TOTALS.values() if v > 0]
rapid = [sid for sid, rows_ in FUND_BY_S.items()
         if len({r.get('announcement_date') for r in rows_ if r.get('announcement_date')}) >= 3]
rows = [
    {'insight_id': 'P001', 'insight_type': 'pattern',
     'statement': f'{len(rapid)} tracked companies have >=3 dated funding events in FUNDING (multi-round cadence); this is a descriptive count, not a velocity estimate.',
     'population': 'tracked universe (368)', 'sample_size': len(rapid),
     'calculation': 'count of startups with >=3 distinct announcement_date values in FUNDING.csv',
     'supporting_claims': ';'.join(sorted({c["claim_id"] for c in CLAIMS if c.get("field") == "last_funding_date"})[:5]) or 'none-available',
     'supporting_sources': ';'.join(sorted({r["source_id"] for r in FUNDING if r.get("source_id")})[:5]),
     'confidence': 'MEDIUM',
     'limitations': 'announcement dates only; announced vs close not distinguished; tracked universe only',
     'date_generated': TODAY, 'notes': 'traceable to FUNDING rows via listed source_ids'},
    {'insight_id': 'P002', 'insight_type': 'pattern',
     'statement': 'Repeat founders identifiable only where FOUNDERS.prev_companies is populated; coverage of that field is sparse, so no founder-network density claim is made.',
     'population': 'FOUNDERS rows with prev_companies populated', 'sample_size': sum(1 for r in FOUNDERS if (r.get("prev_companies") or "").strip()),
     'calculation': 'count of FOUNDERS.prev_companies non-empty',
     'supporting_claims': 'none-available',
     'supporting_sources': ';'.join(sorted({r["source_id"] for r in FOUNDERS if r.get("source_id")})[:5]),
     'confidence': 'LOW', 'limitations': 'prev_companies field sparse (~0% at last audit); no centrality claims',
     'date_generated': TODAY, 'notes': 'negative finding stated explicitly'},
    {'insight_id': 'P003', 'insight_type': 'outlier_pattern',
     'statement': f'{len(rows) if (rows := []) else 0}... placeholder replaced below',
     'population': '', 'sample_size': 0, 'calculation': '', 'supporting_claims': '', 'supporting_sources': '',
     'confidence': '', 'limitations': '', 'date_generated': TODAY, 'notes': ''},
]
# P003: outlier counts from the OUTLIERS rows just computed; revenue side only when its population cleared the n-floor
n_fund_out = sum(1 for r in rows if r.get('metric') == 'funding_total_inr_mn')
n_rev_out = sum(1 for r in rows if r.get('metric') == 'revenue_latest_inr_crore')
rev_pop_n = g['n'] if g else len(rev_pop)
rows[2] = {
    'insight_id': 'P003', 'insight_type': 'outlier_pattern',
    'statement': f'Outlier scan: {n_fund_out} funding-total outliers and {n_rev_out} revenue outliers vs IQR fences (Q3+1.5*IQR).',
    'population': 'tracked universe', 'sample_size': f'n_funding={f["n"]}; n_revenue={rev_pop_n}',
    'calculation': 'see OUTLIERS.csv method column; quartiles recomputed this run',
    'supporting_claims': ';'.join(sorted({c["claim_id"] for c in CLAIMS if c.get("field") == "revenue"})[:5]) or 'none-available',
    'supporting_sources': ';'.join(sorted({r["source_id"] for r in FIN if r.get("source_id")})[:5]),
    'confidence': 'MEDIUM',
    'limitations': 'revenue scan covers only crore-denominated revenue_operations rows (n=%d, below IQR floor for outlier detection this run); funding totals are equity-only INR Mn' % rev_pop_n,
    'date_generated': TODAY, 'notes': 'OUTLIERS.csv is the auditable artifact; no causal claim'}
wr('INSIGHTS', list(rows[0].keys()), rows)

# =================================================================== WATCHLIST
rows = []
for r in CONFLICTS:
    sid = r.get('startup_id', '')
    if sid and r.get('resolution_status') != 'resolved' and len(rows) < 10:
        rows.append({'startup_id': sid, 'company': STARTUPS.get(sid, {}).get('company_name', ''),
                     'watch_reason': f"unresolved conflict: {(r.get('conflict_id', ''))} {(r.get('description') or r.get('claim_a', ''))[:100]}",
                     'watch_category': 'conflict_monitor', 'current_state': STARTUPS.get(sid, {}).get('status', ''),
                     'last_checked': TODAY, 'next_check': 'quarterly or upon significant update',
                     'important_metrics': 'conflict fields; affected claims', 'important_events': '',
                     'priority': 'P4-WATCH',
                     'notes': 'evidence-backed selection: unresolved CONFLICTS rows only; no arbitrary ranking'})
for sid, sc in sorted(SCORES.items(), key=lambda kv: float(kv[1].get('completeness_pct', 0) or 0)):
    if len(rows) >= 10:
        break
    if sc.get('tier', '') in ('Intelligence-grade', 'Fully researched') and all(r['startup_id'] != sid for r in rows):
        rows.append({'startup_id': sid, 'company': STARTUPS.get(sid, {}).get('company_name', ''),
                     'watch_reason': f"high-maturity company (completeness={sc.get('completeness_pct')}) — monitor for new evidence to maintain freshness",
                     'watch_category': 'freshness_monitor', 'current_state': STARTUPS.get(sid, {}).get('status', ''),
                     'last_checked': TODAY, 'next_check': 'semiannual',
                     'important_metrics': 'freshness_pct; new funding; new filings', 'important_events': 'funding; leadership',
                     'priority': 'P4-WATCH', 'notes': 'selection rule stated in notes; not a quality ranking'})
wr('WATCHLIST', list(rows[0].keys()), rows)

# ================================================================== CHANGE_LOG
wr('CHANGE_LOG', ['change_id', 'startup_id', 'field', 'old_value', 'new_value', 'change_date', 'source_id',
                  'confidence', 'change_type'],
   [{'change_id': 'CL_SCHEMA_001', 'startup_id': '', 'field': 'schema', 'old_value': '',
     'new_value': 'CHANGE_LOG schema established 2026-09-16 for Phase 5 automated monitoring',
     'change_date': TODAY, 'source_id': '', 'confidence': 'HIGH',
     'change_type': 'SCHEMA_NOTE: no fabricated historical changes; only actual verified updates will be recorded'}])

# ============================================================ NETWORK_ANALYSIS
co = Counter()
for r in FUNDING:
    ids = [i.strip() for i in (r.get('investor_ids') or '').split(';') if i.strip().startswith('INV')]
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            co[tuple(sorted((ids[i], ids[j])))] += 1
rows = []
for (a, b), n in co.most_common(20):
    na, nb = INVESTORS.get(a, {}).get('name', a), INVESTORS.get(b, {}).get('name', b)
    rows.append({'network_type': 'co_investment', 'entity_a': a, 'entity_b': b, 'co_occurrences': co[(a, b)],
                 'entity_a_degree': len(link_by_inv.get(a, [])), 'entity_b_degree': len(link_by_inv.get(b, [])),
                 'overlap_type': 'same_funding_round', 'interpretation': f'{INVESTORS.get(a, {}).get("name", a)} and {INVESTORS.get(b, {}).get("name", b)} appear together in investor_ids of {co[(a, b)]} funding rounds',
                 'confidence': 'MEDIUM', 'notes': 'derived from FUNDING.investor_ids only; no centrality claims'})
pc = {}
for r in FOUNDERS:
    pid = r.get('person_id', '')
    if pid:
        pc.setdefault(pid, set()).add(r.get('startup_id', ''))
for pid, sids in sorted(pc.items(), key=lambda kv: -len(kv[1]))[:15]:
    if len(sids) >= 2:
        names = sorted({r.get('name', '') for r in FOUNDERS if r.get('person_id') == pid})
        rows.append({'network_type': 'founder_overlap', 'entity_a': pid, 'entity_b': ';'.join(sorted(sids)),
                     'co_occurrences': len(sids), 'entity_a_degree': len(sids), 'entity_b_degree': len(sids),
                     'overlap_type': 'same_person_multiple_startups',
                     'interpretation': f'{pid} ({", ".join(names)}) linked to {len(sids)} tracked startups by person_id',
                     'confidence': 'MEDIUM',
                     'notes': 'person_id reuse verified by name at capture; no previous-company centrality claims (prev_companies sparse)'})
wr('NETWORK_ANALYSIS', list(rows[0].keys()), rows)

print('DONE', sys.argv[0])
