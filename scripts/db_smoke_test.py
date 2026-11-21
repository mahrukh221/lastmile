from app.db import SessionLocal
from app.models import Case, User

db = SessionLocal()

user = User(
    email="test@example.com",
    full_name="Test Citizen",
    role="citizen",
    password_hash="not-a-real-hash",
)
db.add(user)
db.commit()
db.refresh(user)

case = Case(citizen_id=user.id)
db.add(case)
db.commit()
db.refresh(case)
print("user id:", user.id, "| case id:", case.id, "| status:", case.status)

db.delete(case)
db.delete(user)
db.commit()
print("saved, read and deleted OK")
db.close()