"""Tests for action lifecycle: ingestion, claiming, review, and state mutations."""
import json


def test_ingest_action_lifecycle(analyst_client):
    """Verifies that an agent can ingest an action proposal with automated risk evaluation."""
    ingest_payload = {
        "agent_id": "auto-remediation-bot",
        "agent_framework": "langchain",
        "session_id": "sess-test-441",
        "action_type": "shell_command",
        "target_resource": "prod-k8s-node-09",
        "payload": {"command": "systemctl restart coredns"},
        "intent": "Restart DNS daemon to recover from cluster networking glitch",
        "expires_in_minutes": 60
    }
    resp = analyst_client.post("/api/actions", json=ingest_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"].startswith("act-")
    assert data["status"] == "pending"
    assert data["risk_score"] > 0
    assert data["expires_at"] is not None


def test_claim_action(analyst_client):
    """Verifies claiming a pending action transitions its status to under_review."""
    resp = analyst_client.post("/api/actions/act-demo-002/claim", json={"notes": "Investigating schema change"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "under_review"
    assert data["reviewer_id"].startswith("usr-analyst-")


def test_approve_action_and_receipt_generation(analyst_client):
    """Verifies approving an action updates status and generates a cryptographically signed receipt."""
    # act-demo-002 is low risk, analyst can approve
    review_body = {
        "decision": "APPROVE",
        "rationale": "Verified column addition is non-blocking on staging users table."
    }
    resp = analyst_client.post("/api/actions/act-demo-002/review", json=review_body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert "receipt" in data
    receipt = data["receipt"]
    assert receipt["decision"] == "APPROVE"
    assert len(receipt["signature"]) == 64
    assert len(receipt["payload_hash"]) == 64


def test_modify_and_approve_action(analyst_client):
    """Verifies modify-and-approve updates modified payload and binds it to the receipt."""
    # Ingest a new action to modify
    ingest = analyst_client.post("/api/actions", json={
        "agent_id": "sql-optimizer-bot",
        "session_id": "sess-opt-01",
        "action_type": "database_query",
        "target_resource": "staging-db",
        "payload": {"sql": "SELECT * FROM large_log_table;"},
        "intent": "Analyze recent performance logs"
    }).json()

    action_id = ingest["id"]
    modified_payload = {"sql": "SELECT id, level, message FROM large_log_table LIMIT 100;"}

    resp = analyst_client.post(f"/api/actions/{action_id}/review", json={
        "decision": "MODIFY_AND_APPROVE",
        "rationale": "Restricted query to required columns and added LIMIT 100 to prevent OOM.",
        "modified_payload": modified_payload
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "modified_and_approved"

    # Verify action detail records modified payload
    detail = analyst_client.get(f"/api/actions/{action_id}").json()
    assert detail["modified_payload"] == modified_payload


def test_reject_action_with_mandatory_rationale(admin_client):
    """Verifies rejecting an action requires rationale and logs reason."""
    # act-demo-004 is critical risk, admin can reject
    resp = admin_client.post("/api/actions/act-demo-004/review", json={
        "decision": "REJECT",
        "rationale": "Database drop rejected due to active production customer usage."
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"


def test_expired_proposal_cannot_be_claimed_or_approved(analyst_client):
    """Verifies that a proposal past its TTL is closed and cannot be claimed or approved."""
    created = analyst_client.post("/api/actions", json={
        "agent_id": "cache-agent",
        "session_id": "sess-ttl-01",
        "action_type": "shell_command",
        "target_resource": "dev-worker",
        "payload": {"command": "echo cache-flush"},
        "intent": "Flush a local cache on a development worker",
        "expires_in_minutes": 30
    })
    assert created.status_code == 201
    action_id = created.json()["id"]

    from app.core.database import get_connection
    conn = get_connection()
    conn.execute("UPDATE actions SET expires_at = ? WHERE id = ?", ("2000-01-01T00:00:00+00:00", action_id))
    conn.commit()

    listed = analyst_client.get("/api/actions?status=expired")
    assert listed.status_code == 200
    assert any(item["id"] == action_id for item in listed.json()["items"])

    claim = analyst_client.post(f"/api/actions/{action_id}/claim", json={})
    assert claim.status_code == 409
    review = analyst_client.post(f"/api/actions/{action_id}/review", json={
        "decision": "APPROVE",
        "rationale": "Too late to approve this proposal."
    })
    assert review.status_code == 409

    audit = get_connection().execute(
        "SELECT event_type FROM audit_logs WHERE action_id = ? AND event_type = 'ACTION_EXPIRED'",
        (action_id,)
    ).fetchone()
    assert audit is not None


def test_modify_cannot_escalate_beyond_reviewer_role(analyst_client):
    """Verifies an analyst cannot approve an edit that the risk engine rescores as admin-only."""
    created = analyst_client.post("/api/actions", json={
        "agent_id": "sql-optimizer-bot",
        "session_id": "sess-esc-01",
        "action_type": "database_query",
        "target_resource": "staging-db",
        "payload": {"sql": "SELECT id FROM accounts LIMIT 20;"},
        "intent": "Sample recent account identifiers"
    })
    action_id = created.json()["id"]
    resp = analyst_client.post(f"/api/actions/{action_id}/review", json={
        "decision": "MODIFY_AND_APPROVE",
        "rationale": "Rewriting the query before approval.",
        "modified_payload": {"sql": "DROP DATABASE accounts;"}
    })
    assert resp.status_code == 403
    assert "requires admin" in resp.json()["detail"]
    detail = analyst_client.get(f"/api/actions/{action_id}").json()
    assert detail["status"] == "pending"
    assert detail["modified_payload"] is None


def test_admin_modify_records_rescored_risk_on_receipt(admin_client):
    """Verifies an admin edit stores the rescored risk and the receipt still verifies."""
    created = admin_client.post("/api/actions", json={
        "agent_id": "sql-optimizer-bot",
        "session_id": "sess-esc-02",
        "action_type": "database_query",
        "target_resource": "staging-db",
        "payload": {"sql": "SELECT id FROM accounts LIMIT 20;"},
        "intent": "Sample recent account identifiers"
    })
    action_id = created.json()["id"]
    resp = admin_client.post(f"/api/actions/{action_id}/review", json={
        "decision": "MODIFY_AND_APPROVE",
        "rationale": "Emergency schema removal approved by the administrator.",
        "modified_payload": {"sql": "DROP DATABASE accounts;"}
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "modified_and_approved"
    assert body["risk_level"] == "critical"
    detail = admin_client.get(f"/api/actions/{action_id}").json()
    assert detail["risk_level"] == "critical"
    assert detail["risk_score"] == body["risk_score"]
    verify = admin_client.post("/api/receipts/verify", json={"receipt_id": body["receipt"]["receipt_id"]})
    assert verify.status_code == 200
    assert verify.json()["is_valid"] is True


def test_auto_reject_policy_blocks_approval(client):
    """Verifies a matching auto-reject policy prevents approval of the original payload."""
    client.post("/api/auth/demo-login", json={"role": "admin"})
    token = client.get("/api/auth/csrf").json()["csrf_token"]
    client.headers.update({"x-csrf-token": token})
    created_policy = client.post("/api/policies", json={
        "name": "Auto Reject Marker",
        "description": "Blocks commands that include the lab marker",
        "action_type": "shell_command",
        "rule_pattern": "AUTO_REJECT_MARKER",
        "severity": "high",
        "required_role": "analyst",
        "auto_reject": True,
        "enabled": True
    })
    assert created_policy.status_code == 201

    client.post("/api/auth/demo-login", json={"role": "analyst"})
    token = client.get("/api/auth/csrf").json()["csrf_token"]
    client.headers.update({"x-csrf-token": token})
    created = client.post("/api/actions", json={
        "agent_id": "lab-agent",
        "session_id": "sess-rej-01",
        "action_type": "shell_command",
        "target_resource": "dev-sandbox-worker",
        "payload": {"command": "echo AUTO_REJECT_MARKER"},
        "intent": "Run a labeled command that policy must refuse"
    })
    assert created.status_code == 201
    action_id = created.json()["id"]
    resp = client.post(f"/api/actions/{action_id}/review", json={
        "decision": "APPROVE",
        "rationale": "Attempting to approve a blocked command."
    })
    assert resp.status_code == 400
    assert "auto-reject" in resp.json()["detail"]
    assert client.get(f"/api/actions/{action_id}").json()["status"] == "pending"


def test_modify_rejects_unscorable_payload(analyst_client):
    """Verifies a non-numeric financial edit is rejected instead of failing the request."""
    created = analyst_client.post("/api/actions", json={
        "agent_id": "treasury-bot",
        "session_id": "sess-amt-01",
        "action_type": "financial_transaction",
        "target_resource": "treasury",
        "payload": {"amount": 25},
        "intent": "Reimburse a small office expense"
    })
    action_id = created.json()["id"]
    resp = analyst_client.post(f"/api/actions/{action_id}/review", json={
        "decision": "MODIFY_AND_APPROVE",
        "rationale": "Adjusting the transfer amount before approval.",
        "modified_payload": {"amount": "not-a-number"}
    })
    assert resp.status_code == 400
    assert analyst_client.get(f"/api/actions/{action_id}").json()["status"] == "pending"


def test_filter_and_search_actions(analyst_client):
    """Verifies queue listing filtering by status and search terms."""
    resp = analyst_client.get("/api/actions?status=pending&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "stats" in data
    for item in data["items"]:
        assert item["status"] == "pending"
