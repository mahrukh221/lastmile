import hashlib
import secrets

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.db import get_db
from app.models import ApiKey, User, utcnow

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_api_key(key: str) -> str:
    """SHA-256 is fine here: API keys are long and random, unlike human passwords."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def create_key(db: Session, name: str, admin: User) -> tuple[ApiKey, str]:
    """Returns the saved record AND the plain key. The plain key is never stored."""
    plaintext = "lm_" + secrets.token_urlsafe(32)
    record = ApiKey(
        name=name.strip(),
        prefix=plaintext[:11],
        key_hash=hash_api_key(plaintext),
        created_by=admin.id,
    )
    db.add(record)
    db.flush()
    audit.record(db, "apikey.created", actor=admin,
                 details={"key_id": record.id, "name": record.name, "prefix": record.prefix})
    db.commit()
    db.refresh(record)
    return record, plaintext


def revoke_key(db: Session, key_id: int, actor: User | None = None) -> ApiKey | None:
    record = db.get(ApiKey, key_id)
    if record is None:
        return None
    if record.revoked_at is None:
        record.revoked_at = utcnow()
        audit.record(db, "apikey.revoked", actor=actor,
                     details={"key_id": record.id, "name": record.name, "prefix": record.prefix})
        db.commit()
        db.refresh(record)
    return record


def require_api_key(
    key: str | None = Security(api_key_header),
    db: Session = Depends(get_db),
) -> ApiKey:
    """Use as a route dependency on the public API: Depends(require_api_key)."""
    if not key:
        raise HTTPException(
            401,
            "Missing API key. Send it in the X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    record = db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_api_key(key)))
    if record is None or record.revoked_at is not None:
        raise HTTPException(
            401, "Invalid or revoked API key", headers={"WWW-Authenticate": "ApiKey"}
        )
    record.last_used_at = utcnow()
    db.commit()
    return record