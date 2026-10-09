"""SQLite persistent storage layer with parameterized SQL and transactional context."""
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator
from app.core.config import settings

_local = threading.local()

def get_db_path() -> str:
    p = Path(settings.database_path)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent.parent / settings.database_path
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)

def get_connection() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        conn = sqlite3.connect(get_db_path(), timeout=20.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        _local.conn = conn
    return _local.conn

@contextmanager
def db_transaction() -> Generator[sqlite3.Cursor, None, None]:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE;")
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise

def init_db() -> None:
    conn = get_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS actions (
                id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, agent_framework TEXT NOT NULL,
                session_id TEXT NOT NULL, action_type TEXT NOT NULL, target_resource TEXT NOT NULL,
                payload_json TEXT NOT NULL, intent TEXT NOT NULL, context_metadata_json TEXT,
                risk_score INTEGER NOT NULL, risk_level TEXT NOT NULL, status TEXT NOT NULL,
                reviewer_id TEXT, reviewer_role TEXT, reviewed_at TEXT, rationale TEXT,
                modified_payload_json TEXT, created_at TEXT NOT NULL, expires_at TEXT
            );
            CREATE TABLE IF NOT EXISTS policies (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
                action_type TEXT NOT NULL, rule_pattern TEXT NOT NULL, severity TEXT NOT NULL,
                required_role TEXT NOT NULL, auto_reject INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS receipts (
                id TEXT PRIMARY KEY, action_id TEXT NOT NULL UNIQUE, agent_id TEXT NOT NULL,
                decision TEXT NOT NULL, reviewer_id TEXT NOT NULL, reviewer_role TEXT NOT NULL,
                signed_at TEXT NOT NULL, payload_hash TEXT NOT NULL, rationale_hash TEXT NOT NULL,
                receipt_hash TEXT NOT NULL, prev_receipt_hash TEXT NOT NULL,
                signature TEXT NOT NULL, receipt_data_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY, action_id TEXT, actor_id TEXT NOT NULL,
                actor_role TEXT NOT NULL, event_type TEXT NOT NULL, details_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, username TEXT NOT NULL,
                email TEXT NOT NULL, roles_json TEXT NOT NULL, created_at TEXT NOT NULL,
                expires_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status);
            CREATE INDEX IF NOT EXISTS idx_actions_risk ON actions(risk_level);
        """)
    seed_default_policies()
    seed_sample_actions()

def seed_default_policies() -> None:
    conn = get_connection()
    if conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0] > 0:
        return
    now = datetime.now(timezone.utc).isoformat()
    defaults = [
        ("pol-01-destructive-shell", "Block Destructive Commands", "Blocks rm -rf, mkfs, dd overwrite", "shell_command", r"(?i)\b(rm\s+-[rf]{1,3}|mkfs|dd\s+if=|shutdown|reboot|iptables\s+-F)\b", "critical", "admin", 0, 1, now),
        ("pol-02-drop-database", "Guard Against Schema Deletions", "Flags DROP TABLE and DROP DATABASE", "database_query", r"(?i)\b(DROP\s+TABLE|DROP\s+DATABASE|TRUNCATE\s+TABLE)\b", "critical", "admin", 0, 1, now),
        ("pol-03-wildcard-iam", "Flag Cloud IAM Wildcards", "Restricts AdministratorAccess or '*' actions", "privilege_escalation", r"(?i)(\*:|\"Action\":\s*\"\*\"|AdministratorAccess)", "critical", "admin", 0, 1, now),
        ("pol-04-sys-file-write", "Restrict Root File Overwrites", "Restricts modifications to /etc, /root, ~/.ssh", "file_mutation", r"^(/etc/|/boot/|/root/|\.ssh/|/usr/bin/)", "high", "admin", 0, 1, now),
        ("pol-05-large-financial", "Threshold on Financial Transfers", "Requires review for transactions over $1,000", "financial_transaction", r"amount>1000", "high", "analyst", 0, 1, now),
        ("pol-06-delete-no-where", "Prevent Unfiltered SQL Deletions", "Flags DELETE without a WHERE clause", "database_query", r"(?i)\bDELETE\s+FROM\b", "high", "analyst", 0, 1, now)
    ]
    with conn:
        conn.executemany("INSERT INTO policies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", defaults)

def seed_sample_actions() -> None:
    conn = get_connection()
    if conn.execute("SELECT COUNT(*) FROM actions").fetchone()[0] > 0:
        return
    now = datetime.now(timezone.utc).isoformat()
    raw = [
        ("act-demo-001", "infra-agent-v3", "langchain", "sess-9481", "shell_command", "prod-worker-04",
         {"command": "rm -rf /var/log/app/* && systemctl restart celery-worker"},
         "Clear stale log files to recover disk space on worker node", {"disk_usage": "98%"}, 88, "high"),
        ("act-demo-002", "db-migration-bot", "autogen", "sess-1029", "database_query", "postgres-staging-users",
         {"sql": "ALTER TABLE users ADD COLUMN phone_verified BOOLEAN DEFAULT FALSE;"},
         "Add phone verification tracking column to staging user schema", {"environment": "staging"}, 25, "low"),
        ("act-demo-003", "secops-agent", "crewai", "sess-5512", "privilege_escalation", "aws-iam-role-pipeline",
         {"policy_name": "S3Sync", "statement": {"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "arn:aws:s3:::archive/*"}},
         "Grant read-only access to analytics bucket for disaster recovery", {"ttl_hours": 4}, 45, "medium"),
        ("act-demo-004", "incident-responder", "langchain", "sess-8833", "shell_command", "prod-db-cluster-01",
         {"command": "DROP DATABASE legacy_analytics_archive;"},
         "Drop deprecated database during emergency storage cleanup", {"free_space_mb": 120}, 98, "critical")
    ]
    samples = [(i, a, f, s, t, r, json.dumps(p), it, json.dumps(c), sc, lvl, "pending", None, None, None, None, None, now, None)
               for i, a, f, s, t, r, p, it, c, sc, lvl in raw]
    with conn:
        conn.executemany("INSERT INTO actions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", samples)
