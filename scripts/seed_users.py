"""Creates one demo account for each role. All fake. Safe to run more than once."""
from sqlalchemy import select

from app.db import SessionLocal
from app.models import User
from app.security import hash_password

DEMO_PASSWORD = "demo12345"

USERS = [
    # (email, full name, mock CNIC or None, role)
    ("citizen@example.com", "Zainab Bibi", "00000-0000001-1", "citizen"),
    ("helper@example.com", "Rashid Memon", "00000-0000003-3", "helper"),
    ("officer@example.com", "Officer Hina Qureshi", None, "officer"),
    ("admin@example.com", "Admin Salman Naqvi", None, "admin"),
    ("auditor@example.com", "Auditor Maryam Rizvi", None, "auditor"),
]

db = SessionLocal()
for email, name, cnic, role in USERS:
    if db.scalar(select(User).where(User.email == email)):
        print("already exists:", email)
        continue
    db.add(User(email=email, full_name=name, cnic=cnic, role=role,
                password_hash=hash_password(DEMO_PASSWORD)))
    print("created:", email, "->", role)
db.commit()
db.close()
print(f"All demo accounts use the password: {DEMO_PASSWORD}")