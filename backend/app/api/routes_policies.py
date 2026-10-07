"""Security policy management endpoints."""
import uuid
from datetime import datetime, timezone
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.auth import require_role, verify_csrf
from app.core.database import db_transaction, get_connection
from app.models.schemas import PolicyCreate, PolicyResponse, PolicyUpdate, UserProfile

router = APIRouter(prefix="/api/policies", tags=["Policies"])

@router.get("", response_model=List[PolicyResponse])
def list_policies(user: UserProfile = Depends(require_role(["viewer", "analyst", "admin"]))) -> List[PolicyResponse]:
    rows = get_connection().execute("SELECT * FROM policies ORDER BY created_at ASC").fetchall()
    return [
        PolicyResponse(
            id=r["id"], name=r["name"], description=r["description"], action_type=r["action_type"],
            rule_pattern=r["rule_pattern"], severity=r["severity"], required_role=r["required_role"],
            auto_reject=bool(r["auto_reject"]), enabled=bool(r["enabled"]), created_at=r["created_at"]
        ) for r in rows
    ]

@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
def create_policy(req: PolicyCreate, user: UserProfile = Depends(require_role(["admin"])), csrf: None = Depends(verify_csrf)) -> PolicyResponse:
    pid = f"pol-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    with db_transaction() as cur:
        cur.execute("INSERT INTO policies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (pid, req.name, req.description, req.action_type, req.rule_pattern, req.severity,
                     req.required_role, 1 if req.auto_reject else 0, 1 if req.enabled else 0, now_iso))
    return PolicyResponse(id=pid, name=req.name, description=req.description, action_type=req.action_type,
                          rule_pattern=req.rule_pattern, severity=req.severity, required_role=req.required_role,
                          auto_reject=req.auto_reject, enabled=req.enabled, created_at=now_iso)

@router.put("/{policy_id}", response_model=PolicyResponse)
def update_policy(policy_id: str, req: PolicyUpdate, user: UserProfile = Depends(require_role(["admin"])), csrf: None = Depends(verify_csrf)) -> PolicyResponse:
    conn = get_connection()
    row = conn.execute("SELECT * FROM policies WHERE id = ?", (policy_id,)).fetchone()
    if not row: raise HTTPException(status_code=404, detail="Policy not found.")
    n_name = req.name if req.name is not None else row["name"]
    n_desc = req.description if req.description is not None else row["description"]
    n_pat = req.rule_pattern if req.rule_pattern is not None else row["rule_pattern"]
    n_sev = req.severity if req.severity is not None else row["severity"]
    n_role = req.required_role if req.required_role is not None else row["required_role"]
    n_auto = req.auto_reject if req.auto_reject is not None else bool(row["auto_reject"])
    n_en = req.enabled if req.enabled is not None else bool(row["enabled"])

    with db_transaction() as cur:
        cur.execute("UPDATE policies SET name=?, description=?, rule_pattern=?, severity=?, required_role=?, auto_reject=?, enabled=? WHERE id=?",
                    (n_name, n_desc, n_pat, n_sev, n_role, 1 if n_auto else 0, 1 if n_en else 0, policy_id))
    return PolicyResponse(id=policy_id, name=n_name, description=n_desc, action_type=row["action_type"],
                          rule_pattern=n_pat, severity=n_sev, required_role=n_role, auto_reject=n_auto, enabled=n_en, created_at=row["created_at"])

@router.delete("/{policy_id}")
def delete_policy(policy_id: str, user: UserProfile = Depends(require_role(["admin"])), csrf: None = Depends(verify_csrf)) -> Dict[str, str]:
    if not get_connection().execute("SELECT id FROM policies WHERE id = ?", (policy_id,)).fetchone():
        raise HTTPException(status_code=404, detail="Policy not found.")
    with db_transaction() as cur: cur.execute("DELETE FROM policies WHERE id = ?", (policy_id,))
    return {"message": "Policy deleted."}
