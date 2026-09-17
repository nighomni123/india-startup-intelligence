# Missing-Data Register — India Startup Intelligence Database (as of 2026-09-14 build)

Companion to QUALITY_REPORT.md. Percentages = column fill across the shipped CSVs in `build/csv/`.

## 1. Universe-level backlog (biggest gap by volume)
- **284 of 367 STARTUPS rows are shallow** (confidence UNVERIFIED, "Shallow candidate: discovery-layer only") — name + sector guess + 1 discovery source only. These drag every sheet; enriching them is the single highest-yield next action (machine-findable: SCORES.completeness_pct < 30).
- **47 rows have no city** (listicle sources gave no HQ evidence; never guessed).

## 2. STARTUPS columns with thin coverage (of 367 rows)
| Field | Filled | Why missing / how to close |
|---|---|---|
| aliases, subsidiary_of, website_status | 0% | never populated; derivable for groups (Tata/Reliance-adjacent, post-acq) |
| cin / incorporation_date / registered_office / parent_company | 1–2% | MCA/ROC not machine-accessible here → paid API (Tofler/CinAPI) or manual MCA search |
| dpiit_recognized | 3% | registry bulk list not downloadable; per-company only where news names it |
| employee_estimate(+date) | 10%/2% | LinkedIn not scrapeable; only when press quotes a headcount |
| hq_type | 10% | only enriched companies; needs legal-registered vs operating split per row |
| last_known_valuation | 8% | = enriched+IPO cos only |
| revenue/profit_latest_fy | 11–19% | tied to §1; press-quoted filings only |
| founded_date/legal_name/website/business_model/customer_type | ~20–22% | shallow backlog again |
| Fully empty cols in sibling sheets | — | FOUNDERS: linkedin/prev_companies/departure_date/location (0%); INVESTORS: type/geography/india_presence/notable_portfolio/fund_vintage (0–2%); FINANCIALS: basis/consolidated/filing_date/period (0%); PARTNERSHIPS: type/purpose/duration/status (0%); PRODUCTS: pricing_model/b2b_b2c (0%); ACQ: counterparty (0%); FUNDING: new_or_existing (0%), valuation+round_date ~41% |

## 3. Per-company gaps inside the 83 DEEP/LITE records (328 logged gap entries)
Theme counts: **CIN/incorporation 68 · audited-MCA financials 60 · early/private round history 34 · headcount 33 · DPIIT 23 · founder current-role status 18 · post-2024 valuation 13 · debt terms 8 · hq-registered-vs-operating 6 · litigation-confirmed-absent 6 · named customers 5 · consolidated global figures 4 · investor stake % 3 · acquisition terms 2.**
Notable specifics: Nykaa/Fineats/DeHaat etc. FY25 audited numbers exist in MCA PDFs but were not machine-pullable; Zepto/Meesho FY25/26 filings pending at press time; BrowserStack consolidated (Irish domicile) financials; Neysa debt close status; Square Yards legal name/CIN; OfBusiness Series A–F ladder.

## 4. Provenance holes (SOURCES spine)
- **210 field-claims quarantined**: enrichment JSONs stated facts without any URL → kept as notes text only, NOT in the claim→source join. Closing = finding real articles, never inventing one.
- **10 DEAD source URLs (HTTP 404 at linkcheck)** — downgraded to LOW, listed in QUALITY_REPORT §5 (Pixxel ×4, Udaan TNW, Yahoo/Nykaa call page, Shashvat wiki, SquareYards blog, Tracxn explore). Facts survive only at vault snippet level → need replacement sources.
- **124 bot-blocked URLs (403/429)** — pages were vault-captured at fetch time, but re-verification from browser is blocked to scripts; treat as medium-confidence anchors.
- publication_date missing on 40% of SOURCES rows.

## 5. Unresolved conflicts preserved (114 entries, by design not averaged)
Heaviest: total-raised totals (Tracxn vs press, e.g. upGrad $320M vs $766M; Skyroot $160M vs $100M), valuation epochs vs stale marks (Rapido, Dream11, Mu Sigma, MoEngage), FY scope (consolidated Singapore vs India standalone — Moglix, Lenskart), round-amount headline vs primary-only (Innovaccer $275M vs $179M; Rapido $730M vs $240M), founder-co-founder naming (Mu Sigma), co-reported vs audited revenue (Pristyn, BharatPe).

