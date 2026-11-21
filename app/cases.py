"""Subproblem 8: case management. Create, assign, escalate, close, with allowed moves only.

A case is always in exactly one status, and it can only move along the arrows below.
Anything else is refused with 409 and the refusal is written to the audit log.

    new        --assign-->    assigned
    new        --escalate-->  escalated
    assigned   --escalate-->  escalated   (the officer's name is cleared: back to the queue)
    escalated  --assign-->    assigned
    assigned   --assign-->    assigned    (admin reassigns to a different officer)
    new / assigned / escalated --close--> closed   (closed is final)

Who may do what (everything is checked here, on the server):
  create    citizen (for herself) | helper (for a citizen who named them, see consent)
  assign    officer (claims a case for herself) | admin (any officer, can also reassign)
  escalate  citizen/helper (only while the case is "new") | the assigned officer | admin
  close     citizen/helper ("withdrawn" only) | the assigned officer | admin ("rejected"/"withdrawn")
  read      citizen (own) | helper (with consent) | officer (with consent, own or queue) | admin, auditor

Only an officer can close a case as "approved": a human makes that decision.
Officers only see a case while the citizen's 'case_share' consent is active.
"""
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import audit
from app.consent import has_consent, require_consent
from app.models import Case, Consent, User, utcnow

STATUSES = ("new", "assigned", "escalated", "closed")
OPEN_STATUSES = ("new", "assigned", "escalated")
QUEUE_STATUSES = ("new", "escalated")  # waiting for an officer
RESOLUTIONS = ("approved", "rejected", "withdrawn")
PRIORITIES = ("low", "normal", "high", "urgent")

# action -> {status it may start from: status it ends in}.  This table IS the rulebook.
TRANSITIONS: dict[str, dict[str, str]] = {
    "assign": {"new": "assigned", "escalated": "assigned", "assigned": "assigned"},
    "escalate": {"new": "escalated", "assigned": "escalated"},
    "close": {"new": "closed", "assigned": "closed", "escalated": "closed"},
}
_PAST = {"assign": "assigned", "escalate": "escalated", "close": "closed"}


# ---------------------------------------------------------------- reading
def read_problem(db: Session, user: User, case: Case) -> tuple[int, str] | None:
    """None if `user` may read this case, otherwise (http status, reason)."""
    if user.role in ("admin", "auditor"):
        return None
    if user.role == "citizen":
        return None if case.citizen_id == user.id else (404, "No such case")
    if user.role == "helper":
        if has_consent(db, case.citizen_id, "helper_access", "helper", user.id):
            return None
        return 403, "This citizen has not named you as a helper, or has withdrawn it"
    if user.role == "officer":
        if not has_consent(db, case.citizen_id, "case_share", "officer"):
            return 403, "The citizen has not shared this case with officers, or has withdrawn it"
        mine = case.assigned_officer_id == user.id
        in_queue = case.assigned_officer_id is None and case.status in QUEUE_STATUSES
        if mine or in_queue:
            return None
        return 403, "This case belongs to another officer"
    return 403, "Not allowed"


def _refuse(db: Session, user: User, case: Case, action: str, status: int, reason: str):
    audit.record(db, "case.access_denied", actor=user, case_id=case.id,
                 details={"attempted": action, "reason": reason}, commit=True)
    raise HTTPException(status, reason)


def get_readable_case(db: Session, user: User, case_id: int, action: str = "read") -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "No such case")
    problem = read_problem(db, user, case)
    if problem is not None:
        _refuse(db, user, case, action, *problem)
    return case


def visible_cases_query(user: User):
    """The same rules as read_problem, written as a database query for lists."""
    query = select(Case)
    if user.role in ("admin", "auditor"):
        return query
    if user.role == "citizen":
        return query.where(Case.citizen_id == user.id)
    if user.role == "helper":
        named_me = select(Consent.citizen_id).where(
            Consent.purpose == "helper_access", Consent.grantee == "helper",
            Consent.grantee_user_id == user.id, Consent.status == "active")
        return query.where(Case.citizen_id.in_(named_me))
    if user.role == "officer":
        shared = select(Consent.citizen_id).where(
            Consent.purpose == "case_share", Consent.grantee == "officer",
            Consent.status == "active")
        return query.where(
            Case.citizen_id.in_(shared),
            (Case.assigned_officer_id == user.id)
            | (Case.assigned_officer_id.is_(None) & Case.status.in_(QUEUE_STATUSES)),
        )
    return query.where(Case.id == -1)  # unknown role sees nothing


# ---------------------------------------------------------------- the move
def _move(db: Session, case: Case, user: User, action: str, values: dict, details: dict) -> Case:
    """Apply one allowed move. Refuses moves that are not in TRANSITIONS."""
    target = TRANSITIONS[action].get(case.status)
    if target is None:
        audit.record(db, "case.move_refused", actor=user, case_id=case.id,
                     details={"action": action, "from": case.status}, commit=True)
        raise HTTPException(409, f"A case that is '{case.status}' cannot be moved by '{action}'")

    # Guarded update: only succeeds if nobody changed the status since we read it,
    # so two officers cannot both claim the same case.
    result = db.execute(
        update(Case)
        .where(Case.id == case.id, Case.status == case.status)
        .values(status=target, updated_at=utcnow(), **values)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "The case was changed by someone else. Reload and try again.")
    audit.record(db, f"case.{_PAST[action]}", actor=user, case_id=case.id,
                 details={"from": case.status, "to": target, **details})
    db.commit()
    db.refresh(case)
    return case


