import time

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import User

PASSWORD = "demo12345"
ROLE_EMAIL = {
    "citizen": "citizen@example.com",
    "helper": "helper@example.com",
    "officer": "officer@example.com",
    "admin": "admin@example.com",
    "auditor": "auditor@example.com",
}
client = TestClient(app)


def login(email, password=PASSWORD):
    return client.post("/auth/token", data={"username": email, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


# 1. Every role can log in; wrong passwords cannot
tokens = {}
for role, email in ROLE_EMAIL.items():
    r = login(email)
    assert r.status_code == 200, (email, r.text)
    tokens[role] = r.json()["access_token"]
print("1. all 5 roles can log in")

assert login("citizen@example.com", "wrong-password").status_code == 401
assert login("nobody@example.com").status_code == 401
print("2. wrong password and unknown email are rejected (401)")

# 3. /auth/me
for role, token in tokens.items():
    me = client.get("/auth/me", headers=bearer(token)).json()
    assert me["role"] == role and "password_hash" not in me
assert client.get("/auth/me").status_code == 401
print("3. /auth/me returns the right role, hides the password hash, and needs login")

# 4. The role matrix: who may open which area
ALLOWED = {
    "/demo/citizen-area": {"citizen", "helper"},
    "/demo/officer-area": {"officer"},
    "/demo/admin-area": {"admin"},
    "/demo/auditor-area": {"auditor"},
}
for path, allowed in ALLOWED.items():
    for role, token in tokens.items():
        status = client.get(path, headers=bearer(token)).status_code
        expected = 200 if role in allowed else 403
        assert status == expected, (path, role, status, expected)
    assert client.get(path).status_code == 401, path
print("4. role matrix OK: 20 role/area pairs and 4 anonymous calls behave correctly")

# 5. Fake and altered tokens
bad = tokens["citizen"][:-3] + ("abc" if not tokens["citizen"].endswith("abc") else "xyz")
assert client.get("/demo/admin-area", headers=bearer(bad)).status_code == 401
forged = jwt.encode({"sub": "1", "role": "admin", "exp": time.time() + 3600},
                    "wrong-secret-wrong-secret-wrong-secret", algorithm="HS256")
assert client.get("/demo/admin-area", headers=bearer(forged)).status_code == 401
expired = jwt.encode({"sub": "1", "role": "admin", "exp": time.time() - 10},
                     settings.secret_key, algorithm="HS256")
assert client.get("/demo/admin-area", headers=bearer(expired)).status_code == 401
print("5. altered, forged and expired tokens are rejected")

# 6. Self-registration can never create a privileged account
new = {"email": "newuser@example.com", "full_name": "New User",
       "password": "longenough1", "role": "admin"}
r = client.post("/auth/register", json=new)
assert r.status_code == 201 and r.json()["role"] == "citizen", r.text
assert client.post("/auth/register", json=new).status_code == 409
assert client.post("/auth/register", json={**new, "email": "x@example.com", "password": "short"}).status_code == 422
db = SessionLocal()
db.delete(db.scalar(select(User).where(User.email == "newuser@example.com")))
db.commit()
db.close()
print("6. registering with role=admin still gives a citizen; duplicates and short passwords refused")

# 7. Browser login with a cookie
web = TestClient(app)
assert web.get("/dashboard", follow_redirects=False).status_code == 303
r = web.post("/login", data={"email": "officer@example.com", "password": PASSWORD},
             follow_redirects=False)
assert r.status_code == 303 and "access_token" in web.cookies
page = web.get("/dashboard")
assert page.status_code == 200 and "Officer Hina Qureshi" in page.text
web.get("/logout", follow_redirects=False)
assert web.get("/dashboard", follow_redirects=False).status_code == 303
print("7. browser login, dashboard and logout work")

print("ALL LOGIN AND ROLE CHECKS PASSED")