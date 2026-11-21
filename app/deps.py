from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import decode_access_token

ROLES = ("citizen", "helper", "officer", "admin", "auditor")

# auto_error=False: we also accept the token from a browser cookie
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


def get_optional_user(
    request: Request,
    bearer: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """The logged-in user, or None. Reads the token from the header or the cookie."""
    token = bearer or request.cookies.get("access_token")
    if not token:
        return None
    payload = decode_access_token(token)
    if payload is None:
        return None
    # The role is read from the DATABASE, never trusted from the token alone.
    return db.get(User, int(payload["sub"]))


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Not logged in, or the session expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(*allowed: str):
    """Use as a route dependency: Depends(require_role("officer"))."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"The role '{user.role}' is not allowed to do this",
            )
        return user

    return checker