# ---------------------------------------------------------------- actions
def create_case(db: Session, user: User, citizen_id: int | None) -> Case:
    if user.role == "citizen":
        if citizen_id is not None and citizen_id != user.id:
            raise HTTPException(403, "You can only open a case for yourself")
        owner_id = user.id
    elif user.role == "helper":
        if citizen_id is None:
            raise HTTPException(422, "Send citizen_id: the citizen you are helping")
        owner = db.get(User, citizen_id)
        if owner is None or owner.role != "citizen":
            raise HTTPException(404, "No such citizen")
        require_consent(db, citizen_id, "helper_access", "helper",
                        grantee_user_id=user.id, actor=user)
        owner_id = citizen_id
    else:
        raise HTTPException(403, f"The role '{user.role}' cannot open cases")

    existing = db.scalar(select(Case.id).where(
        Case.citizen_id == owner_id, Case.status.in_(OPEN_STATUSES)))
    if existing is not None:
        raise HTTPException(409, f"This citizen already has an open case (id {existing})")

    case = Case(citizen_id=owner_id, status="new")
    db.add(case)
    db.flush()
    audit.record(db, "case.created", actor=user, case_id=case.id,
                 details={"citizen_id": owner_id, "on_behalf": user.id != owner_id})
    db.commit()
    db.refresh(case)
    return case


def assign_case(db: Session, user: User, case_id: int, officer_id: int | None) -> Case:
    if user.role not in ("officer", "admin"):
        raise HTTPException(403, f"The role '{user.role}' cannot assign cases")
    case = get_readable_case(db, user, case_id, "assign")

    if user.role == "officer":
        if officer_id not in (None, user.id):
            raise HTTPException(403, "Officers can only assign a case to themselves")
        if case.status == "assigned":  # reassigning is an admin move, not a claim
            audit.record(db, "case.move_refused", actor=user, case_id=case.id,
                         details={"action": "assign", "from": case.status,
                                  "why": "already assigned; only an admin can reassign"},
                         commit=True)
            raise HTTPException(409, "This case is already assigned to an officer")
        target_officer = user
    else:  # admin
        if officer_id is None:
            raise HTTPException(422, "Send officer_id: the officer who should get this case")
        target_officer = db.get(User, officer_id)
        if target_officer is None or target_officer.role != "officer":
            raise HTTPException(422, "officer_id must be the id of an officer account")
        if case.status == "assigned" and case.assigned_officer_id == officer_id:
            raise HTTPException(409, "The case is already assigned to this officer")

    return _move(db, case, user, "assign",
                 {"assigned_officer_id": target_officer.id},
                 {"officer_id": target_officer.id, "previous_officer_id": case.assigned_officer_id})


def escalate_case(db: Session, user: User, case_id: int, reason: str) -> Case:
    case = get_readable_case(db, user, case_id, "escalate")
    if user.role in ("citizen", "helper"):
        if case.status != "new":
            audit.record(db, "case.move_refused", actor=user, case_id=case.id,
                         details={"action": "escalate", "from": case.status,
                                  "why": "citizens can only ask for a human while the case is new"},
                         commit=True)
            raise HTTPException(409, "You can ask for a human only while the case is new. "
                                     "After that, an officer already has it.")
    elif user.role == "officer":
        if not (case.status == "new" or case.assigned_officer_id == user.id):
            _refuse(db, user, case, "escalate", 403, "Only the assigned officer can escalate this case")
    elif user.role != "admin":
        raise HTTPException(403, f"The role '{user.role}' cannot escalate cases")

    return _move(db, case, user, "escalate", {"assigned_officer_id": None},
                 {"reason": reason, "previous_officer_id": case.assigned_officer_id})


def close_case(db: Session, user: User, case_id: int, resolution: str, note: str | None) -> Case:
    case = get_readable_case(db, user, case_id, "close")
    if resolution not in RESOLUTIONS:
        raise HTTPException(422, f"resolution must be one of: {', '.join(RESOLUTIONS)}")

    if user.role in ("citizen", "helper"):
        allowed = ("withdrawn",)
    elif user.role == "officer":
        if case.assigned_officer_id != user.id:
            _refuse(db, user, case, "close", 403, "Claim the case before closing it")
        allowed = RESOLUTIONS
    elif user.role == "admin":
        allowed = ("rejected", "withdrawn")
    else:
        raise HTTPException(403, f"The role '{user.role}' cannot close cases")
    if resolution not in allowed:
        _refuse(db, user, case, "close", 403,
                f"The role '{user.role}' may only close a case as: {', '.join(allowed)}")

    note = (note or "").strip() or None
    if resolution == "rejected" and (note is None or len(note) < 3):
        raise HTTPException(422, "A rejected case needs a note that explains why")

    return _move(db, case, user, "close",
                 {"resolution": resolution, "resolution_note": note},
                 {"resolution": resolution, "note": note})