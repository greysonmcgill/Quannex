"""
Metro 2 Credit Bureau Bridge - Modernizing Legacy Reporting

Addresses the thesis criticism: "Metro 2 is a relic of the mainframe era"

This module bridges the gap between QUAN's real-time Shadow Bureau data
and the legacy Metro 2 format required by traditional credit bureaus.

Key Innovations:
1. Shadow Bureau -> Metro 2 translation with minimal latency
2. Proper categorization of modern debt types (BNPL, gig economy, etc.)
3. Real-time update capabilities (vs traditional 30-90 day lag)
4. Full E-OSCAR integration for dispute management
5. CDIA-compliant validation preventing rejections

Metro 2 Format Reference: Consumer Data Industry Association (CDIA)
Fixed-width format: Base Segment = 426 characters
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum, auto
from typing import Any, Optional, Callable
import hashlib
import json
import logging
import re
import gzip
import os
from collections import defaultdict

# Import Shadow Bureau types if available
try:
    from quan.shadow_bureau.live_ledger import (
        DebtCategory,
        MicroDebtRecord,
        ConsumerLedgerProfile,
        PaymentBehavior,
        RiskTier,
    )
except ImportError:
    # Standalone mode - define minimal types
    class DebtCategory(Enum):
        BNPL = "bnpl"
        SUBSCRIPTION = "subscription"
        GIG_ADVANCE = "gig_advance"
        OVERDRAFT = "overdraft"
        UTILITY = "utility"
        MEDICAL = "medical"
        FINTECH_LOAN = "fintech_loan"
        TELECOM = "telecom"
        OTHER = "other"


logger = logging.getLogger(__name__)


# =============================================================================
# METRO 2 FIELD CODES AND CONSTANTS
# =============================================================================

class AccountType(Enum):
    """Metro 2 Account Type Codes (Field 11)"""
    # Traditional types
    INSTALLMENT = "00"       # Installment (fixed number of payments)
    REVOLVING = "01"         # Revolving (credit cards, lines of credit)
    MORTGAGE_FIRST = "02"    # First Mortgage
    MORTGAGE_SECOND = "04"   # Second Mortgage
    HELOC = "05"             # Home Equity Line of Credit
    CHARGE = "06"            # Charge Account
    STUDENT_LOAN = "07"      # Student Loan
    AUTO_LOAN = "08"         # Auto Loan
    OPEN = "18"              # Open Account (30-day terms, utilities, etc.)
    COLLECTION = "9A"        # Collection Account

    # Modern mappings (QUAN innovation)
    BNPL_INSTALLMENT = "00"  # BNPL maps to installment
    SUBSCRIPTION = "01"      # Subscription maps to revolving
    GIG_ADVANCE = "00"       # Gig advance maps to installment
    FINTECH = "01"           # Fintech credit maps to revolving


class AccountStatus(Enum):
    """Metro 2 Account Status Codes (Field 17)"""
    CURRENT = "11"                    # Current, paying as agreed
    LATE_30 = "71"                    # 30 days past due
    LATE_60 = "78"                    # 60 days past due
    LATE_90 = "80"                    # 90 days past due
    LATE_120 = "82"                   # 120 days past due
    LATE_150 = "83"                   # 150 days past due
    LATE_180 = "84"                   # 180+ days past due
    COLLECTION = "93"                 # Collection account
    CHARGED_OFF = "97"                # Charged off
    PAID_COLLECTION = "62"            # Paid collection
    SETTLED = "65"                    # Settled for less than full
    PAID_FULL = "13"                  # Paid in full
    PAID_CHARGE_OFF = "64"            # Paid charge-off
    DISPUTED = "DA"                   # Account disputed
    TRANSFERRED = "05"                # Transferred to another lender


class PaymentRating(Enum):
    """Metro 2 Payment Rating (Field 19)"""
    CURRENT = "0"        # Current
    LATE_30 = "1"        # 30-59 days past due
    LATE_60 = "2"        # 60-89 days past due
    LATE_90 = "3"        # 90-119 days past due
    LATE_120 = "4"       # 120-149 days past due
    LATE_150 = "5"       # 150-179 days past due
    LATE_180 = "6"       # 180+ days past due
    UNKNOWN = "G"        # Unknown
    NO_PAYMENT = "L"     # No payment history available


class SpecialComment(Enum):
    """Metro 2 Special Comment Codes (Field 25)"""
    NONE = ""
    PAID_CREDITOR = "AC"              # Paid directly to creditor
    DISPUTED = "AU"                    # Account disputed
    CONSUMER_DECEASED = "AW"           # Consumer deceased
    ACCOUNT_CLOSED = "B"               # Account closed at consumer request
    BANKRUPTCY_CHAPTER_7 = "CB"        # Chapter 7 bankruptcy
    BANKRUPTCY_CHAPTER_13 = "CC"       # Chapter 13 bankruptcy
    DEED_IN_LIEU = "CF"               # Deed received in lieu
    SETTLED = "CP"                     # Settled for less
    PARTIAL_PAYMENT = "DF"             # Making partial payments
    DEFERMENT = "DG"                   # Account in deferment
    MEDICAL = "M"                      # Medical account
    MILITARY_DUTY = "V"                # Account affected by military


class ComplianceCondition(Enum):
    """Metro 2 Compliance Condition Codes (Field 26)"""
    NONE = ""
    MEETS_FCRA = "XA"                  # Meets FCRA requirements
    MEETS_STATE = "XB"                 # Meets state requirements
    UNDER_FCBA = "XC"                  # Under FCBA dispute
    CONSUMER_DISPUTE = "XF"            # Consumer disputes accuracy
    IDENTITY_THEFT = "XH"              # Identity theft victim
    LEGAL_NOTICE = "XJ"                # In legal notice period


class ECOACode(Enum):
    """Metro 2 ECOA (Ownership) Codes (Field 10)"""
    INDIVIDUAL = "1"                   # Individual account
    JOINT = "2"                        # Joint account
    AUTHORIZED_USER = "3"              # Authorized user
    COSIGNER = "5"                     # Co-signer
    BUSINESS_INDIVIDUAL = "7"          # Business - individual responsible


class PortfolioType(Enum):
    """Metro 2 Portfolio Type Codes (Field 5)"""
    LINE_OF_CREDIT = "C"
    INSTALLMENT = "I"
    MORTGAGE = "M"
    OPEN = "O"
    REVOLVING = "R"


# =============================================================================
# METRO 2 SEGMENT DATACLASSES
# =============================================================================

@dataclass
class Metro2BaseSegment:
    """
    Metro 2 Base Segment (426 characters fixed-width)

    This is the core record for reporting tradelines to credit bureaus.
    All fields follow CDIA Metro 2 Format specifications.
    """
    # Header/Identification (Positions 1-38)
    record_descriptor_word: int = 426           # Always 0426 for base segment
    processing_indicator: int = 1               # 1=Update, 2=Delete
    timestamp: datetime = field(default_factory=datetime.now)

    # Reporter Identification (Positions 1-10)
    identification_number: str = ""             # Subscriber code (10 chars)
    cycle_identifier: str = ""                  # Reporting cycle (2 chars)

    # Consumer Identification (Positions 11-80)
    consumer_account_number: str = ""           # Account number (30 chars)
    portfolio_type: PortfolioType = PortfolioType.INSTALLMENT
    account_type: AccountType = AccountType.COLLECTION

    # Account Information (Positions 81-160)
    date_opened: date | None = None
    credit_limit: int = 0                       # Dollars, no cents
    highest_credit: int = 0
    terms_duration: int = 0                     # Months
    terms_frequency: str = "M"                  # M=Monthly, W=Weekly

    # Balances (Positions 161-200)
    current_balance: int = 0                    # Current balance in dollars
    amount_past_due: int = 0                    # Past due amount
    original_charge_off_amount: int = 0         # Original charge-off amount

    # Dates (Positions 201-240)
    date_closed: date | None = None
    date_last_payment: date | None = None
    date_first_delinquency: date | None = None
    date_account_status: date | None = None

    # Status Codes (Positions 241-270)
    account_status: AccountStatus = AccountStatus.COLLECTION
    payment_rating: PaymentRating = PaymentRating.LATE_180
    payment_history_profile: str = ""           # 24-month history
    special_comment: SpecialComment = SpecialComment.NONE
    compliance_condition: ComplianceCondition = ComplianceCondition.NONE

    # Consumer Info (Positions 271-350)
    consumer_first_name: str = ""
    consumer_middle_name: str = ""
    consumer_last_name: str = ""
    consumer_suffix: str = ""
    consumer_generation: str = ""

    # Consumer Demographics (Positions 351-426)
    ssn: str = ""                               # 9 digits, no dashes
    date_of_birth: date | None = None
    telephone_number: str = ""
    ecoa_code: ECOACode = ECOACode.INDIVIDUAL

    # Address
    address_first_line: str = ""
    address_second_line: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    country_code: str = "US"

    # QUAN Extensions (not in Metro 2, for internal tracking)
    quan_record_id: str = ""
    shadow_score: int | None = None
    debt_category: DebtCategory = DebtCategory.OTHER

    def to_fixed_width(self) -> str:
        """
        Convert to Metro 2 fixed-width format (426 characters)

        This is the critical method that produces bureau-compliant output.
        """
        # Helper for padding
        def alpha(val: str, length: int) -> str:
            """Left-justify, pad with spaces, uppercase"""
            return str(val).upper().ljust(length)[:length]

        def numeric(val: int, length: int) -> str:
            """Right-justify, pad with zeros"""
            return str(abs(int(val))).zfill(length)[:length]

        def date_fmt(d: date | None) -> str:
            """Format date as MMDDYYYY or spaces if None"""
            if d is None:
                return " " * 8
            return d.strftime("%m%d%Y")

        # Build the fixed-width record
        record = []

        # Positions 1-4: Record Descriptor Word
        record.append(numeric(self.record_descriptor_word, 4))

        # Position 5: Processing Indicator
        record.append(str(self.processing_indicator))

        # Positions 6-9: Reserved
        record.append(" " * 4)

        # Positions 10-19: Identification Number (Subscriber ID)
        record.append(alpha(self.identification_number, 10))

        # Positions 20-21: Cycle Identifier
        record.append(alpha(self.cycle_identifier, 2))

        # Positions 22-51: Consumer Account Number
        record.append(alpha(self.consumer_account_number, 30))

        # Position 52: Portfolio Type
        record.append(self.portfolio_type.value)

        # Positions 53-54: Account Type
        record.append(self.account_type.value)

        # Positions 55-62: Date Opened
        record.append(date_fmt(self.date_opened))

        # Positions 63-71: Credit Limit / Highest Credit
        record.append(numeric(self.credit_limit or self.highest_credit, 9))

        # Positions 72-74: Terms Duration
        record.append(numeric(self.terms_duration, 3))

        # Position 75: Terms Frequency
        record.append(self.terms_frequency)

        # Positions 76-84: Original Loan Amount / Highest Credit
        record.append(numeric(self.highest_credit, 9))

        # Positions 85-93: Current Balance
        record.append(numeric(self.current_balance, 9))

        # Positions 94-102: Amount Past Due
        record.append(numeric(self.amount_past_due, 9))

        # Positions 103-111: Original Charge-off Amount
        record.append(numeric(self.original_charge_off_amount, 9))

        # Positions 112-119: Date Closed
        record.append(date_fmt(self.date_closed))

        # Positions 120-127: Date of Last Payment
        record.append(date_fmt(self.date_last_payment))

        # Positions 128-135: Date of First Delinquency
        record.append(date_fmt(self.date_first_delinquency))

        # Positions 136-143: Date of Account Information
        record.append(date_fmt(self.date_account_status or datetime.now().date()))

        # Positions 144-145: Account Status
        record.append(self.account_status.value)

        # Position 146: Payment Rating
        record.append(self.payment_rating.value)

        # Positions 147-170: Payment History Profile (24 months)
        payment_history = self.payment_history_profile.ljust(24)[:24]
        record.append(payment_history)

        # Positions 171-172: Special Comment
        record.append(alpha(self.special_comment.value, 2))

        # Positions 173-174: Compliance Condition Code
        record.append(alpha(self.compliance_condition.value, 2))

        # Positions 175-179: Reserved
        record.append(" " * 5)

        # Position 180: ECOA Code
        record.append(self.ecoa_code.value)

        # Positions 181-205: Consumer Name
        record.append(alpha(self.consumer_first_name, 15))
        record.append(alpha(self.consumer_middle_name, 15))
        record.append(alpha(self.consumer_last_name, 25))

        # Positions 256-259: Generation Code
        record.append(alpha(self.consumer_generation, 4))

        # Positions 260-268: SSN
        ssn_clean = re.sub(r'\D', '', self.ssn)
        record.append(numeric(int(ssn_clean) if ssn_clean else 0, 9))

        # Positions 269-276: Date of Birth
        record.append(date_fmt(self.date_of_birth))

        # Positions 277-286: Telephone Number
        phone_clean = re.sub(r'\D', '', self.telephone_number)
        record.append(alpha(phone_clean, 10))

        # Address block
        # Positions 287-318: Address Line 1
        record.append(alpha(self.address_first_line, 32))

        # Positions 319-350: Address Line 2
        record.append(alpha(self.address_second_line, 32))

        # Positions 351-370: City
        record.append(alpha(self.city, 20))

        # Positions 371-372: State
        record.append(alpha(self.state, 2))

        # Positions 373-381: ZIP Code
        zip_clean = re.sub(r'\D', '', self.zip_code)
        record.append(alpha(zip_clean, 9))

        # Positions 382-383: Country Code
        record.append(alpha(self.country_code, 2))

        # Positions 384-426: Reserved / Filler
        record.append(" " * 43)

        # Join and validate length
        output = "".join(record)

        # Ensure exactly 426 characters
        if len(output) < 426:
            output = output.ljust(426)
        elif len(output) > 426:
            output = output[:426]
            logger.warning(f"Base segment truncated from {len(output)} to 426 chars")

        return output

    @classmethod
    def from_fixed_width(cls, line: str) -> "Metro2BaseSegment":
        """Parse a Metro 2 fixed-width line into a BaseSegment"""
        if len(line) < 426:
            raise ValueError(f"Line too short: {len(line)} < 426")

        segment = cls()

        # Parse fields from fixed positions
        segment.record_descriptor_word = int(line[0:4])
        segment.processing_indicator = int(line[4:5])
        segment.identification_number = line[9:19].strip()
        segment.cycle_identifier = line[19:21].strip()
        segment.consumer_account_number = line[21:51].strip()

        # Parse portfolio type
        pt = line[51:52]
        for ptype in PortfolioType:
            if ptype.value == pt:
                segment.portfolio_type = ptype
                break

        # Continue parsing other fields...
        # (abbreviated for demo - full implementation would parse all fields)

        return segment


@dataclass
class Metro2J1Segment:
    """
    J1 Segment - Associated Consumer (Secondary) Information

    Used when reporting joint accounts or authorized users.
    Follows the base segment.
    """
    record_descriptor_word: int = 100
    segment_identifier: str = "J1"

    # Associated consumer info
    surname: str = ""
    first_name: str = ""
    middle_name: str = ""
    generation_code: str = ""

    ssn: str = ""
    date_of_birth: date | None = None
    ecoa_code: ECOACode = ECOACode.JOINT
    telephone_number: str = ""

    # Address (if different)
    address_first_line: str = ""
    address_second_line: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    country_code: str = "US"

    def to_fixed_width(self) -> str:
        """Convert to J1 segment fixed-width format (100 characters)"""
        def alpha(val: str, length: int) -> str:
            return str(val).upper().ljust(length)[:length]

        def numeric(val: int, length: int) -> str:
            return str(abs(int(val))).zfill(length)[:length]

        def date_fmt(d: date | None) -> str:
            if d is None:
                return " " * 8
            return d.strftime("%m%d%Y")

        record = []

        # Positions 1-4: Record Descriptor Word
        record.append(numeric(self.record_descriptor_word, 4))

        # Positions 5-6: Segment Identifier
        record.append(self.segment_identifier)

        # Positions 7-31: Surname
        record.append(alpha(self.surname, 25))

        # Positions 32-46: First Name
        record.append(alpha(self.first_name, 15))

        # Positions 47-61: Middle Name
        record.append(alpha(self.middle_name, 15))

        # Positions 62-65: Generation Code
        record.append(alpha(self.generation_code, 4))

        # Positions 66-74: SSN
        ssn_clean = re.sub(r'\D', '', self.ssn)
        record.append(numeric(int(ssn_clean) if ssn_clean else 0, 9))

        # Positions 75-82: Date of Birth
        record.append(date_fmt(self.date_of_birth))

        # Position 83: ECOA Code
        record.append(self.ecoa_code.value)

        # Positions 84-93: Telephone
        phone_clean = re.sub(r'\D', '', self.telephone_number)
        record.append(alpha(phone_clean, 10))

        # Positions 94-100: Reserved
        record.append(" " * 7)

        output = "".join(record)
        return output.ljust(100)[:100]


@dataclass
class Metro2J2Segment:
    """
    J2 Segment - Additional Associated Consumer Information

    Extended information for associated consumer, including full address.
    """
    record_descriptor_word: int = 200
    segment_identifier: str = "J2"

    # Same consumer info as J1
    surname: str = ""
    first_name: str = ""
    middle_name: str = ""
    generation_code: str = ""
    ssn: str = ""
    date_of_birth: date | None = None
    ecoa_code: ECOACode = ECOACode.JOINT
    telephone_number: str = ""

    # Full address
    address_first_line: str = ""
    address_second_line: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    country_code: str = "US"

    def to_fixed_width(self) -> str:
        """Convert to J2 segment fixed-width format (200 characters)"""
        def alpha(val: str, length: int) -> str:
            return str(val).upper().ljust(length)[:length]

        def numeric(val: int, length: int) -> str:
            return str(abs(int(val))).zfill(length)[:length]

        def date_fmt(d: date | None) -> str:
            if d is None:
                return " " * 8
            return d.strftime("%m%d%Y")

        record = []

        # Positions 1-4: Record Descriptor Word
        record.append(numeric(self.record_descriptor_word, 4))

        # Positions 5-6: Segment Identifier
        record.append(self.segment_identifier)

        # Consumer info (same structure as J1)
        record.append(alpha(self.surname, 25))
        record.append(alpha(self.first_name, 15))
        record.append(alpha(self.middle_name, 15))
        record.append(alpha(self.generation_code, 4))

        ssn_clean = re.sub(r'\D', '', self.ssn)
        record.append(numeric(int(ssn_clean) if ssn_clean else 0, 9))
        record.append(date_fmt(self.date_of_birth))
        record.append(self.ecoa_code.value)

        phone_clean = re.sub(r'\D', '', self.telephone_number)
        record.append(alpha(phone_clean, 10))

        # Full address block
        record.append(alpha(self.address_first_line, 32))
        record.append(alpha(self.address_second_line, 32))
        record.append(alpha(self.city, 20))
        record.append(alpha(self.state, 2))

        zip_clean = re.sub(r'\D', '', self.zip_code)
        record.append(alpha(zip_clean, 9))
        record.append(alpha(self.country_code, 2))

        # Padding to 200
        output = "".join(record)
        return output.ljust(200)[:200]


@dataclass
class Metro2KSegment:
    """
    K Segment - Original Creditor Information

    Required when reporting debt that has been sold or transferred.
    Critical for collection accounts to show chain of custody.
    """
    record_descriptor_word: int = 34
    segment_identifier: str = "K1"

    # Original creditor info
    original_creditor_name: str = ""
    original_creditor_classification: str = ""  # 2-char code

    # Original account info
    original_account_number: str = ""

    def to_fixed_width(self) -> str:
        """Convert to K segment fixed-width format (34 characters)"""
        def alpha(val: str, length: int) -> str:
            return str(val).upper().ljust(length)[:length]

        def numeric(val: int, length: int) -> str:
            return str(abs(int(val))).zfill(length)[:length]

        record = []

        # Positions 1-4: Record Descriptor Word
        record.append(numeric(self.record_descriptor_word, 4))

        # Positions 5-6: Segment Identifier
        record.append(self.segment_identifier)

        # Positions 7-36: Original Creditor Name (30 chars in spec)
        record.append(alpha(self.original_creditor_name, 30))

        # Remaining positions vary - simplified version
        output = "".join(record)
        return output.ljust(34)[:34]


@dataclass
class Metro2LSegment:
    """
    L Segment - Portfolio Sale/Transfer Information

    Used when portfolio is sold or transferred to another entity.
    """
    record_descriptor_word: int = 54
    segment_identifier: str = "L1"

    # Transfer info
    new_identification_number: str = ""   # New servicer ID
    new_account_number: str = ""
    date_of_transfer: date | None = None

    def to_fixed_width(self) -> str:
        """Convert to L segment fixed-width format (54 characters)"""
        def alpha(val: str, length: int) -> str:
            return str(val).upper().ljust(length)[:length]

        def numeric(val: int, length: int) -> str:
            return str(abs(int(val))).zfill(length)[:length]

        def date_fmt(d: date | None) -> str:
            if d is None:
                return " " * 8
            return d.strftime("%m%d%Y")

        record = []

        record.append(numeric(self.record_descriptor_word, 4))
        record.append(self.segment_identifier)
        record.append(alpha(self.new_identification_number, 10))
        record.append(alpha(self.new_account_number, 30))
        record.append(date_fmt(self.date_of_transfer))

        output = "".join(record)
        return output.ljust(54)[:54]


# =============================================================================
# HEADER AND TRAILER RECORDS
# =============================================================================

@dataclass
class Metro2HeaderRecord:
    """Metro 2 Header Record - Required at start of each file"""
    record_descriptor_word: int = 426
    record_identifier: str = "HEADER"
    cycle_identifier: str = ""
    innovis_program_identifier: str = ""
    equifax_program_identifier: str = ""
    experian_program_identifier: str = ""
    transunion_program_identifier: str = ""
    activity_date: date = field(default_factory=date.today)
    date_created: date = field(default_factory=date.today)
    program_date: date = field(default_factory=date.today)
    program_revision_date: date = field(default_factory=date.today)
    reporter_name: str = ""
    reporter_address: str = ""
    reporter_city: str = ""
    reporter_state: str = ""
    reporter_zip: str = ""
    reporter_phone: str = ""

    def to_fixed_width(self) -> str:
        """Generate fixed-width header record"""
        def alpha(val: str, length: int) -> str:
            return str(val).upper().ljust(length)[:length]

        def numeric(val: int, length: int) -> str:
            return str(abs(int(val))).zfill(length)[:length]

        def date_fmt(d: date | None) -> str:
            if d is None:
                return " " * 8
            return d.strftime("%m%d%Y")

        record = []

        # Build header
        record.append(numeric(self.record_descriptor_word, 4))
        record.append(alpha("HEADER", 6))
        record.append(alpha(self.cycle_identifier, 2))
        record.append(alpha(self.innovis_program_identifier, 10))
        record.append(alpha(self.equifax_program_identifier, 10))
        record.append(alpha(self.experian_program_identifier, 10))
        record.append(alpha(self.transunion_program_identifier, 10))
        record.append(date_fmt(self.activity_date))
        record.append(date_fmt(self.date_created))
        record.append(date_fmt(self.program_date))
        record.append(date_fmt(self.program_revision_date))
        record.append(alpha(self.reporter_name, 40))
        record.append(alpha(self.reporter_address, 96))
        record.append(alpha(self.reporter_phone, 10))

        output = "".join(record)
        return output.ljust(426)[:426]


@dataclass
class Metro2TrailerRecord:
    """Metro 2 Trailer Record - Required at end of each file"""
    record_descriptor_word: int = 426
    record_identifier: str = "TRAILER"
    total_base_records: int = 0
    total_j1_segments: int = 0
    total_j2_segments: int = 0
    total_k_segments: int = 0
    total_l_segments: int = 0
    total_status_11: int = 0  # Current accounts
    total_status_collections: int = 0
    total_date_of_birth_included: int = 0
    total_ssn_included: int = 0
    total_ecoa_codes: dict = field(default_factory=dict)

    def to_fixed_width(self) -> str:
        """Generate fixed-width trailer record"""
        def alpha(val: str, length: int) -> str:
            return str(val).upper().ljust(length)[:length]

        def numeric(val: int, length: int) -> str:
            return str(abs(int(val))).zfill(length)[:length]

        record = []

        record.append(numeric(self.record_descriptor_word, 4))
        record.append(alpha("TRAILER", 7))
        record.append(numeric(self.total_base_records, 9))
        record.append(" " * 9)  # Reserved
        record.append(numeric(self.total_j1_segments, 9))
        record.append(numeric(self.total_j2_segments, 9))
        record.append(numeric(self.total_k_segments, 9))
        record.append(numeric(self.total_l_segments, 9))
        record.append(numeric(self.total_status_11, 9))
        record.append(numeric(self.total_status_collections, 9))
        record.append(numeric(self.total_date_of_birth_included, 9))
        record.append(numeric(self.total_ssn_included, 9))

        output = "".join(record)
        return output.ljust(426)[:426]


# =============================================================================
# TRADE LINE MAPPING - SOLVING THE "CATEGORIZATION FAILURE" PROBLEM
# =============================================================================

class TradeLineMapper:
    """
    Map modern debt types to Metro 2 account codes

    This addresses the thesis criticism that Metro 2 can't handle
    modern debt types like BNPL, gig economy advances, etc.

    Key insight: The codes exist, the mapping logic doesn't.
    """

    # Mapping from QUAN DebtCategory to Metro 2 codes
    CATEGORY_TO_ACCOUNT_TYPE = {
        DebtCategory.BNPL: AccountType.INSTALLMENT,
        DebtCategory.SUBSCRIPTION: AccountType.REVOLVING,
        DebtCategory.GIG_ADVANCE: AccountType.INSTALLMENT,
        DebtCategory.OVERDRAFT: AccountType.REVOLVING,
        DebtCategory.UTILITY: AccountType.OPEN,
        DebtCategory.MEDICAL: AccountType.INSTALLMENT,
        DebtCategory.FINTECH_LOAN: AccountType.REVOLVING,
        DebtCategory.TELECOM: AccountType.INSTALLMENT,
        DebtCategory.OTHER: AccountType.COLLECTION,
    }

    CATEGORY_TO_PORTFOLIO_TYPE = {
        DebtCategory.BNPL: PortfolioType.INSTALLMENT,
        DebtCategory.SUBSCRIPTION: PortfolioType.REVOLVING,
        DebtCategory.GIG_ADVANCE: PortfolioType.INSTALLMENT,
        DebtCategory.OVERDRAFT: PortfolioType.LINE_OF_CREDIT,
        DebtCategory.UTILITY: PortfolioType.OPEN,
        DebtCategory.MEDICAL: PortfolioType.INSTALLMENT,
        DebtCategory.FINTECH_LOAN: PortfolioType.REVOLVING,
        DebtCategory.TELECOM: PortfolioType.INSTALLMENT,
        DebtCategory.OTHER: PortfolioType.INSTALLMENT,
    }

    # Industry-specific mappings for enhanced categorization
    CREDITOR_PATTERNS = {
        # BNPL providers
        r"klarna|afterpay|affirm|sezzle|zip": DebtCategory.BNPL,
        # Gig economy
        r"uber|lyft|doordash|instacart|grubhub": DebtCategory.GIG_ADVANCE,
        # Streaming/subscriptions
        r"netflix|spotify|hulu|disney|amazon prime": DebtCategory.SUBSCRIPTION,
        # Fintech
        r"cashapp|venmo|paypal|chime|dave": DebtCategory.FINTECH_LOAN,
        # Telecom
        r"verizon|att|t-mobile|sprint": DebtCategory.TELECOM,
        # Medical
        r"hospital|medical|clinic|health|doctor": DebtCategory.MEDICAL,
    }

    # Special comment codes for modern debt
    CATEGORY_TO_SPECIAL_COMMENT = {
        DebtCategory.MEDICAL: SpecialComment.MEDICAL,
        # Others use standard codes based on status
    }

    @classmethod
    def infer_category(cls, creditor_name: str, balance: float = 0) -> DebtCategory:
        """
        Infer debt category from creditor name

        This solves the "categorization failure" problem by using
        pattern matching on known modern creditors.
        """
        name_lower = creditor_name.lower()

        for pattern, category in cls.CREDITOR_PATTERNS.items():
            if re.search(pattern, name_lower):
                return category

        # Heuristics based on balance
        if balance < 50:
            return DebtCategory.SUBSCRIPTION
        elif balance < 200:
            return DebtCategory.BNPL
        elif balance < 500:
            return DebtCategory.FINTECH_LOAN

        return DebtCategory.OTHER

    @classmethod
    def get_account_type(cls, category: DebtCategory) -> AccountType:
        """Get Metro 2 account type for debt category"""
        return cls.CATEGORY_TO_ACCOUNT_TYPE.get(category, AccountType.COLLECTION)

    @classmethod
    def get_portfolio_type(cls, category: DebtCategory) -> PortfolioType:
        """Get Metro 2 portfolio type for debt category"""
        return cls.CATEGORY_TO_PORTFOLIO_TYPE.get(category, PortfolioType.INSTALLMENT)

    @classmethod
    def get_special_comment(
        cls,
        category: DebtCategory,
        status: str,
        is_disputed: bool = False
    ) -> SpecialComment:
        """Determine appropriate special comment code"""
        if is_disputed:
            return SpecialComment.DISPUTED

        if category == DebtCategory.MEDICAL:
            return SpecialComment.MEDICAL

        if status == "settled":
            return SpecialComment.SETTLED

        return SpecialComment.NONE

    @classmethod
    def calculate_payment_history(
        cls,
        payment_records: list[dict],
        months: int = 24
    ) -> str:
        """
        Generate 24-month payment history profile

        Returns string of 24 characters, each representing payment status:
        0=Current, 1=30 days, 2=60 days, etc., B=No history
        """
        history = []

        # Sort by date descending (most recent first)
        sorted_records = sorted(
            payment_records,
            key=lambda x: x.get("date", datetime.min),
            reverse=True
        )

        for i in range(months):
            if i < len(sorted_records):
                days_late = sorted_records[i].get("days_late", 0)
                if days_late == 0:
                    history.append("0")
                elif days_late < 30:
                    history.append("0")
                elif days_late < 60:
                    history.append("1")
                elif days_late < 90:
                    history.append("2")
                elif days_late < 120:
                    history.append("3")
                elif days_late < 150:
                    history.append("4")
                elif days_late < 180:
                    history.append("5")
                else:
                    history.append("6")
            else:
                history.append("B")  # No history for this month

        return "".join(history)


# =============================================================================
# METRO 2 BRIDGE - CORE TRANSLATION ENGINE
# =============================================================================

class Metro2Bridge:
    """
    Core Metro 2 Bridge - Translates QUAN data to Metro 2 format

    This is the main class that takes QUAN debt records and produces
    compliant Metro 2 output for credit bureau submission.
    """

    def __init__(
        self,
        subscriber_id: str,
        subscriber_name: str,
        subscriber_address: str = "",
        subscriber_city: str = "",
        subscriber_state: str = "",
        subscriber_zip: str = "",
        subscriber_phone: str = "",
    ):
        self.subscriber_id = subscriber_id
        self.subscriber_name = subscriber_name
        self.subscriber_address = subscriber_address
        self.subscriber_city = subscriber_city
        self.subscriber_state = subscriber_state
        self.subscriber_zip = subscriber_zip
        self.subscriber_phone = subscriber_phone

        self.mapper = TradeLineMapper()
        self.validator = Metro2Validator()

        # Track conversion statistics
        self.stats = {
            "records_processed": 0,
            "records_valid": 0,
            "records_invalid": 0,
            "validation_errors": defaultdict(int),
        }

    def translate_quan_record(
        self,
        quan_record: dict[str, Any],
        include_k_segment: bool = True,
    ) -> tuple[Metro2BaseSegment, list[Any], list[str]]:
        """
        Translate a QUAN debt record to Metro 2 segments

        Args:
            quan_record: QUAN debt record dictionary
            include_k_segment: Include K segment for original creditor

        Returns:
            Tuple of (base_segment, additional_segments, validation_errors)
        """
        errors = []
        additional_segments = []

        # Extract QUAN fields
        record_id = quan_record.get("record_id", "")
        consumer_id = quan_record.get("consumer_id", "")
        creditor_name = quan_record.get("creditor_name", "")

        # Determine category
        category_str = quan_record.get("category", "other")
        if isinstance(category_str, DebtCategory):
            category = category_str
        else:
            try:
                category = DebtCategory(category_str)
            except ValueError:
                category = TradeLineMapper.infer_category(
                    creditor_name,
                    quan_record.get("original_balance", 0)
                )

        # Calculate days past due
        charge_off_date = quan_record.get("charge_off_date")
        if isinstance(charge_off_date, str):
            charge_off_date = datetime.fromisoformat(charge_off_date)
        elif isinstance(charge_off_date, datetime):
            charge_off_date = charge_off_date.date() if hasattr(charge_off_date, 'date') else charge_off_date

        days_past_due = quan_record.get("days_past_due", 0)
        if charge_off_date and days_past_due == 0:
            if isinstance(charge_off_date, datetime):
                days_past_due = (datetime.now() - charge_off_date).days
            else:
                days_past_due = (date.today() - charge_off_date).days

        # Determine account status
        collection_status = quan_record.get("collection_status", "active")
        resolution_type = quan_record.get("resolution_type")

        if collection_status == "resolved":
            if resolution_type == "paid_full":
                account_status = AccountStatus.PAID_COLLECTION
            elif resolution_type == "settled":
                account_status = AccountStatus.SETTLED
            else:
                account_status = AccountStatus.PAID_COLLECTION
        elif collection_status == "disputed":
            account_status = AccountStatus.DISPUTED
        else:
            # Active collection - determine by days past due
            if days_past_due < 30:
                account_status = AccountStatus.CURRENT
            elif days_past_due < 60:
                account_status = AccountStatus.LATE_30
            elif days_past_due < 90:
                account_status = AccountStatus.LATE_60
            elif days_past_due < 120:
                account_status = AccountStatus.LATE_90
            elif days_past_due < 150:
                account_status = AccountStatus.LATE_120
            elif days_past_due < 180:
                account_status = AccountStatus.LATE_150
            else:
                account_status = AccountStatus.COLLECTION

        # Determine payment rating
        if collection_status == "resolved":
            payment_rating = PaymentRating.CURRENT
        elif days_past_due >= 180:
            payment_rating = PaymentRating.LATE_180
        elif days_past_due >= 150:
            payment_rating = PaymentRating.LATE_150
        elif days_past_due >= 120:
            payment_rating = PaymentRating.LATE_120
        elif days_past_due >= 90:
            payment_rating = PaymentRating.LATE_90
        elif days_past_due >= 60:
            payment_rating = PaymentRating.LATE_60
        elif days_past_due >= 30:
            payment_rating = PaymentRating.LATE_30
        else:
            payment_rating = PaymentRating.CURRENT

        # Build base segment
        base_segment = Metro2BaseSegment(
            identification_number=self.subscriber_id,
            cycle_identifier=datetime.now().strftime("%m"),
            consumer_account_number=record_id or consumer_id[:30],
            portfolio_type=TradeLineMapper.get_portfolio_type(category),
            account_type=TradeLineMapper.get_account_type(category),
            date_opened=charge_off_date,
            credit_limit=0,
            highest_credit=int(quan_record.get("original_balance", 0)),
            terms_duration=quan_record.get("terms_months", 0),
            terms_frequency="M",
            current_balance=int(quan_record.get("current_balance", 0)),
            amount_past_due=int(quan_record.get("current_balance", 0)) if collection_status == "active" else 0,
            original_charge_off_amount=int(quan_record.get("original_balance", 0)),
            date_last_payment=self._parse_date(quan_record.get("last_payment_date")),
            date_first_delinquency=charge_off_date,
            date_account_status=date.today(),
            account_status=account_status,
            payment_rating=payment_rating,
            payment_history_profile=TradeLineMapper.calculate_payment_history(
                quan_record.get("payment_history", [])
            ),
            special_comment=TradeLineMapper.get_special_comment(
                category,
                collection_status,
                quan_record.get("is_disputed", False)
            ),
            compliance_condition=ComplianceCondition.MEETS_FCRA,
            consumer_first_name=quan_record.get("first_name", ""),
            consumer_middle_name=quan_record.get("middle_name", ""),
            consumer_last_name=quan_record.get("last_name", ""),
            ssn=quan_record.get("ssn", ""),
            date_of_birth=self._parse_date(quan_record.get("date_of_birth")),
            telephone_number=quan_record.get("phone", ""),
            ecoa_code=ECOACode.INDIVIDUAL,
            address_first_line=quan_record.get("address_line1", ""),
            address_second_line=quan_record.get("address_line2", ""),
            city=quan_record.get("city", ""),
            state=quan_record.get("state", ""),
            zip_code=quan_record.get("zip_code", ""),
            quan_record_id=record_id,
            shadow_score=quan_record.get("shadow_score"),
            debt_category=category,
        )

        # Add K segment for original creditor if this is a purchased debt
        if include_k_segment and creditor_name:
            k_segment = Metro2KSegment(
                original_creditor_name=creditor_name,
                original_creditor_classification="01",  # Financial
                original_account_number=quan_record.get("original_account_number", ""),
            )
            additional_segments.append(k_segment)

        # Add J1/J2 for joint accounts
        if quan_record.get("joint_consumer"):
            joint = quan_record["joint_consumer"]
            j1_segment = Metro2J1Segment(
                surname=joint.get("last_name", ""),
                first_name=joint.get("first_name", ""),
                middle_name=joint.get("middle_name", ""),
                ssn=joint.get("ssn", ""),
                date_of_birth=self._parse_date(joint.get("date_of_birth")),
                ecoa_code=ECOACode.JOINT,
                telephone_number=joint.get("phone", ""),
            )
            additional_segments.append(j1_segment)

        # Validate
        validation_errors = self.validator.validate_base_segment(base_segment)
        errors.extend(validation_errors)

        # Update stats
        self.stats["records_processed"] += 1
        if errors:
            self.stats["records_invalid"] += 1
            for err in errors:
                self.stats["validation_errors"][err] += 1
        else:
            self.stats["records_valid"] += 1

        return base_segment, additional_segments, errors

    def _parse_date(self, value: Any) -> date | None:
        """Parse various date formats to date object"""
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
            except ValueError:
                try:
                    return datetime.strptime(value, "%Y-%m-%d").date()
                except ValueError:
                    return None
        return None

    def generate_metro2_file(
        self,
        records: list[dict[str, Any]],
        output_path: str | None = None,
        compress: bool = False,
    ) -> str:
        """
        Generate complete Metro 2 file from QUAN records

        Args:
            records: List of QUAN debt records
            output_path: Path to write file (optional)
            compress: Whether to gzip the output

        Returns:
            The Metro 2 file content as string
        """
        lines = []

        # Generate header
        header = Metro2HeaderRecord(
            cycle_identifier=datetime.now().strftime("%m"),
            activity_date=date.today(),
            date_created=date.today(),
            reporter_name=self.subscriber_name,
            reporter_address=self.subscriber_address,
            reporter_city=self.subscriber_city,
            reporter_state=self.subscriber_state,
            reporter_zip=self.subscriber_zip,
            reporter_phone=self.subscriber_phone,
        )
        lines.append(header.to_fixed_width())

        # Track trailer counts
        trailer = Metro2TrailerRecord()

        # Process each record
        for quan_record in records:
            base_segment, additional_segments, errors = self.translate_quan_record(quan_record)

            if not errors:  # Only include valid records
                lines.append(base_segment.to_fixed_width())
                trailer.total_base_records += 1

                if base_segment.ssn:
                    trailer.total_ssn_included += 1
                if base_segment.date_of_birth:
                    trailer.total_date_of_birth_included += 1
                if base_segment.account_status == AccountStatus.COLLECTION:
                    trailer.total_status_collections += 1
                elif base_segment.account_status == AccountStatus.CURRENT:
                    trailer.total_status_11 += 1

                # Add additional segments
                for segment in additional_segments:
                    lines.append(segment.to_fixed_width())
                    if isinstance(segment, Metro2J1Segment):
                        trailer.total_j1_segments += 1
                    elif isinstance(segment, Metro2J2Segment):
                        trailer.total_j2_segments += 1
                    elif isinstance(segment, Metro2KSegment):
                        trailer.total_k_segments += 1
                    elif isinstance(segment, Metro2LSegment):
                        trailer.total_l_segments += 1

        # Generate trailer
        lines.append(trailer.to_fixed_width())

        # Combine into file
        content = "\n".join(lines)

        # Write to file if path provided
        if output_path:
            if compress:
                with gzip.open(output_path + ".gz", "wt") as f:
                    f.write(content)
            else:
                with open(output_path, "w") as f:
                    f.write(content)

        return content


# =============================================================================
# BATCH PROCESSING
# =============================================================================

class Metro2BatchProcessor:
    """
    Batch processing for Metro 2 file generation

    Handles:
    - Monthly full-file generation
    - Incremental updates
    - Corrections and deletions
    - Archive management
    """

    def __init__(
        self,
        bridge: Metro2Bridge,
        archive_dir: str = "/var/quan/metro2/archive",
    ):
        self.bridge = bridge
        self.archive_dir = archive_dir
        self.batch_log: list[dict] = []

    def generate_monthly_file(
        self,
        records: list[dict[str, Any]],
        reporting_month: date | None = None,
    ) -> dict[str, Any]:
        """
        Generate monthly Metro 2 file

        Returns metadata about the generated file.
        """
        if reporting_month is None:
            reporting_month = date.today().replace(day=1)

        # Generate filename
        filename = f"METRO2_{self.bridge.subscriber_id}_{reporting_month.strftime('%Y%m')}.txt"
        filepath = os.path.join(self.archive_dir, filename)

        # Generate file
        content = self.bridge.generate_metro2_file(records, filepath)

        # Calculate hash for integrity
        file_hash = hashlib.sha256(content.encode()).hexdigest()

        # Log batch
        batch_info = {
            "batch_id": hashlib.md5(f"{filename}{datetime.now().isoformat()}".encode()).hexdigest()[:12],
            "filename": filename,
            "filepath": filepath,
            "reporting_month": reporting_month.isoformat(),
            "generated_at": datetime.now().isoformat(),
            "total_records": len(records),
            "valid_records": self.bridge.stats["records_valid"],
            "invalid_records": self.bridge.stats["records_invalid"],
            "file_size_bytes": len(content),
            "file_hash": file_hash,
            "status": "generated",
        }

        self.batch_log.append(batch_info)

        return batch_info

    def generate_incremental_update(
        self,
        changed_records: list[dict[str, Any]],
        update_type: str = "regular",  # regular, correction, deletion
    ) -> dict[str, Any]:
        """
        Generate incremental update file

        For real-time bridge capability - more frequent updates.
        """
        timestamp = datetime.now()
        filename = f"METRO2_INC_{self.bridge.subscriber_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = os.path.join(self.archive_dir, filename)

        # Set processing indicator based on update type
        processing_indicator = 1  # Update
        if update_type == "deletion":
            for record in changed_records:
                record["_processing_indicator"] = 2  # Delete

        content = self.bridge.generate_metro2_file(changed_records, filepath)

        return {
            "batch_id": hashlib.md5(f"{filename}{timestamp.isoformat()}".encode()).hexdigest()[:12],
            "filename": filename,
            "filepath": filepath,
            "update_type": update_type,
            "generated_at": timestamp.isoformat(),
            "record_count": len(changed_records),
            "status": "generated",
        }

    def generate_correction_file(
        self,
        corrections: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Generate correction file for previously reported data

        Corrections require special handling to update bureau records.
        """
        for correction in corrections:
            # Mark as correction
            correction["_is_correction"] = True
            # Ensure we have original account reference
            if not correction.get("original_record_id"):
                logger.warning(f"Correction missing original_record_id: {correction}")

        return self.generate_incremental_update(corrections, "correction")

    def generate_deletion_file(
        self,
        deletions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Generate deletion file to remove previously reported data

        Required when:
        - Identity theft confirmed
        - Data reported in error
        - Account not owned by consumer
        """
        return self.generate_incremental_update(deletions, "deletion")

    def get_batch_history(
        self,
        limit: int = 100,
        status_filter: str | None = None,
    ) -> list[dict]:
        """Get batch processing history"""
        history = self.batch_log[-limit:]

        if status_filter:
            history = [b for b in history if b.get("status") == status_filter]

        return history


# =============================================================================
# E-OSCAR INTEGRATION
# =============================================================================

class DisputeStatus(Enum):
    """E-OSCAR dispute statuses"""
    RECEIVED = "received"
    INVESTIGATING = "investigating"
    VERIFIED = "verified"
    MODIFIED = "modified"
    DELETED = "deleted"
    FRIVOLOUS = "frivolous"
    PENDING_RESPONSE = "pending_response"


@dataclass
class ACDVRequest:
    """
    Automated Consumer Dispute Verification (ACDV) Request

    Represents an incoming dispute from a credit bureau.
    """
    acdv_id: str
    control_number: str
    bureau: str  # EFX, EXP, TUC
    received_date: datetime
    response_due_date: datetime

    # Consumer info
    consumer_name: str
    consumer_ssn: str
    consumer_dob: date | None

    # Account info
    account_number: str
    dispute_code: str
    dispute_narrative: str

    # Our response
    response_code: str | None = None
    response_narrative: str | None = None
    response_date: datetime | None = None
    status: DisputeStatus = DisputeStatus.RECEIVED


@dataclass
class ACDVResponse:
    """ACDV Response to send back to bureau"""
    control_number: str
    account_number: str
    response_code: str  # V=Verified, M=Modified, D=Deleted, etc.
    response_date: datetime

    # If modified, include updated fields
    modified_fields: dict[str, Any] = field(default_factory=dict)

    # Narrative for complex responses
    narrative: str = ""


class EOscarIntegration:
    """
    E-OSCAR Integration for Dispute Management

    E-OSCAR (Online Solution for Complete and Accurate Reporting) is
    the web-based system used to process consumer disputes between
    credit bureaus and data furnishers.

    Key capabilities:
    - Receive ACDV requests
    - Process disputes within compliance timeframes
    - Generate compliant responses
    - Track dispute metrics
    """

    # Response codes
    RESPONSE_VERIFIED = "V"              # Verified as accurate
    RESPONSE_MODIFIED = "M"              # Modified per consumer
    RESPONSE_DELETED = "D"               # Deleted per consumer
    RESPONSE_CANNOT_VERIFY = "X"         # Unable to verify
    RESPONSE_PENDING = "P"               # Information pending
    RESPONSE_FRIVOLOUS = "F"             # Frivolous/irrelevant

    # Dispute code mappings
    DISPUTE_CODES = {
        "001": "Not my account",
        "002": "Account paid",
        "003": "Never late",
        "004": "Wrong balance",
        "005": "Wrong status",
        "006": "Identity theft",
        "007": "Duplicate account",
        "008": "Wrong date",
        "009": "Account closed",
        "010": "Other",
    }

    # Compliance timeframes (days)
    STANDARD_RESPONSE_DAYS = 30
    EXPEDITED_RESPONSE_DAYS = 15  # For ID theft, military

    def __init__(
        self,
        subscriber_id: str,
        bridge: Metro2Bridge,
    ):
        self.subscriber_id = subscriber_id
        self.bridge = bridge

        # Active disputes
        self.disputes: dict[str, ACDVRequest] = {}

        # Response tracking
        self.response_log: list[dict] = []

        # Metrics
        self.metrics = {
            "total_received": 0,
            "total_responded": 0,
            "verified": 0,
            "modified": 0,
            "deleted": 0,
            "avg_response_days": 0.0,
            "compliance_rate": 100.0,
        }

    def receive_acdv(
        self,
        acdv_data: dict[str, Any],
    ) -> ACDVRequest:
        """
        Receive and parse ACDV dispute request

        In production, this would integrate with the E-OSCAR API.
        """
        acdv = ACDVRequest(
            acdv_id=acdv_data.get("acdv_id", hashlib.md5(str(acdv_data).encode()).hexdigest()[:12]),
            control_number=acdv_data.get("control_number", ""),
            bureau=acdv_data.get("bureau", ""),
            received_date=datetime.now(),
            response_due_date=datetime.now() + timedelta(days=self.STANDARD_RESPONSE_DAYS),
            consumer_name=acdv_data.get("consumer_name", ""),
            consumer_ssn=acdv_data.get("consumer_ssn", ""),
            consumer_dob=self._parse_date(acdv_data.get("consumer_dob")),
            account_number=acdv_data.get("account_number", ""),
            dispute_code=acdv_data.get("dispute_code", "010"),
            dispute_narrative=acdv_data.get("dispute_narrative", ""),
        )

        # Check for expedited processing
        if acdv_data.get("is_identity_theft") or acdv_data.get("is_military"):
            acdv.response_due_date = datetime.now() + timedelta(days=self.EXPEDITED_RESPONSE_DAYS)

        self.disputes[acdv.acdv_id] = acdv
        self.metrics["total_received"] += 1

        logger.info(f"ACDV received: {acdv.acdv_id} - Code: {acdv.dispute_code}")

        return acdv

    def investigate_dispute(
        self,
        acdv_id: str,
        account_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Investigate a dispute against our records

        Returns investigation findings and recommended response.
        """
        acdv = self.disputes.get(acdv_id)
        if not acdv:
            return {"error": "ACDV not found"}

        acdv.status = DisputeStatus.INVESTIGATING

        findings = {
            "acdv_id": acdv_id,
            "dispute_code": acdv.dispute_code,
            "investigation_date": datetime.now().isoformat(),
            "account_found": account_data is not None,
            "recommended_response": None,
            "findings": [],
            "modifications": {},
        }

        if not account_data:
            findings["recommended_response"] = self.RESPONSE_DELETED
            findings["findings"].append("Account not found in our records")
            return findings

        # Analyze dispute based on code
        dispute_code = acdv.dispute_code

        if dispute_code == "001":  # Not my account
            # Check if consumer info matches
            name_match = self._fuzzy_name_match(
                acdv.consumer_name,
                f"{account_data.get('first_name', '')} {account_data.get('last_name', '')}"
            )
            ssn_match = acdv.consumer_ssn == account_data.get("ssn", "")

            if not ssn_match:
                findings["recommended_response"] = self.RESPONSE_DELETED
                findings["findings"].append("SSN does not match")
            elif not name_match:
                findings["recommended_response"] = self.RESPONSE_MODIFIED
                findings["findings"].append("Name discrepancy - updating consumer info")
            else:
                findings["recommended_response"] = self.RESPONSE_VERIFIED
                findings["findings"].append("Consumer info verified")

        elif dispute_code == "002":  # Account paid
            if account_data.get("collection_status") == "resolved":
                findings["recommended_response"] = self.RESPONSE_VERIFIED
                findings["findings"].append("Account already marked as paid")
            else:
                # Check for payment not yet reflected
                findings["recommended_response"] = self.RESPONSE_MODIFIED
                findings["modifications"]["account_status"] = AccountStatus.PAID_COLLECTION.value
                findings["findings"].append("Updating to reflect payment")

        elif dispute_code == "004":  # Wrong balance
            findings["recommended_response"] = self.RESPONSE_VERIFIED
            findings["findings"].append(
                f"Balance verified: ${account_data.get('current_balance', 0):.2f}"
            )

        elif dispute_code == "006":  # Identity theft
            findings["recommended_response"] = self.RESPONSE_DELETED
            findings["findings"].append("Identity theft claim - deleting per FCRA")

        else:
            findings["recommended_response"] = self.RESPONSE_VERIFIED
            findings["findings"].append("No discrepancies found")

        return findings

    def generate_response(
        self,
        acdv_id: str,
        response_code: str,
        modifications: dict[str, Any] | None = None,
        narrative: str = "",
    ) -> ACDVResponse:
        """
        Generate ACDV response to send to bureau
        """
        acdv = self.disputes.get(acdv_id)
        if not acdv:
            raise ValueError(f"ACDV not found: {acdv_id}")

        response = ACDVResponse(
            control_number=acdv.control_number,
            account_number=acdv.account_number,
            response_code=response_code,
            response_date=datetime.now(),
            modified_fields=modifications or {},
            narrative=narrative,
        )

        # Update ACDV record
        acdv.response_code = response_code
        acdv.response_narrative = narrative
        acdv.response_date = datetime.now()

        # Set status
        if response_code == self.RESPONSE_VERIFIED:
            acdv.status = DisputeStatus.VERIFIED
            self.metrics["verified"] += 1
        elif response_code == self.RESPONSE_MODIFIED:
            acdv.status = DisputeStatus.MODIFIED
            self.metrics["modified"] += 1
        elif response_code == self.RESPONSE_DELETED:
            acdv.status = DisputeStatus.DELETED
            self.metrics["deleted"] += 1

        # Log response
        self.response_log.append({
            "acdv_id": acdv_id,
            "response_code": response_code,
            "response_date": datetime.now().isoformat(),
            "days_to_respond": (datetime.now() - acdv.received_date).days,
        })

        self.metrics["total_responded"] += 1

        # Update average response time
        total_days = sum(r["days_to_respond"] for r in self.response_log)
        self.metrics["avg_response_days"] = total_days / len(self.response_log)

        return response

    def get_pending_disputes(
        self,
        days_until_due: int | None = None,
    ) -> list[ACDVRequest]:
        """Get disputes pending response"""
        pending = [
            d for d in self.disputes.values()
            if d.status in [DisputeStatus.RECEIVED, DisputeStatus.INVESTIGATING]
        ]

        if days_until_due is not None:
            cutoff = datetime.now() + timedelta(days=days_until_due)
            pending = [d for d in pending if d.response_due_date <= cutoff]

        return sorted(pending, key=lambda d: d.response_due_date)

    def get_compliance_report(self) -> dict[str, Any]:
        """Generate E-OSCAR compliance report"""
        # Calculate compliance rate (responded within deadline)
        on_time = sum(
            1 for r in self.response_log
            if r["days_to_respond"] <= self.STANDARD_RESPONSE_DAYS
        )
        total = len(self.response_log)

        return {
            "reporting_period": {
                "start": min(
                    (d.received_date for d in self.disputes.values()),
                    default=datetime.now()
                ).isoformat(),
                "end": datetime.now().isoformat(),
            },
            "metrics": {
                "total_disputes_received": self.metrics["total_received"],
                "total_responses_sent": self.metrics["total_responded"],
                "pending_disputes": len(self.get_pending_disputes()),
                "verified_rate": self.metrics["verified"] / max(total, 1) * 100,
                "modified_rate": self.metrics["modified"] / max(total, 1) * 100,
                "deleted_rate": self.metrics["deleted"] / max(total, 1) * 100,
                "avg_response_days": self.metrics["avg_response_days"],
                "on_time_rate": on_time / max(total, 1) * 100,
            },
            "overdue_disputes": [
                {
                    "acdv_id": d.acdv_id,
                    "days_overdue": (datetime.now() - d.response_due_date).days,
                }
                for d in self.get_pending_disputes()
                if d.response_due_date < datetime.now()
            ],
        }

    def _parse_date(self, value: Any) -> date | None:
        """Parse date from various formats"""
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value).date()
            except ValueError:
                return None
        return None

    def _fuzzy_name_match(self, name1: str, name2: str) -> bool:
        """Simple fuzzy name matching"""
        n1 = name1.lower().strip().split()
        n2 = name2.lower().strip().split()

        # Check if at least first and last name match
        if len(n1) >= 2 and len(n2) >= 2:
            return n1[0] == n2[0] and n1[-1] == n2[-1]

        return name1.lower().strip() == name2.lower().strip()


