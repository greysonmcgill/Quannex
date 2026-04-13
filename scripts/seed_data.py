#!/usr/bin/env python3
"""
Seed Data Script for QUAN Recovery

Generates 1,000 realistic test accounts across all debt types
using the MicroLoanUniverseGenerator.

Usage:
    python scripts/seed_data.py
    python scripts/seed_data.py --count 5000  # Custom count
    python scripts/seed_data.py --reset       # Drop and recreate all tables
"""

import argparse
import random
import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quan.database import init_db_sync, get_sync_session, get_sync_engine
from quan.models.database import (
    Base,
    Account,
    Portfolio,
    Campaign,
    ContactAttempt,
    Payment,
    ComplianceEvent,
    AccountStatus,
    ContactChannel,
    ContactOutcome,
    PaymentStatus,
    PaymentMethod,
    ComplianceEventType,
)
from quan.models.micro_loan_universe import (
    MicroLoanUniverseGenerator,
    DebtType,
    MICRO_LOAN_UNIVERSE,
)
from quan.intelligence import CollectionIntelligence


# US States for realistic addresses
US_STATES = [
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
]

# Sample creditors by debt type
CREDITORS = {
    'payday': ['QuickCash Loans', 'FastMoney Inc', 'PaydayNow', 'CashAdvance Pro'],
    'personal_micro': ['LendUp', 'SoFi Personal', 'Upstart', 'Prosper Loans'],
    'buy_now_pay_later': ['Affirm', 'Klarna', 'Afterpay', 'Sezzle', 'Zip'],
    'medical': ['St. Mary Hospital', 'Regional Medical Center', 'City Health Clinic', 'Urgent Care Plus'],
    'utility': ['Power & Light Co', 'City Water Works', 'Natural Gas Corp', 'Electric Cooperative'],
    'telecom': ['Verizon', 'AT&T', 'T-Mobile', 'Spectrum', 'Comcast'],
    'auto_micro': ['DriveTime', 'CarMax Auto Finance', 'Santander Consumer', 'Capital One Auto'],
    'student_micro': ['Sallie Mae', 'Navient', 'SoFi Student', 'CommonBond'],
    'retail_credit': ['Target Credit', 'Amazon Store Card', 'Best Buy Card', 'Walmart Credit'],
    'subscription': ['Netflix', 'Spotify', 'Planet Fitness', 'Adobe Creative', 'Microsoft 365'],
}

# First names
FIRST_NAMES = [
    'James', 'Mary', 'Robert', 'Patricia', 'John', 'Jennifer', 'Michael', 'Linda',
    'David', 'Elizabeth', 'William', 'Barbara', 'Richard', 'Susan', 'Joseph', 'Jessica',
    'Thomas', 'Sarah', 'Christopher', 'Karen', 'Charles', 'Lisa', 'Daniel', 'Nancy',
    'Matthew', 'Betty', 'Anthony', 'Margaret', 'Mark', 'Sandra', 'Donald', 'Ashley',
    'Steven', 'Kimberly', 'Andrew', 'Emily', 'Paul', 'Donna', 'Joshua', 'Michelle',
    'Kevin', 'Carol', 'Brian', 'Amanda', 'George', 'Dorothy', 'Timothy', 'Melissa',
]

# Last names
LAST_NAMES = [
    'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis',
    'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson',
    'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Perez', 'Thompson',
    'White', 'Harris', 'Sanchez', 'Clark', 'Ramirez', 'Lewis', 'Robinson', 'Walker',
    'Young', 'Allen', 'King', 'Wright', 'Scott', 'Torres', 'Nguyen', 'Hill',
    'Flores', 'Green', 'Adams', 'Nelson', 'Baker', 'Hall', 'Rivera', 'Campbell',
]


def generate_phone():
    """Generate a realistic US phone number"""
    area_code = random.randint(200, 999)
    exchange = random.randint(200, 999)
    subscriber = random.randint(1000, 9999)
    return f"{area_code}-{exchange}-{subscriber}"


def generate_email(first_name: str, last_name: str) -> str:
    """Generate a realistic email address"""
    domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'aol.com', 'icloud.com']
    separators = ['.', '_', '']
    sep = random.choice(separators)
    suffix = random.randint(1, 99) if random.random() < 0.3 else ''
    return f"{first_name.lower()}{sep}{last_name.lower()}{suffix}@{random.choice(domains)}"


