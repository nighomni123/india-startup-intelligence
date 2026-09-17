#!/usr/bin/env python3
"""merge_gapfill.py — fold gapfill/*.json + gapfill/*.status.json into enrich/*.json (session-2 run).
Rules: NEVER overwrite existing non-empty values; append financials/round_supplements matched by (type,year);
status cards create/patch company.status (+closure facts) on their enrich file, else create a thin enrich file."""
import json, glob, os, re, sys, shutil
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
ENR = f"{BASE}/enrich"
GAP = f"{BASE}/gapfill"
UNIV = json.load(open(f"{BASE}/structured/universe.json"))["universe"]
BY_KEY = {u["canonical_key"]: u for u in UNIV}

def load_enrich(key):
    # returns (doc, real_path) — writes MUST go back to real_path to avoid shadow duplicates
    p = f"{ENR}/{key}.json"
    if os.path.exists(p):
        try: return json.load(open(p)), p
        except Exception: return None, None
    # fall back: any file whose canonical_key matches
    for f in glob.glob(f"{ENR}/*.json"):
        try:
            d = json.load(open(f))
            if d.get("canonical_key") == key: return d, f
        except Exception: pass
    u = BY_KEY.get(key)
    if not u: return None, None
    return {"canonical_key": key, "company": {"company_name": u["company_name"], "city": u["city"]}, "sources": []}, None

def new_src(doc, url, fields, conf, claim=""):
    doc.setdefault("sources", [])
    for s in doc["sources"]:
        if (s.get("url") if isinstance(s, dict) else s) == url:
            return
    doc["sources"].append({"url": url, "title": claim[:160], "fields": fields, "confidence": conf})

def salvage_json(path):
    t=open(path).read()
    for cut in range(len(t), 0, -50):
        frag=t[:cut]; in_s=False; esc=False; stack=[]
        for ch in frag:
            if in_s:
                if esc: esc=False
                elif ch=='\\': esc=True
                elif ch=='"': in_s=False
            else:
                if ch=='"': in_s=True
                elif ch in '{[': stack.append(ch)
                elif ch in '}]':
                    if stack and ((ch=='}' and stack[-1]=='{') or (ch==']' and stack[-1]=='[')): stack.pop()
        if in_s or frag[-1] not in ',{[: \n': continue
        cand=frag.rstrip().rstrip(',') + ''.join('}' if c=='{' else ']' for c in reversed(stack))
        try:
            d=json.loads(cand); json.dump(d,open(path,'w'),ensure_ascii=False,indent=1); return d
        except Exception: continue
    return None

