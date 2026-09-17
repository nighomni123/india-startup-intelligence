# PHASE 4 — DEEPEN THE EXISTING INTELLIGENCE · §33 COMPLETION REPORT
As-of 2026-09-16 · workbook: india-startup-intelligence.xlsx (28 sheets) · chain: merge→build→validate(0 issues)→excel rebuild→zip audit

## 1. Machinery shipped (§28/§27/§8/§31/§25)
- **RESEARCH_CONTROL** (368 rows): cohort EXHAUST 38 / TARGET 62 / honest-blank rest; 4 score axes + 13 area-missing flags + open/verification/conflict counts + last_researched vs last_verified (HIGH-claim SOURCES join) + **specific next_best_action on exactly the 100 frontier seats** (§27 decision engine: open identity conflicts → zero-band fills → sq<50 primary-upgrade → stale re-verify → floor-close → maintain).
- **DERIVED_METRICS** (83 rows, all value_type=DERIVED, periods in-row): revenue_cagr 62 · rev/employee 7 · valuation/rev 6 · funding/rev 5 · loss/rev 3. Currency-mixed denominators excluded (not fx-converted); period-misaligned ratios flagged indicative-only.
- **§31 dashboard accuracy block** (DASHBOARD rows 97–106): claims/company ratio, companies-with-conflicts %, claims-needing-verification %, T1/T2 claims %, ≥75/≥90 counts, Mumbai-vs-Bengaluru completeness split, **§25 startup-class vs all-entity funding contrast** (census-framing trap fixed). Live COUNTA/COUNTIF formulas + labeled statics. Bugs fixed en route: CAVEATS A76→A95 (row collision), props-clobber numberformat (18 empty §31 cells — caught only by zip audit, not the build log).
- **Validator**: FK + one-row-per-company + cohort enum + DERIVED purity → **0 ISSUES / 1 informational WARN** at every fold.

## 2. Research waves — 11 waves · 66 dispatches · 63 net upgrades this phase (113 cumulative since P3 baseline)
| W | results (pre→post) |
|---|---|
| P4-1 | Pine Labs 56→87.5I · LeadSquared→93.8F · Drools→81.2 · Edubuk→81.2 · Cradlewise 21→83.3 · Ultrahuman→93.8F |
| P4-2 | Krutrim→91.7F · ThirdWave pass-2 (sq 53→100) · Arya.ag→89.6 · IndiQube→87.5 · Mindgrove→68.8(ceiling) · EatClub→87.5 |
| P4-3 | Chargebee→91.7F · CARS24 21→79.2(sq100) · Ammunic 12.5→81.2 · Euler→87.5 · Fundly→83.3 · Elivaas→89.6 |
| P4-4 | PSL→93.8F · Comet→87.5 · Butterfly→91.7F · VerveSemi→89.6 · Yuma→70.8(ceiling) · Digantara→85.4 |
| P4-5 | Infra.Market→**97.9F** · R-for-Rabbit 21→**97.9F** · Neo→95.8F · Zepto→95.8F(conf high kept) · QNu→89.6 · PumPumPum→87.5(sq43 capped) |
| P4-6 | Meesho 40→**93.8F** · Rebel→93.8F · Rezolv→89.6 · Mitigata→83.3 · Kepler 23→77.1 · VectON 12.5→70.8(sq100) |
| P4-7 | Zetwerk→95.8F · BrowserStack→93.8F · Jumbotail→93.8F · Postman→91.7F(dual-entity) · Nua→83.3 · **Toddle→100.0 F sq100 (first perfect)** |
| P4-8 | **Kiwi→100.0 F** · MuSigma→97.9F · Delhivery→93.8F(exchange quarters) · Livspace→91.7F · Innovist→91.7F · GIVA→87.5 |
| P4-9 | StockGro→95.8F · SqYards→91.7F · Flipkart→91.7F(sq86.7 honest) · Swish→83.3 · Zupee→81.2(litigation statused) · Nestasia 21→79.2 |
| P4-10 | Akasa→97.9F · OfBusiness→97.9F · CynLr→95.8F · Dhan→89.6 · Curefoods→87.5 · Runable→87.5 |
| P4-11 | InMobi→95.8F · Zenoti→91.7F · NexEdge 33→91.7F(key-mismatch recovery) · G24X7→89.6 · VerSe→87.5 · ThirdWave pass-3→81.2 |

