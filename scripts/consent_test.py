"""Subproblem 7 checks.   python -m scripts.consent_test"""
from scripts.testdb import login, make_user, use_temp_db, user_id

use_temp_db()

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)
make_user("citizen2@example.com", "Nasreen Akhtar", "citizen")  # no CNIC yet
H = {r: login(client, f"{r}@example.com") for r in ("citizen", "helper", "officer", "admin", "auditor")}
H["citizen2"] = login(client, "citizen2@example.com")
helper_id = user_id("helper@example.com")
citizen_id = user_id("citizen@example.com")

# 1. Only citizens manage consent
assert client.get("/consents").status_code == 401
for role in ("helper", "officer", "admin", "auditor"):
    assert client.get("/consents", headers=H[role]).status_code == 403, role
purposes = client.get("/consents/purposes", headers=H["citizen"]).json()
assert {p["purpose"] for p in purposes} == {"identity_check", "programme_data", "payment",
                                            "case_share", "helper_access"}
print("1. only citizens can manage consent; the purposes are listed in plain words")

# 2. SEE and SHARE
assert client.get("/consents", headers=H["citizen"]).json() == []
r = client.post("/consents", json={"purpose": "case_share"}, headers=H["citizen"])
assert r.status_code == 201 and r.json()["grantee"] == "officer" and r.json()["status"] == "active"
share_id = r.json()["id"]
again = client.post("/consents", json={"purpose": "case_share"}, headers=H["citizen"])
assert again.status_code == 200 and again.json()["id"] == share_id
assert len(client.get("/consents", headers=H["citizen"]).json()) == 1
print("2. sharing works; sharing the same thing twice returns the same record")

# 3. Bad requests
post = lambda body: client.post("/consents", json=body, headers=H["citizen"]).status_code  # noqa: E731
assert post({"purpose": "sell_my_data"}) == 422
assert post({"purpose": "helper_access"}) == 422                                  # no helper
assert post({"purpose": "helper_access", "helper_id": user_id("officer@example.com")}) == 422
assert post({"purpose": "helper_access", "helper_id": 99999}) == 422
assert post({"purpose": "payment", "helper_id": helper_id}) == 422                # helper_id misuse
print("3. unknown purposes, missing or wrong helpers are refused (422)")

# 4. Helper consent names ONE helper
r = client.post("/consents", json={"purpose": "helper_access", "helper_id": helper_id}, headers=H["citizen"])
assert r.status_code == 201 and r.json()["grantee_user_id"] == helper_id
helper_consent = r.json()["id"]
print("4. a citizen can name a helper")

# 5. WITHDRAW: only the owner; twice is harmless
assert client.post(f"/consents/{share_id}/withdraw", headers=H["citizen2"]).status_code == 404
assert client.post("/consents/99999/withdraw", headers=H["citizen"]).status_code == 404
assert client.post(f"/consents/{share_id}/withdraw", headers=H["officer"]).status_code == 403
print("5. someone else's consent cannot be withdrawn (404), and non-citizens get 403")

# 6. WITHDRAWAL REALLY BLOCKS ACCESS (officer and helper)
case = client.post("/cases", headers=H["citizen"]).json()
cid = case["id"]
seen = client.get(f"/cases/{cid}", headers=H["officer"])
assert seen.status_code == 200 and seen.json()["citizen_name"] == "Zainab Bibi"
assert [c["id"] for c in client.get("/cases", headers=H["officer"]).json()] == [cid]
assert client.get(f"/cases/{cid}", headers=H["helper"]).status_code == 200

w = client.post(f"/consents/{share_id}/withdraw", headers=H["citizen"])
assert w.status_code == 200 and w.json()["status"] == "withdrawn" and w.json()["withdrawn_at"]
assert client.get(f"/cases/{cid}", headers=H["officer"]).status_code == 403
assert client.get("/cases", headers=H["officer"]).json() == []
assert client.post(f"/cases/{cid}/assign", json={}, headers=H["officer"]).status_code == 403
assert client.get(f"/cases/{cid}", headers=H["helper"]).status_code == 200     # helper unaffected

client.post(f"/consents/{helper_consent}/withdraw", headers=H["citizen"])
assert client.get(f"/cases/{cid}", headers=H["helper"]).status_code == 403
assert client.post("/cases", json={"citizen_id": citizen_id}, headers=H["helper"]).status_code == 403
print("6. after withdrawal the officer and the helper are blocked at once (detail, list, assign)")

# 7. Sharing again restores access, and the history is kept
back = client.post("/consents", json={"purpose": "case_share"}, headers=H["citizen"])
assert back.status_code == 201 and back.json()["id"] != share_id
assert client.get(f"/cases/{cid}", headers=H["officer"]).status_code == 200
mine = client.get("/consents", headers=H["citizen"]).json()
assert sorted(c["status"] for c in mine) == ["active", "withdrawn", "withdrawn"]
print("7. sharing again gives a NEW record; the withdrawn one stays in the history")

# 8. withdrawing twice does not add a second log entry
n = lambda: len([e for e in client.get("/audit/log?action=consent.withdrawn&limit=500",  # noqa: E731
                                       headers=H["auditor"]).json()])
before = n()
assert client.post(f"/consents/{share_id}/withdraw", headers=H["citizen"]).status_code == 200
assert n() == before
print("8. withdrawing twice is harmless and logged once")

# 9. CORRECT my data
assert client.get("/consents/my-data", headers=H["citizen"]).json()["full_name"] == "Zainab Bibi"
r = client.patch("/consents/my-data", json={"full_name": "  Zainab Bibi Memon "}, headers=H["citizen"])
assert r.status_code == 200 and r.json()["full_name"] == "Zainab Bibi Memon"
assert client.patch("/consents/my-data", json={}, headers=H["citizen"]).status_code == 422
assert client.patch("/consents/my-data", json={"cnic": "12345"}, headers=H["citizen"]).status_code == 422
r = client.patch("/consents/my-data", json={"cnic": "00000-0000009-9"}, headers=H["citizen"])
assert r.status_code == 409, "a CNIC that is already set must not be changeable here"
assert client.get("/consents/my-data", headers=H["citizen"]).json()["cnic"] == "00000-0000001-1"
r = client.patch("/consents/my-data", json={"cnic": "00000-0000002-2"}, headers=H["citizen2"])
assert r.status_code == 200 and r.json()["cnic"] == "00000-0000002-2"   # missing CNIC can be filled in
print("9. names can be corrected; a missing CNIC can be filled in; an existing CNIC cannot be changed")

# 10. The auditor sees all of it
actions = [e["action"] for e in client.get("/audit/log?limit=500", headers=H["auditor"]).json()]
for expected in ("consent.shared", "consent.withdrawn", "consent.access_denied", "profile.corrected"):
    assert expected in actions, expected
fixes = client.get("/audit/log?action=profile.corrected", headers=H["auditor"]).json()
assert len(fixes) == 2
assert {"old": "Zainab Bibi", "new": "Zainab Bibi Memon"} in [f["details"].get("full_name") for f in fixes]
assert {"old": None, "new": "00000-0000002-2"} in [f["details"].get("cnic") for f in fixes]
records = client.get("/audit/consents", headers=H["auditor"]).json()
assert {r["status"] for r in records} == {"active", "withdrawn"}
assert len(client.get(f"/audit/consents?citizen_id={citizen_id}", headers=H["auditor"]).json()) == 3
print("10. sharing, withdrawing, refused access and corrections all appear in the auditor's views")

print("ALL CONSENT CHECKS PASSED")