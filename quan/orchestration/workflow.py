"""Distributed orchestration of collection workflows"""

from typing import Dict, List, Optional, Any
import asyncio
from enum import Enum
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging
import uuid

from quan.config import settings

logger = logging.getLogger(__name__)


class CollectionStage(Enum):
    """Stages in the collection workflow"""

    INTAKE = "intake"
    ENRICHMENT = "enrichment"
    SCORING = "scoring"
    SKIP_TRACE = "skip_trace"
    INITIAL_CONTACT = "initial_contact"
    FOLLOW_UP = "follow_up"
    NEGOTIATION = "negotiation"
    SETTLEMENT = "settlement"
    PAYMENT = "payment"
    CLOSURE = "closure"


@dataclass
class Campaign:
    """Collection campaign for a portfolio"""

    id: str
    portfolio_id: str
    accounts: List[Dict]
    stage: CollectionStage
    start_time: datetime
    client_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> timedelta:
        return datetime.utcnow() - self.start_time


class StageHandler:
    """Base class for stage handlers"""

    async def process(self, account: Dict, campaign: Campaign) -> Dict:
        """Process account through this stage"""
        raise NotImplementedError


class IntakeHandler(StageHandler):
    """Handle intake stage"""

    async def process(self, account: Dict, campaign: Campaign) -> Dict:
        return {
            "stage_completed": "intake",
            "timestamp": datetime.utcnow().isoformat(),
            "validated": True,
        }


class EnrichmentHandler(StageHandler):
    """Handle data enrichment stage"""

    async def process(self, account: Dict, campaign: Campaign) -> Dict:
        # Would call enrichment services
        return {
            "stage_completed": "enrichment",
            "enriched_fields": ["phone", "email", "address"],
            "timestamp": datetime.utcnow().isoformat(),
        }


class ScoringHandler(StageHandler):
    """Handle quantum scoring stage"""

    async def process(self, account: Dict, campaign: Campaign) -> Dict:
        from quan.quantum import QuantumEngine

        engine = QuantumEngine()
        state = engine.quantum_analyze([account])
        strategies = engine.collapse_to_strategy(state)

        if strategies:
            strategy = strategies[0]
            return {
                "stage_completed": "scoring",
                "recovery_probability": strategy.recovery_probability,
                "optimal_channels": strategy.optimal_channels,
                "timestamp": datetime.utcnow().isoformat(),
            }

        return {"stage_completed": "scoring", "error": "No strategy generated"}


class ContactHandler(StageHandler):
    """Handle contact stages"""

    async def process(self, account: Dict, campaign: Campaign) -> Dict:
        # Would trigger contact orchestrator
        return {
            "stage_completed": "contact",
            "contact_attempted": True,
            "channel": "sms",
            "timestamp": datetime.utcnow().isoformat(),
        }


class QuantumOrchestrator:
    """Distributed orchestration of collection workflows"""

    def __init__(self):
        self.active_campaigns: Dict[str, Campaign] = {}
        self.stage_handlers = self._initialize_handlers()
        self._event_store = EventStore()

    def _initialize_handlers(self) -> Dict[CollectionStage, StageHandler]:
        """Initialize stage handlers"""
        return {
            CollectionStage.INTAKE: IntakeHandler(),
            CollectionStage.ENRICHMENT: EnrichmentHandler(),
            CollectionStage.SCORING: ScoringHandler(),
            CollectionStage.INITIAL_CONTACT: ContactHandler(),
            CollectionStage.FOLLOW_UP: ContactHandler(),
            CollectionStage.NEGOTIATION: ContactHandler(),
        }

    async def process_portfolio(
        self,
        portfolio_id: str,
        accounts: List[Dict],
        client_id: str,
    ) -> Campaign:
        """Main orchestration flow for portfolio processing"""

        campaign = Campaign(
            id=f"campaign_{uuid.uuid4().hex[:12]}",
            portfolio_id=portfolio_id,
            accounts=accounts,
            stage=CollectionStage.INTAKE,
            start_time=datetime.utcnow(),
            client_id=client_id,
        )

        self.active_campaigns[campaign.id] = campaign
        logger.info(f"Started campaign {campaign.id} for {len(accounts)} accounts")

        # Process through stages
        stages_to_run = [
            CollectionStage.INTAKE,
            CollectionStage.ENRICHMENT,
            CollectionStage.SCORING,
            CollectionStage.INITIAL_CONTACT,
        ]

        for stage in stages_to_run:
            campaign.stage = stage
            logger.info(f"Campaign {campaign.id} entering stage: {stage.value}")

            # Parallel processing of accounts
            tasks = []
            for account in accounts:
                task = self._process_account_stage(account, stage, campaign)
                tasks.append(task)

            # Wait for stage completion
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Update accounts with results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error processing account: {result}")
                    accounts[i]["stage_error"] = str(result)
                else:
                    accounts[i].update(result)

            # Check stage gates
            if not self._should_continue(campaign, stage):
                logger.info(f"Campaign {campaign.id} stopped at stage: {stage.value}")
                break

        campaign.metadata["completed_at"] = datetime.utcnow().isoformat()
        return campaign

    async def _process_account_stage(
        self,
        account: Dict,
        stage: CollectionStage,
        campaign: Campaign,
    ) -> Dict:
        """Process single account through stage"""

        handler = self.stage_handlers.get(stage)
        if not handler:
            return {"error": f"No handler for stage {stage.value}"}

        try:
            result = await handler.process(account, campaign)

            # Log to event store
            await self._event_store.log({
                "account_id": account.get("account_id"),
                "campaign_id": campaign.id,
                "stage": stage.value,
                "result": result,
                "timestamp": datetime.utcnow().isoformat(),
            })

            return result

        except Exception as e:
            logger.error(f"Stage error for account {account.get('account_id')}: {e}")
            return {"error": str(e), "stage": stage.value}

    def _should_continue(self, campaign: Campaign, stage: CollectionStage) -> bool:
        """Check if campaign should continue to next stage"""

        # Check for too many errors
        error_count = sum(
            1 for acc in campaign.accounts
            if acc.get("stage_error")
        )

        if error_count > len(campaign.accounts) * 0.5:
            logger.warning(f"Campaign {campaign.id}: >50% errors, stopping")
            return False

        return True

    async def get_campaign_status(self, campaign_id: str) -> Optional[Dict]:
        """Get status of a campaign"""
        campaign = self.active_campaigns.get(campaign_id)
        if not campaign:
            return None

        return {
            "id": campaign.id,
            "stage": campaign.stage.value,
            "accounts": len(campaign.accounts),
            "duration_seconds": campaign.duration.total_seconds(),
            "start_time": campaign.start_time.isoformat(),
        }


