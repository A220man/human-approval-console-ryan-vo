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


def test_filter_and_search_actions(analyst_client):
    """Verifies queue listing filtering by status and search terms."""
    resp = analyst_client.get("/api/actions?status=pending&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "stats" in data
    for item in data["items"]:
        assert item["status"] == "pending"
