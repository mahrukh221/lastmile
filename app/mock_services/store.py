import json
from functools import lru_cache
from pathlib import Path

# app/mock_services/store.py -> parents[2] is the project root
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _load(filename: str):
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run:  python -m scripts.seed_mock_data"
        )
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache
def identity_by_cnic() -> dict:
    return {p["cnic"]: p for p in _load("mock_identity.json")}


@lru_cache
def programme_by_cnic() -> dict:
    return _load("mock_programme.json")


@lru_cache
def accounts_by_cnic() -> dict:
    return _load("mock_accounts.json")


def public(record: dict) -> dict:
    """Hide internal fields (those starting with an underscore)."""
    return {k: v for k, v in record.items() if not k.startswith("_")}