"""
Automated Retry and Re-Engagement Engine

Sophisticated retry strategies and re-engagement campaigns
for maximizing collection rates.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
import logging
import random
import math

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Payment retry strategies"""
    IMMEDIATE = "immediate"  # Retry immediately on soft failure
    EXPONENTIAL = "exponential"  # Exponential backoff
    SCHEDULED = "scheduled"  # Retry at specific times
    SMART = "smart"  # ML-based optimal timing
    CHANNEL_ROTATION = "channel_rotation"  # Try different channels


class ReEngagementType(Enum):
    """Types of re-engagement campaigns"""
    REMINDER = "reminder"  # Simple reminder
    HARDSHIP_OFFER = "hardship_offer"  # Reduced payment offer
    SETTLEMENT = "settlement"  # One-time settlement
    FRESH_START = "fresh_start"  # Reset plan terms
    WIN_BACK = "win_back"  # Long-dormant accounts
    URGENT = "urgent"  # Time-limited offer


class ContactChannel(Enum):
    """Communication channels"""
    SMS = "sms"
    EMAIL = "email"
    VOICE = "voice"
    PUSH = "push"
    MAIL = "mail"


class FailureType(Enum):
    """Types of payment failures"""
    SOFT = "soft"  # Temporary - retry immediately
    HARD = "hard"  # Permanent - don't retry same method
    FRAUD = "fraud"  # Suspected fraud - escalate
    NETWORK = "network"  # Network issues - retry soon
    BANK = "bank"  # Bank-side issue - retry later


@dataclass
class RetryAttempt:
    """Record of a retry attempt"""
    attempt_id: str
    payment_id: str
    strategy: RetryStrategy
    channel: Optional[ContactChannel]
    scheduled_at: datetime
    executed_at: Optional[datetime] = None
    success: bool = False
    response: Optional[Dict[str, Any]] = None


@dataclass
class ReEngagementCampaign:
    """A re-engagement campaign for an account"""
    campaign_id: str
    account_id: str
    campaign_type: ReEngagementType
    created_at: datetime
    expires_at: datetime
    status: str = "pending"

    # Campaign details
    offer_amount: Optional[Decimal] = None
    discount_pct: Optional[float] = None
    message_template: str = ""
    channels: List[ContactChannel] = field(default_factory=list)

    # Tracking
    messages_sent: int = 0
    opens: int = 0
    clicks: int = 0
    conversions: int = 0
    response_received: bool = False


@dataclass
class AccountEngagementProfile:
    """Profile tracking engagement history"""
    account_id: str
    total_contacts: int = 0
    total_responses: int = 0
    total_payments: int = 0
    preferred_channel: Optional[ContactChannel] = None
    best_contact_hour: Optional[int] = None
    best_contact_day: Optional[int] = None  # 0=Monday, 6=Sunday
    payment_success_rate: float = 0.0
    last_contact: Optional[datetime] = None
    last_response: Optional[datetime] = None
    last_payment: Optional[datetime] = None

    # Behavioral scores
    responsiveness_score: float = 0.5
    payment_likelihood_score: float = 0.5
    engagement_fatigue: float = 0.0


