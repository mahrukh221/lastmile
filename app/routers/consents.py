from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit, consent as consent_service
from app.db import get_db
from app.deps import require_role
from app.models import Consent, User
from app.schemas import UserOut

router = APIRouter(prefix="/consents", tags=["Consent (citizen)"])

CNIC_PATTERN = r"^\d{5}-\d{7}-\d$"


class ConsentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    purpose: str
    grantee: str
    grantee_user_id: int | None
    status: str
    granted_at: datetime
    withdrawn_at: datetime | None


class ShareRequest(BaseModel):
    purpose: str
    helper_id: int | None = Field(None, description="Only for purpose 'helper_access'")


class CorrectionRequest(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=200)
    cnic: str | None = Field(None, pattern=CNIC_PATTERN)


@router.get("/purposes")
def purposes(citizen: User = Depends(require_role("citizen"))):
    """What can be shared, with whom, in plain words."""
    return [
        {"purpose": name, "shared_with": grantee, "meaning": text}
        for name, (grantee, text) in consent_service.PURPOSES.items()
    ]


@router.get("", response_model=list[ConsentOut])
def my_consents(
    citizen: User = Depends(require_role("citizen")), db: Session = Depends(get_db)
):
    """SEE: everything I have shared, and everything I have taken back."""
    return db.scalars(
        select(Consent).where(Consent.citizen_id == citizen.id).order_by(Consent.id.desc())
    ).all()


@router.post("", response_model=ConsentOut, status_code=201)
def share(
    data: ShareRequest,
    response: Response,
    citizen: User = Depends(require_role("citizen")),
    db: Session = Depends(get_db),
):
    """SHARE: give permission. Sharing something already shared returns it (200)."""
    consent, created = consent_service.share(db, citizen, data.purpose, data.helper_id)
    if not created:
        response.status_code = 200
    return consent


@router.post("/{consent_id}/withdraw", response_model=ConsentOut)
def withdraw(
    consent_id: int,
    citizen: User = Depends(require_role("citizen")),
    db: Session = Depends(get_db),
):
    """WITHDRAW: take the permission back. Access stops with the next request."""
    return consent_service.withdraw(db, citizen, consent_id)


@router.get("/my-data", response_model=UserOut)
def my_data(citizen: User = Depends(require_role("citizen"))):
    """SEE: the personal details the platform holds about me."""
    return citizen


@router.patch("/my-data", response_model=UserOut)
def correct_my_data(
    data: CorrectionRequest,
    citizen: User = Depends(require_role("citizen")),
    db: Session = Depends(get_db),
):
    """CORRECT: fix a wrong name. A CNIC can only be filled in when it is missing;
    changing one that is already set must go through an officer."""
    changes: dict[str, dict] = {}
    if data.full_name is not None and data.full_name.strip() != citizen.full_name:
        changes["full_name"] = {"old": citizen.full_name, "new": data.full_name.strip()}
    if data.cnic is not None and data.cnic != citizen.cnic:
        if citizen.cnic is not None:
            raise HTTPException(
                409, "Your CNIC is already set. To change it, ask an officer through your case."
            )
        changes["cnic"] = {"old": None, "new": data.cnic}
    if data.full_name is None and data.cnic is None:
        raise HTTPException(422, "Send full_name and/or cnic")

    if changes:
        for field, change in changes.items():
            setattr(citizen, field, change["new"])
        audit.record(db, "profile.corrected", actor=citizen, details=changes)
        db.commit()
        db.refresh(citizen)
    return citizen