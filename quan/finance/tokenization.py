"""
Real-World Asset (RWA) Tokenization Layer - Centrifuge/Tinlake Model

QUAN Recovery's blockchain-based securitization infrastructure for
tokenizing distressed micro-debt into tradeable digital assets.

Architecture based on Centrifuge/Tinlake protocol:
- NFT representation of individual debt records
- Pool aggregation by asset class
- DROP (Senior) / TIN (Junior) tranche structure
- Algorithmic waterfall distribution
- DeFi-ready liquidity layer

Key Innovation: Convert millions of $40 BNPL defaults and $200 subscription
defaults into standardized, rated, tradeable digital securities with
real-time pricing and instant liquidity.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum, auto
from typing import Any, Callable, TypeVar, Generic
import hashlib
import json
import secrets
import uuid
import logging
from collections import defaultdict
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMERATIONS AND CONSTANTS
# =============================================================================

class AssetClass(Enum):
    """Standardized debt asset classifications"""
    BNPL_PRIME = "bnpl_prime"              # Buy Now Pay Later, high score
    BNPL_SUBPRIME = "bnpl_subprime"        # BNPL, lower score
    SUBSCRIPTION_TECH = "subscription_tech" # Tech/SaaS subscriptions
    SUBSCRIPTION_MEDIA = "subscription_media"  # Media/streaming
    SUBSCRIPTION_FITNESS = "subscription_fitness"  # Fitness/wellness
    GIG_ECONOMY = "gig_economy"            # Gig worker cash advances
    UTILITY_ELECTRIC = "utility_electric"   # Electric utility
    UTILITY_TELECOM = "utility_telecom"     # Telecom/mobile
    MEDICAL_MICRO = "medical_micro"         # Small medical debts
    RENT_ARREARS = "rent_arrears"           # Rental payment defaults
    MIXED_MICRO = "mixed_micro"             # Mixed micro-debt portfolio


class RiskRating(Enum):
    """S&P-style risk ratings with expected recovery bands"""
    AAA = ("AAA", 0.85, 1.00)   # 85-100% expected recovery
    AA = ("AA", 0.75, 0.85)     # 75-85%
    A = ("A", 0.65, 0.75)       # 65-75%
    BBB = ("BBB", 0.55, 0.65)   # 55-65%
    BB = ("BB", 0.45, 0.55)     # 45-55%
    B = ("B", 0.35, 0.45)       # 35-45%
    CCC = ("CCC", 0.25, 0.35)   # 25-35%
    CC = ("CC", 0.15, 0.25)     # 15-25%
    C = ("C", 0.00, 0.15)       # 0-15%

    def __init__(self, rating: str, low: float, high: float):
        self.rating = rating
        self.recovery_low = low
        self.recovery_high = high


class TokenStandard(Enum):
    """Token standards for on-chain representation"""
    ERC721 = "ERC-721"    # Individual NFT per debt
    ERC1155 = "ERC-1155"  # Semi-fungible (batch operations)
    ERC20 = "ERC-20"      # Fungible tranche tokens


class TrancheType(Enum):
    """Tinlake tranche types"""
    DROP = "DROP"  # Senior tranche - first claim, lower yield, protected
    TIN = "TIN"    # Junior tranche - first-loss, higher yield


class PoolStatus(Enum):
    """Pool lifecycle status"""
    OPEN = "open"                # Accepting new assets
    CLOSING = "closing"          # No new assets, preparing for close
    CLOSED = "closed"            # Closed for new assets
    ACTIVE = "active"            # Deployed, generating yields
    MATURE = "mature"            # Reached maturity
    LIQUIDATING = "liquidating"  # Winding down
    TERMINATED = "terminated"    # Fully wound down


class OrderSide(Enum):
    """Order book sides"""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LIMIT = "stop_limit"


# Constants
MIN_POOL_SIZE = Decimal("1000000")  # $1M minimum pool size
DROP_TARGET_YIELD = (Decimal("0.05"), Decimal("0.08"))  # 5-8% for senior
TIN_TARGET_YIELD = (Decimal("0.12"), Decimal("0.20"))   # 12-20% for junior
EPOCH_DURATION_DAYS = 1  # Tinlake epoch duration
RESERVE_RATIO = Decimal("0.05")  # 5% reserve requirement


# =============================================================================
# CRYPTOGRAPHIC UTILITIES
# =============================================================================

class CryptoUtils:
    """Cryptographic utilities for token generation and verification"""

    @staticmethod
    def generate_token_id(data: dict, salt: str | None = None) -> str:
        """Generate cryptographically secure token ID"""
        if salt is None:
            salt = secrets.token_hex(16)

        payload = json.dumps(data, sort_keys=True, default=str)
        combined = f"{payload}:{salt}:{datetime.utcnow().isoformat()}"

        return hashlib.sha3_256(combined.encode()).hexdigest()

    @staticmethod
    def generate_merkle_root(hashes: list[str]) -> str:
        """Generate Merkle root from list of hashes"""
        if not hashes:
            return hashlib.sha3_256(b"empty").hexdigest()

        # Make a copy to avoid modifying input
        current_level = list(hashes)

        if len(current_level) == 1:
            return current_level[0]

        # Build tree
        while len(current_level) > 1:
            # Pad to even length at each level
            if len(current_level) % 2 == 1:
                current_level.append(current_level[-1])

            new_level = []
            for i in range(0, len(current_level), 2):
                combined = current_level[i] + current_level[i + 1]
                new_hash = hashlib.sha3_256(combined.encode()).hexdigest()
                new_level.append(new_hash)
            current_level = new_level

        return current_level[0]

    @staticmethod
    def verify_integrity(token_id: str, metadata_hash: str, stored_hash: str) -> bool:
        """Verify token integrity"""
        computed = hashlib.sha3_256(f"{token_id}:{metadata_hash}".encode()).hexdigest()
        return computed == stored_hash


# =============================================================================
# DATA MODELS - ASSET TOKENIZATION
# =============================================================================

@dataclass
class PaymentHistoryEntry:
    """Individual payment history record"""
    payment_date: datetime
    amount_due: Decimal
    amount_paid: Decimal
    payment_status: str  # on_time, late, missed, partial
    days_late: int = 0


@dataclass
class DebtMetadata:
    """Immutable metadata for tokenized debt record"""
    # Origination data
    original_creditor: str
    debt_category: str
    origination_date: datetime
    original_amount: Decimal
    charge_off_date: datetime | None
    charge_off_amount: Decimal

    # Payment history (immutable snapshot)
    payment_history: list[PaymentHistoryEntry] = field(default_factory=list)
    total_payments_made: Decimal = Decimal("0")
    longest_delinquency_days: int = 0
    payment_velocity: float = 0.0  # Payments per month

    # Risk scoring
    quan_risk_score: float = 0.0  # QUAN's proprietary score
    shadow_bureau_score: int = 0   # Shadow Bureau score
    recovery_probability: float = 0.0

    # Consumer data (anonymized)
    consumer_hash: str = ""  # Hashed PII
    geo_region: str = ""
    age_bucket: str = ""     # e.g., "25-34"

    # Metadata hash for integrity
    metadata_hash: str = ""

    def __post_init__(self):
        """Calculate metadata hash after initialization"""
        if not self.metadata_hash:
            self.metadata_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute cryptographic hash of metadata"""
        data = {
            "creditor": self.original_creditor,
            "category": self.debt_category,
            "origination": self.origination_date.isoformat(),
            "original_amount": str(self.original_amount),
            "charge_off_date": self.charge_off_date.isoformat() if self.charge_off_date else None,
            "charge_off_amount": str(self.charge_off_amount),
            "total_payments": str(self.total_payments_made),
            "risk_score": self.quan_risk_score,
            "shadow_score": self.shadow_bureau_score,
            "recovery_prob": self.recovery_probability,
        }
        return hashlib.sha3_256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass
class DebtNFT:
    """
    NFT representation of a single debt record

    Each debt becomes a unique ERC-721 compatible token with
    immutable metadata stored on-chain (simulated).
    """
    token_id: str
    token_standard: TokenStandard = TokenStandard.ERC721

    # Link to original record
    original_record_id: str = ""

    # Immutable metadata
    metadata: DebtMetadata | None = None

    # Current valuation
    face_value: Decimal = Decimal("0")
    current_value: Decimal = Decimal("0")
    last_valuation_date: datetime = field(default_factory=datetime.now)

    # Classification
    asset_class: AssetClass = AssetClass.MIXED_MICRO
    risk_rating: RiskRating = RiskRating.B

    # Pool assignment
    pool_id: str | None = None

    # Ownership
    owner_address: str = ""  # Simulated blockchain address

    # Status
    is_active: bool = True
    is_locked: bool = False  # Locked when in active pool

    # Timestamps
    minted_at: datetime = field(default_factory=datetime.now)
    last_transfer_at: datetime | None = None

    # Integrity
    integrity_hash: str = ""

    def compute_integrity_hash(self) -> str:
        """Compute integrity hash for on-chain verification"""
        data = {
            "token_id": self.token_id,
            "record_id": self.original_record_id,
            "metadata_hash": self.metadata.metadata_hash if self.metadata else "",
            "face_value": str(self.face_value),
            "minted_at": self.minted_at.isoformat(),
        }
        return hashlib.sha3_256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass
class BatchTokenization:
    """Batch tokenization operation for portfolio efficiency"""
    batch_id: str
    token_ids: list[str] = field(default_factory=list)

    # Batch metrics
    total_face_value: Decimal = Decimal("0")
    total_tokens: int = 0

    # Processing
    status: str = "pending"  # pending, processing, completed, failed
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Merkle root for batch verification
    merkle_root: str = ""

    # Gas estimation (simulated)
    estimated_gas: int = 0
    actual_gas: int = 0


# =============================================================================
# DATA MODELS - POOL MANAGEMENT
# =============================================================================

@dataclass
class PoolMetrics:
    """Real-time pool-level metrics"""
    # Portfolio composition
    total_assets: int = 0
    total_face_value: Decimal = Decimal("0")
    total_current_value: Decimal = Decimal("0")

    # Weighted Average Life (WAL)
    weighted_avg_life_days: float = 0.0

    # Performance metrics
    cumulative_collections: Decimal = Decimal("0")
    cumulative_defaults: Decimal = Decimal("0")
    cumulative_recoveries: Decimal = Decimal("0")

    # Rates (annualized)
    default_rate: float = 0.0
    recovery_rate: float = 0.0
    delinquency_rate: float = 0.0
    prepayment_rate: float = 0.0

    # Risk metrics
    weighted_avg_risk_score: float = 0.0
    weighted_avg_shadow_score: float = 0.0
    concentration_hhi: float = 0.0  # Herfindahl-Hirschman Index

    # Diversification
    unique_creditors: int = 0
    unique_categories: int = 0
    geographic_spread: int = 0

    # Timestamp
    calculated_at: datetime = field(default_factory=datetime.now)


