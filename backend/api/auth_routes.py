"""Auth endpoints: register, login, refresh, me."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.api.auth import get_current_user_required
from backend.database.models import User
from backend.services.auth_service import (
    register_user,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    DuplicateEmailError,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])


# --- Request/Response Models ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str | None = Field(None, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: str | None
    is_active: bool
    created_at: str


# --- Endpoints ---

@auth_router.post("/register", response_model=TokenResponse, status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Create a new user account and return tokens."""
    try:
        user = register_user(
            email=req.email,
            password=req.password,
            display_name=req.display_name,
            db=db,
        )
    except DuplicateEmailError:
        raise HTTPException(status_code=409, detail="Email already registered")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@auth_router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate and return tokens."""
    user = authenticate_user(email=req.email, password=req.password, db=db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@auth_router.post("/refresh", response_model=TokenResponse)
def refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a refresh token for new access + refresh tokens."""
    payload = decode_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@auth_router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user_required)):
    """Return the currently authenticated user's profile."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        is_active=current_user.is_active,
        created_at=str(current_user.created_at),
    )
