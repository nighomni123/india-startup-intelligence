# Phase 5 — Change Detection Rules (focused design)

Per specification §14, §28, §4, §15–18.

## Materiality classification
- CRITICAL: major financing, IPO, acquisition, shutdown, major regulatory action, founder departure, major restatement, restructuring.
- HIGH: CEO/CFO/CTO change, large funding, major product launch, major partnership, major hiring change, geographic expansion.
- MEDIUM: meaningful financial update, new investor, product update, new customer, moderate hiring change.
- LOW: minor website change, small job-opening variation, small descriptive change.

## Funding detection rules (§14 — Funding)
- Compare new round to known rounds by (startup, round_type, approximate_amount_range, source_date).
- Prevent cumulative/accumulated announcements from being counted as new rounds.
- Require primary / transaction source for HIGH/CRITICAL events.
- If amounts/dates differ across sources, create claim versioning (old/new) and queue verification — do not overwrite preferred state until verified.

## Revenue detection rules (§14 — Revenue)
- Identify fiscal year, entity (standalone/consolidated), source quality.
- Compare against existing claim; if supplementary, retain both; if contradictory, preserve both and mark preferred only with stronger source.

## Leadership detection rules (§14 — Leadership)
- Verify old CEO actually departed (not just new name appearing in press).
- Record successor + effective date.
- Preserve historical leader info; do not delete old state.

## Hiring detection rules (§14 — Hiring)
- Compare against prior observation; avoid interpreting seasonal changes as structural momentum.
- Require sustained change (>1 observation window) before accelerating/decelerating signal.

## Source monitoring profiles (§5)
- Tier A companies: company website, newsroom, investor announcements, regulatory (MCA/SEBI/RBI/CCI), reputable media, hiring pages.
- Tier B: funding, financials, leadership, products, major events, legal.
- Tier C: event-triggered only.
- Source tier hierarchy: T1 (gov/regulatory/exchange), T2 (data/transaction), T3 (reputable media), T4 (industry/specialized), T5 (social/unverified). Do not treat equally.

## Deduplication / noise rules (§28)
- Website redesign ≠ business change.
- Duplicate article ≠ new event.
- Repeated funding announcement ≠ new round.
- Seasonal hiring fluctuation ≠ structural momentum.
- Edited article ≠ new event.
- Use deterministic IDs (hash-based) to prevent duplicate claims/events/sources.

## Refresh windows (§15)
- Very high frequency: news/events, funding, regulatory, leadership.
- Medium: hiring, product launches, partnerships, technology.
- Low: company identity, founder education, historical info, patents, stable corporate facts.

## Zero-fabrication (§35)
- Unknown / unresolved conflict is acceptable.
- No invented company events.
- No exact numerical inference without evidence.
- Source-backed only.
