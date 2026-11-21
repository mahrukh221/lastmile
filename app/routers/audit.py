from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_role
from app.models import AuditLog, Consent, User

router = APIRouter(prefix="/audit", tags=["Audit (auditor, read-only)"])


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    actor_id: int | None
    actor_role: str
    action: str
    case_id: int | None
    details: dict
class ConsentRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    citizen_id: int
    purpose: str
    grantee: str
    grantee_user_id: int | None
    status: str
    granted_at: datetime
    withdrawn_at: datetime | None

@router.get("/log", response_model=list[AuditOut])
def audit_log(
    action: str | None = Query(None, description="Action name or start of it, e.g. 'case.'"),
    actor_id: int | None = None,
    case_id: int | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    auditor: User = Depends(require_role("auditor")),
    db: Session = Depends(get_db),
):
    """Every recorded action, newest first. Read-only: there is no way to edit or delete."""
    query = select(AuditLog).order_by(AuditLog.id.desc())
    if action:
        query = query.where(AuditLog.action.startswith(action))
    if actor_id is not None:
        query = query.where(AuditLog.actor_id == actor_id)
    if case_id is not None:
        query = query.where(AuditLog.case_id == case_id)
    return db.scalars(query.limit(limit).offset(offset)).all()
@router.get("/consents", response_model=list[ConsentRecordOut])
def all_consents(
    citizen_id: int | None = None,
    auditor: User = Depends(require_role("auditor")),
    db: Session = Depends(get_db),
):
    """Every consent record (active and withdrawn), newest first."""
    query = select(Consent).order_by(Consent.id.desc())
    if citizen_id is not None:
        query = query.where(Consent.citizen_id == citizen_id)
    return db.scalars(query).all()