@dataclass
class DebtPool:
    """
    Aggregated pool of tokenized debt assets

    Following Centrifuge model: Assets are pooled together
    and used to back DROP/TIN tranche tokens.
    """
    pool_id: str
    pool_name: str
    asset_class: AssetClass

    # Pool composition
    asset_token_ids: list[str] = field(default_factory=list)

    # Metrics (updated in real-time)
    metrics: PoolMetrics = field(default_factory=PoolMetrics)

    # Thresholds
    min_pool_size: Decimal = MIN_POOL_SIZE
    max_pool_size: Decimal | None = None

    # Tranche configuration
    drop_ratio: Decimal = Decimal("0.80")  # 80% senior by default
    tin_ratio: Decimal = Decimal("0.20")   # 20% junior by default

    # Reserve
    reserve_balance: Decimal = Decimal("0")
    reserve_ratio: Decimal = RESERVE_RATIO

    # Status
    status: PoolStatus = PoolStatus.OPEN

    # Lifecycle dates
    created_at: datetime = field(default_factory=datetime.now)
    closed_at: datetime | None = None
    activated_at: datetime | None = None
    maturity_date: datetime | None = None

    # Contract addresses (simulated)
    pool_contract: str = ""
    drop_token_contract: str = ""
    tin_token_contract: str = ""


# =============================================================================
# DATA MODELS - TRANCHE STRUCTURE (Tinlake Model)
# =============================================================================

@dataclass
class TrancheToken:
    """
    Tranche token (DROP or TIN) following Tinlake model

    DROP: Senior tranche - first claim on cash flows, protected by TIN
    TIN: Junior tranche - first-loss position, higher yield potential
    """
    token_id: str
    pool_id: str
    tranche_type: TrancheType
    token_standard: TokenStandard = TokenStandard.ERC20

    # Token economics
    total_supply: Decimal = Decimal("0")
    circulating_supply: Decimal = Decimal("0")

    # Pricing
    token_price: Decimal = Decimal("1.0")  # Price per token
    nav_per_token: Decimal = Decimal("1.0")  # NAV per token

    # Yield (annualized)
    target_yield_low: Decimal = Decimal("0")
    target_yield_high: Decimal = Decimal("0")
    current_yield: Decimal = Decimal("0")

    # Protection (for DROP)
    subordination_ratio: Decimal = Decimal("0")  # TIN below DROP

    # Risk
    risk_rating: RiskRating = RiskRating.BBB

    # Waterfall priority
    priority: int = 1  # 1 = highest priority (DROP)

    # Status
    is_active: bool = True
    is_tradeable: bool = True

    # Contract (simulated)
    contract_address: str = ""

    # Timestamps
    issued_at: datetime = field(default_factory=datetime.now)
    last_rebalance: datetime | None = None


@dataclass
class WaterfallDistribution:
    """
    Payment waterfall distribution record

    Implements Tinlake waterfall:
    1. Operating expenses
    2. DROP interest
    3. DROP principal
    4. TIN interest
    5. TIN principal
    6. Reserve
    """
    distribution_id: str
    pool_id: str
    epoch: int

    # Incoming cash
    total_cash_inflow: Decimal = Decimal("0")
    collections: Decimal = Decimal("0")
    recoveries: Decimal = Decimal("0")
    other_income: Decimal = Decimal("0")

    # Waterfall allocation
    operating_expenses: Decimal = Decimal("0")
    drop_interest: Decimal = Decimal("0")
    drop_principal: Decimal = Decimal("0")
    tin_interest: Decimal = Decimal("0")
    tin_principal: Decimal = Decimal("0")
    reserve_contribution: Decimal = Decimal("0")

    # Shortfalls
    drop_shortfall: Decimal = Decimal("0")
    tin_shortfall: Decimal = Decimal("0")

    # Execution
    executed_at: datetime = field(default_factory=datetime.now)
    status: str = "pending"  # pending, executing, completed


# =============================================================================
# DATA MODELS - LIQUIDITY OPERATIONS
# =============================================================================

@dataclass
class AssetValuation:
    """Mark-to-model valuation for tokenized assets"""
    token_id: str
    valuation_date: datetime

    # Valuation components
    face_value: Decimal
    base_value: Decimal  # Face * recovery probability

    # Adjustments
    seasoning_adj: Decimal = Decimal("0")  # Age adjustment
    performance_adj: Decimal = Decimal("0")  # Payment history
    market_adj: Decimal = Decimal("0")  # Market conditions
    liquidity_adj: Decimal = Decimal("0")  # Liquidity discount

    # Final value
    fair_value: Decimal = Decimal("0")

    # Model parameters
    model_version: str = "1.0"
    confidence_level: float = 0.95

    def calculate_fair_value(self) -> Decimal:
        """Calculate fair value with all adjustments"""
        self.fair_value = (
            self.base_value +
            self.seasoning_adj +
            self.performance_adj +
            self.market_adj +
            self.liquidity_adj
        )
        return self.fair_value


@dataclass
class OrderBookEntry:
    """Order book entry for secondary market"""
    order_id: str
    token_id: str  # Can be pool tranche token or individual NFT

    # Order details
    side: OrderSide
    order_type: OrderType

    # Pricing
    price: Decimal  # Price per unit (% of face for NFTs, $ for tranches)
    quantity: Decimal

    # Parties
    trader_id: str

    # Fields with defaults must come after non-default fields
    filled_quantity: Decimal = Decimal("0")
    counterparty_id: str | None = None

    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime | None = None
    executed_at: datetime | None = None

    # Status
    status: str = "open"  # open, partial, filled, cancelled, expired

    @property
    def remaining_quantity(self) -> Decimal:
        return self.quantity - self.filled_quantity


@dataclass
class LiquidityMetrics:
    """Pool and market liquidity metrics"""
    pool_id: str
    calculated_at: datetime = field(default_factory=datetime.now)

    # Instant liquidity
    instant_liquidity: Decimal = Decimal("0")  # Available for immediate redemption

    # Order book depth
    bid_depth: Decimal = Decimal("0")  # Total buy orders
    ask_depth: Decimal = Decimal("0")  # Total sell orders
    bid_ask_spread: Decimal = Decimal("0")

    # Velocity
    daily_volume: Decimal = Decimal("0")
    weekly_volume: Decimal = Decimal("0")

    # DeFi collateral metrics
    collateral_value: Decimal = Decimal("0")  # Value as DeFi collateral
    ltv_ratio: Decimal = Decimal("0.70")  # Loan-to-value ratio
    max_borrow_capacity: Decimal = Decimal("0")


# =============================================================================
# DATA MODELS - INVESTOR INTERFACE
# =============================================================================

@dataclass
class InvestorPosition:
    """Investor's position in a pool"""
    investor_id: str
    pool_id: str

    # DROP holdings
    drop_tokens: Decimal = Decimal("0")
    drop_cost_basis: Decimal = Decimal("0")
    drop_current_value: Decimal = Decimal("0")

    # TIN holdings
    tin_tokens: Decimal = Decimal("0")
    tin_cost_basis: Decimal = Decimal("0")
    tin_current_value: Decimal = Decimal("0")

    # Yield earned
    total_yield_earned: Decimal = Decimal("0")
    pending_yield: Decimal = Decimal("0")

    # Subscriptions/Redemptions
    pending_subscription: Decimal = Decimal("0")
    pending_redemption_drop: Decimal = Decimal("0")
    pending_redemption_tin: Decimal = Decimal("0")

    # Timestamps
    first_investment: datetime | None = None
    last_activity: datetime = field(default_factory=datetime.now)


@dataclass
class YieldDistribution:
    """Yield distribution to investor"""
    distribution_id: str
    investor_id: str
    pool_id: str
    epoch: int

    # Distribution breakdown
    drop_yield: Decimal = Decimal("0")
    tin_yield: Decimal = Decimal("0")
    total_yield: Decimal = Decimal("0")

    # Annualized rate
    drop_yield_rate: Decimal = Decimal("0")
    tin_yield_rate: Decimal = Decimal("0")

    # Status
    status: str = "pending"  # pending, distributed, claimed
    distributed_at: datetime | None = None
    claimed_at: datetime | None = None


@dataclass
class NAVCalculation:
    """Net Asset Value calculation"""
    pool_id: str
    calculation_date: datetime

    # Asset side
    total_asset_value: Decimal = Decimal("0")
    cash_reserve: Decimal = Decimal("0")
    accrued_interest: Decimal = Decimal("0")

    # Liability side
    drop_liability: Decimal = Decimal("0")
    tin_liability: Decimal = Decimal("0")

    # NAV
    total_nav: Decimal = Decimal("0")
    drop_nav: Decimal = Decimal("0")
    tin_nav: Decimal = Decimal("0")

    # Per token
    drop_nav_per_token: Decimal = Decimal("1.0")
    tin_nav_per_token: Decimal = Decimal("1.0")


@dataclass
class RedemptionRequest:
    """Investor redemption request"""
    request_id: str
    investor_id: str
    pool_id: str

    # Request details
    tranche_type: TrancheType
    token_amount: Decimal

    # Processing
    epoch_submitted: int
    epoch_processed: int | None = None

    # Execution
    execution_price: Decimal | None = None
    cash_amount: Decimal | None = None

    # Status
    status: str = "pending"  # pending, queued, processing, completed, cancelled
    submitted_at: datetime = field(default_factory=datetime.now)
    processed_at: datetime | None = None


# =============================================================================
# DATA MODELS - ON-CHAIN SIMULATION
# =============================================================================

@dataclass
class BlockchainTransaction:
    """Simulated blockchain transaction"""
    tx_hash: str
    block_number: int

    # Transaction details
    from_address: str
    to_address: str

    # Contract interaction
    contract_address: str
    function_name: str
    parameters: dict = field(default_factory=dict)

    # Value
    value: Decimal = Decimal("0")

    # Gas
    gas_used: int = 0
    gas_price: Decimal = Decimal("0")

    # Status
    status: str = "pending"  # pending, confirmed, failed
    confirmations: int = 0

    # Timestamps
    submitted_at: datetime = field(default_factory=datetime.now)
    confirmed_at: datetime | None = None


@dataclass
class SmartContractState:
    """Simulated smart contract state"""
    contract_address: str
    contract_type: str  # pool, drop_token, tin_token, nft

    # State variables (simplified)
    state: dict = field(default_factory=dict)

    # Access control
    owner: str = ""
    admins: list[str] = field(default_factory=list)

    # Events
    events: list[dict] = field(default_factory=list)

    # Deployment
    deployed_at: datetime = field(default_factory=datetime.now)
    deployer: str = ""


@dataclass
class ComplianceRecord:
    """Securities regulation compliance record"""
    record_id: str
    pool_id: str

    # Regulation type
    regulation: str  # reg_d, reg_a, reg_s

    # Investor qualification
    accredited_only: bool = True
    max_investors: int | None = None
    current_investors: int = 0

    # Filing status
    filed_with_sec: bool = False
    filing_date: datetime | None = None
    filing_number: str = ""

    # Geographic restrictions
    allowed_jurisdictions: list[str] = field(default_factory=list)
    blocked_jurisdictions: list[str] = field(default_factory=list)

    # KYC/AML
    kyc_required: bool = True
    aml_verified: bool = False


# =============================================================================
# CORE ENGINE - ASSET TOKENIZATION
# =============================================================================