stats = defaultdict(int)
import time as _t
for gf in sorted(glob.glob(f"{GAP}/*.json")):
    if _t.time() - os.path.getmtime(gf) < 180:  # skip files still being checkpointed
        continue
    try:
        g = json.load(open(gf))
    except Exception:
        g = salvage_json(gf)
        if g is None: print("!! unrecoverable gapfill", gf); continue
        print("~ salvaged truncated", os.path.basename(gf)); stats["salvaged"] += 1
    key = g.get("canonical_key") or os.path.basename(gf).split(".")[0].replace(".status","")
    doc, dpath = load_enrich(key)
    if not doc:
        u = BY_KEY.get(key)
        if not u: print("!! orphan gapfill", gf); continue
        doc = {"canonical_key": key, "startup_id": u["startup_id"],
               "company": {"company_name": u["company_name"], "city": u.get("city",""), "primary_sector": u.get("sector_guess","").split("|")[0].strip()},
               "funding_rounds": [], "founders": [], "investor_links": [], "financials": [], "events": [],
               "sources": [], "conflicts": [], "gaps": ["Gap-filled session-2; base record was discovery-shallow."],
               "research_log": [{"date": "2026-09-14", "query": "G/S-wave gap-fill on shallow row", "found": "see updates", "unresolved": "", "next_action": "none"}],
               "completeness_self": 0.3}
        print("~ created doc for", key)
    c = doc.setdefault("company", {})
    upd = (g.get("updates") or {}).get("company") or {}
    for k, v in upd.items():
        if v not in (None, "", [], {}) and not str(c.get(k, "")).strip():
            c[k] = v; stats["company_fields"] += 1
    for fr in g.get("financials_add") or []:
        doc.setdefault("financials", []).append({x: fr.get(x, "") for x in
            ["metric","value","unit","currency","fiscal_year","value_type","basis","source_url","source_title","source_date","confidence","notes"]})
        if fr.get("source_url"): new_src(doc, fr["source_url"], "FINANCIALS", fr.get("confidence","MEDIUM"))
        stats["financials"] += 1
    for rs in g.get("round_supplements") or []:
        mt, my = str(rs.get("match_round_type","")).lower(), str(rs.get("match_year",""))
        hit = None
        for r in doc.get("funding_rounds") or []:
            rt = str(r.get("round_type") or r.get("type") or "").lower()
            dt = str(r.get("announced_date") or r.get("round_date") or r.get("date") or r.get("source_date") or "")
            if rt == mt and (not my or my in dt): hit = r; break
        if hit is None:
            doc.setdefault("funding_rounds", []).append({"round_type": rs.get("match_round_type"), "amount": rs.get("amount",""),
                "currency": rs.get("currency","USD"), "round_date": rs.get("round_date",""), "valuation": rs.get("valuation",""),
                "valuation_currency": rs.get("valuation_currency",""), "valuation_type": rs.get("valuation_type",""),
                "lead_investors": rs.get("lead_investors") or [], "all_investors": rs.get("all_investors") or [],
                "new_or_existing": rs.get("new_or_existing",""), "purpose": rs.get("purpose",""),
                "source_url": rs.get("source_url",""), "confidence": rs.get("confidence","MEDIUM"), "notes": "added session-2 gapfill"})
            stats["rounds_new"] += 1
        else:
            for k in ["round_date","announcement_date","valuation","valuation_currency","valuation_type","new_or_existing","purpose"]:
                if rs.get(k) and not hit.get(k): hit[k] = rs[k]; stats["round_fields"] += 1
            if rs.get("source_url") and not hit.get("source_url"): hit["source_url"] = rs["source_url"]
        if rs.get("source_url"): new_src(doc, rs["source_url"], "FUNDING", rs.get("confidence","MEDIUM"))
    for im in g.get("investors_meta") or []:
        doc.setdefault("investors_meta", []).append(im)
        if im.get("source_url"): new_src(doc, im["source_url"], "INVESTORS", "MEDIUM")
        stats["investors_meta"] += 1
    for pl in g.get("people") or []:
        doc.setdefault("people", []).append(pl)
        if pl.get("source_url"): new_src(doc, pl["source_url"], "PEOPLE", pl.get("confidence","MEDIUM"))
    for sm in g.get("sources") or []:
        u_ = sm.get("url") if isinstance(sm, dict) else sm
        if u_ and str(u_).startswith("http"): new_src(doc, u_, (sm.get("fields") if isinstance(sm,dict) else "") or "company", (sm.get("confidence") if isinstance(sm,dict) else "") or "MEDIUM", (sm.get("title","") if isinstance(sm,dict) else ""))
    for lg in g.get("log") or []:
        doc.setdefault("research_log", []).append({"date": "2026-09-14", **lg})
    if g.get("still_missing"):
        existing = {str(x) for x in (doc.get("gaps") or [])}
        doc["gaps"] = list(doc.get("gaps") or []) + [x for x in g["still_missing"] if str(x) not in existing]
    doc["_merged_session2"] = True
    json.dump(doc, open(dpath or f"{ENR}/{key}.json", "w"), ensure_ascii=False, indent=1)
    stats["files"] += 1

