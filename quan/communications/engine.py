"""Multi-channel communication with AI personalization"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
import asyncio
import logging
import re

from quan.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CommunicationResult:
    """Result of a communication attempt"""

    success: bool
    channel: str
    message_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class CommunicationEngine:
    """Multi-channel communication with AI personalization"""

    def __init__(self):
        self._twilio_client = None
        self._sendgrid_client = None
        self._tts_client = None
        self.nlp_generator = NLPGenerator()
        self._templates = self._load_templates()

    def _get_twilio(self):
        """Lazy load Twilio client"""
        if self._twilio_client is None and settings.twilio_account_sid:
            try:
                from twilio.rest import Client
                self._twilio_client = Client(
                    settings.twilio_account_sid,
                    settings.twilio_auth_token,
                )
            except ImportError:
                logger.warning("Twilio not installed")
        return self._twilio_client

    def _get_sendgrid(self):
        """Lazy load SendGrid client"""
        if self._sendgrid_client is None and settings.sendgrid_api_key:
            try:
                import sendgrid
                self._sendgrid_client = sendgrid.SendGridAPIClient(
                    settings.sendgrid_api_key,
                )
            except ImportError:
                logger.warning("SendGrid not installed")
        return self._sendgrid_client

    def _load_templates(self) -> Dict[str, Dict[str, str]]:
        """Load message templates"""
        return {
            "sms_collection_low": {
                "body": "Hi {name}, this is QUAN Recovery regarding your {creditor} account. "
                       "We have a settlement offer available. Reply YES to discuss options. "
                       "This is an attempt to collect a debt.",
            },
            "sms_collection_medium": {
                "body": "Hi {name}, your {creditor} balance of ${balance} has a special "
                       "settlement available for a limited time. Reply YES or call {phone}. "
                       "This is an attempt to collect a debt by QUAN Recovery, a debt collector.",
            },
            "sms_collection_high": {
                "body": "{name}, action required on your {creditor} account. Settlement options "
                       "are expiring soon. Reply YES now. This is a debt collector.",
            },
            "email_collection_low": {
                "subject": "Settlement Opportunity - {creditor}",
                "body": """Dear {name},

We're reaching out regarding your {creditor} account with a current balance of ${balance}.

We have several flexible settlement options available that could significantly reduce your balance.

Please reply to this email or call us at {phone} to discuss your options.

This communication is from QUAN Recovery, a debt collection company. This is an attempt to collect a debt and any information obtained will be used for that purpose.

Best regards,
QUAN Recovery Team
""",
            },
            "email_collection_medium": {
                "subject": "Important: {creditor} Account - Action Needed",
                "body": """Dear {name},

Your {creditor} account balance of ${balance} requires your attention.

We're authorized to offer settlement options that could reduce what you owe. These options are time-sensitive.

To discuss your personalized payment options:
- Reply to this email
- Call us at {phone}
- Visit: {payment_url}

This communication is from QUAN Recovery, a debt collection company. This is an attempt to collect a debt and any information obtained will be used for that purpose.

