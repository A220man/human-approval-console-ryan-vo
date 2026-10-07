"""Role-based human review and decision recording endpoints."""
import json
from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.auth import get_current_user, require_role, verify_csrf
from app.core.database import db_transaction, get_connection
from app.models.schemas import ActionReviewRequest, UserProfile
from app.services.receipt_service import ReceiptService

router = APIRouter(prefix="/api/actions", tags=["Reviews"])


@router.post("/{action_id}/review", response_model=Dict[str, Any])
def submit_review(
    action_id: str,
    req: ActionReviewRequest,
    user: UserProfile = Depends(require_role(["analyst", "admin"])),
    csrf: None = Depends(verify_csrf)
) -> Dict[str, Any]:
    """
    Submits a role-based human decision (APPROVE, REJECT, MODIFY_AND_APPROVE).
    Enforces role thresholds (critical risk strictly requires admin), updates state,
    and generates a cryptographically signed approval receipt.
    """
    conn = get_connection()
    row = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Action not found.")

    if row["status"] in ("approved", "rejected", "modified_and_approved"):
        raise HTTPException(
            status_code=400,
            detail=f"Action '{action_id}' has already been reviewed (status: {row['status']})."
        )

    # Enforce role hierarchy: critical actions mandate admin role
    is_admin = "admin" in user.roles
    if row["risk_level"] == "critical" and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role Denied: Critical risk actions require Administrator authorization to review."
        )

    # Validate decision requirements
    decision = req.decision
    rationale = req.rationale.strip()
    if len(rationale) < 5:
        raise HTTPException(status_code=400, detail="A detailed decision rationale (min 5 characters) is required.")

    modified_payload = None
    if decision == "MODIFY_AND_APPROVE":
        if not req.modified_payload:
            raise HTTPException(
                status_code=400,
                detail="Decision MODIFY_AND_APPROVE requires providing modified_payload parameters."
            )
        modified_payload = req.modified_payload

    new_status = {
        "APPROVE": "approved",
        "REJECT": "rejected",
        "MODIFY_AND_APPROVE": "modified_and_approved"
    }[decision]

    now_iso = datetime.now(timezone.utc).isoformat()
    reviewer_role = "admin" if is_admin else "analyst"
    effective_payload = modified_payload if modified_payload else json.loads(row["payload_json"])

    # Update database record
    with db_transaction() as cursor:
        cursor.execute("""
            UPDATE actions 
            SET status = ?, reviewer_id = ?, reviewer_role = ?, reviewed_at = ?,
                rationale = ?, modified_payload_json = ?
            WHERE id = ?
        """, (
            new_status,
            user.user_id,
            reviewer_role,
            now_iso,
            rationale,
            json.dumps(modified_payload) if modified_payload else None,
            action_id
        ))

    # Generate immutable cryptographic approval receipt
    receipt_data = ReceiptService.create_receipt(
        action=dict(row),
        decision=decision,
        reviewer_id=user.user_id,
        reviewer_role=reviewer_role,
        rationale=rationale,
        effective_payload=effective_payload
    )

    return {
        "message": f"Action {decision.lower()} recorded successfully.",
        "action_id": action_id,
        "status": new_status,
        "reviewer_id": user.user_id,
        "reviewer_role": reviewer_role,
        "reviewed_at": now_iso,
        "receipt": receipt_data
    }
