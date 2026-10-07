"""Deterministic policy enforcement engine."""
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from app.core.database import get_connection
from app.models.schemas import PolicyViolation


class PolicyEngine:
    """Evaluates proposed agent actions against stored security and compliance policies."""

    @classmethod
    def get_active_policies(cls) -> List[Dict[str, Any]]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, name, description, action_type, rule_pattern, severity, required_role, auto_reject FROM policies WHERE enabled = 1"
        ).fetchall()
        return [dict(r) for r in rows]

    @classmethod
    def evaluate(cls, action_type: str, target_resource: str, payload: Dict[str, Any]) -> Tuple[List[PolicyViolation], str, bool]:
        """
        Evaluates an action against active policies.
        Returns:
            - violations: List[PolicyViolation]
            - minimum_required_role: 'viewer' | 'analyst' | 'admin'
            - auto_reject: bool
        """
        policies = cls.get_active_policies()
        violations: List[PolicyViolation] = []
        auto_reject = False
        highest_role = "analyst"

        role_hierarchy = {"viewer": 1, "analyst": 2, "admin": 3}

        # Payload strings for regex inspection
        payload_str = json.dumps(payload, ensure_ascii=False)
        combined_text = f"{target_resource}\n{payload_str}"

        for pol in policies:
            # Check action type affinity
            if pol["action_type"] != "all" and pol["action_type"] != action_type:
                continue

            pattern = pol["rule_pattern"]
            matched = False
            matched_snippet = ""

            # Check special financial rule: amount>X
            if action_type == "financial_transaction" and pattern.startswith("amount>"):
                try:
                    threshold = float(pattern.split(">")[1])
                    amount = float(payload.get("amount", 0))
                    if amount > threshold:
                        matched = True
                        matched_snippet = f"Transaction amount ${amount:,.2f} exceeds threshold ${threshold:,.2f}"
                except Exception:
                    pass
            elif "delete-no-where" in pol["id"] or "Unfiltered SQL" in pol["name"]:
                if re.search(r"\bDELETE\s+FROM\b", combined_text, re.IGNORECASE) and not re.search(r"\bWHERE\b", combined_text, re.IGNORECASE):
                    matched = True
                    matched_snippet = "DELETE statement without WHERE filter clause"
            else:
                try:
                    match = re.search(pattern, combined_text, re.IGNORECASE)
                    if match:
                        matched = True
                        matched_snippet = match.group(0)
                except re.error:
                    if pattern.lower() in combined_text.lower():
                        matched = True
                        matched_snippet = pattern

            if matched:
                violation = PolicyViolation(
                    policy_id=pol["id"],
                    policy_name=pol["name"],
                    severity=pol["severity"],
                    required_role=pol["required_role"],
                    auto_reject=bool(pol["auto_reject"]),
                    matched_detail=matched_snippet
                )
                violations.append(violation)
                if violation.auto_reject:
                    auto_reject = True

                # Escalate required role
                req_role = pol["required_role"]
                if role_hierarchy.get(req_role, 1) > role_hierarchy.get(highest_role, 1):
                    highest_role = req_role

        return violations, highest_role, auto_reject
