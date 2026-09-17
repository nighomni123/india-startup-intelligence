# Quality Report — INDIA STARTUP INTELLIGENCE DATABASE
**Workbook:** `india-startup-intelligence.xlsx` · **Built:** 2026-09-14 · **Run:** `india-startup-db-265749` · **Tooling:** OfficeCLI 1.0.149 (all sheet/cell ops), hyperresearch vault (all source pages), subagent research waves (web_search + tinyfish free lane)

## 1. Scope & loop executed
DISCOVER (4 waves → 433 raw rows) → NORMALIZE/DEDUPE (367 companies; 2 near-dupe merges + 2 dup-name passes) → ENRICH (pilot + 3 deep waves = 58 companies at 15–30 searches each; + 1 lite wave = 24 companies core-layer) → VERIFY (seed falsification was expected and delivered: agents corrected Zepto→Mumbai, Darwinbox→Hyderabad, Gupshup→Mumbai/SF, Sarvam→Chennai-founded, MoEngage not-a-unicorn, Moglix seed round refuted, BrowserStack Dublin-corporate/Mumbai-ops) → STRUCTURE → WRITE XLSX → VALIDATE → AUDIT → GAP REGISTER.

## 2. Workbook structure (audited post-build, this run)
- **22 sheets** (README + 20 data + DASHBOARD), every data sheet: frozen header row, Excel Table with header autoFilter (dropdowns), column widths, wrap on long-text columns, header styling. (Sheet-level freeze applied uniformly at finalize — OfficeCLI's `import --header` skipped the first sheet.)
- **6 DASHBOARD charts** (funding by sector/year/city, stage donut, investor frequency, top-funded) with cached series data; KPI cells carry **live formulas** (COUNTIFS/SUMIFS/AVERAGEIFS) with static as-of values; SCORES has live `completeness_calc(DERIVED-live)` recompute of the weighted score + color scale.
- **101 conditional formats** (confidence colour scale on 15 sheets, status highlights, 3 databars) · **18 dropdown validations** · **821 clickable external hyperlinks** (counted in OOXML relationship parts of the shipped file).
- OpenXML `validate` = OK; custom validator `qc/validation.md` = **0 ISSUES** (FK integrity, dup IDs, URL sanity, date format, confidence enums, amount-plausibility caps all pass); 64 benign WARNINGS (temporal date strings like `2009 (brand founded; legal entity 2018)` — preserved deliberately, never normalized away).

## 3. Data counts (rows per sheet, final build)
STARTUPS 367 · FOUNDERS 212 · PEOPLE 26 · FUNDING 251 rounds · INVESTOR_LINKS 1,115 · INVESTORS 394 · FINANCIALS 219 · TRACTION 87 · PRODUCTS 96 · CUSTOMERS 27 · PARTNERSHIPS 12 · COMPETITORS 86 · ACQUISITIONS 33 · LOCATIONS 82 · HIRING 24 · LEGAL_REGULATORY 15 · NEWS_EVENTS 207 · **SOURCES 751 unique URLs** · RESEARCH_LOG 144 · SCORES 367. (Workbook 504 KB.)

## 4. Coverage & confidence
- Cities (post-correction): Bengaluru 138, Mumbai 55, Gurugram 32, Delhi NCR 10, Ahmedabad 10, Chennai 9, Kolkata 9 … 47 shallow rows carry **no city** (discovery listicle gave no city evidence — left blank, not guessed).
- STARTUPS confidence: HIGH 38 · MEDIUM 45 · UNVERIFIED 284 (the shallow backlog, explicitly labelled “Shallow candidate: discovery-layer only”).
- Research Completeness Score (weighted, user spec): mean 20.5 % across universe; **43 companies ≥ 60 %**; max ≈ 79 % (Pixxel / Moneyview band). No company reaches 80 — audited MCA filings remain the binding constraint (see §6).
- 114 source-conflicts **preserved verbatim** in `conflicts`/notes (e.g. Innovaccer $275M headline vs $179M primary; Pristyn FY25 ₹442cr mgmt vs ₹600cr FY24 audited; Dream11 valuation epochs) — never averaged.
- 328 explicit gap entries per company + RESEARCH_LOG next_action column.

## 5. Provenance audit (link liveness, 2026-09-14)
All 751 SOURCES urls probed (UA-spoofed HEAD→GET): **610 LIVE · 124 bot-blocked (403/429: LinkedIn, Tracxn, Wikipedia, ET paywalls — content was captured at fetch time via vault) · 10 DEAD (404) · 7 conn-err**. The 10 dead rows are annotated in SOURCES.notes and auto-downgraded to confidence LOW; they are:
Udaan $160M TNW, Nykaa earnings-call Yahoo page, Shashvat Nakrani wiki page, 4× Pixxel pages (TNW $100M, moneycontrol consortium, pixxel.space $24M, indianexpress firefly, trilegal PPP), SquareYards own blog post, Tracxn food-tech explore page. Facts they carried remain at their vault-recorded snippet level and are flagged.
- 210 field-level claims from agent JSONs had **no usable URL** → quarantined from SOURCES spine (kept only as notes text); no URLs were ever invented.

## 6. What could NOT be verified (honest limits — no 100 % claims anywhere)
1. **MCA/ROC filings**: not machine-pullable here → audited FY25 revenue/PAT figures exist only where a T1 outlet published them; value_type marks management vs press-quoted vs audited.
2. **CIN numbers** for ~90 % of companies; DPIIT recognition only per-company where a source names it (registry bulk list inaccessible).
3. **LinkedIn headcounts** never treated as audited; employee_estimate = band + as-of date.
4. **Debt rounds/valuations** frequently single-sourced (labelled MEDIUM/LOW).
5. 2026 events (Navi Prosus $100M, Rapido Series F, Skyroot $60M, Square Yards unicorn, UDRHP/DRHP filings) are recent-press only — vault-tagged as-of dates included.
6. 284 discovery-layer companies are deliberately shallow (name/city-tier/sector/1 source) — the queued enrichment backlog, machine-findable via SCORES < 30.
7. FX INR conversions use documented annual-average approximations (table in README) — every converted value DERIVED-marked.

## 7. Known quirks of the toolchain (for future rebuilds — codified in excel_build.py)
- `add --type column` **wipes existing cells in that column** → use `set /SHEET/col[L] --prop width` on imported sheets; create columns before writing cells on hand-built sheets.
- Resident edit-flush race → build runs with `OFFICECLI_RESIDENT_FLUSH=each`; never `open` after `create` (dual residents split writes).
- Batch top-level success hides item failures → batch() checks per-item summary.
- PivotTables not creatable via OfficeCLI verbs here → DASHBOARD ships SUMIFS/AVERAGEIFS live grids + 6 native charts instead (documented in README).

*Counts in §3/§4 are regenerated by `python3 build_tables.py && python3 validate_db.py && python3 excel_build.py`; re-run `validate_urls.py` before shipping any future version.*

---

# SESSION-2 FURNISHING RUN (addendum — this file's §3/§4 counts below describe V1)

## S2.1 Method
Six wave families under a binding ACTIVE-ONLY gate (defunct/insolvent companies get one status lookup + closure source, then are excluded from enrichment — 20+ status-only records preserved in the spine with LOW/MEDIUM confidence, none enriched):
- **P0 plumbing fixes** (build_tables): CIN-state crosscheck (never auto-delete), loose-date quarantine into notes (ISO-only columns), dict-value coercion (3 silent-crash classes: person(), city groupby, archive-map shape — each had been leaving STALE CSVs behind "successful" builds), `parse_money` root bug ("N Cr" mislabeled USD → INR crore), auto-titles for bare URLs, host-dot guard killing placeholder URLs, investor metadata override map (91 funds), mechanical derivations: website_status (from linkcheck), aliases (all_names), parent/subsidiary (regex from sourced notes: 10 groups), FUNDING.new_or_existing (investor-repeat chronology, 579 rows `(DERIVED)`).
- **S waves**: S1 40 famous-active deep-lite (40/40); S2 117-company mid tier ×24 batches with status-gate (20 defunct found and excluded); S3 63-company tail with best-effort (all batches landed incl. 3 re-runs after transport deaths).
- **G waves**: 17 targeted gap manifests (CIN/incorporation, FY financials, round dates/valuations, investor type/geo, city backfill) + IV investor-metadata files.
- **Q wave**: quarantined-claim source hunt — 214 claim rows triaged; 174 were field-name bookkeeping noise; 58 real claims: 4 genuine contradictions applied (Dezerv→Mumbai, MoEngage valuation ~$900M+, Games24x7 own-brand, Zeta $2B era), rest re-sourced with live URLs.
- **P1 sources**: full 2,268-URL re-audit: ~1,739 live, ~451 bot-blocked (captured-at-fetch-time; tinyfish re-capture lane tested 124/124 = 0 recoverable — documented exhausted), 32 dead (4 wired to true Wayback copies; rest LOW + duplicate-live backing), 5 of 10 V1 dead URLs naturally retired by live re-sourcing. Prior dead-map's "10" contained Wayback homepage-bounce false positives — corrected.

## S2.2 Before → after (FINAL ship numbers)
| Metric | V1 | Session-2 |
|---|---|---|
| Company records (367 universe) | 83 enriched, 284 shallow | **367/367 sourced records** (incl. 20+ defunct status-only per active-only rule) |
| Mean completeness score | 20.5% | **44.4%** (max 82%, ≥60%: 43→75 companies) |
| Rows without city | 47 | **0 (100% coverage)** |
| SOURCES rows | 751 | **2,272** |
| Linkcheck | 751 urls (610 live) | 2,316 urls: **1,769 live / 457 bot-blocked / 34 dead / 56 conn-err**; 5 archive-wired |
| FUNDING rounds | 251 | **775** (new_or_existing 64% DERIVED) |
| FINANCIALS rows | 219 | **544**; revenue_latest_fy 11%→44% |
| FOUNDERS rows | ~530 | **706**, active-status **73%** |
| ACQUISITIONS | 45, no type | **52, type 85%, value 81%** |
| INVESTORS | 628, type 2% | **1,109, type 29%, geo 22%** (131 fund metas) |
| CIN / incorporation | ~1% / ~2% | **47% / 39%** |
| website / website_status | 21% / 0% | **81% / 81%** |
| validate_db | 0 issues | **0 issues / 0 warnings** |

## S2.3 Honest limits after this run
CIN for private companies without aggregator coverage; DPIIT registry bulk inaccessible; LinkedIn profiles bot-walled (founder linkedin ~0%); audited MCA filings paywalled (press-published FY numbers only, value_type-labeled); ~451 sources are bot-blocked-at-probe but were captured live at research time; defunct rows carry closure only, not enrichment, per the active-only order; 126 FUNDING rows can't classify new_or_existing (rounds listed without investor names).

---

## PRECISION UPGRADE (2026-09-15) — research-maturity model replaces deep/shallow

**Why:** user audit correctly identified that `tier="deep"` was hardcoded for every enriched
record — 368/368 "deep" was not defensible (actual completeness median was ~40%, not ~70%).
The single score was also overloaded: easy-to-fill categories (identity/funding press) inflated
records with zero financials/traction/customers.

**New model (SPEC amendment #2):**
- 12 categories × objective banded coverage {0, .25, .5, .75, 1} → Research Completeness = equal-weight mean.
- Separate axes: Source Quality % (tier-weighted: 10 T3 items ≠ 5 T1 items), Freshness %, Conflict Level.
- Tiers: <20 Candidate · 20-39.9 Basic · 40-59.9 Enriched · 60-74.9 Deep · 75-89.9 Intelligence-grade · 90+ Fully researched.

**Honest distribution (368 tracked):** Candidate 65 (17.7%) · Basic 127 (34.5%) · Enriched 131 (35.6%)
· Deep 41 (11.1%) · Intelligence-grade 4 (1.1%) · Fully researched 0. Mean completeness 38.6%
(min 6.2 / median 39.6 / max 79.2). Avg source quality 61.5% · avg freshness 63.9% · conflicts: 225 none / 87 low / 56 moderate.

**New execution ledger (sheet 23, RESEARCH_TASKS):** 2,932 task rows — 990 completed, 69 logged-no-result,
1,873 not_started (P1 417 / P2 854 / P3 1,661) — one row per (startup, area), derived from the deduped audit
trail + coverage. Gap-driven research queries are now answerable natively (e.g. area=funding & status=not_started & priority=P1).
RESEARCH_LOG deduped 1,239→872 rows (reps column; Pync-style status-gate spam collapsed).

**company_class (DERIVED):** Startup 147 · Other-status-unverified 65 · Scale-up 62 · Public 30 · Mature private 29 ·
Former startup 24 · Acquired-operating 7 · Subsidiary 4. Funding headlines relabeled as tracked-universe sums;
dashboard carries explicit census/entity-class caveats.

**Ship state after upgrade:** validate_db 0 issues / 0 warnings; workbook 23 sheets.
What this DB honestly is now: a broad discovery database with ~190 companies researched to Enriched-or-better,
41 Deep — not "368 deep records." Next phase per user plan: gap-driven deep-enrichment from RESEARCH_TASKS P1/P2.

---

# > **FINAL Phase-3 numbers live in [`PHASE3_REPORT.md`](PHASE3_REPORT.md) (2026-09-16 02:12 ship); section below is the round-11 interim.**

PHASE 3 — Intelligence-Grade Enrichment & Verification (2026-09-15/16)

## Program scoreboard (measured, honest)
**Machinery**: CLAIMS sheet (3,524 evidence rows: every round amount, valuation, financial, traction metric, dict-sourced company field — each with source_id/confidence/period/status), CONFLICTS sheet (350 = 157 resolved with stated preferred value + 190 preserved-conflict + 3 unresolved; nothing silently overwritten), TECHNOLOGY sheet (113 rows/62 cos — salvaged research that previously reached no sheet), priority queue (SCORES priority_score/rank/cohort; importance×gap; drives all research order), numeric purity enforced at validator (FINANCIALS.value & latest-FY columns plain numbers; currency/unit/period split into *_period columns), task statuses extended (in_progress = live wave; needs-verification = conflict/stale; completed requires result text).

**Waves 1–5 (+5 in flight): 31/31 companies researched from the priority queue upgraded; zero no-ops.**
- Maturity tiers (was 0 / 4 / 41 / 131 / 127 / 65 pre-Phase-3):
  Fully researched **11** · Intelligence-grade **23** · Deep 42 · Enriched 115 · Basic 116 · Candidate 61 — deep-or-better **45 → 76**
- Funding rounds 761 → **882** (+121 genuine, 0 duplicates found in audit)
- FY-tagged revenue rows **131**, profit rows **121** (financial-year filling mandate)
- Primary-upgrade: folded-cohort mean source_quality **37.2 → 86.2**, freshness **46.2 → 92.3**, completeness **30.3 → 74.2** (n=13 measured cohort); 21 companies gained ≥25 source-quality points
- Claims added: +764 net of dedupe; conflicts discovered by agents: +144 (all preserved/resolved, never overwritten)

**Verification wins (orchestration-level QC catching real errors)**
- Porter & Navana agents rejected incorrect founder hints in the orchestrator's own briefs; primary sources confirmed real founders both times
- Spot source-audit of sampled CLAIMS rows re-fetched cited pages: claimed figures present (Mokobara FY25 ₹230 Cr exact match)
- Three orchestrator-side bugs found by measurement, not vibes: sort_keys/[:80] dedup silencing 17 Navi traction facts; conflicts re-append inflation (434→300); company-field no-apply silent failure (InsuranceDekho) — all fixed with P3-APPLY audit visibility. Agents' payloads were correct in every case.

**Data-integrity ledger**: 134 duplicate conflicts removed; 27 duplicate founder rows removed (write-time (sid,name) guard added); 0 duplicate round clusters across wave companies; CONFLICTS & FUNDING stable across refolds (idempotent merge).

## Method notes
- Universe held at 368 through the entire phase; no discovery budget spent (UNIVERSE_AMENDMENTS.md records zero Phase-3 additions)
- Research proceeded strictly by priority (importance×gap), never alphabetically; EXHAUST frontier is recomputed each build — completed companies exit, 37 fresh names promoted so far; frontier continues until no unresearched name scores above the researched floor
- Mumbai/Bengaluru weighting in importance; deep-dive wave companies: Rapido, ShareChat, Zeta, Niyo, VerSe, SatSure, Porter, PharmEasy, Graas, NoBroker, Navi, Upstox, Mokobara, Navana, upGrad, OYO, KGeN, Arohan, Seekho, EscapePlan, CleverTap, Unacademy, Neysa, Snitch, Juspay, InsuranceDekho, SUGAR, RentoMojo, Leap, EloElo, Agrani + wave-6 in flight
