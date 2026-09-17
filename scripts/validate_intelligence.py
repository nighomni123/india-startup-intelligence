#!/usr/bin/env python3
"""Read-only XLSX/CSV integrity checks. No spreadsheet-writing dependency required."""
import csv
import json
import re
from datetime import date, timedelta
import posixpath
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
M = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
SHEETS = 'ANALYTICS_MASTER TIME_SERIES FOUNDER_NETWORK INVESTOR_NETWORK CAPITAL_FLOWS CITY_ANALYSIS SECTOR_ANALYSIS COMPANY_SIGNALS COMPANY_TRAJECTORIES OUTLIERS RESEARCH_QUALITY INSIGHTS WATCHLIST CHANGE_LOG NETWORK_ANALYSIS'.split()


def target_path(parent, target):
    return target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.dirname(parent) + '/' + target)


def check(path, csv_dir=None):
    csv_dir = Path(csv_dir) if csv_dir else ROOT / 'build/csv'
    errors, stats = [], {}
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None, 'ZIP CRC failure'
        rel = {e.get('Id'): e.get('Target') for e in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            shared = [''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        styles = ET.fromstring(z.read('xl/styles.xml'))
        custom_formats = {int(e.get('numFmtId')): e.get('formatCode', '') for e in styles.iter(M + 'numFmt')}
        cell_styles = list(styles.find(M + 'cellXfs'))
        workbook = ET.fromstring(z.read('xl/workbook.xml'))
        props = workbook.find(M + 'workbookPr')
        epoch = date(1904, 1, 1) if props is not None and props.get('date1904') in ('1', 'true') else date(1899, 12, 30)
        sheets = {}
        for s in ET.fromstring(z.read('xl/workbook.xml')).iter(M + 'sheet'):
            p = target_path('xl/workbook.xml', rel[s.get(R + 'id')])
            sheets[s.get('name')] = (p, ET.fromstring(z.read(p)))
        for name in SHEETS:
            if name not in sheets:
                errors.append(f'{name}: missing sheet')
                continue
            p, x = sheets[name]
            cells = {c.get('r'): c for c in x.iter(M + 'c')}

            def value(c):
                if c is None:
                    return ''
                if c.get('t') == 'inlineStr':
                    return ''.join(t.text or '' for t in c.iter(M + 't'))
                v = c.findtext(M + 'v', '')
                return shared[int(v)] if c.get('t') == 's' and v else v

            with (csv_dir / (name + '.csv')).open(newline='') as f:
                csv_rows = list(csv.reader(f))
            count = sum(bool(value(c)) for ref, c in cells.items() if ref.startswith('A') and ref[1:].isdigit() and int(ref[1:]) > 1)
            stats[name] = {'csv_rows': len(csv_rows) - 1, 'xlsx_rows': count, 'tables': len(list(x.iter(M + 'tablePart')))}
            if count != len(csv_rows) - 1:
                errors.append(f'{name}: XLSX/CSV count mismatch {count}/{len(csv_rows)-1}')
            if stats[name]['tables'] != 1:
                errors.append(f'{name}: expected one Excel table')
            for i, expected in enumerate(csv_rows, 1):
                if len(expected) != len(csv_rows[0]):
                    errors.append(f'{name}:{i}: malformed CSV width')
                # All values, not only row presence; allow Excel numeric canonicalization.
                for j, want in enumerate(expected, 1):
                    n, col = j, ''
                    while n:
                        n, rem = divmod(n-1, 26)
                        col = chr(65 + rem) + col
                    got = value(cells.get(f'{col}{i}'))
                    if got != want:
                        try:
                            equal = float(got) == float(want)
                        except ValueError:
                            equal = False
                        if not equal:
                            errors.append(f'{name}!{col}{i}: CSV/XLSX differs: {want[:70]!r} != {got[:70]!r}')
        formula_errors = []
        for name, (_, x) in sheets.items():
            for c in x.iter(M + 'c'):
                if c.get('t') == 'e':
                    formula_errors.append(f'{name}!{c.get("r")}: {c.findtext(M + "v", "")}')
        errors.extend(formula_errors)
        result = {'workbook': str(path), 'sheet_count': len(sheets), 'table_count': sum(n.startswith('xl/tables/') and n.endswith('.xml') for n in z.namelist()), 'sheets': stats, 'errors': errors, 'scope': 'Structural and full CSV parity checks only; does not certify analytical meaning or source truth.'}
    return result


if __name__ == '__main__':
    result = check(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'india-startup-intelligence.xlsx')
    print(json.dumps(result, indent=2))
    sys.exit(bool(result['errors']))