class AssetTokenizer:
    """
    Core tokenization engine for converting debt records to NFTs

    Handles:
    - Individual NFT minting
    - Batch tokenization
    - Metadata management
    - Token lifecycle
    """

    def __init__(self):
        self.tokens: dict[str, DebtNFT] = {}
        self.batches: dict[str, BatchTokenization] = {}
        self.token_index_by_record: dict[str, str] = {}  # record_id -> token_id

        # Counters
        self.total_minted = 0
        self.total_face_value = Decimal("0")

    def mint_nft(
        self,
        record_id: str,
        metadata: DebtMetadata,
        owner_address: str = ""
    ) -> DebtNFT:
        """
        Mint NFT representation of a debt record

        Args:
            record_id: Original debt record identifier
            metadata: Immutable debt metadata
            owner_address: Initial owner (defaults to protocol)

        Returns:
            Minted DebtNFT
        """
        # Generate unique token ID with cryptographic integrity
        token_id = CryptoUtils.generate_token_id({
            "record_id": record_id,
            "metadata_hash": metadata.metadata_hash,
            "origination": metadata.origination_date.isoformat(),
        })

        # Classify asset
        asset_class = self._classify_asset(metadata)
        risk_rating = self._calculate_risk_rating(metadata)

        # Calculate current value
        face_value = metadata.charge_off_amount
        current_value = face_value * Decimal(str(metadata.recovery_probability))

        # Create NFT
        nft = DebtNFT(
            token_id=token_id,
            original_record_id=record_id,
            metadata=metadata,
            face_value=face_value,
            current_value=current_value,
            asset_class=asset_class,
            risk_rating=risk_rating,
            owner_address=owner_address or f"0x{secrets.token_hex(20)}",
        )

        # Compute integrity hash
        nft.integrity_hash = nft.compute_integrity_hash()

        # Store
        self.tokens[token_id] = nft
        self.token_index_by_record[record_id] = token_id
        self.total_minted += 1
        self.total_face_value += face_value

        logger.info(f"Minted NFT {token_id[:16]}... for debt {record_id}")

        return nft

    def batch_tokenize(
        self,
        records: list[tuple[str, DebtMetadata]],
        owner_address: str = ""
    ) -> BatchTokenization:
        """
        Batch tokenization for portfolio operations

        Efficient processing of multiple debt records in single operation.

        Args:
            records: List of (record_id, metadata) tuples
            owner_address: Owner for all minted tokens

        Returns:
            BatchTokenization with results
        """
        batch_id = f"BATCH-{secrets.token_hex(8)}"

        batch = BatchTokenization(
            batch_id=batch_id,
            status="processing",
            started_at=datetime.now(),
            estimated_gas=len(records) * 150000,  # ~150k gas per mint
        )

        self.batches[batch_id] = batch

        token_hashes = []

        for record_id, metadata in records:
            try:
                nft = self.mint_nft(record_id, metadata, owner_address)
                batch.token_ids.append(nft.token_id)
                batch.total_face_value += nft.face_value
                batch.total_tokens += 1
                token_hashes.append(nft.integrity_hash)
            except Exception as e:
                logger.error(f"Failed to mint {record_id}: {e}")

        # Generate Merkle root for batch verification
        batch.merkle_root = CryptoUtils.generate_merkle_root(token_hashes)
        batch.actual_gas = batch.total_tokens * 145000  # Actual slightly less
        batch.status = "completed"
        batch.completed_at = datetime.now()

        logger.info(f"Batch {batch_id}: Minted {batch.total_tokens} tokens")

        return batch

    def get_token(self, token_id: str) -> DebtNFT | None:
        """Get token by ID"""
        return self.tokens.get(token_id)

    def get_token_by_record(self, record_id: str) -> DebtNFT | None:
        """Get token by original record ID"""
        token_id = self.token_index_by_record.get(record_id)
        return self.tokens.get(token_id) if token_id else None

    def transfer_token(
        self,
        token_id: str,
        to_address: str,
        from_address: str | None = None
    ) -> bool:
        """Transfer token ownership"""
        token = self.tokens.get(token_id)
        if not token:
            return False

        if token.is_locked:
            logger.warning(f"Cannot transfer locked token {token_id}")
            return False

        if from_address and token.owner_address != from_address:
            logger.warning(f"Transfer not authorized for {token_id}")
            return False

        token.owner_address = to_address
        token.last_transfer_at = datetime.now()

        return True

    def lock_token(self, token_id: str) -> bool:
        """Lock token (when added to pool)"""
        token = self.tokens.get(token_id)
        if token:
            token.is_locked = True
            return True
        return False

    def unlock_token(self, token_id: str) -> bool:
        """Unlock token (when removed from pool)"""
        token = self.tokens.get(token_id)
        if token:
            token.is_locked = False
            return True
        return False

    def _classify_asset(self, metadata: DebtMetadata) -> AssetClass:
        """Classify asset based on metadata"""
        category = metadata.debt_category.lower()

        if "bnpl" in category or "buy now" in category:
            if metadata.shadow_bureau_score >= 600:
                return AssetClass.BNPL_PRIME
            return AssetClass.BNPL_SUBPRIME
        elif "subscription" in category:
            if "tech" in category or "saas" in category:
                return AssetClass.SUBSCRIPTION_TECH
            elif "fitness" in category or "gym" in category:
                return AssetClass.SUBSCRIPTION_FITNESS
            return AssetClass.SUBSCRIPTION_MEDIA
        elif "gig" in category or "advance" in category:
            return AssetClass.GIG_ECONOMY
        elif "utility" in category or "electric" in category:
            return AssetClass.UTILITY_ELECTRIC
        elif "telecom" in category or "mobile" in category:
            return AssetClass.UTILITY_TELECOM
        elif "medical" in category:
            return AssetClass.MEDICAL_MICRO
        elif "rent" in category:
            return AssetClass.RENT_ARREARS
        else:
            return AssetClass.MIXED_MICRO

    def _calculate_risk_rating(self, metadata: DebtMetadata) -> RiskRating:
        """Calculate risk rating from metadata"""
        # Composite score: recovery prob (40%), shadow score (40%), age (20%)
        days_since_charge_off = (datetime.now() - metadata.charge_off_date).days if metadata.charge_off_date else 90

        score = (
            metadata.recovery_probability * 40 +
            (metadata.shadow_bureau_score / 850) * 40 +
            max(0, (180 - days_since_charge_off) / 180) * 20
        )

        if score >= 85:
            return RiskRating.AAA
        elif score >= 75:
            return RiskRating.AA
        elif score >= 65:
            return RiskRating.A
        elif score >= 55:
            return RiskRating.BBB
        elif score >= 45:
            return RiskRating.BB
        elif score >= 35:
            return RiskRating.B
        elif score >= 25:
            return RiskRating.CCC
        elif score >= 15:
            return RiskRating.CC
        else:
            return RiskRating.C


# =============================================================================
# CORE ENGINE - POOL MANAGEMENT
# =============================================================================

class PoolManager:
    """
    Pool management engine for aggregating tokenized assets

    Handles:
    - Pool creation and lifecycle
    - Asset aggregation
    - Metric calculation
    - Threshold enforcement
    """

    def __init__(self, tokenizer: AssetTokenizer):
        self.tokenizer = tokenizer
        self.pools: dict[str, DebtPool] = {}

    def create_pool(
        self,
        pool_name: str,
        asset_class: AssetClass,
        drop_ratio: Decimal = Decimal("0.80"),
        min_size: Decimal = MIN_POOL_SIZE,
        max_size: Decimal | None = None
    ) -> DebtPool:
        """
        Create new debt pool for asset class

        Args:
            pool_name: Human-readable pool name
            asset_class: Target asset class
            drop_ratio: Senior tranche ratio (default 80%)
            min_size: Minimum pool size (default $1M)
            max_size: Optional maximum pool size

        Returns:
            Created DebtPool
        """
        pool_id = f"POOL-{asset_class.value.upper()}-{secrets.token_hex(6)}"

        pool = DebtPool(
            pool_id=pool_id,
            pool_name=pool_name,
            asset_class=asset_class,
            drop_ratio=drop_ratio,
            tin_ratio=Decimal("1") - drop_ratio,
            min_pool_size=min_size,
            max_pool_size=max_size,
            pool_contract=f"0x{secrets.token_hex(20)}",
            drop_token_contract=f"0x{secrets.token_hex(20)}",
            tin_token_contract=f"0x{secrets.token_hex(20)}",
        )

        self.pools[pool_id] = pool
        logger.info(f"Created pool {pool_id}: {pool_name}")

        return pool

    def add_asset_to_pool(self, pool_id: str, token_id: str) -> bool:
        """
        Add tokenized asset to pool

        Args:
            pool_id: Target pool ID
            token_id: NFT token ID to add

        Returns:
            True if successful
        """
        pool = self.pools.get(pool_id)
        token = self.tokenizer.get_token(token_id)

        if not pool or not token:
            return False

        if pool.status != PoolStatus.OPEN:
            logger.warning(f"Pool {pool_id} not accepting assets")
            return False

        if token.is_locked:
            logger.warning(f"Token {token_id} already locked")
            return False

        # Check max size
        if pool.max_pool_size:
            projected = pool.metrics.total_face_value + token.face_value
            if projected > pool.max_pool_size:
                logger.warning(f"Pool {pool_id} would exceed max size")
                return False

        # Add to pool
        pool.asset_token_ids.append(token_id)
        token.pool_id = pool_id
        self.tokenizer.lock_token(token_id)

        # Update metrics
        self._update_pool_metrics(pool)

        return True

    def add_assets_batch(self, pool_id: str, token_ids: list[str]) -> int:
        """Add multiple assets to pool, returns count added"""
        added = 0
        for token_id in token_ids:
            if self.add_asset_to_pool(pool_id, token_id):
                added += 1
        return added

    def close_pool(self, pool_id: str) -> bool:
        """
        Close pool for new assets

        Pool must meet minimum size threshold.
        """
        pool = self.pools.get(pool_id)
        if not pool:
            return False

        # Only an OPEN pool can be closed; closing an ACTIVE pool would be
        # an invalid backward lifecycle transition.
        if pool.status != PoolStatus.OPEN:
            logger.warning(f"Pool {pool_id} cannot be closed from status {pool.status}")
            return False

        if pool.metrics.total_face_value < pool.min_pool_size:
            logger.warning(
                f"Pool {pool_id} below minimum size: "
                f"${pool.metrics.total_face_value:,.2f} < ${pool.min_pool_size:,.2f}"
            )
            return False

        pool.status = PoolStatus.CLOSED
        pool.closed_at = datetime.now()

        # Final metrics update
        self._update_pool_metrics(pool)

        logger.info(f"Closed pool {pool_id} with ${pool.metrics.total_face_value:,.2f}")

        return True

    def activate_pool(self, pool_id: str) -> bool:
        """Activate pool for yield generation"""
        pool = self.pools.get(pool_id)
        if not pool or pool.status != PoolStatus.CLOSED:
            return False

        pool.status = PoolStatus.ACTIVE
        pool.activated_at = datetime.now()
        pool.maturity_date = datetime.now() + timedelta(days=365)  # 1 year default

        return True

    def get_pool(self, pool_id: str) -> DebtPool | None:
        """Get pool by ID"""
        return self.pools.get(pool_id)

    def get_pool_assets(self, pool_id: str) -> list[DebtNFT]:
        """Get all assets in pool"""
        pool = self.pools.get(pool_id)
        if not pool:
            return []

        assets = []
        for token_id in pool.asset_token_ids:
            token = self.tokenizer.get_token(token_id)
            if token:
                assets.append(token)

        return assets

    def calculate_pool_metrics(self, pool_id: str) -> PoolMetrics | None:
        """Calculate comprehensive pool metrics"""
        pool = self.pools.get(pool_id)
        if not pool:
            return None

        self._update_pool_metrics(pool)
        return pool.metrics

    def _update_pool_metrics(self, pool: DebtPool) -> None:
        """Update pool metrics from constituent assets"""
        assets = self.get_pool_assets(pool.pool_id)

        if not assets:
            return

        metrics = pool.metrics

        # Basic counts
        metrics.total_assets = len(assets)
        metrics.total_face_value = sum(a.face_value for a in assets)
        metrics.total_current_value = sum(a.current_value for a in assets)

        # Weighted averages
        total_value = float(metrics.total_face_value)
        if total_value > 0:
            metrics.weighted_avg_risk_score = sum(
                a.metadata.quan_risk_score * float(a.face_value) for a in assets if a.metadata
            ) / total_value

            metrics.weighted_avg_shadow_score = sum(
                a.metadata.shadow_bureau_score * float(a.face_value) for a in assets if a.metadata
            ) / total_value

        # WAL calculation
        wal_days = []
        for asset in assets:
            if asset.metadata and asset.metadata.charge_off_date:
                days = (datetime.now() - asset.metadata.charge_off_date).days
                wal_days.append(days * float(asset.face_value))

        if wal_days and total_value > 0:
            metrics.weighted_avg_life_days = sum(wal_days) / total_value

        # Recovery rate from metadata
        recovery_probs = [a.metadata.recovery_probability for a in assets if a.metadata]
        if recovery_probs:
            metrics.recovery_rate = sum(recovery_probs) / len(recovery_probs)

        # Diversification
        creditors = set()
        categories = set()
        regions = set()

        for asset in assets:
            if asset.metadata:
                creditors.add(asset.metadata.original_creditor)
                categories.add(asset.metadata.debt_category)
                regions.add(asset.metadata.geo_region)

        metrics.unique_creditors = len(creditors)
        metrics.unique_categories = len(categories)
        metrics.geographic_spread = len(regions)

        # Concentration (HHI)
        if creditors:
            value_by_creditor = defaultdict(Decimal)
            for asset in assets:
                if asset.metadata:
                    value_by_creditor[asset.metadata.original_creditor] += asset.face_value

            shares = [(float(v) / total_value) ** 2 for v in value_by_creditor.values()]
            metrics.concentration_hhi = sum(shares)

        metrics.calculated_at = datetime.now()


