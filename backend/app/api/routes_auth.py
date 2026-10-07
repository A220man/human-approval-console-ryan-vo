"""Authentication endpoints for OIDC and Demo Mode."""
import urllib.parse
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
import httpx
from app.core.auth import CSRF_HEADER_NAME, SESSION_COOKIE_NAME, SessionManager, get_current_user
from app.core.config import settings
from app.core.security import create_csrf_token, generate_pkce_pair, generate_secure_token
from app.models.schemas import CSRFTokenResponse, DemoLoginRequest, UserProfile

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
_pkce_in_flight: Dict[str, Any] = {}

@router.post("/demo-login", response_model=UserProfile)
def demo_login(req: DemoLoginRequest, response: Response, request: Request) -> UserProfile:
    if settings.environment.lower() == "production" or not settings.demo_mode:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Demo login strictly disabled in production.")

    role_map = {
        "viewer": ("demo-viewer", "viewer@demo.local", ["viewer"]),
        "analyst": ("demo-analyst", "analyst@demo.local", ["analyst", "viewer"]),
        "admin": ("demo-admin", "admin@demo.local", ["admin", "analyst", "viewer"]),
    }
    username, email, roles = role_map.get(req.role, ("demo-user", "user@demo.local", [req.role]))
    user_id = f"usr-{req.role}-{generate_secure_token(6)}"

    session_id = SessionManager.create_session(user_id=user_id, username=username, email=email, roles=roles)
    response.set_cookie(key=SESSION_COOKIE_NAME, value=session_id, httponly=True, samesite="lax",
                        secure=(settings.environment.lower() == "production"), max_age=86400, path="/")
    return UserProfile(user_id=user_id, username=username, email=email, roles=roles)

@router.get("/login")
def oidc_login_redirect(request: Request) -> Dict[str, str]:
    verifier, challenge = generate_pkce_pair()
    state, nonce = generate_secure_token(16), generate_secure_token(16)
    _pkce_in_flight[state] = {"verifier": verifier, "nonce": nonce}
    params = {
        "client_id": settings.oidc_client_id, "response_type": "code", "scope": settings.oidc_scopes,
        "redirect_uri": settings.oidc_redirect_uri, "state": state, "nonce": nonce,
        "code_challenge": challenge, "code_challenge_method": "S256"
    }
    return {"authorization_url": f"{settings.oidc_issuer_url.rstrip('/')}/protocol/openid-connect/auth?{urllib.parse.urlencode(params)}", "state": state}

@router.get("/callback")
async def oidc_callback(code: str, state: str, response: Response) -> UserProfile:
    flight = _pkce_in_flight.pop(state, None)
    if not flight: raise HTTPException(status_code=400, detail="Invalid state")
    data = {
        "grant_type": "authorization_code", "client_id": settings.oidc_client_id,
        "client_secret": settings.oidc_client_secret, "code": code,
        "redirect_uri": settings.oidc_redirect_uri, "code_verifier": flight["verifier"]
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"{settings.oidc_issuer_url.rstrip('/')}/protocol/openid-connect/token", data=data)
        if resp.status_code != 200: raise HTTPException(status_code=401, detail="Token exchange failed")
        tokens = resp.json()
        u_resp = await client.get(f"{settings.oidc_issuer_url.rstrip('/')}/protocol/openid-connect/userinfo",
                                  headers={"Authorization": f"Bearer {tokens.get('access_token')}"})
        userinfo = u_resp.json() if u_resp.status_code == 200 else {}

    roles = userinfo.get("roles") or userinfo.get("realm_access", {}).get("roles", ["viewer"])
    user_id = userinfo.get("sub", f"usr-{generate_secure_token(6)}")
    username = userinfo.get("preferred_username", "oidc-user")
    email = userinfo.get("email", "user@oidc.local")

    session_id = SessionManager.create_session(user_id=user_id, username=username, email=email, roles=roles)
    response.set_cookie(key=SESSION_COOKIE_NAME, value=session_id, httponly=True, samesite="lax", max_age=86400, path="/")
    return UserProfile(user_id=user_id, username=username, email=email, roles=roles)

@router.get("/me", response_model=UserProfile)
def get_me(user: UserProfile = Depends(get_current_user)) -> UserProfile:
    return user

@router.post("/logout")
def logout(response: Response, approval_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME)) -> Dict[str, str]:
    if approval_session: SessionManager.destroy_session(approval_session)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"message": "Logged out."}

@router.get("/csrf", response_model=CSRFTokenResponse)
def get_csrf(user: UserProfile = Depends(get_current_user), approval_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME)) -> CSRFTokenResponse:
    return CSRFTokenResponse(csrf_token=create_csrf_token(approval_session or f"bearer-{user.user_id}", settings.secret_key))