# =============================================================================
# REAL-TIME BRIDGE - THE INNOVATION
# =============================================================================

class RealTimeBridge:
    """
    Real-Time Shadow Bureau -> Metro 2 Bridge

    This is the key innovation that addresses the thesis criticism.
    Traditional bureau reporting has 30-90 day latency. This bridge
    enables near-real-time updates by:

    1. Maintaining a queue of changes from Shadow Bureau
    2. Batching changes efficiently for bureau submission
    3. Supporting frequent update cycles (daily or more)
    4. Handling velocity mismatch between systems

    The "velocity mismatch" problem:
    - Shadow Bureau updates in milliseconds
    - Metro 2 expects monthly batches
    - Solution: Intelligent batching with priority queuing
    """

    def __init__(
        self,
        bridge: Metro2Bridge,
        batch_processor: Metro2BatchProcessor,
        max_batch_size: int = 10000,
        min_batch_interval_hours: int = 4,
    ):
        self.bridge = bridge
        self.batch_processor = batch_processor
        self.max_batch_size = max_batch_size
        self.min_batch_interval = timedelta(hours=min_batch_interval_hours)

        # Change queue with priority
        self.change_queue: list[dict] = []
        self.priority_queue: list[dict] = []  # High-priority changes

        # State tracking
        self.last_batch_time: datetime | None = None
        self.pending_records: dict[str, dict] = {}  # record_id -> latest state

        # Metrics
        self.metrics = {
            "total_changes_received": 0,
            "total_batches_sent": 0,
            "avg_batch_latency_hours": 0.0,
            "records_in_queue": 0,
        }

    def receive_shadow_update(
        self,
        shadow_record: dict[str, Any],
        priority: str = "normal",  # normal, high, immediate
    ) -> None:
        """
        Receive an update from the Shadow Bureau

        Changes are queued for the next batch cycle.
        """
        record_id = shadow_record.get("record_id")

        # Store latest state (deduplication)
        self.pending_records[record_id] = {
            **shadow_record,
            "_received_at": datetime.now().isoformat(),
            "_priority": priority,
        }

        self.metrics["total_changes_received"] += 1
        self.metrics["records_in_queue"] = len(self.pending_records)

        # Immediate priority triggers instant processing
        if priority == "immediate":
            self._process_immediate(shadow_record)

    def _process_immediate(self, record: dict) -> None:
        """Process immediate-priority update (ID theft, major errors)"""
        # Generate single-record incremental file
        batch_info = self.batch_processor.generate_incremental_update(
            [record],
            update_type="correction" if record.get("_is_correction") else "regular"
        )
        logger.info(f"Immediate update processed: {batch_info['batch_id']}")

    def should_batch_now(self) -> bool:
        """Determine if we should send a batch now"""
        # Check minimum interval
        if self.last_batch_time:
            elapsed = datetime.now() - self.last_batch_time
            if elapsed < self.min_batch_interval:
                return False

        # Check queue size
        if len(self.pending_records) >= self.max_batch_size:
            return True

        # Check for high-priority items aging
        high_priority = [
            r for r in self.pending_records.values()
            if r.get("_priority") == "high"
        ]
        if len(high_priority) > 100:  # Configurable threshold
            return True

        # Default: batch every interval
        if self.last_batch_time is None:
            return len(self.pending_records) > 0

        return datetime.now() - self.last_batch_time >= self.min_batch_interval

    def process_batch(self) -> dict[str, Any] | None:
        """
        Process pending changes and generate Metro 2 batch

        Returns batch info or None if no batch needed.
        """
        if not self.pending_records:
            return None

        records = list(self.pending_records.values())

        # Generate incremental update
        batch_info = self.batch_processor.generate_incremental_update(records)

        # Clear processed records
        self.pending_records.clear()

        # Update state
        self.last_batch_time = datetime.now()
        self.metrics["total_batches_sent"] += 1
        self.metrics["records_in_queue"] = 0

        # Calculate latency
        if records:
            latencies = []
            for r in records:
                received = r.get("_received_at")
                if received:
                    delta = datetime.now() - datetime.fromisoformat(received)
                    latencies.append(delta.total_seconds() / 3600)
            if latencies:
                self.metrics["avg_batch_latency_hours"] = sum(latencies) / len(latencies)

        return batch_info

    def get_queue_status(self) -> dict[str, Any]:
        """Get current queue status"""
        records = list(self.pending_records.values())

        priority_counts = defaultdict(int)
        for r in records:
            priority_counts[r.get("_priority", "normal")] += 1

        oldest = None
        if records:
            oldest = min(
                r.get("_received_at", datetime.now().isoformat())
                for r in records
            )

        return {
            "total_pending": len(records),
            "by_priority": dict(priority_counts),
            "oldest_record": oldest,
            "last_batch": self.last_batch_time.isoformat() if self.last_batch_time else None,
            "next_batch_eligible": self.should_batch_now(),
            "metrics": self.metrics,
        }

    def translate_shadow_to_quan(
        self,
        shadow_record: Any,  # MicroDebtRecord from Shadow Bureau
    ) -> dict[str, Any]:
        """
        Translate Shadow Bureau MicroDebtRecord to QUAN format

        Bridge between live_ledger.py types and metro2_bridge.py
        """
        # Handle both dataclass and dict inputs
        if hasattr(shadow_record, "__dict__"):
            record = shadow_record.__dict__.copy()
        else:
            record = dict(shadow_record)

        # Map Shadow Bureau fields to QUAN format
        return {
            "record_id": record.get("record_id"),
            "consumer_id": record.get("consumer_id"),
            "creditor_name": record.get("creditor_name"),
            "original_balance": record.get("original_balance", 0),
            "current_balance": record.get("current_balance", 0),
            "charge_off_date": record.get("charge_off_date"),
            "days_past_due": record.get("days_past_due", 0),
            "collection_status": record.get("collection_status", "active"),
            "resolution_type": record.get("resolution_type"),
            "category": record.get("category"),

            # Consumer info (would come from consumer profile)
            "first_name": record.get("consumer_first_name", ""),
            "last_name": record.get("consumer_last_name", ""),
            "ssn": record.get("consumer_ssn", ""),
            "address_line1": record.get("consumer_address", ""),
            "city": record.get("consumer_city", ""),
            "state": record.get("consumer_state", ""),
            "zip_code": record.get("consumer_zip", ""),

            # Shadow Bureau enrichments
            "shadow_score": record.get("shadow_score"),
            "payment_behavior": record.get("payment_behavior"),
        }


