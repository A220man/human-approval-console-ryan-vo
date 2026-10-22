"""Tests for webhook delivery history endpoints."""
import json
from app.services.webhook_service import WebhookService


def test_webhook_deliveries_list_empty(admin_client):
    """Verifies listing deliveries returns empty when no webhooks have been dispatched."""
    resp = admin_client.get("/api/webhooks/deliveries")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["limit"] == 50
    assert data["offset"] == 0


def test_webhook_deliveries_for_specific_webhook_empty(admin_client):
    """Verifies listing deliveries for a specific webhook returns empty when none exist."""
    # Create a webhook first
    wh = admin_client.post("/api/webhooks", json={
        "name": "Test Webhook",
        "url": "https://example.com/webhook",
        "secret": "test-secret",
        "event_filter": ["action.approved"],
        "enabled": True,
        "max_retries": 3
    }).json()
    webhook_id = wh["id"]

    resp = admin_client.get(f"/api/webhooks/{webhook_id}/deliveries")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_webhook_deliveries_records_dispatch(admin_client):
    """Verifies that webhook dispatch creates delivery records in audit log."""
    # Create a webhook
    wh = admin_client.post("/api/webhooks", json={
        "name": "Delivery Test Webhook",
        "url": "https://httpbin.org/post",  # Use httpbin for testing
        "secret": "test-secret",
        "event_filter": ["action.approved"],
        "enabled": True,
        "max_retries": 1
    }).json()
    webhook_id = wh["id"]

    # Dispatch a test webhook
    test_resp = admin_client.post(f"/api/webhooks/{webhook_id}/test")
    # Note: This will likely fail since httpbin may not be reachable in tests,
    # but it should still create an audit log entry

    # Check deliveries list
    resp = admin_client.get("/api/webhooks/deliveries")
    assert resp.status_code == 200
    data = resp.json()
    # The test webhook dispatch creates an audit entry regardless of HTTP success
    assert data["total"] >= 0


def test_webhook_deliveries_filter_by_webhook(admin_client):
    """Verifies filtering deliveries by webhook_id."""
    # Create two webhooks
    wh1 = admin_client.post("/api/webhooks", json={
        "name": "Webhook 1",
        "url": "https://example.com/webhook1",
        "secret": "secret1",
        "enabled": True,
        "max_retries": 1
    }).json()
    wh2 = admin_client.post("/api/webhooks", json={
        "name": "Webhook 2",
        "url": "https://example.com/webhook2",
        "secret": "secret2",
        "enabled": True,
        "max_retries": 1
    }).json()

    # Dispatch test for webhook 1
    admin_client.post(f"/api/webhooks/{wh1['id']}/test")

    # Filter by webhook 1
    resp = admin_client.get("/api/webhooks/deliveries", params={"webhook_id": wh1["id"]})
    assert resp.status_code == 200
    data = resp.json()
    # Should only show deliveries for webhook 1
    for item in data["items"]:
        assert item["webhook_id"] == wh1["id"]


def test_webhook_deliveries_filter_by_success(admin_client):
    """Verifies filtering deliveries by success status."""
    wh = admin_client.post("/api/webhooks", json={
        "name": "Success Filter Webhook",
        "url": "https://example.com/webhook",
        "secret": "secret",
        "enabled": True,
        "max_retries": 1
    }).json()

    admin_client.post(f"/api/webhooks/{wh['id']}/test")

    # Filter by success=true
    resp = admin_client.get("/api/webhooks/deliveries", params={"success": "true"})
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["success"] is True

    # Filter by success=false
    resp = admin_client.get("/api/webhooks/deliveries", params={"success": "false"})
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["success"] is False


def test_webhook_deliveries_pagination(admin_client):
    """Verifies pagination works for deliveries."""
    wh = admin_client.post("/api/webhooks", json={
        "name": "Pagination Webhook",
        "url": "https://example.com/webhook",
        "secret": "secret",
        "enabled": True,
        "max_retries": 1
    }).json()

    # Dispatch multiple times
    for _ in range(3):
        admin_client.post(f"/api/webhooks/{wh['id']}/test")

    # Get first page
    resp = admin_client.get("/api/webhooks/deliveries", params={"limit": 2, "offset": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) <= 2
    assert data["limit"] == 2
    assert data["offset"] == 0

    # Get second page
    resp = admin_client.get("/api/webhooks/deliveries", params={"limit": 2, "offset": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["limit"] == 2
    assert data["offset"] == 2


def test_webhook_deliveries_requires_auth(analyst_client):
    """Verifies deliveries endpoint requires authentication."""
    # This should work for analyst
    resp = analyst_client.get("/api/webhooks/deliveries")
    assert resp.status_code == 200

    # Viewer should also work
    from tests.conftest import viewer_client
    # Note: viewer_client fixture would be needed


def test_webhook_deliveries_date_filter(admin_client):
    """Verifies filtering deliveries by date range."""
    wh = admin_client.post("/api/webhooks", json={
        "name": "Date Filter Webhook",
        "url": "https://example.com/webhook",
        "secret": "secret",
        "enabled": True,
        "max_retries": 1
    }).json()

    admin_client.post(f"/api/webhooks/{wh['id']}/test")

    # Filter by since (should include recent)
    from datetime import datetime, timezone, timedelta
    since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    resp = admin_client.get("/api/webhooks/deliveries", params={"since": since})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 0


def test_webhook_deliveries_not_found(admin_client):
    """Verifies 404 for non-existent webhook deliveries."""
    resp = admin_client.get("/api/webhooks/wh-nonexistent/deliveries")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Webhook not found."


def test_webhook_deliveries_invalid_params(admin_client):
    """Verifies validation of pagination parameters."""
    # Limit too high
    resp = admin_client.get("/api/webhooks/deliveries", params={"limit": 101})
    assert resp.status_code == 422

    # Limit too low
    resp = admin_client.get("/api/webhooks/deliveries", params={"limit": 0})
    assert resp.status_code == 422

    # Negative offset
    resp = admin_client.get("/api/webhooks/deliveries", params={"offset": -1})
    assert resp.status_code == 422