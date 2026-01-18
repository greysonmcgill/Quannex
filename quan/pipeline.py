"""
QUAN Recovery Pipeline

Seven-stage collection workflow:
ACQUIRE → LOCATE → CONTACT → NEGOTIATE → COLLECT → CLOSE → PROFIT
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
import asyncio
import logging

from quan.intelligence.engine import CollectionIntelligence, CollectionStrategy
from quan.ml.models import PaymentProbabilityNet, NegotiationAgent, SettlementOptimizer
from quan.compliance.engine import ComplianceEngine, ContactGovernor
from quan.communications.engine import CommunicationEngine
from quan.payments.processor import PaymentProcessor, SettlementEngine
from quan.monitoring.metrics import get_metrics

logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    """Seven stages of QUAN collection pipeline"""
    ACQUIRE = "acquire"
    LOCATE = "locate"
    CONTACT = "contact"
    NEGOTIATE = "negotiate"
    COLLECT = "collect"
    CLOSE = "close"
    PROFIT = "profit"


class AccountStatus(Enum):
    """Account status within pipeline"""
    NEW = "new"
    SCORED = "scored"
    LOCATED = "located"
    IN_CONTACT = "in_contact"
    NEGOTIATING = "negotiating"
    PAYMENT_PENDING = "payment_pending"
    PAYING = "paying"  # Active payment plan
    PAID_IN_FULL = "paid_in_full"
    SETTLED = "settled"
    UNCOLLECTABLE = "uncollectable"
    DISPUTE = "dispute"


@dataclass
class Account:
    """Account moving through pipeline"""
    account_id: str
    client_id: str
    original_creditor: str
    balance: Decimal
    charge_off_date: datetime
    debtor: Dict[str, Any]

    # Pipeline state
    status: AccountStatus = AccountStatus.NEW
    stage: PipelineStage = PipelineStage.ACQUIRE

    # Scoring
    ml_score: float = 0.0
    recovery_probability: float = 0.0
    priority_rank: int = 0

    # Contact info (populated in LOCATE)
    contacts: Dict[str, List[str]] = field(default_factory=dict)
    best_channel: Optional[str] = None
    best_time: Optional[str] = None

    # Contact history
    contact_attempts: int = 0
    last_contact: Optional[datetime] = None
    last_response: Optional[datetime] = None

    # Negotiation state
    current_offer: Optional[Decimal] = None
    counter_offers: List[Decimal] = field(default_factory=list)
    settlement_authority: Optional[Decimal] = None
    payment_plan: Optional[Dict] = None

    # Collection
    amount_collected: Decimal = Decimal("0")
    payments: List[Dict] = field(default_factory=list)

    # Financials
    commission_rate: float = 0.30  # 30% contingency
    commission_earned: Decimal = Decimal("0")


@dataclass
class PipelineResult:
    """Result from pipeline stage execution"""
    success: bool
    account: Account
    next_stage: Optional[PipelineStage] = None
    retry_after: Optional[timedelta] = None
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


class QuanPipeline:
    """
    Main QUAN collection pipeline orchestrator.

    Moves accounts through seven stages:
    ACQUIRE → LOCATE → CONTACT → NEGOTIATE → COLLECT → CLOSE → PROFIT
    """

    def __init__(self):
        # Core engines
        self.intelligence = CollectionIntelligence()
        self.compliance = ComplianceEngine()
        self.contact_governor = ContactGovernor()
        self.communications = CommunicationEngine()
        self.payments = PaymentProcessor()
        self.settlement = SettlementEngine()
        self.metrics = get_metrics()

        # ML models
        self.scorer = PaymentProbabilityNet()
        self.negotiator = NegotiationAgent()
        self.settlement_optimizer = SettlementOptimizer()

        # Stage handlers
        self.stage_handlers: Dict[PipelineStage, Callable] = {
            PipelineStage.ACQUIRE: self._stage_acquire,
            PipelineStage.LOCATE: self._stage_locate,
            PipelineStage.CONTACT: self._stage_contact,
            PipelineStage.NEGOTIATE: self._stage_negotiate,
            PipelineStage.COLLECT: self._stage_collect,
            PipelineStage.CLOSE: self._stage_close,
            PipelineStage.PROFIT: self._stage_profit,
        }

        # Channel escalation order
        self.channel_priority = ["sms", "email", "voice", "mail"]

        logger.info("QUAN Pipeline initialized")

    # =========================================================================
    # STAGE 1: ACQUIRE
    # Ingest portfolio, score accounts, rank by recovery potential
    # =========================================================================

    async def _stage_acquire(self, account: Account) -> PipelineResult:
        """
        ACQUIRE: Score and rank account for recovery potential.

        - Run quantum analysis on portfolio batch
        - Calculate payment probability
        - Assign priority rank
        """

        with self.metrics.track_processing(account.account_id, "acquire"):

            # Extract features for scoring
            features = self._extract_scoring_features(account)

            # ML scoring - payment probability
            recovery_prob = float(self.scorer.predict_proba(features)[0])

            # Get strategy from collection intelligence
            strategy = self.intelligence.generate_strategy(account.__dict__)
            ml_score = strategy.recovery_probability

            # Combined score (weighted average)
            combined_score = (0.6 * recovery_prob) + (0.4 * ml_score)

            # Update account
            account.recovery_probability = recovery_prob
            account.ml_score = ml_score
            account.status = AccountStatus.SCORED

            # Priority ranking (higher score = higher priority)
            # Also factor in balance (larger balances get slight boost)
            balance_factor = min(float(account.balance) / 1000, 1.5)
            account.priority_rank = int(combined_score * balance_factor * 1000)

            logger.info(
                f"ACQUIRE complete: {account.account_id} "
                f"score={combined_score:.3f} rank={account.priority_rank}"
            )

            return PipelineResult(
                success=True,
                account=account,
                next_stage=PipelineStage.LOCATE,
                metrics={
                    "recovery_probability": recovery_prob,
                    "ml_score": ml_score,
                    "priority_rank": account.priority_rank,
                },
            )

    # =========================================================================
    # STAGE 2: LOCATE
    # Skip trace, append contacts, verify best channel
    # =========================================================================

    async def _stage_locate(self, account: Account) -> PipelineResult:
        """
        LOCATE: Find and verify contact information.

        - Skip trace for missing info
        - Append/verify phone, email, address
        - Determine best contact channel and time
        """

        with self.metrics.track_processing(account.account_id, "locate"):

            contacts = {
                "phone": [],
                "email": [],
                "address": [],
            }

            # Start with existing debtor info
            debtor = account.debtor

            if debtor.get("phone"):
                contacts["phone"].append(debtor["phone"])
            if debtor.get("email"):
                contacts["email"].append(debtor["email"])
            if debtor.get("address"):
                contacts["address"].append(debtor["address"])

            # Skip trace if missing critical info
            if not contacts["phone"] and not contacts["email"]:
                skip_trace_result = await self._skip_trace(account)

                contacts["phone"].extend(skip_trace_result.get("phones", []))
                contacts["email"].extend(skip_trace_result.get("emails", []))
                contacts["address"].extend(skip_trace_result.get("addresses", []))

            # Verify contacts
            verified_contacts = await self._verify_contacts(contacts)

            # Determine best channel based on:
            # - Available verified contacts
            # - Historical response rates
            # - Debtor preferences/consent
            best_channel = await self._determine_best_channel(
                account, verified_contacts
            )

            # Determine best contact time
            best_time = await self._determine_best_time(account)

            # Update account
            account.contacts = verified_contacts
            account.best_channel = best_channel
            account.best_time = best_time
            account.status = AccountStatus.LOCATED

            # Check if we have any valid contact method
            has_contact = any(
                len(v) > 0 for v in verified_contacts.values()
            )

            if not has_contact:
                logger.warning(f"LOCATE failed - no contacts: {account.account_id}")
                return PipelineResult(
                    success=False,
                    account=account,
                    retry_after=timedelta(days=30),  # Retry skip trace later
                    error="No valid contact information found",
                )

            logger.info(
                f"LOCATE complete: {account.account_id} "
                f"channel={best_channel} contacts={len(contacts['phone'])}ph/"
                f"{len(contacts['email'])}em"
            )

            return PipelineResult(
                success=True,
                account=account,
                next_stage=PipelineStage.CONTACT,
                metrics={
                    "phones_found": len(verified_contacts.get("phone", [])),
                    "emails_found": len(verified_contacts.get("email", [])),
                    "best_channel": best_channel,
                },
            )

    # =========================================================================
    # STAGE 3: CONTACT
    # AI outreach with escalating frequency, channel rotation on dead ends
    # =========================================================================

    async def _stage_contact(self, account: Account) -> PipelineResult:
        """
        CONTACT: Execute AI-powered outreach campaign.

        - Compliance check before each attempt
        - Escalating frequency (1, 2, 3, 5, 7 days)
        - Channel rotation on non-response
        - Personalized messaging
        """

        with self.metrics.track_processing(account.account_id, "contact"):

            # Compliance check
            can_contact, reason = await self.compliance.validate_contact(
                account.__dict__,
                account.best_channel,
            )

            if not can_contact:
                logger.info(f"CONTACT blocked: {account.account_id} - {reason}")

                # Determine retry based on reason
                if "hours" in reason.lower():
                    retry = timedelta(hours=12)
                elif "limit" in reason.lower():
                    retry = timedelta(days=1)
                else:
                    retry = timedelta(days=7)

                return PipelineResult(
                    success=False,
                    account=account,
                    retry_after=retry,
                    error=reason,
                )

            # Check if we should rotate channel
            channel = account.best_channel
            if account.contact_attempts > 0 and not account.last_response:
                channel = self._rotate_channel(account)

            # Generate personalized message
            message = await self._generate_contact_message(account, channel)

            # Execute contact
            result = await self._execute_contact(account, channel, message)

            # Update account
            account.contact_attempts += 1
            account.last_contact = datetime.utcnow()
            account.status = AccountStatus.IN_CONTACT

            # Record attempt for compliance
            await self.contact_governor.record_attempt(
                account.__dict__,
                {"channel": channel},
                result,
            )

            # Check response
            if result.get("response_received"):
                account.last_response = datetime.utcnow()

                # Analyze response intent
                intent = await self._analyze_response(result.get("response"))

                if intent == "pay":
                    return PipelineResult(
                        success=True,
                        account=account,
                        next_stage=PipelineStage.COLLECT,
                    )
                elif intent == "negotiate":
                    return PipelineResult(
                        success=True,
                        account=account,
                        next_stage=PipelineStage.NEGOTIATE,
                    )
                elif intent == "dispute":
                    account.status = AccountStatus.DISPUTE
                    return PipelineResult(
                        success=False,
                        account=account,
                        error="Debtor disputed - requires manual review",
                    )

            # Calculate next contact interval (escalating)
            intervals = [1, 2, 3, 5, 7, 7, 7]  # Days between attempts
            attempt_idx = min(account.contact_attempts, len(intervals) - 1)
            next_interval = timedelta(days=intervals[attempt_idx])

            # Max attempts before channel rotation or pause
            if account.contact_attempts >= 21:  # 7 attempts x 3 channels
                logger.info(f"CONTACT exhausted: {account.account_id}")
                return PipelineResult(
                    success=False,
                    account=account,
                    retry_after=timedelta(days=90),  # Long pause before retry
                    error="Contact attempts exhausted",
                )

            logger.info(
                f"CONTACT attempt {account.contact_attempts}: {account.account_id} "
                f"via {channel}, next in {next_interval.days}d"
            )

            return PipelineResult(
                success=True,
                account=account,
                next_stage=PipelineStage.CONTACT,  # Loop back
                retry_after=next_interval,
                metrics={
                    "channel": channel,
                    "attempt": account.contact_attempts,
                    "response": result.get("response_received", False),
                },
            )

    # =========================================================================
    # STAGE 4: NEGOTIATE
    # Push for max recovery—full pay first, counter high, structure plans
    # =========================================================================

    async def _stage_negotiate(self, account: Account) -> PipelineResult:
        """
        NEGOTIATE: AI-powered negotiation for maximum recovery.

        Strategy:
        1. Always push for full payment first
        2. Counter settlement offers HIGH (start at 80%)
        3. Gradually reduce to floor (typically 40-50%)
        4. Offer payment plans to close deals
        """

        with self.metrics.track_processing(account.account_id, "negotiate"):

            account.status = AccountStatus.NEGOTIATING
            balance = account.balance

            # Calculate settlement authority (floor we can accept)
            authority = await self._calculate_settlement_authority(account)
            account.settlement_authority = authority

            # Get collection strategy for negotiation context
            collection_strategy = self.intelligence.generate_strategy(account.__dict__)

            # Determine negotiation strategy
            strategy = await self._determine_negotiation_strategy(
                account, collection_strategy
            )

            # STEP 1: Always start with full payment ask
            if account.current_offer is None:
                offer = NegotiationOffer(
                    type="full_payment",
                    amount=balance,
                    message=self._generate_full_payment_pitch(account),
                    expires=datetime.utcnow() + timedelta(days=7),
                )

                result = await self._present_offer(account, offer)

                if result.get("accepted"):
                    return PipelineResult(
                        success=True,
                        account=account,
                        next_stage=PipelineStage.COLLECT,
                        metrics={"offer_type": "full_payment", "accepted": True},
                    )

                # Record counter offer if provided
                if result.get("counter_offer"):
                    account.counter_offers.append(
                        Decimal(str(result["counter_offer"]))
                    )

            # STEP 2: Counter settlement offers HIGH
            if account.counter_offers:
                debtor_offer = account.counter_offers[-1]

                # Start counters at 80% of balance, work down
                counter_pcts = [0.80, 0.70, 0.60, 0.50, 0.45, 0.40]
                counter_idx = len(account.counter_offers) - 1
                counter_idx = min(counter_idx, len(counter_pcts) - 1)

                our_counter = balance * Decimal(str(counter_pcts[counter_idx]))

                # Don't go below authority
                our_counter = max(our_counter, authority)

                # If debtor offer meets authority, accept
                if debtor_offer >= authority:
                    account.current_offer = debtor_offer
                    return PipelineResult(
                        success=True,
                        account=account,
                        next_stage=PipelineStage.COLLECT,
                        metrics={
                            "offer_type": "settlement",
                            "amount": float(debtor_offer),
                            "pct_of_balance": float(debtor_offer / balance),
                        },
                    )

                # Present counter
                offer = NegotiationOffer(
                    type="settlement",
                    amount=our_counter,
                    message=self._generate_settlement_pitch(account, our_counter),
                    expires=datetime.utcnow() + timedelta(days=3),
                )

                result = await self._present_offer(account, offer)
                account.current_offer = our_counter

                if result.get("accepted"):
                    return PipelineResult(
                        success=True,
                        account=account,
                        next_stage=PipelineStage.COLLECT,
                    )

                if result.get("counter_offer"):
                    account.counter_offers.append(
                        Decimal(str(result["counter_offer"]))
                    )

            # STEP 3: Offer payment plan to close
            if len(account.counter_offers) >= 3:
                plan = self._generate_payment_plan(account)

                offer = NegotiationOffer(
                    type="payment_plan",
                    amount=plan["total"],
                    payment_plan=plan,
                    message=self._generate_plan_pitch(account, plan),
                    expires=datetime.utcnow() + timedelta(days=5),
                )

                result = await self._present_offer(account, offer)

                if result.get("accepted"):
                    account.payment_plan = plan
                    return PipelineResult(
                        success=True,
                        account=account,
                        next_stage=PipelineStage.COLLECT,
                        metrics={"offer_type": "payment_plan"},
                    )

            # Still negotiating - loop back to contact for follow-up
            logger.info(
                f"NEGOTIATE ongoing: {account.account_id} "
                f"counters={len(account.counter_offers)}"
            )

            return PipelineResult(
                success=True,
                account=account,
                next_stage=PipelineStage.CONTACT,
                retry_after=timedelta(days=2),
            )

    # =========================================================================
    # STAGE 5: COLLECT
    # Capture payment, process, retry failures
    # =========================================================================

    async def _stage_collect(self, account: Account) -> PipelineResult:
        """
        COLLECT: Process payment with retry logic.

        - Capture payment method
        - Process transaction
        - Retry failures with exponential backoff
        - Handle partial payments
        """

        with self.metrics.track_processing(account.account_id, "collect"):

            account.status = AccountStatus.PAYMENT_PENDING

            # Determine payment amount
            if account.payment_plan:
                # Get next scheduled payment
                payment_amount = self._get_next_plan_payment(account)
            elif account.current_offer:
                # Settlement amount
                payment_amount = account.current_offer
            else:
                # Full balance
                payment_amount = account.balance

            # Request payment
            payment_request = await self._request_payment(account, payment_amount)

            if not payment_request.get("payment_method"):
                # No payment method provided - back to contact
                return PipelineResult(
                    success=False,
                    account=account,
                    next_stage=PipelineStage.CONTACT,
                    retry_after=timedelta(days=1),
                    error="Payment method not provided",
                )

            # Process payment
            max_retries = 3
            retry_delays = [0, 60, 300]  # seconds

            for attempt in range(max_retries):
                if attempt > 0:
                    await asyncio.sleep(retry_delays[attempt])

                result = await self.payments.process_payment(
                    account.__dict__,
                    payment_request["payment_method"],
                    payment_amount,
                )

                if result.get("success"):
                    # Payment successful
                    account.amount_collected += payment_amount
                    account.payments.append({
                        "amount": float(payment_amount),
                        "date": datetime.utcnow().isoformat(),
                        "transaction_id": result.get("transaction_id"),
                        "method": payment_request["payment_method"].get("type"),
                    })

                    self.metrics.record_payment(
                        float(payment_amount),
                        payment_request["payment_method"].get("type", "unknown"),
                        account.account_id,
                    )

                    logger.info(
                        f"COLLECT success: {account.account_id} "
                        f"${payment_amount} collected"
                    )

                    return PipelineResult(
                        success=True,
                        account=account,
                        next_stage=PipelineStage.CLOSE,
                        metrics={
                            "amount": float(payment_amount),
                            "attempts": attempt + 1,
                        },
                    )

                logger.warning(
                    f"COLLECT retry {attempt + 1}: {account.account_id} "
                    f"error={result.get('error')}"
                )

            # All retries failed
            logger.error(f"COLLECT failed: {account.account_id}")

            return PipelineResult(
                success=False,
                account=account,
                next_stage=PipelineStage.CONTACT,  # Back to contact
                retry_after=timedelta(days=3),
                error=f"Payment failed after {max_retries} attempts",
            )

    # =========================================================================
    # STAGE 6: CLOSE
    # Monitor plans, loop missed payments back, book revenue on completion
    # =========================================================================

    async def _stage_close(self, account: Account) -> PipelineResult:
        """
        CLOSE: Monitor account to completion.

        - Track payment plan progress
        - Loop missed payments back to CONTACT
        - Book revenue on full completion
        """

        with self.metrics.track_processing(account.account_id, "close"):

            # Determine target amount
            if account.current_offer:
                target = account.current_offer
            else:
                target = account.balance

            # Check if fully paid
            if account.amount_collected >= target:
                # FULLY PAID - proceed to profit
                if account.amount_collected >= account.balance:
                    account.status = AccountStatus.PAID_IN_FULL
                else:
                    account.status = AccountStatus.SETTLED

                logger.info(
                    f"CLOSE complete: {account.account_id} "
                    f"collected=${account.amount_collected} "
                    f"status={account.status.value}"
                )

                return PipelineResult(
                    success=True,
                    account=account,
                    next_stage=PipelineStage.PROFIT,
                )

            # Check payment plan status
            if account.payment_plan:
                account.status = AccountStatus.PAYING

                plan_status = self._check_plan_status(account)

                if plan_status == "current":
                    # On track - schedule next payment check
                    next_payment_date = self._get_next_payment_date(account)

                    return PipelineResult(
                        success=True,
                        account=account,
                        next_stage=PipelineStage.COLLECT,
                        retry_after=next_payment_date - datetime.utcnow(),
                    )

                elif plan_status == "missed":
                    # MISSED PAYMENT - loop back to contact
                    logger.warning(
                        f"CLOSE missed payment: {account.account_id}"
                    )

                    return PipelineResult(
                        success=False,
                        account=account,
                        next_stage=PipelineStage.CONTACT,
                        error="Missed scheduled payment",
                    )

                elif plan_status == "defaulted":
                    # Multiple missed - renegotiate
                    account.payment_plan = None

                    return PipelineResult(
                        success=False,
                        account=account,
                        next_stage=PipelineStage.NEGOTIATE,
                        error="Payment plan defaulted",
                    )

            # Partial payment without plan - continue collection
            remaining = target - account.amount_collected
            logger.info(
                f"CLOSE partial: {account.account_id} "
                f"remaining=${remaining}"
            )

            return PipelineResult(
                success=True,
                account=account,
                next_stage=PipelineStage.CONTACT,
                retry_after=timedelta(days=7),
            )

    # =========================================================================
    # STAGE 7: PROFIT
    # Commission calculation, net margin
    # =========================================================================

    async def _stage_profit(self, account: Account) -> PipelineResult:
        """
        PROFIT: Calculate and book revenue.

        - Calculate commission (typically 30% contingency)
        - Track net margin
        - Report to client
        """

        with self.metrics.track_processing(account.account_id, "profit"):

            collected = account.amount_collected
            commission_rate = account.commission_rate

            # Calculate commission
            commission = collected * Decimal(str(commission_rate))
            account.commission_earned = commission

            # Calculate metrics
            recovery_rate = float(collected / account.balance) if account.balance else 0

            # Estimate costs (simplified)
            estimated_cost = Decimal("0.50")  # $0.50 per account
            net_profit = commission - estimated_cost
            margin = float(net_profit / commission) if commission else 0

            # Book revenue
            await self._book_revenue(account, commission)

            # Notify client
            await self._notify_client_completion(account)

            # Update recovery rate metrics
            self.metrics.update_recovery_rate(
                account.client_id,
                recovery_rate,
            )

            logger.info(
                f"PROFIT booked: {account.account_id} "
                f"collected=${collected} commission=${commission:.2f} "
                f"margin={margin:.1%}"
            )

            return PipelineResult(
                success=True,
                account=account,
                next_stage=None,  # Pipeline complete
                metrics={
                    "amount_collected": float(collected),
                    "commission": float(commission),
                    "recovery_rate": recovery_rate,
                    "net_profit": float(net_profit),
                    "margin": margin,
                },
            )

    # =========================================================================
    # PIPELINE EXECUTION
    # =========================================================================

    async def process_account(self, account: Account) -> PipelineResult:
        """Process single account through current stage"""

        handler = self.stage_handlers.get(account.stage)

        if not handler:
            raise ValueError(f"Unknown stage: {account.stage}")

        try:
            result = await handler(account)

            # Advance stage if successful
            if result.success and result.next_stage:
                account.stage = result.next_stage

            return result

        except Exception as e:
            logger.exception(f"Pipeline error: {account.account_id} at {account.stage}")
            return PipelineResult(
                success=False,
                account=account,
                error=str(e),
                retry_after=timedelta(hours=1),
            )

    async def run_account_to_completion(
        self,
        account: Account,
        max_iterations: int = 100,
    ) -> PipelineResult:
        """Run account through pipeline until completion or max iterations"""

        for i in range(max_iterations):
            result = await self.process_account(account)

            if result.next_stage is None:
                # Pipeline complete
                return result

            if not result.success and result.retry_after:
                # Would wait in production - return for scheduling
                return result

            # Continue to next stage
            account = result.account

        return PipelineResult(
            success=False,
            account=account,
            error=f"Max iterations ({max_iterations}) reached",
        )

    async def process_portfolio(
        self,
        accounts: List[Account],
        concurrency: int = 50,
    ) -> List[PipelineResult]:
        """Process portfolio of accounts with concurrency control"""

        semaphore = asyncio.Semaphore(concurrency)

        async def process_with_limit(account: Account) -> PipelineResult:
            async with semaphore:
                return await self.process_account(account)

        tasks = [process_with_limit(acc) for acc in accounts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to PipelineResults
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(PipelineResult(
                    success=False,
                    account=accounts[i],
                    error=str(result),
                ))
            else:
                processed_results.append(result)

        return processed_results

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _extract_scoring_features(self, account: Account) -> list:
        """Extract features for ML scoring"""

        days_since_charge_off = (
            datetime.utcnow() - account.charge_off_date
        ).days

        return [
            float(account.balance),
            days_since_charge_off,
            len(account.debtor.get("phone", "") or ""),
            len(account.debtor.get("email", "") or ""),
            1 if account.debtor.get("employed") else 0,
            # ... more features
        ]

    def _get_collection_strategy(self, account: Account) -> CollectionStrategy:
        """Get collection strategy for account"""
        return self.intelligence.generate_strategy(account.__dict__)

    async def _skip_trace(self, account: Account) -> Dict[str, List[str]]:
        """Perform skip trace to find contact info"""
        # Integration with skip trace providers (LexisNexis, etc.)
        return {"phones": [], "emails": [], "addresses": []}

    async def _verify_contacts(
        self,
        contacts: Dict[str, List[str]],
    ) -> Dict[str, List[str]]:
        """Verify contact information is valid and deliverable"""
        # Phone validation, email verification, address standardization
        return contacts

    async def _determine_best_channel(
        self,
        account: Account,
        contacts: Dict[str, List[str]],
    ) -> str:
        """Determine optimal contact channel"""

        # Prioritize based on availability and historical performance
        if contacts.get("phone"):
            return "sms"
        elif contacts.get("email"):
            return "email"
        elif contacts.get("address"):
            return "mail"

        return "sms"  # Default

    async def _determine_best_time(self, account: Account) -> str:
        """Determine optimal contact time"""
        # Based on timezone and historical response patterns
        return "10:00"

    def _rotate_channel(self, account: Account) -> str:
        """Rotate to next channel after non-response"""

        current = account.best_channel
        current_idx = self.channel_priority.index(current)
        next_idx = (current_idx + 1) % len(self.channel_priority)

        # Check if we have contact info for next channel
        for i in range(len(self.channel_priority)):
            check_idx = (next_idx + i) % len(self.channel_priority)
            channel = self.channel_priority[check_idx]

            contact_key = "phone" if channel in ["sms", "voice"] else channel
            if account.contacts.get(contact_key):
                return channel

        return current  # Fallback to current

    async def _generate_contact_message(
        self,
        account: Account,
        channel: str,
    ) -> str:
        """Generate personalized contact message"""

        # Templates with personalization
        templates = {
            "sms": (
                f"QUAN Recovery: We're reaching out about your "
                f"${account.balance:.2f} balance. Reply PAY for easy options "
                f"or call 1-800-XXX-XXXX. This is an attempt to collect a debt."
            ),
            "email": (
                f"Your account balance of ${account.balance:.2f} requires attention. "
                f"We have flexible payment options available."
            ),
        }

        return templates.get(channel, templates["sms"])

    async def _execute_contact(
        self,
        account: Account,
        channel: str,
        message: str,
    ) -> Dict:
        """Execute contact via channel"""

        if channel == "sms":
            return await self.communications.send_sms(account.__dict__, message)
        elif channel == "email":
            return await self.communications.send_email(account.__dict__, message)

        return {"success": False}

    async def _analyze_response(self, response: str) -> str:
        """Analyze debtor response intent"""

        if not response:
            return "none"

        response_lower = response.lower()

        if any(w in response_lower for w in ["pay", "card", "payment"]):
            return "pay"
        elif any(w in response_lower for w in ["settle", "less", "offer", "lower"]):
            return "negotiate"
        elif any(w in response_lower for w in ["dispute", "wrong", "not mine", "fraud"]):
            return "dispute"

        return "unknown"

    async def _calculate_settlement_authority(self, account: Account) -> Decimal:
        """Calculate minimum acceptable settlement"""

        # Use ML model for optimal floor
        features = self._extract_scoring_features(account)
        ratio = self.settlement_optimizer.predict_settlement(features)

        # Minimum 35% of balance
        min_ratio = max(ratio, 0.35)

        return account.balance * Decimal(str(min_ratio))

    async def _determine_negotiation_strategy(
        self,
        account: Account,
        collection_strategy: CollectionStrategy,
    ) -> Dict:
        """Determine negotiation strategy based on collection intelligence"""

        return {
            "aggression": collection_strategy.confidence,
            "max_discount": 1 - (collection_strategy.recovery_probability * 0.5),
        }

    def _generate_full_payment_pitch(self, account: Account) -> str:
        """Generate full payment request message"""
        return (
            f"Resolve your ${account.balance:.2f} balance today and put this "
            f"behind you. Pay in full now to avoid additional collection activity."
        )

    def _generate_settlement_pitch(
        self,
        account: Account,
        amount: Decimal,
    ) -> str:
        """Generate settlement offer message"""
        savings = account.balance - amount
        return (
            f"We can settle your account for ${amount:.2f} - "
            f"a savings of ${savings:.2f}. This offer expires in 3 days."
        )

    def _generate_payment_plan(self, account: Account) -> Dict:
        """Generate payment plan options"""

        balance = account.current_offer or account.balance

        # 3-month plan
        monthly = balance / 3

        return {
            "total": float(balance),
            "monthly_amount": float(monthly),
            "num_payments": 3,
            "first_payment_date": (
                datetime.utcnow() + timedelta(days=7)
            ).isoformat(),
            "schedule": [
                {"due": (datetime.utcnow() + timedelta(days=7 + 30*i)).isoformat(),
                 "amount": float(monthly)}
                for i in range(3)
            ],
        }

    def _generate_plan_pitch(self, account: Account, plan: Dict) -> str:
        """Generate payment plan offer message"""
        return (
            f"We can set up a payment plan: ${plan['monthly_amount']:.2f}/month "
            f"for {plan['num_payments']} months. First payment due in 7 days."
        )

    async def _present_offer(
        self,
        account: Account,
        offer: 'NegotiationOffer',
    ) -> Dict:
        """Present offer to debtor and get response"""
        # In production, this would send message and await response
        return {"accepted": False, "counter_offer": None}

    async def _request_payment(
        self,
        account: Account,
        amount: Decimal,
    ) -> Dict:
        """Request payment from debtor"""
        # In production, this would present payment form
        return {"payment_method": None}

    def _get_next_plan_payment(self, account: Account) -> Decimal:
        """Get next scheduled payment amount from plan"""
        if not account.payment_plan:
            return Decimal("0")

        return Decimal(str(account.payment_plan.get("monthly_amount", 0)))

    def _check_plan_status(self, account: Account) -> str:
        """Check payment plan status"""

        if not account.payment_plan:
            return "none"

        # Check payments against schedule
        schedule = account.payment_plan.get("schedule", [])
        payments_made = len(account.payments)

        now = datetime.utcnow()
        payments_due = sum(
            1 for p in schedule
            if datetime.fromisoformat(p["due"]) <= now
        )

        if payments_made >= payments_due:
            return "current"
        elif payments_due - payments_made == 1:
            return "missed"
        else:
            return "defaulted"

    def _get_next_payment_date(self, account: Account) -> datetime:
        """Get next payment due date"""

        if not account.payment_plan:
            return datetime.utcnow() + timedelta(days=30)

        schedule = account.payment_plan.get("schedule", [])
        payments_made = len(account.payments)

        if payments_made < len(schedule):
            return datetime.fromisoformat(schedule[payments_made]["due"])

        return datetime.utcnow() + timedelta(days=30)

    async def _book_revenue(self, account: Account, commission: Decimal) -> None:
        """Book revenue in accounting system"""
        logger.info(f"Revenue booked: {account.account_id} ${commission:.2f}")

    async def _notify_client_completion(self, account: Account) -> None:
        """Notify client of account completion"""
        logger.info(f"Client notified: {account.client_id} - {account.account_id}")


@dataclass
class NegotiationOffer:
    """Negotiation offer structure"""
    type: str  # full_payment, settlement, payment_plan
    amount: Decimal
    message: str
    expires: datetime
    payment_plan: Optional[Dict] = None


# Need numpy for QuantumSignal default
import numpy as np
