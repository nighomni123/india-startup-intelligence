#!/usr/bin/env python3
"""scripts/load_intelligence.py — import analytical CSVs into india-startup-intelligence.xlsx (Part B)."""
import json, os, sys, subprocess
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = f"{BASE}/india-startup-intelligence.xlsx"
OUT_DRY = os.environ.get("OUT_XLSX") or XLSX
ENV = dict(os.environ, OFFICECLI_RESIDENT_FLUSH="each")

def cli(*args, inp=None, check=False):
    p = subprocess.run(["officecli", *args], capture_output=True, text=True, input=inp, env=ENV)
    try:
        out = json.loads(p.stdout)
    except Exception:
        out = {"raw": p.stdout[:200], "stderr": p.stderr[:200]}
    ok = (p.returncode == 0) and (out.get("success", out.get("ok", True)) not in (False,))
    if not ok and check:
        print(f"FAIL: officecli {' '.join(args[:4])} -> {str(out)[:200]}", file=sys.stderr)
    return out

# List of new sheets/csv pairs (exclude READ, raw data)
SHEETS = [
    ("ANALYTICS_MASTER", f"{BASE}/build/csv/ANALYTICS_MASTER.csv"),
    ("TIME_SERIES", f"{BASE}/build/csv/TIME_SERIES.csv"),
    ("FOUNDER_NETWORK", f"{BASE}/build/csv/FOUNDER_NETWORK.csv"),
    ("INVESTOR_NETWORK", f"{BASE}/build/csv/INVESTOR_NETWORK.csv"),
    ("CAPITAL_FLOWS", f"{BASE}/build/csv/CAPITAL_FLOWS.csv"),
    ("CITY_ANALYSIS", f"{BASE}/build/csv/CITY_ANALYSIS.csv"),
    ("SECTOR_ANALYSIS", f"{BASE}/build/csv/SECTOR_ANALYSIS.csv"),
    ("COMPANY_SIGNALS", f"{BASE}/build/csv/COMPANY_SIGNALS.csv"),
    ("COMPANY_TRAJECTORIES", f"{BASE}/build/csv/COMPANY_TRAJECTORIES.csv"),
    ("OUTLIERS", f"{BASE}/build/csv/OUTLIERS.csv"),
    ("RESEARCH_QUALITY", f"{BASE}/build/csv/RESEARCH_QUALITY.csv"),
    ("WATCHLIST", f"{BASE}/build/csv/WATCHLIST.csv"),
    ("CHANGE_LOG", f"{BASE}/build/csv/CHANGE_LOG.csv"),
    ("INSIGHTS", f"{BASE}/build/csv/INSIGHTS.csv"),
    ("NETWORK_ANALYSIS", f"{BASE}/build/csv/NETWORK_ANALYSIS.csv"),
]

def add_and_import(name, csv_path):
    # add sheet
    cli("add", OUT_DRY, "/", "--type", "sheet", "--prop", f"name={name}", "--json")
    # import csv (header row treated as header, columns mapped by header)
    cli("import", OUT_DRY, f"/{name}", "--file", csv_path, "--header", "--json")
    # freeze first row
    cli("batch", OUT_DRY, "--commands", json.dumps([
        {"command":"freeze","path":f"/{name}/A2"},
        {"command":"set","path":f"/{name}/A1","props":{"font.bold":"true","font.size":"12","fill":"#DDEBF7"}}
    ]), "--json")

print('Starting import to', OUT_DRY)
for name, csv_path in SHEETS:
    print('Importing', name)
    add_and_import(name, csv_path)

print('Import complete.')
