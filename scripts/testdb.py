"""Shared helper for the newer test scripts.

Gives a test its OWN throw-away database (a temp file), migrated with Alembic and seeded
with the five demo accounts. Your real lastmile.db is never touched, and tests do not
need to clean up. Call use_temp_db() BEFORE importing anything from `app`.
"""
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "demo12345"


def use_temp_db() -> None:
    os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp()) / 'test.db'}"
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(cfg, "head")
    import scripts.seed_users  # noqa: F401  (creates the 5 demo accounts when imported)


def make_user(email: str, name: str, role: str, cnic: str | None = None) -> int:
    """Add an extra fake user (a second officer, a second citizen...). Returns its id."""
    from app.db import SessionLocal
    from app.models import User
    from app.security import hash_password

    db = SessionLocal()
    user = User(email=email, full_name=name, role=role, cnic=cnic,
                password_hash=hash_password(PASSWORD))
    db.add(user)
    db.commit()
    user_id = user.id
    db.close()
    return user_id


def user_id(email: str) -> int:
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import User

    db = SessionLocal()
    found = db.scalar(select(User.id).where(User.email == email))
    db.close()
    return found


def login(client, email: str) -> dict:
    r = client.post("/auth/token", data={"username": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}