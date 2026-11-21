"""Subproblem 8 checks.   python -m scripts.case_test"""
from scripts.testdb import login, make_user, use_temp_db, user_id

use_temp_db()

from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app import cases as svc  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Case, User  # noqa: E402

client = TestClient(app)
make_user("citizen2@example.com", "Nasreen Akhtar", "citizen", "00000-0000004-4")
make_user("officer2@example.com", "Officer Bilal Shaikh", "officer")
H = {n: login(client, f"{n}@example.com")
     for n in ("citizen", "citizen2", "helper", "officer", "officer2", "admin", "auditor")}
ID = {n: user_id(f"{n}@example.com") for n in H}

call = lambda method, path, who, **kw: getattr(client, method)(path, headers=H[who], **kw)  # noqa: E731

# ---- 1. CREATE ---------------------------------------------------------------
assert client.post("/cases").status_code == 401
for who in ("officer", "admin", "auditor"):
    assert call("post", "/cases", who).status_code == 403, who
r = call("post", "/cases", "citizen")
assert r.status_code == 201 and r.json()["status"] == "new" and r.json()["citizen_id"] == ID["citizen"]
c1 = r.json()["id"]
assert call("post", "/cases", "citizen").status_code == 409                       # one open case each
assert call("post", "/cases", "citizen", json={"citizen_id": ID["citizen2"]}).status_code == 403
assert call("post", "/cases", "helper", json={"citizen_id": ID["citizen2"]}).status_code == 403  # no consent
assert call("post", "/cases", "helper").status_code == 422
call("post", "/consents", "citizen2", json={"purpose": "helper_access", "helper_id": ID["helper"]})
r = call("post", "/cases", "helper", json={"citizen_id": ID["citizen2"]})
assert r.status_code == 201 and r.json()["citizen_id"] == ID["citizen2"]
c2 = r.json()["id"]
print("1. create: citizens for themselves, helpers only with consent, one open case each, others 403")

# ---- 2. READ / LIST (who sees what) -----------------------------------------------
assert call("get", f"/cases/{c1}", "citizen2").status_code == 404                  # not hers
assert call("get", f"/cases/{c1}", "helper").status_code == 403                    # helper of citizen2 only
assert call("get", f"/cases/{c1}", "officer").status_code == 403                   # no case_share yet
assert call("get", "/cases", "officer").json() == []
assert call("get", "/cases", "citizen").json()[0]["id"] == c1 and len(call("get", "/cases", "citizen").json()) == 1
assert [c["id"] for c in call("get", "/cases", "helper").json()] == [c2]
assert {c["id"] for c in call("get", "/cases", "admin").json()} == {c1, c2}
assert {c["id"] for c in call("get", "/cases", "auditor").json()} == {c1, c2}
admin_view = call("get", f"/cases/{c1}", "admin").json()
assert "citizen_name" not in admin_view and "citizen_cnic" not in admin_view     # no personal data
assert call("get", "/cases?status=bogus", "admin").status_code == 422
for cit in ("citizen", "citizen2"):
    call("post", "/consents", cit, json={"purpose": "case_share"})
detail = call("get", f"/cases/{c1}", "officer").json()
assert detail["citizen_name"] == "Zainab Bibi" and detail["citizen_cnic"] == "00000-0000001-1"
assert {c["id"] for c in call("get", "/cases", "officer").json()} == {c1, c2}
assert {c["id"] for c in call("get", "/cases?status=new", "officer2").json()} == {c1, c2}
print("2. read/list rules hold; admins and auditors never see names or CNICs; officers need consent")

# ---- 3. ASSIGN -----------------------------------------------------------------
assert call("post", f"/cases/{c1}/assign", "citizen").status_code == 403
assert call("post", f"/cases/{c1}/assign", "auditor").status_code == 403
assert call("post", f"/cases/{c1}/assign", "officer", json={"officer_id": ID["officer2"]}).status_code == 403
r = call("post", f"/cases/{c1}/assign", "officer")                                  # claim, no body
assert r.status_code == 200 and r.json()["status"] == "assigned" and r.json()["assigned_officer_id"] == ID["officer"]
assert call("post", f"/cases/{c1}/assign", "officer").status_code == 409            # already mine
assert call("post", f"/cases/{c1}/assign", "officer2").status_code == 403           # not his, can't even see it
assert call("get", f"/cases/{c1}", "officer2").status_code == 403
assert c1 not in [c["id"] for c in call("get", "/cases", "officer2").json()]
assert call("post", f"/cases/{c1}/assign", "admin").status_code == 422               # admin must name an officer
assert call("post", f"/cases/{c1}/assign", "admin", json={"officer_id": ID["helper"]}).status_code == 422
assert call("post", f"/cases/{c1}/assign", "admin", json={"officer_id": ID["officer"]}).status_code == 409
r = call("post", f"/cases/{c1}/assign", "admin", json={"officer_id": ID["officer2"]})  # reassign
assert r.status_code == 200 and r.json()["assigned_officer_id"] == ID["officer2"]
assert call("get", f"/cases/{c1}", "officer").status_code == 403                    # officer 1 lost it
print("3. assign: officers claim for themselves, admins assign/reassign, wrong moves get 409/403/422")

