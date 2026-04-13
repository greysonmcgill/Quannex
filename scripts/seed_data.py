"""Seed the operational database with realistic test data."""

from __future__ import annotations

import argparse
import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from quan.database import SessionLocal, init_database
from quan.intelligence import CollectionIntelligence
from quan.models.database import Account, Campaign, ComplianceEvent, ContactAttempt, Payment, Portfolio

FIRST_NAMES = [
    "Jordan", "Taylor", "Morgan", "Alex", "Cameron", "Riley", "Avery", "Parker",
    "Skyler", "Quinn", "Casey", "Hayden", "Jules", "Reese", "Micah", "Kendall",
]
LAST_NAMES = [
    "Walker", "Morgan", "Diaz", "Reed", "Bennett", "Perry", "Collins", "Sullivan",
    "Turner", "Foster", "Hayes", "Barnes", "Price", "Sanders", "Coleman", "Bryant",
]
STATES = ["CA", "TX", "FL", "NY", "IL", "GA", "NC", "OH", "PA", "MI", "AZ", "WA", "CO", "VA"]
DEBT_CONFIG = {
    "bnpl": ["Klarna", "Affirm", "Afterpay", "Sezzle"],
    "medical": ["Mercy Health", "CommonSpirit", "Kaiser Permanente", "Tenet"],
    "telecom": ["Verizon", "AT&T", "T-Mobile", "Comcast"],
    "subscription": ["Adobe", "Spotify", "Netflix", "Hulu"],
    "utility": ["Duke Energy", "PG&E", "ComEd", "Xcel Energy"],
    "credit_card": ["Capital One", "Discover", "Chase", "Citi"],
    "bank": ["Wells Fargo", "Bank of America", "PNC", "US Bank"],
    "personal_loan": ["SoFi", "Upstart", "LendingClub", "Upgrade"],
    "auto": ["Toyota Financial", "GM Financial", "Santander", "Carvana"],
    "rent": ["Invitation Homes", "Greystar", "AvalonBay", "Equity Residential"],
}
STATUS_WEIGHTS = [
    ("scored", 0.35),
    ("contacted", 0.25),
    ("negotiating", 0.15),
    ("payment_pending", 0.15),
    ("paid_in_full", 0.10),
]
CHANNELS = ["sms", "email", "voice", "digital", "mail"]
CHANNEL_COSTS = {
    "sms": Decimal("0.02"),
    "email": Decimal("0.01"),
    "voice": Decimal("0.15"),
    "digital": Decimal("0.03"),
    "mail": Decimal("0.55"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the QUAN operational database.")
    parser.add_argument("--count", type=int, default=1000, help="Number of accounts to generate.")
    parser.add_argument("--reset", action="store_true", help="Delete existing operational data before seeding.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    random.seed(args.seed)
    init_database()

    engine = CollectionIntelligence()

    with SessionLocal() as db:
        if args.reset:
            db.query(ComplianceEvent).delete()
            db.query(ContactAttempt).delete()
            db.query(Payment).delete()
            db.query(Campaign).delete()
            db.query(Account).delete()
            db.query(Portfolio).delete()
            db.commit()

        portfolio_ids = []
        debt_types = list(DEBT_CONFIG.keys())
        chunk_size = max(args.count // len(debt_types), 1)
        for index, debt_type in enumerate(debt_types, start=1):
            portfolio = Portfolio(
                name=f"{debt_type.replace('_', ' ').title()} Seed Portfolio {index}",
                source_file=f"{debt_type}_seed.csv",
                upload_status="completed",
                total_accounts=0,
                total_balance=0,
                valid_rows=0,
                invalid_rows=0,
            )
            db.add(portfolio)
            db.flush()
            portfolio_ids.append((debt_type, portfolio.id))
            db.add(
                Campaign(
                    name=f"{debt_type.title()} Recovery Campaign",
                    portfolio_id=portfolio.id,
                    status="running",
                    started_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 45)),
                )
            )

        created_accounts = 0
        for debt_type, portfolio_id in portfolio_ids:
            target = min(chunk_size, args.count - created_accounts)
            for _ in range(target):
                created_accounts += 1
                account_id = f"ACC-{created_accounts:06d}"
                debtor_name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
                original_creditor = random.choice(DEBT_CONFIG[debt_type])
                state = random.choice(STATES)
                original_balance = Decimal(str(round(random.uniform(85, 1800), 2)))
                days_past_due = random.randint(15, 365)
                status = _weighted_choice(STATUS_WEIGHTS)

                payment_willingness = _payment_willingness(days_past_due, debt_type)
                has_phone = random.random() > 0.12
                has_email = random.random() > 0.18
                strategy = engine.generate_strategy(
                    {
                        "account_id": account_id,
                        "balance": float(original_balance),
                        "original_balance": float(original_balance),
                        "original_creditor": original_creditor,
                        "debt_type": debt_type,
                        "days_past_due": days_past_due,
                        "has_mobile": has_phone,
                        "email_valid": has_email,
                        "payment_willingness": payment_willingness,
                        "age": random.randint(24, 67),
                    }
                )

                total_paid = Decimal("0.00")
                if status == "paid_in_full":
                    total_paid = original_balance
                elif status == "payment_pending":
                    total_paid = (original_balance * Decimal(str(random.uniform(0.15, 0.65)))).quantize(Decimal("0.01"))
                elif status == "negotiating":
                    total_paid = (original_balance * Decimal(str(random.uniform(0.05, 0.25)))).quantize(Decimal("0.01"))

                balance = max(Decimal("0.00"), original_balance - total_paid)
                created_at = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 180))
                updated_at = created_at + timedelta(days=random.randint(0, 45))

                account = Account(
                    external_account_id=account_id,
                    portfolio_id=portfolio_id,
                    debtor_name=debtor_name,
                    current_balance=balance,
                    original_balance=original_balance,
                    original_creditor=original_creditor,
                    debt_type=debt_type,
                    days_past_due=days_past_due,
                    state=state,
                    phone=_fake_phone() if has_phone else None,
                    email=_fake_email(debtor_name) if has_email else None,
                    status=status,
                    recovery_probability=strategy.recovery_probability,
                    optimal_channels=strategy.optimal_channels,
                    settlement_threshold=strategy.settlement_threshold,
                    total_payments=total_paid,
                    contact_attempts_count=0,
                    payment_willingness=payment_willingness,
                    has_mobile=has_phone,
                    age=random.randint(24, 67),
                    created_at=created_at,
                    updated_at=updated_at,
                )
                db.add(account)
                db.flush()

                contact_count = random.randint(0, 4)
                for attempt_index in range(contact_count):
                    channel = random.choice(CHANNELS)
                    contact_at = created_at + timedelta(days=attempt_index * random.randint(2, 8))
                    consent_ok = random.random() > 0.08
                    outcome = random.choice(
                        ["no_answer", "connected", "left_message", "delivered", "bounced"]
                    )
                    db.add(
                        ContactAttempt(
                            account_id=account.id,
                            channel=channel,
                            outcome=outcome,
                            consent_verified=consent_ok,
                            within_contact_hours=random.random() > 0.05,
                            cost=CHANNEL_COSTS[channel],
                            created_at=contact_at,
                        )
                    )
                    account.contact_attempts_count += 1
                    account.last_contact_date = contact_at

                    if not consent_ok:
                        db.add(
                            ComplianceEvent(
                                account_id=account.id,
                                event_type=random.choice(["contact_attempt", "tcpa_violation", "fdcpa_violation"]),
                                severity=random.choice(["warning", "critical"]),
                                description=f"Seeded compliance exception on {channel} attempt.",
                                resolution="Pending QA review.",
                                state=state,
                                created_at=contact_at,
                            )
                        )

                if total_paid > 0:
                    payment_count = 1 if status in {"payment_pending", "paid_in_full"} else random.randint(0, 1)
                    for payment_index in range(payment_count):
                        amount = (
                            total_paid if payment_count == 1 else (total_paid / payment_count).quantize(Decimal("0.01"))
                        )
                        pay_at = updated_at - timedelta(days=max(payment_count - payment_index, 0))
                        db.add(
                            Payment(
                                account_id=account.id,
                                amount=amount,
                                payment_method=random.choice(["card", "ach"]),
                                status="completed",
                                processed_at=pay_at,
                                created_at=pay_at,
                            )
                        )
                        account.last_payment_date = pay_at

                if random.random() < 0.03:
                    db.add(
                        ComplianceEvent(
                            account_id=account.id,
                            event_type="consent_obtained",
                            severity="info",
                            description="Consent confirmation logged during seed generation.",
                            resolution="Automatically resolved.",
                            resolved_at=updated_at,
                            state=state,
                            created_at=updated_at,
                        )
                    )

            portfolio_obj = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
            if portfolio_obj:
                type_count = db.query(Account).filter(Account.portfolio_id == portfolio_id).count()
                total_bal = db.query(Account).filter(Account.portfolio_id == portfolio_id).with_entities(
                    Account.current_balance
                ).all()
                portfolio_obj.total_accounts = type_count
                portfolio_obj.total_balance = sum(float(r[0] or 0) for r in total_bal)
                portfolio_obj.valid_rows = type_count

        db.commit()
        print(f"Seeded {created_accounts} accounts across {len(portfolio_ids)} portfolios.")


def _weighted_choice(weighted_values: list[tuple[str, float]]) -> str:
    roll = random.random()
    cursor = 0.0
    for value, weight in weighted_values:
        cursor += weight
        if roll <= cursor:
            return value
    return weighted_values[-1][0]


def _payment_willingness(days_past_due: int, debt_type: str) -> float:
    base = {
        "bnpl": 0.58,
        "medical": 0.33,
        "telecom": 0.48,
        "subscription": 0.62,
        "utility": 0.45,
        "credit_card": 0.37,
        "bank": 0.34,
        "personal_loan": 0.29,
        "auto": 0.31,
        "rent": 0.41,
    }.get(debt_type, 0.4)
    penalty = min(days_past_due / 365, 0.35)
    return max(0.05, min(0.95, base - penalty))


def _fake_phone() -> str:
    return f"+1{random.randint(2000000000, 9999999999)}"


def _fake_email(name: str) -> str:
    local = name.lower().replace(" ", ".")
    return f"{local}{random.randint(1, 999)}@example.com"


if __name__ == "__main__":
    main()