# =============================================================================
# COMPLIANCE VALIDATION
# =============================================================================

class Metro2Validator:
    """
    Metro 2 Format Validation

    Validates records against CDIA specifications to prevent
    bureau rejections.

    Key validation areas:
    - Field format validation
    - Required field presence
    - Date logic validation
    - NCAP compliance (medical debt rules)
    - State-specific rules
    """

    # Required fields for base segment
    REQUIRED_FIELDS = [
        "identification_number",
        "consumer_account_number",
        "account_status",
        "consumer_last_name",
    ]

    # NCAP (National Consumer Assistance Plan) rules
    NCAP_RULES = {
        "medical_debt_minimum_dollars": 500,  # Don't report medical < $500
        "medical_debt_minimum_days": 180,     # Don't report until 180 days past due
        "paid_medical_deletion": True,        # Delete paid medical debts
    }

    def __init__(self):
        self.error_counts: dict[str, int] = defaultdict(int)

    def validate_base_segment(
        self,
        segment: Metro2BaseSegment,
    ) -> list[str]:
        """
        Validate base segment for CDIA compliance

        Returns list of validation errors.
        """
        errors = []

        # Required fields
        if not segment.identification_number:
            errors.append("Missing required field: identification_number")
        if not segment.consumer_account_number:
            errors.append("Missing required field: consumer_account_number")
        if not segment.consumer_last_name:
            errors.append("Missing required field: consumer_last_name")

        # Field length validation
        if len(segment.identification_number) > 10:
            errors.append("identification_number exceeds 10 characters")
        if len(segment.consumer_account_number) > 30:
            errors.append("consumer_account_number exceeds 30 characters")

        # SSN validation (if provided)
        if segment.ssn:
            ssn_clean = re.sub(r'\D', '', segment.ssn)
            if len(ssn_clean) != 9:
                errors.append("Invalid SSN format (must be 9 digits)")
            if ssn_clean in ["000000000", "123456789", "987654321"]:
                errors.append("Invalid SSN (known test/invalid pattern)")

        # Date logic validation
        if segment.date_opened and segment.date_closed:
            if segment.date_closed < segment.date_opened:
                errors.append("date_closed cannot be before date_opened")

        if segment.date_first_delinquency and segment.date_opened:
            if segment.date_first_delinquency < segment.date_opened:
                errors.append("date_first_delinquency cannot be before date_opened")

        # Balance validation
        if segment.current_balance < 0:
            errors.append("current_balance cannot be negative")

        if segment.amount_past_due > segment.current_balance:
            errors.append("amount_past_due cannot exceed current_balance")

        # NCAP medical debt rules
        if segment.debt_category == DebtCategory.MEDICAL:
            ncap_errors = self._validate_ncap_medical(segment)
            errors.extend(ncap_errors)

        # Payment history validation
        if segment.payment_history_profile:
            valid_chars = set("0123456789BDEG L")
            invalid = set(segment.payment_history_profile) - valid_chars
            if invalid:
                errors.append(f"Invalid payment history characters: {invalid}")

        # Track error types
        for err in errors:
            self.error_counts[err.split(":")[0]] += 1

        return errors

    def _validate_ncap_medical(
        self,
        segment: Metro2BaseSegment,
    ) -> list[str]:
        """Validate NCAP rules for medical debt"""
        errors = []

        # Check minimum amount
        if segment.current_balance < self.NCAP_RULES["medical_debt_minimum_dollars"]:
            errors.append(
                f"Medical debt below NCAP minimum (${self.NCAP_RULES['medical_debt_minimum_dollars']})"
            )

        # Check minimum days (180 days before reporting)
        if segment.date_first_delinquency:
            days_since = (date.today() - segment.date_first_delinquency).days
            if days_since < self.NCAP_RULES["medical_debt_minimum_days"]:
                errors.append(
                    f"Medical debt not yet reportable (need {self.NCAP_RULES['medical_debt_minimum_days']} days)"
                )

        # Paid medical debts should be deleted
        if segment.account_status in [AccountStatus.PAID_COLLECTION, AccountStatus.PAID_FULL]:
            if self.NCAP_RULES["paid_medical_deletion"]:
                errors.append("Paid medical debt should be deleted per NCAP")

        return errors

    def validate_file(
        self,
        content: str,
    ) -> dict[str, Any]:
        """
        Validate entire Metro 2 file

        Returns validation report.
        """
        lines = content.strip().split("\n")

        report = {
            "total_lines": len(lines),
            "header_valid": False,
            "trailer_valid": False,
            "record_errors": [],
            "summary": {},
        }

        if not lines:
            report["summary"]["error"] = "Empty file"
            return report

        # Check header
        header_line = lines[0]
        if "HEADER" in header_line[:10]:
            report["header_valid"] = True

        # Check trailer
        trailer_line = lines[-1]
        if "TRAILER" in trailer_line[:10]:
            report["trailer_valid"] = True

        # Validate each base segment
        for i, line in enumerate(lines[1:-1], start=2):
            if len(line) < 426:
                report["record_errors"].append({
                    "line": i,
                    "error": f"Line too short: {len(line)} < 426",
                })

        report["summary"] = {
            "valid_records": len(lines) - 2 - len(report["record_errors"]),
            "invalid_records": len(report["record_errors"]),
            "error_rate": len(report["record_errors"]) / max(len(lines) - 2, 1) * 100,
        }

        return report

    def get_error_summary(self) -> dict[str, int]:
        """Get summary of validation errors encountered"""
        return dict(self.error_counts)


