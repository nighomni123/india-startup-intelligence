#!/usr/bin/env python3
"""Minimal regression check for the three Phase 4 CSV alignment failures."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'build' / 'csv'


def check():
    for name in ('SECTOR_ANALYSIS', 'OUTLIERS', 'INSIGHTS'):
        with (ROOT / f'{name}.csv').open(newline='') as f:
            rows = list(csv.reader(f))
        width = len(rows[0])
        bad = [(i, len(row)) for i, row in enumerate(rows, 1) if len(row) != width]
        assert not bad, f'{name}: header={width}; bad rows={bad[:5]}'
        print(f'{name}: PASS ({len(rows)-1} data rows, {width} columns)')
        if name == 'OUTLIERS':
            assert rows[0][-1] == 'notes'
        if name == 'INSIGHTS':
            p003 = next(dict(zip(rows[0], row)) for row in rows[1:] if row[0] == 'P003')
            assert p003['supporting_entities'] == ''
            assert p003['confidence'] == 'MEDIUM'
            assert p003['date_generated'] == '2026-09-16'
    print('Structural alignment only; analytical correctness is not certified.')


if __name__ == '__main__':
    check()
