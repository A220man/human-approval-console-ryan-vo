"""Approval receipt querying, export, and cryptographic verification endpoints."""
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from app.core.auth import get_current_user, require_role, verify_csrf
from app.core.database import get_connection
from app.models.schemas import ChainVerifyResult, ReceiptResponse, ReceiptVerifyRequest, ReceiptVerifyResult, UserProfile
from app.services.receipt_service import ReceiptService

router = APIRouter(prefix="/api/receipts", tags=["Receipts"])


@router.get("", response_model=Dict[str, Any])
def list_receipts(
    decision: Optional[str] = Query(None),
    action_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: UserProfile = Depends(require_role(["viewer", "analyst", "admin"]))
) -> Dict[str, Any]:
    """Lists signed approval receipts with filtering and search."""
    conn = get_connection()
    q = "SELECT * FROM receipts WHERE 1=1"
    params: List[Any] = []
    if decision:
        q += " AND decision = ?"; params.append(decision)
    if action_id:
        q += " AND action_id = ?"; params.append(action_id)
    if search:
        q += " AND (id LIKE ? OR action_id LIKE ? OR reviewer_id LIKE ? OR agent_id LIKE ?)"
        st = f"%{search}%"; params.extend([st, st, st, st])

    total_count = conn.execute(q.replace("SELECT *", "SELECT COUNT(*)", 1), params).fetchone()[0]
    q += " ORDER BY rowid DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(q, params).fetchall()
    receipts = [
        ReceiptResponse(
            id=r["id"], action_id=r["action_id"], agent_id=r["agent_id"], decision=r["decision"],
            reviewer_id=r["reviewer_id"], reviewer_role=r["reviewer_role"], signed_at=r["signed_at"],
            payload_hash=r["payload_hash"], rationale_hash=r["rationale_hash"], receipt_hash=r["receipt_hash"],
            prev_receipt_hash=r["prev_receipt_hash"], signature=r["signature"], receipt_data=json.loads(r["receipt_data_json"])
        ) for r in rows
    ]

    return {"total": total_count, "limit": limit, "offset": offset, "items": receipts}


@router.get("/{receipt_id}", response_model=ReceiptResponse)
def get_receipt(
    receipt_id: str,
    user: UserProfile = Depends(require_role(["viewer", "analyst", "admin"]))
) -> ReceiptResponse:
    """Retrieves full details for a signed approval receipt."""
    receipt = ReceiptService.get_receipt_by_id(receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found.")

    return ReceiptResponse(
        id=receipt["id"],
        action_id=receipt["action_id"],
        agent_id=receipt["agent_id"],
        decision=receipt["decision"],
        reviewer_id=receipt["reviewer_id"],
        reviewer_role=receipt["reviewer_role"],
        signed_at=receipt["signed_at"],
        payload_hash=receipt["payload_hash"],
        rationale_hash=receipt["rationale_hash"],
        receipt_hash=receipt["receipt_hash"],
        prev_receipt_hash=receipt["prev_receipt_hash"],
        signature=receipt["signature"],
        receipt_data=json.loads(receipt["receipt_data_json"])
    )


@router.get("/{receipt_id}/export")
def export_receipt_markdown(
    receipt_id: str,
    user: UserProfile = Depends(require_role(["viewer", "analyst", "admin"]))
) -> Response:
    """Exports approval receipt in human-readable and cryptographically provable Markdown."""
    markdown_content = ReceiptService.format_markdown(receipt_id)
    return Response(
        content=markdown_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{receipt_id}.md"'}
    )


@router.post("/verify", response_model=ReceiptVerifyResult)
def verify_receipt_integrity(
    req: ReceiptVerifyRequest,
    user: UserProfile = Depends(require_role(["viewer", "analyst", "admin"])),
    csrf: None = Depends(verify_csrf)
) -> ReceiptVerifyResult:
    """
    Verifies the cryptographic HMAC-SHA256 signature, payload canonical hash,
    decision rationale hash, and audit hash-chain continuity.
    """
    return ReceiptService.verify_receipt(req.receipt_id)


@router.post("/verify-chain", response_model=ChainVerifyResult)
def verify_audit_chain(
    user: UserProfile = Depends(require_role(["viewer", "analyst", "admin"])),
    csrf: None = Depends(verify_csrf)
) -> ChainVerifyResult:
    """
    Verifies unbroken cryptographic HMAC-SHA256 hash-chain integrity
    across all approval receipts from the genesis block to head.
    """
    return ReceiptService.verify_chain()