# =============================================================================
# REPORTING ANALYTICS
# =============================================================================

class ReportingAnalytics:
    """
    Reporting Analytics for Metro 2 Operations

    Tracks:
    - Reporting status by account
    - Bureau acceptance rates
    - Dispute rates
    - Data quality metrics
    """

    def __init__(self):
        # Account-level tracking
        self.account_status: dict[str, dict] = {}

        # Bureau-level tracking
        self.bureau_metrics: dict[str, dict] = {
            "EFX": {"submitted": 0, "accepted": 0, "rejected": 0},
            "EXP": {"submitted": 0, "accepted": 0, "rejected": 0},
            "TUC": {"submitted": 0, "accepted": 0, "rejected": 0},
        }

        # Quality metrics
        self.quality_metrics = {
            "total_reported": 0,
            "total_disputes": 0,
            "validation_failures": 0,
            "data_completeness": 100.0,
        }

    def track_submission(
        self,
        record_id: str,
        bureau: str,
        accepted: bool,
        rejection_reason: str | None = None,
    ) -> None:
        """Track a submission to a credit bureau"""
        # Update account status
        if record_id not in self.account_status:
            self.account_status[record_id] = {
                "first_reported": datetime.now().isoformat(),
                "last_reported": None,
                "bureaus_reported": [],
                "rejections": [],
                "disputes": 0,
            }

        status = self.account_status[record_id]
        status["last_reported"] = datetime.now().isoformat()

        if bureau not in status["bureaus_reported"]:
            status["bureaus_reported"].append(bureau)

        if not accepted and rejection_reason:
            status["rejections"].append({
                "bureau": bureau,
                "reason": rejection_reason,
                "date": datetime.now().isoformat(),
            })

        # Update bureau metrics
        if bureau in self.bureau_metrics:
            self.bureau_metrics[bureau]["submitted"] += 1
            if accepted:
                self.bureau_metrics[bureau]["accepted"] += 1
            else:
                self.bureau_metrics[bureau]["rejected"] += 1

        self.quality_metrics["total_reported"] += 1

    def track_dispute(
        self,
        record_id: str,
        bureau: str,
        dispute_type: str,
    ) -> None:
        """Track a dispute received"""
        if record_id in self.account_status:
            self.account_status[record_id]["disputes"] += 1

        self.quality_metrics["total_disputes"] += 1

    def get_account_report(self, record_id: str) -> dict | None:
        """Get reporting status for a specific account"""
        return self.account_status.get(record_id)

    def get_bureau_acceptance_rates(self) -> dict[str, float]:
        """Get acceptance rate by bureau"""
        rates = {}
        for bureau, metrics in self.bureau_metrics.items():
            total = metrics["submitted"]
            if total > 0:
                rates[bureau] = metrics["accepted"] / total * 100
            else:
                rates[bureau] = 100.0
        return rates

    def get_dispute_rate(self) -> float:
        """Get overall dispute rate"""
        total = self.quality_metrics["total_reported"]
        disputes = self.quality_metrics["total_disputes"]
        if total > 0:
            return disputes / total * 100
        return 0.0

    def get_quality_dashboard(self) -> dict[str, Any]:
        """Get comprehensive quality dashboard"""
        acceptance_rates = self.get_bureau_acceptance_rates()

        return {
            "summary": {
                "total_accounts_tracked": len(self.account_status),
                "total_submissions": self.quality_metrics["total_reported"],
                "total_disputes": self.quality_metrics["total_disputes"],
                "dispute_rate": f"{self.get_dispute_rate():.2f}%",
            },
            "bureau_metrics": {
                bureau: {
                    "submitted": m["submitted"],
                    "accepted": m["accepted"],
                    "rejected": m["rejected"],
                    "acceptance_rate": f"{acceptance_rates.get(bureau, 100):.1f}%",
                }
                for bureau, m in self.bureau_metrics.items()
            },
            "data_quality": {
                "completeness": f"{self.quality_metrics['data_completeness']:.1f}%",
                "validation_failures": self.quality_metrics["validation_failures"],
            },
            "top_rejection_reasons": self._get_top_rejections(),
        }

    def _get_top_rejections(self, limit: int = 5) -> list[dict]:
        """Get most common rejection reasons"""
        reasons: dict[str, int] = defaultdict(int)

        for status in self.account_status.values():
            for rejection in status.get("rejections", []):
                reasons[rejection["reason"]] += 1

        sorted_reasons = sorted(reasons.items(), key=lambda x: x[1], reverse=True)

        return [
            {"reason": r, "count": c}
            for r, c in sorted_reasons[:limit]
        ]