def generate_address():
    """Generate a realistic US address"""
    street_nums = [str(random.randint(100, 9999))]
    street_types = ['St', 'Ave', 'Blvd', 'Dr', 'Ln', 'Ct', 'Way', 'Rd']
    street_names = ['Main', 'Oak', 'Maple', 'Cedar', 'Pine', 'Elm', 'Washington', 'Park',
                   'Lake', 'Hill', 'Valley', 'River', 'Forest', 'Spring', 'Church']

    address_line1 = f"{random.choice(street_nums)} {random.choice(street_names)} {random.choice(street_types)}"

    # Sometimes add apt/suite
    if random.random() < 0.3:
        apt_type = random.choice(['Apt', 'Suite', 'Unit', '#'])
        apt_num = random.randint(1, 500)
        address_line2 = f"{apt_type} {apt_num}"
    else:
        address_line2 = None

    cities = ['Springfield', 'Franklin', 'Greenville', 'Bristol', 'Clinton',
              'Fairview', 'Salem', 'Madison', 'Georgetown', 'Arlington']

    return {
        'address_line1': address_line1,
        'address_line2': address_line2,
        'city': random.choice(cities),
        'state': random.choice(US_STATES),
        'zip_code': f"{random.randint(10000, 99999)}"
    }


def create_account_from_generated(generated: dict, portfolio_id: str, intelligence: CollectionIntelligence) -> Account:
    """Convert generated account data to Account model instance"""

    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    debt_type = generated.get('debt_type', 'other')

    # Get creditor based on debt type
    creditor_list = CREDITORS.get(debt_type, ['General Creditor'])
    original_creditor = random.choice(creditor_list)

    # Generate contact info
    phone = generate_phone() if generated.get('phone_valid', True) else None
    email = generate_email(first_name, last_name) if generated.get('email_valid', True) else None
    address = generate_address()

    # Generate dates
    days_past_due = generated.get('account_age_days', random.randint(30, 365))
    charge_off_date = datetime.now() - timedelta(days=days_past_due)
    last_payment_date = charge_off_date - timedelta(days=random.randint(30, 180)) if random.random() < 0.6 else None

    # Determine status based on days past due
    if days_past_due < 30:
        status = AccountStatus.NEW.value
    elif days_past_due < 60:
        status = AccountStatus.SCORED.value
    elif days_past_due < 90:
        status = AccountStatus.CONTACTED.value
    elif days_past_due < 120:
        status = AccountStatus.NEGOTIATING.value
    else:
        status = random.choice([
            AccountStatus.NEGOTIATING.value,
            AccountStatus.PAYMENT_PENDING.value,
            AccountStatus.SETTLED.value if random.random() < 0.2 else AccountStatus.NEGOTIATING.value
        ])

    # Get intelligence scores
    account_dict = {
        'account_id': generated['account_id'],
        'balance': float(generated['balance']),
        'original_balance': float(generated.get('original_balance', generated['balance'])),
        'payment_willingness': generated.get('collectability_score', 0.5),
        'has_mobile': generated.get('mobile_device', False),
        'email_valid': generated.get('email_valid', True),
        'employed': generated.get('employed', True),
        'age': generated.get('age', 35),
        'income_bracket': generated.get('income_bracket', 'medium'),
    }

    strategy = intelligence.generate_strategy(account_dict)

    return Account(
        id=generated['account_id'],
        external_account_id=f"EXT-{generated['account_id'][-7:]}",
        portfolio_id=portfolio_id,

        # Debtor info
        debtor_name=f"{first_name} {last_name}",
        debtor_first_name=first_name,
        debtor_last_name=last_name,

        # Contact info
        phone=phone,
        phone_valid=phone is not None,
        phone_type='mobile' if generated.get('mobile_device', False) else 'landline',
        email=email,
        email_valid=email is not None,
        address_line1=address['address_line1'],
        address_line2=address['address_line2'],
        city=address['city'],
        state=address['state'],
        zip_code=address['zip_code'],

        # Debt details
        original_creditor=original_creditor,
        current_creditor='QUAN Recovery',
        debt_type=debt_type,
        original_balance=float(generated.get('original_balance', generated['balance'])),
        current_balance=float(generated['balance']),

        # Aging
        charge_off_date=charge_off_date,
        last_payment_date=last_payment_date,
        days_past_due=days_past_due,

        # Status
        status=status,

        # Intelligence scores
        recovery_probability=strategy.recovery_probability,
        settlement_threshold=strategy.settlement_threshold,
        optimal_channels=strategy.optimal_channels,

        # Behavioral
        payment_willingness=generated.get('collectability_score', 0.5),
        has_mobile=generated.get('mobile_device', False),
        employed=generated.get('employed', True),
        income_bracket=generated.get('income_bracket', 'medium'),
        age=generated.get('age', 35),

        # Compliance flags
        bankruptcy_flag=generated.get('is_bankruptcy', False),
        disputed=generated.get('has_dispute', False),
        statute_of_limitations_expired=generated.get('sol_expired', False),
    )


