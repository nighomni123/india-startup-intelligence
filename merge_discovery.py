#!/usr/bin/env python3
"""merge_discovery.py — normalize + dedupe discovery JSONs into a candidate universe
with stable startup_ids and research-priority scores. Outputs:
  structured/universe.json  (authoritative candidate list, id-anchored)
  structured/universe.csv   (human-readable)
  structured/conflicts.md   (dedupe log: what merged into what, on what evidence)
Usage: python3 merge_discovery.py <discovery_dir> <out_dir>
"""
import json, csv, re, sys, math, glob, os
from collections import defaultdict

LEGAL_SUFFIX = re.compile(r"\b(pvt|private|limited|ltd|llp|inc|co|corp|corporation)\b\.?", re.I)
CITY_MAP = {
 "mumbai": "Mumbai", "bombay": "Mumbai", "navi mumbai": "Mumbai", "thane": "Mumbai MMR",
 "bengaluru": "Bengaluru", "bangalore": "Bengaluru",
 "delhi ncr": "Delhi NCR", "ncr": "Delhi NCR", "gurugram": "Gurugram", "gurgaon": "Gurugram",
 "new delhi": "Delhi NCR", "noida": "Noida", "greater noida": "Noida",
 "hyderabad": "Hyderabad", "pune": "Pune", "chennai": "Chennai", "ahmedabad": "Ahmedabad",
 "kolkata": "Kolkata", "jaipur": "Jaipur", "kochi": "Kochi", "chandigarh": "Chandigarh",
 "indore": "Indore", "surat": "Surat", "mohali": "Chandigarh",
}
CITY_STATE = {"Mumbai":"Maharashtra","Mumbai MMR":"Maharashtra","Pune":"Maharashtra","Bengaluru":"Karnataka",
 "Hyderabad":"Telangana","Chennai":"Tamil Nadu","Delhi NCR":"Delhi","Gurugram":"Haryana","Noida":"Uttar Pradesh",
 "Ahmedabad":"Gujarat","Kolkata":"West Bengal","Jaipur":"Rajasthan","Kochi":"Kerala","Chandigarh":"Chandigarh",
 "Indore":"Madhya Pradesh","Surat":"Gujarat"}
STRATEGIC = ["ai","fintech","deep tech","deep-tech","saas","space","defence","defense","semiconductor",
 "robotics","quantum","climate","ev ","battery","biotech","medtech","healthtech","quick commerce","qe"]
BIG_HUB = {"Mumbai":30,"Bengaluru":28,"Delhi NCR":18,"Gurugram":16,"Noida":14,"Hyderabad":13,"Pune":12,
 "Chennai":11,"Ahmedabad":9,"Kolkata":8,"Kochi":7,"Jaipur":6,"Surat":5,"Indore":5,"Chandigarh":5,"Mumbai MMR":24}

