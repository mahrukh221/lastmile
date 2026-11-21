from fastapi import APIRouter, Depends

from app.deps import require_role
from app.models import User

router = APIRouter(prefix="/demo", tags=["Role check demo (temporary)"])


@router.get("/citizen-area")
def citizen_area(user: User = Depends(require_role("citizen", "helper"))):
    return {"message": f"Hello {user.full_name}, this is the citizen area", "role": user.role}


@router.get("/officer-area")
def officer_area(user: User = Depends(require_role("officer"))):
    return {"message": f"Hello {user.full_name}, this is the officer area", "role": user.role}


@router.get("/admin-area")
def admin_area(user: User = Depends(require_role("admin"))):
    return {"message": f"Hello {user.full_name}, this is the admin area", "role": user.role}


@router.get("/auditor-area")
def auditor_area(user: User = Depends(require_role("auditor"))):
    return {"message": f"Hello {user.full_name}, this is the auditor area", "role": user.role}