# =============================================================================
# CORE ENGINE - TRANCHE STRUCTURE
# =============================================================================

class TrancheManager:
    """
    Tranche management following Tinlake DROP/TIN model

    DROP (Senior):
    - First claim on cash flows
    - Target yield: 5-8%
    - Protected by TIN subordination

    TIN (Junior):
    - First-loss position
    - Target yield: 12-20%
    - Absorbs losses before DROP
    """

    def __init__(self, pool_manager: PoolManager):
        self.pool_manager = pool_manager
        self.tranches: dict[str, TrancheToken] = {}
        self.waterfalls: list[WaterfallDistribution] = []
        self.current_epoch: dict[str, int] = {}  # pool_id -> epoch

    def create_tranches(self, pool_id: str) -> tuple[TrancheToken, TrancheToken]:
        """
        Create DROP and TIN tranches for pool

        Args:
            pool_id: Pool to create tranches for

        Returns:
            Tuple of (DROP token, TIN token)
        """
        pool = self.pool_manager.get_pool(pool_id)
        if not pool:
            raise ValueError(f"Pool {pool_id} not found")

        if pool.status not in [PoolStatus.CLOSED, PoolStatus.ACTIVE]:
            raise ValueError(f"Pool must be closed before tranche creation")

        total_value = pool.metrics.total_current_value

        # DROP (Senior) token
        drop_id = f"DROP-{pool_id}"
        drop_value = total_value * pool.drop_ratio

        drop_token = TrancheToken(
            token_id=drop_id,
            pool_id=pool_id,
            tranche_type=TrancheType.DROP,
            total_supply=drop_value,
            circulating_supply=Decimal("0"),
            token_price=Decimal("1.0"),
            nav_per_token=Decimal("1.0"),
            target_yield_low=DROP_TARGET_YIELD[0],
            target_yield_high=DROP_TARGET_YIELD[1],
            current_yield=(DROP_TARGET_YIELD[0] + DROP_TARGET_YIELD[1]) / 2,
            subordination_ratio=pool.tin_ratio,
            risk_rating=self._calculate_drop_rating(pool),
            priority=1,
            contract_address=pool.drop_token_contract,
        )

        # TIN (Junior) token
        tin_id = f"TIN-{pool_id}"
        tin_value = total_value * pool.tin_ratio

        tin_token = TrancheToken(
            token_id=tin_id,
            pool_id=pool_id,
            tranche_type=TrancheType.TIN,
            total_supply=tin_value,
            circulating_supply=Decimal("0"),
            token_price=Decimal("1.0"),
            nav_per_token=Decimal("1.0"),
            target_yield_low=TIN_TARGET_YIELD[0],
            target_yield_high=TIN_TARGET_YIELD[1],
            current_yield=(TIN_TARGET_YIELD[0] + TIN_TARGET_YIELD[1]) / 2,
            subordination_ratio=Decimal("0"),  # TIN is first-loss
            risk_rating=self._calculate_tin_rating(pool),
            priority=2,
            contract_address=pool.tin_token_contract,
        )

        self.tranches[drop_id] = drop_token
        self.tranches[tin_id] = tin_token
        self.current_epoch[pool_id] = 0

        logger.info(f"Created tranches for {pool_id}: DROP ${drop_value:,.2f}, TIN ${tin_value:,.2f}")

        return drop_token, tin_token

    def get_tranche(self, token_id: str) -> TrancheToken | None:
        """Get tranche token by ID"""
        return self.tranches.get(token_id)

    def get_pool_tranches(self, pool_id: str) -> tuple[TrancheToken | None, TrancheToken | None]:
        """Get DROP and TIN tranches for pool"""
        drop = self.tranches.get(f"DROP-{pool_id}")
        tin = self.tranches.get(f"TIN-{pool_id}")
        return drop, tin

    def execute_waterfall(
        self,
        pool_id: str,
        collections: Decimal,
        recoveries: Decimal = Decimal("0"),
        operating_expenses: Decimal = Decimal("0")
    ) -> WaterfallDistribution:
        """
        Execute payment waterfall distribution

        Tinlake waterfall order:
        1. Operating expenses
        2. DROP interest
        3. DROP principal repayment
        4. TIN interest
        5. TIN principal repayment
        6. Reserve

        Args:
            pool_id: Pool ID
            collections: Regular collections
            recoveries: Recovery amounts
            operating_expenses: Operating costs

        Returns:
            WaterfallDistribution with allocation details
        """
        pool = self.pool_manager.get_pool(pool_id)
        drop, tin = self.get_pool_tranches(pool_id)

        if not pool or not drop or not tin:
            raise ValueError(f"Pool or tranches not found for {pool_id}")

        # Advance epoch
        self.current_epoch[pool_id] = self.current_epoch.get(pool_id, 0) + 1
        epoch = self.current_epoch[pool_id]

        dist_id = f"WF-{pool_id}-E{epoch}"

        distribution = WaterfallDistribution(
            distribution_id=dist_id,
            pool_id=pool_id,
            epoch=epoch,
            total_cash_inflow=collections + recoveries,
            collections=collections,
            recoveries=recoveries,
            operating_expenses=operating_expenses,
        )

        # Available cash after expenses; floored at zero so that expenses
        # exceeding inflow never produce a negative interest allocation.
        available = max(Decimal("0"), collections + recoveries - operating_expenses)

        # Calculate required interest
        daily_rate_drop = drop.current_yield / Decimal("365")
        daily_rate_tin = tin.current_yield / Decimal("365")

        drop_interest_due = drop.circulating_supply * daily_rate_drop * EPOCH_DURATION_DAYS
        tin_interest_due = tin.circulating_supply * daily_rate_tin * EPOCH_DURATION_DAYS

        # Waterfall allocation
        remaining = available

        # 1. DROP interest (priority 1)
        if remaining >= drop_interest_due:
            distribution.drop_interest = drop_interest_due
            remaining -= drop_interest_due
        else:
            distribution.drop_interest = remaining
            distribution.drop_shortfall = drop_interest_due - remaining
            remaining = Decimal("0")

        # 2. DROP principal (if applicable - simplified)
        # In full implementation, this would handle redemption queues

        # 3. TIN interest (priority 2)
        if remaining >= tin_interest_due:
            distribution.tin_interest = tin_interest_due
            remaining -= tin_interest_due
        else:
            distribution.tin_interest = remaining
            distribution.tin_shortfall = tin_interest_due - remaining
            remaining = Decimal("0")

        # 4. Reserve contribution
        if remaining > 0:
            reserve_target = pool.metrics.total_face_value * pool.reserve_ratio
            reserve_need = max(Decimal("0"), reserve_target - pool.reserve_balance)
            reserve_contribution = min(remaining, reserve_need)
            distribution.reserve_contribution = reserve_contribution
            pool.reserve_balance += reserve_contribution
            remaining -= reserve_contribution

        # Any remainder stays in pool for next epoch

        distribution.status = "completed"
        distribution.executed_at = datetime.now()

        self.waterfalls.append(distribution)

        # Update tranche yields based on actual performance
        self._update_tranche_yields(pool_id, distribution)

        logger.info(
            f"Waterfall {dist_id}: DROP interest ${distribution.drop_interest:,.2f}, "
            f"TIN interest ${distribution.tin_interest:,.2f}"
        )

        return distribution

    def calculate_tranche_value(self, token_id: str) -> Decimal:
        """Calculate real-time tranche valuation"""
        tranche = self.tranches.get(token_id)
        if not tranche:
            return Decimal("0")

        pool = self.pool_manager.get_pool(tranche.pool_id)
        if not pool:
            return Decimal("0")

        # Base value from pool
        pool_value = pool.metrics.total_current_value + pool.reserve_balance

        if tranche.tranche_type == TrancheType.DROP:
            # DROP gets face value up to available, protected by TIN
            drop_face = tranche.total_supply
            return min(drop_face, pool_value)
        else:
            # TIN gets residual after DROP
            drop, _ = self.get_pool_tranches(tranche.pool_id)
            drop_claim = drop.total_supply if drop else Decimal("0")
            residual = max(Decimal("0"), pool_value - drop_claim)
            return residual

    def _calculate_drop_rating(self, pool: DebtPool) -> RiskRating:
        """Calculate DROP rating (typically 2-3 notches above pool)"""
        # Pool average rating
        avg_score = pool.metrics.weighted_avg_risk_score

        # Boost for subordination
        subordination_boost = float(pool.tin_ratio) * 30  # Up to 6 points for 20% sub

        adjusted_score = min(100, avg_score + subordination_boost)

        if adjusted_score >= 85:
            return RiskRating.AAA
        elif adjusted_score >= 75:
            return RiskRating.AA
        elif adjusted_score >= 65:
            return RiskRating.A
        elif adjusted_score >= 55:
            return RiskRating.BBB
        else:
            return RiskRating.BB

    def _calculate_tin_rating(self, pool: DebtPool) -> RiskRating:
        """Calculate TIN rating (typically 2-3 notches below pool)"""
        avg_score = pool.metrics.weighted_avg_risk_score

        # Penalty for first-loss position
        first_loss_penalty = 20

        adjusted_score = max(0, avg_score - first_loss_penalty)

        if adjusted_score >= 55:
            return RiskRating.BBB
        elif adjusted_score >= 45:
            return RiskRating.BB
        elif adjusted_score >= 35:
            return RiskRating.B
        elif adjusted_score >= 25:
            return RiskRating.CCC
        else:
            return RiskRating.CC

    def _update_tranche_yields(
        self,
        pool_id: str,
        distribution: WaterfallDistribution
    ) -> None:
        """Update tranche yields based on actual distributions"""
        drop, tin = self.get_pool_tranches(pool_id)

        if drop and drop.circulating_supply > 0:
            actual_drop_yield = (
                distribution.drop_interest / drop.circulating_supply
            ) * 365 / EPOCH_DURATION_DAYS
            drop.current_yield = actual_drop_yield

        if tin and tin.circulating_supply > 0:
            actual_tin_yield = (
                distribution.tin_interest / tin.circulating_supply
            ) * 365 / EPOCH_DURATION_DAYS
            tin.current_yield = actual_tin_yield


