import httpx

from app.config import settings


class MockServiceError(Exception):
    """The mock service could not be reached or returned an error."""


def _request(method: str, path: str, **kwargs):
    try:
        response = httpx.request(
            method, f"{settings.mock_base_url}{path}", timeout=5.0, **kwargs
        )
    except httpx.HTTPError as exc:
        raise MockServiceError(f"Mock service unreachable: {exc}") from exc
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        raise MockServiceError(f"Mock service error {response.status_code}: {response.text}")
    return response.json()


def get_identity(cnic: str):
    return _request("GET", f"/identity/{cnic}")


def search_identity(name: str, limit: int = 10):
    return _request("GET", "/identity/search", params={"q": name, "limit": limit}) or []


def get_programme(cnic: str):
    return _request("GET", f"/data/programme/{cnic}")


def get_account(cnic: str):
    return _request("GET", f"/payment/account/{cnic}")


def simulate_transfer(cnic: str, amount: int, idempotency_key: str):
    return _request(
        "POST",
        "/payment/simulate-transfer",
        json={"cnic": cnic, "amount": amount, "idempotency_key": idempotency_key},
    )