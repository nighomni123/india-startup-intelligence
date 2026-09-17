#!/usr/bin/env python3
"""recapture_blocked.py — fetch every BOTBLOCKED SOURCES url through monid tinyfish /fetch (rendering lane).
Writes qc/botblocked_capture.csv rows: url, note_id|status, chars, error."""
import csv, json, subprocess, os, sys, time
os.environ["XDG_CONFIG_HOME"] = "/Users/Mitesh Gada/Documents/Projects/.monid/xdg"
MONID = "/Users/Mitesh Gada/.npm-global/bin/monid"
rows=list(csv.DictReader(open('build/csv/SOURCES.csv')))
urls=sorted({r['url'] for r in rows if 'BOTBLOCKED' in (r.get('notes') or '')})
done=set()
OUT='qc/botblocked_capture.csv'
if os.path.exists(OUT):
    for r in csv.DictReader(open(OUT)): done.add(r['url'])
todo=[u for u in urls if u not in done]
print(f"{len(urls)} blocked | {len(done)} already | {len(todo)} to fetch", flush=True)
fh=open(OUT,'a',newline=''); w=csv.writer(fh)
if not os.path.getsize(OUT): w.writerow(['url','status','chars','error'])
for i,u in enumerate(todo):
    ok=False
    for attempt in range(2):
        try:
            p=subprocess.run([MONID,'run','--provider','tinyfish','--endpoint','/fetch','-i',json.dumps({"urls":[u]}),'--wait','90','-j'],capture_output=True,text=True,timeout=150)
            d=json.loads(p.stdout)
            outp=d.get('output') or {}
            txt=json.dumps(outp)
            # find any substantial content
            content=None
            def hunt(o):
                if isinstance(o,dict):
                    for k,v in o.items():
                        if k in ('content','markdown','text','html') and isinstance(v,str) and len(v)>200: return v
                        r=hunt(v)
                        if r: return r
                if isinstance(o,list):
                    for v in o:
                        r=hunt(v)
                        if r: return r
            content=hunt(outp)
            if content: w.writerow([u,'CAPTURED',len(content),'']); ok=True; break
            else: err=(d.get('error') or d.get('message') or 'no-content')
            if attempt==1: w.writerow([u,'FAILED',0,str(err)[:120]])
            time.sleep(3)
        except Exception as e:
            if attempt==1: w.writerow([u,'ERROR',0,str(e)[:120]])
            time.sleep(3)
    fh.flush()
    if (i+1)%10==0: print(f"{i+1}/{len(todo)} done", flush=True)
fh.close(); print("ALL DONE", flush=True)
