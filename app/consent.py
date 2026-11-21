"""Subproblem 7: consent. The citizen decides who may use which part of her data.

The rule for the whole platform: before anyone (an officer, a helper, or the system on
her behalf) touches a citizen's data, call `require_consent`. Withdrawing a consent
makes that call fail from the very next request, and the refusal is written to the log.

What can be shared (purpose), and with whom (grantee):
"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.models import Consent, User, utcnow

# purpose -> (grantee, plain-language text shown to the citizen)
PURPOSES: dict[str, tuple[str, str]] = {
    "identity_check": ("system", "Let the system check my identity details against the identity service."),
    "programme_data": ("system", "Let the system read my relief programme record (income, household size)."),
    "payment": ("system", "Let the system check my payment account and send my relief payment."),
    "case_share": ("officer", "Let department officers see my case and my personal details."),
    "helper_access": ("helper", "Let one helper I name act for me on my case."),
}


def has_consent(
    db: Session, citizen_id: int, purpose: str, grantee: str, grantee_user_id: int | None = None
) -> bool:
    query = select(Consent.id).where(
        Consent.citizen_id == citizen_id,
        Consent.purpose == purpose,
        Consent.grantee == grantee,
        Consent.status == "active",
    )
    if grantee_user_id is not None:
        query = query.where(Consent.grantee_user_id == grantee_user_id)
    return db.scalar(query.limit(1)) is not None


def require_consent(
    db: Session,
    citizen_id: int,
    purpose: str,
    grantee: str,
    *,
    grantee_user_id: int | None = None,
    actor: User | None = None,
    actor_role: str | None = None,
    case_id: int | None = None,
) -> None:
    """Stop with 403 unless consent is active. A refusal is saved in the audit log."""
    if has_consent(db, citizen_id, purpose, grantee, grantee_user_id):
        return
    audit.record(
        db, "consent.access_denied", actor=actor, actor_role=actor_role, case_id=case_id,
        details={"citizen_id": citizen_id, "purpose": purpose, "grantee": grantee}, commit=True,
    )
    raise HTTPException(
        403, f"The citizen has not shared '{purpose}' with {grantee}, or has withdrawn it"
    )


def share(
    db: Session, citizen: User, purpose: str, helper_id: int | None = None
) -> tuple[Consent, bool]:
    """Grant a consent. Returns (consent, created). Sharing twice changes nothing."""
    if purpose not in PURPOSES:
        raise HTTPException(422, f"Unknown purpose. Choose one of: {', '.join(PURPOSES)}")
    grantee = PURPOSES[purpose][0]

    if purpose == "helper_access":
        helper = db.get(User, helper_id) if helper_id is not None else None
        if helper is None or helper.role != "helper":
            raise HTTPException(422, "helper_id must be the id of a helper account")
    elif helper_id is not None:
        raise HTTPException(422, "helper_id is only used with the purpose 'helper_access'")

    existing = db.scalar(
        select(Consent).where(
            Consent.citizen_id == citizen.id,
            Consent.purpose == purpose,
            Consent.grantee == grantee,
            Consent.grantee_user_id == helper_id if helper_id is not None
            else Consent.grantee_user_id.is_(None),
            Consent.status == "active",
        )
    )
    if existing is not None:
        return existing, False

    consent = Consent(
        citizen_id=citizen.id, purpose=purpose, grantee=grantee, grantee_user_id=helper_id
    )
    db.add(consent)
    db.flush()
    audit.record(
        db, "consent.shared", actor=citizen,
        details={"consent_id": consent.id, "purpose": purpose, "grantee": grantee,
                 "grantee_user_id": helper_id},
    )
    db.commit()
    db.refresh(consent)
    return consent, True


def withdraw(db: Session, citizen: User, consent_id: int) -> Consent:
    """Take a consent back. Only its owner can; withdrawing twice is harmless."""
    consent = db.get(Consent, consent_id)
    if consent is None or consent.citizen_id != citizen.id:
        raise HTTPException(404, "No such consent")  # same answer for 'not yours'
    if consent.status == "active":
        consent.status = "withdrawn"
        consent.withdrawn_at = utcnow()
        audit.record(
            db, "consent.withdrawn", actor=citizen,
            details={"consent_id": consent.id, "purpose": consent.purpose,
                     "grantee": consent.grantee, "grantee_user_id": consent.grantee_user_id},
        )
        db.commit()
        db.refresh(consent)
    return consent