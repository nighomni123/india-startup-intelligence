# PHASE 3 — FINAL REPORT (intelligence-grade enrichment & verification)
_Final — 2026-09-16 02:12 IST: shipped workbook audited and accepted._

## Headline
- **51 research dispatches across waves 1–8 covering 50 companies off the living priority queue: 50/50 upgraded, 0 payload no-ops, 0 universe additions.**
- Maturity curve (pre → post): Fully researched 0→**17**, Intelligence-grade 4→**30**, Deep 41→41, Enriched 131→109, Basic 127→111, Candidate 65→60
- Deep-or-better: 45 → **88** of 368. Mean completeness 38.6 → **44.6**; median 39.6 → **42.8**. Best record now 97.9 (KreditBee, AgroStar).

## Fact counts (never inflated; dedupe-audited)
| dataset | pre-P3 | now |
|---|---|---|
| CLAIMS (evidence rows) | sheet created | **3,927** — 75% carry source_id, 42% carry explicit date_from |
| CONFLICTS ledger | 206 | **422** (180 resolved w/ preferred value · 239 preserved · 3 genuinely open) |
| FUNDING rounds | 761 | **923** (+162; audit: 0 duplicate clusters) |
| FINANCIALS rows | 544 | **889**; FY24+ rows: 725; companies w/ FY24+ data: 170+ |
| SOURCES | 2,223 | **3,211** (T1 share ↑: folded cohort sq 37→86 avg) |
| TECHNOLOGY (new sheet) | dropped data | 113 rows / 62 companies |

## Primary-source upgrades (§5)
MCA/CIN + incorporation now on dozens of formerly-identity-less records (SatSure, Navana, Mokobara, Apna, BGauss, RentoMojo, Weaver, Tonbo, Graph-AI India subsidiary…); RBI/SEBI/NSE/BXI filings drive Navi, Upstox, Groww, KreditBee, PhonePe, Weaver, Arohan, InsuranceDekho; CCI order for Porter; EPFO-backed headcounts where cited. Aggregator-only claims down 63%→25% on the 13-company pilot cohort.

## Verification events
- Three orchestrator-brief contaminations caught by agents verifying sources: Porter founders, Navana founder (Dr Banga belongs to Balbix), Graph AI sector description. Each resolved primary-first; DB never received the bad hint.
- Three orchestrator-side data bugs caught by measurement, fixed, post-mortemed in wave_log: sort_keys/[:80] traction silencing (17 facts), conflicts re-append inflation (→ deduped −134), company-field silent no-apply (+P3-APPLY audit prints); plus founder case-dup fix (−27 rows) and write-time (sid,name) guard.
- 42-claim spot source-audit incl. verbatim match (Mokobara ₹230 Cr FY25).

## Remaining gaps (honest)
- 60 Candidate + 111 Basic remain — mostly outer-ring/former-startups by design (×0.2 importance); queue continues to surface names but at lower marginal value.
- needs-verification tasks (644 at last build) — by design: preserved conflicts and stale evidence stay open for human review; 3 conflicts genuinely unresolved (OYO mgmt-vs-filing PAT/revenue; 1 empty-side).
- Private-company FY24/25 financials unavailable below filing thresholds — left as gaps, not estimates.
- Customers area remains the scarcest category outside folded companies (evidence rule: no logo-inference).

## Workbook
26 sheets (23 + CLAIMS, CONFLICTS, TECHNOLOGY) + named tables + 6 charts + frozen panes; dry-run FAILED=0 accepted. **Shipped 2026-09-16 02:12 — audit PASS**: 2,326,674 bytes · 26 sheets (CLAIMS/CONFLICTS/TECHNOLOGY before DASHBOARD) · 24 named tables incl. all Phase-3 tables · 6 charts · 26/26 frozen panes · dashboard cross-formulas resolve (CLAIMS×1, CONFLICTS×3, RESEARCH_TASKS×8 incl. new needs-verification/no-result/blocked counters) · build log FAILURES: 0, officecli validate ok=True.
Final counts: CLAIMS 3,994 · CONFLICTS 433 (181 resolved, 249 preserved, 3 open) · ROUNDS 929 · SOURCES 3,229 · upgraded 50 companies; tiers FR 19 / IG 31 / Deep 41 / Enriched 106 / Basic 111 / Candidate 60.
