# Phase 5 Table Schemas

## CHANGE_LOG
change_id, startup_id, entity_type, entity_id, field, old_value, new_value, change_type, detected_date, effective_date, source_id, claim_id, verification_status, confidence, materiality, summary

## INTELLIGENCE_EVENTS
event_id, startup_id, event_date, event_type, materiality, title, summary, old_state, new_state, evidence, source_ids, claim_ids, confidence, status

## UPDATE_QUEUE
update_id, startup_id, reason, detected_change, priority, required_action, source, status, assigned, created_at, completed_at

## SIGNAL_HISTORY
startup_id, signal_type, previous_value, new_value, change_date, trigger_claim, trigger_event, confidence

## INTELLIGENCE_FEED
date, startup, event, why_it_matters, old_state, new_state, evidence, confidence, sector, city, materiality

## FRESHNESS
startup_id, field_group, last_verified, age_days, freshness_status, priority

## ALERTS
alert_id, startup_id, alert_type, materiality, event_date, summary, evidence, confidence, status

## SNAPSHOTS
snapshot_id, snapshot_date, description, companies_included, changes_since_previous, status

## DATABASE_DIFF
diff_id, snapshot_a, snapshot_b, category, old_value, new_value, count, notes

## SOURCE_SNAPSHOTS
source_id, url, title, first_seen, last_seen, content_fingerprint, tier, status
