"""Tests for authentication, RBAC role enforcement, CSRF protection, and security boundaries."""
import pytest
from app.core.config import Settings


def test_unauthenticated_rejection(client):
    """Verifies that unauthenticated requests to protected endpoints return 401 Unauthorized."""
    resp = client.get("/api/actions")
    assert resp.status_code == 401
    assert "Authentication required" in resp.json()["detail"]


def test_demo_login_viewer_analyst_admin(client):
    """Verifies demo login assigns distinct roles and session cookies."""
    for role in ("viewer", "analyst", "admin"):
        resp = client.post("/api/auth/demo-login", json={"role": role})
        assert resp.status_code == 200
        data = resp.json()
        assert role in data["roles"]
        assert "approval_session" in client.cookies


def test_role_denial_viewer_cannot_review(viewer_client):
    """Verifies that viewer role is denied mutation/review capability with 403 Forbidden."""
    resp = viewer_client.post("/api/actions/act-demo-002/review", json={
        "decision": "APPROVE",
        "rationale": "Viewer attempting unauthorized approval."
    })
    assert resp.status_code == 403
    assert "Access denied" in resp.json()["detail"]


def test_critical_action_requires_admin_role(analyst_client):
    """Verifies that analyst role is denied reviewing critical risk actions."""
    # act-demo-004 is seeded as critical risk
    resp = analyst_client.post("/api/actions/act-demo-004/review", json={
        "decision": "APPROVE",
        "rationale": "Analyst attempting critical action approval without admin authority."
    })
    assert resp.status_code == 403
    assert "Critical risk actions require Administrator authorization" in resp.json()["detail"]


def test_csrf_token_required_on_cookie_mutation(client):
    """Verifies that state mutations via cookie authentication without valid CSRF header fail with 403."""
    # Log in as analyst to obtain session cookie
    login_resp = client.post("/api/auth/demo-login", json={"role": "analyst"})
    assert login_resp.status_code == 200

    # Attempt mutation without x-csrf-token header
    resp = client.post("/api/actions/act-demo-002/claim", json={})
    assert resp.status_code == 403
    assert "CSRF validation failed" in resp.json()["detail"]


def test_startup_refuses_demo_mode_in_production():
    """Verifies that application configuration strictly refuses demo mode in production."""
    with pytest.raises(ValueError) as excinfo:
        Settings(
            environment="production",
            demo_mode=True,
            secret_key="some-key-that-is-long-enough-32chars",
            receipt_signing_key="some-receipt-key-that-is-long-enough"
        ).validate_runtime_safety()
    assert "DEMO_MODE=true is strictly forbidden when ENVIRONMENT=production" in str(excinfo.value)
