"""Subproblem 6 checks.   python -m scripts.audit_test"""
from scripts.testdb import login, use_temp_db

use_temp_db()

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app import audit  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AuditLog, User  # noqa: E402

client = TestClient(app)
db = SessionLocal()
citizen = db.scalar(select(User).where(User.email == "citizen@example.com"))

# 1. A user action is stored with who, what, which case and the details
entry = audit.record(db, "demo.thing", actor=citizen, case_id=None,
                     details={"note": "hello", "password": "hunter2", "nested": {"api_key": "lm_x"}},
                     commit=True)
assert entry.id and entry.actor_id == citizen.id and entry.actor_role == "citizen"
assert entry.details["note"] == "hello"
assert entry.details["password"] == "[hidden]" and entry.details["nested"]["api_key"] == "[hidden]"
print("1. a user action is saved with actor, role and details; passwords and keys are hidden")

# 2. AI, system and anonymous actors
ai = audit.record(db, "ai.classified", actor_role=audit.ACTOR_AI, details={"confidence": 0.62})
sysd = audit.record(db, "system.job")
anon = audit.record(db, "demo.anon", actor_role=audit.ACTOR_ANONYMOUS, commit=True)
assert (ai.actor_role, ai.actor_id) == ("ai", None)
assert (sysd.actor_role, sysd.actor_id) == ("system", None)
assert anon.actor_role == "anonymous"
print("2. AI, system and anonymous actions are recorded too")

# 3. The entry is saved in the SAME transaction as the change: roll back = both gone
before = db.query(AuditLog).count()
audit.record(db, "demo.rolled_back")
db.rollback()
assert db.query(AuditLog).count() == before
print("3. an entry that is not committed disappears with a rolled-back change")

# 4. Append-only
row = db.scalar(select(AuditLog).where(AuditLog.action == "demo.thing"))
row.action = "tampered"
try:
    db.commit()
    raise SystemExit("FAIL: an audit entry was changed")
except RuntimeError:
    db.rollback()
db.delete(db.scalar(select(AuditLog).where(AuditLog.action == "demo.thing")))
try:
    db.commit()
    raise SystemExit("FAIL: an audit entry was deleted")
except RuntimeError:
    db.rollback()
assert db.scalar(select(AuditLog).where(AuditLog.action == "demo.thing")).action == "demo.thing"
print("4. changing or deleting a saved entry is refused")

# 5. Existing flows now write to the log
client.post("/auth/token", data={"username": "citizen@example.com", "password": "wrong-password"})
client.post("/auth/token", data={"username": "citizen@example.com", "password": "demo12345"})
r = client.post("/auth/register", json={"email": "fresh@example.com", "full_name": "Fresh User",
                                        "password": "longenough1"})
assert r.status_code == 201
admin = login(client, "admin@example.com")
created = client.post("/admin/api-keys", json={"name": "Audit test key"}, headers=admin).json()
client.post(f"/admin/api-keys/{created['id']}/revoke", headers=admin)
client.post(f"/admin/api-keys/{created['id']}/revoke", headers=admin)  # twice: logged once
web = TestClient(app)
web.post("/login", data={"email": "officer@example.com", "password": "demo12345"})
web.get("/logout")

auditor = login(client, "auditor@example.com")
log = client.get("/audit/log?limit=500", headers=auditor).json()
actions = [e["action"] for e in log]
for expected in ("auth.login_failed", "auth.login", "auth.registered", "apikey.created",
                 "apikey.revoked", "auth.logout"):
    assert expected in actions, (expected, actions)
assert actions.count("apikey.revoked") == 1
assert created["api_key"] not in str(log), "the plain API key leaked into the log"
failed = next(e for e in log if e["action"] == "auth.login_failed")
assert failed["actor_role"] == "anonymous" and "wrong-password" not in str(failed)
print("5. login, failed login, register, logout, key create/revoke are all logged; no secrets in it")

# 6. Who can read the log
assert client.get("/audit/log").status_code == 401
for email in ("citizen@example.com", "helper@example.com", "officer@example.com", "admin@example.com"):
    assert client.get("/audit/log", headers=login(client, email)).status_code == 403, email
print("6. only the auditor can read the log; everyone else gets 403, visitors 401")

# 7. Filters and paging
only_keys = client.get("/audit/log?action=apikey.", headers=auditor).json()
assert only_keys and all(e["action"].startswith("apikey.") for e in only_keys)
page = client.get("/audit/log?limit=2", headers=auditor).json()
assert len(page) == 2 and page[0]["id"] > page[1]["id"]  # newest first
assert client.get("/audit/log?limit=0", headers=auditor).status_code == 422
print("7. filter by action prefix, newest-first paging, bad limits rejected")

db.close()
print("ALL AUDIT CHECKS PASSED")