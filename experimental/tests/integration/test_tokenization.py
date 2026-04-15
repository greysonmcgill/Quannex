"""
QUAN Integration Tests: Tokenization

Testing for asset tokenization and securitization:
1. Asset standardization
2. Pool creation and tranching
3. Waterfall distribution
4. NAV calculation

Tests verify the financial engineering components for debt securitization.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Any, Optional
import uuid
from dataclasses import dataclass, field
from enum import Enum



# =============================================================================
# TOKENIZATION IMPLEMENTATION FOR TESTING
# =============================================================================

class TrancheRating(Enum):
    """Tranche risk ratings"""
    AAA = "AAA"
    AA = "AA"
    A = "A"
    BBB = "BBB"
    BB = "BB"
    EQUITY = "EQUITY"


class AssetStatus(Enum):
    """Asset status"""
    ACTIVE = "active"
    PERFORMING = "performing"
    DELINQUENT = "delinquent"
    DEFAULTED = "defaulted"
    RESOLVED = "resolved"


@dataclass
class StandardizedAsset:
    """Standardized debt asset for tokenization"""
    asset_id: str
    original_balance: Decimal
    current_balance: Decimal
    days_past_due: int
    creditor_type: str
    debtor_state: str
    charge_off_date: datetime
    expected_recovery_rate: float
    shadow_score: Optional[int] = None
    status: AssetStatus = AssetStatus.ACTIVE
    payments_received: Decimal = Decimal("0")
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Tranche:
    """Investment tranche in a debt pool"""
    tranche_id: str
    rating: TrancheRating
    principal: Decimal
    coupon_rate: float
    subordination_level: float  # Percentage of losses absorbed before this tranche
    payments_received: Decimal = Decimal("0")
    losses_absorbed: Decimal = Decimal("0")
    status: str = "active"


@dataclass
class DebtPool:
    """Pool of tokenized debt assets"""
    pool_id: str
    assets: List[StandardizedAsset]
    tranches: List[Tranche]
    total_principal: Decimal
    weighted_avg_recovery: float
    created_at: datetime = field(default_factory=datetime.utcnow)
    total_collections: Decimal = Decimal("0")
    total_losses: Decimal = Decimal("0")


class TokenizationEngine:
    """Engine for debt tokenization and securitization"""

    # Standard tranche structure
    DEFAULT_TRANCHES = [
        {"rating": TrancheRating.AAA, "pct": 0.50, "coupon": 0.05, "subordination": 0.50},
        {"rating": TrancheRating.AA, "pct": 0.20, "coupon": 0.07, "subordination": 0.30},
        {"rating": TrancheRating.A, "pct": 0.15, "coupon": 0.10, "subordination": 0.15},
        {"rating": TrancheRating.EQUITY, "pct": 0.15, "coupon": 0.20, "subordination": 0.00},
    ]

    def __init__(self):
        self.pools: Dict[str, DebtPool] = {}
        self.assets: Dict[str, StandardizedAsset] = {}

    def standardize_asset(self, account: Dict) -> StandardizedAsset:
        """Standardize an account into a tokenizable asset"""
        asset_id = f"AST_{uuid.uuid4().hex[:12]}"

        # Calculate expected recovery based on characteristics
        base_recovery = 0.30
        dpd = account.get("days_overdue", 60)

        # Adjust for DPD
        if dpd < 30:
            recovery_adj = 0.15
        elif dpd < 90:
            recovery_adj = 0.05
        elif dpd < 180:
            recovery_adj = -0.05
        else:
            recovery_adj = -0.15

        # Adjust for creditor type
        type_adjustments = {
            "bnpl": 0.05,
            "medical": 0.03,
            "subscription": 0.08,
            "telecom": 0.00,
            "utility": -0.02
        }
        type_adj = type_adjustments.get(account.get("creditor_type", ""), 0)

        expected_recovery = max(0.10, min(0.60, base_recovery + recovery_adj + type_adj))

        charge_off = account.get("charge_off_date")
        if isinstance(charge_off, str):
            charge_off = datetime.fromisoformat(charge_off.replace("Z", "+00:00"))
        elif charge_off is None:
            charge_off = datetime.utcnow() - timedelta(days=dpd)

        asset = StandardizedAsset(
            asset_id=asset_id,
            original_balance=Decimal(str(account.get("balance", 0))),
            current_balance=Decimal(str(account.get("balance", 0))),
            days_past_due=dpd,
            creditor_type=account.get("creditor_type", "unknown"),
            debtor_state=account.get("debtor_state", "NY"),
            charge_off_date=charge_off,
            expected_recovery_rate=expected_recovery,
            shadow_score=account.get("shadow_score")
        )

        self.assets[asset_id] = asset
        return asset

    def create_pool(
        self,
        assets: List[StandardizedAsset],
        tranche_structure: List[Dict] = None
    ) -> DebtPool:
        """Create a tokenized pool from standardized assets"""
        pool_id = f"POOL_{uuid.uuid4().hex[:10]}"

        if tranche_structure is None:
            tranche_structure = self.DEFAULT_TRANCHES

        # Calculate pool metrics
        total_principal = sum(a.current_balance for a in assets)
        weighted_recovery = sum(
            a.expected_recovery_rate * float(a.current_balance)
            for a in assets
        ) / float(total_principal) if total_principal > 0 else 0

        # Create tranches
        tranches = []
        for ts in tranche_structure:
            tranche_principal = total_principal * Decimal(str(ts["pct"]))
            tranche = Tranche(
                tranche_id=f"TR_{pool_id}_{ts['rating'].value}",
                rating=ts["rating"],
                principal=tranche_principal,
                coupon_rate=ts["coupon"],
                subordination_level=ts["subordination"]
            )
            tranches.append(tranche)

        pool = DebtPool(
            pool_id=pool_id,
            assets=assets,
            tranches=tranches,
            total_principal=total_principal,
            weighted_avg_recovery=weighted_recovery
        )

        self.pools[pool_id] = pool
        return pool

    def process_collection(self, pool_id: str, amount: Decimal) -> Dict:
        """Process a collection and distribute via waterfall"""
        pool = self.pools.get(pool_id)
        if not pool:
            return {"success": False, "error": "Pool not found"}

        pool.total_collections += amount
        remaining = amount
        distributions = []

        # Waterfall distribution - senior tranches first
        sorted_tranches = sorted(
            pool.tranches,
            key=lambda t: t.subordination_level,
            reverse=True
        )

        for tranche in sorted_tranches:
            if remaining <= 0:
                break

            # Calculate what this tranche is owed (coupon + principal)
            owed = tranche.principal * Decimal(str(tranche.coupon_rate))

            # Pay minimum of remaining and owed
            payment = min(remaining, owed)
            tranche.payments_received += payment
            remaining -= payment

            distributions.append({
                "tranche_id": tranche.tranche_id,
                "rating": tranche.rating.value,
                "amount": float(payment)
            })

        return {
            "success": True,
            "pool_id": pool_id,
            "collection_amount": float(amount),
            "distributions": distributions,
            "remaining": float(remaining)
        }

    def process_loss(self, pool_id: str, amount: Decimal) -> Dict:
        """Process a loss through the waterfall (equity absorbs first)"""
        pool = self.pools.get(pool_id)
        if not pool:
            return {"success": False, "error": "Pool not found"}

        pool.total_losses += amount
        remaining_loss = amount
        absorptions = []

        # Loss allocation - equity/junior tranches absorb first
        sorted_tranches = sorted(
            pool.tranches,
            key=lambda t: t.subordination_level
        )

        for tranche in sorted_tranches:
            if remaining_loss <= 0:
                break

            # Available to absorb is remaining principal
            available = tranche.principal - tranche.losses_absorbed

            # Absorb minimum of remaining loss and available
            absorption = min(remaining_loss, available)
            tranche.losses_absorbed += absorption
            remaining_loss -= absorption

            if absorption > 0:
                absorptions.append({
                    "tranche_id": tranche.tranche_id,
                    "rating": tranche.rating.value,
                    "loss_absorbed": float(absorption)
                })

            # Check if tranche is wiped out
            if tranche.losses_absorbed >= tranche.principal:
                tranche.status = "defaulted"

        return {
            "success": True,
            "pool_id": pool_id,
            "loss_amount": float(amount),
            "absorptions": absorptions,
            "unallocated_loss": float(remaining_loss)
        }

    def calculate_nav(self, pool_id: str) -> Dict:
        """Calculate Net Asset Value for pool and tranches"""
        pool = self.pools.get(pool_id)
        if not pool:
            return {"success": False, "error": "Pool not found"}

        # Pool-level NAV
        expected_collections = sum(
            float(a.current_balance) * a.expected_recovery_rate
            for a in pool.assets
        )

        pool_nav = Decimal(str(expected_collections)) - pool.total_losses

        # Tranche-level NAV
        tranche_navs = []
        remaining_nav = pool_nav

        # Allocate NAV through waterfall (senior first)
        sorted_tranches = sorted(
            pool.tranches,
            key=lambda t: t.subordination_level,
            reverse=True
        )

        for tranche in sorted_tranches:
            # Tranche NAV is minimum of remaining and principal minus losses
            tranche_available = tranche.principal - tranche.losses_absorbed
            tranche_nav = min(remaining_nav, tranche_available)
            remaining_nav -= tranche_nav

            nav_percent = float(tranche_nav / tranche.principal) if tranche.principal > 0 else 0

            tranche_navs.append({
                "tranche_id": tranche.tranche_id,
                "rating": tranche.rating.value,
                "principal": float(tranche.principal),
                "nav": float(max(Decimal("0"), tranche_nav)),
                "nav_percent": nav_percent * 100,
                "losses_absorbed": float(tranche.losses_absorbed)
            })

        return {
            "success": True,
            "pool_id": pool_id,
            "pool_nav": float(pool_nav),
            "total_principal": float(pool.total_principal),
            "total_collections": float(pool.total_collections),
            "total_losses": float(pool.total_losses),
            "expected_collections": expected_collections,
            "tranches": tranche_navs
        }

    def get_pool_metrics(self, pool_id: str) -> Dict:
        """Get comprehensive pool metrics"""
        pool = self.pools.get(pool_id)
        if not pool:
            return {"success": False, "error": "Pool not found"}

        # Asset-level metrics
        performing = sum(1 for a in pool.assets if a.status == AssetStatus.PERFORMING)
        defaulted = sum(1 for a in pool.assets if a.status == AssetStatus.DEFAULTED)
        resolved = sum(1 for a in pool.assets if a.status == AssetStatus.RESOLVED)

        # Balance metrics
        current_balance = sum(a.current_balance for a in pool.assets)
        collections_to_date = pool.total_collections

        # Recovery rate
        actual_recovery = float(collections_to_date / pool.total_principal) if pool.total_principal > 0 else 0

        return {
            "pool_id": pool_id,
            "asset_count": len(pool.assets),
            "performing": performing,
            "defaulted": defaulted,
            "resolved": resolved,
            "total_principal": float(pool.total_principal),
            "current_balance": float(current_balance),
            "collections_to_date": float(collections_to_date),
            "losses_to_date": float(pool.total_losses),
            "weighted_avg_recovery": pool.weighted_avg_recovery,
            "actual_recovery_rate": actual_recovery,
            "created_at": pool.created_at.isoformat()
        }


# =============================================================================
# TEST CLASSES
# =============================================================================

class TestAssetStandardization:
    """Test asset standardization"""

    @pytest.fixture
    def engine(self):
        return TokenizationEngine()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_basic_standardization(self, engine, data_generator):
        """Test basic asset standardization"""
        account = data_generator.generate_account(
            balance=Decimal("185.00"),
            days_past_due=45
        )

        asset = engine.standardize_asset(account)

        assert asset is not None
        assert asset.asset_id.startswith("AST_")
        assert asset.original_balance == Decimal("185.00")
        assert asset.days_past_due == 45
        assert 0.10 <= asset.expected_recovery_rate <= 0.60

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_recovery_rate_by_dpd(self, engine, data_generator):
        """Test recovery rate varies by days past due"""
        dpd_values = [15, 45, 120, 200]
        recovery_rates = []

        for dpd in dpd_values:
            account = data_generator.generate_account(days_past_due=dpd)
            asset = engine.standardize_asset(account)
            recovery_rates.append(asset.expected_recovery_rate)

        # Recovery should generally decrease with DPD
        assert recovery_rates[0] >= recovery_rates[-1]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_recovery_rate_by_creditor_type(self, engine, data_generator):
        """Test recovery rate varies by creditor type"""
        types = ["bnpl", "subscription", "medical", "utility"]
        recovery_by_type = {}

        for ctype in types:
            account = data_generator.generate_account(
                days_past_due=60,
                creditor_type=ctype
            )
            asset = engine.standardize_asset(account)
            recovery_by_type[ctype] = asset.expected_recovery_rate

        # Different types should have different rates
        assert len(set(recovery_by_type.values())) > 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_bulk_standardization(self, engine, data_generator):
        """Test bulk asset standardization"""
        portfolio = data_generator.generate_portfolio(100)

        assets = [engine.standardize_asset(acc) for acc in portfolio]

        assert len(assets) == 100
        assert all(a.asset_id in engine.assets for a in assets)


class TestPoolCreationAndTranching:
    """Test pool creation and tranching"""

    @pytest.fixture
    def engine(self):
        return TokenizationEngine()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_basic_pool_creation(self, engine, data_generator):
        """Test basic pool creation"""
        portfolio = data_generator.generate_portfolio(50)
        assets = [engine.standardize_asset(acc) for acc in portfolio]

        pool = engine.create_pool(assets)

        assert pool is not None
        assert pool.pool_id.startswith("POOL_")
        assert len(pool.assets) == 50
        assert len(pool.tranches) == 4  # Default structure

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_tranche_structure(self, engine, data_generator):
        """Test tranche structure is correct"""
        portfolio = data_generator.generate_portfolio(20)
        assets = [engine.standardize_asset(acc) for acc in portfolio]

        pool = engine.create_pool(assets)

        # Verify tranche percentages sum to 100%
        total_tranche_pct = sum(
            float(t.principal / pool.total_principal)
            for t in pool.tranches
        )
        assert abs(total_tranche_pct - 1.0) < 0.01

        # Verify ratings present
        ratings = [t.rating for t in pool.tranches]
        assert TrancheRating.AAA in ratings
        assert TrancheRating.EQUITY in ratings

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_custom_tranche_structure(self, engine, data_generator):
        """Test custom tranche structure"""
        portfolio = data_generator.generate_portfolio(30)
        assets = [engine.standardize_asset(acc) for acc in portfolio]

        custom_tranches = [
            {"rating": TrancheRating.AAA, "pct": 0.60, "coupon": 0.04, "subordination": 0.40},
            {"rating": TrancheRating.BBB, "pct": 0.25, "coupon": 0.08, "subordination": 0.15},
            {"rating": TrancheRating.EQUITY, "pct": 0.15, "coupon": 0.25, "subordination": 0.00},
        ]

        pool = engine.create_pool(assets, custom_tranches)

        assert len(pool.tranches) == 3
        assert any(t.rating == TrancheRating.BBB for t in pool.tranches)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_weighted_average_recovery(self, engine, data_generator):
        """Test weighted average recovery calculation"""
        portfolio = data_generator.generate_portfolio(25)
        assets = [engine.standardize_asset(acc) for acc in portfolio]

        pool = engine.create_pool(assets)

        # WAR should be between min and max individual rates
        individual_rates = [a.expected_recovery_rate for a in assets]
        assert min(individual_rates) <= pool.weighted_avg_recovery <= max(individual_rates)


class TestWaterfallDistribution:
    """Test waterfall distribution mechanics"""

    @pytest.fixture
    def engine(self):
        return TokenizationEngine()

    @pytest.fixture
    def test_pool(self, engine, data_generator):
        portfolio = data_generator.generate_portfolio(20)
        assets = [engine.standardize_asset(acc) for acc in portfolio]
        return engine.create_pool(assets)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_collection_waterfall(self, engine, test_pool):
        """Test collection flows through waterfall correctly"""
        pool_id = test_pool.pool_id

        # Process a collection
        result = engine.process_collection(pool_id, Decimal("1000.00"))

        assert result["success"]
        assert result["collection_amount"] == 1000.00
        assert len(result["distributions"]) > 0

        # Senior tranche should receive first
        first_dist = result["distributions"][0]
        assert first_dist["rating"] == "AAA"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_loss_waterfall(self, engine, test_pool):
        """Test losses flow through waterfall correctly"""
        pool_id = test_pool.pool_id

        # Process a loss
        result = engine.process_loss(pool_id, Decimal("500.00"))

        assert result["success"]
        assert result["loss_amount"] == 500.00
        assert len(result["absorptions"]) > 0

        # Equity tranche should absorb first
        first_absorption = result["absorptions"][0]
        assert first_absorption["rating"] == "EQUITY"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_subordination_protection(self, engine, test_pool):
        """Test senior tranches are protected by subordination"""
        pool_id = test_pool.pool_id

        # Get equity tranche principal
        equity_tranche = next(t for t in test_pool.tranches if t.rating == TrancheRating.EQUITY)
        equity_principal = float(equity_tranche.principal)

        # Process loss less than equity
        engine.process_loss(pool_id, Decimal(str(equity_principal * 0.5)))

        # AAA should have no losses
        aaa_tranche = next(t for t in test_pool.tranches if t.rating == TrancheRating.AAA)
        assert aaa_tranche.losses_absorbed == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_loss_exceeds_subordination(self, engine, test_pool):
        """Test losses cascade when exceeding subordination"""
        pool_id = test_pool.pool_id

        # Process large loss
        total_principal = float(test_pool.total_principal)
        large_loss = Decimal(str(total_principal * 0.20))  # 20% loss

        result = engine.process_loss(pool_id, large_loss)

        # Multiple tranches should absorb
        assert len(result["absorptions"]) >= 2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multiple_collections(self, engine, test_pool):
        """Test multiple collections accumulate correctly"""
        pool_id = test_pool.pool_id

        # Process multiple collections
        for _ in range(5):
            engine.process_collection(pool_id, Decimal("200.00"))

        pool = engine.pools[pool_id]
        assert pool.total_collections == Decimal("1000.00")


class TestNAVCalculation:
    """Test NAV calculation"""

    @pytest.fixture
    def engine(self):
        return TokenizationEngine()

    @pytest.fixture
    def test_pool(self, engine, data_generator):
        portfolio = data_generator.generate_portfolio(30)
        assets = [engine.standardize_asset(acc) for acc in portfolio]
        return engine.create_pool(assets)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_initial_nav(self, engine, test_pool):
        """Test initial NAV calculation"""
        nav_result = engine.calculate_nav(test_pool.pool_id)

        assert nav_result["success"]
        assert nav_result["pool_nav"] > 0
        assert nav_result["total_principal"] > 0
        assert len(nav_result["tranches"]) == 4

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_nav_after_collections(self, engine, test_pool):
        """Test NAV updates after collections"""
        pool_id = test_pool.pool_id

        initial_nav = engine.calculate_nav(pool_id)

        # Process collections
        engine.process_collection(pool_id, Decimal("500.00"))

        updated_nav = engine.calculate_nav(pool_id)

        # Collections should increase total tracked
        assert updated_nav["total_collections"] > initial_nav["total_collections"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_nav_after_losses(self, engine, test_pool):
        """Test NAV decreases after losses"""
        pool_id = test_pool.pool_id

        initial_nav = engine.calculate_nav(pool_id)

        # Process losses
        engine.process_loss(pool_id, Decimal("1000.00"))

        updated_nav = engine.calculate_nav(pool_id)

        assert updated_nav["pool_nav"] < initial_nav["pool_nav"]
        assert updated_nav["total_losses"] == 1000.00

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_tranche_nav_ordering(self, engine, test_pool):
        """Test senior tranches have higher NAV percentages"""
        nav_result = engine.calculate_nav(test_pool.pool_id)

        tranches = nav_result["tranches"]

        # Find AAA and equity NAV percentages
        aaa_nav_pct = next(t["nav_percent"] for t in tranches if t["rating"] == "AAA")
        equity_nav_pct = next(t["nav_percent"] for t in tranches if t["rating"] == "EQUITY")

        # AAA should have higher NAV percentage (more protected)
        assert aaa_nav_pct >= equity_nav_pct

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_pool_metrics(self, engine, test_pool):
        """Test pool metrics calculation"""
        pool_id = test_pool.pool_id

        # Process some activity
        engine.process_collection(pool_id, Decimal("500.00"))
        engine.process_loss(pool_id, Decimal("100.00"))

        metrics = engine.get_pool_metrics(pool_id)

        assert metrics["asset_count"] == 30
        assert metrics["collections_to_date"] == 500.00
        assert metrics["losses_to_date"] == 100.00
        assert "actual_recovery_rate" in metrics


class TestTokenizationIntegration:
    """Test full tokenization integration"""

    @pytest.fixture
    def engine(self):
        return TokenizationEngine()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_tokenization_lifecycle(self, engine, data_generator, audit_logger):
        """Test complete tokenization lifecycle"""
        # 1. Generate and standardize assets
        portfolio = data_generator.generate_portfolio(50)
        assets = [engine.standardize_asset(acc) for acc in portfolio]
        audit_logger.log("tokenization", "POOL", "assets_standardized", {"count": len(assets)})

        # 2. Create pool
        pool = engine.create_pool(assets)
        audit_logger.log("tokenization", pool.pool_id, "pool_created", {
            "total_principal": float(pool.total_principal)
        })

        # 3. Simulate collections over time
        total_collected = Decimal("0")
        for i in range(10):
            collection = Decimal(str(float(pool.total_principal) * 0.03))  # 3% per period
            engine.process_collection(pool.pool_id, collection)
            total_collected += collection

        # 4. Simulate some losses
        loss = Decimal(str(float(pool.total_principal) * 0.05))  # 5% loss
        engine.process_loss(pool.pool_id, loss)

        # 5. Calculate final NAV
        nav = engine.calculate_nav(pool.pool_id)
        audit_logger.log("tokenization", pool.pool_id, "nav_calculated", {
            "pool_nav": nav["pool_nav"]
        })

        # 6. Get metrics
        metrics = engine.get_pool_metrics(pool.pool_id)

        # Verify results
        assert metrics["collections_to_date"] == float(total_collected)
        assert metrics["losses_to_date"] == float(loss)
        assert nav["pool_nav"] > 0

        # Verify audit trail
        entries = audit_logger.get_entries(event_type="tokenization")
        assert len(entries) >= 3

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_large_pool_performance(self, engine, data_generator, perf_tracker):
        """Test tokenization performance with large pool"""
        perf_tracker.start_timer("large_pool")

        # Create large portfolio
        portfolio = data_generator.generate_portfolio(1000)
        assets = [engine.standardize_asset(acc) for acc in portfolio]

        # Create pool
        pool = engine.create_pool(assets)

        # Process many transactions
        for _ in range(100):
            engine.process_collection(pool.pool_id, Decimal("1000.00"))

        # Calculate NAV
        nav = engine.calculate_nav(pool.pool_id)

        elapsed = perf_tracker.stop_timer("large_pool")

        assert len(pool.assets) == 1000
        assert nav["success"]
        assert elapsed < 10.0  # Should complete in under 10 seconds
