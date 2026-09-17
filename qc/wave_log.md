# Session-2 orchestration log
- P0 mapping recovery: startup_stage/public_private/state/country/leads/date/type/parent-subsidiary/financials.tier mappings added; aliases+website_status mechanical fills; quarantined list full dump (structured/quarantined.csv, 210).
- P1: 3/10 dead urls have true wayback archives (wired into SOURCES notes); 7 need replacement articles (Q-wave). recapture_blocked.py running over 124 bot-blocked via tinyfish /fetch -> qc/botblocked_capture.csv.
- Wave S1 (40 top shallow, 5/batch): b00-b02 opencode OK-launch; b06-b07 kilo launch; b03-b05 FIRST ON MISTRAL = 3x transport failures (zero output) -> canary retry #9 failed again -> pool declared dead, redistributed to opencode (#10-12).
- Concurrency now: 5 opencode + 2 kilo searchers.
- Next on completions: file-existence verification per batch, then G-wave dispatch (17 batches over 3 active-enriched slots/wave), Q-wave (10 batches), S2/S3 waves; merge_gapfill -> build -> linkcheck new urls -> validate -> excel rebuild -> report update.

- FOLLOWUP: Ninjacart Tracxn 'Under CIRP' flag unresolved vs active $6M raise — needs targeted resolution before final report. g07/g08 delivered 10/10 CIN+inc dates.

## Round-2 audit (S1 completion → 8-wave fleet)
- **P0 found: build_tables was CRASHING mid-loop since ~mid-session** (dict-valued `name`/`city` fields from agent files) — all "successful-looking" builds wrote stale CSVs. Fixed: dict coercion in person()/investor(), scalar-safe city/website, dump-time confidence+date normalizers, city parenthetical→notes.
- **P0 found: parse_money bare "N Cr" → labeled USD** (unit inflation across any agent omitting ₹ prefix). Fixed at root; validator back to 0 real issues (auto-titles added; JustAI entity-match-risk annotated instead of silently merged).
- S1 40/40 ✓; S2 15/50→(b10-b12 in flight); S3 b00-02 30/30 landed, **3 defunct status cards** (gate working); G g00-g14 merged/pending, tail g15/16+cities dispatched; IV investors_00/01 on disk (02/03 in flight).
- Agent-file-path discipline: relative `gapfill/` from enrich cwd produced `enrich/gapfill/` sink (30 G files recovered from it); ALL prompts now absolute-path-forced.
- Agent write truncation ~8KB → 6,500-char cap + json.load verify + merge salvage.
- Bot-block re-capture (tinyfish lane): 124/124 attempted, 0 recovered → lane exhausted; documented dead end.
- POOL HEALTH: opencode began dying at prompt/transport (55,60,61,63 zero-output) alongside dead mistral; all re-runs routed to kilo. Kilo: zero transport deaths all session.