# =============================================================================
# CORE ENGINE - LIQUIDITY OPERATIONS
# =============================================================================

class LiquidityEngine:
    """
    Liquidity management for tokenized assets

    Handles:
    - Mark-to-model pricing
    - Secondary market order book
    - Instant liquidity calculations
    - DeFi collateral valuation
    """

    def __init__(
        self,
        tokenizer: AssetTokenizer,
        pool_manager: PoolManager,
        tranche_manager: TrancheManager
    ):
        self.tokenizer = tokenizer
        self.pool_manager = pool_manager
        self.tranche_manager = tranche_manager

        self.order_book: dict[str, list[OrderBookEntry]] = defaultdict(list)
        self.trade_history: list[dict] = []
        self.valuations: dict[str, AssetValuation] = {}

    def value_asset(self, token_id: str) -> AssetValuation:
        """
        Mark-to-model pricing for tokenized asset

        Valuation model:
        Base = Face Value * Recovery Probability
        + Seasoning adjustment
        + Performance adjustment
        + Market adjustment
        - Liquidity discount
        """
        token = self.tokenizer.get_token(token_id)
        if not token or not token.metadata:
            raise ValueError(f"Token {token_id} not found")

        metadata = token.metadata

        # Base value
        face_value = token.face_value
        base_value = face_value * Decimal(str(metadata.recovery_probability))

        # Seasoning adjustment (older debts better understood)
        days_old = (datetime.now() - metadata.origination_date).days
        seasoning_factor = min(1.0, days_old / 365) * 0.05  # Up to 5% boost
        seasoning_adj = base_value * Decimal(str(seasoning_factor))

        # Performance adjustment (based on payment history)
        if metadata.payment_velocity > 0:
            perf_factor = min(0.10, metadata.payment_velocity * 0.02)  # Up to 10%
            performance_adj = base_value * Decimal(str(perf_factor))
        else:
            performance_adj = Decimal("0")

        # Market adjustment (simplified - would use market data)
        market_adj = Decimal("0")  # Neutral

        # Liquidity discount
        if token.is_locked:  # In pool - higher liquidity
            liquidity_adj = Decimal("0")
        else:  # Individual NFT - lower liquidity
            liquidity_adj = -base_value * Decimal("0.05")  # 5% discount

        valuation = AssetValuation(
            token_id=token_id,
            valuation_date=datetime.now(),
            face_value=face_value,
            base_value=base_value,
            seasoning_adj=seasoning_adj,
            performance_adj=performance_adj,
            market_adj=market_adj,
            liquidity_adj=liquidity_adj,
        )

        valuation.calculate_fair_value()

        # Update token
        token.current_value = valuation.fair_value
        token.last_valuation_date = datetime.now()

        self.valuations[token_id] = valuation

        return valuation

    def place_order(
        self,
        token_id: str,
        side: OrderSide,
        price: Decimal,
        quantity: Decimal,
        trader_id: str,
        order_type: OrderType = OrderType.LIMIT,
        expires_in_hours: int = 24
    ) -> OrderBookEntry:
        """
        Place order in secondary market order book

        Args:
            token_id: Token to trade (NFT or tranche)
            side: Buy or sell
            price: Limit price (% of face for NFT, $ for tranche)
            quantity: Amount to trade
            trader_id: Trader identifier
            order_type: Order type
            expires_in_hours: Order expiration

        Returns:
            Created OrderBookEntry
        """
        order_id = f"ORD-{secrets.token_hex(8)}"

        order = OrderBookEntry(
            order_id=order_id,
            token_id=token_id,
            side=side,
            order_type=order_type,
            price=price,
            quantity=quantity,
            trader_id=trader_id,
            expires_at=datetime.now() + timedelta(hours=expires_in_hours),
        )

        self.order_book[token_id].append(order)

        # Attempt to match
        self._match_orders(token_id)

        return order

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order"""
        for token_id, orders in self.order_book.items():
            for order in orders:
                if order.order_id == order_id and order.status == "open":
                    order.status = "cancelled"
                    return True
        return False

    def get_order_book(self, token_id: str) -> dict:
        """Get order book for token"""
        orders = self.order_book.get(token_id, [])

        bids = sorted(
            [o for o in orders if o.side == OrderSide.BUY and o.status == "open"],
            key=lambda x: x.price,
            reverse=True
        )

        asks = sorted(
            [o for o in orders if o.side == OrderSide.SELL and o.status == "open"],
            key=lambda x: x.price
        )

        return {
            "token_id": token_id,
            "bids": [
                {"price": float(o.price), "quantity": float(o.remaining_quantity), "order_id": o.order_id}
                for o in bids[:10]
            ],
            "asks": [
                {"price": float(o.price), "quantity": float(o.remaining_quantity), "order_id": o.order_id}
                for o in asks[:10]
            ],
            "best_bid": float(bids[0].price) if bids else None,
            "best_ask": float(asks[0].price) if asks else None,
            "spread": float(asks[0].price - bids[0].price) if bids and asks else None,
        }

    def calculate_instant_liquidity(self, pool_id: str) -> Decimal:
        """
        Calculate instant liquidity available

        Instant liquidity = Reserve + Available credit lines
        """
        pool = self.pool_manager.get_pool(pool_id)
        if not pool:
            return Decimal("0")

        # Reserve balance
        reserve = pool.reserve_balance

        # Could add credit facility calculations here

        return reserve

    def calculate_liquidity_metrics(self, pool_id: str) -> LiquidityMetrics:
        """Calculate comprehensive liquidity metrics"""
        pool = self.pool_manager.get_pool(pool_id)
        drop, tin = self.tranche_manager.get_pool_tranches(pool_id)

        if not pool:
            raise ValueError(f"Pool {pool_id} not found")

        # Order book depth for tranches
        drop_book = self.get_order_book(f"DROP-{pool_id}") if drop else {"bids": [], "asks": []}
        tin_book = self.get_order_book(f"TIN-{pool_id}") if tin else {"bids": [], "asks": []}

        bid_depth = sum(b["quantity"] for b in drop_book["bids"]) + sum(b["quantity"] for b in tin_book["bids"])
        ask_depth = sum(a["quantity"] for a in drop_book["asks"]) + sum(a["quantity"] for a in tin_book["asks"])

        # Spread
        spread = Decimal("0")
        if drop_book["spread"]:
            spread = Decimal(str(drop_book["spread"]))

        # Collateral value (for DeFi)
        collateral_value = pool.metrics.total_current_value
        ltv_ratio = Decimal("0.70")  # 70% LTV
        max_borrow = collateral_value * ltv_ratio

        metrics = LiquidityMetrics(
            pool_id=pool_id,
            instant_liquidity=self.calculate_instant_liquidity(pool_id),
            bid_depth=Decimal(str(bid_depth)),
            ask_depth=Decimal(str(ask_depth)),
            bid_ask_spread=spread,
            collateral_value=collateral_value,
            ltv_ratio=ltv_ratio,
            max_borrow_capacity=max_borrow,
        )

        return metrics

    def _match_orders(self, token_id: str) -> None:
        """Match orders in the order book"""
        orders = self.order_book.get(token_id, [])

        bids = sorted(
            [o for o in orders if o.side == OrderSide.BUY and o.status == "open"],
            key=lambda x: x.price,
            reverse=True
        )

        asks = sorted(
            [o for o in orders if o.side == OrderSide.SELL and o.status == "open"],
            key=lambda x: x.price
        )

        for bid in bids:
            for ask in asks:
                if bid.price >= ask.price and bid.remaining_quantity > 0 and ask.remaining_quantity > 0:
                    # Match found
                    match_quantity = min(bid.remaining_quantity, ask.remaining_quantity)
                    match_price = (bid.price + ask.price) / 2  # Midpoint

                    bid.filled_quantity += match_quantity
                    ask.filled_quantity += match_quantity

                    if bid.filled_quantity >= bid.quantity:
                        bid.status = "filled"
                    else:
                        bid.status = "partial"

                    if ask.filled_quantity >= ask.quantity:
                        ask.status = "filled"
                    else:
                        ask.status = "partial"

                    # Record trade
                    self.trade_history.append({
                        "trade_id": f"TRD-{secrets.token_hex(6)}",
                        "token_id": token_id,
                        "price": float(match_price),
                        "quantity": float(match_quantity),
                        "buyer": bid.trader_id,
                        "seller": ask.trader_id,
                        "timestamp": datetime.now().isoformat(),
                    })


# =============================================================================
# CORE ENGINE - INVESTOR INTERFACE
# =============================================================================

class InvestorPortal:
    """
    Investor interface for portfolio management

    Handles:
    - Subscriptions (buying DROP/TIN)
    - Redemptions
    - Yield distribution
    - NAV calculation
    """

    def __init__(
        self,
        pool_manager: PoolManager,
        tranche_manager: TrancheManager,
        liquidity_engine: LiquidityEngine
    ):
        self.pool_manager = pool_manager
        self.tranche_manager = tranche_manager
        self.liquidity_engine = liquidity_engine

        self.positions: dict[str, dict[str, InvestorPosition]] = defaultdict(dict)  # investor -> pool -> position
        self.distributions: list[YieldDistribution] = []
        self.redemption_queue: list[RedemptionRequest] = []

    def subscribe(
        self,
        investor_id: str,
        pool_id: str,
        tranche_type: TrancheType,
        amount: Decimal
    ) -> InvestorPosition:
        """
        Subscribe to pool tranche

        Args:
            investor_id: Investor identifier
            pool_id: Pool to invest in
            tranche_type: DROP or TIN
            amount: Investment amount in $

        Returns:
            Updated InvestorPosition
        """
        drop, tin = self.tranche_manager.get_pool_tranches(pool_id)

        if tranche_type == TrancheType.DROP:
            tranche = drop
        else:
            tranche = tin

        if not tranche:
            raise ValueError(f"Tranche not found for {pool_id}")

        # Calculate tokens to receive
        tokens = amount / tranche.token_price

        # Check availability
        available = tranche.total_supply - tranche.circulating_supply
        if tokens > available:
            raise ValueError(f"Insufficient supply: {tokens} requested, {available} available")

        # Get or create position
        if pool_id not in self.positions[investor_id]:
            self.positions[investor_id][pool_id] = InvestorPosition(
                investor_id=investor_id,
                pool_id=pool_id,
                first_investment=datetime.now(),
            )

        position = self.positions[investor_id][pool_id]

        # Update position
        if tranche_type == TrancheType.DROP:
            position.drop_tokens += tokens
            position.drop_cost_basis += amount
            position.drop_current_value = position.drop_tokens * tranche.nav_per_token
        else:
            position.tin_tokens += tokens
            position.tin_cost_basis += amount
            position.tin_current_value = position.tin_tokens * tranche.nav_per_token

        # Update tranche supply
        tranche.circulating_supply += tokens

        position.last_activity = datetime.now()

        logger.info(f"Investor {investor_id} subscribed {amount} to {tranche_type.value} in {pool_id}")

        return position

    def request_redemption(
        self,
        investor_id: str,
        pool_id: str,
        tranche_type: TrancheType,
        token_amount: Decimal
    ) -> RedemptionRequest:
        """
        Request redemption of tranche tokens

        Redemptions are processed at epoch end following Tinlake model.
        """
        position = self.positions.get(investor_id, {}).get(pool_id)
        if not position:
            raise ValueError(f"No position found for {investor_id} in {pool_id}")

        # Check balance
        if tranche_type == TrancheType.DROP:
            if token_amount > position.drop_tokens:
                raise ValueError(f"Insufficient DROP balance")
        else:
            if token_amount > position.tin_tokens:
                raise ValueError(f"Insufficient TIN balance")

        current_epoch = self.tranche_manager.current_epoch.get(pool_id, 0)

        request = RedemptionRequest(
            request_id=f"RED-{secrets.token_hex(8)}",
            investor_id=investor_id,
            pool_id=pool_id,
            tranche_type=tranche_type,
            token_amount=token_amount,
            epoch_submitted=current_epoch,
        )

        self.redemption_queue.append(request)

        # Update pending redemption
        if tranche_type == TrancheType.DROP:
            position.pending_redemption_drop += token_amount
        else:
            position.pending_redemption_tin += token_amount

        return request

    def process_redemptions(self, pool_id: str) -> list[RedemptionRequest]:
        """Process pending redemptions for pool"""
        pool = self.pool_manager.get_pool(pool_id)
        drop, tin = self.tranche_manager.get_pool_tranches(pool_id)

        if not pool:
            return []

        # Available liquidity
        available = self.liquidity_engine.calculate_instant_liquidity(pool_id)

        processed = []
        current_epoch = self.tranche_manager.current_epoch.get(pool_id, 0)

        # Process DROP redemptions first (senior priority)
        drop_requests = [
            r for r in self.redemption_queue
            if r.pool_id == pool_id
            and r.tranche_type == TrancheType.DROP
            and r.status == "pending"
        ]

        for request in drop_requests:
            if not drop:
                continue

            redemption_value = request.token_amount * drop.nav_per_token

            if redemption_value <= available:
                request.execution_price = drop.nav_per_token
                request.cash_amount = redemption_value
                request.status = "completed"
                request.epoch_processed = current_epoch
                request.processed_at = datetime.now()

                # Update position
                position = self.positions.get(request.investor_id, {}).get(pool_id)
                if position:
                    position.drop_tokens -= request.token_amount
                    position.pending_redemption_drop -= request.token_amount
                    position.drop_current_value = position.drop_tokens * drop.nav_per_token

                # Update tranche
                drop.circulating_supply -= request.token_amount

                available -= redemption_value
                processed.append(request)

        # Then TIN redemptions
        tin_requests = [
            r for r in self.redemption_queue
            if r.pool_id == pool_id
            and r.tranche_type == TrancheType.TIN
            and r.status == "pending"
        ]

        for request in tin_requests:
            if not tin:
                continue

            redemption_value = request.token_amount * tin.nav_per_token

            if redemption_value <= available:
                request.execution_price = tin.nav_per_token
                request.cash_amount = redemption_value
                request.status = "completed"
                request.epoch_processed = current_epoch
                request.processed_at = datetime.now()

                # Update position
                position = self.positions.get(request.investor_id, {}).get(pool_id)
                if position:
                    position.tin_tokens -= request.token_amount
                    position.pending_redemption_tin -= request.token_amount
                    position.tin_current_value = position.tin_tokens * tin.nav_per_token

                # Update tranche
                tin.circulating_supply -= request.token_amount

                available -= redemption_value
                processed.append(request)

        return processed

    def distribute_yield(
        self,
        pool_id: str,
        waterfall: WaterfallDistribution
    ) -> list[YieldDistribution]:
        """Distribute yield to investors based on waterfall"""
        drop, tin = self.tranche_manager.get_pool_tranches(pool_id)

        distributions = []

        # Find all investors in this pool
        for investor_id, pools in self.positions.items():
            if pool_id not in pools:
                continue

            position = pools[pool_id]

            # Calculate share of yield
            drop_share = Decimal("0")
            tin_share = Decimal("0")

            if drop and drop.circulating_supply > 0 and position.drop_tokens > 0:
                drop_share = (position.drop_tokens / drop.circulating_supply) * waterfall.drop_interest

            if tin and tin.circulating_supply > 0 and position.tin_tokens > 0:
                tin_share = (position.tin_tokens / tin.circulating_supply) * waterfall.tin_interest

            if drop_share > 0 or tin_share > 0:
                dist = YieldDistribution(
                    distribution_id=f"YIELD-{secrets.token_hex(6)}",
                    investor_id=investor_id,
                    pool_id=pool_id,
                    epoch=waterfall.epoch,
                    drop_yield=drop_share,
                    tin_yield=tin_share,
                    total_yield=drop_share + tin_share,
                    drop_yield_rate=drop.current_yield if drop else Decimal("0"),
                    tin_yield_rate=tin.current_yield if tin else Decimal("0"),
                    status="distributed",
                    distributed_at=datetime.now(),
                )

                position.total_yield_earned += dist.total_yield
                distributions.append(dist)
                self.distributions.append(dist)

        return distributions

    def calculate_nav(self, pool_id: str) -> NAVCalculation:
        """Calculate Net Asset Value for pool"""
        pool = self.pool_manager.get_pool(pool_id)
        drop, tin = self.tranche_manager.get_pool_tranches(pool_id)

        if not pool:
            raise ValueError(f"Pool {pool_id} not found")

        # Asset value
        total_asset_value = pool.metrics.total_current_value
        cash_reserve = pool.reserve_balance

        # Simplified accrued interest (would be more complex in practice)
        accrued_interest = Decimal("0")

        total_assets = total_asset_value + cash_reserve + accrued_interest

        # Liabilities (tranche obligations)
        drop_liability = drop.circulating_supply * drop.nav_per_token if drop else Decimal("0")
        tin_liability = tin.circulating_supply * tin.nav_per_token if tin else Decimal("0")

        # NAV calculation
        # DROP gets priority claim
        drop_nav = min(drop_liability, total_assets)
        remaining = total_assets - drop_nav

        # TIN gets residual
        tin_nav = max(Decimal("0"), remaining)

        total_nav = drop_nav + tin_nav

        # Per token NAV
        drop_nav_per_token = drop_nav / drop.circulating_supply if drop and drop.circulating_supply > 0 else Decimal("1.0")
        tin_nav_per_token = tin_nav / tin.circulating_supply if tin and tin.circulating_supply > 0 else Decimal("1.0")

        # Update tranches
        if drop:
            drop.nav_per_token = drop_nav_per_token
        if tin:
            tin.nav_per_token = tin_nav_per_token

        nav = NAVCalculation(
            pool_id=pool_id,
            calculation_date=datetime.now(),
            total_asset_value=total_asset_value,
            cash_reserve=cash_reserve,
            accrued_interest=accrued_interest,
            drop_liability=drop_liability,
            tin_liability=tin_liability,
            total_nav=total_nav,
            drop_nav=drop_nav,
            tin_nav=tin_nav,
            drop_nav_per_token=drop_nav_per_token,
            tin_nav_per_token=tin_nav_per_token,
        )

        return nav

    def get_position(self, investor_id: str, pool_id: str) -> InvestorPosition | None:
        """Get investor position in pool"""
        return self.positions.get(investor_id, {}).get(pool_id)

    def get_portfolio_summary(self, investor_id: str) -> dict:
        """Get investor's full portfolio summary"""
        investor_pools = self.positions.get(investor_id, {})

        total_invested = Decimal("0")
        total_current_value = Decimal("0")
        total_yield = Decimal("0")

        positions = []

        for pool_id, position in investor_pools.items():
            pool = self.pool_manager.get_pool(pool_id)
            drop, tin = self.tranche_manager.get_pool_tranches(pool_id)

            invested = position.drop_cost_basis + position.tin_cost_basis
            current = position.drop_current_value + position.tin_current_value

            total_invested += invested
            total_current_value += current
            total_yield += position.total_yield_earned

            positions.append({
                "pool_id": pool_id,
                "pool_name": pool.pool_name if pool else "Unknown",
                "drop_tokens": float(position.drop_tokens),
                "drop_value": float(position.drop_current_value),
                "drop_yield_rate": float(drop.current_yield) if drop else 0,
                "tin_tokens": float(position.tin_tokens),
                "tin_value": float(position.tin_current_value),
                "tin_yield_rate": float(tin.current_yield) if tin else 0,
                "total_invested": float(invested),
                "total_current_value": float(current),
                "yield_earned": float(position.total_yield_earned),
                "return_pct": float((current - invested) / invested * 100) if invested > 0 else 0,
            })

        return {
            "investor_id": investor_id,
            "total_invested": float(total_invested),
            "total_current_value": float(total_current_value),
            "total_yield_earned": float(total_yield),
            "total_return_pct": float((total_current_value - total_invested) / total_invested * 100) if total_invested > 0 else 0,
            "positions": positions,
        }


