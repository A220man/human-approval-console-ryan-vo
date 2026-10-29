"""Webhook configuration and management endpoints."""
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl

from app.core.auth import require_role
from app.core.database import get_connection
from app.models.schemas import UserProfile, WebhookDeliveryResponse, WebhookDeliveriesListResponse
from app.services.webhook_service import WebhookService

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


class WebhookBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    url: HttpUrl
    secret: Optional[str] = Field(None, max_length=256)
    event_filter: Optional[List[str]] = None
    enabled: bool = True
    max_retries: int = Field(5, ge=1, le=20)


class WebhookCreate(WebhookBase):
    pass


class WebhookUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    url: Optional[HttpUrl] = None
    secret: Optional[str] = Field(None, max_length=256)
    event_filter: Optional[List[str]] = None
    enabled: Optional[bool] = None
    max_retries: Optional[int] = Field(None, ge=1, le=20)


class WebhookResponse(WebhookBase):
    id: str
    created_at: str
    updated_at: str


def _row_to_webhook(r: Any) -> WebhookResponse:
    return WebhookResponse(
        id=r["id"],
        name=r["name"],
        url=r["url"],
        secret=r["secret"],
        event_filter=json.loads(r["event_filter_json"]) if r["event_filter_json"] else None,
        enabled=bool(r["enabled"]),
        max_retries=r["max_retries"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


@router.post("", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
def create_webhook(
    req: WebhookCreate,
    user: UserProfile = Depends(require_role(["admin"]))
) -> WebhookResponse:
    """Create a new webhook configuration (admin only)."""
    webhook = WebhookService.create_webhook(
        name=req.name,
        url=str(req.url),
        secret=req.secret,
        event_filter=req.event_filter,
        enabled=req.enabled,
        max_retries=req.max_retries,
    )
    return _row_to_webhook(webhook)


@router.get("", response_model=Dict[str, Any])
def list_webhooks(
    enabled_only: bool = Query(False),
    user: UserProfile = Depends(require_role(["viewer", "analyst", "admin"]))
) -> Dict[str, Any]:
    """List all webhook configurations."""
    webhooks = WebhookService.list_webhooks(enabled_only=enabled_only)
    return {"total": len(webhooks), "items": [_row_to_webhook(w) for w in webhooks]}


# Delivery history endpoints - must come before /{webhook_id} to avoid path parameter conflicts
@router.get("/deliveries", response_model=WebhookDeliveriesListResponse)
def list_webhook_deliveries(
    webhook_id: Optional[str] = Query(None),
    success: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    since: Optional[str] = Query(None),
    until: Optional[str] = Query(None),
    user: UserProfile = Depends(require_role(["viewer", "analyst", "admin"]))
) -> WebhookDeliveriesListResponse:
    """List webhook delivery attempts across all webhooks with filtering."""
    result = WebhookService.get_webhook_deliveries(
        webhook_id=webhook_id,
        success=success,
        limit=limit,
        offset=offset,
        since=since,
        until=until,
    )
    return WebhookDeliveriesListResponse(**result)


@router.get("/{webhook_id}/deliveries", response_model=WebhookDeliveriesListResponse)
def list_webhook_deliveries_by_webhook(
    webhook_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: UserProfile = Depends(require_role(["viewer", "analyst", "admin"]))
) -> WebhookDeliveriesListResponse:
    """List delivery attempts for a specific webhook."""
    webhook = WebhookService.get_webhook_by_id(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found.")

    result = WebhookService.get_webhook_deliveries_by_webhook(
        webhook_id=webhook_id,
        limit=limit,
        offset=offset,
    )
    return WebhookDeliveriesListResponse(**result)


@router.get("/{webhook_id}", response_model=WebhookResponse)
def get_webhook(
    webhook_id: str,
    user: UserProfile = Depends(require_role(["viewer", "analyst", "admin"]))
) -> WebhookResponse:
    """Get a specific webhook configuration."""
    webhook = WebhookService.get_webhook_by_id(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found.")
    return _row_to_webhook(webhook)


@router.patch("/{webhook_id}", response_model=WebhookResponse)
def update_webhook(
    webhook_id: str,
    req: WebhookUpdate,
    user: UserProfile = Depends(require_role(["admin"]))
) -> WebhookResponse:
    """Update a webhook configuration (admin only)."""
    webhook = WebhookService.update_webhook(
        webhook_id=webhook_id,
        name=req.name,
        url=str(req.url) if req.url else None,
        secret=req.secret,
        event_filter=req.event_filter,
        enabled=req.enabled,
        max_retries=req.max_retries,
    )
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found.")
    return _row_to_webhook(webhook)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(
    webhook_id: str,
    user: UserProfile = Depends(require_role(["admin"]))
) -> None:
    """Delete a webhook configuration (admin only)."""
    if not WebhookService.delete_webhook(webhook_id):
        raise HTTPException(status_code=404, detail="Webhook not found.")


@router.post("/{webhook_id}/test", response_model=Dict[str, Any])
async def test_webhook(
    webhook_id: str,
    user: UserProfile = Depends(require_role(["admin"]))
) -> Dict[str, Any]:
    """Send a test payload to verify webhook configuration."""
    webhook = WebhookService.get_webhook_by_id(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found.")

    # Build a test payload
    test_action = {
        "id": "act-test-001",
        "agent_id": "test-agent",
        "action_type": "api_call",
        "target_resource": "test-target",
        "intent": "Test webhook delivery",
        "payload_json": json.dumps({"method": "GET", "url": "https://example.com/test"}),
        "risk_score": 10,
        "risk_level": "low",
    }
    test_receipt = {
        "id": "rcpt-test-001",
        "decision": "APPROVE",
        "reviewer_id": user.user_id,
        "reviewer_role": "admin",
        "signed_at": "2024-01-01T00:00:00Z",
        "receipt_hash": "0" * 64,
        "payload_hash": "0" * 64,
    }

    result = await WebhookService.dispatch_webhook(webhook_id, test_action, test_receipt, "webhook.test")
    return result
@router.post("/deliveries/{delivery_id}/retry", response_model=Dict[str, Any])
async def retry_delivery(
    delivery_id: str,
    user: UserProfile = Depends(require_role(["admin"]))
) -> Dict[str, Any]:
    """Retry a failed webhook delivery by delivery ID (admin only)."""
    result = await WebhookService.retry_delivery(delivery_id, user.user_id)
    if not result.get("success") and result.get("reason") == "Delivery record not found":
        raise HTTPException(status_code=404, detail="Delivery record not found.")
    if not result.get("success") and result.get("reason") in ("Webhook not found or disabled", "Original action not found", "Original receipt not found"):
        raise HTTPException(status_code=404, detail=result["reason"])
    return result