class ContactOrchestrator:
    """Orchestrates multi-channel contact campaigns"""

    def __init__(self):
        self.channels = {}  # Would be initialized with channel handlers
        self.contact_governor = ContactGovernor()

    async def execute_campaign(
        self,
        account: Dict,
        strategy: Dict,
    ) -> List[Dict]:
        """Execute multi-channel contact campaign"""

        from quan.compliance import ComplianceEngine

        compliance = ComplianceEngine()

        # Check contact permissions
        permissions = await self._get_permissions(account)

        # Build contact sequence from strategy
        sequence = strategy.get("contact_sequence", [])

        results = []
        for step in sequence:
            # Check timing restrictions
            can_contact, reason = await compliance.validate_contact(
                account,
                step["channel"],
            )

            if not can_contact:
                logger.info(f"Cannot contact {account['account_id']}: {reason}")
                await self._schedule_later(step, account)
                continue

            # Execute contact
            result = await self._execute_contact(account, step)
            results.append(result)

            # Record attempt
            await self.contact_governor.record_attempt(account, step, result)

            # Check for response
            if result.get("response_received"):
                break

            # Wait between attempts
            wait_time = step.get("delay_hours", 24) * 3600
            # In production, this would schedule next contact, not sleep
            # await asyncio.sleep(wait_time)

        return results

    async def _get_permissions(self, account: Dict) -> Dict[str, bool]:
        """Get contact permissions for account"""
        return {
            "sms": account.get("sms_consent", False),
            "email": True,  # Email generally allowed
            "voice": account.get("voice_consent", True),
            "mail": True,
        }

    async def _execute_contact(self, account: Dict, step: Dict) -> Dict:
        """Execute a single contact attempt"""
        channel = step.get("channel")

        # Would call actual channel handlers
        return {
            "channel": channel,
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "response_received": False,
        }

    async def _schedule_later(self, step: Dict, account: Dict) -> None:
        """Schedule contact for later"""
        # Would add to scheduling queue
        pass


class ContactGovernor:
    """Governs contact frequency and timing per Regulation F"""

    def __init__(self):
        self._contact_log: Dict[str, List[Dict]] = {}

    async def can_contact_now(
        self,
        account: Dict,
        channel: Optional[str] = None,
    ) -> bool:
        """Check if contact is allowed right now"""

        account_id = account.get("account_id")

        # Check daily conversation limit
        today = datetime.utcnow().date()
        today_contacts = [
            c for c in self._contact_log.get(account_id, [])
            if datetime.fromisoformat(c["timestamp"]).date() == today
            and c.get("conversation_occurred")
        ]

        if len(today_contacts) >= 1:
            return False

        # Check weekly attempt limit (Regulation F: 7 per week)
        week_ago = datetime.utcnow() - timedelta(days=7)
        week_contacts = [
            c for c in self._contact_log.get(account_id, [])
            if datetime.fromisoformat(c["timestamp"]) > week_ago
        ]

        if len(week_contacts) >= 7:
            return False

        # Check time of day (8am-9pm debtor's time)
        debtor_hour = datetime.utcnow().hour  # Would convert to debtor's timezone
        if debtor_hour < settings.contact_hours_start or debtor_hour >= settings.contact_hours_end:
            return False

        return True

    async def record_attempt(
        self,
        account: Dict,
        contact: Dict,
        result: Dict,
    ) -> None:
        """Record contact attempt for compliance tracking"""

        account_id = account.get("account_id")

        if account_id not in self._contact_log:
            self._contact_log[account_id] = []

        self._contact_log[account_id].append({
            "timestamp": datetime.utcnow().isoformat(),
            "channel": contact.get("channel"),
            "result": result,
            "conversation_occurred": result.get("response_received", False),
        })


class EventStore:
    """Store for workflow events"""

    def __init__(self):
        self._events: List[Dict] = []

    async def log(self, event: Dict) -> None:
        """Log event to store"""
        self._events.append(event)

    async def get_events(
        self,
        account_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
    ) -> List[Dict]:
        """Get events with optional filters"""
        events = self._events

        if account_id:
            events = [e for e in events if e.get("account_id") == account_id]

        if campaign_id:
            events = [e for e in events if e.get("campaign_id") == campaign_id]

        return events
