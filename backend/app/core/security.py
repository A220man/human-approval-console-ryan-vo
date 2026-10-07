"""Cryptographic security utilities for session management, CSRF, and receipt signing."""
import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Dict, Optional, Tuple


def canonical_json_bytes(data: Any) -> bytes:
    """Serializes data into deterministic canonical JSON bytes for hashing and signing."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_digest(data: Any) -> str:
    """Calculates SHA-256 hex digest for arbitrary serializable data or bytes."""
    if isinstance(data, (bytes, bytearray)):
        raw = data
    elif isinstance(data, str):
        raw = data.encode("utf-8")
    else:
        raw = canonical_json_bytes(data)
    return hashlib.sha256(raw).hexdigest()


def sign_hmac_sha256(key: str, message: bytes) -> str:
    """Signs bytes using HMAC-SHA256 with the specified secret key."""
    return hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_hmac_sha256(key: str, message: bytes, signature: str) -> bool:
    """Constant-time verification of HMAC-SHA256 signatures."""
    expected = sign_hmac_sha256(key, message)
    return hmac.compare_digest(expected, signature)


def generate_secure_token(nbytes: int = 32) -> str:
    """Generates a cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(nbytes)


def generate_pkce_pair() -> Tuple[str, str]:
    """Generates PKCE code_verifier and code_challenge (S256)."""
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def create_csrf_token(session_id: str, secret_key: str, expires_in_sec: int = 3600) -> str:
    """Generates a signed, timestamped CSRF token bound to a session."""
    now = int(time.time())
    payload = f"{session_id}:{now}:{now + expires_in_sec}"
    sig = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    token_str = f"{payload}:{sig}"
    return base64.urlsafe_b64encode(token_str.encode("utf-8")).decode("utf-8")


def verify_csrf_token(token: str, session_id: str, secret_key: str) -> bool:
    """Validates signature, session binding, and expiry of a CSRF token."""
    try:
        raw = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        parts = raw.split(":")
        if len(parts) != 4:
            return False
        tok_session_id, _issued, exp_str, sig = parts
        if not hmac.compare_digest(tok_session_id, session_id):
            return False
        exp = int(exp_str)
        if time.time() > exp:
            return False
        payload = f"{parts[0]}:{parts[1]}:{parts[2]}"
        expected_sig = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
        return hmac.compare_digest(expected_sig, sig)
    except Exception:
        return False
