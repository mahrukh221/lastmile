from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.apikeys import require_api_key
from app.db import get_db
from app.models import ApiKey, Case

router = APIRouter(prefix="/api/v1", tags=["Public API (needs an X-API-Key)"])


@router.get("/ping")
def ping(key: ApiKey = Depends(require_api_key)):
    """Check that your key works."""
    return {"status": "ok", "key_name": key.name, "prototype": True}


@router.get("/stats/cases")
def case_stats(key: ApiKey = Depends(require_api_key), db: Session = Depends(get_db)):
    """Case counts by status. Totals only, no personal data."""
    rows = db.execute(select(Case.status, func.count()).group_by(Case.status)).all()
    return {"total": sum(count for _, count in rows),
            "by_status": {status: count for status, count in rows}}