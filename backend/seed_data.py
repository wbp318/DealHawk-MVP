"""
Seed the database with invoice pricing and incentive data.

Data sourced from TRUCK_BUYING_GUIDE.md (February 2026 market research).
Run: python -m backend.seed_data
"""

from datetime import date
from backend.database.db import init_db, SessionLocal
from backend.database.models import InvoicePriceCache, IncentiveProgram


def seed_invoice_prices(db):
    """Seed invoice price cache with known truck data."""
    invoice_data = [
        # Ford F-150
        {"year": 2026, "make": "Ford", "model": "F-150", "trim": "XL", "msrp": 38355, "invoice_price": 35670, "destination_charge": 1995},
        {"year": 2026, "make": "Ford", "model": "F-150", "trim": "XLT", "msrp": 44530, "invoice_price": 40520, "destination_charge": 1995},
        {"year": 2026, "make": "Ford", "model": "F-150", "trim": "Lariat", "msrp": 53870, "invoice_price": 48970, "destination_charge": 1995},
        {"year": 2026, "make": "Ford", "model": "F-150", "trim": "King Ranch", "msrp": 64540, "invoice_price": 57440, "destination_charge": 1995},
        {"year": 2026, "make": "Ford", "model": "F-150", "trim": "Platinum", "msrp": 68895, "invoice_price": 61320, "destination_charge": 1995},
        {"year": 2025, "make": "Ford", "model": "F-150", "trim": "XLT", "msrp": 43500, "invoice_price": 39585, "destination_charge": 1995},
        # Ford F-250
        {"year": 2026, "make": "Ford", "model": "F-250", "trim": "XL", "msrp": 44965, "invoice_price": 41820, "destination_charge": 1995},
        {"year": 2026, "make": "Ford", "model": "F-250", "trim": "XLT", "msrp": 50850, "invoice_price": 46270, "destination_charge": 1995},
        {"year": 2026, "make": "Ford", "model": "F-250", "trim": "Lariat", "msrp": 62090, "invoice_price": 56500, "destination_charge": 1995},
        # Ram 1500
        {"year": 2026, "make": "Ram", "model": "Ram 1500", "trim": "Tradesman", "msrp": 40630, "invoice_price": 37380, "destination_charge": 1995},
        {"year": 2026, "make": "Ram", "model": "Ram 1500", "trim": "Big Horn", "msrp": 47335, "invoice_price": 42600, "destination_charge": 1995},
        {"year": 2026, "make": "Ram", "model": "Ram 1500", "trim": "Laramie", "msrp": 55045, "invoice_price": 48540, "destination_charge": 1995},
        {"year": 2026, "make": "Ram", "model": "Ram 1500", "trim": "Warlock", "msrp": 49500, "invoice_price": 44550, "destination_charge": 1995},
        {"year": 2025, "make": "Ram", "model": "Ram 1500", "trim": "Big Horn", "msrp": 46500, "invoice_price": 41850, "destination_charge": 1995},
        # Ram 2500
        {"year": 2026, "make": "Ram", "model": "Ram 2500", "trim": "Tradesman", "msrp": 45450, "invoice_price": 41820, "destination_charge": 1995},
        {"year": 2026, "make": "Ram", "model": "Ram 2500", "trim": "Big Horn", "msrp": 53365, "invoice_price": 48030, "destination_charge": 1995},
        {"year": 2026, "make": "Ram", "model": "Ram 2500", "trim": "Laramie", "msrp": 62575, "invoice_price": 55030, "destination_charge": 1995},
        {"year": 2025, "make": "Ram", "model": "Ram 2500", "trim": "Laramie", "msrp": 61800, "invoice_price": 54380, "destination_charge": 1995},
        # Ram 3500
        {"year": 2026, "make": "Ram", "model": "Ram 3500", "trim": "Tradesman", "msrp": 46555, "invoice_price": 42830, "destination_charge": 1995},
        {"year": 2026, "make": "Ram", "model": "Ram 3500", "trim": "Laramie", "msrp": 64630, "invoice_price": 56840, "destination_charge": 1995},
        {"year": 2025, "make": "Ram", "model": "Ram 3500", "trim": "Tradesman", "msrp": 45700, "invoice_price": 42040, "destination_charge": 1995},
        # Chevrolet Silverado 1500
        {"year": 2026, "make": "Chevrolet", "model": "Silverado 1500", "trim": "WT", "msrp": 39600, "invoice_price": 36830, "destination_charge": 1995},
        {"year": 2026, "make": "Chevrolet", "model": "Silverado 1500", "trim": "LT", "msrp": 48400, "invoice_price": 44040, "destination_charge": 1995},
        {"year": 2026, "make": "Chevrolet", "model": "Silverado 1500", "trim": "LTZ", "msrp": 56200, "invoice_price": 50580, "destination_charge": 1995},
        # Chevrolet Silverado 2500HD
        {"year": 2026, "make": "Chevrolet", "model": "Silverado 2500HD", "trim": "WT", "msrp": 45500, "invoice_price": 41860, "destination_charge": 1995},
        {"year": 2026, "make": "Chevrolet", "model": "Silverado 2500HD", "trim": "LTZ", "msrp": 64300, "invoice_price": 57870, "destination_charge": 1995},
        # GMC Sierra 1500
        {"year": 2025, "make": "GMC", "model": "Sierra 1500", "trim": "Elevation", "msrp": 48200, "invoice_price": 43380, "destination_charge": 1995},
        {"year": 2026, "make": "GMC", "model": "Sierra 1500", "trim": "SLE", "msrp": 49500, "invoice_price": 44550, "destination_charge": 1995},
        {"year": 2026, "make": "GMC", "model": "Sierra 1500", "trim": "SLT", "msrp": 57800, "invoice_price": 50950, "destination_charge": 1995},
        {"year": 2026, "make": "GMC", "model": "Sierra 1500", "trim": "AT4", "msrp": 60500, "invoice_price": 53240, "destination_charge": 1995},
        # GMC Sierra 2500HD
        {"year": 2026, "make": "GMC", "model": "Sierra 2500HD", "trim": "Pro", "msrp": 46800, "invoice_price": 43060, "destination_charge": 1995},
        {"year": 2026, "make": "GMC", "model": "Sierra 2500HD", "trim": "SLT", "msrp": 65200, "invoice_price": 58680, "destination_charge": 1995},
    ]

    for data in invoice_data:
        from backend.config.holdback_rates import get_holdback
        holdback = get_holdback(data["make"], data["msrp"], data["invoice_price"])
        existing = db.query(InvoicePriceCache).filter(
            InvoicePriceCache.year == data["year"],
            InvoicePriceCache.make == data["make"],
            InvoicePriceCache.model == data["model"],
            InvoicePriceCache.trim == data["trim"],
        ).first()
        if existing:
            continue
        db.add(InvoicePriceCache(
            **data,
            holdback_amount=holdback,
            source="seed_data_feb_2026",
        ))

    db.commit()
    print(f"Seeded {len(invoice_data)} invoice price records")


