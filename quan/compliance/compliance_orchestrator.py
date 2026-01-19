"""
Compliance Orchestration System

A comprehensive compliance layer that makes non-compliance technically impossible
while minimizing friction for valid contacts. Handles FDCPA, Regulation F, TCPA,
state-specific rules, consent management, audit trails, disputes, and licensing.
"""

import asyncio
import hashlib
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time, date
from decimal import Decimal
from enum import Enum, auto
from typing import (
    Dict, List, Optional, Any, Set, Tuple, Callable,
    Protocol, TypeVar, Generic, Union
)
import logging
import re
from collections import defaultdict
from functools import wraps
import copy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class ComplianceStatus(Enum):
    """Compliance check result status"""
    COMPLIANT = "compliant"
    WARNING = "warning"
    VIOLATION = "violation"
    BLOCKED = "blocked"
    PENDING_REVIEW = "pending_review"


class ContactChannel(Enum):
    """Communication channels"""
    PHONE_LIVE = "phone_live"
    PHONE_AUTO = "phone_auto"
    VOICEMAIL = "voicemail"
    SMS = "sms"
    EMAIL = "email"
    LETTER = "letter"
    PORTAL = "portal"
    IN_PERSON = "in_person"


class RuleCategory(Enum):
    """Categories of compliance rules"""
    FDCPA = "fdcpa"
    REGULATION_F = "regulation_f"
    TCPA = "tcpa"
    STATE_SPECIFIC = "state_specific"
    SCRA = "scra"
    BANKRUPTCY = "bankruptcy"
    LICENSING = "licensing"
    INTERNAL = "internal"


class DisputeType(Enum):
    """Types of disputes"""
    DEBT_NOT_OWED = "debt_not_owed"
    WRONG_AMOUNT = "wrong_amount"
    WRONG_PERSON = "wrong_person"
    PAID_IN_FULL = "paid_in_full"
    IDENTITY_THEFT = "identity_theft"
    STATUTE_OF_LIMITATIONS = "statute_of_limitations"
    OTHER = "other"


class DisputeStatus(Enum):
    """Dispute resolution status"""
    RECEIVED = "received"
    UNDER_INVESTIGATION = "under_investigation"
    PENDING_DOCUMENTATION = "pending_documentation"
    RESOLVED_VALID = "resolved_valid"
    RESOLVED_INVALID = "resolved_invalid"
    ESCALATED = "escalated"
    CLOSED = "closed"


class ConsentType(Enum):
    """Types of consent"""
    EXPRESS_WRITTEN = "express_written"
    EXPRESS_ORAL = "express_oral"
    IMPLIED = "implied"
    TRANSACTIONAL = "transactional"


class ConsentStatus(Enum):
    """Consent status"""
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    PENDING_VERIFICATION = "pending_verification"


class LicenseStatus(Enum):
    """License status"""
    ACTIVE = "active"
    PENDING = "pending"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"
    NOT_REQUIRED = "not_required"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ValidationResult:
    """Result of a compliance validation"""
    validation_id: str
    timestamp: datetime
    status: ComplianceStatus
    rule_category: RuleCategory
    rule_id: str
    rule_name: str
    account_id: str
    channel: Optional[ContactChannel]
    details: str
    blocking_reason: Optional[str] = None
    remediation: Optional[str] = None
    alternatives: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "rule_category": self.rule_category.value,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "account_id": self.account_id,
            "channel": self.channel.value if self.channel else None,
            "details": self.details,
            "blocking_reason": self.blocking_reason,
            "remediation": self.remediation,
            "alternatives": self.alternatives,
            "metadata": self.metadata
        }


@dataclass
class ContactAttempt:
    """Record of a contact attempt"""
    attempt_id: str
    account_id: str
    channel: ContactChannel
    timestamp: datetime
    timezone: str
    conversation_occurred: bool
    duration_seconds: Optional[int] = None
    outcome: Optional[str] = None
    agent_id: Optional[str] = None
    validation_id: Optional[str] = None


@dataclass
class ConsentRecord:
    """Record of consent"""
    consent_id: str
    account_id: str
    channel: ContactChannel
    consent_type: ConsentType
    status: ConsentStatus
    granted_at: datetime
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    source: str
    evidence_ref: Optional[str] = None
    ip_address: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DisputeRecord:
    """Record of a dispute"""
    dispute_id: str
    account_id: str
    dispute_type: DisputeType
    status: DisputeStatus
    received_date: datetime
    description: str
    evidence_provided: List[str] = field(default_factory=list)
    resolution_date: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    cfpb_complaint_id: Optional[str] = None
    assigned_to: Optional[str] = None
    deadline: Optional[datetime] = None


@dataclass
class LicenseRecord:
    """State licensing record"""
    license_id: str
    state: str
    license_number: str
    license_type: str
    status: LicenseStatus
    issued_date: datetime
    expiration_date: datetime
    bond_amount: Optional[Decimal] = None
    bond_expiration: Optional[datetime] = None
    restrictions: List[str] = field(default_factory=list)
    renewal_reminder_sent: bool = False


@dataclass
class AuditEntry:
    """Immutable audit log entry"""
    entry_id: str
    timestamp: datetime
    event_type: str
    account_id: Optional[str]
    user_id: Optional[str]
    action: str
    details: Dict[str, Any]
    validation_results: List[ValidationResult]
    outcome: str
    checksum: str  # For integrity verification

    def compute_checksum(self) -> str:
        """Compute integrity checksum"""
        data = f"{self.entry_id}{self.timestamp.isoformat()}{self.event_type}"
        data += f"{self.account_id}{self.action}{json.dumps(self.details, sort_keys=True)}"
        return hashlib.sha256(data.encode()).hexdigest()


# =============================================================================
# STATE-SPECIFIC RULES DATABASE
# =============================================================================

