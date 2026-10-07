"""Tests for cryptographic receipts, offline advisory, and AI safety benchmark evaluation."""
import json
from app.services.receipt_service import ReceiptService


def test_receipt_cryptographic_verification(analyst_client):
    """Verifies that an approved action generates a receipt whose cryptographic signature and hashes verify."""
    review_resp = analyst_client.post("/api/actions/act-demo-002/review", json={
        "decision": "APPROVE",
        "rationale": "Validated schema backwards compatibility."
    })
    assert review_resp.status_code == 200
    receipt_id = review_resp.json()["receipt"]["receipt_id"]

    verify_resp = analyst_client.post("/api/receipts/verify", json={"receipt_id": receipt_id})
    assert verify_resp.status_code == 200
    res = verify_resp.json()
    assert res["is_valid"] is True
    assert res["signature_valid"] is True
    assert res["payload_hash_matches"] is True
    assert res["rationale_hash_matches"] is True
    assert res["chain_link_intact"] is True


def test_tampered_receipt_detection(analyst_client):
    """Verifies that tampering with database payload triggers signature or hash mismatch."""
    review_resp = analyst_client.post("/api/actions/act-demo-002/review", json={
        "decision": "APPROVE",
        "rationale": "Audit passed."
    })
    receipt_id = review_resp.json()["receipt"]["receipt_id"]

    # Tamper with action payload in SQLite directly
    from app.core.database import get_connection
    conn = get_connection()
    conn.execute("UPDATE actions SET payload_json = ? WHERE id = 'act-demo-002'", (json.dumps({"tampered": True}),))
    conn.commit()

    verify_resp = analyst_client.post("/api/receipts/verify", json={"receipt_id": receipt_id})
    res = verify_resp.json()
    assert res["is_valid"] is False
    assert res["payload_hash_matches"] is False


def test_receipt_markdown_export(analyst_client):
    """Verifies exporting receipt returns markdown document with verification block."""
    review_resp = analyst_client.post("/api/actions/act-demo-002/review", json={
        "decision": "APPROVE",
        "rationale": "Ready for export."
    })
    receipt_id = review_resp.json()["receipt"]["receipt_id"]

    resp = analyst_client.get(f"/api/receipts/{receipt_id}/export")
    assert resp.status_code == 200
    assert "text/markdown" in resp.headers["content-type"]
    text = resp.text
    assert "# AI Agent Human Approval Receipt" in text
    assert receipt_id in text
    assert "hmac_sha256_signature" in text


def test_llm_advisory_offline_deterministic(analyst_client):
    """Verifies that when no LLM key is configured, advisory provides grounded deterministic analysis."""
    resp = analyst_client.post("/api/actions/act-demo-001/advisory")
    assert resp.status_code == 200
    adv = resp.json()
    assert adv["is_advisory"] is True
    assert adv["offline_deterministic"] is True
    assert adv["provider"] == "offline-deterministic"
    assert "OFFLINE DETERMINISTIC ADVISORY" in adv["summary"]
    assert len(adv["security_concerns"]) > 0


def test_evaluation_benchmark_run(analyst_client):
    """Verifies running benchmark evaluation executes across all samples and returns valid metrics."""
    resp = analyst_client.post("/api/eval/run")
    assert resp.status_code == 200
    metrics = resp.json()
    assert metrics["total_samples"] >= 20
    assert metrics["accuracy"] > 0.80
    assert metrics["precision"] > 0.80
    assert metrics["critical_false_negative_rate"] <= 0.05
    assert "confusion_matrix" in metrics
    assert "breakdown_by_category" in metrics


def test_policy_crud_admin_enforcement(client):
    """Verifies policy mutations require admin role and work correctly."""
    policy_data = {
        "name": "Block Custom Malicious Tool",
        "description": "Custom rule",
        "action_type": "shell_command",
        "rule_pattern": r"\bcustom_malware\b",
        "severity": "critical",
        "required_role": "admin",
        "auto_reject": False,
        "enabled": True
    }

    # 1. Login as Analyst (obtain CSRF)
    client.post("/api/auth/demo-login", json={"role": "analyst"})
    csrf_tok = client.get("/api/auth/csrf").json()["csrf_token"]
    client.headers.update({"x-csrf-token": csrf_tok})

    # Analyst cannot create policy (forbidden)
    fail_resp = client.post("/api/policies", json=policy_data)
    assert fail_resp.status_code == 403

    # 2. Switch login to Admin
    client.post("/api/auth/demo-login", json={"role": "admin"})
    admin_csrf = client.get("/api/auth/csrf").json()["csrf_token"]
    client.headers.update({"x-csrf-token": admin_csrf})

    # Admin can create policy
    succ_resp = client.post("/api/policies", json=policy_data)
    assert succ_resp.status_code == 201
    pol_id = succ_resp.json()["id"]

    # Admin can delete policy
    del_resp = client.delete(f"/api/policies/{pol_id}")
    assert del_resp.status_code == 200
