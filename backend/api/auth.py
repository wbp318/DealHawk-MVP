"""FastAPI auth dependencies for extracting the current user from JWT tokens."""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.database.models import User
from backend.services.auth_service import decode_token


def _extract_token(request: Request) -> str | None:
    """Extract Bearer token from Authorization header."""
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    return auth[7:]


def get_current_user_optional(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    """Returns the authenticated user or None. For free-tier compatible endpoints."""
    token = _extract_token(request)
    if not token:
        return None

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None

    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        return None

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    return user


def get_current_user_required(
    request: Request, db: Session = Depends(get_db)
) -> User:
    """Returns the authenticated user or raises 401. For auth-required endpoints."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


def get_pro_user_required(
    current_user: User = Depends(get_current_user_required),
) -> User:
    """Returns the user if they have an active Pro subscription, otherwise 403."""
    if (current_user.subscription_tier or "free") != "pro":
        raise HTTPException(status_code=403, detail="Pro subscription required")
    if (current_user.subscription_status or "active") not in ("active", "past_due"):
        raise HTTPException(status_code=403, detail="Subscription not active")
    return current_user