class RetryEngine:
    """
    Intelligent retry engine with multiple strategies.
    """

    # Failure classification
    FAILURE_TYPES = {
        "INSUFFICIENT_FUNDS": FailureType.SOFT,
        "CARD_DECLINED": FailureType.SOFT,
        "NETWORK_ERROR": FailureType.NETWORK,
        "TIMEOUT": FailureType.NETWORK,
        "CARD_EXPIRED": FailureType.HARD,
        "INVALID_CARD": FailureType.HARD,
        "FRAUD_SUSPECTED": FailureType.FRAUD,
        "BANK_DECLINE": FailureType.SOFT,
        "DO_NOT_HONOR": FailureType.HARD,
        "LOST_STOLEN": FailureType.FRAUD,
        "ACCOUNT_CLOSED": FailureType.HARD,
    }

    # Retry intervals by strategy (hours)
    RETRY_INTERVALS = {
        RetryStrategy.IMMEDIATE: [0.1, 0.5, 1],
        RetryStrategy.EXPONENTIAL: [4, 24, 72, 168],
        RetryStrategy.SCHEDULED: [24, 72, 168],  # 1 day, 3 days, 1 week
        RetryStrategy.SMART: [],  # Dynamically calculated
    }

    def __init__(self):
        self.attempts: List[RetryAttempt] = {}
        self.profiles: Dict[str, AccountEngagementProfile] = {}
        self.pending_retries: List[RetryAttempt] = []

    def classify_failure(self, error_code: str) -> FailureType:
        """Classify a payment failure"""
        return self.FAILURE_TYPES.get(error_code, FailureType.SOFT)

    def determine_strategy(
        self,
        failure_type: FailureType,
        attempt_count: int,
        profile: Optional[AccountEngagementProfile]
    ) -> RetryStrategy:
        """Determine the best retry strategy"""
        if failure_type == FailureType.FRAUD:
            return None  # Don't retry

        if failure_type == FailureType.HARD:
            return RetryStrategy.CHANNEL_ROTATION

        if failure_type == FailureType.NETWORK:
            return RetryStrategy.IMMEDIATE if attempt_count < 3 else RetryStrategy.EXPONENTIAL

        if profile and profile.payment_likelihood_score > 0.7:
            return RetryStrategy.SMART

        if attempt_count == 0:
            return RetryStrategy.IMMEDIATE

        return RetryStrategy.EXPONENTIAL

    def calculate_retry_time(
        self,
        strategy: RetryStrategy,
        attempt_count: int,
        profile: Optional[AccountEngagementProfile]
    ) -> datetime:
        """Calculate optimal retry time"""
        now = datetime.now()

        if strategy == RetryStrategy.IMMEDIATE:
            intervals = self.RETRY_INTERVALS[strategy]
            idx = min(attempt_count, len(intervals) - 1)
            return now + timedelta(hours=intervals[idx])

        elif strategy == RetryStrategy.EXPONENTIAL:
            # Exponential backoff with jitter
            base_hours = 4
            hours = base_hours * (2 ** attempt_count)
            jitter = random.uniform(0, hours * 0.1)
            return now + timedelta(hours=hours + jitter)

        elif strategy == RetryStrategy.SCHEDULED:
            intervals = self.RETRY_INTERVALS[strategy]
            idx = min(attempt_count, len(intervals) - 1)
            retry_time = now + timedelta(hours=intervals[idx])

            # Adjust to optimal contact time if profile exists
            if profile and profile.best_contact_hour:
                retry_time = retry_time.replace(hour=profile.best_contact_hour)

            return retry_time

        elif strategy == RetryStrategy.SMART:
            # Use profile data to find optimal time
            if profile:
                return self._calculate_smart_retry_time(profile, attempt_count)
            else:
                # Fallback to exponential
                return self.calculate_retry_time(
                    RetryStrategy.EXPONENTIAL, attempt_count, None
                )

        return now + timedelta(hours=24)

    def _calculate_smart_retry_time(
        self,
        profile: AccountEngagementProfile,
        attempt_count: int
    ) -> datetime:
        """Calculate ML-based optimal retry time"""
        now = datetime.now()

        # Base delay increases with attempts
        base_delay = 24 * (1.5 ** attempt_count)

        # Adjust based on responsiveness
        delay_multiplier = 1 + (1 - profile.responsiveness_score)
        adjusted_delay = base_delay * delay_multiplier

        retry_time = now + timedelta(hours=adjusted_delay)

        # Snap to best contact day if known
        if profile.best_contact_day is not None:
            current_day = retry_time.weekday()
            days_until_best = (profile.best_contact_day - current_day) % 7
            if days_until_best > 0 and days_until_best <= 3:
                retry_time += timedelta(days=days_until_best)

        # Snap to best contact hour
        if profile.best_contact_hour is not None:
            retry_time = retry_time.replace(
                hour=profile.best_contact_hour,
                minute=0
            )

        return retry_time

    async def schedule_retry(
        self,
        payment_id: str,
        error_code: str,
        account_id: str,
        attempt_count: int = 0
    ) -> Optional[RetryAttempt]:
        """Schedule a retry for a failed payment"""
        failure_type = self.classify_failure(error_code)

        # Get or create profile
        profile = self.profiles.get(account_id)
        if not profile:
            profile = AccountEngagementProfile(account_id=account_id)
            self.profiles[account_id] = profile

        # Determine strategy
        strategy = self.determine_strategy(failure_type, attempt_count, profile)
        if strategy is None:
            logger.warning(f"No retry for {payment_id} - {failure_type}")
            return None

        # Calculate retry time
        retry_time = self.calculate_retry_time(strategy, attempt_count, profile)

        attempt = RetryAttempt(
            attempt_id=str(uuid.uuid4()),
            payment_id=payment_id,
            strategy=strategy,
            channel=None,
            scheduled_at=retry_time
        )

        self.pending_retries.append(attempt)

        logger.info(f"Scheduled retry for {payment_id} at {retry_time} "
                   f"using {strategy.value} strategy")

        return attempt

    def update_profile_from_result(
        self,
        account_id: str,
        success: bool,
        response_received: bool,
        contact_time: datetime
    ):
        """Update engagement profile from result"""
        profile = self.profiles.get(account_id)
        if not profile:
            profile = AccountEngagementProfile(account_id=account_id)
            self.profiles[account_id] = profile

        profile.total_contacts += 1
        profile.last_contact = contact_time

        if response_received:
            profile.total_responses += 1
            profile.last_response = datetime.now()

            # Update best contact time
            if profile.best_contact_hour is None:
                profile.best_contact_hour = contact_time.hour
                profile.best_contact_day = contact_time.weekday()
            else:
                # Weighted average towards successful contact times
                profile.best_contact_hour = int(
                    0.7 * profile.best_contact_hour + 0.3 * contact_time.hour
                )
                profile.best_contact_day = int(
                    0.7 * profile.best_contact_day + 0.3 * contact_time.weekday()
                ) % 7

        if success:
            profile.total_payments += 1
            profile.last_payment = datetime.now()

        # Recalculate scores
        profile.responsiveness_score = (
            profile.total_responses / max(1, profile.total_contacts)
        )
        profile.payment_success_rate = (
            profile.total_payments / max(1, profile.total_contacts)
        )
        profile.payment_likelihood_score = (
            0.6 * profile.payment_success_rate +
            0.4 * profile.responsiveness_score
        )

        # Calculate engagement fatigue
        if profile.last_contact:
            days_since_contact = (datetime.now() - profile.last_contact).days
            recent_contacts = sum(
                1 for _ in range(min(10, profile.total_contacts))
            )
            profile.engagement_fatigue = min(1.0, recent_contacts / 10 *
                                            (1 - days_since_contact / 30))