def norm_name(n):
    if not n: return ""
    n = n.lower().strip()
    n = LEGAL_SUFFIX.sub("", n)
    n = re.sub(r"[^a-z0-9& ]+", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n

def norm_domain(w):
    if not w: return ""
    m = re.search(r"https?://(?:www\.)?([^/ ]+)", w.lower())
    return m.group(1) if m else ""

def city_guess(s):
    s = (s or "").lower()
    for k, v in CITY_MAP.items():
        if re.search(r"\b"+re.escape(k)+r"\b", s):
            return v
    return ""

def funding_musd(hint):
    """Parse '$45M', 'Rs 400 crore', '$1.2B', '₹2,000 Cr', 'undisclosed' -> USD millions float or 0."""
    h = (hint or "").lower().replace(",", "")
    if not h: return 0.0
    m = re.search(r"[\$]\s*([\d.]+)\s*(b|bn|billion)\b", h)
    if m: return float(m.group(1)) * 1000
    m = re.search(r"[\$]\s*([\d.]+)\s*(m|mn|million)?\b", h)
    if m and (m.group(2) or "m"): return float(m.group(1))
    m = re.search(r"(?:rs\.?|inr|₹)\s*([\d.]+)\s*(crore|cr)\b", h)
    if m: return float(m.group(1)) / 83.5
    m = re.search(r"(?:rs\.?|inr|₹)\s*([\d.]+)\s*(billion|bn|b)\b", h)
    if m: return float(m.group(1)) * 1000 / 83.5
    return 0.0

def main(disc_dir, out_dir):
    rows, meta = [], {}
    for f in sorted(glob.glob(os.path.join(disc_dir, "*.json"))):
        try:
            data = json.load(open(f))
        except Exception as e:
            print(f"!! unreadable {f}: {e}"); continue
        if isinstance(data, dict): data = data.get("candidates") or data.get("rows") or data.get("companies") or []
        for r in data:
            if not isinstance(r, dict): continue
            cn = (r.get("company_name") or "").strip()
            if not cn or cn.upper().startswith("__META"):
                meta[cn] = r; continue
            if str(r.get("excluded", "")).lower() in ("true","1"): continue
            r["_from"] = os.path.basename(f)
            rows.append(r)
    # group by canonical key (name first, then domain)
    by_key, by_dom = defaultdict(list), defaultdict(list)
    for r in rows:
        k = norm_name(r["company_name"])
        if not k or len(k) < 2: continue
        by_key[k].append(r)
        d = norm_domain(r.get("website") or "")
        if d: by_dom[d].append((k, r))
    clusters = {}
    for k, rs in by_key.items():
        clusters.setdefault(k, {"keys": [k], "rows": []})["rows"].extend(rs)
    # domain-based merge of differently-named clusters (safe: same root domain)
    for d, pairs in by_dom.items():
        keys = sorted({k for k, _ in pairs})
        if len(keys) > 1:
            base = clusters[keys[0]]
            for kk in keys[1:]:
                base["keys"].extend(clusters[kk]["keys"]); base["rows"].extend(clusters[kk]["rows"])
                clusters[kk]["merged_into"] = keys[0]
    universe, merge_log = [], []
    for k, c in clusters.items():
        if "merged_into" in c: continue
        rs = c["rows"]
        freq = len(rs)
        srcs = sorted({r.get("discovery_url","") for r in rs if r.get("discovery_url")})
        cities = [city_guess(r.get("city") or r.get("state_guess") or "") for r in rs]
        cities = [x for x in cities if x]
        city = max(set(cities), key=cities.count) if cities else ""
        fh = max((funding_musd(r.get("funding_hint_usd_or_inr") or r.get("funding_hint") or "") for r in rs), default=0.0)
        vh = max((funding_musd(r.get("valuation_hint") or "") for r in rs), default=0.0)
        name = max((r["company_name"] for r in rs), key=lambda n: len(n))
        sectors = " | ".join(sorted({(r.get("sector_guess") or "").strip().lower() for r in rs if r.get("sector_guess")}))
        score = 0.0
        score += BIG_HUB.get(city, 0)
        score += min(25, 6 * max(0, math.log10(fh + 1)) * 2.5) if fh else 0
        if vh >= 1000: score += 10
        score += min(9, freq * 3)
        low = sectors.lower()
        if any(s in low for s in STRATEGIC): score += 5
        if any(str(r.get("status_hint","")).lower() not in ("","unknown") for r in rs): score += 2
        rec = any(x in json.dumps(rs).lower() for x in ["2026","2025","fy26","fy25","recent"])
        if rec: score += 4
        best = max(rs, key=lambda r: funding_musd(r.get("funding_hint_usd_or_inr","") or ""))
        universe.append({
            "company_name": name, "canonical_key": k, "all_names": sorted({r["company_name"] for r in rs}),
            "city": city, "state": CITY_STATE.get(city, ""), "sector_guess": sectors[:180],
            "stage_guess": best.get("stage_guess",""), "funding_musd_hint": fh, "valuation_musd_hint": vh,
            "founders_hint": best.get("founders_hint",""), "status_hint": " | ".join(sorted({str(r.get("status_hint","")) for r in rs if r.get("status_hint")}))[:160],
            "why_notable": (best.get("why_notable") or "")[:200],
            "freq": freq, "discovery_urls": srcs[:6], "sources_files": sorted({r["_from"] for r in rs}),
            "priority_score": round(min(score, 100), 1),
        })
    universe.sort(key=lambda u: (-u["priority_score"], u["company_name"].lower()))
    # ---- second pass: near-duplicate merge (containment / parenthetical aliases) ----
    def tokens(k): return set(k.split())
    drop = {}
    kept = []
    for cand in universe:  # highest priority first
        k = cand["canonical_key"]; killed = False
        for kk, keeper in ((x["canonical_key"], x) for x in kept):
            if not k or not kk or k == kk: continue
            same_tokens = tokens(k) == tokens(kk)
            sub_tokens = (len(tokens(k)) > 1 and tokens(k) <= tokens(kk)) or (len(tokens(kk)) > 1 and tokens(kk) <= tokens(k))
            if same_tokens or sub_tokens or k.startswith(kk + " ") or kk.startswith(k + " "):
                # "ecofy finance ecofy" vs "ecofy"; "weaver services weaver" vs "weaver services"
                merge_evidence = cand["city"] == keeper["city"] or not cand["city"] or not keeper["city"]
                if merge_evidence:
                    drop[k] = kk
                    keeper["all_names"] = sorted(set(keeper["all_names"]) | set(cand["all_names"]))
                    keeper["freq"] += cand["freq"]
                    keeper["discovery_urls"] = list(dict.fromkeys(keeper["discovery_urls"] + cand["discovery_urls"]))[:6]
                    keeper["funding_musd_hint"] = max(keeper["funding_musd_hint"], cand["funding_musd_hint"])
                    keeper["priority_score"] = max(keeper["priority_score"], cand["priority_score"])
                    killed = True; break
        if not killed:
            kept.append(cand)
    universe = kept
    universe.sort(key=lambda u: (-u["priority_score"], u["company_name"].lower()))
    for i, u in enumerate(universe, 1):
        u["startup_id"] = f"S{i:04d}"
        if u.get("merged_from"): pass
    os.makedirs(out_dir, exist_ok=True)
    json.dump({"generated": "2026-09-14", "run": "india-startup-db-265749", "meta": meta,
               "count": len(universe), "universe": universe},
              open(os.path.join(out_dir, "universe.json"), "w"), indent=1, ensure_ascii=False)
    with open(os.path.join(out_dir, "universe.csv"), "w", newline="") as fh_:
        w = csv.DictWriter(fh_, fieldnames=list(universe[0].keys()))
        w.writeheader(); [w.writerow({k: (";".join(v) if isinstance(v, list) else v) for k, v in u.items()}) for u in universe]
    with open(os.path.join(out_dir, "conflicts.md"), "w") as fh_:
        fh_.write("# Dedupe log\n\nMerged name clusters (domain-key merges):\n")
        for k, c in clusters.items():
            if "merged_into" in c: fh_.write(f"- `{k}` -> `{c['merged_into']}`\n")
    by_city = defaultdict(int)
    for u in universe: by_city[u["city"] or "(unknown)"] += 1
    print(f"universe: {len(universe)} companies  | Mumbai {by_city.get('Mumbai',0)} Bengaluru {by_city.get('Bengaluru',0)}")
    print("top20:", [u['company_name'] for u in universe[:20]])

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "india-startup-db/discovery",
         sys.argv[2] if len(sys.argv) > 2 else "india-startup-db/structured")
