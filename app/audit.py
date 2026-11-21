"""Subproblem 6: ONE helper that records every action.

Every user, AI and system action goes through `record()`. Nothing else writes to
the audit_log table, and the ORM refuses to change or delete a saved entry.

Action names are "area.verb" (for example: auth.login, case.escalated, consent.withdrawn).

Who acted (actor_role):
  - a real user      -> pass actor=user; the role comes from the user (citizen, officer, ...)
  - the AI           -> actor_role=ACTOR_AI      (later phases)
  - the platform     -> actor_role=ACTOR_SYSTEM  (default when no actor is given)
  - not logged in    -> actor_role=ACTOR_ANONYMOUS
  - a partner's key  -> actor_role=ACTOR_API_KEY
"""
from sqlalchemy.orm import Session

from app.models import AuditLog, User

ACTOR_AI = "ai"
ACTOR_SYSTEM = "system"
ACTOR_ANONYMOUS = "anonymous"
ACTOR_API_KEY = "api_key"

# Anything stored under one of these names is replaced before it is saved,
# so a password or key can never end up in the log by accident.
_SECRET_NAMES = {
    "password", "password_hash", "token", "access_token", "api_key",
    "key_hash", "secret", "authorization",
}


def _clean(value):
    """Make details safe to store: hide secrets and keep everything JSON-friendly."""
    if isinstance(value, dict):
        return {
            str(k): "[hidden]" if str(k).lower() in _SECRET_NAMES else _clean(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_clean(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)  # dates and other objects


def record(
    db: Session,
    action: str,
    *,
    actor: User | None = None,
    actor_role: str | None = None,
    case_id: int | None = None,
    details: dict | None = None,
    commit: bool = False,
) -> AuditLog:
    """Add one entry to the audit log.

    By default the entry is only added to the current transaction, so it is saved in the
    SAME commit as the change it describes: either both are saved or neither. Pass
    commit=True when nothing else is being saved (a refused request, a failed login).
    """
    if actor is not None:
        actor_id, role = actor.id, actor.role
    else:
        actor_id, role = None, actor_role or ACTOR_SYSTEM
    entry = AuditLog(
        actor_id=actor_id,
        actor_role=role,
        action=action[:100],
        case_id=case_id,
        details=_clean(details or {}),
    )
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    else:
        db.flush()  # assigns the id now, and reports problems early
    return entry