STATE_RULES_DATABASE: Dict[str, Dict[str, Any]] = {
    "AL": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "AK": {"sol_years": 3, "requires_license": False, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "AZ": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "AR": {"sol_years": 5, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "CA": {"sol_years": 4, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21,
           "additional_disclosures": ["CA Civil Code 1788.52"], "restrict_time_barred_suits": True},
    "CO": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "CT": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21,
           "additional_disclosures": ["CT consumer protection notice"]},
    "DE": {"sol_years": 3, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "FL": {"sol_years": 5, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21,
           "fccpa_applies": True},
    "GA": {"sol_years": 6, "requires_license": False, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "HI": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "ID": {"sol_years": 5, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "IL": {"sol_years": 5, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "IN": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "IA": {"sol_years": 5, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "KS": {"sol_years": 5, "requires_license": False, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "KY": {"sol_years": 5, "requires_license": False, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "LA": {"sol_years": 3, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "ME": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "MD": {"sol_years": 3, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21,
           "additional_disclosures": ["MD collection agency notice"]},
    "MA": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21,
           "additional_disclosures": ["MA 93A notice"]},
    "MI": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "MN": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "MS": {"sol_years": 3, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "MO": {"sol_years": 5, "requires_license": False, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "MT": {"sol_years": 5, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "NE": {"sol_years": 5, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "NV": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "NH": {"sol_years": 3, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "NJ": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "NM": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "NY": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21,
           "additional_disclosures": ["NY City DCA notice"], "restrict_time_barred_suits": True},
    "NC": {"sol_years": 3, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "ND": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "OH": {"sol_years": 6, "requires_license": False, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "OK": {"sol_years": 5, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "OR": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "PA": {"sol_years": 4, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "RI": {"sol_years": 10, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "SC": {"sol_years": 3, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "SD": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "TN": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "TX": {"sol_years": 4, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21,
           "additional_disclosures": ["TX Finance Code notice"]},
    "UT": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "VT": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "VA": {"sol_years": 5, "requires_license": False, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "WA": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "WV": {"sol_years": 10, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "WI": {"sol_years": 6, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "WY": {"sol_years": 8, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
    "DC": {"sol_years": 3, "requires_license": True, "mini_miranda_required": True, "calling_hours_start": 8, "calling_hours_end": 21},
}

# Timezone mapping for states
STATE_TIMEZONES: Dict[str, str] = {
    "AL": "America/Chicago", "AK": "America/Anchorage", "AZ": "America/Phoenix",
    "AR": "America/Chicago", "CA": "America/Los_Angeles", "CO": "America/Denver",
    "CT": "America/New_York", "DE": "America/New_York", "FL": "America/New_York",
    "GA": "America/New_York", "HI": "Pacific/Honolulu", "ID": "America/Boise",
    "IL": "America/Chicago", "IN": "America/Indiana/Indianapolis", "IA": "America/Chicago",
    "KS": "America/Chicago", "KY": "America/Kentucky/Louisville", "LA": "America/Chicago",
    "ME": "America/New_York", "MD": "America/New_York", "MA": "America/New_York",
    "MI": "America/Detroit", "MN": "America/Chicago", "MS": "America/Chicago",
    "MO": "America/Chicago", "MT": "America/Denver", "NE": "America/Chicago",
    "NV": "America/Los_Angeles", "NH": "America/New_York", "NJ": "America/New_York",
    "NM": "America/Denver", "NY": "America/New_York", "NC": "America/New_York",
    "ND": "America/Chicago", "OH": "America/New_York", "OK": "America/Chicago",
    "OR": "America/Los_Angeles", "PA": "America/New_York", "RI": "America/New_York",
    "SC": "America/New_York", "SD": "America/Chicago", "TN": "America/Chicago",
    "TX": "America/Chicago", "UT": "America/Denver", "VT": "America/New_York",
    "VA": "America/New_York", "WA": "America/Los_Angeles", "WV": "America/New_York",
    "WI": "America/Chicago", "WY": "America/Denver", "DC": "America/New_York",
}


# =============================================================================
# RULE ENGINE - ABSTRACT BASE AND IMPLEMENTATIONS
# =============================================================================

class ComplianceRule(ABC):
    """Abstract base class for compliance rules"""

    def __init__(self, rule_id: str, rule_name: str, category: RuleCategory):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.category = category
        self.enabled = True
        self.effective_date: Optional[datetime] = None
        self.expiration_date: Optional[datetime] = None

    @abstractmethod
    async def validate(
        self,
        account: Dict[str, Any],
        channel: Optional[ContactChannel],
        context: Dict[str, Any]
    ) -> ValidationResult:
        """Validate compliance for this rule"""
        pass

    def is_active(self) -> bool:
        """Check if rule is currently active"""
        if not self.enabled:
            return False
        now = datetime.utcnow()
        if self.effective_date and now < self.effective_date:
            return False
        if self.expiration_date and now > self.expiration_date:
            return False
        return True

    def _create_result(
        self,
        status: ComplianceStatus,
        account_id: str,
        channel: Optional[ContactChannel],
        details: str,
        blocking_reason: Optional[str] = None,
        remediation: Optional[str] = None,
        alternatives: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> ValidationResult:
        """Helper to create validation result"""
        return ValidationResult(
            validation_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            status=status,
            rule_category=self.category,
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            account_id=account_id,
            channel=channel,
            details=details,
            blocking_reason=blocking_reason,
            remediation=remediation,
            alternatives=alternatives or [],
            metadata=metadata or {}
        )


class FDCPATimingRule(ComplianceRule):
    """FDCPA calling hours rule (8am-9pm local time)"""

    def __init__(self):
        super().__init__(
            rule_id="FDCPA-001",
            rule_name="FDCPA Calling Hours",
            category=RuleCategory.FDCPA
        )

    async def validate(
        self,
        account: Dict[str, Any],
        channel: Optional[ContactChannel],
        context: Dict[str, Any]
    ) -> ValidationResult:
        # Only applies to phone/voicemail
        if channel not in [ContactChannel.PHONE_LIVE, ContactChannel.PHONE_AUTO, ContactChannel.VOICEMAIL]:
            return self._create_result(
                ComplianceStatus.COMPLIANT,
                account.get("account_id", ""),
                channel,
                "Rule not applicable to this channel"
            )

        state = account.get("debtor_state", "NY")
        state_rules = STATE_RULES_DATABASE.get(state, STATE_RULES_DATABASE["NY"])

        # Get current local time (simplified calculation)
        current_time = context.get("current_time", datetime.utcnow())
        tz_offsets = {
            "America/New_York": -5, "America/Chicago": -6,
            "America/Denver": -7, "America/Los_Angeles": -8,
            "America/Phoenix": -7, "America/Anchorage": -9,
            "Pacific/Honolulu": -10, "America/Boise": -7,
            "America/Indiana/Indianapolis": -5, "America/Kentucky/Louisville": -5,
            "America/Detroit": -5
        }

        tz_name = STATE_TIMEZONES.get(state, "America/New_York")
        offset = tz_offsets.get(tz_name, -5)
        local_hour = (current_time.hour + offset) % 24

        start_hour = state_rules.get("calling_hours_start", 8)
        end_hour = state_rules.get("calling_hours_end", 21)

        if local_hour < start_hour or local_hour >= end_hour:
            return self._create_result(
                ComplianceStatus.BLOCKED,
                account.get("account_id", ""),
                channel,
                f"Outside calling hours. Local time ~{local_hour}:00 in {state}",
                blocking_reason=f"FDCPA: Calls prohibited before {start_hour}am or after {end_hour-12}pm local time",
                remediation=f"Schedule contact for {start_hour}am-{end_hour-12}pm {state} time",
                alternatives=["email", "letter", "portal"],
                metadata={"local_hour": local_hour, "state": state}
            )

        return self._create_result(
            ComplianceStatus.COMPLIANT,
            account.get("account_id", ""),
            channel,
            f"Within calling hours ({local_hour}:00 local)"
        )


class FDCPAContentRule(ComplianceRule):
    """FDCPA prohibited and required content validation"""

    PROHIBITED_TERMS = [
        r"\barrest\b", r"\bjail\b", r"\bprison\b", r"\bcriminal\b",
        r"\bgarnish\b", r"\bseize\b", r"\bfreeze.*account\b",
        r"\breport.*police\b", r"\bsue\b", r"\blawsuit\b"
    ]

    REQUIRED_DISCLOSURES = {
        "mini_miranda": [
            r"debt collector",
            r"attempt.*(collect|collecting).*debt"
        ],
        "validation_notice": [
            r"30 days",
            r"dispute",
            r"validation"
        ]
    }

    def __init__(self):
        super().__init__(
            rule_id="FDCPA-002",
            rule_name="FDCPA Content Requirements",
            category=RuleCategory.FDCPA
        )

    async def validate(
        self,
        account: Dict[str, Any],
        channel: Optional[ContactChannel],
        context: Dict[str, Any]
    ) -> ValidationResult:
        message_content = context.get("message_content", "")
        is_initial_contact = context.get("is_initial_contact", False)

        if not message_content:
            return self._create_result(
                ComplianceStatus.COMPLIANT,
                account.get("account_id", ""),
                channel,
                "No message content to validate"
            )

        violations = []

        # Check prohibited terms
        for pattern in self.PROHIBITED_TERMS:
            if re.search(pattern, message_content, re.IGNORECASE):
                violations.append(f"Prohibited term detected: {pattern}")

        # Check required disclosures for initial contact
        if is_initial_contact:
            message_lower = message_content.lower()
            for disclosure_name, patterns in self.REQUIRED_DISCLOSURES.items():
                found = any(re.search(p, message_lower) for p in patterns)
                if not found:
                    violations.append(f"Missing required disclosure: {disclosure_name}")

        if violations:
            return self._create_result(
                ComplianceStatus.BLOCKED,
                account.get("account_id", ""),
                channel,
                f"Content violations found: {len(violations)}",
                blocking_reason="; ".join(violations),
                remediation="Review and revise message content",
                metadata={"violations": violations}
            )

        return self._create_result(
            ComplianceStatus.COMPLIANT,
            account.get("account_id", ""),
            channel,
            "Message content compliant"
        )


class RegulationF7in7Rule(ComplianceRule):
    """Regulation F 7-in-7 rule: max 7 call attempts per 7 days"""

    def __init__(self, contact_tracker: 'ContactFrequencyManager'):
        super().__init__(
            rule_id="REGF-001",
            rule_name="Regulation F 7-in-7 Rule",
            category=RuleCategory.REGULATION_F
        )
        self.contact_tracker = contact_tracker

    async def validate(
        self,
        account: Dict[str, Any],
        channel: Optional[ContactChannel],
        context: Dict[str, Any]
    ) -> ValidationResult:
        # Only applies to phone channels
        if channel not in [ContactChannel.PHONE_LIVE, ContactChannel.PHONE_AUTO]:
            return self._create_result(
                ComplianceStatus.COMPLIANT,
                account.get("account_id", ""),
                channel,
                "7-in-7 rule not applicable to this channel"
            )

        account_id = account.get("account_id", "")
        phone_number = account.get("phone_number", "")

        # Get attempts in rolling 7-day window
        attempts = await self.contact_tracker.get_attempts_in_window(
            account_id=account_id,
            phone_number=phone_number,
            channels=[ContactChannel.PHONE_LIVE, ContactChannel.PHONE_AUTO],
            days=7
        )

        if attempts >= 7:
            next_allowed = await self.contact_tracker.get_next_allowed_time(
                account_id=account_id,
                phone_number=phone_number,
                channels=[ContactChannel.PHONE_LIVE, ContactChannel.PHONE_AUTO]
            )
            return self._create_result(
                ComplianceStatus.BLOCKED,
                account_id,
                channel,
                f"7-in-7 limit reached: {attempts} attempts in past 7 days",
                blocking_reason="Regulation F: Maximum 7 telephone calls per 7-day period",
                remediation=f"Wait until {next_allowed.strftime('%Y-%m-%d %H:%M')} or use alternative channel",
                alternatives=["email", "sms", "letter"],
                metadata={"attempts": attempts, "next_allowed": next_allowed.isoformat()}
            )

        return self._create_result(
            ComplianceStatus.COMPLIANT,
            account_id,
            channel,
            f"Within 7-in-7 limit: {attempts}/7 attempts used",
            metadata={"attempts": attempts, "remaining": 7 - attempts}
        )


class RegulationFConversationRule(ComplianceRule):
    """Regulation F: Only 1 conversation per day after contact"""

    def __init__(self, contact_tracker: 'ContactFrequencyManager'):
        super().__init__(
            rule_id="REGF-002",
            rule_name="Regulation F Daily Conversation Limit",
            category=RuleCategory.REGULATION_F
        )
        self.contact_tracker = contact_tracker

    async def validate(
        self,
        account: Dict[str, Any],
        channel: Optional[ContactChannel],
        context: Dict[str, Any]
    ) -> ValidationResult:
        if channel not in [ContactChannel.PHONE_LIVE, ContactChannel.PHONE_AUTO]:
            return self._create_result(
                ComplianceStatus.COMPLIANT,
                account.get("account_id", ""),
                channel,
                "Conversation limit not applicable"
            )

        account_id = account.get("account_id", "")

        conversations_today = await self.contact_tracker.get_conversations_today(account_id)

        if conversations_today >= 1:
            return self._create_result(
                ComplianceStatus.BLOCKED,
                account_id,
                channel,
                f"Daily conversation limit reached: {conversations_today}",
                blocking_reason="Regulation F: No additional calls after conversation on same day",
                remediation="Wait until tomorrow or use alternative channel",
                alternatives=["email", "sms", "letter"]
            )

        return self._create_result(
            ComplianceStatus.COMPLIANT,
            account_id,
            channel,
            "No conversation yet today"
        )


class TCPAConsentRule(ComplianceRule):
    """TCPA consent requirements for automated communications"""

    def __init__(self, consent_manager: 'ConsentManager'):
        super().__init__(
            rule_id="TCPA-001",
            rule_name="TCPA Consent Requirement",
            category=RuleCategory.TCPA
        )
        self.consent_manager = consent_manager

    async def validate(
        self,
        account: Dict[str, Any],
        channel: Optional[ContactChannel],
        context: Dict[str, Any]
    ) -> ValidationResult:
        # TCPA consent required for autodialed calls and SMS
        requires_consent = channel in [
            ContactChannel.PHONE_AUTO,
            ContactChannel.SMS,
            ContactChannel.VOICEMAIL
        ]

        if not requires_consent:
            return self._create_result(
                ComplianceStatus.COMPLIANT,
                account.get("account_id", ""),
                channel,
                "TCPA consent not required for this channel"
            )

        account_id = account.get("account_id", "")
        has_consent = await self.consent_manager.has_valid_consent(
            account_id=account_id,
            channel=channel
        )

        if not has_consent:
            consent_type = "express written" if channel == ContactChannel.SMS else "prior express"
            return self._create_result(
                ComplianceStatus.BLOCKED,
                account_id,
                channel,
                f"No valid {consent_type} consent for {channel.value}",
                blocking_reason=f"TCPA: {consent_type} consent required for automated {channel.value}",
                remediation="Obtain consent or use manual dialing/mail",
                alternatives=["phone_live", "letter", "email"],
                metadata={"consent_required": consent_type}
            )

        return self._create_result(
            ComplianceStatus.COMPLIANT,
            account_id,
            channel,
            f"Valid consent on file for {channel.value}"
        )


class TCPADoNotCallRule(ComplianceRule):
    """TCPA Do-Not-Call list compliance"""

    def __init__(self, consent_manager: 'ConsentManager'):
        super().__init__(
            rule_id="TCPA-002",
            rule_name="TCPA Do-Not-Call",
            category=RuleCategory.TCPA
        )
        self.consent_manager = consent_manager

    async def validate(
        self,
        account: Dict[str, Any],
        channel: Optional[ContactChannel],
        context: Dict[str, Any]
    ) -> ValidationResult:
        if channel not in [ContactChannel.PHONE_LIVE, ContactChannel.PHONE_AUTO, ContactChannel.SMS]:
            return self._create_result(
                ComplianceStatus.COMPLIANT,
                account.get("account_id", ""),
                channel,
                "DNC not applicable to this channel"
            )

        account_id = account.get("account_id", "")
        phone_number = account.get("phone_number", "")

        is_on_dnc = await self.consent_manager.is_on_do_not_call(account_id, phone_number)

        if is_on_dnc:
            return self._create_result(
                ComplianceStatus.BLOCKED,
                account_id,
                channel,
                "Number on Do-Not-Call list",
                blocking_reason="TCPA: Number registered on DNC list",
                remediation="Use mail for required communications only",
                alternatives=["letter"]
            )

        return self._create_result(
            ComplianceStatus.COMPLIANT,
            account_id,
            channel,
            "Number not on DNC list"
        )


class CeaseAndDesistRule(ComplianceRule):
    """Cease and desist compliance"""

    def __init__(self, dispute_handler: 'DisputeHandler'):
        super().__init__(
            rule_id="FDCPA-003",
            rule_name="Cease and Desist Compliance",
            category=RuleCategory.FDCPA
        )
        self.dispute_handler = dispute_handler

    async def validate(
        self,
        account: Dict[str, Any],
        channel: Optional[ContactChannel],
        context: Dict[str, Any]
    ) -> ValidationResult:
        account_id = account.get("account_id", "")

        cease_status = await self.dispute_handler.get_cease_desist_status(account_id)

        if cease_status.get("active"):
            # Determine allowed communications
            allowed_channels = [ContactChannel.LETTER]
            allowed_purposes = ["legal_notice", "final_notice", "lawsuit_filing"]

            purpose = context.get("contact_purpose", "collection")

            if purpose not in allowed_purposes:
                return self._create_result(
                    ComplianceStatus.BLOCKED,
                    account_id,
                    channel,
                    f"Cease and desist active since {cease_status.get('effective_date')}",
                    blocking_reason="FDCPA: Consumer requested cease communication",
                    remediation="Mail only for: lawsuit notice, final notice before legal action",
                    alternatives=["letter_legal_notice"],
                    metadata={"cease_date": cease_status.get("effective_date")}
                )

        return self._create_result(
            ComplianceStatus.COMPLIANT,
            account_id,
            channel,
            "No cease and desist on file"
        )


class DebtValidationRule(ComplianceRule):
    """Debt validation period compliance"""

    VALIDATION_PERIOD_DAYS = 30

    def __init__(self, dispute_handler: 'DisputeHandler'):
        super().__init__(
            rule_id="FDCPA-004",
            rule_name="Debt Validation Period",
            category=RuleCategory.FDCPA
        )
        self.dispute_handler = dispute_handler

    async def validate(
        self,
        account: Dict[str, Any],
        channel: Optional[ContactChannel],
        context: Dict[str, Any]
    ) -> ValidationResult:
        account_id = account.get("account_id", "")

        validation_status = await self.dispute_handler.get_validation_status(account_id)

        if validation_status.get("pending"):
            request_date = validation_status.get("request_date")
            if request_date:
                deadline = request_date + timedelta(days=self.VALIDATION_PERIOD_DAYS)

                return self._create_result(
                    ComplianceStatus.BLOCKED,
                    account_id,
                    channel,
                    f"Debt validation requested on {request_date.date()}",
                    blocking_reason="FDCPA: Must cease collection until debt validated",
                    remediation=f"Send validation documents by {deadline.date()}",
                    metadata={
                        "request_date": request_date.isoformat(),
                        "deadline": deadline.isoformat()
                    }
                )

        return self._create_result(
            ComplianceStatus.COMPLIANT,
            account_id,
            channel,
            "No pending validation request"
        )


class BankruptcyProtectionRule(ComplianceRule):
    """Bankruptcy automatic stay compliance"""

    def __init__(self):
        super().__init__(
            rule_id="BANK-001",
            rule_name="Bankruptcy Automatic Stay",
            category=RuleCategory.BANKRUPTCY
        )
        self._filings: Dict[str, Dict] = {}

    async def validate(
        self,
        account: Dict[str, Any],
        channel: Optional[ContactChannel],
        context: Dict[str, Any]
    ) -> ValidationResult:
        account_id = account.get("account_id", "")

        # Check for bankruptcy filing
        bankruptcy = account.get("bankruptcy_filed") or self._filings.get(account_id)

        if bankruptcy:
            filing_info = bankruptcy if isinstance(bankruptcy, dict) else {"chapter": "unknown"}
            return self._create_result(
                ComplianceStatus.BLOCKED,
                account_id,
                channel,
                f"Bankruptcy Chapter {filing_info.get('chapter', 'unknown')} filed",
                blocking_reason="11 USC 362: Automatic stay prohibits all collection activity",
                remediation="File proof of claim in bankruptcy court",
                alternatives=[],
                metadata={"bankruptcy_info": filing_info}
            )

        return self._create_result(
            ComplianceStatus.COMPLIANT,
            account_id,
            channel,
            "No bankruptcy on file"
        )

    def record_bankruptcy(self, account_id: str, chapter: str, case_number: str, filing_date: datetime):
        """Record a bankruptcy filing"""
        self._filings[account_id] = {
            "chapter": chapter,
            "case_number": case_number,
            "filing_date": filing_date,
            "recorded_at": datetime.utcnow()
        }


class SCRAProtectionRule(ComplianceRule):
    """Servicemembers Civil Relief Act compliance"""

    def __init__(self):
        super().__init__(
            rule_id="SCRA-001",
            rule_name="SCRA Active Military Protection",
            category=RuleCategory.SCRA
        )

    async def validate(
        self,
        account: Dict[str, Any],
        channel: Optional[ContactChannel],
        context: Dict[str, Any]
    ) -> ValidationResult:
        account_id = account.get("account_id", "")

        if account.get("active_military") or account.get("scra_protected"):
            return self._create_result(
                ComplianceStatus.WARNING,
                account_id,
                channel,
                "Consumer is active military - SCRA protections apply",
                remediation="Review SCRA requirements: interest cap, no default judgment",
                metadata={"scra_status": "protected"}
            )

        return self._create_result(
            ComplianceStatus.COMPLIANT,
            account_id,
            channel,
            "No SCRA protection on file"
        )


class StateLicenseRule(ComplianceRule):
    """State licensing compliance"""

    def __init__(self, license_manager: 'LicenseManager'):
        super().__init__(
            rule_id="LIC-001",
            rule_name="State License Requirement",
            category=RuleCategory.LICENSING
        )
        self.license_manager = license_manager

    async def validate(
        self,
        account: Dict[str, Any],
        channel: Optional[ContactChannel],
        context: Dict[str, Any]
    ) -> ValidationResult:
        account_id = account.get("account_id", "")
        state = account.get("debtor_state", "")

        if not state:
            return self._create_result(
                ComplianceStatus.WARNING,
                account_id,
                channel,
                "Debtor state unknown - cannot verify license",
                remediation="Obtain debtor state before proceeding"
            )

        license_status = await self.license_manager.check_license_status(state)

        state_rules = STATE_RULES_DATABASE.get(state, {})
        requires_license = state_rules.get("requires_license", True)

        if not requires_license:
            return self._create_result(
                ComplianceStatus.COMPLIANT,
                account_id,
                channel,
                f"State {state} does not require collection license"
            )

        if license_status.status not in [LicenseStatus.ACTIVE, LicenseStatus.NOT_REQUIRED]:
            return self._create_result(
                ComplianceStatus.BLOCKED,
                account_id,
                channel,
                f"No active license for state {state}",
                blocking_reason=f"Cannot collect in {state}: License {license_status.status.value}",
                remediation=f"Obtain/renew {state} collection license",
                metadata={"license_status": license_status.status.value}
            )

        # Check for license restrictions
        if license_status.restrictions:
            restrictions_str = ", ".join(license_status.restrictions)
            return self._create_result(
                ComplianceStatus.WARNING,
                account_id,
                channel,
                f"License restrictions for {state}: {restrictions_str}",
                remediation="Review restrictions before proceeding"
            )

        return self._create_result(
            ComplianceStatus.COMPLIANT,
            account_id,
            channel,
            f"Active license for {state}"
        )


class StatuteOfLimitationsRule(ComplianceRule):
    """Statute of limitations compliance"""

    def __init__(self):
        super().__init__(
            rule_id="SOL-001",
            rule_name="Statute of Limitations",
            category=RuleCategory.STATE_SPECIFIC
        )

    async def validate(
        self,
        account: Dict[str, Any],
        channel: Optional[ContactChannel],
        context: Dict[str, Any]
    ) -> ValidationResult:
        account_id = account.get("account_id", "")
        state = account.get("debtor_state", "NY")

        # Get last activity date (payment, acknowledgment, etc.)
        last_activity = account.get("last_activity_date")
        if isinstance(last_activity, str):
            last_activity = datetime.fromisoformat(last_activity)

        if not last_activity:
            return self._create_result(
                ComplianceStatus.WARNING,
                account_id,
                channel,
                "Last activity date unknown",
                remediation="Verify last activity date before collection"
            )

        state_rules = STATE_RULES_DATABASE.get(state, {"sol_years": 6})
        sol_years = state_rules.get("sol_years", 6)

        expiration_date = last_activity + timedelta(days=sol_years * 365)
        now = datetime.utcnow()

        if now > expiration_date:
            # Check if state restricts time-barred suits
            restrict_suits = state_rules.get("restrict_time_barred_suits", False)

            status = ComplianceStatus.BLOCKED if restrict_suits else ComplianceStatus.WARNING

            return self._create_result(
                status,
                account_id,
                channel,
                f"Statute of limitations expired on {expiration_date.date()}",
                blocking_reason="Cannot sue on time-barred debt" if restrict_suits else None,
                remediation="Collection only - no legal remedies; disclosure may be required",
                metadata={
                    "sol_years": sol_years,
                    "last_activity": last_activity.isoformat(),
                    "expiration": expiration_date.isoformat(),
                    "restrict_suits": restrict_suits
                }
            )

        days_remaining = (expiration_date - now).days

        if days_remaining < 90:
            return self._create_result(
                ComplianceStatus.WARNING,
                account_id,
                channel,
                f"SOL expires in {days_remaining} days",
                remediation="Consider escalation before SOL expiration",
                metadata={"days_remaining": days_remaining}
            )

        return self._create_result(
            ComplianceStatus.COMPLIANT,
            account_id,
            channel,
            f"Within SOL: {days_remaining} days remaining"
        )


# =============================================================================
# CONTACT FREQUENCY MANAGER
# =============================================================================

class ContactFrequencyManager:
    """
    Manages contact frequency tracking with rolling windows.
    Enforces per-account, per-channel limits.
    """

    def __init__(self):
        self._attempts: Dict[str, List[ContactAttempt]] = defaultdict(list)
        self._phone_attempts: Dict[str, List[ContactAttempt]] = defaultdict(list)

        # Channel-specific limits
        self.channel_limits = {
            ContactChannel.PHONE_LIVE: {"daily": 3, "weekly": 7},
            ContactChannel.PHONE_AUTO: {"daily": 2, "weekly": 7},
            ContactChannel.SMS: {"daily": 3, "weekly": 10},
            ContactChannel.EMAIL: {"daily": 2, "weekly": 7},
            ContactChannel.VOICEMAIL: {"daily": 1, "weekly": 3},
        }

        # Cool-down periods after conversation (hours)
        self.cooldown_periods = {
            ContactChannel.PHONE_LIVE: 24,
            ContactChannel.PHONE_AUTO: 24,
            ContactChannel.SMS: 4,
            ContactChannel.EMAIL: 24,
        }

    async def record_attempt(self, attempt: ContactAttempt) -> None:
        """Record a contact attempt"""
        self._attempts[attempt.account_id].append(attempt)

        # Also track by phone number for Reg F
        if attempt.channel in [ContactChannel.PHONE_LIVE, ContactChannel.PHONE_AUTO]:
            phone_key = f"{attempt.account_id}"
            self._phone_attempts[phone_key].append(attempt)

        logger.info(f"Contact attempt recorded: {attempt.account_id} via {attempt.channel.value}")

    async def get_attempts_in_window(
        self,
        account_id: str,
        phone_number: Optional[str] = None,
        channels: Optional[List[ContactChannel]] = None,
        days: int = 7
    ) -> int:
        """Get number of attempts within rolling window"""
        cutoff = datetime.utcnow() - timedelta(days=days)

        attempts = self._attempts.get(account_id, [])

        count = 0
        for attempt in attempts:
            if attempt.timestamp < cutoff:
                continue
            if channels and attempt.channel not in channels:
                continue
            count += 1

        return count

    async def get_conversations_today(self, account_id: str) -> int:
        """Get number of conversations today"""
        today = datetime.utcnow().date()

        attempts = self._attempts.get(account_id, [])

        return sum(
            1 for a in attempts
            if a.timestamp.date() == today and a.conversation_occurred
        )

    async def get_next_allowed_time(
        self,
        account_id: str,
        phone_number: Optional[str] = None,
        channels: Optional[List[ContactChannel]] = None
    ) -> datetime:
        """Calculate when next contact is allowed"""
        attempts = self._attempts.get(account_id, [])

        if not attempts:
            return datetime.utcnow()

        # Filter relevant attempts
        relevant = [
            a for a in attempts
            if not channels or a.channel in channels
        ]

        if len(relevant) < 7:
            return datetime.utcnow()

        # Sort by timestamp and find oldest in window
        relevant.sort(key=lambda x: x.timestamp)
        oldest_in_window = relevant[-7]

        # Next allowed is 7 days after oldest
        return oldest_in_window.timestamp + timedelta(days=7)

    async def check_cooldown(
        self,
        account_id: str,
        channel: ContactChannel
    ) -> Tuple[bool, Optional[datetime]]:
        """Check if account is in cooldown period"""
        cooldown_hours = self.cooldown_periods.get(channel, 24)
        cutoff = datetime.utcnow() - timedelta(hours=cooldown_hours)

        attempts = self._attempts.get(account_id, [])

        for attempt in reversed(attempts):
            if attempt.timestamp < cutoff:
                break
            if attempt.conversation_occurred:
                cooldown_end = attempt.timestamp + timedelta(hours=cooldown_hours)
                return True, cooldown_end

        return False, None

    async def get_contact_summary(self, account_id: str) -> Dict[str, Any]:
        """Get summary of contact attempts for account"""
        attempts = self._attempts.get(account_id, [])

        now = datetime.utcnow()
        today = now.date()
        week_ago = now - timedelta(days=7)

        summary = {
            "total_attempts": len(attempts),
            "attempts_today": sum(1 for a in attempts if a.timestamp.date() == today),
            "attempts_this_week": sum(1 for a in attempts if a.timestamp > week_ago),
            "conversations_today": sum(1 for a in attempts if a.timestamp.date() == today and a.conversation_occurred),
            "last_attempt": max((a.timestamp for a in attempts), default=None),
            "last_conversation": max(
                (a.timestamp for a in attempts if a.conversation_occurred),
                default=None
            ),
            "by_channel": {}
        }

        for channel in ContactChannel:
            channel_attempts = [a for a in attempts if a.channel == channel]
            if channel_attempts:
                summary["by_channel"][channel.value] = {
                    "total": len(channel_attempts),
                    "this_week": sum(1 for a in channel_attempts if a.timestamp > week_ago)
                }

        return summary


# =============================================================================
# CONSENT MANAGER
# =============================================================================

class ConsentManager:
    """
    Manages consent records with tracking for:
    - Express consent (written and oral)
    - Channel-specific consent
    - Consent expiration
    - Revocation handling
    """

    DEFAULT_CONSENT_VALIDITY_DAYS = 365

    def __init__(self):
        self._consents: Dict[str, Dict[ContactChannel, ConsentRecord]] = defaultdict(dict)
        self._dnc_list: Set[str] = set()
        self._dnc_phones: Set[str] = set()

    async def record_consent(
        self,
        account_id: str,
        channel: ContactChannel,
        consent_type: ConsentType,
        source: str,
        evidence_ref: Optional[str] = None,
        ip_address: Optional[str] = None,
        expiration_days: Optional[int] = None
    ) -> ConsentRecord:
        """Record a new consent"""
        expiration = None
        if expiration_days:
            expiration = datetime.utcnow() + timedelta(days=expiration_days)
        elif consent_type != ConsentType.EXPRESS_WRITTEN:
            expiration = datetime.utcnow() + timedelta(days=self.DEFAULT_CONSENT_VALIDITY_DAYS)

        record = ConsentRecord(
            consent_id=str(uuid.uuid4()),
            account_id=account_id,
            channel=channel,
            consent_type=consent_type,
            status=ConsentStatus.ACTIVE,
            granted_at=datetime.utcnow(),
            expires_at=expiration,
            revoked_at=None,
            source=source,
            evidence_ref=evidence_ref,
            ip_address=ip_address
        )

        self._consents[account_id][channel] = record
        logger.info(f"Consent recorded: {account_id} - {channel.value} via {source}")

        return record

    async def revoke_consent(
        self,
        account_id: str,
        channel: Optional[ContactChannel] = None,
        reason: Optional[str] = None
    ) -> List[ConsentRecord]:
        """Revoke consent for account (specific channel or all)"""
        revoked = []

        if account_id not in self._consents:
            return revoked

        channels_to_revoke = [channel] if channel else list(self._consents[account_id].keys())

        for ch in channels_to_revoke:
            if ch in self._consents[account_id]:
                record = self._consents[account_id][ch]
                record.status = ConsentStatus.REVOKED
                record.revoked_at = datetime.utcnow()
                record.metadata["revocation_reason"] = reason
                revoked.append(record)

        logger.info(f"Consent revoked: {account_id} - {len(revoked)} channel(s)")
        return revoked

    async def has_valid_consent(
        self,
        account_id: str,
        channel: ContactChannel
    ) -> bool:
        """Check if valid consent exists for channel"""
        if account_id not in self._consents:
            return False

        if channel not in self._consents[account_id]:
            return False

        record = self._consents[account_id][channel]

        # Check status
        if record.status != ConsentStatus.ACTIVE:
            return False

        # Check expiration
        if record.expires_at and datetime.utcnow() > record.expires_at:
            record.status = ConsentStatus.EXPIRED
            return False

        return True

    async def get_consent_record(
        self,
        account_id: str,
        channel: ContactChannel
    ) -> Optional[ConsentRecord]:
        """Get consent record for account/channel"""
        if account_id in self._consents and channel in self._consents[account_id]:
            return self._consents[account_id][channel]
        return None

    async def add_to_do_not_call(
        self,
        account_id: str,
        phone_number: Optional[str] = None
    ) -> None:
        """Add to do-not-call list"""
        self._dnc_list.add(account_id)
        if phone_number:
            normalized = re.sub(r'\D', '', phone_number)
            self._dnc_phones.add(normalized)

        logger.info(f"Added to DNC: {account_id}")

    async def is_on_do_not_call(
        self,
        account_id: str,
        phone_number: Optional[str] = None
    ) -> bool:
        """Check if on do-not-call list"""
        if account_id in self._dnc_list:
            return True

        if phone_number:
            normalized = re.sub(r'\D', '', phone_number)
            if normalized in self._dnc_phones:
                return True

        return False

    async def get_consent_summary(self, account_id: str) -> Dict[str, Any]:
        """Get consent summary for account"""
        if account_id not in self._consents:
            return {"has_any_consent": False, "channels": {}}

        summary = {
            "has_any_consent": False,
            "channels": {},
            "on_dnc": account_id in self._dnc_list
        }

        for channel, record in self._consents[account_id].items():
            is_valid = await self.has_valid_consent(account_id, channel)
            summary["channels"][channel.value] = {
                "status": record.status.value,
                "type": record.consent_type.value,
                "granted_at": record.granted_at.isoformat(),
                "expires_at": record.expires_at.isoformat() if record.expires_at else None,
                "is_valid": is_valid
            }
            if is_valid:
                summary["has_any_consent"] = True

        return summary


# =============================================================================
# DISPUTE HANDLER
# =============================================================================

class DisputeHandler:
    """
    Handles disputes, cease and desist, debt validation,
    and CFPB complaint tracking.
    """

    VALIDATION_RESPONSE_DAYS = 30
    DISPUTE_INVESTIGATION_DAYS = 30

    def __init__(self):
        self._disputes: Dict[str, List[DisputeRecord]] = defaultdict(list)
        self._cease_desist: Dict[str, Dict] = {}
        self._validation_requests: Dict[str, Dict] = {}
        self._cfpb_complaints: Dict[str, List[Dict]] = defaultdict(list)

    async def record_dispute(
        self,
        account_id: str,
        dispute_type: DisputeType,
        description: str,
        evidence: Optional[List[str]] = None,
        cfpb_id: Optional[str] = None
    ) -> DisputeRecord:
        """Record a new dispute"""
        dispute = DisputeRecord(
            dispute_id=str(uuid.uuid4()),
            account_id=account_id,
            dispute_type=dispute_type,
            status=DisputeStatus.RECEIVED,
            received_date=datetime.utcnow(),
            description=description,
            evidence_provided=evidence or [],
            deadline=datetime.utcnow() + timedelta(days=self.DISPUTE_INVESTIGATION_DAYS),
            cfpb_complaint_id=cfpb_id
        )

        self._disputes[account_id].append(dispute)

        # If CFPB complaint, track separately
        if cfpb_id:
            self._cfpb_complaints[account_id].append({
                "complaint_id": cfpb_id,
                "received": datetime.utcnow(),
                "dispute_id": dispute.dispute_id
            })

        logger.info(f"Dispute recorded: {account_id} - {dispute_type.value}")
        return dispute

    async def update_dispute_status(
        self,
        dispute_id: str,
        new_status: DisputeStatus,
        notes: Optional[str] = None,
        assigned_to: Optional[str] = None
    ) -> Optional[DisputeRecord]:
        """Update dispute status"""
        for account_id, disputes in self._disputes.items():
            for dispute in disputes:
                if dispute.dispute_id == dispute_id:
                    dispute.status = new_status
                    if notes:
                        dispute.resolution_notes = notes
                    if assigned_to:
                        dispute.assigned_to = assigned_to
                    if new_status in [DisputeStatus.RESOLVED_VALID, DisputeStatus.RESOLVED_INVALID, DisputeStatus.CLOSED]:
                        dispute.resolution_date = datetime.utcnow()

                    logger.info(f"Dispute updated: {dispute_id} -> {new_status.value}")
                    return dispute
        return None

    async def get_active_disputes(self, account_id: str) -> List[DisputeRecord]:
        """Get active disputes for account"""
        active_statuses = [
            DisputeStatus.RECEIVED,
            DisputeStatus.UNDER_INVESTIGATION,
            DisputeStatus.PENDING_DOCUMENTATION,
            DisputeStatus.ESCALATED
        ]

        return [
            d for d in self._disputes.get(account_id, [])
            if d.status in active_statuses
        ]

    async def record_cease_desist(
        self,
        account_id: str,
        source: str,
        received_date: Optional[datetime] = None
    ) -> Dict:
        """Record cease and desist request"""
        record = {
            "account_id": account_id,
            "active": True,
            "effective_date": received_date or datetime.utcnow(),
            "source": source,
            "recorded_at": datetime.utcnow()
        }

        self._cease_desist[account_id] = record
        logger.info(f"Cease and desist recorded: {account_id}")

        return record

    async def get_cease_desist_status(self, account_id: str) -> Dict:
        """Get cease and desist status"""
        if account_id in self._cease_desist:
            return self._cease_desist[account_id]
        return {"active": False}

    async def record_validation_request(
        self,
        account_id: str,
        request_date: Optional[datetime] = None
    ) -> Dict:
        """Record debt validation request"""
        request = {
            "account_id": account_id,
            "pending": True,
            "request_date": request_date or datetime.utcnow(),
            "response_deadline": (request_date or datetime.utcnow()) + timedelta(days=self.VALIDATION_RESPONSE_DAYS),
            "validated": False,
            "validation_sent": None
        }

        self._validation_requests[account_id] = request
        logger.info(f"Validation request recorded: {account_id}")

        return request

    async def mark_validation_sent(
        self,
        account_id: str,
        tracking_number: Optional[str] = None
    ) -> Optional[Dict]:
        """Mark debt validation as sent"""
        if account_id not in self._validation_requests:
            return None

        request = self._validation_requests[account_id]
        request["validated"] = True
        request["validation_sent"] = datetime.utcnow()
        request["pending"] = False
        request["tracking_number"] = tracking_number

        logger.info(f"Validation sent: {account_id}")
        return request

    async def get_validation_status(self, account_id: str) -> Dict:
        """Get validation request status"""
        if account_id in self._validation_requests:
            return self._validation_requests[account_id]
        return {"pending": False}

    async def record_cfpb_complaint(
        self,
        account_id: str,
        complaint_id: str,
        complaint_type: str,
        received_date: datetime,
        description: str
    ) -> Dict:
        """Record CFPB complaint"""
        complaint = {
            "complaint_id": complaint_id,
            "account_id": account_id,
            "type": complaint_type,
            "received_date": received_date,
            "description": description,
            "status": "received",
            "response_deadline": received_date + timedelta(days=15),
            "recorded_at": datetime.utcnow()
        }

        self._cfpb_complaints[account_id].append(complaint)

        # Auto-create dispute
        await self.record_dispute(
            account_id=account_id,
            dispute_type=DisputeType.OTHER,
            description=f"CFPB Complaint: {description}",
            cfpb_id=complaint_id
        )

        logger.info(f"CFPB complaint recorded: {complaint_id}")
        return complaint

    async def get_cfpb_complaints(self, account_id: str) -> List[Dict]:
        """Get CFPB complaints for account"""
        return self._cfpb_complaints.get(account_id, [])

    async def get_dispute_summary(self, account_id: str) -> Dict[str, Any]:
        """Get dispute summary for account"""
        disputes = self._disputes.get(account_id, [])
        active = await self.get_active_disputes(account_id)

        return {
            "total_disputes": len(disputes),
            "active_disputes": len(active),
            "cease_desist": await self.get_cease_desist_status(account_id),
            "validation_pending": (await self.get_validation_status(account_id)).get("pending", False),
            "cfpb_complaints": len(self._cfpb_complaints.get(account_id, [])),
            "disputes_by_type": {
                dtype.value: sum(1 for d in disputes if d.dispute_type == dtype)
                for dtype in DisputeType
            }
        }


# =============================================================================
# LICENSE MANAGER
# =============================================================================

class LicenseManager:
    """
    Manages state licensing status, renewals, and restrictions.
    """

    RENEWAL_WARNING_DAYS = 60
    BOND_WARNING_DAYS = 30

    def __init__(self):
        self._licenses: Dict[str, LicenseRecord] = {}
        self._renewal_callbacks: List[Callable] = []

    async def register_license(
        self,
        state: str,
        license_number: str,
        license_type: str,
        issued_date: datetime,
        expiration_date: datetime,
        bond_amount: Optional[Decimal] = None,
        bond_expiration: Optional[datetime] = None,
        restrictions: Optional[List[str]] = None
    ) -> LicenseRecord:
        """Register a state license"""
        record = LicenseRecord(
            license_id=str(uuid.uuid4()),
            state=state.upper(),
            license_number=license_number,
            license_type=license_type,
            status=LicenseStatus.ACTIVE,
            issued_date=issued_date,
            expiration_date=expiration_date,
            bond_amount=bond_amount,
            bond_expiration=bond_expiration,
            restrictions=restrictions or []
        )

        self._licenses[state.upper()] = record
        logger.info(f"License registered: {state} - {license_number}")

        return record

    async def check_license_status(self, state: str) -> LicenseRecord:
        """Check license status for state"""
        state = state.upper()

        # Check if state requires license
        state_rules = STATE_RULES_DATABASE.get(state, {})
        if not state_rules.get("requires_license", True):
            return LicenseRecord(
                license_id="N/A",
                state=state,
                license_number="NOT_REQUIRED",
                license_type="N/A",
                status=LicenseStatus.NOT_REQUIRED,
                issued_date=datetime.utcnow(),
                expiration_date=datetime.utcnow() + timedelta(days=36500)
            )

        if state not in self._licenses:
            return LicenseRecord(
                license_id="MISSING",
                state=state,
                license_number="",
                license_type="",
                status=LicenseStatus.PENDING,
                issued_date=datetime.utcnow(),
                expiration_date=datetime.utcnow()
            )

        record = self._licenses[state]

        # Check expiration
        now = datetime.utcnow()
        if now > record.expiration_date:
            record.status = LicenseStatus.EXPIRED
        elif (record.expiration_date - now).days <= self.RENEWAL_WARNING_DAYS:
            if not record.renewal_reminder_sent:
                await self._send_renewal_alert(record)
                record.renewal_reminder_sent = True

        return record

    async def update_license_status(
        self,
        state: str,
        new_status: LicenseStatus,
        reason: Optional[str] = None
    ) -> Optional[LicenseRecord]:
        """Update license status"""
        state = state.upper()
        if state not in self._licenses:
            return None

        record = self._licenses[state]
        record.status = new_status

        logger.info(f"License status updated: {state} -> {new_status.value}")
        return record

    async def renew_license(
        self,
        state: str,
        new_expiration: datetime,
        new_license_number: Optional[str] = None
    ) -> Optional[LicenseRecord]:
        """Renew a license"""
        state = state.upper()
        if state not in self._licenses:
            return None

        record = self._licenses[state]
        record.expiration_date = new_expiration
        record.status = LicenseStatus.ACTIVE
        record.renewal_reminder_sent = False

        if new_license_number:
            record.license_number = new_license_number

        logger.info(f"License renewed: {state} until {new_expiration.date()}")
        return record

    async def add_restriction(
        self,
        state: str,
        restriction: str
    ) -> Optional[LicenseRecord]:
        """Add restriction to license"""
        state = state.upper()
        if state not in self._licenses:
            return None

        record = self._licenses[state]
        if restriction not in record.restrictions:
            record.restrictions.append(restriction)

        logger.info(f"Restriction added to {state}: {restriction}")
        return record

    async def _send_renewal_alert(self, record: LicenseRecord) -> None:
        """Send renewal alert (calls registered callbacks)"""
        for callback in self._renewal_callbacks:
            try:
                await callback(record)
            except Exception as e:
                logger.error(f"Renewal callback error: {e}")

    def register_renewal_callback(self, callback: Callable) -> None:
        """Register callback for renewal alerts"""
        self._renewal_callbacks.append(callback)

    async def get_license_summary(self) -> Dict[str, Any]:
        """Get summary of all licenses"""
        summary = {
            "total_states": len(STATE_RULES_DATABASE),
            "licensed_states": len(self._licenses),
            "active": 0,
            "expiring_soon": 0,
            "expired": 0,
            "suspended": 0,
            "by_state": {}
        }

        now = datetime.utcnow()

        for state, record in self._licenses.items():
            status = record.status
            days_to_expiry = (record.expiration_date - now).days

            if status == LicenseStatus.ACTIVE:
                summary["active"] += 1
                if days_to_expiry <= self.RENEWAL_WARNING_DAYS:
                    summary["expiring_soon"] += 1
            elif status == LicenseStatus.EXPIRED:
                summary["expired"] += 1
            elif status == LicenseStatus.SUSPENDED:
                summary["suspended"] += 1

            summary["by_state"][state] = {
                "status": status.value,
                "expiration": record.expiration_date.isoformat(),
                "days_to_expiry": days_to_expiry,
                "restrictions": record.restrictions
            }

        return summary


# =============================================================================
# AUDIT TRAIL MANAGER
# =============================================================================

class AuditTrailManager:
    """
    Generates immutable audit logs with integrity verification.
    Supports regulatory-ready export formats.
    """

    def __init__(self):
        self._entries: List[AuditEntry] = []
        self._entry_index: Dict[str, AuditEntry] = {}

    async def log_event(
        self,
        event_type: str,
        action: str,
        details: Dict[str, Any],
        validation_results: List[ValidationResult],
        outcome: str,
        account_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> AuditEntry:
        """Log an audit event"""
        entry = AuditEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            event_type=event_type,
            account_id=account_id,
            user_id=user_id,
            action=action,
            details=details,
            validation_results=validation_results,
            outcome=outcome,
            checksum=""
        )

        # Compute checksum for integrity
        entry.checksum = entry.compute_checksum()

        self._entries.append(entry)
        self._entry_index[entry.entry_id] = entry

        logger.debug(f"Audit logged: {event_type} - {action} -> {outcome}")
        return entry

    async def get_entries(
        self,
        account_id: Optional[str] = None,
        event_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditEntry]:
        """Query audit entries"""
        results = []

        for entry in reversed(self._entries):
            if len(results) >= limit:
                break

            if account_id and entry.account_id != account_id:
                continue
            if event_type and entry.event_type != event_type:
                continue
            if start_date and entry.timestamp < start_date:
                continue
            if end_date and entry.timestamp > end_date:
                continue

            results.append(entry)

        return results

    async def verify_integrity(self, entry_id: str) -> Tuple[bool, str]:
        """Verify integrity of audit entry"""
        if entry_id not in self._entry_index:
            return False, "Entry not found"

        entry = self._entry_index[entry_id]
        computed = entry.compute_checksum()

        if computed != entry.checksum:
            return False, "Checksum mismatch - entry may be tampered"

        return True, "Integrity verified"

    async def export_regulatory(
        self,
        format_type: str = "json",
        account_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> str:
        """Export audit log in regulatory-ready format"""
        entries = await self.get_entries(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )

        if format_type == "json":
            return json.dumps([
                {
                    "entry_id": e.entry_id,
                    "timestamp": e.timestamp.isoformat(),
                    "event_type": e.event_type,
                    "account_id": e.account_id,
                    "user_id": e.user_id,
                    "action": e.action,
                    "details": e.details,
                    "validation_results": [v.to_dict() for v in e.validation_results],
                    "outcome": e.outcome,
                    "checksum": e.checksum
                }
                for e in entries
            ], indent=2)

        elif format_type == "csv":
            lines = ["entry_id,timestamp,event_type,account_id,action,outcome,checksum"]
            for e in entries:
                lines.append(
                    f"{e.entry_id},{e.timestamp.isoformat()},{e.event_type},"
                    f"{e.account_id},{e.action},{e.outcome},{e.checksum}"
                )
            return "\n".join(lines)

        return ""

    async def calculate_compliance_score(
        self,
        account_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Calculate compliance score based on audit history"""
        start_date = datetime.utcnow() - timedelta(days=days)
        entries = await self.get_entries(
            account_id=account_id,
            start_date=start_date,
            limit=10000
        )

        total_validations = 0
        compliant = 0
        warnings = 0
        blocked = 0
        violations = 0

        for entry in entries:
            for result in entry.validation_results:
                total_validations += 1
                if result.status == ComplianceStatus.COMPLIANT:
                    compliant += 1
                elif result.status == ComplianceStatus.WARNING:
                    warnings += 1
                elif result.status == ComplianceStatus.BLOCKED:
                    blocked += 1
                elif result.status == ComplianceStatus.VIOLATION:
                    violations += 1

        if total_validations == 0:
            return {
                "score": 100.0,
                "total_validations": 0,
                "period_days": days
            }

        # Score: 100 - (warnings * 1) - (blocked * 5) - (violations * 10)
        penalty = (warnings * 1) + (blocked * 5) + (violations * 10)
        score = max(0, 100 - (penalty / total_validations * 100))

        return {
            "score": round(score, 2),
            "total_validations": total_validations,
            "compliant": compliant,
            "warnings": warnings,
            "blocked": blocked,
            "violations": violations,
            "compliance_rate": round(compliant / total_validations * 100, 2),
            "block_rate": round(blocked / total_validations * 100, 2),
            "period_days": days
        }


# =============================================================================
# DYNAMIC RULE UPDATER
# =============================================================================

class DynamicRuleUpdater:
    """
    Handles dynamic updates to compliance rules from regulatory feeds.
    """

    def __init__(self, rule_engine: 'RealTimeRuleEngine'):
        self.rule_engine = rule_engine
        self._update_history: List[Dict] = []
        self._pending_updates: List[Dict] = []

    async def process_regulatory_update(
        self,
        source: str,
        update_type: str,
        rule_category: RuleCategory,
        changes: Dict[str, Any],
        effective_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Process a regulatory update"""
        update_record = {
            "update_id": str(uuid.uuid4()),
            "source": source,
            "update_type": update_type,
            "rule_category": rule_category.value,
            "changes": changes,
            "effective_date": effective_date or datetime.utcnow(),
            "received_at": datetime.utcnow(),
            "applied": False
        }

        if effective_date and effective_date > datetime.utcnow():
            self._pending_updates.append(update_record)
            logger.info(f"Regulatory update queued for {effective_date}")
        else:
            await self._apply_update(update_record)

        return update_record

    async def _apply_update(self, update: Dict) -> None:
        """Apply a regulatory update"""
        changes = update["changes"]

        # Handle state rule updates
        if "state_rules" in changes:
            for state, rules in changes["state_rules"].items():
                if state in STATE_RULES_DATABASE:
                    STATE_RULES_DATABASE[state].update(rules)
                else:
                    STATE_RULES_DATABASE[state] = rules

        # Handle rule activation/deactivation
        if "activate_rules" in changes:
            for rule_id in changes["activate_rules"]:
                rule = self.rule_engine.get_rule(rule_id)
                if rule:
                    rule.enabled = True

        if "deactivate_rules" in changes:
            for rule_id in changes["deactivate_rules"]:
                rule = self.rule_engine.get_rule(rule_id)
                if rule:
                    rule.enabled = False

        update["applied"] = True
        update["applied_at"] = datetime.utcnow()
        self._update_history.append(update)

        logger.info(f"Regulatory update applied: {update['update_id']}")

    async def check_pending_updates(self) -> int:
        """Check and apply pending updates"""
        now = datetime.utcnow()
        applied = 0

        remaining = []
        for update in self._pending_updates:
            if update["effective_date"] <= now:
                await self._apply_update(update)
                applied += 1
            else:
                remaining.append(update)

        self._pending_updates = remaining
        return applied


# =============================================================================
# REAL-TIME RULE ENGINE
# =============================================================================

class RealTimeRuleEngine:
    """
    Real-time compliance rule engine that validates all rules
    before any contact attempt.
    """

    def __init__(self):
        self.contact_tracker = ContactFrequencyManager()
        self.consent_manager = ConsentManager()
        self.dispute_handler = DisputeHandler()
        self.license_manager = LicenseManager()
        self.audit_manager = AuditTrailManager()

        self._rules: Dict[str, ComplianceRule] = {}
        self._initialize_rules()

    def _initialize_rules(self) -> None:
        """Initialize all compliance rules"""
        # FDCPA Rules
        self.register_rule(FDCPATimingRule())
        self.register_rule(FDCPAContentRule())
        self.register_rule(CeaseAndDesistRule(self.dispute_handler))
        self.register_rule(DebtValidationRule(self.dispute_handler))

        # Regulation F Rules
        self.register_rule(RegulationF7in7Rule(self.contact_tracker))
        self.register_rule(RegulationFConversationRule(self.contact_tracker))

        # TCPA Rules
        self.register_rule(TCPAConsentRule(self.consent_manager))
        self.register_rule(TCPADoNotCallRule(self.consent_manager))

        # Bankruptcy & SCRA
        self.register_rule(BankruptcyProtectionRule())
        self.register_rule(SCRAProtectionRule())

        # State-specific
        self.register_rule(StateLicenseRule(self.license_manager))
        self.register_rule(StatuteOfLimitationsRule())

    def register_rule(self, rule: ComplianceRule) -> None:
        """Register a compliance rule"""
        self._rules[rule.rule_id] = rule
        logger.debug(f"Rule registered: {rule.rule_id} - {rule.rule_name}")

    def get_rule(self, rule_id: str) -> Optional[ComplianceRule]:
        """Get rule by ID"""
        return self._rules.get(rule_id)

    async def validate_all(
        self,
        account: Dict[str, Any],
        channel: ContactChannel,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, List[ValidationResult]]:
        """
        Validate all applicable rules.
        Returns (can_proceed, list of validation results).
        """
        context = context or {}
        context["current_time"] = context.get("current_time", datetime.utcnow())

        results = []
        can_proceed = True

        for rule_id, rule in self._rules.items():
            if not rule.is_active():
                continue

            try:
                result = await rule.validate(account, channel, context)
                results.append(result)

                if result.status == ComplianceStatus.BLOCKED:
                    can_proceed = False
                elif result.status == ComplianceStatus.VIOLATION:
                    can_proceed = False

            except Exception as e:
                logger.error(f"Rule validation error ({rule_id}): {e}")
                # Fail closed - block on error
                results.append(ValidationResult(
                    validation_id=str(uuid.uuid4()),
                    timestamp=datetime.utcnow(),
                    status=ComplianceStatus.BLOCKED,
                    rule_category=rule.category,
                    rule_id=rule_id,
                    rule_name=rule.rule_name,
                    account_id=account.get("account_id", ""),
                    channel=channel,
                    details=f"Rule validation error: {str(e)}",
                    blocking_reason="System error - contact blocked for safety"
                ))
                can_proceed = False

        return can_proceed, results


# =============================================================================
# COMPLIANCE ORCHESTRATOR - MAIN ENTRY POINT
# =============================================================================

class ComplianceOrchestrator:
    """
    Main compliance orchestration system.

    Provides a single entry point for all compliance operations,
    making non-compliance technically impossible while minimizing
    friction for valid contacts.
    """

    def __init__(self):
        self.rule_engine = RealTimeRuleEngine()
        self.rule_updater = DynamicRuleUpdater(self.rule_engine)

        # Convenience accessors
        self.contacts = self.rule_engine.contact_tracker
        self.consent = self.rule_engine.consent_manager
        self.disputes = self.rule_engine.dispute_handler
        self.licenses = self.rule_engine.license_manager
        self.audit = self.rule_engine.audit_manager

        # Statistics
        self._stats = {
            "total_validations": 0,
            "approved": 0,
            "blocked": 0,
            "alternatives_suggested": 0
        }

    async def validate_contact(
        self,
        account_id: str,
        channel: ContactChannel,
        account_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate a contact attempt before execution.

        This is the PRIMARY entry point for pre-contact validation.
        Call this before ANY contact attempt.

        Returns:
            {
                "approved": bool,
                "account_id": str,
                "channel": str,
                "validation_results": [...],
                "blocking_reasons": [...] if blocked,
                "alternatives": [...] suggested alternatives,
                "compliance_score": float,
                "validation_id": str
            }
        """
        account_data["account_id"] = account_id
        context = context or {}

        # Run all validations
        can_proceed, results = await self.rule_engine.validate_all(
            account=account_data,
            channel=channel,
            context=context
        )

        self._stats["total_validations"] += 1

        # Collect blocking reasons and alternatives
        blocking_reasons = []
        alternatives = set()

        for result in results:
            if result.status == ComplianceStatus.BLOCKED:
                if result.blocking_reason:
                    blocking_reasons.append(result.blocking_reason)
                alternatives.update(result.alternatives)

        if can_proceed:
            self._stats["approved"] += 1
        else:
            self._stats["blocked"] += 1
            if alternatives:
                self._stats["alternatives_suggested"] += 1

        # Log to audit trail
        validation_id = str(uuid.uuid4())
        await self.audit.log_event(
            event_type="contact_validation",
            action=f"validate_{channel.value}",
            details={
                "account_id": account_id,
                "channel": channel.value,
                "approved": can_proceed,
                "rules_checked": len(results)
            },
            validation_results=results,
            outcome="approved" if can_proceed else "blocked",
            account_id=account_id
        )

        # Build response
        response = {
            "approved": can_proceed,
            "account_id": account_id,
            "channel": channel.value,
            "validation_id": validation_id,
            "timestamp": datetime.utcnow().isoformat(),
            "validation_results": [r.to_dict() for r in results],
            "rules_checked": len(results),
            "compliant_rules": sum(1 for r in results if r.status == ComplianceStatus.COMPLIANT),
            "warnings": sum(1 for r in results if r.status == ComplianceStatus.WARNING)
        }

        if not can_proceed:
            response["blocking_reasons"] = blocking_reasons
            response["alternatives"] = list(alternatives)
            response["suggested_action"] = await self._suggest_alternative(
                account_id, account_data, alternatives
            )

        return response

    async def _suggest_alternative(
        self,
        account_id: str,
        account_data: Dict[str, Any],
        blocked_alternatives: Set[str]
    ) -> Optional[Dict[str, Any]]:
        """Suggest a compliant alternative contact method"""
        # Priority order of channels
        channel_priority = [
            ContactChannel.EMAIL,
            ContactChannel.LETTER,
            ContactChannel.PORTAL,
            ContactChannel.SMS,
            ContactChannel.PHONE_LIVE
        ]

        for channel in channel_priority:
            if channel.value in blocked_alternatives:
                continue

            # Quick validation of alternative
            can_use, _ = await self.rule_engine.validate_all(
                account=account_data,
                channel=channel,
                context={}
            )

            if can_use:
                return {
                    "channel": channel.value,
                    "reason": f"{channel.value} is available and compliant"
                }

        return None

    async def record_contact_attempt(
        self,
        account_id: str,
        channel: ContactChannel,
        conversation_occurred: bool = False,
        duration_seconds: Optional[int] = None,
        outcome: Optional[str] = None,
        agent_id: Optional[str] = None,
        validation_id: Optional[str] = None
    ) -> ContactAttempt:
        """
        Record a contact attempt after it occurs.
        Must be called after every contact to maintain accurate tracking.
        """
        attempt = ContactAttempt(
            attempt_id=str(uuid.uuid4()),
            account_id=account_id,
            channel=channel,
            timestamp=datetime.utcnow(),
            timezone="UTC",
            conversation_occurred=conversation_occurred,
            duration_seconds=duration_seconds,
            outcome=outcome,
            agent_id=agent_id,
            validation_id=validation_id
        )

        await self.contacts.record_attempt(attempt)

        # Log to audit
        await self.audit.log_event(
            event_type="contact_attempt",
            action=f"attempt_{channel.value}",
            details={
                "attempt_id": attempt.attempt_id,
                "channel": channel.value,
                "conversation": conversation_occurred,
                "outcome": outcome
            },
            validation_results=[],
            outcome="recorded",
            account_id=account_id,
            user_id=agent_id
        )

        return attempt

    async def process_cease_desist(
        self,
        account_id: str,
        source: str = "consumer_request"
    ) -> Dict[str, Any]:
        """
        Process a cease and desist request.
        Automatically revokes all consent and blocks future contact.
        """
        # Record cease and desist
        cease_record = await self.disputes.record_cease_desist(
            account_id=account_id,
            source=source
        )

        # Revoke all consent
        revoked = await self.consent.revoke_consent(
            account_id=account_id,
            reason="cease_and_desist"
        )

        # Add to DNC
        await self.consent.add_to_do_not_call(account_id)

        # Log to audit
        await self.audit.log_event(
            event_type="cease_desist",
            action="process_cease_desist",
            details={
                "source": source,
                "consents_revoked": len(revoked)
            },
            validation_results=[],
            outcome="processed",
            account_id=account_id
        )

        return {
            "processed": True,
            "account_id": account_id,
            "cease_record": cease_record,
            "consents_revoked": len(revoked),
            "allowed_contact": ["letter_legal_notice", "letter_final_notice"]
        }

    async def process_debt_validation_request(
        self,
        account_id: str
    ) -> Dict[str, Any]:
        """
        Process a debt validation request.
        Automatically pauses collection until validation sent.
        """
        request = await self.disputes.record_validation_request(account_id)

        await self.audit.log_event(
            event_type="validation_request",
            action="record_validation_request",
            details={"deadline": request["response_deadline"].isoformat()},
            validation_results=[],
            outcome="recorded",
            account_id=account_id
        )

        return {
            "processed": True,
            "account_id": account_id,
            "request": request,
            "collection_paused": True,
            "validation_deadline": request["response_deadline"].isoformat()
        }

    async def get_account_compliance_status(
        self,
        account_id: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive compliance status for an account.
        """
        contact_summary = await self.contacts.get_contact_summary(account_id)
        consent_summary = await self.consent.get_consent_summary(account_id)
        dispute_summary = await self.disputes.get_dispute_summary(account_id)
        compliance_score = await self.audit.calculate_compliance_score(account_id)

        # Determine available channels
        available_channels = []
        for channel in ContactChannel:
            # Quick mock account for validation
            mock_account = {"account_id": account_id, "debtor_state": "NY"}
            can_use, _ = await self.rule_engine.validate_all(
                account=mock_account,
                channel=channel,
                context={}
            )
            if can_use:
                available_channels.append(channel.value)

        return {
            "account_id": account_id,
            "compliance_score": compliance_score,
            "contact_summary": contact_summary,
            "consent_summary": consent_summary,
            "dispute_summary": dispute_summary,
            "available_channels": available_channels,
            "restrictions": {
                "cease_desist": dispute_summary["cease_desist"].get("active", False),
                "validation_pending": dispute_summary["validation_pending"],
                "active_disputes": dispute_summary["active_disputes"]
            }
        }

    async def get_orchestrator_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics"""
        license_summary = await self.licenses.get_license_summary()
        compliance_score = await self.audit.calculate_compliance_score()

        return {
            "validation_stats": {
                "total": self._stats["total_validations"],
                "approved": self._stats["approved"],
                "blocked": self._stats["blocked"],
                "approval_rate": (
                    self._stats["approved"] / self._stats["total_validations"]
                    if self._stats["total_validations"] > 0 else 1.0
                ),
                "alternatives_suggested": self._stats["alternatives_suggested"]
            },
            "compliance_score": compliance_score,
            "license_summary": license_summary,
            "rules_active": sum(1 for r in self.rule_engine._rules.values() if r.is_active())
        }

    async def export_compliance_report(
        self,
        account_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        format_type: str = "json"
    ) -> str:
        """Export compliance report for regulatory purposes"""
        return await self.audit.export_regulatory(
            format_type=format_type,
            account_id=account_id,
            start_date=start_date,
            end_date=end_date
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

# Global orchestrator instance
_orchestrator: Optional[ComplianceOrchestrator] = None


def get_orchestrator() -> ComplianceOrchestrator:
    """Get or create the global orchestrator instance"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ComplianceOrchestrator()
    return _orchestrator


async def validate_contact(
    account_id: str,
    channel: str,
    account_data: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenience function for validating a contact attempt.

    Usage:
        result = await validate_contact(
            account_id="ACC-123",
            channel="phone_live",
            account_data={"debtor_state": "CA", "phone_number": "555-1234"}
        )
        if result["approved"]:
            # Proceed with contact
            pass
        else:
            # Handle blocked contact
            print(result["blocking_reasons"])
    """
    orchestrator = get_orchestrator()
    channel_enum = ContactChannel(channel) if isinstance(channel, str) else channel
    return await orchestrator.validate_contact(
        account_id=account_id,
        channel=channel_enum,
        account_data=account_data,
        context=context
    )


async def record_contact(
    account_id: str,
    channel: str,
    conversation_occurred: bool = False,
    **kwargs
) -> ContactAttempt:
    """Convenience function for recording a contact attempt"""
    orchestrator = get_orchestrator()
    channel_enum = ContactChannel(channel) if isinstance(channel, str) else channel
    return await orchestrator.record_contact_attempt(
        account_id=account_id,
        channel=channel_enum,
        conversation_occurred=conversation_occurred,
        **kwargs
    )


# =============================================================================
# DEMO / TESTING
# =============================================================================

if __name__ == "__main__":
    async def demo():
        """Demonstrate the compliance orchestrator"""
        print("=" * 60)
        print("COMPLIANCE ORCHESTRATOR DEMO")
        print("=" * 60)

        orchestrator = ComplianceOrchestrator()

        # Register a test license
        await orchestrator.licenses.register_license(
            state="CA",
            license_number="CA-12345",
            license_type="Collection Agency",
            issued_date=datetime.utcnow() - timedelta(days=365),
            expiration_date=datetime.utcnow() + timedelta(days=180)
        )

        # Test account
        test_account = {
            "account_id": "ACC-001",
            "debtor_state": "CA",
            "phone_number": "555-123-4567",
            "email": "debtor@example.com",
            "balance": 500.00,
            "last_activity_date": datetime.utcnow() - timedelta(days=180)
        }

        print("\n1. VALIDATING PHONE CONTACT")
        print("-" * 40)

        result = await orchestrator.validate_contact(
            account_id="ACC-001",
            channel=ContactChannel.PHONE_LIVE,
            account_data=test_account
        )

        print(f"   Approved: {result['approved']}")
        print(f"   Rules Checked: {result['rules_checked']}")
        print(f"   Compliant Rules: {result['compliant_rules']}")

        if not result["approved"]:
            print(f"   Blocking Reasons: {result.get('blocking_reasons', [])}")
            print(f"   Alternatives: {result.get('alternatives', [])}")

        # Record the attempt if approved
        if result["approved"]:
            await orchestrator.record_contact_attempt(
                account_id="ACC-001",
                channel=ContactChannel.PHONE_LIVE,
                conversation_occurred=True,
                duration_seconds=120,
                outcome="payment_promise"
            )

        print("\n2. TESTING 7-IN-7 RULE")
        print("-" * 40)

        # Simulate multiple attempts
        for i in range(7):
            await orchestrator.contacts.record_attempt(ContactAttempt(
                attempt_id=str(uuid.uuid4()),
                account_id="ACC-002",
                channel=ContactChannel.PHONE_LIVE,
                timestamp=datetime.utcnow() - timedelta(hours=i*2),
                timezone="UTC",
                conversation_occurred=False
            ))

        result2 = await orchestrator.validate_contact(
            account_id="ACC-002",
            channel=ContactChannel.PHONE_LIVE,
            account_data={"account_id": "ACC-002", "debtor_state": "NY"}
        )

        print(f"   After 7 attempts - Approved: {result2['approved']}")
        if not result2["approved"]:
            for reason in result2.get("blocking_reasons", []):
                print(f"   Reason: {reason}")

        print("\n3. TESTING CEASE AND DESIST")
        print("-" * 40)

        cease_result = await orchestrator.process_cease_desist(
            account_id="ACC-003",
            source="written_request"
        )

        print(f"   Processed: {cease_result['processed']}")
        print(f"   Allowed Contact: {cease_result['allowed_contact']}")

        # Try to contact after cease
        result3 = await orchestrator.validate_contact(
            account_id="ACC-003",
            channel=ContactChannel.PHONE_LIVE,
            account_data={"account_id": "ACC-003", "debtor_state": "TX"}
        )

        print(f"   Phone Contact After Cease - Approved: {result3['approved']}")

        print("\n4. COMPLIANCE SCORE")
        print("-" * 40)

        stats = await orchestrator.get_orchestrator_stats()
        print(f"   Overall Score: {stats['compliance_score']['score']}")
        print(f"   Total Validations: {stats['validation_stats']['total']}")
        print(f"   Approval Rate: {stats['validation_stats']['approval_rate']:.1%}")

        print("\n5. ACCOUNT STATUS")
        print("-" * 40)

        status = await orchestrator.get_account_compliance_status("ACC-001")
        print(f"   Account: ACC-001")
        print(f"   Available Channels: {status['available_channels']}")
        print(f"   Contact Attempts Today: {status['contact_summary']['attempts_today']}")

        print("\n" + "=" * 60)
        print("DEMO COMPLETE")
        print("=" * 60)

    asyncio.run(demo())
