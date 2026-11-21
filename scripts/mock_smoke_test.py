from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
WIDOW = "00000-0000001-1"

r = client.get(f"/mock/identity/{WIDOW}")
assert r.status_code == 200, r.text
assert r.json()["full_name"] == "Zainab Bibi"
assert "_truth_id" not in r.json()
print("identity lookup OK:", r.json()["full_name"])

assert client.get("/mock/identity/00000-9999999-9").status_code == 404
print("unknown CNIC gives 404 OK")

assert client.get("/mock/identity/not-a-cnic").status_code == 422
print("bad CNIC shape rejected OK")

names = [p["full_name"] for p in client.get("/mock/identity/search", params={"q": "zainab"}).json()]
assert "Zainab Bibi" in names, names
print("name search OK:", names)

assert client.get(f"/mock/data/programme/{WIDOW}").json()["already_paid"] is False
print("programme record OK")

assert client.get(f"/mock/payment/account/{WIDOW}").json()["status"] == "active"
print("payment account OK")

body = {"cnic": WIDOW, "amount": 15000, "idempotency_key": "smoke-key-0001"}
first = client.post("/mock/payment/simulate-transfer", json=body).json()
second = client.post("/mock/payment/simulate-transfer", json=body).json()
assert first["replayed"] is False and second["replayed"] is True
assert first["transfer_id"] == second["transfer_id"]
print("retry-safe transfer OK:", first["transfer_id"])

print("ALL MOCK SERVICE CHECKS PASSED")