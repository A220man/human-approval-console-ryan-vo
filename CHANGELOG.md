# Changelog

## 1.5.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.4.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.3.0 — 2026-10-15

### Added
- Webhook delivery history and monitoring dashboard:
  - `GET /api/webhooks/deliveries` endpoint for paginated delivery attempts across all webhooks with filtering by webhook, success status, and date range.
  - `GET /api/webhooks/{webhook_id}/deliveries` endpoint for delivery history of a specific webhook.
  - `WebhookService.get_webhook_deliveries()` and `get_webhook_deliveries_by_webhook()` methods querying the audit log.
  - Extended `WebhookManager` UI with "View Delivery History" navigation, delivery attempt table with status badges, pagination, and error detail display.
  - Backend test coverage in `test_webhook_deliveries.py` (10 tests) and frontend test coverage in `WebhookManager.test.tsx` (7 tests).
- Webhook dispatch service (`WebhookService`) with configurable HTTPS endpoints, HMAC-SHA256 signed payloads, event filtering, and exponential backoff retries (up to 5 attempts with jitter).
- Webhook configuration API (`POST/GET/PATCH/DELETE /api/webhooks`) for admin users to manage dispatch targets with secrets, event filters, and retry limits.
- Automatic webhook dispatch on action approval (`action.approved` event) delivering signed approval payload and receipt token to all matching enabled webhooks.
- Webhook delivery audit logging (`WEBHOOK_DISPATCH` events) capturing attempt number, success/failure, status code, and error details.
- Frontend `WebhookManager` component with create/edit/delete/test UI, role-gated to administrators, accessible via new "Webhook Dispatch" navigation tab.
- API client extensions (`getWebhooks`, `createWebhook`, `updateWebhook`, `deleteWebhook`, `testWebhook`) with typed request/response models.

### Fixed
- Backend advisor router registration restored after import cleanup.
- Frontend Navbar and App routing updated to include Webhook Dispatch tab.

## [1.2.0] - 2026-10-09

## [1.1.0] - 2026-10-07

All notable changes to `human-approval-console-ryan-vo` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Action lifecycle audit trail endpoint (`GET /api/actions/{action_id}/audit-trail`) returning chronological custody logs (`ACTION_INGESTED`, `ACTION_CLAIMED`, `ACTION_APPROVE`, `ACTION_EXPIRED`) with actor identifiers, roles, event types, and structured metadata.
- Interactive audit trail and custody history section in `ActionDetailModal` displaying the chronological sequence of lifecycle events for inspected proposals.
- Automated tests covering the complete audit trail lifecycle and boundary conditions across backend pytest and frontend Vitest suites.

### Fixed
- Proposals past `expires_at` move to `expired`, are written to the audit log, and can no longer be claimed or approved.
- `MODIFY_AND_APPROVE` scores the edited payload before approval. Analysts cannot approve an edit that exceeds their role, and a matching auto-reject policy blocks approval. The stored risk and signed receipt use the rescored values.
- The action queue reloads after a review decision and can filter expired proposals.

## [1.0.0] - 2026-10-07

### Added
- Initial release of Human Approval Console for AI Agent actions.
- Autonomous agent action queuing and ingestion endpoint (`/api/actions`).
- Multi-factor risk scoring engine evaluating blast radius, reversibility, and resource criticality.
- Deterministic policy enforcement engine with configurable safety guardrails and rule violation detection.
- Role-based human-in-the-loop review workflow (`viewer`, `analyst`, `admin`) with action locking, decision rationale logging, and parameter modification.
- Cryptographically signed (HMAC-SHA256) approval receipts with tamper-evident audit chaining and exportable JSON/Markdown format.
- Grounded provider-agnostic LLM advisory explainer supporting OpenAI-compatible, Anthropic, Gemini, and Ollama providers with deterministic offline fallback.
- AI/ML safety evaluation suite and benchmark dataset measuring policy detection accuracy, recall, and false negative rates.
- Keycloak OIDC authorization-code integration with PKCE, server sessions, CSRF protection, and local demo mode.
- React TypeScript Vite console with interactive queue, risk visualization, payload diffing, receipt export, and evaluation metrics dashboard.