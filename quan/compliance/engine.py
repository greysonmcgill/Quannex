"""Real-time compliance monitoring and enforcement"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import re
import logging

from quan.config import settings

logger = logging.getLogger(__name__)


# State-specific collection rules
STATE_RULES = {
    "CA": {
        "sol_years": 4,
        "requires_license": True,
        "additional_disclosures": True,
    },
    "NY": {
        "sol_years": 6,
        "requires_license": True,
        "additional_disclosures": True,
    },
    "TX": {
        "sol_years": 4,
        "requires_license": False,
    },
    "FL": {
        "sol_years": 5,
        "requires_license": True,
    },
}


class ComplianceEngine:
    """Real-time compliance monitoring and enforcement"""

    # Regulation F limits
    MAX_WEEKLY_ATTEMPTS = 7
    MAX_DAILY_CONVERSATIONS = 1
    CONTACT_HOURS_START = 8
    CONTACT_HOURS_END = 21

    def __init__(self):
        self.rules = self._load_compliance_rules()
        self.contact_tracker = ContactTracker()
        self.consent_manager = ConsentManager()

    def _load_compliance_rules(self) -> Dict[str, Any]:
        """Load compliance rules from configuration"""
        return {
            "fdcpa": {
                "mini_miranda_required": True,
                "prohibited_terms": [
                    "arrest", "jail", "prison", "criminal",
                    "wage garnishment",  # unless actually authorized
                    "sue",  # unless actually intending
                ],
                "required_disclosures": [
                    "debt collector",
                    "attempt to collect a debt",
                ],
            },
            "tcpa": {
                "require_consent_autodialer": True,
                "require_consent_prerecorded": True,
            },
            "reg_f": {
                "max_calls_per_week": 7,
                "max_conversations_per_day": 1,
                "contact_hours_start": 8,
                "contact_hours_end": 21,
            },
        }

    async def validate_contact(
        self,
        account: Dict,
        channel: str,
        timestamp: Optional[datetime] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Validate contact attempt for compliance"""

        if timestamp is None:
            timestamp = datetime.utcnow()

        # Check time restrictions (8am-9pm local time)
        if not self._check_time_restriction(account, timestamp):
            return False, "Outside allowed contact hours (8am-9pm)"

        # Check frequency limits (Reg F: 7 attempts per week)
        attempts = await self.contact_tracker.get_week_attempts(
            account.get("account_id")
        )
        if attempts >= self.MAX_WEEKLY_ATTEMPTS:
            return False, "Weekly attempt limit reached (7)"

        # Check daily conversation limit
        conversations = await self.contact_tracker.get_day_conversations(
            account.get("account_id")
        )
        if conversations >= self.MAX_DAILY_CONVERSATIONS:
            return False, "Daily conversation limit reached (1)"

        # Check consent for automated calls/texts
        if channel in ["sms", "voice_auto"]:
            consent = await self.consent_manager.check_consent(account, channel)
            if not consent:
                return False, f"No consent for automated {channel}"

        # Check cease and desist
        if account.get("cease_desist"):
            return False, "Cease and desist active"

        # Check bankruptcy
        if account.get("bankruptcy_filed"):
            return False, "Bankruptcy protection active"

        # Check active military (SCRA)
        if account.get("active_military"):
            return False, "SCRA protection active"

        # State-specific rules
        state_valid = await self._check_state_rules(account, channel, timestamp)
        if not state_valid[0]:
            return state_valid

        return True, None

    def _check_time_restriction(
        self,
        account: Dict,
        timestamp: datetime,
    ) -> bool:
        """Check if contact is within allowed hours"""

        # Would convert to debtor's local time
        # For now, use UTC
        hour = timestamp.hour

        return self.CONTACT_HOURS_START <= hour < self.CONTACT_HOURS_END

    async def _check_state_rules(
        self,
        account: Dict,
        channel: str,
        timestamp: datetime,
    ) -> Tuple[bool, Optional[str]]:
        """Check state-specific compliance rules"""

        state = account.get("debtor_state", "").upper()
        rules = STATE_RULES.get(state, {})

        # Check statute of limitations
        charge_off_date = account.get("charge_off_date")
        if charge_off_date:
            sol_years = rules.get("sol_years", 6)
            if isinstance(charge_off_date, str):
                charge_off_date = datetime.fromisoformat(charge_off_date)

            sol_date = charge_off_date + timedelta(days=sol_years * 365)
            if timestamp > sol_date:
                return False, f"Past statute of limitations ({state}: {sol_years} years)"

        return True, None

    async def validate_message(
        self,
        message: str,
        channel: str,
        state: str,
        is_initial: bool = False,
    ) -> Tuple[bool, List[str]]:
        """Validate message content for compliance"""

        violations = []

        # Check for required disclosures
        if is_initial or channel == "initial_contact":
            if "debt collector" not in message.lower():
                violations.append("Missing debt collector disclosure")

            if "attempt to collect" not in message.lower():
                violations.append("Missing mini-miranda warning")

        # Check for prohibited content
        prohibited_patterns = self.rules["fdcpa"]["prohibited_terms"]

        for pattern in prohibited_patterns:
            if re.search(rf"\b{pattern}\b", message, re.IGNORECASE):
                violations.append(f"Prohibited content: {pattern}")

        # Check message length for SMS
        if channel == "sms" and len(message) > 160:
            # Warning only - may need multiple segments
            logger.warning(f"SMS message exceeds 160 chars: {len(message)}")

        # State-specific requirements
        state_violations = await self._check_state_message_rules(message, state)
        violations.extend(state_violations)

        return len(violations) == 0, violations

    async def _check_state_message_rules(
        self,
        message: str,
        state: str,
    ) -> List[str]:
        """Check state-specific message requirements"""

        violations = []
        rules = STATE_RULES.get(state.upper(), {})

        if rules.get("additional_disclosures"):
            # Some states require additional disclosures
            pass

        return violations

    async def validate_settlement(
        self,
        account: Dict,
        settlement_amount: float,
    ) -> Tuple[bool, Optional[str]]:
        """Validate settlement offer is compliant"""

        balance = account.get("balance", 0)

        if settlement_amount <= 0:
            return False, "Settlement amount must be positive"

        if settlement_amount > balance:
            return False, "Settlement cannot exceed balance"

        # Check minimum settlement (business rule)
        min_settlement = balance * 0.20  # 20% minimum
        if settlement_amount < min_settlement:
            return False, f"Below minimum authority ({min_settlement:.2f})"

        return True, None


