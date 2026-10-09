"""Cryptographic approval receipt service."""
import json
from contextlib import nullcontext
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from app.core.config import settings
from app.core.database import db_transaction, get_connection
from app.core.security import sha256_digest, sign_hmac_sha256, verify_hmac_sha256
from app.models.schemas import ChainVerifyResult, ReceiptVerifyResult

GENESIS_HASH = "0" * 64

class ReceiptService:
    @classmethod
    def get_latest_receipt_hash(cls) -> str:
        row = get_connection().execute("SELECT receipt_hash FROM receipts ORDER BY rowid DESC LIMIT 1").fetchone()
        return row[0] if row else GENESIS_HASH

    @staticmethod
    def _manifest(rid, aid, agid, dec, rev_id, rev_role, signed, p_hash, r_hash, prev_h, score, lvl, atype, tgt):
        return {
            "receipt_id": rid, "action_id": aid, "agent_id": agid, "decision": dec, "reviewer_id": rev_id,
            "reviewer_role": rev_role, "signed_at": signed, "payload_hash": p_hash, "rationale_hash": r_hash,
            "prev_receipt_hash": prev_h, "risk_score": score, "risk_level": lvl, "action_type": atype, "target_resource": tgt
        }

    @classmethod
    def create_receipt(cls, action: Dict[str, Any], decision: str, reviewer_id: str, reviewer_role: str, rationale: str, effective_payload: Dict[str, Any], cursor=None) -> Dict[str, Any]:
        receipt_id = f"rcpt-{action['id']}-{int(datetime.now(timezone.utc).timestamp())}"
        now_iso = datetime.now(timezone.utc).isoformat()
        payload_hash = sha256_digest(effective_payload)
        rationale_hash = sha256_digest(rationale.strip())
        with (nullcontext(cursor) if cursor is not None else db_transaction()) as cur:
            prev_hash = cls.get_latest_receipt_hash()
            manifest = cls._manifest(receipt_id, action["id"], action["agent_id"], decision, reviewer_id, reviewer_role, now_iso, payload_hash, rationale_hash, prev_hash, action["risk_score"], action["risk_level"], action["action_type"], action["target_resource"])
            receipt_hash = sha256_digest(manifest)
            signature = sign_hmac_sha256(settings.receipt_signing_key, receipt_hash.encode("ascii"))
            receipt_data = {**manifest, "signature": signature, "original_intent": action["intent"], "rationale": rationale}

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

        manifest = cls._manifest(receipt["id"], receipt["action_id"], receipt["agent_id"], receipt["decision"], receipt["reviewer_id"], receipt["reviewer_role"], receipt["signed_at"], receipt["payload_hash"], receipt["rationale_hash"], receipt["prev_receipt_hash"], action_row["risk_score"], action_row["risk_level"], action_row["action_type"], action_row["target_resource"])
        recomputed_hash = sha256_digest(manifest)
        sig_valid = verify_hmac_sha256(settings.receipt_signing_key, recomputed_hash.encode("ascii"), receipt["signature"])

        prev_row = conn.execute("SELECT receipt_hash FROM receipts WHERE rowid < (SELECT rowid FROM receipts WHERE id = ?) ORDER BY rowid DESC LIMIT 1", (receipt["id"],)).fetchone()
        chain_intact = ((prev_row[0] if prev_row else GENESIS_HASH) == receipt["prev_receipt_hash"])

        try:
            exported = json.loads(receipt["receipt_data_json"])
            export_matches = exported == {
                **manifest, "signature": receipt["signature"],
                "original_intent": action_row["intent"], "rationale": action_row["rationale"]
            }
        except (ValueError, TypeError):
            export_matches = False
        is_valid = bool(export_matches and payload_matches and rationale_matches and (recomputed_hash == receipt["receipt_hash"]) and sig_valid and chain_intact)
        return ReceiptVerifyResult(receipt_id=receipt_id, is_valid=is_valid, signature_valid=sig_valid, payload_hash_matches=payload_matches, rationale_hash_matches=rationale_matches, chain_link_intact=chain_intact, details="Signature and audit chain verified intact." if is_valid else "Verification failed.")

    @classmethod
    def verify_chain(cls) -> ChainVerifyResult:
        rows = get_connection().execute("SELECT id, prev_receipt_hash, receipt_hash FROM receipts ORDER BY rowid ASC").fetchall()
        if not rows:
            return ChainVerifyResult(is_valid=True, total_receipts=0, verified_count=0, genesis_hash=GENESIS_HASH, head_receipt_hash=None, broken_at_receipt_id=None, details="Audit ledger is empty; genesis state verified.")
        expected_prev = GENESIS_HASH
        for idx, r in enumerate(rows):
            if r["prev_receipt_hash"] != expected_prev:
                return ChainVerifyResult(is_valid=False, total_receipts=len(rows), verified_count=idx, genesis_hash=GENESIS_HASH, head_receipt_hash=expected_prev, broken_at_receipt_id=r["id"], details=f"Chain broken at receipt '{r['id']}': expected prev hash '{expected_prev}', got '{r['prev_receipt_hash']}'.")
            single = cls.verify_receipt(r["id"])
            if not single.is_valid:
                return ChainVerifyResult(is_valid=False, total_receipts=len(rows), verified_count=idx, genesis_hash=GENESIS_HASH, head_receipt_hash=expected_prev, broken_at_receipt_id=r["id"], details=f"Integrity check failed at receipt '{r['id']}': {single.details}")
            expected_prev = r["receipt_hash"]
        return ChainVerifyResult(is_valid=True, total_receipts=len(rows), verified_count=len(rows), genesis_hash=GENESIS_HASH, head_receipt_hash=expected_prev, broken_at_receipt_id=None, details=f"Cryptographic hash chain intact across all {len(rows)} approval receipts from genesis block.")

    @classmethod
    def format_markdown(cls, receipt_id: str) -> str:
        r = cls.get_receipt_by_id(receipt_id)
        if not r: return "# Receipt Not Found"
        d = json.loads(r["receipt_data_json"])
        return f"# AI Agent Human Approval Receipt\n\n- Receipt ID: `{r['id']}`\n- Action ID: `{r['action_id']}`\n- Decision: **{r['decision']}**\n- Reviewer: `{r['reviewer_id']}` ({r['reviewer_role']})\n- Signed: {r['signed_at']} UTC\n\n```json\n{json.dumps({'receipt_id': r['id'], 'receipt_hash': r['receipt_hash'], 'payload_sha256': r['payload_hash'], 'prev_hash': r['prev_receipt_hash'], 'hmac_sha256_signature': r['signature']}, indent=2)}\n```"
