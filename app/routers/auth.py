from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import RegisterRequest, TokenOut, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Login and roles"])


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


@router.post("/register", response_model=UserOut, status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """Self-registration. The role is ALWAYS citizen; the client cannot choose it."""
    email = data.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "This email is already registered")
    user = User(
        email=email,
        full_name=data.full_name.strip(),
        cnic=data.cnic,
        role="citizen",
        password_hash=hash_password(data.password),
    )
    db.add(user)
    db.flush()  # gives the user an id, so the audit entry is saved in the same commit
    audit.record(db, "auth.registered", actor=user, details={"email": email})
    db.commit()
    db.refresh(user)
    return user


@router.post("/token", response_model=TokenOut)
def token(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Log in with email (in the username box) and password. Returns a JWT."""
    user = authenticate(db, form.username, form.password)
    if user is None:
        audit.record(db, "auth.login_failed", actor_role=audit.ACTOR_ANONYMOUS,
                     details={"email": form.username.lower().strip(), "via": "api"}, commit=True)
        raise HTTPException(
            401, "Wrong email or password", headers={"WWW-Authenticate": "Bearer"}
        )
    audit.record(db, "auth.login", actor=user, details={"via": "api"}, commit=True)
    return TokenOut(access_token=create_access_token(user.id, user.role))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user