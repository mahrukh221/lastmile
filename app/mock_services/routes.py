from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from app.mock_services import store

router = APIRouter(prefix="/mock", tags=["Mock services (simulated, fake data)"])

CNIC_PATTERN = r"^\d{5}-\d{7}-\d$"


# ---------------- Identity service (pretends to be NADRA) ----------------
@router.get("/identity/search")
def identity_search(
    q: str = Query(..., min_length=2, description="Part of a name"),
    limit: int = Query(10, ge=1, le=50),
):
    """Find people whose name contains every word in q (case-insensitive)."""
    words = q.lower().split()
    matches = []
    for record in store.identity_by_cnic().values():
        name = " ".join(record["full_name"].lower().split())
        if all(word in name for word in words):
            matches.append(store.public(record))
        if len(matches) >= limit:
            break
    return matches


@router.get("/identity/{cnic}")
def identity_lookup(cnic: str = Path(..., pattern=CNIC_PATTERN)):
    record = store.identity_by_cnic().get(cnic)
    if record is None:
        raise HTTPException(404, "No identity record for this CNIC (mock)")
    return store.public(record)


# ---------------- Payment service (pretends to be Raast) ----------------
@router.get("/payment/account/{cnic}")
def payment_account(cnic: str = Path(..., pattern=CNIC_PATTERN)):
    account = store.accounts_by_cnic().get(cnic)
    if account is None:
        raise HTTPException(404, "No payment account for this CNIC (mock)")
    return account


class TransferRequest(BaseModel):
    cnic: str = Field(..., pattern=CNIC_PATTERN)
    amount: int = Field(..., gt=0, le=1_000_000)
    idempotency_key: str = Field(..., min_length=8)


_transfers: dict[str, dict] = {}  # lives in memory, resets when the server restarts


@router.post("/payment/simulate-transfer")
def simulate_transfer(req: TransferRequest):
    """Pretend to send money. No real money moves. Safe to retry with the same key."""
    if req.idempotency_key in _transfers:
        return {**_transfers[req.idempotency_key], "replayed": True}
    account = store.accounts_by_cnic().get(req.cnic)
    if account is None or account["status"] != "active":
        raise HTTPException(422, "No active payment account (mock)")
    result = {
        "transfer_id": f"MOCK-{len(_transfers) + 1:06d}",
        "cnic": req.cnic,
        "amount": req.amount,
        "status": "simulated_success",
        "note": "Simulated. No real money moved.",
    }
    _transfers[req.idempotency_key] = result
    return {**result, "replayed": False}


# ---------------- Data service (relief programme records) ----------------
@router.get("/data/programme/{cnic}")
def programme_record(cnic: str = Path(..., pattern=CNIC_PATTERN)):
    record = store.programme_by_cnic().get(cnic)
    if record is None:
        raise HTTPException(404, "No programme record for this CNIC (mock)")
    return record