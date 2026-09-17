#!/usr/bin/env python3
"""scripts/dashboard_extend.py — append intelligence-layer sections to DASHBOARD sheet."""
import os, json, subprocess
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = os.environ.get('OUT_XLSX') or f"{BASE}/india-startup-intelligence.xlsx"
ENV = dict(os.environ, OFFICECLI_RESIDENT_FLUSH="each")

def cli(*args, inp=None):
    p = subprocess.run(["officecli", *args], capture_output=True, text=True, input=inp, env=ENV)
    try:
        out = json.loads(p.stdout)
    except Exception:
        out = {"raw": p.stdout[:200], "stderr": p.stderr[:200]}
    ok = (p.returncode == 0) and (out.get("success", out.get("ok", True)) not in (False,))
    if not ok:
        with open(f"{BASE}/qc/dashboard_extend_errors.log", "a") as log_f:
            log_f.write(str(args) + " -> " + str(out)[:300] + "\n")
    return out

cmds = [
    {"command":"set","path":"/DASHBOARD/A115","props":{"value":"INTELLIGENCE LAYER — Phase 4 (2026-09-16)","font.bold":"true","font.size":"14","fill":"#1F4E79","font.color":"#FFFFFF"}},
    {"command":"set","path":"/DASHBOARD/A117","props":{"value":"ECO-SYSTEM: tracked companies (ANALYTICS_MASTER live count)","font.bold":"true","fill":"#DDEBF7"}},
    {"command":"set","path":"/DASHBOARD/B117","props":{"formula":"=COUNTA(ANALYTICS_MASTER!A2:A400)","numberformat":"0","font.size":"12","fill":"#F2F2F2"}},
    {"command":"set","path":"/DASHBOARD/A118","props":{"value":"Deep or better (SCORES live)","font.bold":"true","fill":"#DDEBF7"}},
    {"command":"set","path":"/DASHBOARD/B118","props":{"formula":"=COUNTIF(SCORES!$O$2:$O$600,\"Fully researched\")+COUNTIF(SCORES!$O$2:$O$600,\"Intelligence-grade\")+COUNTIF(SCORES!$O$2:$O$600,\"Deep\")","numberformat":"0","font.size":"12","fill":"#F2F2F2"}},
    {"command":"set","path":"/DASHBOARD/A119","props":{"value":"DERIVED_METRICS rows (DERIVED ratios live)","font.bold":"true","fill":"#DDEBF7"}},
    {"command":"set","path":"/DASHBOARD/B119","props":{"formula":"=COUNTA(DERIVED_METRICS!A2:A500)","numberformat":"0","font.size":"12","fill":"#F2F2F2"}},
    {"command":"set","path":"/DASHBOARD/A121","props":{"value":"CAPITAL: funding rounds (FUNDING live count)","font.bold":"true","fill":"#DDEBF7"}},
    {"command":"set","path":"/DASHBOARD/B121","props":{"formula":"=COUNTA(FUNDING!A2:A2000)","numberformat":"0","font.size":"12","fill":"#F2F2F2"}},
    {"command":"set","path":"/DASHBOARD/A122","props":{"value":"Capital-flow rows (derived, period-tagged)","font.bold":"true","fill":"#DDEBF7"}},
    {"command":"set","path":"/DASHBOARD/B122","props":{"formula":"=COUNTA(CAPITAL_FLOWS!A2:A2000)","numberformat":"0","font.size":"12","fill":"#F2F2F2"}},
    {"command":"set","path":"/DASHBOARD/A124","props":{"value":"NETWORKS: founder-network entries","font.bold":"true","fill":"#DDEBF7"}},
    {"command":"set","path":"/DASHBOARD/B124","props":{"formula":"=COUNTA(FOUNDER_NETWORK!A2:A1000)","numberformat":"0","font.size":"12","fill":"#F2F2F2"}},
    {"command":"set","path":"/DASHBOARD/A125","props":{"value":"Investor-network (co-investment pairs; evidence-backed)","font.bold":"true","fill":"#DDEBF7"}},
    {"command":"set","path":"/DASHBOARD/B125","props":{"formula":"=COUNTA(INVESTOR_NETWORK!A2:A2000)","numberformat":"0","font.size":"12","fill":"#F2F2F2"}},
    {"command":"set","path":"/DASHBOARD/A127","props":{"value":"SIGNALS: company signal records (evidence-backed; not predictions)","font.bold":"true","fill":"#DDEBF7"}},
    {"command":"set","path":"/DASHBOARD/B127","props":{"formula":"=COUNTA(COMPANY_SIGNALS!A2:A500)","numberformat":"0","font.size":"12","fill":"#F2F2F2"}},
    {"command":"set","path":"/DASHBOARD/A128","props":{"value":"Signals confidence HIGH (derived from CSV evidence counts)","font.bold":"true","fill":"#DDEBF7"}},
    {"command":"set","path":"/DASHBOARD/B128","props":{"formula":"=COUNTIF(COMPANY_SIGNALS!$I$2:$I$500,\"HIGH\")","numberformat":"0","font.size":"12","fill":"#F2F2F2"}},
    {"command":"set","path":"/DASHBOARD/A130","props":{"value":"INSIGHTS: evidence-backed patterns and outliers","font.bold":"true","fill":"#DDEBF7"}},
    {"command":"set","path":"/DASHBOARD/B130","props":{"formula":"=COUNTA(INSIGHTS!A2:A200)","numberformat":"0","font.size":"12","fill":"#F2F2F2"}},
    {"command":"set","path":"/DASHBOARD/A131","props":{"value":"OUTLIERS detected (explicit comparison groups)","font.bold":"true","fill":"#DDEBF7"}},
    {"command":"set","path":"/DASHBOARD/B131","props":{"formula":"=COUNTA(OUTLIERS!A2:A200)","numberformat":"0","font.size":"12","fill":"#F2F2F2"}},
    {"command":"set","path":"/DASHBOARD/A133","props":{"value":"WATCHLIST: evidence-backed monitored companies","font.bold":"true","fill":"#DDEBF7"}},
    {"command":"set","path":"/DASHBOARD/B133","props":{"formula":"=COUNTA(WATCHLIST!A2:A200)","numberformat":"0","font.size":"12","fill":"#F2F2F2"}},
    {"command":"set","path":"/DASHBOARD/A135","props":{"value":"CHANGE_LOG: Phase 5 monitoring schema (only verified updates)","font.bold":"true","fill":"#DDEBF7"}},
    {"command":"set","path":"/DASHBOARD/B135","props":{"formula":"=COUNTA(CHANGE_LOG!A2:A200)","numberformat":"0","font.size":"12","fill":"#F2F2F2"}},
    {"command":"set","path":"/DASHBOARD/A137","props":{"value":"CAVEATS: tracked universe only (not census) · ratios computed from CSV · DERIVED fields marked · conflicts preserved · no arbitrary best-company ranking · no predictions · all derived ratios show periods + inputs · previous-company/founder-investor overlap honest · sample-sizes shown · no unverified inferences · no universe inflation · no fabricated historical changes · WATCHLIST evidence-backed · INSIGHTS traceable to claims · OUTLIERS use explicit comparison groups (IQR + 1.5*IQR) · NETWORK_ANALYSIS derived only from FUNDING co-investor strings + FOUNDERS (prev_companies sparse); no centrality claims.","font.size":"10","alignment":"wrapText","fill":"#FFE5B4","font.italic":"true"}}
]
cli("batch", XSLX, "--commands", json.dumps(cmds), "--json")
print('Dashboard extension applied.')