## Round-4 highlights
- validate_db: **0 ISSUES 0 WARNINGS** interim (city 100% incl. NeoGeo=Gurugram Entrackr-cited; smallest.ai entity-risk annotated; atlys 'batch-file' placeholder URL killed via host-dot rule; archive-map shape crash fixed — another silent-stale-CSV class).
- Linkcheck #2: 1965 urls → 1522 OK / 379 botblocked / 24 DEAD / 40 ERR; wayback resweep +4 TRUE archives (prior '10' included false-positive homepage bounces; corrected map = 4 wired).
- Defunct status cards: 20 (active-only gate). Enriched 344/367.
- Pools: kilo ~93% (one transport death #64, 3/5 files had landed; remainder recovered by #74); opencode degrading (4 zero-output deaths); mistral dead; copilot pool now in test (#75,#78). IV files: 91 investor metas.

## Money-parse post-mortem (user-reported: Traqo Seed "$998M @ $6M val")
- Root cause 3rd class: parse_money USD branch had no K/thousand unit → "$998K" → 998 MN (×1000 inflation). Affected 5 rounds (traqo, cynlr seed, vervesemi seed, foxtale seed, dialflo USD-parenthetical). Fixed; dialflo additionally reordered to INR-priority when Rs/crore markers present.
- Root cause 4th class: valuation RANGES ("$7-9 billion") matched only the first digits and dropped the unit → 7.0 instead of 7000 (groww IPO, upstox SerC, oyo IPO). Fixed with range branch: low end stored + notes "valuation range per source: … (low end stored)" — no averaging, per spec.
- Post-fix sweep: amount>>5x valuation outliers = 0 remaining; validate 0/0.
- Lesson logged: agent raw strings were CORRECT in every case — three of the four money bugs live in MY normalizer, which is why the workbook-level skim audit matters.

## PRECISION UPGRADE (post-website wave, 2026-09-15, user audit driven)
- Tier logic rebuilt: hard-coded deep/shallow retired → 6-band research-maturity tiers on objective banded coverage (score_company rewritten; agent self-assessment no longer blended). Result: 65 Candidate / 127 Basic / 131 Enriched / 41 Deep / 4 Intelligence-grade / 0 Fully researched.
- 4 axes in SCORES: completeness | source_quality_pct (T1=5/T2=3/T3=1.5 pts ÷15) | freshness_pct | conflict_level.
- Sheet 23 RESEARCH_TASKS (2,932 rows): per-(startup,area) ledger with status/priority; not_started+P1 = the gap-driven research backlog (replaces "discover more companies").
- RESEARCH_LOG: real per-entry dates (was forced 2026-09-14), deduped 1,239→872 with reps counts (Pync status-gate spam collapsed).
- STARTUPS.company_class DERIVED (Startup 147 / Scale-up 62 / Mature private 29 / Public 30 / Subsidiary 4 / Acquired-op 7 / Former 24 / Other-unverified 65). Dashboard relabels: funding totals = universe-tracked not ecosystem census; Mumbai/Bengaluru = tracked sample not census; top-funded rows tagged with class; caveats block added.
- SPEC amendment #2 + QUALITY_REPORT addendum. Workbook rebuild: 23 sheets.

## Phase-3 Wave-1/2 post-mortem: merge-handler dedup bug (2026-09-16)
- `.p3.json` list dedup used `json.dumps(x, sort_keys=True)[:80]`. With sorted keys, long shared prefixes (as_of/company_reported/confidence) pushed `metric` past char 80 → **17 of Navi's 20 traction facts silently dropped**; verse locations collided at 160 too (160-char addresses).
- Caught by an under-application audit (file counts vs doc counts across all merged p3 files), not by the happy path. This is the **third orchestrator-side bug discovered by Wave processing** (after parse_money K-units and the normalizer-order issue). Agents' data was again correct.
- Fix: per-list **semantic identity keys** (traction=(metric,value,unit,period,as_of), rounds=(type,date,amount,currency), locations=(type,address[:60],city,as_of)…). Re-folded; audit shows 0 under-applied, no duplicate inflation; navi traction 3→23, verse locations 1→2.
- Lesson stands: a successful merge count is not evidence the data landed. Observe the result.

## Phase-3 research waves (per-wave ledger)
- **Wave 1 (9/9 up)**: Zeta 35.4→91.7F · Rapido 39.6→95.8F · Porter 39.6→85.4I · PharmEasy 47.9→89.6I · ShareChat 41.7→93.8F · Niyo 18.8→89.6I · VerSe 14.6→79.2I · SatSure 12.5→85.4I · Graas 31.2→91.7F. Caught: parse/normalizer bugs (see above post-mortems), Porter founder-hint rejected by agent with EY/Outlook primaries.
- **Wave 2 (5/5 up; CleverTap 1st attempt died, retried W4)**: NoBroker 35.4→93.8F · Navi 39.6→93.8F (RBI actions statused; entity split) · Upstox 54.2→89.6I · Mokobara 31.2→81.2I · Navana 35.4→89.6I (founder-hint rejection #2).
- **Wave 3 (6/6 up)**: EscapePlan 43.8→87.5I · Seekho 45.8→89.6I · upGrad 54.2→91.7F · KGeN 45.8→87.5I · Arohan 43.8→95.8F · OYO 45.8→93.8F. Caught: conflicts re-append inflation → semantic dedup everywhere.
- **Wave 4 (6/6 up)**: CleverTap-retry 31.2→89.6I · Neysa 54.2→83.3I · Unacademy 41.7→87.5I · Snitch 43.8→87.5I · Juspay 58.3→95.8F · InsuranceDekho 18.8→83.3I. Caught: silent no-apply fold (fixed via manual apply + P3-APPLY audit prints).
- **Wave 5 (6/6 up)**: Agrani 27.1→72.9D · EloElo 45.8→89.6I · SUGAR 41.7→93.8F · RentoMojo 35.4→79.2I · Leap 54.2→89.6I · Foxtale (pending at write time).
- **Wave 6 (in flight)**: PhonePe, Ninjacart, Skydo, Apna, BGauss, Avammune.
- Cumulative upgrade record: **31 attempts, 31 upgrades, 0 no-ops.** Fold hygiene: 134 dup conflicts removed, 27 dup founder rows removed, 0 dup rounds; CONFLICTS/FUNDING counts stable across refolds.
- Wave-8 note: Graph AI agent REJECTED the orchestrator brief's sector description ("edge AI construction cameras") — verified via sources that the entity is the pharmacovigilance company already in doc (third brief-contamination catch: Porter, Navana, Graph AI). Agent found Hyderabad subsidiary CIN, founders w/ titles, $3M seed (Bessemer) + $13.3M Series A (Insight, Sep-2026) — all sourced; "IIT grads" and "$1.5M round" unconfirmed → logged no-results.
- **Wave 6 folded (6/6)**: PhonePe 62.5→91.7F · Ninjacart 43.8→91.7F · Apna 35.4→95.8F · BGauss 39.6→89.6I · Avammune 35.4→70.8D (thin public record, honest) · [Skydo deferred → folded with W8].
- **Wave 7 folded (6/6)**: Weaver 58.3→91.7F · TrueMed 60.4→89.6I · Groww 62.5→87.5I(sq100) · Eruditus 50→87.5I · XpressBees 31.2→85.4I(sq40 honest) · Third Wave 47.9→72.9D(sq53 DRHP-press only).
- **Wave 8 folded (6/6)**: KreditBee 62.5→**97.9F** · AgroStar 41.7→**97.9F** · Tonbo 18.8→89.6I(sq100) · GraphAI→70.8D (brief sector-error caught, #3) · Yulu 56.2→95.8F · HerSpace 41.7→77.1I · +stragglers Foxtale→64.6D & Skydo→95.8F.
- **Program total: 51 agent dispatches → 50 companies upgraded, 1 dispatch died (CleverTap #1, retried successfully), 0 silent failures after P3-APPLY instrumentation, 0 universe additions.**
- Final CONFLICTS rise to 433 verified as genuine research yield (no exact dups remain in any doc; deep-wave companies average 5–10 documented disagreements, all preserved w/ sources).

## Phase-4 research waves (EXHAUST-deepening ledger)
- **P4 machinery**: RESEARCH_CONTROL (§28) + specific next_best_action engine (§27) + DERIVED_METRICS (§8, value_type=DERIVED, inputs+periods in-row, currency-homogeneous) + §31 accuracy dashboard (ratios not raw-count %, Mum/Beng split, computed-static values labeled) + validator extension (RC uniqueness/cohort enum, DM purity). Dry-28 build: 28 sheets, FAILURES 0. Bug caught in dry zip audit: §31 static cells clobbered by props-assignment (A(c_) overwrote value/formula inside props) — fixed (`props["numberformat"]=` instead of `props={...}`); will verify non-empty in ship audit.
- **P4-W1 (6/6)**: Pine Labs 56.2→87.5I · LeadSquared 58.3→93.8F · Drools 37.5→81.2I · Edubuk 43.8→81.2I · Cradlewise 20.8→83.3I · Ultrahuman 50→93.8F. Lesson: agents re-write payloads just before completion — fold must re-run post-notification (write-race), payload↔doc audit each time.
- **P4-W2 (6/6)**: Krutrim 58.3→91.7F · ThirdWave pass-2 sq 53→100 (77.1I, primary-upgrade pattern works) · Arya.ag 37.5→89.6I · IndiQube 22.9→87.5I · Mindgrove 18.8→68.8D (source ceiling honest) · EatClub 54.2→87.5I.
- **P4-W3 (6/6)**: Chargebee 41.7→91.7F · CARS24 20.8→79.2I(sq100; needed post-notification refold) · Ammunic 12.5→81.2I · Euler 37.5→87.5I · Fundly 27.1→83.3I · Elivaas 35.4→89.6I.
- **P4-W4 running**: PSL, Comet, Butterfly, VerveSemi, Yuma, Digantara.
- Frontier mechanics confirmed: EXHAUST = seats of MOST-NEEDED research; upgraded companies exit it (≥85 floor satisfied by exit condition, cohort membership ≠ completion). Universe remains exactly 368.
- **P4-W5 (6/6)**: Infra.Market 56.2→**97.9F** (filing-lane) · R-for-Rabbit 20.8→**97.9F** (FirstCry parent chain documented) · Neo 45.8→95.8F · Zepto 62.5→**95.8F** (conflict_level=high kept: IPO-figure disagreements preserved) · QNu 54.2→89.6I · PumPumPum 41.7→87.5I but sq 43 (thin sourcing honestly capped). Pumpumpum needed post-notification refold again (write-race normal).
- Cumulative after W5: **79 unique companies upgraded since P3 baseline · 119 deep+ · 28 Fully · 78 ≥75%** · CLAIMS 4,712 · CONFLICTS 569 · DERIVED 63 · validate 0 issues every fold · universe 368 (0 adds).
- **P4-W6 running**: Meesho, Rebel Foods, VectON, Kepler, Rezolv, Mitigata.
- **P4-W6 (6/6)**: Meesho 39.6→93.8F (IPO filings) · Rebel 58.3→93.8F · Rezolv 35.4→89.6I · Mitigata 31.2→83.3I (partial-capture refold handled) · Kepler 22.9→77.1I (KSO disambiguation done) · VectON 12.5→70.8D(sq100).
- Cumulative: **85 unique upgraded · 125 deep+ · 30 Fully · 83 ≥75%** · CLAIMS 4,836 · validate 0 issues · 0 universe adds.
- **P4-W7 running**: BrowserStack, Nua, Jumbotail, Zetwerk, Toddle, Postman (dual-entity guard noted).
- **P4-W7 (6/6)**: Zetwerk→95.8F · BrowserStack→93.8F · Jumbotail→93.8F · Postman→91.7F (dual-entity done) · Nua→83.3I · Toddle 52.1→**100.0 F sq100** (first perfect record; mid-write-capture skip then final fold).
- **P4-W8 (6/6)**: Kiwi→**100.0 F** · MuSigma 60.4→**97.9 F** (transport-death retry #2 pattern) · Livspace 37.5→91.7 · Innovist 50→91.7 · Delhivery 50→93.8 (exchange lane) · GIVA 54.2→87.5.
- Program: **97/98 dispatches upgraded (1 transport death retried ok, 0 silent failures)** · Fully researched 40 · deep-or-better 134 · CLAIMS 5,139 · CONFLICTS 668 (all preserved/deduped) · DERIVED 73 · universe 368, 0 adds · validator 0 issues every fold.
- Next: TARGET-head waves toward 70%+, Third Wave pass-3 conflict resolution, then ship: final chain + 28-sheet rebuild + zip audit (verify §31 props-fix cells non-empty) + §33 report + SPEC/README.
- **P4-W9 (6/6)**: StockGro 60.4→95.8F · SqYards 58.3→91.7F · Flipkart 39.6→91.7F (sq 86.7 — entity web honest; conflicts high) · Swish 47.9→83.3I · Zupee 52.1→81.2I (litigation statuses kept distinct) · Nestasia 20.8→79.2I.
- Program: **103 unique upgraded / 104 dispatches** (1 transport death retried) · Fully 43 · deep+ 139 · CLAIMS 5,280 · universe 368 flat.
- TARGET still sub-70: 49 (of 62 seats; frontier rotates as usual).
- **P4-W10 (6/6)**: CynLr→95.8F · Dhan 60.4→89.6I (333-fact doc, TradingView episode statused) · Curefoods→87.5I (brand-exactness held) · Akasa→97.9F · OfBusiness→97.9F · Runable→87.5I. Cumulative **109/109 dispatched companies upgraded; 109 payloads; Fully 46, deep+ 142**.
- **P4-W11 (6/6)**: InMobi→95.8F · Zenoti→91.7F · G24X7→89.6I (GST/ban statuses distinct) · VerSe 79.2→87.5I · ThirdWave pass3→81.2I (400+ fact doc; founded_date: resolution attempts logged, conflicts preserved-honest) · NexEdge→91.7F (RECOVERY: agent wrote canonical_key 'nexedge-capital' mismatch → silent skip; manual key-fix + re-guard fold; NEW gate: payload↔key check).
- Conflicts ledger: 756 total · 300 resolved · 453 preserved-conflict · 3 unresolved.
- P4 research CLOSED: 11 waves, 66 dispatches, 113 names upgraded, 0 universe adds. → SHIP: final chain + 28-sheet rebuild + zip audit + §33.
- **P4-SHIP (2026-09-16 05:47)**: final chain clean → 28-sheet rebuild FAILURES 0 → zip audit PASS (28 sheets/tail order ✓ · tblResearchControl+tblDerived ✓ · 6 charts under xl/drawings/charts ✓ · §31 A98-A106 + B99-B106 ALL non-empty (props-fix live-verified) ✓ · CAVEATS A95 ✓ · frozen 28/28 ✓ · 3,065,729 B). README-sheet Phase-4 paragraphs verified (earlier "empty" reading = audit-script regex artifact, logged honestly). PHASE4_REPORT.md final §33 complete; SPEC amendment #4 in.