def seed_database(account_count: int = 1000, reset: bool = False):
    """Seed the database with realistic test data"""

    print(f"\n{'='*60}")
    print("  QUAN Recovery - Database Seeding")
    print(f"{'='*60}\n")

    engine = get_sync_engine()

    if reset:
        print("Resetting database...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        print("  Database reset complete.\n")
    else:
        # Just create tables if they don't exist
        Base.metadata.create_all(bind=engine)

    session = get_sync_session()

    try:
        # Check if data already exists
        existing_accounts = session.query(Account).count()
        if existing_accounts > 0 and not reset:
            print(f"  Database already has {existing_accounts} accounts.")
            print("  Use --reset to clear and reseed.")
            return

        # Create portfolio
        print(f"Creating seed portfolio with {account_count} accounts...")
        portfolio = Portfolio(
            name=f"Seed Portfolio - {datetime.now().strftime('%Y-%m-%d')}",
            client_id="seed-client-001",
            upload_status="completed",
            source_file="seed_data.py",
        )
        session.add(portfolio)
        session.flush()  # Get portfolio ID

        # Generate accounts using MicroLoanUniverseGenerator
        print("Generating realistic account data...")
        generator = MicroLoanUniverseGenerator()
        generated_accounts = generator.generate_full_portfolio(account_count)

        # Initialize intelligence engine for scoring
        intelligence = CollectionIntelligence()

        # Convert to Account models
        print("Creating account records with AI scoring...")
        accounts = []
        for i, gen_account in enumerate(generated_accounts):
            account = create_account_from_generated(gen_account, portfolio.id, intelligence)
            accounts.append(account)

            if (i + 1) % 100 == 0:
                print(f"  Processed {i + 1}/{account_count} accounts...")

        session.add_all(accounts)
        session.flush()

        # Update portfolio totals
        portfolio.total_accounts = len(accounts)
        portfolio.total_balance = sum(float(a.current_balance) for a in accounts)
        portfolio.valid_rows = len(accounts)

        # Add some contact attempts for realism
        print("Adding sample contact history...")
        contact_count = 0
        for account in random.sample(accounts, min(len(accounts) // 3, 300)):
            # Add 1-5 contact attempts
            for _ in range(random.randint(1, 5)):
                channel = random.choice(list(ContactChannel))
                outcome = random.choice(list(ContactOutcome))

                contact = ContactAttempt(
                    account_id=account.id,
                    channel=channel.value,
                    direction='outbound',
                    contact_target=account.phone if channel in [ContactChannel.SMS, ContactChannel.VOICE] else account.email,
                    outcome=outcome.value,
                    duration_seconds=random.randint(30, 300) if channel == ContactChannel.VOICE else None,
                    response_received=outcome in [ContactOutcome.REPLIED, ContactOutcome.CONNECTED],
                    cost=0.02 if channel == ContactChannel.SMS else 0.01 if channel == ContactChannel.EMAIL else 0.15,
                    created_at=datetime.now() - timedelta(days=random.randint(1, 60)),
                )
                session.add(contact)
                contact_count += 1

                # Update account contact stats
                account.contact_attempts += 1
                if outcome in [ContactOutcome.REPLIED, ContactOutcome.CONNECTED]:
                    account.successful_contacts += 1
                    account.last_contact_date = contact.created_at
                    account.last_contact_channel = channel.value

        # Add some payments
        print("Adding sample payment history...")
        payment_count = 0
        settled_accounts = [a for a in accounts if a.status in [AccountStatus.SETTLED.value, AccountStatus.PAID_IN_FULL.value]]
        negotiating_accounts = [a for a in accounts if a.status == AccountStatus.PAYMENT_PENDING.value]

        for account in settled_accounts + random.sample(negotiating_accounts, min(len(negotiating_accounts) // 2, 50)):
            # Full payment or settlement
            is_settlement = random.random() < 0.6
            amount = float(account.current_balance) * (random.uniform(0.4, 0.7) if is_settlement else 1.0)

            payment = Payment(
                account_id=account.id,
                amount=amount,
                payment_method=random.choice(list(PaymentMethod)).value,
                status=PaymentStatus.COMPLETED.value,
                is_settlement=is_settlement,
                processed_at=datetime.now() - timedelta(days=random.randint(1, 30)),
                net_amount=amount * 0.97,  # 3% processing fee
                processing_fee=amount * 0.03,
            )
            session.add(payment)
            payment_count += 1

            # Update account
            account.total_payments += Decimal(str(amount))
            if is_settlement:
                account.settlement_amount = amount
                account.settlement_accepted_at = payment.processed_at

        # Add some compliance events
        print("Adding sample compliance events...")
        compliance_count = 0
        for _ in range(20):
            account = random.choice(accounts)
            event_type = random.choice(list(ComplianceEventType))

            event = ComplianceEvent(
                account_id=account.id,
                event_type=event_type.value,
                severity='info' if event_type in [ComplianceEventType.CONTACT_ATTEMPT, ComplianceEventType.CONSENT_OBTAINED] else 'warning',
                description=f"Compliance event: {event_type.value.replace('_', ' ').title()}",
                regulation=random.choice(['fdcpa', 'tcpa', 'reg_f']),
                state=account.state,
                created_by='system',
                created_at=datetime.now() - timedelta(days=random.randint(1, 90)),
            )
            session.add(event)
            compliance_count += 1

        # Commit everything
        session.commit()

        # Print summary
        print(f"\n{'='*60}")
        print("  Seeding Complete!")
        print(f"{'='*60}")
        print(f"\n  Portfolio: {portfolio.name}")
        print(f"  Portfolio ID: {portfolio.id}")
        print(f"\n  Records Created:")
        print(f"    - Accounts: {len(accounts)}")
        print(f"    - Contact Attempts: {contact_count}")
        print(f"    - Payments: {payment_count}")
        print(f"    - Compliance Events: {compliance_count}")

        # Show debt type breakdown
        print(f"\n  Debt Type Breakdown:")
        debt_type_counts = {}
        for account in accounts:
            dt = account.debt_type
            debt_type_counts[dt] = debt_type_counts.get(dt, 0) + 1

        for dt, count in sorted(debt_type_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"    - {dt}: {count} accounts")

        # Show status breakdown
        print(f"\n  Status Breakdown:")
        status_counts = {}
        for account in accounts:
            status_counts[account.status] = status_counts.get(account.status, 0) + 1

        for status, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"    - {status}: {count} accounts")

        total_balance = sum(float(a.current_balance) for a in accounts)
        total_original = sum(float(a.original_balance) for a in accounts)
        print(f"\n  Financial Summary:")
        print(f"    - Total Current Balance: ${total_balance:,.2f}")
        print(f"    - Total Original Balance: ${total_original:,.2f}")
        print(f"    - Average Balance: ${total_balance/len(accounts):,.2f}")

        print(f"\n{'='*60}\n")

    except Exception as e:
        session.rollback()
        print(f"\nError seeding database: {e}")
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description='Seed QUAN Recovery database with test data')
    parser.add_argument('--count', type=int, default=1000, help='Number of accounts to generate (default: 1000)')
    parser.add_argument('--reset', action='store_true', help='Drop and recreate all tables before seeding')

    args = parser.parse_args()

    seed_database(account_count=args.count, reset=args.reset)


if __name__ == '__main__':
    main()
