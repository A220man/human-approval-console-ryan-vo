"""Grounded LLM advisory endpoints."""
import json
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.auth import get_current_user, require_role, verify_csrf
from app.core.database import get_connection
from app.models.schemas import AdvisoryResponse, UserProfile
from app.services.llm_service import LLMService

router = APIRouter(prefix="/api/actions", tags=["Advisor"])


@router.post("/{action_id}/advisory", response_model=AdvisoryResponse)
async def generate_advisory(
    action_id: str,
    user: UserProfile = Depends(require_role(["viewer", "analyst", "admin"])),
    csrf: None = Depends(verify_csrf)
) -> AdvisoryResponse:
    """
    Generates a grounded advisory explanation for human reviewers.
    Adapts across supported LLM providers or falls back to the deterministic offline engine.
    """
    conn = get_connection()
    row = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Action not found.")

    action_dict = dict(row)
    action_dict["payload"] = json.loads(row["payload_json"])
    action_dict["context_metadata"] = json.loads(row["context_metadata_json"]) if row["context_metadata_json"] else {}

    return await LLMService.get_advisory(action_dict)