# =============================================================================
# WORKING DEMO
# =============================================================================

def demo_metro2_generation():
    """
    Working demo that takes a QUAN debt record and generates valid Metro 2 output
    """
    print("=" * 70)
    print("METRO 2 CREDIT BUREAU BRIDGE - DEMONSTRATION")
    print("Bridging Shadow Bureau Data to Legacy Bureau Format")
    print("=" * 70)
    print()

    # Initialize the bridge
    bridge = Metro2Bridge(
        subscriber_id="QUAN123456",
        subscriber_name="QUAN RECOVERY LLC",
        subscriber_address="123 Collection Ave",
        subscriber_city="San Francisco",
        subscriber_state="CA",
        subscriber_zip="94105",
        subscriber_phone="4155551234",
    )

    # Sample QUAN debt records (simulating Shadow Bureau data)
    quan_records = [
        {
            "record_id": "REC001",
            "consumer_id": "C001",
            "creditor_name": "Klarna",
            "original_balance": 147.50,
            "current_balance": 147.50,
            "charge_off_date": datetime(2025, 6, 15),
            "days_past_due": 180,
            "collection_status": "active",
            "category": DebtCategory.BNPL,
            "first_name": "John",
            "last_name": "Smith",
            "ssn": "458923176",  # Valid format SSN for demo
            "date_of_birth": date(1990, 5, 15),
            "address_line1": "456 Consumer St",
            "city": "Oakland",
            "state": "CA",
            "zip_code": "94612",
            "phone": "5105551234",
            "shadow_score": 520,
        },
        {
            "record_id": "REC002",
            "consumer_id": "C002",
            "creditor_name": "Netflix",
            "original_balance": 45.97,
            "current_balance": 0,
            "charge_off_date": datetime(2025, 3, 1),
            "days_past_due": 90,
            "collection_status": "resolved",
            "resolution_type": "paid_full",
            "category": DebtCategory.SUBSCRIPTION,
            "first_name": "Jane",
            "last_name": "Doe",
            "ssn": "371824956",  # Valid format SSN for demo
            "date_of_birth": date(1985, 8, 22),
            "address_line1": "789 Debtor Ave",
            "city": "Berkeley",
            "state": "CA",
            "zip_code": "94702",
            "phone": "5105559876",
            "shadow_score": 680,
        },
        {
            "record_id": "REC003",
            "consumer_id": "C003",
            "creditor_name": "Uber",
            "original_balance": 75.00,
            "current_balance": 45.00,
            "charge_off_date": datetime(2025, 8, 10),
            "days_past_due": 120,
            "collection_status": "active",
            "category": DebtCategory.GIG_ADVANCE,
            "first_name": "Robert",
            "last_name": "Johnson",
            "ssn": "529147836",  # Valid format SSN for demo
            "date_of_birth": date(1992, 12, 3),
            "address_line1": "321 Gig Lane",
            "city": "San Jose",
            "state": "CA",
            "zip_code": "95112",
            "phone": "4085551111",
            "shadow_score": 450,
            "payment_history": [
                {"date": datetime(2025, 11, 1), "days_late": 120},
                {"date": datetime(2025, 10, 1), "days_late": 90},
                {"date": datetime(2025, 9, 1), "days_late": 60},
            ],
        },
    ]

    print("1. TRADE LINE MAPPING")
    print("-" * 40)
    for record in quan_records:
        category = record.get("category", DebtCategory.OTHER)
        if isinstance(category, str):
            category = DebtCategory(category)
        account_type = TradeLineMapper.get_account_type(category)
        portfolio_type = TradeLineMapper.get_portfolio_type(category)
        print(f"  {record['creditor_name']:15} -> Category: {category.value:12} "
              f"-> Account Type: {account_type.value} Portfolio: {portfolio_type.value}")
    print()

    print("2. INDIVIDUAL RECORD TRANSLATION")
    print("-" * 40)
    for i, record in enumerate(quan_records[:1], 1):  # Show first record in detail
        base_segment, additional_segments, errors = bridge.translate_quan_record(record)

        print(f"  Record: {record['record_id']}")
        print(f"  Consumer: {base_segment.consumer_first_name} {base_segment.consumer_last_name}")
        print(f"  Creditor: {record['creditor_name']}")
        print(f"  Balance: ${base_segment.current_balance}")
        print(f"  Account Status: {base_segment.account_status.value} ({base_segment.account_status.name})")
        print(f"  Payment Rating: {base_segment.payment_rating.value}")
        print(f"  Special Comment: {base_segment.special_comment.value or 'None'}")
        print(f"  K Segment (Original Creditor): {'Yes' if additional_segments else 'No'}")
        if errors:
            print(f"  Validation Errors: {errors}")
        else:
            print(f"  Validation: PASSED")
        print()

        # Show raw Metro 2 output (first 100 chars)
        raw_output = base_segment.to_fixed_width()
        print(f"  Raw Metro 2 (first 100 chars):")
        print(f"  {raw_output[:100]}...")
        print()

    print("3. FULL FILE GENERATION")
    print("-" * 40)
    content = bridge.generate_metro2_file(quan_records)
    lines = content.split("\n")
    print(f"  Total Lines: {len(lines)}")
    print(f"  Header: {lines[0][:50]}...")
    print(f"  Trailer: {lines[-1][:50]}...")
    print(f"  File Size: {len(content)} bytes")
    print()

    print("4. VALIDATION STATISTICS")
    print("-" * 40)
    print(f"  Records Processed: {bridge.stats['records_processed']}")
    print(f"  Valid Records: {bridge.stats['records_valid']}")
    print(f"  Invalid Records: {bridge.stats['records_invalid']}")
    if bridge.stats['validation_errors']:
        print(f"  Error Breakdown:")
        for error, count in bridge.stats['validation_errors'].items():
            print(f"    - {error}: {count}")
    print()

    print("5. E-OSCAR DISPUTE DEMO")
    print("-" * 40)
    eoscar = EOscarIntegration("QUAN123456", bridge)

    # Simulate receiving a dispute
    acdv = eoscar.receive_acdv({
        "control_number": "CTRL001",
        "bureau": "EFX",
        "consumer_name": "John Smith",
        "consumer_ssn": "458923176",
        "account_number": "REC001",
        "dispute_code": "004",  # Wrong balance
        "dispute_narrative": "Consumer claims balance is incorrect",
    })
    print(f"  ACDV Received: {acdv.acdv_id}")
    print(f"  Dispute Code: {acdv.dispute_code} ({EOscarIntegration.DISPUTE_CODES.get(acdv.dispute_code)})")
    print(f"  Response Due: {acdv.response_due_date.strftime('%Y-%m-%d')}")

    # Investigate
    findings = eoscar.investigate_dispute(acdv.acdv_id, quan_records[0])
    print(f"  Investigation Finding: {findings['findings']}")
    print(f"  Recommended Response: {findings['recommended_response']}")

    # Generate response
    response = eoscar.generate_response(
        acdv.acdv_id,
        findings['recommended_response'],
        narrative="Balance verified against original creditor records"
    )
    print(f"  Response Sent: {response.response_code}")
    print()

    print("6. REAL-TIME BRIDGE DEMO")
    print("-" * 40)
    batch_processor = Metro2BatchProcessor(bridge)
    realtime_bridge = RealTimeBridge(bridge, batch_processor)

    # Simulate Shadow Bureau updates
    for record in quan_records:
        realtime_bridge.receive_shadow_update(record, priority="normal")

    status = realtime_bridge.get_queue_status()
    print(f"  Pending Updates: {status['total_pending']}")
    print(f"  By Priority: {status['by_priority']}")
    print(f"  Batch Eligible: {status['next_batch_eligible']}")
    print()

    print("7. REPORTING ANALYTICS")
    print("-" * 40)
    analytics = ReportingAnalytics()

    # Simulate submissions
    for record in quan_records:
        for bureau in ["EFX", "EXP", "TUC"]:
            analytics.track_submission(record["record_id"], bureau, accepted=True)

    # Simulate a dispute
    analytics.track_dispute("REC001", "EFX", "balance")

    dashboard = analytics.get_quality_dashboard()
    print(f"  Total Accounts: {dashboard['summary']['total_accounts_tracked']}")
    print(f"  Total Submissions: {dashboard['summary']['total_submissions']}")
    print(f"  Dispute Rate: {dashboard['summary']['dispute_rate']}")
    print(f"  Bureau Acceptance Rates:")
    for bureau, metrics in dashboard['bureau_metrics'].items():
        print(f"    {bureau}: {metrics['acceptance_rate']}")
    print()

    print("=" * 70)
    print("DEMO COMPLETE - Metro 2 Bridge Successfully Demonstrated")
    print("=" * 70)

    return content


# Run demo if executed directly
if __name__ == "__main__":
    demo_metro2_generation()
