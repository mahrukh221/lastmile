from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import cases as case_service
from app.db import get_db
from app.deps import get_current_user
from app.models import AuditLog, Case, User

router = APIRouter(prefix="/cases", tags=["Cases"])


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    citizen_id: int
    assigned_officer_id: int | None
    status: str
    amount: int
    priority: str
    resolution: str | None
    resolution_note: str | None
    created_at: datetime
    updated_at: datetime


class CaseDetail(CaseOut):
    """What an officer sees: the same case plus the citizen's name and CNIC."""
    citizen_name: str
    citizen_cnic: str | None


class CreateCase(BaseModel):
    citizen_id: int | None = Field(None, description="Helpers only: the citizen being helped")


class AssignRequest(BaseModel):
    officer_id: int | None = Field(None, description="Admin: the officer. Officer: leave empty.")


class EscalateRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class CloseRequest(BaseModel):
    resolution: str = Field(..., description="approved, rejected or withdrawn")
    note: str | None = Field(None, max_length=500)


class HistoryItem(BaseModel):
    created_at: datetime
    action: str
    actor_role: str
    actor_id: int | None = None
    details: dict | None = None


# Entries the citizen should not see in her own case history.
_STAFF_ONLY = ("case.access_denied", "case.move_refused")


@router.post("", response_model=CaseOut, status_code=201)
def create_case(
    data: CreateCase | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Open a case. A citizen opens her own (no body needed); a helper sends citizen_id."""
    return case_service.create_case(db, user, data.citizen_id if data else None)


@router.get("", response_model=list[CaseOut])
def list_cases(
    status: str | None = Query(None, pattern="^(new|assigned|escalated|closed)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The cases YOU are allowed to see, newest first."""
    query = case_service.visible_cases_query(user)
    if status:
        query = query.where(Case.status == status)
    return db.scalars(query.order_by(Case.id.desc())).all()


@router.get("/{case_id}", response_model=CaseDetail | CaseOut)
def get_case(case_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    case = case_service.get_readable_case(db, user, case_id)
    if user.role == "officer":
        citizen = db.get(User, case.citizen_id)
        return CaseDetail(**CaseOut.model_validate(case).model_dump(),
                          citizen_name=citizen.full_name, citizen_cnic=citizen.cnic)
    return CaseOut.model_validate(case)


@router.post("/{case_id}/assign", response_model=CaseOut)
def assign(
    case_id: int, data: AssignRequest | None = None,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Officer: claim a waiting case (no body needed). Admin: send officer_id."""
    return case_service.assign_case(db, user, case_id, data.officer_id if data else None)


@router.post("/{case_id}/escalate", response_model=CaseOut)
def escalate(
    case_id: int, data: EscalateRequest,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Hand the case to a human. It goes back to the waiting queue with the reason attached."""
    return case_service.escalate_case(db, user, case_id, data.reason.strip())


@router.post("/{case_id}/close", response_model=CaseOut)
def close(
    case_id: int, data: CloseRequest,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Close the case with a resolution. 'rejected' needs a note. Only officers can approve."""
    return case_service.close_case(db, user, case_id, data.resolution, data.note)


@router.get("/{case_id}/history", response_model=list[HistoryItem])
def history(case_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """What happened to this case, oldest first. Staff also see who and why."""
    case = case_service.get_readable_case(db, user, case_id, "history")
    entries = db.scalars(
        select(AuditLog).where(AuditLog.case_id == case.id).order_by(AuditLog.id)
    ).all()
    if user.role in ("citizen", "helper"):
        return [HistoryItem(created_at=e.created_at, action=e.action, actor_role=e.actor_role)
                for e in entries if e.action not in _STAFF_ONLY]
    return [HistoryItem(created_at=e.created_at, action=e.action, actor_role=e.actor_role,
                        actor_id=e.actor_id, details=e.details) for e in entries]