# ---- 4. ESCALATE ----------------------------------------------------------------
assert call("post", f"/cases/{c1}/escalate", "citizen", json={"reason": "I want a human"}).status_code == 409  # assigned
assert call("post", f"/cases/{c1}/escalate", "officer", json={"reason": "not mine"}).status_code == 403
assert call("post", f"/cases/{c1}/escalate", "officer2", json={"reason": "x"}).status_code == 422
assert call("post", f"/cases/{c1}/escalate", "auditor", json={"reason": "audit says so"}).status_code == 403
r = call("post", f"/cases/{c1}/escalate", "officer2", json={"reason": "Name does not match the CNIC record"})
assert r.status_code == 200 and r.json()["status"] == "escalated" and r.json()["assigned_officer_id"] is None
assert call("post", f"/cases/{c1}/escalate", "admin", json={"reason": "again?"}).status_code == 409  # escalated->escalated
# a citizen may ask for a human while the case is still new
r = call("post", f"/cases/{c2}/escalate", "citizen2", json={"reason": "I cannot read the form"})
assert r.status_code == 200 and r.json()["status"] == "escalated"
assert {c["id"] for c in call("get", "/cases?status=escalated", "officer").json()} == {c1, c2}
r = call("post", f"/cases/{c1}/assign", "officer")                                  # claim from the queue
assert r.status_code == 200 and r.json()["assigned_officer_id"] == ID["officer"]
print("4. escalate: needs a reason, clears the officer, citizens can ask for a human while new, queue works")

# ---- 5. CLOSE -------------------------------------------------------------------
close = lambda cid, who, res, note=None: call("post", f"/cases/{cid}/close", who,  # noqa: E731
                                              json={"resolution": res, "note": note})
assert close(c1, "citizen", "approved").status_code == 403
assert close(c1, "admin", "approved").status_code == 403                             # only an officer approves
assert close(c1, "officer2", "approved").status_code == 403
assert close(c1, "officer", "paid").status_code == 422
assert close(c1, "officer", "rejected").status_code == 422                           # needs a note
assert close(c1, "auditor", "withdrawn").status_code == 403
assert close(c2, "officer", "approved").status_code == 403                           # c2 unclaimed, must claim first
r = close(c1, "officer", "approved", "All documents match")
assert r.status_code == 200 and r.json()["status"] == "closed"
assert r.json()["resolution"] == "approved" and r.json()["resolution_note"] == "All documents match"
for action, body in (("assign", {"officer_id": ID["officer"]}), ("escalate", {"reason": "reopen?"}),
                     ("close", {"resolution": "withdrawn"})):
    for who in ("admin", "officer"):
        assert call("post", f"/cases/{c1}/{action}", who, json=body).status_code == 409, (action, who)
r = close(c2, "citizen2", "withdrawn", "I changed my mind")                          # citizen withdraws
assert r.status_code == 200 and r.json()["resolution"] == "withdrawn"
assert call("post", "/cases", "citizen").status_code == 201                          # closed -> may open a new one
print("5. close: right roles, right resolutions, notes required for 'rejected'; closed is final")

# ---- 6. admin closes with 'rejected' --------------------------------------------------
c3 = call("get", "/cases?status=new", "admin").json()[0]["id"]
assert close(c3, "admin", "rejected", "Duplicate application").status_code == 200
print("6. admin may close as rejected (with a note)")

# ---- 7. The guarded update: two people racing for one case ---------------------
db1, db2 = SessionLocal(), SessionLocal()
fresh = db1.get(Case, call("post", "/cases", "citizen2").json()["id"])               # status new
stale = db2.get(Case, fresh.id)                                                       # second reader, same moment
officer1, officer2 = (db1.scalar(select(User).where(User.email == e))
                      for e in ("officer@example.com", "officer2@example.com"))
svc._move(db1, fresh, officer1, "assign", {"assigned_officer_id": officer1.id}, {})   # officer 1 wins
try:
    svc._move(db2, stale, officer2, "assign", {"assigned_officer_id": officer2.id}, {})  # officer 2 is late
    raise SystemExit("FAIL: both officers got the same case")
except HTTPException as e:
    assert e.status_code == 409
db1.close(); db2.close()
print("7. two officers cannot both claim the same case (the second gets 409)")

# ---- 8. Every move is in the audit log, and the history views ------------------
log = call("get", f"/audit/log?case_id={c1}&limit=100", "auditor").json()
actions = [e["action"] for e in reversed(log)]
assert actions[0] == "case.created"
for expected in ("case.assigned", "case.escalated", "case.closed", "case.access_denied", "case.move_refused"):
    assert expected in actions, (expected, actions)
esc = next(e for e in log if e["action"] == "case.escalated")
assert esc["details"]["reason"] == "Name does not match the CNIC record" and esc["details"]["to"] == "escalated"

mine = call("get", f"/cases/{c1}/history", "citizen").json()
assert [h["action"] for h in mine][0] == "case.created" and "case.closed" in [h["action"] for h in mine]
assert all(set(h) >= {"created_at", "action", "actor_role"} and h["details"] is None and h["actor_id"] is None
           for h in mine)
assert not {"case.access_denied", "case.move_refused"} & {h["action"] for h in mine}
staff = call("get", f"/cases/{c1}/history", "officer").json()
assert any(h["details"] and h["details"].get("reason") for h in staff)
assert call("get", f"/cases/{c1}/history", "auditor").status_code == 200
assert call("get", f"/cases/{c1}/history", "citizen2").status_code == 404
print("8. every move is logged with its reason; citizens see a safe history, staff see the reasons")

# ---- 9. List rules == single-case rules (they must never disagree) -------------
db = SessionLocal()
everyone = list(db.scalars(select(User)))
for user in everyone:
    listed = {c.id for c in db.scalars(svc.visible_cases_query(user))}
    allowed = {c.id for c in db.scalars(select(Case)) if svc.read_problem(db, user, c) is None}
    assert listed == allowed, (user.email, listed, allowed)
db.close()
print("9. the list query and the single-case check agree for every user")

print("ALL CASE CHECKS PASSED")