# SPEC — India Startup Intelligence Database (condensed operational contract)
Source: user master prompt, session 2026-09-14 (condensed; rules below are binding on every researcher).

## Scope
India startups & startup-like private companies (venture-backed, bootstrapped, high-growth, emerging; all sectors
incl. fintech/SaaS/AI/deep-tech/climate/health/edtech/D2C/mobility/EV/space/defence/biotech/robotics/gaming/
media-tech/agri-tech/logistics/insurtech/HRtech etc.). Also keep companies widely called "startups" even if now
scale-up / mature private / public / subsidiary / acquired / failed / shut down — preserve historical status.
Priority cities: Mumbai + Bengaluru (deepest), then Delhi NCR/Gurugram/Noida, Hyderabad, Pune, Chennai, Ahmedabad,
Kolkata, Jaipur, Kochi, Chandigarh, Indore, Surat, other hubs.

## Hard rules (NEVER)
- Fabricate values/sources/rounds/URLs; invent citations.
- Present estimates as facts; news-quoted "approx revenue" as audited financials; LinkedIn headcount as audited.
- Infer exact valuation from round size; merge similarly named companies without evidence; confuse parent vs subsidiary.
- Overwrite conflicting data (preserve both + resolution note); average conflicting figures.
- Use internal model knowledge as an uncited field value. Missing → UNKNOWN/blank; legitimate inference → ESTIMATE.

## Always
- Assign stable IDs: startup_id, person_id, round_id, investor_id, product_id, customer_id, event_id, source_id, location_id.
- Attach provenance: source_url + title + publisher + publication_date + retrieved_date + tier + confidence + evidence note.
- Distinguish: incorporated vs founded vs launched vs first-funding vs DPIIT-recognized dates.
- Distinguish: founder vs co-founder vs early employee vs advisor vs angel vs director; CEO changes tracked over time.
- Distinguish announced vs closed funding; cumulative vs single round; valuation vs transaction value vs debt vs revenue.
- Temporal fields: value + effective/as-of date + source date. HQ registered vs operating vs founder location — don't conflate.
- Fact vs estimate vs inference flagged per record (confidence: HIGH/MEDIUM/LOW/ESTIMATE/UNVERIFIED).

## Sources tiering
T1 primary/official (company site/PR, filings, DRHP/RHP, exchange filings, MCA, DPIIT/Startup India, RBI/SEBI/IRDAI/CCI,
courts, patents) > T2 databases (Tracxn/Crunchbase/PitchBook/Venture Intelligence/Dealroom — secondary unless corroborated)
> T3 quality journalism (Reuters, ET, Mint, BS, FT, Moneycontrol, YourStory, Inc42, Entrackr, TechCrunch, TCiR, VCCircle,
DCG/Argus reports) > T4 investor/accelerator pages, interviews, conference profiles > T5 weak (Reddit, social, blogs, SEO
directories) = discovery signals only, never sole evidence for important claims.
Conflict resolution order: primary > newer-for-current-state > audited-for-financials > transaction docs > company PR.

## Sheets & core columns

