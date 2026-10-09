"""Role-based human review and decision recording endpoints."""
import json
from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from app.api.routes_actions import sweep_expired_actions
from app.core.auth import require_role, verify_csrf
from app.core.database import db_transaction, get_connection
from app.models.schemas import ActionReviewRequest, UserProfile
from app.services.policy_engine import PolicyEngine
from app.services.receipt_service import ReceiptService
from app.services.risk_engine import RiskEngine

router = APIRouter(prefix="/api/actions", tags=["Reviews"])


@router.post("/{action_id}/review", response_model=Dict[str, Any])
def submit_review(
    action_id: str,
    req: ActionReviewRequest,
    user: UserProfile = Depends(require_role(["analyst", "admin"])),
    csrf: None = Depends(verify_csrf)
) -> Dict[str, Any]:
    sweep_expired_actions()
    # Serialize status checks, decisions, receipts and audit rows in one commit.
    with db_transaction() as cursor:
        conn = get_connection()
        row = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Action not found.")

        if row["status"] == "expired":
            raise HTTPException(status_code=409, detail="Action expired and can no longer be reviewed.")

        if row["status"] in ("approved", "rejected", "modified_and_approved"):
            raise HTTPException(
                status_code=400,
                detail=f"Action '{action_id}' has already been reviewed (status: {row['status']})."
            )

        is_admin = "admin" in user.roles
        if row["risk_level"] == "critical" and not is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role Denied: Critical risk actions require Administrator authorization to review.")

        decision = req.decision
        rationale = req.rationale.strip()
        if len(rationale) < 5:
            raise HTTPException(status_code=400, detail="A detailed decision rationale (min 5 characters) is required.")

        modified_payload = None
        risk_score, risk_level = row["risk_score"], row["risk_level"]
        if decision == "MODIFY_AND_APPROVE":
            if not req.modified_payload:
                raise HTTPException(status_code=400, detail="MODIFY_AND_APPROVE requires modified_payload.")
            modified_payload = req.modified_payload
            context = json.loads(row["context_metadata_json"]) if row["context_metadata_json"] else None
            try:
                scored = RiskEngine.analyze(row["action_type"], row["target_resource"], modified_payload, context)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="Modified payload could not be scored.")
            if any(v.auto_reject for v in scored.violations):
                raise HTTPException(status_code=400, detail="Modified payload matches an auto-reject policy and cannot be approved.")
            ranks = {"viewer": 1, "analyst": 2, "admin": 3}
            required = 3 if scored.risk_level == "critical" else ranks.get(scored.suggested_minimum_role, 2)
            if (3 if is_admin else 2) < required:
                raise HTTPException(status_code=403, detail=f"Modified payload requires {scored.suggested_minimum_role} authority ({scored.risk_level}).")
            risk_score, risk_level = scored.risk_score, scored.risk_level
        elif decision == "APPROVE":
            _, _, auto_reject = PolicyEngine.evaluate(row["action_type"], row["target_resource"], json.loads(row["payload_json"]))
            if auto_reject:
                raise HTTPException(status_code=400, detail="Payload matches an auto-reject policy and cannot be approved.")

        new_status = {
            "APPROVE": "approved",
            "REJECT": "rejected",
            "MODIFY_AND_APPROVE": "modified_and_approved"
        }[decision]

        now_iso = datetime.now(timezone.utc).isoformat()
        reviewer_role = "admin" if is_admin else "analyst"
        effective_payload = modified_payload if modified_payload else json.loads(row["payload_json"])

        cursor.execute(
            "UPDATE actions SET status=?, reviewer_id=?, reviewer_role=?, reviewed_at=?, rationale=?, modified_payload_json=?, risk_score=?, risk_level=? WHERE id=?",
            (new_status, user.user_id, reviewer_role, now_iso, rationale, json.dumps(modified_payload) if modified_payload else None, risk_score, risk_level, action_id)
        )

        action_record = dict(row)
        action_record["risk_score"] = risk_score
        action_record["risk_level"] = risk_level
        receipt_data = ReceiptService.create_receipt(
            action=action_record,
            decision=decision,
            reviewer_id=user.user_id,
            reviewer_role=reviewer_role,
            rationale=rationale,
            effective_payload=effective_payload,
            cursor=cursor
        )

        return {
            "message": f"Action {decision.lower()} recorded successfully.",
            "action_id": action_id,
            "status": new_status,
            "reviewer_id": user.user_id,
            "reviewer_role": reviewer_role,
            "reviewed_at": now_iso,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "receipt": receipt_data
        }
