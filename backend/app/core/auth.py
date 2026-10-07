"""Authentication, sessions, RBAC, and CSRF protection."""
import json
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from app.core.config import settings
from app.core.database import db_transaction, get_connection
from app.core.security import verify_csrf_token
from app.models.schemas import UserProfile

SESSION_COOKIE_NAME = "approval_session"
CSRF_HEADER_NAME = "x-csrf-token"

class SessionManager:
    @classmethod
    def create_session(cls, user_id: str, username: str, email: str, roles: List[str], ttl_seconds: int = 86400) -> str:
        sid = f"sess-{uuid.uuid4().hex}"
        exp = int(time.time()) + ttl_seconds
        now_iso = datetime.now(timezone.utc).isoformat()
        with db_transaction() as cur:
            cur.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)", (sid, user_id, username, email, json.dumps(roles), now_iso, exp))
        return sid

    @classmethod
    def get_session(cls, session_id: str) -> Optional[UserProfile]:
        row = get_connection().execute("SELECT user_id, username, email, roles_json, expires_at FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        if not row: return None
        if int(time.time()) > row["expires_at"]:
            cls.destroy_session(session_id); return None
        return UserProfile(user_id=row["user_id"], username=row["username"], email=row["email"], roles=json.loads(row["roles_json"]))

    @classmethod
    def destroy_session(cls, session_id: str) -> None:
        with db_transaction() as cur: cur.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

def get_current_user_optional(approval_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME), authorization: Optional[str] = Header(None)) -> Optional[UserProfile]:
    sid = approval_session or (authorization.replace("Bearer ", "").strip() if authorization and authorization.startswith("Bearer sess-") else None)
    return SessionManager.get_session(sid) if sid else None

def get_current_user(current_user: Optional[UserProfile] = Depends(get_current_user_optional)) -> UserProfile:
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.", headers={"WWW-Authenticate": "Bearer"})
    return current_user

def require_role(allowed_roles: List[str]):
    def role_checker(user: UserProfile = Depends(get_current_user)) -> UserProfile:
        if "admin" in user.roles or any(r in user.roles for r in allowed_roles):
            return user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Access denied. Requires one of: {', '.join(allowed_roles)}")
    return role_checker

def verify_csrf(request: Request, approval_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME), csrf_token: Optional[str] = Header(None, alias=CSRF_HEADER_NAME)) -> None:
    if request.method in ("GET", "HEAD", "OPTIONS"): return
    if request.headers.get("authorization", "").startswith("Bearer "): return
    if approval_session and (not csrf_token or not verify_csrf_token(csrf_token, approval_session, settings.secret_key)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed: missing or invalid X-CSRF-Token.")