> SPEC AMENDMENT #2 (2026-09-15, user audit — supersedes the weighted-score description below):
> (a) RESEARCH MATURITY: the binary deep/shallow tier is retired. Each of 12 categories (identity, founders, funding, investors, financials, products, traction, people, customers, legal, events, locations) is scored as OBJECTIVE BANDED COVERAGE: 0 / 2.5 / 5 / 7.5 / 10 = no / limited / moderate / substantial / comprehensive usable data, computed from field-presence + quality checks on linked rows only — agent self-assessments never feed the score. Research Completeness = equal-weighted mean of the 12 bands (0-100).
> (b) FOUR AXES, not one overloaded number: SCORES also reports Source Quality % (tier-weighted evidence: T1=5 / T2=3 / T3=1.5 / other=1 pts; 15 pts = 100%; weak secondary evidence can never equal primary), Freshness % (recency of newest evidence: <=6mo=100, <=12mo=80, <=18mo=60, <=24mo=40, older=20), Conflict Level (none/low/moderate/high from preserved-conflict counts — conflicts stay visible, never silently merged).
> (c) TIERS: <20 Candidate | 20-39.9 Basic | 40-59.9 Enriched | 60-74.9 Deep | 75-89.9 Intelligence-grade | 90-100 Fully researched. Dashboard reports the full distribution; no record is called "deep" without >=60% objective coverage.
> (d) SHEET #23 RESEARCH_TASKS = execution ledger: one row per (startup, research_area) — task_id, startup_id, company, research_area, priority (P1 core-area gap on Candidate/Basic, P2 core touched, P3 non-core), assigned, started, completed, result, next_action, status (completed / logged-no-result / not_started), log_events. RESEARCH_LOG remains the raw audit trail (deduped; `reps` column counts collapsed identical events). Next research is gap-driven: filter RESEARCH_TASKS, not by discovering more companies.
> (e) STARTUPS gains `company_class` (DERIVED): Startup / Scale-up / Mature private company / Public company / Subsidiary / Acquired (operating) / Former startup / Other - status unverified. Dashboard funding figures are labeled as THIS-UNIVERSE totals (dominated by mature/listed corporates), never "Indian startup funding"; Mumbai/Bengaluru comparisons are labeled tracked-sample, not census.
> SPEC AMENDMENT (2026-09-15, user request): STARTUPS gains `official_website` (verified company-owned domain, never an article/aggregator URL) and `careers_website` (verified careers/jobs page, own-site or official ATS). Both carry fetch-verification provenance in RESEARCH_LOG/site files; `website` is promoted to the official value when verified. Empty = no verified site/careers page found (explicit gaps, never guesses).
STARTUPS(compact): startup_id, company_name, legal_name, aliases, website, founded_date, incorporation_date, status,
startup_stage, primary_sector, secondary_sectors, business_model, customer_type, city, state, country, hq_type,
registered_office, employee_estimate, employee_estimate_date, total_funding_disclosed, last_funding_date,
last_funding_round, last_known_valuation, revenue_latest_fy, revenue_latest_fy_year, profit_loss_latest_fy,
dpiit_recognized, cin, parent_company, subsidiary_of, public_private, website_status, last_verified, confidence,
primary_source_id, notes.
FUNDING: round_id, startup_id, round_date, announcement_date, fiscal_year, round_type, amount, currency, amount_inr_mn,
valuation, valuation_type, lead_investor_id, investor_ids, new_or_existing, purpose, source_id, confidence, notes.
FOUNDERS: founder_id, startup_id, name, role_title, founder_type, active, departure_date, education, prev_companies,
linkedin, location, notes/source_id, confidence.
PEOPLE: person_id, startup_id, name, position, start_date, end_date, prev_employer, linkedin, source_id, confidence.
INVESTORS: investor_id, name, type, geography, fund_vintage, notable_portfolio, india_presence, partner_if_public.
INVESTOR_LINKS(in INVESTORS or dedicated): startup_id, investor_id, first_investment, rounds, lead, amount, board_seat,
status, source_id, confidence.
FINANCIALS: fy_record_id, startup_id, fiscal_year, period, revenue, other_income, ebitda, pat, total_assets,
net_worth, debt, employee_expense, other metrics, currency, value_type (audited/management/press-quoted/ESTIMATE),
consolidated, source_id, filing_date, confidence. (Indian FY = Apr–Mar; label FY25 = FY2024-25.)
PRODUCTS: product_id, startup_id, name, category, description, b2b_b2c, pricing_model, launch_date, status, source_id.
CUSTOMERS: customer_id, startup_id, name, type(enterprise/sme/gov/consumer/institutional), announced_date, status, source_id.
PARTNERSHIPS, COMPETITORS, ACQUISITIONS (made/received + type/value/date/buyer/seller/source), LOCATIONS (type:
registered/HQ/office/R&D/mfg/warehouse; city; neighborhood for Mumbai/Blr; status; source), HIRING (headcount
as-of, open-roles signal, layoffs/freeze with date+source), LEGAL_REGULATORY (allegation vs notice vs ruling vs
settlement; regulator; dates; source), NEWS_EVENTS (event_id, date, announced_date, type, headline, description,
source_id, confidence).
SOURCES: source_id, startup_id, url, title, publisher, publication_date, retrieved_date, source_tier, source_type,
claim, supports_fields, reliability, confidence, notes. (One source may support many fields; no fake URLs.)
RESEARCH_LOG: date, company, query_strategy, source_found, useful_info, unresolved, next_action, agent, status.
SCORES: startup_id + 11 category scores + weighted Research Completeness Score:
Identity 10, Founders 10, Funding 15, Investors 10, Financials 15, Products 10, Traction 10, People 5, Customers 5,
Legal 5, Sources 5 (percent weights).
DASHBOARD: totals, by city/sector/stage, funding by year/city/sector, top-funded, recent rounds, most active investors,
unicorns, Mumbai-vs-Bengaluru comparison, charts.

