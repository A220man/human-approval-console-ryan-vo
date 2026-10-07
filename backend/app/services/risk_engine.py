"""Multi-factor risk analysis and scoring engine."""
import json
import re
from typing import Any, Dict, List, Literal
from app.models.schemas import RiskEvaluation
from app.services.policy_engine import PolicyEngine

class RiskEngine:
    SHELL_PATTERNS = [
        (r"\brm\s+-[rf]{1,3}\b", "Recursive file deletion command detected", 85, 10),
        (r"\bmkfs\b", "Filesystem creation/formatting detected", 95, 5),
        (r"\bdd\s+if=", "Direct block-level disk overwrite detected", 95, 5),
        (r"\b(shutdown|reboot|poweroff|init\s+0)\b", "Host system termination detected", 75, 40),
        (r"\biptables\s+-F\b", "Firewall flush detected", 80, 20),
        (r"\bchmod\s+.*777\b", "World-writable permission grant detected", 80, 40),
        (r"\b(userdel|groupdel)\b", "System user deletion detected", 60, 40),
        (r"\bkill\s+-9\s+-1\b", "Broadcast process kill detected", 80, 30),
    ]

    DB_PATTERNS = [
        (r"\bDROP\s+DATABASE\b", "Database deletion detected", 98, 5),
        (r"\bDROP\s+TABLE\b", "Table drop detected", 90, 15),
        (r"\bTRUNCATE\s+(?:TABLE\s+)?\w+", "Table truncation detected", 85, 20),
        (r"\bALTER\s+TABLE\s+\w+\s+DROP\s+COLUMN\b", "Column drop detected", 75, 25),
    ]

    FILE_PATHS = [
        (r"(?:/etc/|/boot/|/root/|/sys/|/proc/)", "Sensitive system path mutation", 85, 20),
        (r"\.ssh/(?:authorized_keys|id_rsa)", "SSH credential store mutation", 90, 20),
        (r"(?:\.env|secrets\.json)", "Secret configuration overwrite", 80, 40),
        (r"\.\./\.\./", "Directory traversal detected", 75, 50),
    ]

    CLOUD_IAM = [
        (r"(?:AdministratorAccess|\"Action\":\s*\"\*\"|roles/owner|roles/editor)", "Wildcard or owner privilege assignment", 95, 40),
        (r"0\.0\.0\.0/0", "Public network ingress 0.0.0.0/0", 80, 50),
        (r"(?:DeleteBucket|DeleteVpc|DeleteCluster)", "Cloud infrastructure asset deletion", 90, 10),
    ]

    @classmethod
    def analyze(cls, action_type: str, target_resource: str, payload: Dict[str, Any], context_metadata: Dict[str, Any] | None = None) -> RiskEvaluation:
        reasons: List[str] = []
        payload_str = json.dumps(payload, ensure_ascii=False)
        target_lower = target_resource.lower()

        impact_score = 15
        reversibility_score = 90

        if action_type == "shell_command":
            cmd = str(payload.get("command", ""))
            for pat, desc, imp, rev in cls.SHELL_PATTERNS:
                if re.search(pat, cmd, re.IGNORECASE):
                    impact_score, reversibility_score = max(impact_score, imp), min(reversibility_score, rev)
                    reasons.append(desc)

        elif action_type == "database_query":
            sql = str(payload.get("sql", "") or payload.get("query", ""))
            for pat, desc, imp, rev in cls.DB_PATTERNS:
                if re.search(pat, sql, re.IGNORECASE):
                    impact_score, reversibility_score = max(impact_score, imp), min(reversibility_score, rev)
                    reasons.append(desc)

            if re.search(r"\bDELETE\s+FROM\b", sql, re.IGNORECASE):
                if not re.search(r"\bWHERE\b", sql, re.IGNORECASE):
                    impact_score, reversibility_score = max(impact_score, 95), min(reversibility_score, 10)
                    reasons.append("Unconditional table purge without WHERE clause")
                else:
                    impact_score, reversibility_score = max(impact_score, 50), min(reversibility_score, 50)
                    reasons.append("Scoped table deletion with WHERE filter")
            elif re.search(r"\bUPDATE\b", sql, re.IGNORECASE) and not re.search(r"\bWHERE\b", sql, re.IGNORECASE):
                impact_score, reversibility_score = max(impact_score, 80), min(reversibility_score, 25)
                reasons.append("Unbounded UPDATE without WHERE clause")
            elif not reasons and re.search(r"^\s*SELECT\b", sql, re.IGNORECASE):
                impact_score, reversibility_score = min(impact_score, 10), 100
                reasons.append("Read-only SQL query with zero mutation impact")

        elif action_type == "file_mutation":
            fp = str(payload.get("path", "") or target_resource)
            for pat, desc, imp, rev in cls.FILE_PATHS:
                if re.search(pat, fp, re.IGNORECASE):
                    impact_score, reversibility_score = max(impact_score, imp), min(reversibility_score, rev)
                    reasons.append(desc)

        elif action_type == "privilege_escalation":
            impact_score, reversibility_score = max(impact_score, 60), min(reversibility_score, 60)
            for pat, desc, imp, rev in cls.CLOUD_IAM:
                if re.search(pat, payload_str, re.IGNORECASE):
                    impact_score, reversibility_score = max(impact_score, imp), min(reversibility_score, rev)
                    reasons.append(desc)

        elif action_type == "financial_transaction":
            amt = float(payload.get("amount", 0))
            if amt >= 100000: impact_score, reversibility_score = 95, 15
            elif amt >= 10000: impact_score, reversibility_score = 80, 30
            elif amt >= 1000: impact_score, reversibility_score = 55, 50
            else: impact_score, reversibility_score = 25, 80
            reasons.append(f"Financial transfer of ${amt:,.2f}")

        elif action_type == "api_call":
            meth = str(payload.get("method", "GET")).upper()
            ep = str(payload.get("endpoint", "")).lower()
            if meth in ("DELETE", "POST", "PUT", "PATCH"):
                if any(k in ep or k in target_lower for k in ["vpc", "cluster", "subnet", "firewall", "gateway", "database"]):
                    impact_score, reversibility_score = max(impact_score, 88), min(reversibility_score, 15)
                    reasons.append(f"Destructive HTTP {meth} mutation on infrastructure asset")
                else:
                    impact_score, reversibility_score = max(impact_score, 45), min(reversibility_score, 60)
                    reasons.append(f"HTTP {meth} request")
            else:
                impact_score, reversibility_score = min(impact_score, 15), 100
                reasons.append("Read-only HTTP GET request")

        criticality_score = 40
        env_meta = str(context_metadata or {}).lower()
        if any(t in target_lower or t in env_meta for t in ["prod", "production", "master", "primary", "live", "cluster-01"]):
            criticality_score = 95; reasons.append("Target asset is in production tier")
        elif any(t in target_lower or t in env_meta for t in ["staging", "uat", "preprod"]):
            criticality_score = 55; reasons.append("Target asset is in staging tier")
        elif any(t in target_lower or t in env_meta for t in ["dev", "test", "local", "sandbox"]):
            criticality_score = 20; reasons.append("Target asset is in development tier")

        violations, req_role, _ = PolicyEngine.evaluate(action_type, target_resource, payload)
        for v in violations:
            reasons.append(f"Policy: {v.policy_name} ({v.severity.upper()})")
            if v.severity == "critical": impact_score = max(impact_score, 85)
            elif v.severity == "high": impact_score = max(impact_score, 65)

        raw = (impact_score * 0.45) + ((100 - reversibility_score) * 0.35) + (criticality_score * 0.20)
        risk_score = max(5, min(100, int(round(raw))))

        if risk_score >= 85: risk_level, min_role = "critical", "admin"
        elif risk_score >= 65: risk_level, min_role = "high", "analyst"
        elif risk_score >= 35: risk_level, min_role = "medium", "analyst"
        else: risk_level, min_role = "low", "viewer"

        if req_role == "admin": min_role = "admin"
        if not reasons: reasons.append("Standard operational action")

        return RiskEvaluation(
            impact_score=impact_score, reversibility_score=reversibility_score, criticality_score=criticality_score,
            risk_score=risk_score, risk_level=risk_level, reasons=reasons, violations=violations, suggested_minimum_role=min_role
        )
