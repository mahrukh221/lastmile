from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import ApiKey

PASSWORD = "demo12345"
client = TestClient(app)


def bearer(email):
    r = client.post("/auth/token", data={"username": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


admin, officer = bearer("admin@example.com"), bearer("officer@example.com")

# 1. Only an admin can create a key
body = {"name": "Test partner"}
assert client.post("/admin/api-keys", json=body).status_code == 401
assert client.post("/admin/api-keys", json=body, headers=officer).status_code == 403
r = client.post("/admin/api-keys", json=body, headers=admin)
assert r.status_code == 201, r.text
key, key_id = r.json()["api_key"], r.json()["id"]
assert key.startswith("lm_") and len(key) > 30
print("1. only an admin can create a key; the key is shown once:", key[:11] + "...")

# 2. The plain key is not stored anywhere
db = SessionLocal()
record = db.get(ApiKey, key_id)
assert record.key_hash != key and len(record.key_hash) == 64 and key not in record.prefix
db.close()
listing = client.get("/admin/api-keys", headers=admin).json()
assert all("api_key" not in k and "key_hash" not in k for k in listing)
print("2. only a hash is stored; the list never shows the key")

# 3. The key works on the public API
headers = {"X-API-Key": key}
assert client.get("/api/v1/ping", headers=headers).json()["key_name"] == "Test partner"
stats = client.get("/api/v1/stats/cases", headers=headers).json()
assert "total" in stats and "by_status" in stats
print("3. the key works on the public API:", stats)

# 4. No key, a wrong key, and a login token are all refused
assert client.get("/api/v1/ping").status_code == 401
assert client.get("/api/v1/ping", headers={"X-API-Key": "lm_wrong"}).status_code == 401
assert client.get("/api/v1/ping", headers=admin).status_code == 401
print("4. missing, wrong and login-token credentials are refused (401)")

# 5. Usage is recorded
db = SessionLocal()
assert db.get(ApiKey, key_id).last_used_at is not None
db.close()
print("5. last-used time is recorded")

# 6. Revoking: admins only, and it works at once
assert client.post(f"/admin/api-keys/{key_id}/revoke", headers=officer).status_code == 403
r = client.post(f"/admin/api-keys/{key_id}/revoke", headers=admin)
assert r.status_code == 200 and r.json()["revoked_at"] is not None
assert client.get("/api/v1/ping", headers=headers).status_code == 401
assert client.post(f"/admin/api-keys/{key_id}/revoke", headers=admin).status_code == 200
assert client.post("/admin/api-keys/999999/revoke", headers=admin).status_code == 404
print("6. a revoked key stops working immediately; revoking twice is harmless")

# 7. The admin web page
visitor = TestClient(app)
assert visitor.get("/admin/keys", follow_redirects=False).status_code == 303
officer_web = TestClient(app)
officer_web.post("/login", data={"email": "officer@example.com", "password": PASSWORD},
                 follow_redirects=False)
assert officer_web.get("/admin/keys").status_code == 403
admin_web = TestClient(app)
admin_web.post("/login", data={"email": "admin@example.com", "password": PASSWORD},
               follow_redirects=False)
page = admin_web.get("/admin/keys")
assert page.status_code == 200 and "API keys" in page.text
created = admin_web.post("/admin/keys", data={"name": "Page test key"})
assert created.status_code == 200 and "lm_" in created.text and "never be shown again" in created.text
print("7. admin page: visitors are sent to login, officers get 403, admins can create keys")

# Clean up the keys created by this test
db = SessionLocal()
for k in db.scalars(select(ApiKey).where(ApiKey.name.in_(["Test partner", "Page test key"]))):
    db.delete(k)
db.commit()
db.close()

print("ALL API KEY CHECKS PASSED")