## Prioritization
1 Mumbai/Bengaluru, 2 meaningful funding, 3 recent traction, 4 high growth, 5 unicorns, 6 notable emerging,
7 strategic importance, 8 regulatory activity, 9 major acquisitions, 10 interesting founders/investors,
11 cross-dataset frequency, 12 under-covered promising. Keep low-confidence candidates but label them.

## Stopping rule
Stop per company when: official + major DB + financial + founders/leadership + major events checked, conflicts
investigated, and further searches return mostly duplicates. Record unresolved gaps honestly.

> SPEC AMENDMENT #3 (2026-09-15, Phase 3): (1) Two new sheets — CLAIMS (evidence layer: every factual claim — round amounts, valuations, financials, traction, and all dict-sourced company fields — as its own row with value_type/unit/currency/date_from/date_to/source_id/confidence/status/preferred; summary tables carry the preferred value, CLAIMS carries what supports it) and CONFLICTS (claim_a/source_a vs claim_b/source_b, preferred_claim, resolution, resolution_status ∈ resolved|preserved-conflict|unresolved, last_reviewed; backfilled from prior conflicts[] arrays, 206 preserved — disagreements are data, never overwritten). (2) PRIORITY QUEUE (SCORES T/U/V): priority_score = importance (funding log-scale, revenue, Mumbai/Bengaluru +15, stage, news intensity, marquee-investor presence, strategic sector, recent activity; ×0.2 for Former startup) × gap (100−completeness + conflict bonus + weak-source + stale-evidence). Research proceeds from this queue — never alphabetical. Cohorts: EXHAUST (top 38), TARGET (top 100). (3) Numeric purity enforced: FINANCIALS.value and latest-FY columns must be plain numbers; "Rs X crore"/"$YM" strings are split into value+unit+currency at build (validator rejects otherwise). (4) Temporal discipline: traction/valuation/people/employee facts carry period or as_of; history not collapsed into current state. (5) RESEARCH_TASKS statuses extended: not_started|in_progress|completed|logged-no-result|blocked|needs-verification (last = conflict present or evidence >18mo old); completed requires a result or documented no-result. (6) Universe frozen at 368; additions require a material-omission justification logged in qc/UNIVERSE_AMENDMENTS.md. (7) gapfill/*.p3.json deep-merge protocol: fill-empty + append-dedup lists + conflicts preserved on disagreement, never overwrite.

## AMENDMENT #4 — Phase 4 (2026-09-16): control tower, derived metrics, status semantics
- **RESEARCH_CONTROL sheet** (28th data surface): one row per company — startup_id, company, city, company_class, cohort, priority_rank, completeness/source_quality/freshness/conflict_level, open_tasks, open_P1, verification_tasks, unresolved_conflicts, per-area `*_missing` flags (13 incl. technology), **next_best_action**, last_researched, last_verified.
- **last_verified semantics**: max retrieved_date among HIGH-confidence CLAIMS of the company (CLAIMS→SOURCES join), else max conflict last_reviewed, else latest log date. Distinct from last_researched (log activity).
- **next_best_action engine (§27)**: decision-ordered, company-specific; priority: open founder/identity conflicts → zero-band area actions (area worded actions: identity/founders/funding/financials[which FY]/traction/people/products/customers/legal/locations/events/investors) → sq<50 primary-upgrade → freshness≤40 re-verify → remaining conflicts → cohort floor → maintain. Blank outside TARGET/EXHAUST (no filler).
- **DERIVED_METRICS sheet**: revenue_cagr, loss_to_revenue, revenue_per_employee, funding_to_revenue, valuation_to_revenue. Rules: value_type="DERIVED" mandatory; inputs string carries raw values AND periods in-row; INR-crore series only (mixed-currency denominators EXCLUDED rather than fx-converted); headcount-mismatch flagged indicative-only; never compares incompatible periods without showing both.
- **Fiscal-year purity**: fiscal_year must contain an FY token; bare calendar years/UNKNOWN/N-A route to `period` + note (Phase 3 §8 extension).
- **Task status semantics final**: blocked = ≥2 logged attempts without result (distinct from single logged-no-result); in_progress = payload present in gapfill/ (mechanical); completed carries result or evidence pointer; needs-verification deliberately persists for preserved-conflict companies.
- **§31 dashboard rules**: never counts-as-% of companies; ratio cells are claims/company, companies-with-conflicts %, claims-needing-verification %, T1/T2 claims %, ≥75/≥90 counts, city-split completeness (computed-static, labeled), §25 startup-class vs all-entity funding contrast. CAVEAT cell must not collide with signal rows (row 95+).
- Ship pipeline: merge→build→validate(0)→officecli close→excel_build (28 sheets)→zip audit incl. per-cell non-empty check of §31 block.
