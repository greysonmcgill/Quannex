"""
Risk Mitigation and Compliance Hardening

Comprehensive risk management system ensuring regulatory compliance
and minimizing operational, legal, and financial risks.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Set, Tuple
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ComplianceStatus(Enum):
    """Compliance check status"""
    COMPLIANT = "compliant"
    WARNING = "warning"
    VIOLATION = "violation"
    BLOCKED = "blocked"


class ActionType(Enum):
    """Types of collection actions"""
    PHONE_CALL = "phone_call"
    SMS = "sms"
    EMAIL = "email"
    LETTER = "letter"
    VOICEMAIL = "voicemail"
    PAYMENT_REQUEST = "payment_request"
    SETTLEMENT_OFFER = "settlement_offer"
    LEGAL_ACTION = "legal_action"


@dataclass
class ComplianceCheck:
    """Result of a compliance check"""
    check_id: str
    check_type: str
    status: ComplianceStatus
    account_id: str
    action_type: ActionType
    timestamp: datetime
    details: str
    blocking_reason: Optional[str] = None
    remediation: Optional[str] = None


@dataclass
class RiskAssessment:
    """Risk assessment for an account"""
    account_id: str
    overall_risk_score: float  # 0-1 (1 = highest risk)
    risk_factors: Dict[str, float]
    recommended_actions: List[str]
    restricted_actions: List[ActionType]
    assessment_date: datetime


class TCPAComplianceEngine:
    """
    Telephone Consumer Protection Act compliance.

    Key requirements:
    - Prior express consent for autodialed calls/texts
    - No calls before 8am or after 9pm local time
    - Honor do-not-call requests
    - Proper caller ID
    """

    # State timezone mappings (simplified)
    STATE_TIMEZONES = {
        "CA": "America/Los_Angeles", "WA": "America/Los_Angeles",
        "OR": "America/Los_Angeles", "NV": "America/Los_Angeles",
        "AZ": "America/Phoenix", "MT": "America/Denver",
        "CO": "America/Denver", "NM": "America/Denver",
        "TX": "America/Chicago", "IL": "America/Chicago",
        "NY": "America/New_York", "FL": "America/New_York",
        "PA": "America/New_York", "OH": "America/New_York",
        # Default to Eastern
    }

    def __init__(self):
        self.do_not_call_list: Set[str] = set()
        self.consent_records: Dict[str, Dict] = {}
        self.call_records: Dict[str, List[datetime]] = {}

    def check_calling_hours(
        self,
        phone_number: str,
        state: str,
        current_time: Optional[datetime] = None
    ) -> ComplianceCheck:
        """Check if current time is within allowed calling hours"""
        if current_time is None:
            current_time = datetime.now()

        # Get state timezone (simplified - use hour offset)
        tz_offsets = {
            "America/Los_Angeles": -8,
            "America/Denver": -7,
            "America/Chicago": -6,
            "America/New_York": -5,
            "America/Phoenix": -7,
        }

        tz_name = self.STATE_TIMEZONES.get(state, "America/New_York")
        offset = tz_offsets.get(tz_name, -5)

        # Calculate local hour (simplified)
        utc_hour = current_time.hour
        local_hour = (utc_hour + offset) % 24

        # TCPA: No calls before 8am or after 9pm local time
        if local_hour < 8 or local_hour >= 21:
            return ComplianceCheck(
                check_id=str(uuid.uuid4()),
                check_type="TCPA_CALLING_HOURS",
                status=ComplianceStatus.BLOCKED,
                account_id="",
                action_type=ActionType.PHONE_CALL,
                timestamp=current_time,
                details=f"Outside calling hours. Local time ~{local_hour}:00 in {state}",
                blocking_reason="TCPA violation: Call outside 8am-9pm local time",
                remediation=f"Schedule call for 8am-9pm {tz_name}"
            )

        return ComplianceCheck(
            check_id=str(uuid.uuid4()),
            check_type="TCPA_CALLING_HOURS",
            status=ComplianceStatus.COMPLIANT,
            account_id="",
            action_type=ActionType.PHONE_CALL,
            timestamp=current_time,
            details=f"Within calling hours. Local time ~{local_hour}:00"
        )

    def check_do_not_call(self, phone_number: str) -> ComplianceCheck:
        """Check if number is on do-not-call list"""
        normalized = re.sub(r'\D', '', phone_number)

        if normalized in self.do_not_call_list:
            return ComplianceCheck(
                check_id=str(uuid.uuid4()),
                check_type="TCPA_DNC",
                status=ComplianceStatus.BLOCKED,
                account_id="",
                action_type=ActionType.PHONE_CALL,
                timestamp=datetime.now(),
                details=f"Number {phone_number} on DNC list",
                blocking_reason="Number on do-not-call list",
                remediation="Use alternative contact method (mail)"
            )

        return ComplianceCheck(
            check_id=str(uuid.uuid4()),
            check_type="TCPA_DNC",
            status=ComplianceStatus.COMPLIANT,
            account_id="",
            action_type=ActionType.PHONE_CALL,
            timestamp=datetime.now(),
            details="Number not on DNC list"
        )

    def check_consent(
        self,
        phone_number: str,
        action_type: ActionType
    ) -> ComplianceCheck:
        """Check for prior express consent"""
        normalized = re.sub(r'\D', '', phone_number)

        consent = self.consent_records.get(normalized)

        if action_type in [ActionType.SMS]:
            # SMS requires express written consent
            if not consent or not consent.get("sms_consent"):
                return ComplianceCheck(
                    check_id=str(uuid.uuid4()),
                    check_type="TCPA_CONSENT",
                    status=ComplianceStatus.BLOCKED,
                    account_id="",
                    action_type=action_type,
                    timestamp=datetime.now(),
                    details="No SMS consent on file",
                    blocking_reason="TCPA: SMS requires express written consent",
                    remediation="Obtain consent or use phone/mail"
                )

        return ComplianceCheck(
            check_id=str(uuid.uuid4()),
            check_type="TCPA_CONSENT",
            status=ComplianceStatus.COMPLIANT,
            account_id="",
            action_type=action_type,
            timestamp=datetime.now(),
            details="Consent requirements met"
        )

    def add_to_dnc(self, phone_number: str):
        """Add number to do-not-call list"""
        normalized = re.sub(r'\D', '', phone_number)
        self.do_not_call_list.add(normalized)
        logger.info(f"Added {phone_number} to DNC list")

    def record_consent(
        self,
        phone_number: str,
        consent_type: str,
        consent_date: datetime,
        source: str
    ):
        """Record consent for a phone number"""
        normalized = re.sub(r'\D', '', phone_number)

        if normalized not in self.consent_records:
            self.consent_records[normalized] = {}

        self.consent_records[normalized][f"{consent_type}_consent"] = True
        self.consent_records[normalized][f"{consent_type}_date"] = consent_date
        self.consent_records[normalized][f"{consent_type}_source"] = source


class FDCPAComplianceEngine:
    """
    Fair Debt Collection Practices Act compliance.

    Key requirements:
    - No harassment or abuse
    - No false or misleading statements
    - Debt validation on request
    - Cease communication on request
    - Mini-Miranda warning
    """

    # Maximum contact attempts per time period
    MAX_CALLS_PER_DAY = 1
    MAX_CALLS_PER_WEEK = 7
    VALIDATION_PERIOD_DAYS = 30

    def __init__(self):
        self.cease_communication: Set[str] = set()
        self.validation_requests: Dict[str, datetime] = {}
        self.contact_history: Dict[str, List[Dict]] = {}
        self.disputed_accounts: Set[str] = set()

    def check_contact_frequency(
        self,
        account_id: str,
        action_type: ActionType
    ) -> ComplianceCheck:
        """Check if contact frequency is within limits (Reg F: 7 calls/week)"""
        history = self.contact_history.get(account_id, [])

        now = datetime.now()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        # Count recent contacts
        calls_today = sum(
            1 for c in history
            if c["timestamp"] > day_ago and c["type"] == "phone"
        )
        calls_this_week = sum(
            1 for c in history
            if c["timestamp"] > week_ago and c["type"] == "phone"
        )

        if calls_today >= self.MAX_CALLS_PER_DAY:
            return ComplianceCheck(
                check_id=str(uuid.uuid4()),
                check_type="FDCPA_FREQUENCY",
                status=ComplianceStatus.BLOCKED,
                account_id=account_id,
                action_type=action_type,
                timestamp=now,
                details=f"Already called {calls_today}x today",
                blocking_reason="FDCPA/Reg F: Max 1 call per day to same number",
                remediation="Wait until tomorrow or use different channel"
            )

        if calls_this_week >= self.MAX_CALLS_PER_WEEK:
            return ComplianceCheck(
                check_id=str(uuid.uuid4()),
                check_type="FDCPA_FREQUENCY",
                status=ComplianceStatus.BLOCKED,
                account_id=account_id,
                action_type=action_type,
                timestamp=now,
                details=f"Already called {calls_this_week}x this week",
                blocking_reason="FDCPA/Reg F: Max 7 calls per week",
                remediation="Wait for next week or use mail"
            )

        return ComplianceCheck(
            check_id=str(uuid.uuid4()),
            check_type="FDCPA_FREQUENCY",
            status=ComplianceStatus.COMPLIANT,
            account_id=account_id,
            action_type=action_type,
            timestamp=now,
            details=f"Within limits: {calls_today}/day, {calls_this_week}/week"
        )

    def check_cease_communication(self, account_id: str) -> ComplianceCheck:
        """Check if debtor has requested cease communication"""
        if account_id in self.cease_communication:
            return ComplianceCheck(
                check_id=str(uuid.uuid4()),
                check_type="FDCPA_CEASE",
                status=ComplianceStatus.BLOCKED,
                account_id=account_id,
                action_type=ActionType.PHONE_CALL,
                timestamp=datetime.now(),
                details="Cease communication requested",
                blocking_reason="FDCPA: Consumer requested no further contact",
                remediation="Mail only for legally required notices"
            )

        return ComplianceCheck(
            check_id=str(uuid.uuid4()),
            check_type="FDCPA_CEASE",
            status=ComplianceStatus.COMPLIANT,
            account_id=account_id,
            action_type=ActionType.PHONE_CALL,
            timestamp=datetime.now(),
            details="No cease request on file"
        )

    def check_validation_period(self, account_id: str) -> ComplianceCheck:
        """Check if in validation period (must pause until validated)"""
        if account_id in self.validation_requests:
            request_date = self.validation_requests[account_id]
            if datetime.now() < request_date + timedelta(days=self.VALIDATION_PERIOD_DAYS):
                return ComplianceCheck(
                    check_id=str(uuid.uuid4()),
                    check_type="FDCPA_VALIDATION",
                    status=ComplianceStatus.BLOCKED,
                    account_id=account_id,
                    action_type=ActionType.PHONE_CALL,
                    timestamp=datetime.now(),
                    details="Debt validation requested, not yet provided",
                    blocking_reason="FDCPA: Must cease collection until debt validated",
                    remediation="Send validation letter before continuing"
                )

        return ComplianceCheck(
            check_id=str(uuid.uuid4()),
            check_type="FDCPA_VALIDATION",
            status=ComplianceStatus.COMPLIANT,
            account_id=account_id,
            action_type=ActionType.PHONE_CALL,
            timestamp=datetime.now(),
            details="No pending validation request"
        )

    def check_disputed(self, account_id: str) -> ComplianceCheck:
        """Check if debt is disputed"""
        if account_id in self.disputed_accounts:
            return ComplianceCheck(
                check_id=str(uuid.uuid4()),
                check_type="FDCPA_DISPUTE",
                status=ComplianceStatus.WARNING,
                account_id=account_id,
                action_type=ActionType.PHONE_CALL,
                timestamp=datetime.now(),
                details="Debt is disputed",
                remediation="Investigation required before collection"
            )

        return ComplianceCheck(
            check_id=str(uuid.uuid4()),
            check_type="FDCPA_DISPUTE",
            status=ComplianceStatus.COMPLIANT,
            account_id=account_id,
            action_type=ActionType.PHONE_CALL,
            timestamp=datetime.now(),
            details="Debt not disputed"
        )

    def record_contact(
        self,
        account_id: str,
        contact_type: str,
        timestamp: Optional[datetime] = None
    ):
        """Record a contact attempt"""
        if timestamp is None:
            timestamp = datetime.now()

        if account_id not in self.contact_history:
            self.contact_history[account_id] = []

        self.contact_history[account_id].append({
            "type": contact_type,
            "timestamp": timestamp
        })

    def request_cease(self, account_id: str):
        """Record cease communication request"""
        self.cease_communication.add(account_id)
        logger.info(f"Cease communication recorded for {account_id}")

    def request_validation(self, account_id: str):
        """Record validation request"""
        self.validation_requests[account_id] = datetime.now()
        logger.info(f"Validation requested for {account_id}")

    def dispute_debt(self, account_id: str):
        """Record debt dispute"""
        self.disputed_accounts.add(account_id)
        logger.info(f"Debt disputed for {account_id}")


class BankruptcyMonitor:
    """
    Bankruptcy filing monitoring and automatic stay compliance.
    """

    def __init__(self):
        self.bankruptcy_filings: Dict[str, Dict] = {}

    def check_bankruptcy(self, account_id: str, ssn: str) -> ComplianceCheck:
        """Check if debtor has filed bankruptcy"""
        # Check local records
        if account_id in self.bankruptcy_filings:
            filing = self.bankruptcy_filings[account_id]
            return ComplianceCheck(
                check_id=str(uuid.uuid4()),
                check_type="BANKRUPTCY",
                status=ComplianceStatus.BLOCKED,
                account_id=account_id,
                action_type=ActionType.PHONE_CALL,
                timestamp=datetime.now(),
                details=f"Bankruptcy filed: {filing.get('chapter')} on {filing.get('date')}",
                blocking_reason="Automatic stay in effect - all collection must cease",
                remediation="File proof of claim in bankruptcy court"
            )

        return ComplianceCheck(
            check_id=str(uuid.uuid4()),
            check_type="BANKRUPTCY",
            status=ComplianceStatus.COMPLIANT,
            account_id=account_id,
            action_type=ActionType.PHONE_CALL,
            timestamp=datetime.now(),
            details="No bankruptcy filing on record"
        )

    def record_filing(
        self,
        account_id: str,
        chapter: str,
        case_number: str,
        filing_date: datetime
    ):
        """Record a bankruptcy filing"""
        self.bankruptcy_filings[account_id] = {
            "chapter": chapter,
            "case_number": case_number,
            "date": filing_date,
            "recorded": datetime.now()
        }
        logger.info(f"Bankruptcy Ch.{chapter} recorded for {account_id}")


class StatuteOfLimitationsEngine:
    """
    Statute of limitations tracking by state and debt type.
    """

    # SOL by state (years) - simplified, actual varies by debt type
    STATE_SOL = {
        "AL": 6, "AK": 3, "AZ": 6, "AR": 5, "CA": 4,
        "CO": 6, "CT": 6, "DE": 3, "FL": 5, "GA": 6,
        "HI": 6, "ID": 5, "IL": 5, "IN": 6, "IA": 5,
        "KS": 5, "KY": 5, "LA": 3, "ME": 6, "MD": 3,
        "MA": 6, "MI": 6, "MN": 6, "MS": 3, "MO": 5,
        "MT": 5, "NE": 5, "NV": 6, "NH": 3, "NJ": 6,
        "NM": 6, "NY": 6, "NC": 3, "ND": 6, "OH": 6,
        "OK": 5, "OR": 6, "PA": 4, "RI": 10, "SC": 3,
        "SD": 6, "TN": 6, "TX": 4, "UT": 6, "VT": 6,
        "VA": 5, "WA": 6, "WV": 10, "WI": 6, "WY": 8,
        "DC": 3,
    }

    def check_sol(
        self,
        account_id: str,
        state: str,
        last_activity_date: datetime,
        debt_type: str = "general"
    ) -> ComplianceCheck:
        """Check if statute of limitations has expired"""
        sol_years = self.STATE_SOL.get(state, 6)  # Default 6 years

        expiration_date = last_activity_date + timedelta(days=sol_years * 365)

        if datetime.now() > expiration_date:
            return ComplianceCheck(
                check_id=str(uuid.uuid4()),
                check_type="SOL_EXPIRED",
                status=ComplianceStatus.WARNING,
                account_id=account_id,
                action_type=ActionType.LEGAL_ACTION,
                timestamp=datetime.now(),
                details=f"SOL expired on {expiration_date.date()} ({state}: {sol_years} years)",
                blocking_reason="Cannot pursue legal action after SOL expiration",
                remediation="Collection only - no legal remedies available"
            )

        days_remaining = (expiration_date - datetime.now()).days

        return ComplianceCheck(
            check_id=str(uuid.uuid4()),
            check_type="SOL_ACTIVE",
            status=ComplianceStatus.COMPLIANT,
            account_id=account_id,
            action_type=ActionType.LEGAL_ACTION,
            timestamp=datetime.now(),
            details=f"SOL expires {expiration_date.date()} ({days_remaining} days remaining)"
        )


class ComplianceOrchestrator:
    """
    Central orchestrator for all compliance checks.

    Runs all applicable compliance checks before any action.
    """

    def __init__(self):
        self.tcpa = TCPAComplianceEngine()
        self.fdcpa = FDCPAComplianceEngine()
        self.bankruptcy = BankruptcyMonitor()
        self.sol = StatuteOfLimitationsEngine()

        # Statistics
        self.stats = {
            "total_checks": 0,
            "compliant": 0,
            "warnings": 0,
            "violations": 0,
            "blocked": 0
        }

    async def run_pre_action_checks(
        self,
        account_id: str,
        action_type: ActionType,
        account_data: Dict[str, Any]
    ) -> Tuple[bool, List[ComplianceCheck]]:
        """
        Run all compliance checks before an action.

        Returns:
            Tuple of (can_proceed, list of check results)
        """
        checks = []

        phone = account_data.get("phone", "")
        state = account_data.get("state", "NY")
        ssn = account_data.get("ssn", "")
        last_activity = account_data.get("last_activity_date", datetime.now() - timedelta(days=180))

        # TCPA checks for phone/SMS
        if action_type in [ActionType.PHONE_CALL, ActionType.SMS, ActionType.VOICEMAIL]:
            checks.append(self.tcpa.check_calling_hours(phone, state))
            checks.append(self.tcpa.check_do_not_call(phone))
            checks.append(self.tcpa.check_consent(phone, action_type))

        # FDCPA checks for all actions
        checks.append(self.fdcpa.check_contact_frequency(account_id, action_type))
        checks.append(self.fdcpa.check_cease_communication(account_id))
        checks.append(self.fdcpa.check_validation_period(account_id))
        checks.append(self.fdcpa.check_disputed(account_id))

        # Bankruptcy check
        checks.append(self.bankruptcy.check_bankruptcy(account_id, ssn))

        # SOL check for legal actions
        if action_type == ActionType.LEGAL_ACTION:
            checks.append(self.sol.check_sol(account_id, state, last_activity))

        # Update statistics
        self.stats["total_checks"] += len(checks)

        can_proceed = True
        for check in checks:
            if check.status == ComplianceStatus.BLOCKED:
                can_proceed = False
                self.stats["blocked"] += 1
            elif check.status == ComplianceStatus.VIOLATION:
                can_proceed = False
                self.stats["violations"] += 1
            elif check.status == ComplianceStatus.WARNING:
                self.stats["warnings"] += 1
            else:
                self.stats["compliant"] += 1

        return can_proceed, checks

    def get_compliance_report(self) -> Dict[str, Any]:
        """Get compliance statistics report"""
        total = self.stats["total_checks"]
        if total == 0:
            return {"total_checks": 0, "compliance_rate": 1.0}

        return {
            "total_checks": total,
            "compliant": self.stats["compliant"],
            "warnings": self.stats["warnings"],
            "violations": self.stats["violations"],
            "blocked": self.stats["blocked"],
            "compliance_rate": self.stats["compliant"] / total,
            "block_rate": self.stats["blocked"] / total
        }


class RiskScoringEngine:
    """
    Real-time risk scoring for accounts.
    """

    # Risk weights
    RISK_WEIGHTS = {
        "bankruptcy": 1.0,
        "disputed": 0.6,
        "cease_requested": 0.8,
        "sol_expired": 0.5,
        "fraud_indicator": 0.7,
        "litigation_history": 0.6,
        "multiple_collection_attempts": 0.3,
        "high_balance": 0.2,
        "low_income": 0.2,
    }

    def calculate_risk_score(
        self,
        account_data: Dict[str, Any],
        compliance_checks: List[ComplianceCheck]
    ) -> RiskAssessment:
        """Calculate overall risk score for an account"""
        risk_factors = {}
        restricted_actions = []
        recommendations = []

        # Check compliance results
        for check in compliance_checks:
            if check.status == ComplianceStatus.BLOCKED:
                if "BANKRUPTCY" in check.check_type:
                    risk_factors["bankruptcy"] = 1.0
                    restricted_actions = list(ActionType)
                    recommendations.append("File proof of claim in bankruptcy")
                elif "CEASE" in check.check_type:
                    risk_factors["cease_requested"] = 1.0
                    restricted_actions.extend([ActionType.PHONE_CALL, ActionType.SMS, ActionType.EMAIL])
                    recommendations.append("Use mail for required notices only")
                elif "SOL" in check.check_type:
                    risk_factors["sol_expired"] = 1.0
                    restricted_actions.append(ActionType.LEGAL_ACTION)
                    recommendations.append("Collection only - no legal action")

            elif check.status == ComplianceStatus.WARNING:
                if "DISPUTE" in check.check_type:
                    risk_factors["disputed"] = 0.8
                    recommendations.append("Investigate dispute before continuing")

        # Check account data for risk factors
        if account_data.get("is_fraud_risk"):
            risk_factors["fraud_indicator"] = 0.7
            recommendations.append("Enhanced verification required")

        if account_data.get("litigation_history"):
            risk_factors["litigation_history"] = 0.6
            recommendations.append("Legal review before action")

        if account_data.get("income_bracket") == "low":
            risk_factors["low_income"] = 0.3
            recommendations.append("Consider hardship program")

        balance = account_data.get("balance", 0)
        if balance > 5000:
            risk_factors["high_balance"] = 0.2
            recommendations.append("High-value account - senior agent")

        # Calculate weighted score
        total_score = sum(
            factor * self.RISK_WEIGHTS.get(name, 0.3)
            for name, factor in risk_factors.items()
        )
        overall_score = min(1.0, total_score)

        return RiskAssessment(
            account_id=account_data.get("account_id", ""),
            overall_risk_score=overall_score,
            risk_factors=risk_factors,
            recommended_actions=recommendations,
            restricted_actions=restricted_actions,
            assessment_date=datetime.now()
        )


class ComplianceGateway:
    """
    Main gateway for all compliance and risk operations.

    Use this as the single entry point for compliance checks.
    """

    def __init__(self):
        self.orchestrator = ComplianceOrchestrator()
        self.risk_engine = RiskScoringEngine()
        self.action_log: List[Dict] = []

    async def request_action_approval(
        self,
        account_id: str,
        action_type: ActionType,
        account_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Request approval for a collection action.

        This is the main entry point - call this before any action.
        """
        # Run compliance checks
        can_proceed, checks = await self.orchestrator.run_pre_action_checks(
            account_id, action_type, account_data
        )

        # Calculate risk score
        risk = self.risk_engine.calculate_risk_score(account_data, checks)

        # Log the request
        self.action_log.append({
            "timestamp": datetime.now(),
            "account_id": account_id,
            "action_type": action_type.value,
            "approved": can_proceed,
            "risk_score": risk.overall_risk_score,
            "checks_run": len(checks)
        })

        # Build response
        response = {
            "approved": can_proceed,
            "account_id": account_id,
            "action_type": action_type.value,
            "risk_score": risk.overall_risk_score,
            "risk_level": (
                "CRITICAL" if risk.overall_risk_score > 0.8 else
                "HIGH" if risk.overall_risk_score > 0.5 else
                "MEDIUM" if risk.overall_risk_score > 0.3 else
                "LOW"
            ),
            "checks": [
                {
                    "type": c.check_type,
                    "status": c.status.value,
                    "details": c.details,
                    "remediation": c.remediation
                }
                for c in checks
            ],
            "recommendations": risk.recommended_actions,
            "restricted_actions": [a.value for a in risk.restricted_actions]
        }

        if not can_proceed:
            # Find blocking reasons
            blockers = [c for c in checks if c.status == ComplianceStatus.BLOCKED]
            response["blocking_reasons"] = [c.blocking_reason for c in blockers]

        return response

    def record_action_taken(
        self,
        account_id: str,
        action_type: ActionType,
        result: str
    ):
        """Record that an action was taken (for tracking)"""
        if action_type in [ActionType.PHONE_CALL, ActionType.VOICEMAIL]:
            self.orchestrator.fdcpa.record_contact(account_id, "phone")
        elif action_type == ActionType.SMS:
            self.orchestrator.fdcpa.record_contact(account_id, "sms")
        elif action_type == ActionType.EMAIL:
            self.orchestrator.fdcpa.record_contact(account_id, "email")

    def get_compliance_summary(self) -> Dict[str, Any]:
        """Get overall compliance summary"""
        return {
            "compliance_stats": self.orchestrator.get_compliance_report(),
            "total_actions_logged": len(self.action_log),
            "approvals": sum(1 for a in self.action_log if a["approved"]),
            "denials": sum(1 for a in self.action_log if not a["approved"]),
            "avg_risk_score": (
                sum(a["risk_score"] for a in self.action_log) / len(self.action_log)
                if self.action_log else 0
            )
        }


# Convenience function for quick compliance check
async def check_compliance(
    account_id: str,
    action_type: str,
    account_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Quick compliance check function"""
    gateway = ComplianceGateway()
    action = ActionType(action_type) if isinstance(action_type, str) else action_type
    return await gateway.request_action_approval(account_id, action, account_data)


if __name__ == "__main__":
    # Demo
    async def demo():
        gateway = ComplianceGateway()

        # Test account
        account = {
            "account_id": "ACC-001",
            "phone": "555-123-4567",
            "state": "CA",
            "ssn": "123-45-6789",
            "balance": 500,
            "income_bracket": "medium",
            "last_activity_date": datetime.now() - timedelta(days=180)
        }

        # Test phone call approval
        result = await gateway.request_action_approval(
            "ACC-001",
            ActionType.PHONE_CALL,
            account
        )

        print("Compliance Check Result:")
        print(f"  Approved: {result['approved']}")
        print(f"  Risk Level: {result['risk_level']}")
        print(f"  Risk Score: {result['risk_score']:.2f}")

        for check in result['checks']:
            print(f"  - {check['type']}: {check['status']}")

    asyncio.run(demo())