# qsrc claim-hunt files: attach supported URLs by re-patching the originating enrich lists
for qf in sorted(glob.glob(f"{GAP}/*.qsrc.json")):
    if _t.time() - os.path.getmtime(qf) < 180: continue
    try: q = json.load(open(qf))
    except Exception:
        q = salvage_json(qf)
        if q is None: continue
    key = q.get("canonical_key") or os.path.basename(qf).replace(".qsrc.json","")
    doc, dpath = load_enrich(key)
    if not doc: print("!! orphan qsrc", qf); continue
    sup=0
    for cl in q.get("claims") or []:
        if cl.get("verdict")=="supported" and str(cl.get("url","")).startswith("http"):
            new_src(doc, cl["url"], "quarantine-resolved", cl.get("confidence","MEDIUM"), str(cl.get("claim",""))[:150]); sup+=1
        elif cl.get("verdict")=="contradicted":
            doc.setdefault("conflicts", []).append({"field":"quarantined-claim","claim_a":str(cl.get("claim",""))[:120],"claim_b":str(cl.get("correct_value",""))[:120],"url_a":cl.get("url",""),"url_b":cl.get("url",""),"resolution":"Q-wave source hunt: contradicted"})
            if str(cl.get("url","")).startswith("http"): new_src(doc, cl["url"], "quarantine-contradiction", "MEDIUM", str(cl.get("claim",""))[:150])
            sup+=1
    for k,v in ((q.get("updates") or {}).get("company") or {}).items():
        c = doc.setdefault("company", {})
        if v and not str(c.get(k,"")).strip(): c[k]=v
    doc.setdefault("research_log", []).append({"date":"2026-09-14","query":"Q-wave claim source-hunt","found":f"{sup} resolved","unresolved":"","next_action":"none"})
    json.dump(doc, open(dpath or f"{ENR}/{key}.json","w"), ensure_ascii=False, indent=1)
    stats["qsrc_files"] += 1; stats["claims_resolved"] += sup

# investor metadata files (investors_NN.json) -> consolidated override map
import re as _re3
def _nrm(n): return _re3.sub(r"[^a-z0-9]+"," ",str(n).lower()).strip()
OVR_PATH=f"{BASE}/structured/investor_meta_overrides.json"
OVR=json.load(open(OVR_PATH)) if os.path.exists(OVR_PATH) else {}
for ivf in sorted(glob.glob(f"{GAP}/investors_*.json"))+sorted(glob.glob(f"{GAP}/merged/investors_*.json")):
    try: q=json.load(open(ivf))
    except Exception:
        q=salvage_json(ivf)
        if not q: continue
    for im in q.get("investors_meta") or []:
        k=_nrm(im.get("investor") or im.get("name"))
        if not k: continue
        cur=OVR.setdefault(k,{})
        for fld in ["type","hq_geography","india_presence","source_url","confidence"]:
            if im.get(fld) and not cur.get(fld): cur[fld]=im[fld]
    stats["investor_files"]+=1
json.dump(OVR,open(OVR_PATH,"w"),ensure_ascii=False,indent=1)
print(f"investor overrides: {len(OVR)} investors")

# founder-status updates (.founders.json) -> founders[] in enrich docs
import re as _r4
def _fn(n): return _r4.sub(r"[^a-z ]","",str(n or "").lower()).strip()
for ff in sorted(glob.glob(f"{GAP}/*.founders.json"))+sorted(glob.glob(f"{GAP}/merged/*.founders.json")):
    if _t.time() - os.path.getmtime(ff) < 180: continue
    try: q=json.load(open(ff))
    except Exception:
        q=salvage_json(ff)
        if not q: continue
    key=q.get("canonical_key") or os.path.basename(ff).replace(".founders.json","")
    doc, dpath = load_enrich(key)
    if not doc: print("!! orphan founders file", ff); continue
    applied=0
    for up in q.get("founder_updates") or []:
        un=_fn(up.get("name"))
        for f_ in doc.get("founders") or []:
            fnm=_fn(f_.get("name") or f_.get("person_name"))
            if fnm and (fnm==un or fnm in un or un in fnm):
                for fld in ("active","departure_date","location","linkedin","education","prev_companies"):
                    if up.get(fld) and not f_.get(fld): f_[fld]=up[fld]
                if up.get("source_url"):
                    surl=up["source_url"]
                    if surl.startswith("http"):
                        skey=_r4.sub(r"[^a-z0-9]","",surl.lower())[:120]
                        if not any(skey in _r4.sub(r"[^a-z0-9]","",str(x.get("url") if isinstance(x,dict) else x).lower()) for x in (doc.get("sources") or [])):
                            doc.setdefault("sources", []).append({"url":surl,"title":up.get("source_title","auto: founder status"),"tier":up.get("tier","T2"),"claim":f"founder status {up.get('name','')}"[:140]})
                applied+=1; break
    doc.setdefault("research_log", []).append({"date":"2026-09-14","query":"FS-wave founder status","found":f"{applied} founders updated","unresolved":"","next_action":"none"})
    json.dump(doc, open(dpath or f"{ENR}/{key}.json","w"), ensure_ascii=False, indent=1)
    stats["founder_updates"]+=applied

