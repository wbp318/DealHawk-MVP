"""
CLI tool to create a dealership API key.

Usage:
    python -m backend.create_dealer_key --name "Test Dealer" --email "dealer@test.com"
    python -m backend.create_dealer_key --name "Premium Dealer" --email "premium@dealer.com" --tier premium --daily-limit 5000

Generates a raw API key (printed once), hashes it, and stores in the database.
"""

import argparse
import secrets

from backend.database.db import init_db, SessionLocal
from backend.database.models import Dealership
from backend.api.dealer_auth import _hash_api_key


def create_key(name: str, email: str, tier: str = "standard", daily_limit: int = 1000, monthly_limit: int = 25000):
    init_db()
    db = SessionLocal()

    try:
        existing = db.query(Dealership).filter(Dealership.email == email).first()
        if existing:
            print(f"Error: Dealership with email '{email}' already exists (id={existing.id})")
            return

        raw_key = f"dh_dealer_{secrets.token_hex(24)}"
        key_hash = _hash_api_key(raw_key)

        dealer = Dealership(
            name=name,
            email=email,
            api_key_hash=key_hash,
            tier=tier,
            daily_rate_limit=daily_limit,
            monthly_rate_limit=monthly_limit,
        )
        db.add(dealer)
        db.commit()
        db.refresh(dealer)

        print(f"Dealership created:")
        print(f"  ID:    {dealer.id}")
        print(f"  Name:  {dealer.name}")
        print(f"  Email: {dealer.email}")
        print(f"  Tier:  {dealer.tier}")
        print(f"  Daily limit:   {dealer.daily_rate_limit}")
        print(f"  Monthly limit: {dealer.monthly_rate_limit}")
        print()
        print(f"  API Key: {raw_key}")
        print()
        print("  Store this key securely — it cannot be recovered.")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Create a DealHawk dealer API key")
    parser.add_argument("--name", required=True, help="Dealership name")
    parser.add_argument("--email", required=True, help="Contact email (unique)")
    parser.add_argument("--tier", default="standard", choices=["standard", "premium"])
    parser.add_argument("--daily-limit", type=int, default=1000)
    parser.add_argument("--monthly-limit", type=int, default=25000)

    args = parser.parse_args()
    create_key(args.name, args.email, args.tier, args.daily_limit, args.monthly_limit)


if __name__ == "__main__":
    main()
