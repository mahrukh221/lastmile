from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.apikeys import create_key, revoke_key
from app.db import get_db
from app.deps import get_optional_user
from app.models import ApiKey, User
from app.templating import templates

router = APIRouter(prefix="/admin", include_in_schema=False)


def _denied(user: User | None):
    """A redirect for visitors who are not logged in; a 403 for everyone but admins."""
    if user is None:
        return RedirectResponse("/login", status_code=303)
    if user.role != "admin":
        raise HTTPException(403, "Only admins can manage API keys")
    return None


def _page(request: Request, db: Session, new_key: str | None = None):
    keys = db.scalars(select(ApiKey).order_by(ApiKey.created_at.desc())).all()
    return templates.TemplateResponse(
        request, "admin_keys.html", {"title": "API keys", "keys": keys, "new_key": new_key}
    )


@router.get("/keys", response_class=HTMLResponse)
def keys_page(
    request: Request,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    denied = _denied(user)
    return denied if denied is not None else _page(request, db)


@router.post("/keys", response_class=HTMLResponse)
def keys_create(
    request: Request,
    name: str = Form(..., min_length=3, max_length=100),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    denied = _denied(user)
    if denied is not None:
        return denied
    _, plaintext = create_key(db, name, user)
    return _page(request, db, new_key=plaintext)


@router.post("/keys/{key_id}/revoke")
def keys_revoke(
    key_id: int,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    denied = _denied(user)
    if denied is not None:
        return denied
    revoke_key(db, key_id)
    return RedirectResponse("/admin/keys", status_code=303)