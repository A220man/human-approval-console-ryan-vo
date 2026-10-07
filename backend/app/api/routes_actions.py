"""Agent action ingestion, querying, and claim endpoints."""
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.auth import require_role, verify_csrf
from app.core.database import db_transaction, get_connection
from app.models.schemas import ActionClaimRequest, ActionIngestRequest, ActionResponse, UserProfile
from app.services.policy_engine import PolicyEngine
from app.services.risk_engine import RiskEngine

router = APIRouter(prefix="/api/actions", tags=["Actions"])

@router.post("", response_model=ActionResponse, status_code=status.HTTP_201_CREATED)
def ingest_action(req: ActionIngestRequest, csrf: None = Depends(verify_csrf)) -> ActionResponse:
    action_id = f"act-{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    expires_at = (now + timedelta(minutes=req.expires_in_minutes)).isoformat() if req.expires_in_minutes else None

    risk_eval = RiskEngine.analyze(action_type=req.action_type, target_resource=req.target_resource, payload=req.payload, context_metadata=req.context_metadata)

    with db_transaction() as cur:
        cur.execute("""
            INSERT INTO actions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (action_id, req.agent_id, req.agent_framework, req.session_id, req.action_type, req.target_resource,
              json.dumps(req.payload), req.intent, json.dumps(req.context_metadata or {}), risk_eval.risk_score,
              risk_eval.risk_level, "pending", None, None, None, None, None, now_iso, expires_at))
        cur.execute("INSERT INTO audit_logs VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (f"aud-{uuid.uuid4().hex[:12]}", action_id, req.agent_id, "agent", "ACTION_INGESTED",
                     json.dumps({"risk_score": risk_eval.risk_score, "risk_level": risk_eval.risk_level}), now_iso))

    return ActionResponse(
        id=action_id, agent_id=req.agent_id, agent_framework=req.agent_framework, session_id=req.session_id,
        action_type=req.action_type, target_resource=req.target_resource, payload=req.payload, intent=req.intent,
        context_metadata=req.context_metadata, risk_score=risk_eval.risk_score, risk_level=risk_eval.risk_level,
        status="pending", created_at=now_iso, expires_at=expires_at, violations=risk_eval.violations
    )

@router.get("", response_model=Dict[str, Any])
def list_actions(
    status_filter: Optional[str] = Query(None, alias="status"),
    risk_filter: Optional[str] = Query(None, alias="risk_level"),
    type_filter: Optional[str] = Query(None, alias="action_type"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: UserProfile = Depends(require_role(["viewer", "analyst", "admin"]))
) -> Dict[str, Any]:
    conn = get_connection()
    q = "SELECT * FROM actions WHERE 1=1"
    params: List[Any] = []
    if status_filter: q += " AND status = ?"; params.append(status_filter)
    if risk_filter: q += " AND risk_level = ?"; params.append(risk_filter)
    if type_filter: q += " AND action_type = ?"; params.append(type_filter)
    if search:
        q += " AND (intent LIKE ? OR target_resource LIKE ? OR agent_id LIKE ?)"
        st = f"%{search}%"; params.extend([st, st, st])

    total_count = conn.execute(q.replace("SELECT *", "SELECT COUNT(*)", 1), params).fetchone()[0]
    q += " ORDER BY CASE status WHEN 'pending' THEN 1 WHEN 'under_review' THEN 2 ELSE 3 END ASC, risk_score DESC, created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(q, params).fetchall()
    actions = [
        ActionResponse(
            id=r["id"], agent_id=r["agent_id"], agent_framework=r["agent_framework"], session_id=r["session_id"],
            action_type=r["action_type"], target_resource=r["target_resource"], payload=json.loads(r["payload_json"]),
            intent=r["intent"], context_metadata=json.loads(r["context_metadata_json"]) if r["context_metadata_json"] else None,
            risk_score=r["risk_score"], risk_level=r["risk_level"], status=r["status"], reviewer_id=r["reviewer_id"],
            reviewer_role=r["reviewer_role"], reviewed_at=r["reviewed_at"], rationale=r["rationale"],
            modified_payload=json.loads(r["modified_payload_json"]) if r["modified_payload_json"] else None,
            created_at=r["created_at"], expires_at=r["expires_at"]
        ) for r in rows
    ]

    stats_row = conn.execute("""
        SELECT COUNT(CASE WHEN status = 'pending' THEN 1 END) AS pending,
               COUNT(CASE WHEN status = 'under_review' THEN 1 END) AS under_review,
               COUNT(CASE WHEN status IN ('approved', 'modified_and_approved') THEN 1 END) AS approved,
               COUNT(CASE WHEN status = 'rejected' THEN 1 END) AS rejected,
               COUNT(CASE WHEN risk_level = 'critical' AND status = 'pending' THEN 1 END) AS critical_pending
        FROM actions
    """).fetchone()

    return {
        "total": total_count, "limit": limit, "offset": offset,
        "stats": dict(stats_row) if stats_row else {"pending": 0, "under_review": 0, "approved": 0, "rejected": 0, "critical_pending": 0},
        "items": actions
    }

@router.get("/{action_id}", response_model=ActionResponse)
def get_action_detail(action_id: str, user: UserProfile = Depends(require_role(["viewer", "analyst", "admin"]))) -> ActionResponse:
    row = get_connection().execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    if not row: raise HTTPException(status_code=404, detail="Action not found.")
    payload = json.loads(row["payload_json"])
    violations, _, _ = PolicyEngine.evaluate(row["action_type"], row["target_resource"], payload)
    return ActionResponse(
        id=row["id"], agent_id=row["agent_id"], agent_framework=row["agent_framework"], session_id=row["session_id"],
        action_type=row["action_type"], target_resource=row["target_resource"], payload=payload, intent=row["intent"],
        context_metadata=json.loads(row["context_metadata_json"]) if row["context_metadata_json"] else None,
        risk_score=row["risk_score"], risk_level=row["risk_level"], status=row["status"], reviewer_id=row["reviewer_id"],
        reviewer_role=row["reviewer_role"], reviewed_at=row["reviewed_at"], rationale=row["rationale"],
        modified_payload=json.loads(row["modified_payload_json"]) if row["modified_payload_json"] else None,
        created_at=row["created_at"], expires_at=row["expires_at"], violations=violations
    )

@router.post("/{action_id}/claim", response_model=ActionResponse)
def claim_action(action_id: str, req: ActionClaimRequest = ActionClaimRequest(), user: UserProfile = Depends(require_role(["analyst", "admin"])), csrf: None = Depends(verify_csrf)) -> ActionResponse:
    row = get_connection().execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    if not row: raise HTTPException(status_code=404, detail="Action not found.")
    if row["status"] not in ("pending", "under_review"): raise HTTPException(status_code=400, detail="Action already processed.")

    role = "admin" if "admin" in user.roles else "analyst"
    now_iso = datetime.now(timezone.utc).isoformat()
    with db_transaction() as cur:
        cur.execute("UPDATE actions SET status = 'under_review', reviewer_id = ?, reviewer_role = ? WHERE id = ?", (user.user_id, role, action_id))
        cur.execute("INSERT INTO audit_logs VALUES (?, ?, ?, ?, ?, ?, ?)", (f"aud-{uuid.uuid4().hex[:12]}", action_id, user.user_id, role, "ACTION_CLAIMED", json.dumps({"notes": req.notes}), now_iso))
    return get_action_detail(action_id, user)