# =============================================================================
# CORE ENGINE - ON-CHAIN SIMULATION
# =============================================================================

class BlockchainSimulator:
    """
    Simulates blockchain settlement and smart contract execution

    Provides:
    - Transaction simulation
    - Token ownership tracking
    - Payment waterfall execution
    - Compliance verification
    """

    def __init__(self):
        self.current_block = 0
        self.transactions: list[BlockchainTransaction] = []
        self.contracts: dict[str, SmartContractState] = {}
        self.token_ownership: dict[str, str] = {}  # token_id -> address
        self.compliance_records: dict[str, ComplianceRecord] = {}

        # Simulated addresses
        self.protocol_address = f"0x{secrets.token_hex(20)}"
        self.treasury_address = f"0x{secrets.token_hex(20)}"

    def deploy_pool_contracts(self, pool: DebtPool) -> dict[str, str]:
        """Deploy pool smart contracts (simulated)"""
        self.current_block += 1

        # Pool contract
        pool_contract = SmartContractState(
            contract_address=pool.pool_contract,
            contract_type="pool",
            owner=self.protocol_address,
            state={
                "pool_id": pool.pool_id,
                "asset_class": pool.asset_class.value,
                "status": pool.status.value,
                "total_assets": 0,
            },
            deployer=self.protocol_address,
        )

        # DROP token contract
        drop_contract = SmartContractState(
            contract_address=pool.drop_token_contract,
            contract_type="drop_token",
            owner=pool.pool_contract,
            state={
                "name": f"DROP-{pool.pool_id}",
                "symbol": "DROP",
                "total_supply": 0,
                "decimals": 18,
            },
            deployer=self.protocol_address,
        )

        # TIN token contract
        tin_contract = SmartContractState(
            contract_address=pool.tin_token_contract,
            contract_type="tin_token",
            owner=pool.pool_contract,
            state={
                "name": f"TIN-{pool.pool_id}",
                "symbol": "TIN",
                "total_supply": 0,
                "decimals": 18,
            },
            deployer=self.protocol_address,
        )

        self.contracts[pool.pool_contract] = pool_contract
        self.contracts[pool.drop_token_contract] = drop_contract
        self.contracts[pool.tin_token_contract] = tin_contract

        # Record transactions
        for contract in [pool_contract, drop_contract, tin_contract]:
            tx = BlockchainTransaction(
                tx_hash=f"0x{secrets.token_hex(32)}",
                block_number=self.current_block,
                from_address=self.protocol_address,
                to_address="0x0",  # Contract creation
                contract_address=contract.contract_address,
                function_name="constructor",
                gas_used=2000000,
                status="confirmed",
                confirmations=1,
                confirmed_at=datetime.now(),
            )
            self.transactions.append(tx)

        return {
            "pool": pool.pool_contract,
            "drop": pool.drop_token_contract,
            "tin": pool.tin_token_contract,
        }

    def mint_nft_onchain(self, nft: DebtNFT) -> BlockchainTransaction:
        """Simulate NFT minting on-chain"""
        self.current_block += 1

        tx = BlockchainTransaction(
            tx_hash=f"0x{secrets.token_hex(32)}",
            block_number=self.current_block,
            from_address=self.protocol_address,
            to_address=nft.owner_address,
            contract_address=f"0x{secrets.token_hex(20)}",  # NFT contract
            function_name="mint",
            parameters={
                "token_id": nft.token_id,
                "metadata_hash": nft.metadata.metadata_hash if nft.metadata else "",
                "face_value": str(nft.face_value),
            },
            gas_used=150000,
            status="confirmed",
            confirmations=1,
            confirmed_at=datetime.now(),
        )

        self.transactions.append(tx)
        self.token_ownership[nft.token_id] = nft.owner_address

        return tx

    def execute_waterfall_onchain(
        self,
        distribution: WaterfallDistribution
    ) -> BlockchainTransaction:
        """Simulate waterfall distribution on-chain"""
        self.current_block += 1

        tx = BlockchainTransaction(
            tx_hash=f"0x{secrets.token_hex(32)}",
            block_number=self.current_block,
            from_address=self.protocol_address,
            to_address=self.protocol_address,
            contract_address=self.protocol_address,
            function_name="executeWaterfall",
            parameters={
                "pool_id": distribution.pool_id,
                "epoch": distribution.epoch,
                "collections": str(distribution.collections),
                "drop_interest": str(distribution.drop_interest),
                "tin_interest": str(distribution.tin_interest),
            },
            gas_used=500000,
            status="confirmed",
            confirmations=1,
            confirmed_at=datetime.now(),
        )

        self.transactions.append(tx)

        return tx

    def transfer_token_onchain(
        self,
        token_id: str,
        from_address: str,
        to_address: str
    ) -> BlockchainTransaction:
        """Simulate token transfer on-chain"""
        self.current_block += 1

        tx = BlockchainTransaction(
            tx_hash=f"0x{secrets.token_hex(32)}",
            block_number=self.current_block,
            from_address=from_address,
            to_address=to_address,
            contract_address=self.protocol_address,
            function_name="transfer",
            parameters={
                "token_id": token_id,
            },
            gas_used=65000,
            status="confirmed",
            confirmations=1,
            confirmed_at=datetime.now(),
        )

        self.transactions.append(tx)
        self.token_ownership[token_id] = to_address

        return tx

    def create_compliance_record(
        self,
        pool_id: str,
        regulation: str = "reg_d",
        accredited_only: bool = True
    ) -> ComplianceRecord:
        """Create compliance record for pool"""
        record = ComplianceRecord(
            record_id=f"COMP-{secrets.token_hex(6)}",
            pool_id=pool_id,
            regulation=regulation,
            accredited_only=accredited_only,
            max_investors=None if regulation == "reg_d" else 2000,
            allowed_jurisdictions=["US"],
            blocked_jurisdictions=["CU", "IR", "KP", "SY"],  # OFAC
            kyc_required=True,
        )

        self.compliance_records[pool_id] = record

        return record

    def verify_investor_compliance(
        self,
        pool_id: str,
        investor_address: str,
        is_accredited: bool,
        jurisdiction: str,
        kyc_verified: bool
    ) -> tuple[bool, str]:
        """Verify investor compliance for pool"""
        record = self.compliance_records.get(pool_id)

        if not record:
            return False, "No compliance record found"

        if record.accredited_only and not is_accredited:
            return False, "Investor must be accredited"

        if jurisdiction in record.blocked_jurisdictions:
            return False, f"Jurisdiction {jurisdiction} is restricted"

        if record.allowed_jurisdictions and jurisdiction not in record.allowed_jurisdictions:
            return False, f"Jurisdiction {jurisdiction} not allowed"

        if record.kyc_required and not kyc_verified:
            return False, "KYC verification required"

        if record.max_investors and record.current_investors >= record.max_investors:
            return False, "Maximum investor limit reached"

        return True, "Compliance verified"

    def get_transaction_history(self, address: str) -> list[BlockchainTransaction]:
        """Get transaction history for address"""
        return [
            tx for tx in self.transactions
            if tx.from_address == address or tx.to_address == address
        ]

    def get_block_info(self) -> dict:
        """Get current blockchain state"""
        return {
            "current_block": self.current_block,
            "total_transactions": len(self.transactions),
            "total_contracts": len(self.contracts),
            "total_tokens_tracked": len(self.token_ownership),
        }


