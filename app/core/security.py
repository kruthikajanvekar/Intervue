"""
Lightweight auth for the API. Two mechanisms are supported:

1. A static API key (X-API-Key header) - good enough for a demo / internal tool
   and for the frontend calling this backend.
2. Signed session tokens (JWT) minted per-interview so a candidate can only
   act on the interview session they were handed, without needing full
   user accounts.

This is intentionally minimal. Swap in OAuth2 / real user auth for prod use.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Header, HTTPException, status
from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"


def create_session_token(interview_id: str, expires_minutes: int = 180) -> str:
    payload = {
        "sub": interview_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_session_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        interview_id = payload.get("sub")
        if not interview_id:
            raise ValueError("missing subject")
        return interview_id
    except (JWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
        ) from exc


async def verify_session_token(authorization: Optional[str] = Header(default=None)) -> str:
    """FastAPI dependency: extracts and validates `Authorization: Bearer <token>`."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    return decode_session_token(token)