# Phase 3 deep-enrichment payloads (.p3.json): deep-merge lists, fill-empty company fields, preserve conflicts
for wf in sorted(glob.glob(f"{GAP}/*.p3.json"))+sorted(glob.glob(f"{GAP}/merged/*.p3.json")):
    if _t.time() - os.path.getmtime(wf) < 120: continue
    try: q=json.load(open(wf))
    except Exception: continue
    key=q.get("canonical_key") or os.path.basename(wf)[:-8]
    doc, dpath = load_enrich(key)
    if not doc: continue
    c = doc.setdefault("company", {})
    _cseen = {((str(c.get("field","")), str(c.get("a") or c.get("claim_a") or "")[:80], str(c.get("b") or c.get("claim_b") or "")[:80]) if isinstance(c,dict) else json.dumps(c,ensure_ascii=False,sort_keys=True)[:120]) for c in doc.get("conflicts") or []}
    for fk, fv in (q.get("company") or {}).items():
        cur = c.get(fk)
        curv = (cur.get("v") if isinstance(cur,dict) else cur)
        newv = (fv.get("v") if isinstance(fv,dict) else fv)
        if not str(curv or "").strip():
            c[fk] = fv
        elif str(curv).strip().lower() != str(newv or "").strip().lower():
            _dk=(fk,str(curv)[:80],str(newv)[:80])
            if _dk not in _cseen:
                _cseen.add(_dk)
                doc.setdefault("conflicts", []).append({"field": fk, "claim_a": str(curv)[:200], "url_a": str((cur.get("src") if isinstance(cur,dict) else "") or ""), "claim_b": str(newv)[:200], "url_b": str((fv.get("src") if isinstance(fv,dict) else fv) or "")[:1000] if str(fv).startswith("http") else "", "resolution": "phase3 p3 payload disagrees with existing value; existing kept as preferred pending human review", "resolved_value": "", "reviewed": "p3-merge"})
    def _p3key(lk, x):
        g = lambda *ks: next((str(x[k]).strip() for k in ks if x.get(k)), "")
        if lk=="traction": return (g('metric'), g('value'), g('unit'), g('period'), g('as_of'))
        if lk=="financials": return (g('fiscal_year'), g('period'), g('metric'), g('value'), g('unit'), g('basis'))
        if lk=="funding_rounds": return (g('round_type'), g('round_date','announcement_date'), g('amount'), g('currency'))
        import re as _re
        _nm = _re.sub(r"[^a-z ]","",g('name').lower()); _nm = _re.sub(r"\s+"," ",_nm).strip()
        _po = _re.sub(r"[^a-z ]","",g('position','role').lower()); _po = _re.sub(r"\s+"," ",_po).strip()
        if lk in ("people","founders"): return (_nm, _po)
        if lk=="locations": return (g('type'), g('address_or_area')[:60], g('city'), g('as_of'))
        if lk=="events": return (g('title','event','headline')[:70], g('date','event_date'))
        if lk=="customers": return (g('name','customer')[:70],)
        if lk=="legal": return (g('issue','title','case')[:70], g('date'), g('status'))
        if lk=="products": return (g('name','product')[:70], g('status'))
        if lk=="investor_links": return (g('investor','investor_name','name'), g('round_type'), g('round'))
        return json.dumps(x,ensure_ascii=False,sort_keys=True)[:160]
    for lk in ("funding_rounds","financials","traction","products","people","events","legal","locations","customers","founders","investor_links"):
        incoming = q.get(lk) or []
        if not incoming: continue
        ex = doc.setdefault(lk, [])
        seen = {_p3key(lk,x) for x in ex if isinstance(x,dict)}
        for x in incoming:
            if not isinstance(x,dict): continue
            kk = _p3key(lk,x)
            if kk in seen: continue
            seen.add(kk); ex.append(x)
    for cf in (q.get("conflicts") or []):
        if not isinstance(cf,dict): continue
        _ck = (str(cf.get("field","")), str(cf.get("a") or cf.get("claim_a") or "")[:80], str(cf.get("b") or cf.get("claim_b") or "")[:80])
        if _ck in _cseen: continue
        _cseen.add(_ck); doc.setdefault("conflicts", []).append(cf)
    exs = doc.setdefault("sources", [])
    seen_url = {str((x.get("url") if isinstance(x,dict) else x) or "").lower().split("#")[0].rstrip("/")[:120] for x in exs}
    for sx in (q.get("sources") or []):
        u2 = str((sx.get("url") if isinstance(sx,dict) else sx) or "")
        if u2.startswith("http") and u2.lower().split("#")[0].rstrip("/")[:120] not in seen_url:
            seen_url.add(u2.lower().split("#")[0].rstrip("/")[:120]); exs.append(sx)
    for lgx in (q.get("log") or []):
        if isinstance(lgx,dict): doc.setdefault("research_log", []).append(lgx)
    _facts = sum(len(v) for v in q.values() if isinstance(v,list)) + len(q.get("company") or {})
    if _facts >= 10:
        print(f"P3-APPLY {key}: doc now lists={sum(len(v) for v in doc.values() if isinstance(v,list))} company={len(doc.get('company') or {})}")
    with open(dpath or f"{ENR}/{key}.json","w") as fh: json.dump(doc, fh, ensure_ascii=False, indent=1)
    if not wf.startswith(f"{GAP}/merged/"):
        os.makedirs(f"{GAP}/merged", exist_ok=True); shutil.move(wf, f"{GAP}/merged/"+os.path.basename(wf))
    stats["p3_updates"] = stats.get("p3_updates", 0) + 1

