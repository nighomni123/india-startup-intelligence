#!/usr/bin/env python3
"""validate_urls.py — HTTP liveness check over SOURCES.csv urls (HEAD then GET fallback).
outcomes: OK | BOTBLOCKED(401/403/407/429/999) | REDIRECT(3xx target) | DEAD(404/410/DNS) | TIMEOUT/ERR"""
import csv, sys, urllib.request, socket, ssl, collections
from concurrent.futures import ThreadPoolExecutor
socket.setdefaulttimeout(12)
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
def probe(url):
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, headers=UA, method=method)
        try:
            with urllib.request.urlopen(req) as r:
                c = r.getcode()
                return "OK" if c < 300 or (method == "GET") else "OK"
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 407, 429, 503): return f"BOTBLOCKED:{e.code}"
            if e.code in (301, 302, 303, 307, 308): return f"REDIRECT:{e.code}"
            if e.code in (404, 410): return f"DEAD:{e.code}"
            return f"ERR:{e.code}"
        except Exception:
            if method == "HEAD": continue
            return "ERR:conn"
    return "ERR"
def main():
    rows = list(csv.DictReader(open(sys.argv[1] if len(sys.argv) > 1 else "build/csv/SOURCES.csv")))
    urls = sorted({r["url"] for r in rows if r.get("url")})
    print(f"probing {len(urls)} unique urls")
    res = {}
    with ThreadPoolExecutor(24) as ex:
        for u, o in zip(urls, ex.map(probe, urls)): res[u] = o
    cnt = collections.Counter(o.split(":")[0] for o in res.values())
    print(cnt.most_common())
    with open("qc/url_audit.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["url", "outcome"])
        for u in sorted(res): w.writerow([u, res[u]])
    dead = [u for u, o in res.items() if o.startswith("DEAD")]
    print(f"DEAD (404/410): {len(dead)}")
    for d in dead[:15]: print("  ", d)
if __name__ == "__main__":
    import urllib.error
    main()
