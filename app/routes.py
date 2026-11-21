from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.mock import services as s

router = APIRouter(prefix="/mock", tags=["mock services (simulated)"])


class DisburseIn(BaseModel):
    cnic: str
    amount: int = Field(gt=0)
    idempotency_key: str = Field(min_length=8)


@router.get("/identity/verify")
def verify(cnic: str):
    return {"notice": s.MOCK_NOTICE, **s.identity_verify(cnic)}


@router.get("/identity/search")
def search(name: str = Query(min_length=2)):
    return {"notice": s.MOCK_NOTICE, "results": s.identity_search(name)}


@router.get("/identity/death-record")
def death(cnic: str):
    return {"notice": s.MOCK_NOTICE, **s.death_record(cnic)}


@router.get("/data/people")
def people(offset: int = 0, limit: int = Query(20, le=100)):
    return {"notice": s.MOCK_NOTICE, **s.list_people(offset, limit)}


@router.get("/data/eligibility")
def eligibility(cnic: str):
    return {"notice": s.MOCK_NOTICE, **s.eligibility_facts(cnic)}


@router.post("/payment/disburse")
def disburse(body: DisburseIn):
    return {"notice": s.MOCK_NOTICE, **s.payment_disburse(body.cnic, body.amount, body.idempotency_key)}


@router.get("/payment/{reference}")
def pay_status(reference: str):
    return {"notice": s.MOCK_NOTICE, **s.payment_status(reference)}