# website verification files (.site.json) -> official_website / careers_website
for wf in sorted(glob.glob(f"{GAP}/*.site.json"))+sorted(glob.glob(f"{GAP}/*.careers.json"))+sorted(glob.glob(f"{GAP}/merged/*.site.json"))+sorted(glob.glob(f"{GAP}/merged/*.careers.json")):
    if _t.time() - os.path.getmtime(wf) < 120: continue
    try: q=json.load(open(wf))
    except Exception: continue
    key=q.get("canonical_key") or os.path.basename(wf).replace(".site.json","").replace(".careers.json","")
    doc, dpath = load_enrich(key)
    if not doc: print("!! orphan site file", wf); continue
    c=doc.setdefault("company", {})
    ow=q.get("official_website") or {}
    cw=q.get("careers_website")
    if not ow.get("v") and (ow.get("url") or ow.get("final_url")):
        ow={"v":ow.get("final_url") or ow.get("url"),"conf":ow.get("conf","high"),"src":ow.get("url") or ow.get("final_url"),"note":ow.get("note","W-wave verified 2026-09-15")}
        q["official_website"]=ow
    if cw and not cw.get("v") and (cw.get("url") or cw.get("final_url")):
        cw={"v":cw.get("final_url") or cw.get("url"),"conf":cw.get("conf","high"),"src":cw.get("url") or cw.get("final_url"),"note":cw.get("note","W-wave verified 2026-09-15")}
        q["careers_website"]=cw
    if ow.get("v"): c["official_website"]=ow
    if cw and cw.get("v"): c["careers_website"]=cw
    if ow.get("v") and str((c.get("website") or (c.get("website") or {}).get("v") if isinstance(c.get("website"),dict) else c.get("website")) or "").strip()=="" :
        c["website"]=ow["v"]
    json.dump(doc, open(dpath or f"{ENR}/{key}.json","w"), ensure_ascii=False, indent=1)
    stats["site_updates"]=stats.get("site_updates",0)+1

