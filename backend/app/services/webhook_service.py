"""Webhook dispatch service with exponential backoff retries."""
import json
import uuid
import hmac
import hashlib
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.database import db_transaction, get_connection
from app.core.security import sha256_digest

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
BASE_BACKOFF_SECONDS = 2.0
MAX_BACKOFF_SECONDS = 60.0
WEBHOOK_TIMEOUT_SECONDS = 15.0


@dataclass
class DispatchResult:
    success: bool
    status_code: Optional[int]
    error: Optional[str]
    attempt: int


class WebhookService:
    """Handles webhook dispatch with retries and audit logging."""

    @classmethod
    def _sign_payload(cls, payload: bytes, secret: str) -> str:
        """Generate HMAC-SHA256 signature for payload."""
        return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    @classmethod
    def _build_webhook_payload(
        cls,
        action: Dict[str, Any],
        receipt: Dict[str, Any],
        event_type: str
    ) -> Dict[str, Any]:
        """Build the webhook payload for an approval event."""
        return {
            "event": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": {
                "id": action["id"],
                "agent_id": action["agent_id"],
                "action_type": action["action_type"],
                "target_resource": action["target_resource"],
                "intent": action["intent"],
                "payload": json.loads(action["payload_json"]),
                "risk_score": action["risk_score"],
                "risk_level": action["risk_level"],
            },
            "receipt": {
                "id": receipt["id"],
                "decision": receipt["decision"],
                "reviewer_id": receipt["reviewer_id"],
                "reviewer_role": receipt["reviewer_role"],
                "signed_at": receipt["signed_at"],
                "receipt_hash": receipt["receipt_hash"],
                "payload_hash": receipt["payload_hash"],
            },
        }

    @classmethod
    async def _dispatch_once(
        cls,
        client: httpx.AsyncClient,
        webhook: Dict[str, Any],
        payload: Dict[str, Any],
        attempt: int
    ) -> DispatchResult:
        """Attempt a single webhook delivery."""
        url = webhook["url"]
        secret = webhook.get("secret")
        body = json.dumps(payload, separators=(",", ":")).encode()

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "human-approval-console-webhook/1.0",
            "X-Webhook-Delivery": f"{webhook['id']}-{attempt}",
            "X-Webhook-Event": payload["event"],
        }

        if secret:
            headers["X-Webhook-Signature"] = f"sha256={cls._sign_payload(body, secret)}"

        try:
            response = await client.post(
                url,
                content=body,
                headers=headers,
                timeout=WEBHOOK_TIMEOUT_SECONDS,
            )
            if 200 <= response.status_code < 300:
                return DispatchResult(True, response.status_code, None, attempt)
            else:
                return DispatchResult(False, response.status_code, f"HTTP {response.status_code}: {response.text[:200]}", attempt)
        except httpx.TimeoutException:
            return DispatchResult(False, None, "Timeout", attempt)
        except httpx.RequestError as e:
            return DispatchResult(False, None, f"Request error: {type(e).__name__}: {e}", attempt)

    @classmethod
    def _calculate_backoff(cls, attempt: int) -> float:
        """Calculate exponential backoff with jitter."""
        backoff = min(BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)), MAX_BACKOFF_SECONDS)
        # Add small jitter (±10%)
        import random
        jitter = backoff * 0.1 * (random.random() * 2 - 1)
        return backoff + jitter

    @classmethod
    async def dispatch_webhook(
        cls,
        webhook_id: str,
        action: Dict[str, Any],
        receipt: Dict[str, Any],
        event_type: str = "action.approved"
    ) -> Dict[str, Any]:
        """Dispatch webhook with exponential backoff retries."""
        webhook = cls.get_webhook_by_id(webhook_id)
        if not webhook or not webhook["enabled"]:
            return {"success": False, "reason": "Webhook not found or disabled"}

        # Check event filter
        if webhook.get("event_filter_json"):
            try:
                filters = json.loads(webhook["event_filter_json"])
                if event_type not in filters:
                    return {"success": False, "reason": "Event type not in filter"}
            except json.JSONDecodeError:
                pass

        payload = cls._build_webhook_payload(action, receipt, event_type)
        max_retries = webhook.get("max_retries", MAX_RETRIES)

        async with httpx.AsyncClient() as client:
            for attempt in range(1, max_retries + 1):
                result = await cls._dispatch_once(client, webhook, payload, attempt)
                if result.success:
                    cls._log_dispatch_audit(webhook_id, action["id"], receipt["id"], event_type, True, result.status_code, None, attempt)
                    return {"success": True, "attempt": attempt, "status_code": result.status_code}
                
                # Log failed attempt
                cls._log_dispatch_audit(webhook_id, action["id"], receipt["id"], event_type, False, result.status_code, result.error, attempt)
                
                if attempt < max_retries:
                    backoff = cls._calculate_backoff(attempt)
                    logger.warning(f"Webhook {webhook_id} attempt {attempt} failed: {result.error}. Retrying in {backoff:.1f}s")
                    await asyncio.sleep(backoff)
                else:
                    logger.error(f"Webhook {webhook_id} failed after {max_retries} attempts for action {action['id']}")

        return {"success": False, "attempts": max_retries, "reason": "Max retries exceeded"}

    @classmethod
    def _log_dispatch_audit(
        cls,
        webhook_id: str,
        action_id: str,
        receipt_id: str,
        event_type: str,
        success: bool,
        status_code: Optional[int],
        error: Optional[str],
        attempt: int
    ) -> None:
        """Log webhook dispatch attempt to audit log."""
        audit_id = f"audit-{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        details = {
            "webhook_id": webhook_id,
            "action_id": action_id,
            "receipt_id": receipt_id,
            "event_type": event_type,
            "attempt": attempt,
            "success": success,
            "status_code": status_code,
            "error": error,
        }
        with db_transaction() as cursor:
            cursor.execute(
                "INSERT INTO audit_logs (id, action_id, actor_id, actor_role, event_type, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (audit_id, action_id, f"webhook:{webhook_id}", "system", "WEBHOOK_DISPATCH", json.dumps(details), now_iso)
            )

    # Webhook CRUD operations
    @classmethod
    def create_webhook(
        cls,
        name: str,
        url: str,
        secret: Optional[str] = None,
        event_filter: Optional[List[str]] = None,
        max_retries: int = 5,
        enabled: bool = True
    ) -> Dict[str, Any]:
        """Create a new webhook configuration."""
        webhook_id = f"wh-{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        with db_transaction() as cursor:
            cursor.execute(
                """INSERT INTO webhooks (id, name, url, secret, event_filter_json, enabled, max_retries, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (webhook_id, name, url, secret, json.dumps(event_filter) if event_filter else None, int(enabled), max_retries, now_iso, now_iso)
            )
        return cls.get_webhook_by_id(webhook_id)

    @classmethod
    def get_webhook_by_id(cls, webhook_id: str) -> Optional[Dict[str, Any]]:
        """Get webhook by ID."""
        row = get_connection().execute("SELECT * FROM webhooks WHERE id = ?", (webhook_id,)).fetchone()
        return dict(row) if row else None

    @classmethod
    def list_webhooks(cls, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """List all webhooks."""
        query = "SELECT * FROM webhooks ORDER BY created_at DESC"
        if enabled_only:
            query = "SELECT * FROM webhooks WHERE enabled = 1 ORDER BY created_at DESC"
        rows = get_connection().execute(query).fetchall()
        return [dict(row) for row in rows]

    @classmethod
    def update_webhook(
        cls,
        webhook_id: str,
        name: Optional[str] = None,
        url: Optional[str] = None,
        secret: Optional[str] = None,
        event_filter: Optional[List[str]] = None,
        enabled: Optional[bool] = None,
        max_retries: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Update webhook configuration."""
        webhook = cls.get_webhook_by_id(webhook_id)
        if not webhook:
            return None

        updates = []
        params = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if url is not None:
            updates.append("url = ?")
            params.append(url)
        if secret is not None:
            updates.append("secret = ?")
            params.append(secret)
        if event_filter is not None:
            updates.append("event_filter_json = ?")
            params.append(json.dumps(event_filter))
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(int(enabled))
        if max_retries is not None:
            updates.append("max_retries = ?")
            params.append(max_retries)
        
        if not updates:
            return webhook

        updates.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(webhook_id)

        with db_transaction() as cursor:
            cursor.execute(f"UPDATE webhooks SET {', '.join(updates)} WHERE id = ?", params)
        return cls.get_webhook_by_id(webhook_id)

    @classmethod
    def delete_webhook(cls, webhook_id: str) -> bool:
        """Delete a webhook."""
        webhook = cls.get_webhook_by_id(webhook_id)
        if not webhook:
            return False
        with db_transaction() as cursor:
            cursor.execute("DELETE FROM webhooks WHERE id = ?", (webhook_id,))
        return True

    @classmethod
    def get_enabled_webhooks_for_event(cls, event_type: str) -> List[Dict[str, Any]]:
        """Get all enabled webhooks that should receive this event type."""
        rows = get_connection().execute("SELECT * FROM webhooks WHERE enabled = 1").fetchall()
        result = []
        for row in rows:
            webhook = dict(row)
            if webhook.get("event_filter_json"):
                try:
                    filters = json.loads(webhook["event_filter_json"])
                    if event_type not in filters:
                        continue
                except json.JSONDecodeError:
                    pass
            result.append(webhook)
        return result

    @classmethod
    async def dispatch_to_all_webhooks(
        cls,
        action: Dict[str, Any],
        receipt: Dict[str, Any],
        event_type: str = "action.approved"
    ) -> List[Dict[str, Any]]:
        """Dispatch to all enabled webhooks for the event type."""
        webhooks = cls.get_enabled_webhooks_for_event(event_type)
        if not webhooks:
            return []

        results = []
        for webhook in webhooks:
            result = await cls.dispatch_webhook(webhook["id"], action, receipt, event_type)
            result["webhook_id"] = webhook["id"]
            result["webhook_name"] = webhook["name"]
            results.append(result)
        return results