class ReEngagementEngine:
    """
    Re-engagement campaign engine for dormant and defaulted accounts.
    """

    # Campaign templates
    TEMPLATES = {
        ReEngagementType.REMINDER: {
            "sms": "Reminder: Your payment of ${amount} is due. Pay now: {link}",
            "email_subject": "Payment Reminder",
            "email_body": "This is a friendly reminder that your payment of ${amount} is due.",
            "duration_days": 3
        },
        ReEngagementType.HARDSHIP_OFFER: {
            "sms": "We understand times are tough. We can reduce your payment to ${offer_amount}/mo. Reply YES: {link}",
            "email_subject": "Special Payment Assistance Available",
            "email_body": "We're offering reduced payment options. Pay just ${offer_amount}/month.",
            "duration_days": 14,
            "discount_range": (0.25, 0.50)
        },
        ReEngagementType.SETTLEMENT: {
            "sms": "One-time offer: Settle your ${balance} debt for just ${offer_amount}. Expires {expiry}: {link}",
            "email_subject": "Settlement Offer - Limited Time",
            "email_body": "You can settle your entire balance for ${offer_amount} - a {discount_pct}% discount.",
            "duration_days": 7,
            "discount_range": (0.30, 0.60)
        },
        ReEngagementType.FRESH_START: {
            "sms": "Fresh start: Reset your payment plan with new terms. Start at just ${offer_amount}/mo: {link}",
            "email_subject": "A Fresh Start Awaits",
            "email_body": "We're offering you a chance to start over with better terms.",
            "duration_days": 14,
            "discount_range": (0.15, 0.35)
        },
        ReEngagementType.WIN_BACK: {
            "sms": "We haven't heard from you. Special one-time offer: ${offer_amount} settles everything: {link}",
            "email_subject": "We Want You Back",
            "email_body": "It's been a while. Here's an exclusive offer to resolve your account.",
            "duration_days": 30,
            "discount_range": (0.40, 0.70)
        },
        ReEngagementType.URGENT: {
            "sms": "URGENT: Pay ${offer_amount} in 24hrs and save {discount_pct}%. After that, full amount due: {link}",
            "email_subject": "Urgent: 24-Hour Offer Expiring",
            "email_body": "Act now to save. This offer expires in 24 hours.",
            "duration_days": 1,
            "discount_range": (0.10, 0.25)
        }
    }

    def __init__(self, retry_engine: RetryEngine):
        self.retry_engine = retry_engine
        self.campaigns: Dict[str, ReEngagementCampaign] = {}
        self.account_campaigns: Dict[str, List[str]] = {}  # account_id -> campaign_ids

        # Statistics
        self.stats = {
            "campaigns_created": 0,
            "messages_sent": 0,
            "total_conversions": 0,
            "total_collected": Decimal("0")
        }

    def select_campaign_type(
        self,
        account_data: Dict[str, Any],
        profile: Optional[AccountEngagementProfile]
    ) -> ReEngagementType:
        """Select the best campaign type for an account"""
        balance = Decimal(str(account_data.get("balance", 0)))
        days_dormant = account_data.get("days_dormant", 0)
        previous_campaigns = len(self.account_campaigns.get(
            account_data.get("account_id", ""), []
        ))

        # Long dormant accounts
        if days_dormant > 180:
            return ReEngagementType.WIN_BACK

        # Recent default with history of paying
        if profile and profile.payment_success_rate > 0.5:
            return ReEngagementType.FRESH_START

        # Low balance - push for settlement
        if balance < 200:
            return ReEngagementType.SETTLEMENT

        # Multiple failed campaigns - try hardship
        if previous_campaigns >= 2:
            return ReEngagementType.HARDSHIP_OFFER

        # New default - try reminder first
        if days_dormant < 30:
            return ReEngagementType.REMINDER

        # Default: settlement
        return ReEngagementType.SETTLEMENT

    def calculate_offer_amount(
        self,
        campaign_type: ReEngagementType,
        balance: Decimal,
        profile: Optional[AccountEngagementProfile]
    ) -> Decimal:
        """Calculate optimal offer amount"""
        template = self.TEMPLATES.get(campaign_type, {})
        discount_range = template.get("discount_range", (0.0, 0.0))

        if not discount_range[1]:
            return balance

        # Base discount
        min_discount, max_discount = discount_range

        # Adjust based on profile
        if profile:
            # Lower likelihood = higher discount needed
            likelihood = profile.payment_likelihood_score
            discount = max_discount - (max_discount - min_discount) * likelihood
        else:
            discount = (min_discount + max_discount) / 2

        offer = balance * (1 - Decimal(str(discount)))
        return offer.quantize(Decimal("0.01"))

    def create_campaign(
        self,
        account_id: str,
        account_data: Dict[str, Any],
        campaign_type: Optional[ReEngagementType] = None,
        channels: Optional[List[ContactChannel]] = None
    ) -> ReEngagementCampaign:
        """Create a re-engagement campaign"""
        profile = self.retry_engine.profiles.get(account_id)

        # Auto-select campaign type if not specified
        if campaign_type is None:
            campaign_type = self.select_campaign_type(account_data, profile)

        template = self.TEMPLATES.get(campaign_type, {})
        duration = template.get("duration_days", 7)

        balance = Decimal(str(account_data.get("balance", 0)))
        offer_amount = self.calculate_offer_amount(campaign_type, balance, profile)

        discount_pct = float((balance - offer_amount) / balance * 100) if balance > 0 else 0

        # Select channels
        if channels is None:
            channels = self._select_channels(profile)

        campaign = ReEngagementCampaign(
            campaign_id=str(uuid.uuid4()),
            account_id=account_id,
            campaign_type=campaign_type,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=duration),
            offer_amount=offer_amount,
            discount_pct=discount_pct,
            message_template=template.get("sms", ""),
            channels=channels
        )

        self.campaigns[campaign.campaign_id] = campaign

        # Track by account
        if account_id not in self.account_campaigns:
            self.account_campaigns[account_id] = []
        self.account_campaigns[account_id].append(campaign.campaign_id)

        self.stats["campaigns_created"] += 1

        logger.info(f"Created {campaign_type.value} campaign for {account_id}: "
                   f"${offer_amount} ({discount_pct:.1f}% off)")

        return campaign

    def _select_channels(
        self,
        profile: Optional[AccountEngagementProfile]
    ) -> List[ContactChannel]:
        """Select communication channels"""
        if profile and profile.preferred_channel:
            # Start with preferred, then others
            channels = [profile.preferred_channel]
            for c in [ContactChannel.SMS, ContactChannel.EMAIL, ContactChannel.PUSH]:
                if c not in channels:
                    channels.append(c)
            return channels[:3]

        # Default: SMS first, then email
        return [ContactChannel.SMS, ContactChannel.EMAIL, ContactChannel.PUSH]

    async def execute_campaign(
        self,
        campaign_id: str,
        send_message_fn: Callable[[str, ContactChannel, str], bool]
    ) -> Dict[str, Any]:
        """Execute a campaign by sending messages"""
        campaign = self.campaigns.get(campaign_id)
        if not campaign:
            return {"success": False, "error": "Campaign not found"}

        if campaign.status != "pending":
            return {"success": False, "error": f"Campaign status: {campaign.status}"}

        campaign.status = "active"
        results = []

        for channel in campaign.channels:
            message = self._format_message(campaign, channel)

            try:
                success = await send_message_fn(
                    campaign.account_id,
                    channel,
                    message
                )

                campaign.messages_sent += 1
                self.stats["messages_sent"] += 1

                results.append({
                    "channel": channel.value,
                    "success": success,
                    "message_length": len(message)
                })

            except Exception as e:
                logger.error(f"Failed to send {channel.value} message: {e}")
                results.append({
                    "channel": channel.value,
                    "success": False,
                    "error": str(e)
                })

        return {
            "success": True,
            "campaign_id": campaign_id,
            "messages_sent": campaign.messages_sent,
            "results": results
        }

    def _format_message(
        self,
        campaign: ReEngagementCampaign,
        channel: ContactChannel
    ) -> str:
        """Format message for a specific channel"""
        template = self.TEMPLATES.get(campaign.campaign_type, {})

        if channel == ContactChannel.SMS:
            msg = template.get("sms", "")
        elif channel == ContactChannel.EMAIL:
            msg = template.get("email_body", "")
        else:
            msg = template.get("sms", "")  # Default to SMS format

        # Replace placeholders
        msg = msg.replace("{amount}", str(campaign.offer_amount or ""))
        msg = msg.replace("{offer_amount}", str(campaign.offer_amount or ""))
        msg = msg.replace("{discount_pct}", f"{campaign.discount_pct:.0f}")
        msg = msg.replace("{expiry}", campaign.expires_at.strftime("%m/%d"))
        msg = msg.replace("{link}", f"https://pay.quan.ai/c/{campaign.campaign_id[:8]}")

        return msg

    def record_response(
        self,
        campaign_id: str,
        response_type: str,  # "open", "click", "conversion"
        payment_amount: Optional[Decimal] = None
    ):
        """Record a response to a campaign"""
        campaign = self.campaigns.get(campaign_id)
        if not campaign:
            return

        if response_type == "open":
            campaign.opens += 1
        elif response_type == "click":
            campaign.clicks += 1
            campaign.response_received = True
        elif response_type == "conversion":
            campaign.conversions += 1
            campaign.response_received = True
            campaign.status = "converted"

            self.stats["total_conversions"] += 1
            if payment_amount:
                self.stats["total_collected"] += payment_amount

            # Update profile
            self.retry_engine.update_profile_from_result(
                campaign.account_id,
                success=True,
                response_received=True,
                contact_time=datetime.now()
            )

    def get_campaign_performance(self) -> Dict[str, Any]:
        """Get overall campaign performance metrics"""
        if not self.campaigns:
            return {"campaigns": 0, "conversion_rate": 0}

        total_campaigns = len(self.campaigns)
        active_campaigns = sum(1 for c in self.campaigns.values()
                              if c.status == "active")
        converted_campaigns = sum(1 for c in self.campaigns.values()
                                 if c.status == "converted")

        total_messages = sum(c.messages_sent for c in self.campaigns.values())
        total_opens = sum(c.opens for c in self.campaigns.values())
        total_clicks = sum(c.clicks for c in self.campaigns.values())
        total_conversions = sum(c.conversions for c in self.campaigns.values())

        # Performance by campaign type
        type_performance = {}
        for campaign_type in ReEngagementType:
            type_campaigns = [c for c in self.campaigns.values()
                            if c.campaign_type == campaign_type]
            if type_campaigns:
                type_conversions = sum(c.conversions for c in type_campaigns)
                type_performance[campaign_type.value] = {
                    "campaigns": len(type_campaigns),
                    "conversions": type_conversions,
                    "rate": type_conversions / len(type_campaigns)
                }

        return {
            "total_campaigns": total_campaigns,
            "active": active_campaigns,
            "converted": converted_campaigns,
            "conversion_rate": converted_campaigns / total_campaigns if total_campaigns > 0 else 0,
            "messages": {
                "sent": total_messages,
                "opens": total_opens,
                "open_rate": total_opens / total_messages if total_messages > 0 else 0,
                "clicks": total_clicks,
                "click_rate": total_clicks / total_messages if total_messages > 0 else 0
            },
            "by_type": type_performance,
            "total_collected": str(self.stats["total_collected"])
        }