# acquisition detail fills (.acq.json)
for af in sorted(glob.glob(f"{GAP}/*.acq.json"))+sorted(glob.glob(f"{GAP}/merged/*.acq.json")):
    if _t.time() - os.path.getmtime(af) < 180: continue
    try: q=json.load(open(af))
    except Exception:
        q=salvage_json(af)
        if not q: continue
    key=q.get("canonical_key") or os.path.basename(af).replace(".acq.json","")
    doc, dpath = load_enrich(key)
    if not doc: print("!! orphan acq file", af); continue
    lst=doc.setdefault("acquisitions", [])
    for up in q.get("acq_updates") or []:
        mt=_r4.sub(r"[^a-z ]","",str(up.get("match","")).lower()).strip()
        tgt=None
        for x in lst:
            xn=_r4.sub(r"[^a-z ]","",str(x.get("target") or x.get("buyer") or x.get("name") or "").lower()).strip()
            if xn and (mt and (mt in xn or xn in mt)): tgt=x; break
        if tgt is None:
            tgt={"target":up.get("match"),"direction":up.get("direction","")}; lst.append(tgt)
        for fld in ("type","deal_type","counterparty","seller","value","disclosed","date","transaction_date","rationale"):
            v=up.get(fld)
            if v and not tgt.get(fld): tgt[fld]=v
        if str(up.get("source_url") or "").startswith("http"):
            tgt["source_url"]=up["source_url"]
            doc.setdefault("sources", []).append({"url":up["source_url"],"title":up.get("source_title","auto: acquisition"),"tier":"T2","claim":f"acquisition {up.get('match','')}"[:140]})
    stats["acq_updates"]+=len(q.get("acq_updates") or [])
    json.dump(doc, open(dpath or f"{ENR}/{key}.json","w"), ensure_ascii=False, indent=1)

# status cards (defunct or thin-patch)
for gf in sorted(glob.glob(f"{GAP}/*.status.json")):
    if _t.time() - os.path.getmtime(gf) < 180: continue
    try: g = json.load(open(gf))
    except Exception: continue
    key = g.get("canonical_key") or os.path.basename(gf).replace(".status.json","")
    doc, dpath = load_enrich(key)
    if not doc:
        cc = g.get("company") or {}
        doc = {"canonical_key": key,
               "company": {k2: v2 for k2, v2 in cc.items() if v2},
               "funding_rounds": [], "founders": [], "investor_links": [], "financials": [],
               "sources": g.get("sources") or [], "conflicts": [],
               "gaps": g.get("gaps") or ["Defunct — enrichment intentionally scoped out (active-only)."],
               "research_log": [{"date": "2026-09-14", "query": "S-wave status gate", "found": "defunct; status-only record", "unresolved": "", "next_action": "none"}],
               "completeness_self": 0.15}
        print("~ created thin defunct doc for", key)
    c = doc.setdefault("company", {})
    for k, v in (g.get("company") or {}).items():
        if v and not str(c.get(k, "")).strip(): c[k] = v
    c["status"] = (g.get("company") or {}).get("status") or c.get("status") or "Inactive"
    for s in g.get("sources") or []:
        u_ = s.get("url") if isinstance(s, dict) else s
        if u_ and str(u_).startswith("http"): new_src(doc, u_, "status", (s.get("confidence") if isinstance(s,dict) else "") or "MEDIUM")
    doc.setdefault("gaps", []).append("Defunct — enrichment intentionally scoped out (active-only).")
    doc.setdefault("research_log", []).append({"date": "2026-09-14", "query": "status gate", "found": str(c.get("status"))[:120], "unresolved": "", "next_action": "none"})
    json.dump(doc, open(dpath or f"{ENR}/{key}.json", "w"), ensure_ascii=False, indent=1)
    stats["status_cards"] += 1

# journal: move merged (non-status) files into merged/ so re-runs don't double-append
os.makedirs(f"{GAP}/merged", exist_ok=True)
for gf in sorted(glob.glob(f"{GAP}/*.json")):
    if gf.endswith(".status.json") or "/merged/" in gf or "investors_" in os.path.basename(gf): continue
    shutil.move(gf, f"{GAP}/merged/" + os.path.basename(gf))
    stats["journalled"] += 1
print(json.dumps(dict(stats), indent=1))
