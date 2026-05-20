"""
Generates fintech transaction datasets for the spark-self-heal pipeline.

Produces:
  data/sample/clean_transactions.json           - happy path
  data/broken/01_schema_drift.json              - new unexpected field
  data/broken/02_invalid_currency.json          - non-ISO currency codes
  data/broken/03_negative_amount.json           - amount sign anomaly
  data/broken/04_malformed_timestamps.json      - inconsistent date formats
  data/broken/05_duplicate_ids.json             - duplicate transaction_id
  data/broken/06_null_required_fields.json      - nulls on non-nullable fields

Each file contains 200 records by default. Run from repo root:
    python scripts/generate_dataset.py
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

# ---------------------------------------------------------------------------
# Constants — valid domain values
# ---------------------------------------------------------------------------

CURRENCIES = ["USD", "COP", "MXN", "BRL", "ARS", "EUR"]
PAYMENT_METHODS = ["card", "wallet", "transfer", "crypto"]
STATUSES = ["approved", "declined", "pending", "refunded"]
COUNTRY_CODES = ["CO", "MX", "US", "BR", "AR", "ES"]

START_DATE = datetime(2026, 5, 1, tzinfo=timezone.utc)


def random_timestamp() -> str:
    """ISO 8601 timestamp in May 2026."""
    delta = timedelta(
        days=random.randint(0, 19),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    return (START_DATE + delta).isoformat().replace("+00:00", "Z")


def clean_transaction() -> dict:
    """A well-formed transaction record."""
    return {
        "transaction_id": str(uuid.uuid4()),
        "merchant_id": f"merch_{random.randint(1000, 9999)}",
        "customer_id": f"cust_{random.randint(10000, 99999)}",
        "amount": round(random.uniform(1.0, 5000.0), 2),
        "currency": random.choice(CURRENCIES),
        "payment_method": random.choice(PAYMENT_METHODS),
        "status": random.choice(STATUSES),
        "country_code": random.choice(COUNTRY_CODES),
        "created_at": random_timestamp(),
    }


# ---------------------------------------------------------------------------
# Failure injectors
# ---------------------------------------------------------------------------

def inject_schema_drift(records: list[dict]) -> list[dict]:
    """20% of records get a new unexpected field 'fraud_score'."""
    for r in random.sample(records, k=len(records) // 5):
        r["fraud_score"] = round(random.uniform(0, 1), 3)
    return records


def inject_invalid_currency(records: list[dict]) -> list[dict]:
    """10% of records use invalid currency codes."""
    bad_codes = ["XX", "DOLLAR", "us", "Bitcoin", ""]
    for r in random.sample(records, k=len(records) // 10):
        r["currency"] = random.choice(bad_codes)
    return records


def inject_negative_amount(records: list[dict]) -> list[dict]:
    """5% of records have negative amounts (refunds wrongly encoded as positive in source)."""
    for r in random.sample(records, k=len(records) // 20):
        r["amount"] = -abs(r["amount"])
    return records


def inject_malformed_timestamps(records: list[dict]) -> list[dict]:
    """15% of records have inconsistent timestamp formats."""
    formats = [
        "%Y-%m-%d %H:%M:%S",          # missing T and TZ
        "%d/%m/%Y %H:%M",             # european format
        "%Y%m%dT%H%M%S",              # compact, no separators
    ]
    for r in random.sample(records, k=int(len(records) * 0.15)):
        dt = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
        r["created_at"] = dt.strftime(random.choice(formats))
    return records


def inject_duplicate_ids(records: list[dict]) -> list[dict]:
    """Force 5 transaction_id duplicates by copying IDs."""
    sources = random.sample(records, k=5)
    targets = random.sample([r for r in records if r not in sources], k=5)
    for src, tgt in zip(sources, targets):
        tgt["transaction_id"] = src["transaction_id"]
    return records


def inject_null_required_fields(records: list[dict]) -> list[dict]:
    """10% of records have null on a required field."""
    required = ["merchant_id", "customer_id", "amount", "currency"]
    for r in random.sample(records, k=len(records) // 10):
        field = random.choice(required)
        r[field] = None
    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def write_jsonl(path: Path, records: list[dict]) -> None:
    """Write records as JSON Lines (one JSON object per line)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"[OK] wrote {len(records):>4} records to {path}")


def main(n: int = 200) -> None:
    sample_path = Path("data/sample/clean_transactions.json")
    broken_dir = Path("data/broken")

    # 1) Clean dataset
    clean = [clean_transaction() for _ in range(n)]
    write_jsonl(sample_path, clean)

    # 2) Broken variants (each starts from a fresh clean copy)
    variants = {
        "01_schema_drift.json": inject_schema_drift,
        "02_invalid_currency.json": inject_invalid_currency,
        "03_negative_amount.json": inject_negative_amount,
        "04_malformed_timestamps.json": inject_malformed_timestamps,
        "05_duplicate_ids.json": inject_duplicate_ids,
        "06_null_required_fields.json": inject_null_required_fields,
    }

    for filename, injector in variants.items():
        records = [clean_transaction() for _ in range(n)]
        records = injector(records)
        write_jsonl(broken_dir / filename, records)


if __name__ == "__main__":
    main()
