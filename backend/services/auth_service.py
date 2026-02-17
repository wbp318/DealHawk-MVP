"""Authentication service: password hashing, JWT creation/verification, user management."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy.orm import Session

from backend.config.settings import get_settings
from backend.database.models import User

settings = get_settings()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    """Decode a JWT token. Returns payload dict or None if invalid/expired."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


class DuplicateEmailError(Exception):
    """Raised when trying to register with an already-used email."""
    pass


def register_user(email: str, password: str, display_name: str | None, db: Session) -> User:
    """Create a new user. Raises DuplicateEmailError if email already exists."""
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise DuplicateEmailError("Email already registered")

    user = User(
        email=email,
        hashed_password=hash_password(password),
        display_name=display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# Pre-hashed dummy for constant-time rejection of non-existent users
_DUMMY_HASH = bcrypt.hashpw(b"dummy", bcrypt.gensalt()).decode("utf-8")


def authenticate_user(email: str, password: str, db: Session) -> User | None:
    """Verify email + password. Returns User or None.

    Uses constant-time comparison even for non-existent users to prevent
    timing-based email enumeration.
    """
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        # Run bcrypt anyway to prevent timing difference
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