class AutomatedCollectionOrchestrator:
    """
    Orchestrates the full automated collection flow:
    1. Initial contact
    2. Payment attempt
    3. Retry on failure
    4. Re-engagement on prolonged failure
    5. Continuous monitoring
    """

    def __init__(self):
        self.retry_engine = RetryEngine()
        self.re_engagement_engine = ReEngagementEngine(self.retry_engine)

        # Collection state
        self.active_accounts: Dict[str, Dict[str, Any]] = {}
        self.collection_queue: List[str] = []

        # Configuration
        self.max_retries = 3
        self.re_engagement_threshold_days = 14
        self.campaign_cooldown_days = 30

    async def process_account(
        self,
        account_id: str,
        account_data: Dict[str, Any],
        payment_fn: Callable,
        message_fn: Callable
    ) -> Dict[str, Any]:
        """Process a single account through the collection flow"""
        self.active_accounts[account_id] = {
            "data": account_data,
            "status": "processing",
            "started_at": datetime.now(),
            "attempts": 0,
            "collected": Decimal("0")
        }

        # Attempt payment
        payment_result = await payment_fn(account_id, account_data)

        if payment_result.get("success"):
            # Success!
            amount = Decimal(str(payment_result.get("amount", 0)))
            self.active_accounts[account_id]["collected"] = amount
            self.active_accounts[account_id]["status"] = "collected"

            self.retry_engine.update_profile_from_result(
                account_id, True, True, datetime.now()
            )

            return {"status": "success", "amount": amount}

        # Failed - schedule retry
        error_code = payment_result.get("error_code", "UNKNOWN")
        attempt_count = self.active_accounts[account_id]["attempts"]

        if attempt_count < self.max_retries:
            retry = await self.retry_engine.schedule_retry(
                payment_id=f"{account_id}-{attempt_count}",
                error_code=error_code,
                account_id=account_id,
                attempt_count=attempt_count
            )

            self.active_accounts[account_id]["attempts"] += 1
            self.active_accounts[account_id]["status"] = "retrying"
            self.active_accounts[account_id]["next_retry"] = retry.scheduled_at if retry else None

            return {
                "status": "retry_scheduled",
                "next_attempt": retry.scheduled_at.isoformat() if retry else None
            }

        # Max retries reached - create re-engagement campaign
        campaign = self.re_engagement_engine.create_campaign(
            account_id=account_id,
            account_data=account_data
        )

        await self.re_engagement_engine.execute_campaign(
            campaign.campaign_id,
            message_fn
        )

        self.active_accounts[account_id]["status"] = "re_engaging"
        self.active_accounts[account_id]["campaign_id"] = campaign.campaign_id

        return {
            "status": "re_engagement_started",
            "campaign_id": campaign.campaign_id,
            "campaign_type": campaign.campaign_type.value,
            "offer_amount": str(campaign.offer_amount)
        }

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get overall collection statistics"""
        total_accounts = len(self.active_accounts)
        collected = sum(
            a["collected"] for a in self.active_accounts.values()
        )

        status_counts = {}
        for account in self.active_accounts.values():
            status = account["status"]
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_accounts": total_accounts,
            "total_collected": str(collected),
            "by_status": status_counts,
            "retry_stats": {
                "pending_retries": len(self.retry_engine.pending_retries),
                "profiles": len(self.retry_engine.profiles)
            },
            "campaign_stats": self.re_engagement_engine.get_campaign_performance()
        }


# Integration helper

async def create_collection_system():
    """Create a fully configured collection system"""
    orchestrator = AutomatedCollectionOrchestrator()

    # Configure event handlers
    def on_payment_received(account_id: str, amount: Decimal):
        logger.info(f"Payment received for {account_id}: ${amount}")

    def on_campaign_converted(campaign_id: str):
        logger.info(f"Campaign {campaign_id} converted!")

    return orchestrator


if __name__ == "__main__":
    # Demo
    async def demo():
        orchestrator = await create_collection_system()

        # Simulate accounts
        for i in range(10):
            account = {
                "account_id": f"ACC-{i}",
                "balance": 100 + i * 50,
                "days_dormant": i * 10
            }

            async def mock_payment(aid, data):
                import random
                return {"success": random.random() < 0.3, "amount": data.get("balance", 0)}

            async def mock_message(aid, channel, msg):
                return True

            result = await orchestrator.process_account(
                f"ACC-{i}",
                account,
                mock_payment,
                mock_message
            )
            print(f"Account ACC-{i}: {result['status']}")

        print("\nCollection Stats:")
        print(orchestrator.get_collection_stats())

    asyncio.run(demo())
