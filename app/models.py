from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, event

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    cnic: Mapped[str | None] = mapped_column(String(15), index=True)  # mock numbers only
    role: Mapped[str] = mapped_column(String(20))  # citizen, helper, officer, admin, auditor
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    citizen_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    assigned_officer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    amount: Mapped[int] = mapped_column(Integer, default=0)
        # low, normal, high, urgent (the officer queue will sort on this)
    priority: Mapped[str] = mapped_column(String(10), default="normal", server_default="normal")
    # set only when status == "closed": approved, rejected or withdrawn
    resolution: Mapped[str | None] = mapped_column(String(20))
    resolution_note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    actor_role: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(100), index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    

class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    prefix: Mapped[str] = mapped_column(String(12))  # first characters, only to tell keys apart
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # SHA-256 of the key
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The audit log is append-only: the ORM refuses to change or delete a saved entry.
@event.listens_for(AuditLog, "before_update")
@event.listens_for(AuditLog, "before_delete")
def _audit_log_is_append_only(mapper, connection, target):
    raise RuntimeError("audit_log is append-only: entries cannot be changed or deleted")
class Consent(Base):
    """One permission a citizen has shared. Withdrawing keeps the row (status "withdrawn")
    so the history stays visible; sharing again creates a new row."""

    __tablename__ = "consents"

    id: Mapped[int] = mapped_column(primary_key=True)
    citizen_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(40), index=True)  # see app/consent.py PURPOSES
    grantee: Mapped[str] = mapped_column(String(20))  # system, officer or helper
    grantee_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # helper only
    status: Mapped[str] = mapped_column(String(12), default="active", index=True)  # active, withdrawn
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))