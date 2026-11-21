from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.apikeys import create_key, revoke_key
from app.db import get_db
from app.deps import require_role
from app.models import ApiKey, User

router = APIRouter(prefix="/admin/api-keys", tags=["Admin: API keys"])


class KeyCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)


class KeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class KeyCreated(KeyOut):
    api_key: str  # shown ONCE, at creation


@router.post("", response_model=KeyCreated, status_code=201)
def create(
    data: KeyCreate,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Create a key. Copy `api_key` from the answer now: it is never shown again."""
    record, plaintext = create_key(db, data.name, admin)
    return KeyCreated(**KeyOut.model_validate(record).model_dump(), api_key=plaintext)


@router.get("", response_model=list[KeyOut])
def list_keys(
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    return db.scalars(select(ApiKey).order_by(ApiKey.created_at.desc())).all()


@router.post("/{key_id}/revoke", response_model=KeyOut)
def revoke(
    key_id: int,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Switch a key off. It stops working immediately."""
    record = revoke_key(db, key_id,admin)
    if record is None:
        raise HTTPException(404, "No such API key")
    return record