QUAN Recovery Team
""",
            },
        }

    async def generate_message(
        self,
        account: Dict,
        channel: str,
        strategy: Dict,
    ) -> str:
        """Generate AI-personalized message"""

        template_id = strategy.get("template", f"{channel}_collection_medium")
        template = self._templates.get(template_id, {})

        # Get appropriate content
        if channel == "email":
            content = template.get("body", "")
        else:
            content = template.get("body", "")

        # Personalize with account data
        personalization = {
            "name": account.get("debtor_name", "").split()[0],  # First name
            "creditor": account.get("original_creditor", "your creditor"),
            "balance": f"{account.get('balance', 0):.2f}",
            "phone": settings.twilio_phone_number or "1-800-QUAN",
            "payment_url": f"https://pay.quanrecovery.com/{account.get('account_id', '')}",
        }

        message = content.format(**personalization)

        # AI enhancement if configured
        if strategy.get("use_ai_personalization"):
            message = await self.nlp_generator.personalize(
                account=account,
                template=message,
                tone=strategy.get("tone", "professional"),
                urgency=strategy.get("urgency", "medium"),
            )

        # Compliance check
        message = await self._ensure_compliance(message, channel, account.get("debtor_state", ""))

        return message

    async def _ensure_compliance(
        self,
        message: str,
        channel: str,
        state: str,
    ) -> str:
        """Ensure message is compliant with regulations"""

        # Check for mini-miranda
        mini_miranda_phrases = [
            "debt collector",
            "attempt to collect a debt",
            "used for that purpose",
        ]

        has_disclosure = any(phrase in message.lower() for phrase in mini_miranda_phrases)

        if not has_disclosure and channel != "sms":
            message += "\n\nThis is a communication from a debt collector."

        # Remove prohibited content
        prohibited = ["arrest", "jail", "prison", "criminal prosecution"]
        for word in prohibited:
            message = re.sub(rf"\b{word}\b", "", message, flags=re.IGNORECASE)

        return message

    async def send_sms(
        self,
        account: Dict,
        message: str,
    ) -> CommunicationResult:
        """Send SMS with delivery tracking"""

        phone = account.get("debtor_phone")
        if not phone:
            return CommunicationResult(
                success=False,
                channel="sms",
                error="No phone number",
            )

        twilio = self._get_twilio()
        if not twilio:
            logger.warning("Twilio not configured, SMS not sent")
            return CommunicationResult(
                success=False,
                channel="sms",
                error="Twilio not configured",
            )

        try:
            msg = twilio.messages.create(
                body=message,
                from_=settings.twilio_phone_number,
                to=phone,
            )

            await self._record_communication({
                "account_id": account.get("account_id"),
                "channel": "sms",
                "message_id": msg.sid,
                "content": message,
                "timestamp": datetime.utcnow().isoformat(),
            })

            return CommunicationResult(
                success=True,
                channel="sms",
                message_id=msg.sid,
            )

        except Exception as e:
            logger.error(f"SMS send error: {e}")
            return CommunicationResult(
                success=False,
                channel="sms",
                error=str(e),
            )

    async def send_email(
        self,
        account: Dict,
        subject: str,
        body: str,
    ) -> CommunicationResult:
        """Send email with tracking"""

        email = account.get("debtor_email")
        if not email:
            return CommunicationResult(
                success=False,
                channel="email",
                error="No email address",
            )

        sendgrid = self._get_sendgrid()
        if not sendgrid:
            logger.warning("SendGrid not configured, email not sent")
            return CommunicationResult(
                success=False,
                channel="email",
                error="SendGrid not configured",
            )

        try:
            from sendgrid.helpers.mail import Mail

            message = Mail(
                from_email=settings.sendgrid_from_email,
                to_emails=email,
                subject=subject,
                plain_text_content=body,
            )

            response = sendgrid.send(message)

            await self._record_communication({
                "account_id": account.get("account_id"),
                "channel": "email",
                "message_id": response.headers.get("X-Message-Id"),
                "subject": subject,
                "timestamp": datetime.utcnow().isoformat(),
            })

            return CommunicationResult(
                success=True,
                channel="email",
                message_id=response.headers.get("X-Message-Id"),
            )

        except Exception as e:
            logger.error(f"Email send error: {e}")
            return CommunicationResult(
                success=False,
                channel="email",
                error=str(e),
            )

    async def make_ai_call(
        self,
        account: Dict,
        script: Dict,
    ) -> CommunicationResult:
        """Make AI-powered voice call"""

        phone = account.get("debtor_phone")
        if not phone:
            return CommunicationResult(
                success=False,
                channel="voice",
                error="No phone number",
            )

        twilio = self._get_twilio()
        if not twilio:
            return CommunicationResult(
                success=False,
                channel="voice",
                error="Twilio not configured",
            )

        try:
            # Would set up TwiML for dynamic call handling
            call = twilio.calls.create(
                to=phone,
                from_=settings.twilio_phone_number,
                url=f"https://api.quanrecovery.com/voice/twiml/{account.get('account_id')}",
                method="POST",
                record=True,
            )

            return CommunicationResult(
                success=True,
                channel="voice",
                message_id=call.sid,
            )

        except Exception as e:
            logger.error(f"Voice call error: {e}")
            return CommunicationResult(
                success=False,
                channel="voice",
                error=str(e),
            )

    async def _record_communication(self, record: Dict) -> None:
        """Record communication to database"""
        # Would store in database
        logger.info(f"Communication recorded: {record.get('channel')} to {record.get('account_id')}")


class NLPGenerator:
    """Advanced NLP for message generation"""

    def __init__(self):
        self._model = None

    async def personalize(
        self,
        account: Dict,
        template: str,
        tone: str,
        urgency: str,
    ) -> str:
        """Generate personalized message"""

        # In production, would use GPT or similar
        # For now, return template with minor adjustments

        if urgency == "high":
            template = template.replace("available", "expiring soon")

        if tone == "empathetic":
            template = template.replace(
                "requires your attention",
                "- we understand times can be difficult and want to help",
            )

        return template

    async def analyze_response(
        self,
        message: str,
    ) -> Dict[str, Any]:
        """Analyze debtor response"""

        message_lower = message.lower()

        # Simple intent detection
        intents = {
            "payment_ready": any(w in message_lower for w in ["pay", "payment", "settle"]),
            "hardship": any(w in message_lower for w in ["can't", "cannot", "hardship", "unemployed"]),
            "dispute": any(w in message_lower for w in ["dispute", "not mine", "fraud", "wrong"]),
            "cease": any(w in message_lower for w in ["stop", "cease", "desist", "lawyer"]),
            "positive": any(w in message_lower for w in ["yes", "ok", "sure", "interested"]),
            "negative": any(w in message_lower for w in ["no", "never", "leave me alone"]),
        }

        # Sentiment (simplified)
        positive_words = ["thank", "yes", "ok", "great", "help"]
        negative_words = ["no", "stop", "angry", "frustrated", "sue"]

        positive_count = sum(1 for w in positive_words if w in message_lower)
        negative_count = sum(1 for w in negative_words if w in message_lower)

        if positive_count > negative_count:
            sentiment = "positive"
        elif negative_count > positive_count:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        return {
            "intents": intents,
            "sentiment": sentiment,
            "requires_human": intents.get("dispute") or intents.get("cease"),
        }
