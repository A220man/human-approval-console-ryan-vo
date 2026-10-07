"""Tests for multi-factor risk scoring engine and policy enforcement."""
from app.services.policy_engine import PolicyEngine
from app.services.risk_engine import RiskEngine


def test_destructive_shell_command_scoring():
    """Verifies that high-impact destructive commands like rm -rf receive critical/high risk scores."""
    result = RiskEngine.analyze(
        action_type="shell_command",
        target_resource="prod-worker-01",
        payload={"command": "rm -rf /var/lib/data/*"}
    )
    assert result.impact_score >= 85
    assert result.reversibility_score <= 15
    assert result.risk_level in ("high", "critical")
    assert any("Recursive file deletion" in reason for reason in result.reasons)


def test_destructive_sql_query_scoring():
    """Verifies that destructive schema drop queries receive critical risk and require admin."""
    result = RiskEngine.analyze(
        action_type="database_query",
        target_resource="prod-postgres-main",
        payload={"sql": "DROP DATABASE user_credentials;"}
    )
    assert result.risk_score >= 85
    assert result.risk_level == "critical"
    assert result.suggested_minimum_role == "admin"


def test_unconditional_sql_delete_detection():
    """Verifies that DELETE queries lacking a WHERE clause trigger policy and high risk."""
    result = RiskEngine.analyze(
        action_type="database_query",
        target_resource="prod-orders",
        payload={"sql": "DELETE FROM customer_orders;"}
    )
    assert result.impact_score >= 90
    assert any("without WHERE clause" in reason for reason in result.reasons)


def test_benign_action_scoring():
    """Verifies that non-destructive queries or status commands receive low risk scores."""
    result = RiskEngine.analyze(
        action_type="shell_command",
        target_resource="dev-sandbox-worker",
        payload={"command": "uptime && ps aux | grep python"}
    )
    assert result.risk_score < 35
    assert result.risk_level == "low"
    assert result.suggested_minimum_role == "viewer"


def test_cloud_iam_wildcard_detection():
    """Verifies that IAM wildcard permissions trigger critical escalation."""
    result = RiskEngine.analyze(
        action_type="privilege_escalation",
        target_resource="aws-iam-role-worker",
        payload={"statement": {"Effect": "Allow", "Action": "*", "Resource": "*"}}
    )
    assert result.risk_level in ("high", "critical")
    assert result.suggested_minimum_role == "admin"


def test_financial_transaction_thresholds():
    """Verifies risk scaling across financial disbursement amounts."""
    micro = RiskEngine.analyze(
        action_type="financial_transaction",
        target_resource="treasury",
        payload={"amount": 45.0}
    )
    assert micro.risk_level == "low"

    large = RiskEngine.analyze(
        action_type="financial_transaction",
        target_resource="treasury",
        payload={"amount": 150000.0}
    )
    assert large.risk_level in ("high", "critical")
    assert large.impact_score >= 90
