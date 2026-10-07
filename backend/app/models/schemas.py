"""Pydantic schemas for API requests and responses."""
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

class UserProfile(BaseModel):
    user_id: str
    username: str
    email: str
    roles: List[str]

class DemoLoginRequest(BaseModel):
    role: Literal["viewer", "analyst", "admin"] = "analyst"

class CSRFTokenResponse(BaseModel):
    csrf_token: str

class PolicyBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=120)
    description: str = Field(..., max_length=500)
    action_type: str
    rule_pattern: str
    severity: Literal["low", "medium", "high", "critical"] = "high"
    required_role: Literal["viewer", "analyst", "admin"] = "analyst"
    auto_reject: bool = False
    enabled: bool = True

class PolicyCreate(PolicyBase): pass

class PolicyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rule_pattern: Optional[str] = None
    severity: Optional[Literal["low", "medium", "high", "critical"]] = None
    required_role: Optional[Literal["viewer", "analyst", "admin"]] = None
    auto_reject: Optional[bool] = None
    enabled: Optional[bool] = None

class PolicyResponse(PolicyBase):
    id: str
    created_at: str

class PolicyViolation(BaseModel):
    policy_id: str
    policy_name: str
    severity: str
    required_role: str
    auto_reject: bool
    matched_detail: str

class RiskEvaluation(BaseModel):
    impact_score: int = Field(..., ge=0, le=100)
    reversibility_score: int = Field(..., ge=0, le=100)
    criticality_score: int = Field(..., ge=0, le=100)
    risk_score: int = Field(..., ge=0, le=100)
    risk_level: Literal["low", "medium", "high", "critical"]
    reasons: List[str]
    violations: List[PolicyViolation]
    suggested_minimum_role: Literal["viewer", "analyst", "admin"]

class AdvisoryResponse(BaseModel):
    action_id: str
    provider: str
    model: str
    is_advisory: bool = True
    summary: str
    blast_radius_assessment: str
    security_concerns: List[str]
    suggested_modifications: Optional[str] = None
    offline_deterministic: bool = False

class ActionIngestRequest(BaseModel):
    agent_id: str = Field(..., min_length=2, max_length=64)
    agent_framework: str = Field("custom", max_length=64)
    session_id: str = Field(..., min_length=2, max_length=64)
    action_type: Literal["shell_command", "file_mutation", "database_query", "api_call", "privilege_escalation", "financial_transaction"]
    target_resource: str = Field(..., min_length=1, max_length=256)
    payload: Dict[str, Any]
    intent: str = Field(..., min_length=3, max_length=1000)
    context_metadata: Optional[Dict[str, Any]] = None
    expires_in_minutes: Optional[int] = Field(None, ge=1, le=10080)

class ActionResponse(BaseModel):
    id: str
    agent_id: str
    agent_framework: str
    session_id: str
    action_type: str
    target_resource: str
    payload: Dict[str, Any]
    intent: str
    context_metadata: Optional[Dict[str, Any]] = None
    risk_score: int
    risk_level: str
    status: Literal["pending", "under_review", "approved", "rejected", "modified_and_approved", "expired"]
    reviewer_id: Optional[str] = None
    reviewer_role: Optional[str] = None
    reviewed_at: Optional[str] = None
    rationale: Optional[str] = None
    modified_payload: Optional[Dict[str, Any]] = None
    created_at: str
    expires_at: Optional[str] = None
    violations: Optional[List[PolicyViolation]] = None

class ActionClaimRequest(BaseModel):
    notes: Optional[str] = None

class ActionReviewRequest(BaseModel):
    decision: Literal["APPROVE", "REJECT", "MODIFY_AND_APPROVE"]
    rationale: str = Field(..., min_length=5, max_length=2000)
    modified_payload: Optional[Dict[str, Any]] = None

class ReceiptResponse(BaseModel):
    id: str
    action_id: str
    agent_id: str
    decision: str
    reviewer_id: str
    reviewer_role: str
    signed_at: str
    payload_hash: str
    rationale_hash: str
    receipt_hash: str
    prev_receipt_hash: str
    signature: str
    receipt_data: Dict[str, Any]

class ReceiptVerifyRequest(BaseModel):
    receipt_id: str

class ReceiptVerifyResult(BaseModel):
    receipt_id: str
    is_valid: bool
    signature_valid: bool
    payload_hash_matches: bool
    rationale_hash_matches: bool
    chain_link_intact: bool
    details: str

class BenchmarkAction(BaseModel):
    id: str
    action_type: str
    target_resource: str
    payload: Dict[str, Any]
    intent: str
    ground_truth_destructive: bool
    ground_truth_risk_level: str
    expected_rejection: bool
    category: str

class EvaluationMetrics(BaseModel):
    total_samples: int
    destructive_samples: int
    benign_samples: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    critical_false_negative_rate: float
    confusion_matrix: Dict[str, int]
    breakdown_by_category: Dict[str, Dict[str, Any]]