def seed_incentives(db):
    """Seed incentive programs from February 2026 research."""
    incentives = [
        # Ram incentives
        {"make": "Ram", "model": "Ram 1500", "year": 2026, "incentive_type": "cash_back", "name": "Ram 1500 Big Horn CC 4x4 Cash Allowance", "amount": 7500, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 3, 2), "stackable": False, "notes": "Cannot stack with 0% APR"},
        {"make": "Ram", "model": "Ram 1500", "year": 2026, "incentive_type": "cash_back", "name": "Ram 1500 All Combined Max", "amount": 18250, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 3, 2), "stackable": False, "notes": "Maximum combined incentive"},
        {"make": "Ram", "model": "Ram 1500", "year": 2026, "incentive_type": "apr", "name": "Ram 1500 Low APR", "apr_rate": 0, "apr_months": 60, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 3, 2), "stackable": False, "notes": "0% for 60 months, cannot stack with cash back"},
        {"make": "Ram", "model": "Ram 1500", "year": 2026, "incentive_type": "cash_back", "name": "Ram 1500 Warlock 10% Off", "amount": 5000, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 3, 2), "notes": "10% off MSRP + $2,000 trade assist"},
        {"make": "Ram", "model": "Ram 1500", "year": 2025, "incentive_type": "cash_back", "name": "2025 Ram 1500 SE Region Cash", "amount": 5250, "region": "SE", "start_date": date(2026, 2, 1), "end_date": date(2026, 3, 31)},
        {"make": "Ram", "model": "Ram 1500", "year": 2025, "incentive_type": "apr", "name": "2025 Ram 1500 Zero APR", "apr_rate": 0, "apr_months": 72, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 3, 31), "stackable": False},
        {"make": "Ram", "model": "Ram 2500", "year": 2026, "incentive_type": "cash_back", "name": "2026 Ram 2500 Cash Back", "amount": 7000, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 3, 31)},
        {"make": "Ram", "model": "Ram 2500", "year": 2025, "incentive_type": "cash_back", "name": "2025 Ram 2500 Cash Back", "amount": 10000, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 3, 31)},
        {"make": "Ram", "model": "Ram 2500", "year": 2026, "incentive_type": "apr", "name": "2026 Ram 2500 Financing", "apr_rate": 4.9, "apr_months": 84, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 3, 31)},
        {"make": "Ram", "model": "Ram 3500", "year": 2026, "incentive_type": "cash_back", "name": "2026 Ram 3500 Cash Back", "amount": 7000, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 3, 31)},
        {"make": "Ram", "model": "Ram 3500", "year": 2025, "incentive_type": "cash_back", "name": "2025 Ram 3500 Cash Back", "amount": 6000, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 3, 31)},
        # GMC incentives
        {"make": "GMC", "model": "Sierra 1500", "year": 2025, "incentive_type": "cash_back", "name": "2025 Sierra 1500 Cash Rebate", "amount": 9350, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 2, 28)},
        {"make": "GMC", "model": "Sierra 1500", "year": 2025, "incentive_type": "apr", "name": "2025 Sierra 1500 Zero APR", "apr_rate": 0, "apr_months": 36, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 2, 28)},
        {"make": "GMC", "model": "Sierra 1500", "year": 2026, "incentive_type": "cash_back", "name": "2026 Sierra 1500 TurboMax w/Trade", "amount": 8350, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 2, 28), "notes": "Requires trade-in, TurboMax engine"},
        # Chevrolet incentives
        {"make": "Chevrolet", "model": "Silverado 1500", "year": 2026, "incentive_type": "apr", "name": "Silverado 1500 Low APR", "apr_rate": 1.9, "apr_months": 36, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 2, 28)},
        {"make": "Chevrolet", "model": "Silverado 2500HD", "year": 2026, "incentive_type": "cash_back", "name": "Silverado 2500HD Cash", "amount": 1500, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 2, 28)},
        # Ford incentives
        {"make": "Ford", "model": "F-150", "year": 2025, "incentive_type": "cash_back", "name": "2025 F-150 Bonus Cash", "amount": 3250, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 3, 31)},
        {"make": "Ford", "model": "F-150", "year": 2025, "incentive_type": "apr", "name": "2025 F-150 Financing", "apr_rate": 2.9, "apr_months": 60, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 3, 31)},
        {"make": "Ford", "model": "F-150", "year": 2024, "incentive_type": "dealer_cash", "name": "2024 F-150 Aged Inventory Dealer Cash", "amount": 2000, "region": "national", "start_date": date(2026, 1, 1), "end_date": date(2026, 3, 31), "notes": "Hidden 90+ day aged inventory program"},
        {"make": "Ford", "model": "Super Duty", "year": 2024, "incentive_type": "cash_back", "name": "2024 Super Duty XL Retail Cash", "amount": 6500, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 3, 31)},
        {"make": "Ford", "model": "Super Duty", "year": 2025, "incentive_type": "apr", "name": "2025 Super Duty Zero APR", "apr_rate": 0, "apr_months": 60, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 3, 31)},
        {"make": "Ford", "model": None, "year": None, "incentive_type": "cash_back", "name": "Ford Farm Bureau $500", "amount": 500, "region": "national", "start_date": date(2026, 1, 1), "end_date": date(2026, 12, 31), "stackable": True, "notes": "Requires 30-day Farm Bureau membership. Stacks with all other offers."},
        {"make": "Ford", "model": "F-150 Lightning", "year": 2025, "incentive_type": "cash_back", "name": "2025 F-150 Lightning Cash", "amount": 9000, "region": "national", "start_date": date(2026, 2, 1), "end_date": date(2026, 3, 31)},
    ]

    count = 0
    for data in incentives:
        existing = db.query(IncentiveProgram).filter(
            IncentiveProgram.name == data["name"]
        ).first()
        if existing:
            continue
        db.add(IncentiveProgram(**data))
        count += 1

    db.commit()
    print(f"Seeded {count} incentive programs")


def main():
    init_db()
    db = SessionLocal()
    try:
        seed_invoice_prices(db)
        seed_incentives(db)
        print("Seed data complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
