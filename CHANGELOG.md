# Changelog

All notable changes to `human-approval-console-ryan-vo` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