## 6. Sheets that are structurally sparse (fewer rows than companies)
CUSTOMERS 27 rows (only named-enterprise-customer press), PARTNERSHIPS 12, LEGAL_REGULATORY 15 (litigation "confirmed absent" is itself unverifiable), HIRING 24, PEOPLE 26, PRODUCTS 96 — mostly because the 284 shallow rows contribute nothing.

## 7. Methodological limits (cannot currently be closed here)
MCA paid-API absence · DPIIT bulk list · LinkedIn/Instagram scraping · paywalled ET/BS article bodies (headline+snippet only) · private-company debt schedules · any "as-of-today" liveness (all data stamped 2026-09-14).

---

## SESSION-2 FURNISHING RUN — before/after (numbers finalize at ship; interim as of merge #6)
| Gap (from §1–§4 above) | BEFORE (V1) | NOW (interim) | Remaining |
|---|---|---|---|
| Shallow (UNVERIFIED) rows | 284 | 10 (final S2 b22/b23 in flight) | ~0 expected |
| Rows w/o city | 47 | 0 (last: NeoGeo=Gurugram w/ Entrackr cite) | — |
| cin coverage | 1–2% | **47%** | rest w/o public aggregator hit |
| incorporation_date | ~2% | **39%** | same |
| website / website_status | 21% / 0% | **official_website 99% of active (340/343) + careers_website 69% (237) — verified-or-blank; 3 honest verified-misses + 1 collapsed brand** | see WEBSITE REPAIR WAVE below |
| revenue_latest_fy | 11–19% | ~43% | FY25 filings paywalled |
| INVESTORS type/geo | 0–2% | 25%/20% (IV-00/01/04/05 done; 02/03 re-run pending) | long tail |
| FUNDING new_or_existing | 0% | 64% DERIVED (investor-repeat chronology) | 126 rows lack investor_ids |
| ACQ type + counterparty | 0% | 85% / 81% value (ACQ waves folded; 52 rows) | rest = private deals w/o public terms |
| Founder active-status | 0% | 74% (FS waves folded; unknowns left blank per no-guess) | LinkedIn URLs rare in SERPs (0%) |
| parent/subsidiary | 0% | 10 groups extracted from sourced notes | rare by nature |
| Quarantined no-URL claims | 210 | ~65 resolved w/ URLs or corrections; 174 = field-name bookkeeping noise (documented) | — |
| DEAD source URLs | 10 | 5 replaced live by re-sourcing, 4 archive-wired, 1 backed by live dup | — |
| Bot-blocked re-capture | 124 | 0 capturable via tinyfish lane (tested all) → documented dead end; vault captures stand | — |
| Defunct handling | mixed into backlog | 20+ status-only records, excluded from enrichment per order | — |
| validate_db | 0 issues (V1) | 0 issues / 0 warnings (mid-run re-checks) | final at ship |
| Completeness mean | 20.5% | 43.6% | — |
| Companies ≥60% | 43 | 75 | — |

## WEBSITE REPAIR WAVE (user-requested, 2026-09-15)
- NEW COLUMNS: official_website 340/343 active (99%), careers_website 237/343 (69%) — both live-verified (curl probe → agent hyperresearch fetch → Playwright chromium render), each with src provenance in gapfill/*.site.json / *.careers.json.
- Legacy website column: 121 aggregator/article URLs (wikipedia/techcrunch/etc.) replaced by verified own-domains; blanks only where a verified miss was recorded (Good Glamm collapsed, Graph AI US-HQ, Climatech parked-domain, Baaz Bikes offline).
- Shadow-duplicate bug found+fixed: merge fallback wrote new slug files beside canonical ones (16 folded back; load_enrich now returns real write-path).

## Phase-3 status refresh (2026-09-16 ~01:25)
- 36 names researched from the living priority queue are now Intelligence-grade+ (14 Fully / 23->24 IG); waves 6b/7 in flight.
- Task ledger: 460 completed / 644 needs-verification (conflict or stale-evidence; open by design) / 58 logged-no-result / 6 blocked (multi-attempt dead ends) / 2,185 not_started (frontier + TARGET tail).
- Biggest remaining systemic gaps: ~61 Candidate-tier mostly outer-ring + Former startups (documented, deprioritized ×0.2); customers remains the scarcest area outside waves (evidence discipline: no logo inference); several pre-2023 companies lack FY24/25 financials (private-filing limits; not fabricated).
- Website/careers scoreboard unchanged: official_website 99% of active; verified misses documented above.