# =============================================================================
# UNIFIED RWA TOKENIZATION PLATFORM
# =============================================================================

class RWATokenizationPlatform:
    """
    Unified platform for Real-World Asset tokenization

    Integrates all components:
    - Asset Tokenization
    - Pool Management
    - Tranche Structure
    - Liquidity Operations
    - Investor Interface
    - On-Chain Simulation
    """

    def __init__(self):
        # Initialize all components
        self.tokenizer = AssetTokenizer()
        self.pool_manager = PoolManager(self.tokenizer)
        self.tranche_manager = TrancheManager(self.pool_manager)
        self.liquidity_engine = LiquidityEngine(
            self.tokenizer,
            self.pool_manager,
            self.tranche_manager
        )
        self.investor_portal = InvestorPortal(
            self.pool_manager,
            self.tranche_manager,
            self.liquidity_engine
        )
        self.blockchain = BlockchainSimulator()

        logger.info("RWA Tokenization Platform initialized")

    def tokenize_portfolio(
        self,
        records: list[tuple[str, DebtMetadata]],
        pool_name: str,
        asset_class: AssetClass
    ) -> dict:
        """
        End-to-end portfolio tokenization

        1. Batch tokenize debt records
        2. Create pool
        3. Add assets to pool
        4. Create tranches
        5. Deploy on-chain

        Returns summary of tokenization
        """
        # 1. Batch tokenize
        batch = self.tokenizer.batch_tokenize(records)

        # 2. Create pool
        pool = self.pool_manager.create_pool(
            pool_name=pool_name,
            asset_class=asset_class,
        )

        # 3. Add assets to pool
        added = self.pool_manager.add_assets_batch(pool.pool_id, batch.token_ids)

        # 4. Close pool (if minimum met)
        if pool.metrics.total_face_value >= pool.min_pool_size:
            self.pool_manager.close_pool(pool.pool_id)
            self.pool_manager.activate_pool(pool.pool_id)

            # 5. Create tranches
            drop, tin = self.tranche_manager.create_tranches(pool.pool_id)

            # 6. Deploy contracts
            contracts = self.blockchain.deploy_pool_contracts(pool)

            # 7. Create compliance record
            compliance = self.blockchain.create_compliance_record(pool.pool_id)

            return {
                "success": True,
                "batch_id": batch.batch_id,
                "tokens_minted": batch.total_tokens,
                "total_face_value": float(batch.total_face_value),
                "pool_id": pool.pool_id,
                "pool_status": pool.status.value,
                "drop_token": {
                    "id": drop.token_id,
                    "supply": float(drop.total_supply),
                    "yield_range": f"{float(drop.target_yield_low)*100:.1f}%-{float(drop.target_yield_high)*100:.1f}%",
                    "rating": drop.risk_rating.rating,
                },
                "tin_token": {
                    "id": tin.token_id,
                    "supply": float(tin.total_supply),
                    "yield_range": f"{float(tin.target_yield_low)*100:.1f}%-{float(tin.target_yield_high)*100:.1f}%",
                    "rating": tin.risk_rating.rating,
                },
                "contracts": contracts,
                "compliance": {
                    "regulation": compliance.regulation,
                    "accredited_only": compliance.accredited_only,
                },
            }
        else:
            return {
                "success": False,
                "batch_id": batch.batch_id,
                "tokens_minted": batch.total_tokens,
                "total_face_value": float(batch.total_face_value),
                "pool_id": pool.pool_id,
                "pool_status": pool.status.value,
                "message": f"Pool below minimum size (${float(pool.min_pool_size):,.0f})",
            }

    def run_epoch(self, pool_id: str, collections: Decimal, recoveries: Decimal = Decimal("0")) -> dict:
        """
        Execute a full epoch cycle

        1. Execute waterfall
        2. Calculate NAV
        3. Distribute yields
        4. Process redemptions
        """
        # 1. Waterfall
        waterfall = self.tranche_manager.execute_waterfall(
            pool_id,
            collections,
            recoveries,
            operating_expenses=collections * Decimal("0.01"),  # 1% expense ratio
        )

        # 2. NAV
        nav = self.investor_portal.calculate_nav(pool_id)

        # 3. Yields
        distributions = self.investor_portal.distribute_yield(pool_id, waterfall)

        # 4. Redemptions
        redemptions = self.investor_portal.process_redemptions(pool_id)

        # 5. On-chain settlement
        self.blockchain.execute_waterfall_onchain(waterfall)

        return {
            "epoch": waterfall.epoch,
            "pool_id": pool_id,
            "waterfall": {
                "total_inflow": float(waterfall.total_cash_inflow),
                "drop_interest": float(waterfall.drop_interest),
                "tin_interest": float(waterfall.tin_interest),
                "reserve_contribution": float(waterfall.reserve_contribution),
            },
            "nav": {
                "total": float(nav.total_nav),
                "drop_per_token": float(nav.drop_nav_per_token),
                "tin_per_token": float(nav.tin_nav_per_token),
            },
            "distributions": len(distributions),
            "redemptions_processed": len(redemptions),
        }

    def get_platform_metrics(self) -> dict:
        """Get platform-wide metrics"""
        total_face_value = Decimal("0")
        total_current_value = Decimal("0")
        total_pools = len(self.pool_manager.pools)
        active_pools = 0

        for pool in self.pool_manager.pools.values():
            total_face_value += pool.metrics.total_face_value
            total_current_value += pool.metrics.total_current_value
            if pool.status == PoolStatus.ACTIVE:
                active_pools += 1

        return {
            "total_tokens_minted": self.tokenizer.total_minted,
            "total_face_value": float(total_face_value),
            "total_current_value": float(total_current_value),
            "total_pools": total_pools,
            "active_pools": active_pools,
            "total_tranches": len(self.tranche_manager.tranches),
            "blockchain": self.blockchain.get_block_info(),
        }


