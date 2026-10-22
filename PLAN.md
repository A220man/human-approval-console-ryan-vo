# Product development plan

Each round completes one feature or repair. Future items are planned, not implemented claims.

## Current round

webhook-delivery-history

## Roadmap

### action-queue-risk-scoring — Autonomous agent action queue ingestion and multi-factor risk scoring engine

Status: done

Acceptance:
- Ingests agent action proposals via POST /api/actions with automated blast radius, reversibility, and resource criticality scoring
- Enforces deterministic policy guardrails with regex pattern matching and auto-reject violation rules
- Lists and filters proposals by status, risk tier, and action type with queue summary metrics

Implementation: `backend/app/api/routes_actions.py`, `backend/app/services/risk_engine.py`, `backend/app/services/policy_engine.py`, `frontend/src/components/ActionQueue.tsx`

Tests: `backend/tests/test_actions_and_reviews.py`, `backend/tests/test_risk_engine.py`

### role-based-human-review — Role-based human-in-the-loop review workflow and parameter modification

Status: done

Acceptance:
- Requires analyst role for standard reviews and administrator role for critical risk proposals
- Supports APPROVE, REJECT, and MODIFY_AND_APPROVE with mandatory decision rationale
- Re-scores modified payloads before approval, blocking escalation beyond reviewer authority

Implementation: `backend/app/api/routes_reviews.py`, `frontend/src/components/ActionDetailModal.tsx`

Tests: `backend/tests/test_actions_and_reviews.py`, `backend/tests/test_auth.py`

### cryptographic-receipt-chain — Cryptographic approval receipts and tamper-evident audit hash chain

Status: done

Acceptance:
- Generates immutable HMAC-SHA256 signed receipts chained to prior receipt hash for every review decision
- Provides single receipt verification and full ledger unbroken chain continuity verification
- Supports Markdown export of cryptographic receipts with signed manifests

Implementation: `backend/app/api/routes_receipts.py`, `backend/app/services/receipt_service.py`, `frontend/src/components/ReceiptsView.tsx`

Tests: `backend/tests/test_receipt_atomicity.py`, `backend/tests/test_receipts_and_eval.py`, `frontend/src/test/ReceiptsView.test.tsx`

### action-ttl-expiration — Automatic action proposal expiration sweep and review refusal

Status: done

Acceptance:
- Proposals past expires_at automatically transition to expired status during queue operations
- Expired proposals log ACTION_EXPIRED to audit log and cannot be claimed or reviewed
- UI reflects expired status badge and disables review action forms

Implementation: `backend/app/api/routes_actions.py`, `frontend/src/components/ActionDetailModal.tsx`

Tests: `backend/tests/test_actions_and_reviews.py`

### audit-trail-timeline — Action audit trail inspection and timeline tracking

Status: done

Acceptance:
- GET /api/actions/{action_id}/audit-trail returns chronological audit entries with actors, roles, event types, and structured details
- ActionDetailModal presents an interactive audit trail activity log showing full chain-of-custody history
- Validates role-based access control and handles 404 for missing actions

Implementation: `backend/app/api/routes_actions.py`, `backend/app/models/schemas.py`, `frontend/src/components/ActionDetailModal.tsx`, `frontend/src/services/apiClient.ts`, `frontend/src/types/api.ts`

Tests: `backend/tests/test_actions_and_reviews.py`, `frontend/src/test/App.test.tsx`

### webhook-dispatch-execution — Automated dispatch webhook for downstream agent execution upon approval

Status: done

Acceptance:
- Configurable HTTPS webhook endpoint receiving signed approval payload and receipt token upon approval
- Webhook delivery retries with exponential backoff and dispatch audit event logging

Implementation: `backend/app/api/routes_webhooks.py`, `backend/app/services/webhook_service.py`, `backend/app/core/database.py`, `backend/app/main.py`, `backend/app/api/routes_reviews.py`, `frontend/src/components/WebhookManager.tsx`, `frontend/src/services/apiClient.ts`, `frontend/src/types/api.ts`, `frontend/src/components/Navbar.tsx`, `frontend/src/App.tsx`

Tests: `backend/tests/test_actions_and_reviews.py`, `frontend/src/test/App.test.tsx`

### webhook-delivery-history — Webhook delivery history and monitoring dashboard

Status: done

Acceptance:
- GET /api/webhooks/{webhook_id}/deliveries returns paginated dispatch attempts with status, timestamps, error details
- GET /api/webhooks/deliveries returns paginated dispatch attempts across all webhooks with filtering by webhook, status, date range
- WebhookManager component displays delivery history table with status badges, retry counts, and error details
- Delivery records include attempt number, status code, error message, timestamp, and action/receipt references

Implementation: `backend/app/api/routes_webhooks.py`, `backend/app/services/webhook_service.py`, `backend/app/models/schemas.py`, `frontend/src/components/WebhookManager.tsx`, `frontend/src/services/apiClient.ts`, `frontend/src/types/api.ts`

Tests: `backend/tests/test_webhook_deliveries.py`, `frontend/src/test/WebhookManager.test.tsx`

