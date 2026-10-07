"""Cryptographic approval receipt service."""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from app.core.config import settings
from app.core.database import db_transaction, get_connection
from app.core.security import sha256_digest, sign_hmac_sha256, verify_hmac_sha256
from app.models.schemas import ReceiptVerifyResult

GENESIS_HASH = "0" * 64

class ReceiptService:
    @classmethod
    def get_latest_receipt_hash(cls) -> str:
        row = get_connection().execute("SELECT receipt_hash FROM receipts ORDER BY rowid DESC LIMIT 1").fetchone()
        return row[0] if row else GENESIS_HASH

    @classmethod
    def create_receipt(cls, action: Dict[str, Any], decision: str, reviewer_id: str, reviewer_role: str, rationale: str, effective_payload: Dict[str, Any]) -> Dict[str, Any]:
        receipt_id = f"rcpt-{action['id']}-{int(datetime.now(timezone.utc).timestamp())}"
        now_iso = datetime.now(timezone.utc).isoformat()
        payload_hash = sha256_digest(effective_payload)
        rationale_hash = sha256_digest(rationale.strip())
        prev_hash = cls.get_latest_receipt_hash()

        manifest = {
            "receipt_id": receipt_id, "action_id": action["id"], "agent_id": action["agent_id"],
            "decision": decision, "reviewer_id": reviewer_id, "reviewer_role": reviewer_role,
            "signed_at": now_iso, "payload_hash": payload_hash, "rationale_hash": rationale_hash,
            "prev_receipt_hash": prev_hash, "risk_score": action["risk_score"], "risk_level": action["risk_level"],
            "action_type": action["action_type"], "target_resource": action["target_resource"]
        }
        receipt_hash = sha256_digest(manifest)
        signature = sign_hmac_sha256(settings.receipt_signing_key, receipt_hash.encode("ascii"))
        receipt_data = {**manifest, "signature": signature, "original_intent": action["intent"], "rationale": rationale}

        with db_transaction() as cur:
            cur.execute("""
                INSERT INTO receipts (id, action_id, agent_id, decision, reviewer_id, reviewer_role, signed_at,
                                     payload_hash, rationale_hash, receipt_hash, prev_receipt_hash, signature, receipt_data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (receipt_id, action["id"], action["agent_id"], decision, reviewer_id, reviewer_role, now_iso,
                  payload_hash, rationale_hash, receipt_hash, prev_hash, signature, json.dumps(receipt_data)))
            cur.execute("""
                INSERT INTO audit_logs (id, action_id, actor_id, actor_role, event_type, details_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (f"aud-{uuid.uuid4().hex[:12]}", action["id"], reviewer_id, reviewer_role, f"ACTION_{decision}",
                  json.dumps({"receipt_id": receipt_id, "receipt_hash": receipt_hash, "prev_hash": prev_hash}), now_iso))

        return receipt_data

    @classmethod
    def get_receipt_by_id(cls, receipt_id: str) -> Optional[Dict[str, Any]]:
        row = get_connection().execute("SELECT * FROM receipts WHERE id = ?", (receipt_id,)).fetchone()
        return dict(row) if row else None

    @classmethod
    def get_receipt_by_action_id(cls, action_id: str) -> Optional[Dict[str, Any]]:
        row = get_connection().execute("SELECT * FROM receipts WHERE action_id = ?", (action_id,)).fetchone()
        return dict(row) if row else None

    @classmethod
    def verify_receipt(cls, receipt_id: str) -> ReceiptVerifyResult:
        receipt = cls.get_receipt_by_id(receipt_id)
        if not receipt:
            return ReceiptVerifyResult(receipt_id=receipt_id, is_valid=False, signature_valid=False, payload_hash_matches=False, rationale_hash_matches=False, chain_link_intact=False, details="Receipt not found.")

        conn = get_connection()
        action_row = conn.execute("SELECT * FROM actions WHERE id = ?", (receipt["action_id"],)).fetchone()
        if not action_row:
            return ReceiptVerifyResult(receipt_id=receipt_id, is_valid=False, signature_valid=False, payload_hash_matches=False, rationale_hash_matches=False, chain_link_intact=False, details="Action record missing.")

        effective_payload = json.loads(action_row["modified_payload_json"]) if action_row["modified_payload_json"] else json.loads(action_row["payload_json"])
        payload_matches = (sha256_digest(effective_payload) == receipt["payload_hash"])
        rationale_matches = (sha256_digest((action_row["rationale"] or "").strip()) == receipt["rationale_hash"])

        manifest = {
            "receipt_id": receipt["id"], "action_id": receipt["action_id"], "agent_id": receipt["agent_id"],
            "decision": receipt["decision"], "reviewer_id": receipt["reviewer_id"], "reviewer_role": receipt["reviewer_role"],
            "signed_at": receipt["signed_at"], "payload_hash": receipt["payload_hash"], "rationale_hash": receipt["rationale_hash"],
            "prev_receipt_hash": receipt["prev_receipt_hash"], "risk_score": action_row["risk_score"], "risk_level": action_row["risk_level"],
            "action_type": action_row["action_type"], "target_resource": action_row["target_resource"]
        }
        recomputed_hash = sha256_digest(manifest)
        sig_valid = verify_hmac_sha256(settings.receipt_signing_key, recomputed_hash.encode("ascii"), receipt["signature"])

        prev_row = conn.execute("SELECT receipt_hash FROM receipts WHERE rowid < (SELECT rowid FROM receipts WHERE id = ?) ORDER BY rowid DESC LIMIT 1", (receipt["id"],)).fetchone()
        chain_intact = ((prev_row[0] if prev_row else GENESIS_HASH) == receipt["prev_receipt_hash"])

        is_valid = bool(payload_matches and rationale_matches and (recomputed_hash == receipt["receipt_hash"]) and sig_valid and chain_intact)
        return ReceiptVerifyResult(receipt_id=receipt_id, is_valid=is_valid, signature_valid=sig_valid, payload_hash_matches=payload_matches, rationale_hash_matches=rationale_matches, chain_link_intact=chain_intact, details="Signature and audit chain verified intact." if is_valid else "Verification failed.")

    @classmethod
    def format_markdown(cls, receipt_id: str) -> str:
        r = cls.get_receipt_by_id(receipt_id)
        if not r: return "# Receipt Not Found"
        d = json.loads(r["receipt_data_json"])
        return f"# AI Agent Human Approval Receipt\n\n- Receipt ID: `{r['id']}`\n- Action ID: `{r['action_id']}`\n- Decision: **{r['decision']}**\n- Reviewer: `{r['reviewer_id']}` ({r['reviewer_role']})\n- Signed: {r['signed_at']} UTC\n\n```json\n{json.dumps({'receipt_id': r['id'], 'receipt_hash': r['receipt_hash'], 'payload_sha256': r['payload_hash'], 'prev_hash': r['prev_receipt_hash'], 'hmac_sha256_signature': r['signature']}, indent=2)}\n```"