# =============================================================================
# DEMONSTRATION
# =============================================================================

def run_demo():
    """
    Full working demonstration of RWA tokenization

    Simulates:
    1. Creating sample debt portfolio
    2. Tokenizing as NFTs
    3. Creating and filling pool
    4. Issuing DROP/TIN tranches
    5. Investor subscriptions
    6. Epoch execution with yields
    7. Liquidity operations
    """
    import random

    print("=" * 80)
    print("QUAN RECOVERY - RWA TOKENIZATION PLATFORM DEMO")
    print("Centrifuge/Tinlake Model Implementation")
    print("=" * 80)
    print()

    # Initialize platform
    platform = RWATokenizationPlatform()

    # ==========================================================================
    # PHASE 1: CREATE SAMPLE DEBT PORTFOLIO
    # ==========================================================================
    print("PHASE 1: CREATING SAMPLE DEBT PORTFOLIO")
    print("-" * 50)

    categories = ["BNPL - Klarna", "BNPL - Afterpay", "Subscription - Netflix",
                  "Subscription - Spotify", "Gig - DoorDash Advance",
                  "Medical - LabCorp", "Utility - PG&E", "Telecom - AT&T"]
    creditors = ["Klarna", "Afterpay", "Netflix", "Spotify", "DoorDash",
                 "LabCorp", "PG&E", "AT&T", "Affirm", "Quadpay"]
    regions = ["CA", "TX", "NY", "FL", "IL", "PA", "OH", "GA", "NC", "AZ"]

    sample_records = []

    # Generate 3000 records to exceed $1M minimum pool size
    for i in range(3000):
        # Mix of small and larger debts to get realistic distribution
        if random.random() < 0.7:
            face_value = Decimal(str(random.uniform(50, 500)))  # 70% small debts
        else:
            face_value = Decimal(str(random.uniform(500, 2500)))  # 30% larger debts
        recovery_prob = random.uniform(0.35, 0.75)
        category = random.choice(categories)

        metadata = DebtMetadata(
            original_creditor=random.choice(creditors),
            debt_category=category,
            origination_date=datetime.now() - timedelta(days=random.randint(30, 365)),
            original_amount=face_value * Decimal(str(random.uniform(1.0, 1.5))),
            charge_off_date=datetime.now() - timedelta(days=random.randint(30, 180)),
            charge_off_amount=face_value,
            total_payments_made=face_value * Decimal(str(random.uniform(0, 0.3))),
            longest_delinquency_days=random.randint(30, 120),
            payment_velocity=random.uniform(0, 0.5),
            quan_risk_score=random.uniform(30, 80),
            shadow_bureau_score=random.randint(400, 750),
            recovery_probability=recovery_prob,
            geo_region=random.choice(regions),
            age_bucket=random.choice(["18-24", "25-34", "35-44", "45-54", "55+"]),
        )

        sample_records.append((f"DEBT-{i:05d}", metadata))

    total_face = sum(r[1].charge_off_amount for r in sample_records)
    print(f"  Created {len(sample_records)} sample debt records")
    print(f"  Total Face Value: ${total_face:,.2f}")
    print()

    # ==========================================================================
    # PHASE 2: TOKENIZE PORTFOLIO
    # ==========================================================================
    print("PHASE 2: TOKENIZING PORTFOLIO")
    print("-" * 50)

    result = platform.tokenize_portfolio(
        records=sample_records,
        pool_name="QUAN BNPL Portfolio 2026-Q1",
        asset_class=AssetClass.BNPL_SUBPRIME,
    )

    print(f"  Batch ID: {result['batch_id']}")
    print(f"  Tokens Minted: {result['tokens_minted']}")
    print(f"  Total Face Value: ${result['total_face_value']:,.2f}")
    print(f"  Pool ID: {result['pool_id']}")
    print(f"  Pool Status: {result['pool_status']}")
    print()

    if result['success']:
        print("  DROP Token (Senior Tranche):")
        print(f"    - ID: {result['drop_token']['id']}")
        print(f"    - Supply: ${result['drop_token']['supply']:,.2f}")
        print(f"    - Target Yield: {result['drop_token']['yield_range']}")
        print(f"    - Rating: {result['drop_token']['rating']}")
        print()
        print("  TIN Token (Junior Tranche):")
        print(f"    - ID: {result['tin_token']['id']}")
        print(f"    - Supply: ${result['tin_token']['supply']:,.2f}")
        print(f"    - Target Yield: {result['tin_token']['yield_range']}")
        print(f"    - Rating: {result['tin_token']['rating']}")
        print()
        print("  Smart Contracts Deployed:")
        for name, address in result['contracts'].items():
            print(f"    - {name.upper()}: {address[:20]}...")
        print()

    pool_id = result['pool_id']

    # ==========================================================================
    # PHASE 3: INVESTOR SUBSCRIPTIONS
    # ==========================================================================
    print("PHASE 3: INVESTOR SUBSCRIPTIONS")
    print("-" * 50)

    # Simulate investors
    investors = [
        ("INV-001", "Institutional Credit Fund", Decimal("500000"), TrancheType.DROP),
        ("INV-002", "Yield Seeking Family Office", Decimal("200000"), TrancheType.DROP),
        ("INV-003", "Hedge Fund Alpha", Decimal("100000"), TrancheType.TIN),
        ("INV-004", "DeFi Protocol Treasury", Decimal("50000"), TrancheType.TIN),
    ]

    for inv_id, name, amount, tranche in investors:
        try:
            position = platform.investor_portal.subscribe(
                investor_id=inv_id,
                pool_id=pool_id,
                tranche_type=tranche,
                amount=amount,
            )
            print(f"  {name} ({inv_id})")
            print(f"    - Subscribed ${amount:,.2f} to {tranche.value}")
            if tranche == TrancheType.DROP:
                print(f"    - DROP Tokens: {float(position.drop_tokens):,.2f}")
            else:
                print(f"    - TIN Tokens: {float(position.tin_tokens):,.2f}")
        except Exception as e:
            print(f"  {name}: Subscription failed - {e}")
    print()

    # ==========================================================================
    # PHASE 4: EPOCH EXECUTION (Yield Generation)
    # ==========================================================================
    print("PHASE 4: EPOCH EXECUTION (YIELD GENERATION)")
    print("-" * 50)

    # Simulate 3 epochs of collections
    for epoch in range(1, 4):
        # Simulate collections (5-8% of pool monthly)
        pool = platform.pool_manager.get_pool(pool_id)
        collection_rate = Decimal(str(random.uniform(0.05, 0.08)))
        collections = pool.metrics.total_face_value * collection_rate
        recoveries = pool.metrics.total_face_value * Decimal("0.01")  # 1% recoveries

        epoch_result = platform.run_epoch(
            pool_id=pool_id,
            collections=collections,
            recoveries=recoveries,
        )

        print(f"  Epoch {epoch_result['epoch']}:")
        print(f"    - Total Inflow: ${epoch_result['waterfall']['total_inflow']:,.2f}")
        print(f"    - DROP Interest: ${epoch_result['waterfall']['drop_interest']:,.2f}")
        print(f"    - TIN Interest: ${epoch_result['waterfall']['tin_interest']:,.2f}")
        print(f"    - NAV per DROP: ${epoch_result['nav']['drop_per_token']:.4f}")
        print(f"    - NAV per TIN: ${epoch_result['nav']['tin_per_token']:.4f}")
        print(f"    - Distributions: {epoch_result['distributions']}")
    print()

    # ==========================================================================
    # PHASE 5: INVESTOR PORTFOLIO SUMMARY
    # ==========================================================================
    print("PHASE 5: INVESTOR PORTFOLIO SUMMARY")
    print("-" * 50)

    for inv_id, name, _, _ in investors:
        summary = platform.investor_portal.get_portfolio_summary(inv_id)
        print(f"  {name} ({inv_id}):")
        print(f"    - Total Invested: ${summary['total_invested']:,.2f}")
        print(f"    - Current Value: ${summary['total_current_value']:,.2f}")
        print(f"    - Yield Earned: ${summary['total_yield_earned']:,.2f}")
        print(f"    - Return: {summary['total_return_pct']:.2f}%")
    print()

    # ==========================================================================
    # PHASE 6: LIQUIDITY METRICS
    # ==========================================================================
    print("PHASE 6: LIQUIDITY METRICS")
    print("-" * 50)

    # Place some orders
    platform.liquidity_engine.place_order(
        token_id=f"DROP-{pool_id}",
        side=OrderSide.BUY,
        price=Decimal("0.98"),
        quantity=Decimal("10000"),
        trader_id="TRADER-001",
    )

    platform.liquidity_engine.place_order(
        token_id=f"DROP-{pool_id}",
        side=OrderSide.SELL,
        price=Decimal("1.02"),
        quantity=Decimal("5000"),
        trader_id="TRADER-002",
    )

    liquidity = platform.liquidity_engine.calculate_liquidity_metrics(pool_id)
    print(f"  Instant Liquidity: ${float(liquidity.instant_liquidity):,.2f}")
    print(f"  Bid Depth: ${float(liquidity.bid_depth):,.2f}")
    print(f"  Ask Depth: ${float(liquidity.ask_depth):,.2f}")
    print(f"  DeFi Collateral Value: ${float(liquidity.collateral_value):,.2f}")
    print(f"  Max Borrow Capacity (70% LTV): ${float(liquidity.max_borrow_capacity):,.2f}")
    print()

    # ==========================================================================
    # PHASE 7: PLATFORM SUMMARY
    # ==========================================================================
    print("PHASE 7: PLATFORM SUMMARY")
    print("-" * 50)

    metrics = platform.get_platform_metrics()
    print(f"  Total Tokens Minted: {metrics['total_tokens_minted']}")
    print(f"  Total Face Value: ${metrics['total_face_value']:,.2f}")
    print(f"  Total Current Value: ${metrics['total_current_value']:,.2f}")
    print(f"  Active Pools: {metrics['active_pools']}")
    print(f"  Total Tranches: {metrics['total_tranches']}")
    print()
    print("  Blockchain Simulation:")
    print(f"    - Current Block: {metrics['blockchain']['current_block']}")
    print(f"    - Total Transactions: {metrics['blockchain']['total_transactions']}")
    print(f"    - Total Contracts: {metrics['blockchain']['total_contracts']}")
    print()

    print("=" * 80)
    print("DEMO COMPLETE - RWA TOKENIZATION PLATFORM OPERATIONAL")
    print("=" * 80)

    return platform


if __name__ == "__main__":
    platform = run_demo()