**Objective roster check**: all 38 named EXHAUST companies researched; **25/38 ≥85%**; remaining 13 are thin-public-record names whose caps are documented (Mindgrove, Yuma, VectON, Third-Wave-conflict-honest…) — no padding was used to close them.

## 3. Database movement (P3 baseline → final)
| | start | end |
|---|---|---|
| Fully researched (≥90) | 11 | **49** |
| ≥75% (Fully+IG) | ~78 mid | **111** |
| deep-or-better | 91 | **144** |
| CLAIMS | 3,150 | **5,552** (HIGH 3,540 = **63.8%**, LOW only 126) |
| CONFLICTS | ~300 | **774** — 304 resolved / 467 preserved / 3 unresolved |
| SOURCES / LOG | 2.9k / 1.1k | **3,956 / 1,462** |
| FINANCIALS | ~1,150 | **1,410** (FY-tokened 1,356; FY25 667, FY24 303) |
| Mumbai avg completeness | 44.1 | **62.3** |
| Bengaluru avg completeness | 43.2 | **58.9** |
| Universe | 368 | **368 — 0 additions** (UNIVERSE_AMENDMENTS.md untouched) |

## 4. Integrity events (what the machinery caught)
- **Silent no-apply family** (Comet; InsuranceDekho precedent): post-notification re-fold recovers — now standing close-out move per wave.
- **NexEdge canonical_key mismatch** ('nexedge-capital' vs universe 'nexedge capital'): payload skipped cleanly; payload↔doc audit caught; key-fixed re-fold → 33.3→91.7. New check: key-format warning in merge (logged for Phase 5).
- **Mid-write captures** (Toddle invalid 52KB, Mitigata partial): mtime-guard + json.load skip kept the DB clean; finals folded later — zero corrupt data entered.
- MuSigma transport-death → single clean retry (100% eventual delivery across 66 dispatches).
- §13 discipline held on every legal-heavy name (Zupee/G24x7 gaming acts, Akasa DGCA, Dhan/TradingView, Livspace franchise disputes): statuses never blurred from petition→penalty.
- Founder-hint corrections by agents (brief hints treated as unverified; MCA/primary truth won every time).

## 5. Remaining gaps (honest)
- 49 TARGET seats <70% (next queue: Carrum 31.2, IDfy 50, NeoGeo 14.6, Big Mishra 18.8, C2i 47.9 …) — each carries its own next_best_action.
- 972 needs-verification tasks persist **by design** (preserved-conflict hygiene); 538 P1 not_started ≈ same tail; blocked 10 + logged-no-result 49 = documented dead-ends.
- 3 unresolved conflicts await decisive primaries.

## 6. Next-phase recommendation
Phase 5 = TARGET grind 6/wave strictly off RESEARCH_CONTROL ranks; quarterly freshness pass driven by freshness axis; key-format merge warning; universe additions only via amendment-log evidence bar.

## 7. Ship verification
validate_db 0 issues · workbook zip audit appended below (28 sheets, tblResearchControl/tblDerived, §31 B99–B106 non-empty, A95 CAVEAT, 6 charts, 28/28 frozen, FAILURES 0).

### Zip audit (shipped 2026-09-16 05:47) — PASS
28/28 sheets · tail order correct · tblResearchControl+tblDerived present (26 tables) · 6 charts (xl/drawings/charts) · §31 rows 98-106 labels + B99-B106 values ALL non-empty (props-clobber fix verified live: formulas + statics both present) · CAVEATS A95 clear of signals block · 28/28 frozen panes · build log `FAILURES: 0` · file 3,065,729 bytes.