class ContactTracker:
    """Track contact attempts for compliance"""

    def __init__(self):
        self._attempts: Dict[str, List[Dict]] = {}

    async def record_attempt(
        self,
        account_id: str,
        channel: str,
        conversation_occurred: bool = False,
    ) -> None:
        """Record a contact attempt"""

        if account_id not in self._attempts:
            self._attempts[account_id] = []

        self._attempts[account_id].append({
            "timestamp": datetime.utcnow().isoformat(),
            "channel": channel,
            "conversation": conversation_occurred,
        })

    async def get_week_attempts(self, account_id: str) -> int:
        """Get number of attempts in past week"""

        if account_id not in self._attempts:
            return 0

        week_ago = datetime.utcnow() - timedelta(days=7)

        return sum(
            1 for a in self._attempts[account_id]
            if datetime.fromisoformat(a["timestamp"]) > week_ago
        )

    async def get_day_conversations(self, account_id: str) -> int:
        """Get number of conversations today"""

        if account_id not in self._attempts:
            return 0

        today = datetime.utcnow().date()

        return sum(
            1 for a in self._attempts[account_id]
            if datetime.fromisoformat(a["timestamp"]).date() == today
            and a.get("conversation")
        )


class ConsentManager:
    """Manage consent for communications"""

    def __init__(self):
        self._consents: Dict[str, Dict[str, bool]] = {}

    async def check_consent(
        self,
        account: Dict,
        channel: str,
    ) -> bool:
        """Check if we have consent for channel"""

        account_id = account.get("account_id")

        # Check stored consent
        stored = self._consents.get(account_id, {})
        if channel in stored:
            return stored[channel]

        # Check account data for consent flags
        consent_map = {
            "sms": account.get("sms_consent", False),
            "voice_auto": account.get("voice_consent", False),
            "email": True,  # Generally allowed
        }

        return consent_map.get(channel, False)

    async def record_consent(
        self,
        account_id: str,
        channel: str,
        granted: bool,
    ) -> None:
        """Record consent grant or revocation"""

        if account_id not in self._consents:
            self._consents[account_id] = {}

        self._consents[account_id][channel] = granted
        logger.info(f"Consent {'granted' if granted else 'revoked'}: {account_id} - {channel}")

    async def revoke_all(self, account_id: str) -> None:
        """Revoke all consents (cease and desist)"""

        self._consents[account_id] = {
            "sms": False,
            "voice_auto": False,
            "voice": False,
            "email": False,
        }
        logger.info(f"All consents revoked for {account_id}")


class ContactGovernor:
    """Governs contact frequency and timing per Regulation F"""

    def __init__(self):
        self.tracker = ContactTracker()

    async def can_contact_now(
        self,
        account: Dict,
        channel: Optional[str] = None,
    ) -> bool:
        """Check if contact is allowed right now"""

        account_id = account.get("account_id")

        # Check daily conversation limit
        conversations = await self.tracker.get_day_conversations(account_id)
        if conversations >= 1:
            return False

        # Check weekly attempt limit
        attempts = await self.tracker.get_week_attempts(account_id)
        if attempts >= 7:
            return False

        # Check time of day
        now = datetime.utcnow()
        if now.hour < 8 or now.hour >= 21:
            return False

        # Channel-specific limits
        if channel == "sms":
            # Additional SMS limits could be added here
            pass

        return True

    async def record_attempt(
        self,
        account: Dict,
        contact: Dict,
        result: Dict,
    ) -> None:
        """Record contact attempt for compliance tracking"""

        await self.tracker.record_attempt(
            account_id=account.get("account_id"),
            channel=contact.get("channel"),
            conversation_occurred=result.get("response_received", False),
        )
