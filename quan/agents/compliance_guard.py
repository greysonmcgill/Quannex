# quan/agents/compliance_guard.py
"""
Deterministic compliance guard — the kill-switch layer.

This module contains hard-coded rules that run AFTER any LLM output
and BEFORE any consumer-facing action. It is Constitutional AI in
practice: the probabilistic model proposes, but deterministic code
disposes.

The guard is intentionally strict and will block actions that are
borderline. False positives (blocking compliant actions) are acceptable;
false negatives (allowing non-compliant actions) are not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from enum import Enum
from typing import Any

from quan.logging_config import get_logger

logger = get_logger(__name__)


class ViolationType(Enum):
    """Categories of compliance violations."""

    MISSING_DISCLOSURE = "missing_mini_miranda"
    THREATENING_LANGUAGE = "threatening_language"
    FALSE_REPRESENTATION = "false_representation"
    THIRD_PARTY_DISCLOSURE = "third_party_disclosure"
    CONTACT_HOURS = "outside_contact_hours"
    FREQUENCY_LIMIT = "contact_frequency_exceeded"
    BANKRUPTCY_VIOLATION = "bankruptcy_stay_violation"
    DECEASED_CONTACT = "deceased_contact"
    ATTORNEY_BYPASS = "attorney_representation_bypass"
    DO_NOT_CONTACT = "do_not_contact_violation"
    STATUTE_EXPIRED = "statute_of_limitations_expired"
    HARASSMENT = "harassment_pattern"
    UNFAIR_PRACTICE = "unfair_practice"
    DISPUTED_NO_VALIDATION = "disputed_without_validation"


@dataclass
class ComplianceViolation:
    """A single detected compliance violation."""

    violation_type: ViolationType
    severity: str  # "critical", "high", "warning"
    rule: str  # e.g., "FDCPA § 1692e(11)"
    description: str
    evidence: str
    remediation: str


@dataclass
class GuardResult:
    """Result of running the compliance guard."""

    passed: bool
    violations: list[ComplianceViolation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": [
                {
                    "type": v.violation_type.value,
                    "severity": v.severity,
                    "rule": v.rule,
                    "description": v.description,
                }
                for v in self.violations
            ],
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Pattern definitions (compiled once)
# ---------------------------------------------------------------------------

# Mini-Miranda variations that are acceptable
# FDCPA requires disclosure that it's an attempt to collect a debt
MINI_MIRANDA_PATTERNS = [
    re.compile(
        r"(this\s+)?(is\s+)?(an?\s+)?attempt(ing)?\s+to\s+collect\s+(a\s+)?debt",
        re.IGNORECASE,
    ),
    re.compile(
        r"(communication|call|message)\s+(is\s+)?from\s+a\s+debt\s+collector.+collect\s+(a\s+)?debt",
        re.IGNORECASE,
    ),
    re.compile(
        r"debt\s+collector.+attempt(ing)?\s+to\s+collect",
        re.IGNORECASE,
    ),
]

# Prohibited threatening language
THREAT_PATTERNS = [
    (re.compile(r"\b(arrested|arrest\s+you|jail|prison|imprison)\b", re.I), "criminal_threat"),
    (re.compile(r"\b(garnish|garnishment)\b", re.I), "wage_garnishment_threat"),
    (re.compile(r"\b(seize|seizure|confiscate)\b", re.I), "asset_seizure_threat"),
    (re.compile(r"\b(sue\s+you|lawsuit|legal\s+action|take.+to\s+court)\b", re.I), "legal_threat"),
    (re.compile(r"\b(ruin|destroy|ruined)\s+(your\s+)?(credit|life)\b", re.I), "credit_threat"),
    (re.compile(r"\b(credit|life)\s+(will\s+be|is)\s+(ruin|destroy|ruined)\b", re.I), "credit_threat"),
    (re.compile(r"\b(police|authorities|law\s+enforcement)\s+(have\s+been|will\s+be|are)", re.I), "authority_threat"),
    (re.compile(r"\b(shame|embarrass)\s+(you|your)\b", re.I), "public_shame_threat"),
    (re.compile(r"\b(harass|threaten|intimidate)\b", re.I), "harassment_language"),
]

# False representation patterns
FALSE_REP_PATTERNS = [
    (re.compile(r"\b(attorney|lawyer|legal\s+department)\b", re.I), "impersonating_attorney"),
    (re.compile(r"\b(government|federal|state\s+agency)\b", re.I), "impersonating_government"),
    (re.compile(r"\b(credit\s+bureau|reporting\s+agency)\b", re.I), "impersonating_bureau"),
]

# Contact hour limits (FDCPA: 8 AM - 9 PM debtor local time)
CONTACT_HOUR_START = time(8, 0)
CONTACT_HOUR_END = time(21, 0)

# Regulation F: max 7 calls per 7 days
REG_F_CALL_LIMIT = 7
REG_F_CALL_WINDOW_DAYS = 7


class ComplianceGuard:
    """
    Deterministic compliance filter that blocks non-compliant actions.

    This is the final gate before any consumer-facing action. It does
    NOT use LLM inference — all rules are hard-coded and auditable.
    """

    def __init__(self, strict_mode: bool = True):
        """
        Args:
            strict_mode: If True, borderline cases are blocked. If False,
                         borderline cases generate warnings but pass.
        """
        self.strict_mode = strict_mode

    def check_outreach(
        self,
        message_text: str,
        channel: str,
        account: dict[str, Any],
        contact_time: datetime | None = None,
        recipient: str = "debtor",
    ) -> GuardResult:
        """
        Run all compliance checks on an outreach message.

        Args:
            message_text: The draft message content
            channel: "sms", "email", "voice", "mail", "push"
            account: Account dict with compliance flags
            contact_time: When the contact will occur (for hour check)
            recipient: Who receives the message (must be "debtor")

        Returns:
            GuardResult with pass/fail and any violations
        """
        violations: list[ComplianceViolation] = []
        warnings: list[str] = []

        # 1. Check compliance flags on the account
        flag_violations = self._check_account_flags(account, channel)
        violations.extend(flag_violations)

        # 2. Check for Mini-Miranda disclosure
        if not self._has_mini_miranda(message_text):
            violations.append(
                ComplianceViolation(
                    violation_type=ViolationType.MISSING_DISCLOSURE,
                    severity="critical",
                    rule="FDCPA § 1692e(11)",
                    description="Message missing required Mini-Miranda disclosure",
                    evidence=f"Message: {message_text[:200]}...",
                    remediation="Add: 'This is an attempt to collect a debt...'",
                )
            )

        # 3. Check for threatening language
        threat_violations = self._check_threats(message_text)
        violations.extend(threat_violations)

        # 4. Check for false representations
        false_rep_violations = self._check_false_representations(message_text)
        violations.extend(false_rep_violations)

        # 5. Check recipient is the debtor
        if recipient.lower() != "debtor":
            violations.append(
                ComplianceViolation(
                    violation_type=ViolationType.THIRD_PARTY_DISCLOSURE,
                    severity="critical",
                    rule="FDCPA § 1692c(b)",
                    description="Cannot disclose debt to third parties",
                    evidence=f"Recipient: {recipient}",
                    remediation="Messages must be sent directly to the debtor",
                )
            )

        # 6. Check contact hours (if time provided)
        if contact_time:
            hour_violation = self._check_contact_hours(contact_time)
            if hour_violation:
                violations.append(hour_violation)

        # 7. Check disputed account handling
        if account.get("disputed") and not self._has_validation_notice(message_text):
            if self.strict_mode:
                violations.append(
                    ComplianceViolation(
                        violation_type=ViolationType.DISPUTED_NO_VALIDATION,
                        severity="high",
                        rule="FDCPA § 1692g",
                        description="Disputed account must include validation rights",
                        evidence="Account marked as disputed",
                        remediation="Include debt validation information",
                    )
                )
            else:
                warnings.append("Disputed account — consider including validation notice")

        # 8. Check contact frequency (requires history)
        contact_attempts = account.get("total_contact_attempts", 0)
        days_since_first = account.get("days_since_first_contact", 0)
        if days_since_first > 0 and days_since_first <= REG_F_CALL_WINDOW_DAYS:
            if contact_attempts >= REG_F_CALL_LIMIT:
                violations.append(
                    ComplianceViolation(
                        violation_type=ViolationType.FREQUENCY_LIMIT,
                        severity="critical",
                        rule="Reg F § 1006.14(b)(2)",
                        description="Exceeded 7 contact attempts in 7 days",
                        evidence=f"Attempts: {contact_attempts} in {days_since_first} days",
                        remediation="Wait until 7-day window resets",
                    )
                )

        passed = len(violations) == 0
        return GuardResult(
            passed=passed,
            violations=violations,
            warnings=warnings,
            metadata={
                "channel": channel,
                "message_length": len(message_text),
                "account_id": account.get("account_id"),
            },
        )

    def _check_account_flags(
        self, account: dict[str, Any], channel: str
    ) -> list[ComplianceViolation]:
        """Check account-level compliance flags."""
        violations = []

        if account.get("bankruptcy_flag"):
            violations.append(
                ComplianceViolation(
                    violation_type=ViolationType.BANKRUPTCY_VIOLATION,
                    severity="critical",
                    rule="11 U.S.C. § 362 (Automatic Stay)",
                    description="Cannot contact debtor with active bankruptcy",
                    evidence="Account has bankruptcy_flag=True",
                    remediation="Route to legal/bankruptcy department",
                )
            )

        if account.get("deceased_flag"):
            violations.append(
                ComplianceViolation(
                    violation_type=ViolationType.DECEASED_CONTACT,
                    severity="critical",
                    rule="FDCPA § 1692c",
                    description="Cannot collect from deceased debtor",
                    evidence="Account has deceased_flag=True",
                    remediation="Contact estate executor only",
                )
            )

        if account.get("attorney_represented"):
            violations.append(
                ComplianceViolation(
                    violation_type=ViolationType.ATTORNEY_BYPASS,
                    severity="critical",
                    rule="FDCPA § 1692c(a)(2)",
                    description="Must communicate through attorney when represented",
                    evidence="Account has attorney_represented=True",
                    remediation="Contact attorney on file, not debtor directly",
                )
            )

        if account.get("statute_of_limitations_expired"):
            violations.append(
                ComplianceViolation(
                    violation_type=ViolationType.STATUTE_EXPIRED,
                    severity="critical",
                    rule="State consumer protection laws",
                    description="Cannot collect on time-barred debt without disclosure",
                    evidence="Account has statute_of_limitations_expired=True",
                    remediation="Must disclose debt is time-barred in all communications",
                )
            )

        # Channel-specific flags
        if channel == "voice" and account.get("do_not_call"):
            violations.append(
                ComplianceViolation(
                    violation_type=ViolationType.DO_NOT_CONTACT,
                    severity="critical",
                    rule="FDCPA § 1692c(c) / TCPA",
                    description="Debtor requested no phone calls",
                    evidence="Account has do_not_call=True",
                    remediation="Use alternative channel (email, mail)",
                )
            )

        if channel == "email" and account.get("do_not_email"):
            violations.append(
                ComplianceViolation(
                    violation_type=ViolationType.DO_NOT_CONTACT,
                    severity="critical",
                    rule="FDCPA § 1692c(c)",
                    description="Debtor requested no emails",
                    evidence="Account has do_not_email=True",
                    remediation="Use alternative channel (mail, sms if consented)",
                )
            )

        if channel == "mail" and account.get("do_not_mail"):
            violations.append(
                ComplianceViolation(
                    violation_type=ViolationType.DO_NOT_CONTACT,
                    severity="critical",
                    rule="FDCPA § 1692c(c)",
                    description="Debtor requested no mail",
                    evidence="Account has do_not_mail=True",
                    remediation="Use alternative channel (email if available)",
                )
            )

        return violations

    def _has_mini_miranda(self, text: str) -> bool:
        """Check if text contains Mini-Miranda disclosure."""
        for pattern in MINI_MIRANDA_PATTERNS:
            if pattern.search(text):
                return True
        return False

    def _has_validation_notice(self, text: str) -> bool:
        """Check if text mentions debt validation rights."""
        validation_patterns = [
            re.compile(r"(dispute|validation|verify|verification)\s*(right|request|within)", re.I),
            re.compile(r"right\s+to\s+dispute", re.I),
            re.compile(r"request\s+validation", re.I),
            re.compile(r"dispute\s+this\s+debt", re.I),
            re.compile(r"(provide|send)\s+verification", re.I),
        ]
        return any(p.search(text) for p in validation_patterns)

    def _check_threats(self, text: str) -> list[ComplianceViolation]:
        """Check for threatening language patterns."""
        violations = []
        for pattern, threat_type in THREAT_PATTERNS:
            match = pattern.search(text)
            if match:
                violations.append(
                    ComplianceViolation(
                        violation_type=ViolationType.THREATENING_LANGUAGE,
                        severity="critical",
                        rule="FDCPA § 1692d, § 1692e",
                        description=f"Prohibited language detected: {threat_type}",
                        evidence=f"Found: '{match.group()}' in message",
                        remediation="Remove threatening language; focus on solutions",
                    )
                )
        return violations

    def _check_false_representations(self, text: str) -> list[ComplianceViolation]:
        """Check for false representation patterns."""
        violations = []
        for pattern, rep_type in FALSE_REP_PATTERNS:
            match = pattern.search(text)
            if match:
                violations.append(
                    ComplianceViolation(
                        violation_type=ViolationType.FALSE_REPRESENTATION,
                        severity="critical",
                        rule="FDCPA § 1692e(1-3)",
                        description=f"Potential false representation: {rep_type}",
                        evidence=f"Found: '{match.group()}' in message",
                        remediation="Clearly identify as debt collector, not legal/govt entity",
                    )
                )
        return violations

    def _check_contact_hours(self, contact_time: datetime) -> ComplianceViolation | None:
        """Check if contact time is within allowed hours."""
        local_time = contact_time.time()
        if local_time < CONTACT_HOUR_START or local_time > CONTACT_HOUR_END:
            return ComplianceViolation(
                violation_type=ViolationType.CONTACT_HOURS,
                severity="critical",
                rule="FDCPA § 1692c(a)(1)",
                description="Contact outside allowed hours (8 AM - 9 PM)",
                evidence=f"Scheduled time: {local_time.strftime('%H:%M')}",
                remediation="Reschedule to within 8 AM - 9 PM debtor local time",
            )
        return None


# Singleton instance for convenience
_default_guard: ComplianceGuard | None = None


def get_compliance_guard(strict_mode: bool = True) -> ComplianceGuard:
    """Get or create the default compliance guard instance."""
    global _default_guard
    if _default_guard is None or _default_guard.strict_mode != strict_mode:
        _default_guard = ComplianceGuard(strict_mode=strict_mode)
    return _default_guard
