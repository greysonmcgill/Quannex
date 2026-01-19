"""
Distressed Asset Marketplace - Securitization & Tokenization Layer

Because the AI standardizes the data of millions of messy debts,
we can SECURITIZE them into tradeable asset classes.

Key Innovation: Convert $40 BNPL default + $200 subscription default
into a STANDARDIZED digital asset with a specific risk profile.

These bundled assets can be sold to credit funds who want exposure
to micro-consumer credit but couldn't price it before.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any
import hashlib
import json
import random


class AssetClass(Enum):
    """Standardized asset classifications"""
    BNPL_PRIME = "bnpl_prime"           # BNPL, high shadow score
    BNPL_SUBPRIME = "bnpl_subprime"     # BNPL, low shadow score
    SUBSCRIPTION_TECH = "sub_tech"       # Tech subscriptions
    SUBSCRIPTION_MEDIA = "sub_media"     # Media/streaming
    GIG_ECONOMY = "gig_economy"          # Gig worker advances
    UTILITY_TELECOM = "utility_telecom"  # Utilities and telecom
    MIXED_MICRO = "mixed_micro"          # Mixed micro-debt pool
    RECOVERY_PREMIUM = "recovery_premium"  # High-probability recovery


class RiskRating(Enum):
    """Standardized risk ratings (S&P-style)"""
    AAA = "AAA"  # >85% expected recovery
    AA = "AA"    # 75-85% expected recovery
    A = "A"      # 65-75% expected recovery
    BBB = "BBB"  # 55-65% expected recovery
    BB = "BB"    # 45-55% expected recovery
    B = "B"      # 35-45% expected recovery
    CCC = "CCC"  # 25-35% expected recovery
    CC = "CC"    # 15-25% expected recovery
    C = "C"      # <15% expected recovery


class TrancheType(Enum):
    """Securitization tranche types"""
    SENIOR = "senior"           # First claim on cash flows
    MEZZANINE = "mezzanine"     # Middle priority
    JUNIOR = "junior"           # Last claim, highest yield
    EQUITY = "equity"           # Residual, highest risk/reward


@dataclass
class DebtAsset:
    """Individual debt standardized as an asset"""
    asset_id: str
    original_record_id: str

    # Standardized attributes
    face_value: float
    estimated_recovery_value: float
    recovery_probability: float
    days_since_charge_off: int

    # Classification
    asset_class: AssetClass
    risk_rating: RiskRating
    shadow_score: int

    # Metadata
    category: str
    creditor_type: str
    geo_region: str

    # Timestamps
    originated_at: datetime
    standardized_at: datetime = field(default_factory=datetime.now)


@dataclass
class AssetPool:
    """Collection of standardized debt assets for securitization"""
    pool_id: str
    pool_name: str
    asset_class: AssetClass

    # Pool composition
    assets: list[DebtAsset] = field(default_factory=list)
    total_face_value: float = 0.0
    total_estimated_recovery: float = 0.0

    # Risk metrics
    weighted_avg_recovery_prob: float = 0.0
    weighted_avg_shadow_score: float = 0.0
    pool_risk_rating: RiskRating = RiskRating.B

    # Diversification metrics
    unique_creditors: int = 0
    unique_categories: int = 0
    geographic_spread: int = 0

    # Status
    status: str = "open"  # open, closed, securitized
    created_at: datetime = field(default_factory=datetime.now)
    closed_at: datetime | None = None


@dataclass
class Tranche:
    """Securitization tranche"""
    tranche_id: str
    pool_id: str
    tranche_type: TrancheType

    # Economics
    face_value: float
    purchase_price: float
    expected_yield: float  # Annual %
    priority_order: int

    # Risk
    risk_rating: RiskRating
    subordination_level: float  # % of pool below this tranche

    # Status
    status: str = "available"  # available, sold, partially_sold
    sold_amount: float = 0.0
    buyer_id: str | None = None


@dataclass
class SecuritizedProduct:
    """
    Special Purpose Vehicle (SPV) for securitized micro-debt

    This is the tradeable instrument that credit funds purchase.
    """
    product_id: str
    product_name: str
    pool_id: str

    # Structure
    tranches: list[Tranche] = field(default_factory=list)
    total_face_value: float = 0.0
    total_issue_amount: float = 0.0

    # Legal structure
    spv_name: str = ""
    jurisdiction: str = "Delaware"
    servicer: str = "QUAN Recovery"

    # Performance
    monthly_collections: float = 0.0
    cumulative_collections: float = 0.0
    current_default_rate: float = 0.0

    # Timestamps
    issued_at: datetime = field(default_factory=datetime.now)
    maturity_date: datetime | None = None


@dataclass
class MarketOrder:
    """Order in the distressed asset marketplace"""
    order_id: str
    order_type: str  # buy, sell
    buyer_id: str | None
    seller_id: str | None

    # Asset details
    asset_type: str  # pool, tranche, individual
    asset_id: str
    quantity: float  # Face value amount

    # Pricing
    bid_price: float  # % of face value
    ask_price: float | None

    # Status
    status: str = "pending"  # pending, matched, executed, cancelled
    executed_price: float | None = None
    executed_at: datetime | None = None

    created_at: datetime = field(default_factory=datetime.now)


class DistressedAssetMarketplace:
    """
    The Marketplace for Securitized Micro-Debt

    Key Functions:
    1. STANDARDIZE: Convert messy debts to rated assets
    2. POOL: Bundle assets into diversified pools
    3. TRANCHE: Create risk/return layers for different investors
    4. TRADE: Enable secondary market for these assets
    """

    def __init__(self):
        self.assets: dict[str, DebtAsset] = {}
        self.pools: dict[str, AssetPool] = {}
        self.products: dict[str, SecuritizedProduct] = {}
        self.orders: dict[str, MarketOrder] = {}
        self.trades: list[dict[str, Any]] = []

        # Pricing models
        self._base_pricing = {
            RiskRating.AAA: 0.95,
            RiskRating.AA: 0.88,
            RiskRating.A: 0.80,
            RiskRating.BBB: 0.70,
            RiskRating.BB: 0.55,
            RiskRating.B: 0.40,
            RiskRating.CCC: 0.25,
            RiskRating.CC: 0.12,
            RiskRating.C: 0.05
        }

    def standardize_debt(
        self,
        record_id: str,
        face_value: float,
        recovery_probability: float,
        shadow_score: int,
        days_since_charge_off: int,
        category: str,
        creditor_type: str,
        geo_region: str
    ) -> DebtAsset:
        """
        Convert raw debt record into standardized asset

        This is the key transformation that enables securitization.
        """
        # Determine asset class
        asset_class = self._classify_asset(category, shadow_score, creditor_type)

        # Determine risk rating
        risk_rating = self._rate_asset(recovery_probability, shadow_score, days_since_charge_off)

        # Calculate estimated recovery value
        estimated_recovery = face_value * recovery_probability

        # Generate asset ID
        asset_id = hashlib.sha256(
            f"{record_id}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        asset = DebtAsset(
            asset_id=asset_id,
            original_record_id=record_id,
            face_value=face_value,
            estimated_recovery_value=estimated_recovery,
            recovery_probability=recovery_probability,
            days_since_charge_off=days_since_charge_off,
            asset_class=asset_class,
            risk_rating=risk_rating,
            shadow_score=shadow_score,
            category=category,
            creditor_type=creditor_type,
            geo_region=geo_region,
            originated_at=datetime.now() - timedelta(days=days_since_charge_off)
        )

        self.assets[asset_id] = asset
        return asset

    def create_pool(
        self,
        pool_name: str,
        target_asset_class: AssetClass,
        target_size: float = 1000000.0
    ) -> AssetPool:
        """Create a new asset pool for bundling debts"""
        pool_id = hashlib.sha256(
            f"{pool_name}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        pool = AssetPool(
            pool_id=pool_id,
            pool_name=pool_name,
            asset_class=target_asset_class
        )

        self.pools[pool_id] = pool
        return pool

    def add_to_pool(self, pool_id: str, asset_id: str) -> bool:
        """Add an asset to a pool"""
        pool = self.pools.get(pool_id)
        asset = self.assets.get(asset_id)

        if not pool or not asset:
            return False

        if pool.status != "open":
            return False

        pool.assets.append(asset)
        pool.total_face_value += asset.face_value
        pool.total_estimated_recovery += asset.estimated_recovery_value

        # Recalculate pool metrics
        self._recalculate_pool_metrics(pool)

        return True

    def close_pool(self, pool_id: str) -> AssetPool | None:
        """Close pool for further additions and prepare for securitization"""
        pool = self.pools.get(pool_id)
        if not pool or pool.status != "open":
            return None

        pool.status = "closed"
        pool.closed_at = datetime.now()

        # Final metrics calculation
        self._recalculate_pool_metrics(pool)

        return pool

    def securitize_pool(
        self,
        pool_id: str,
        product_name: str,
        tranche_structure: list[dict[str, Any]] | None = None
    ) -> SecuritizedProduct:
        """
        Create securitized product from pool

        This creates the SPV and tranche structure for sale to investors.
        """
        pool = self.pools.get(pool_id)
        if not pool or pool.status != "closed":
            raise ValueError("Pool must be closed before securitization")

        product_id = hashlib.sha256(
            f"{product_name}{pool_id}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        # Default tranche structure if not provided
        if not tranche_structure:
            tranche_structure = [
                {"type": TrancheType.SENIOR, "pct": 0.60},
                {"type": TrancheType.MEZZANINE, "pct": 0.25},
                {"type": TrancheType.JUNIOR, "pct": 0.10},
                {"type": TrancheType.EQUITY, "pct": 0.05}
            ]

        # Create tranches
        tranches = []
        subordination = 0.0

        for i, t in enumerate(reversed(tranche_structure)):
            tranche_face = pool.total_estimated_recovery * t["pct"]

            # Price based on subordination and pool risk
            base_price = self._base_pricing[pool.pool_risk_rating]
            subordination_adj = 1 + (subordination * 0.3)  # Higher sub = higher price
            tranche_price = min(0.98, base_price * subordination_adj)

            # Yield inversely related to subordination
            base_yield = 0.25 - (subordination * 0.15)  # 25% for equity, ~10% for senior

            tranche_id = f"{product_id}-{t['type'].value}"

            tranche = Tranche(
                tranche_id=tranche_id,
                pool_id=pool_id,
                tranche_type=t["type"],
                face_value=tranche_face,
                purchase_price=tranche_face * tranche_price,
                expected_yield=base_yield,
                priority_order=len(tranche_structure) - i,
                risk_rating=self._tranche_rating(pool.pool_risk_rating, t["type"]),
                subordination_level=subordination
            )

            tranches.append(tranche)
            subordination += t["pct"]

        # Reverse to correct priority order
        tranches.reverse()

        product = SecuritizedProduct(
            product_id=product_id,
            product_name=product_name,
            pool_id=pool_id,
            tranches=tranches,
            total_face_value=pool.total_estimated_recovery,
            total_issue_amount=sum(t.purchase_price for t in tranches),
            spv_name=f"QUAN {product_name} SPV LLC",
            maturity_date=datetime.now() + timedelta(days=365)
        )

        self.products[product_id] = product
        pool.status = "securitized"

        return product

    def place_order(
        self,
        buyer_id: str,
        asset_type: str,
        asset_id: str,
        quantity: float,
        bid_price: float
    ) -> MarketOrder:
        """Place buy order in the marketplace"""
        order_id = hashlib.sha256(
            f"{buyer_id}{asset_id}{datetime.now().isoformat()}{random.random()}".encode()
        ).hexdigest()[:12]

        order = MarketOrder(
            order_id=order_id,
            order_type="buy",
            buyer_id=buyer_id,
            seller_id=None,
            asset_type=asset_type,
            asset_id=asset_id,
            quantity=quantity,
            bid_price=bid_price,
            ask_price=None
        )

        self.orders[order_id] = order

        # Attempt to match immediately
        self._match_order(order)

        return order

    def execute_trade(
        self,
        order_id: str,
        executed_price: float
    ) -> dict[str, Any]:
        """Execute a matched trade"""
        order = self.orders.get(order_id)
        if not order or order.status != "matched":
            return {"success": False, "reason": "Order not matched"}

        order.status = "executed"
        order.executed_price = executed_price
        order.executed_at = datetime.now()

        trade = {
            "trade_id": hashlib.sha256(f"{order_id}{datetime.now()}".encode()).hexdigest()[:12],
            "order_id": order_id,
            "buyer_id": order.buyer_id,
            "asset_type": order.asset_type,
            "asset_id": order.asset_id,
            "quantity": order.quantity,
            "price": executed_price,
            "total_value": order.quantity * executed_price,
            "executed_at": datetime.now().isoformat()
        }

        self.trades.append(trade)

        return {"success": True, "trade": trade}

    def get_market_summary(self) -> dict[str, Any]:
        """Get marketplace summary statistics"""
        total_assets = len(self.assets)
        total_pools = len(self.pools)
        total_products = len(self.products)

        # Calculate volumes
        total_face_value = sum(a.face_value for a in self.assets.values())
        total_recovery_value = sum(a.estimated_recovery_value for a in self.assets.values())

        # Pool breakdown
        pools_by_class: dict[str, int] = {}
        for pool in self.pools.values():
            cls = pool.asset_class.value
            pools_by_class[cls] = pools_by_class.get(cls, 0) + 1

        # Rating distribution
        rating_dist: dict[str, int] = {}
        for asset in self.assets.values():
            r = asset.risk_rating.value
            rating_dist[r] = rating_dist.get(r, 0) + 1

        return {
            "summary_date": datetime.now().isoformat(),
            "total_standardized_assets": total_assets,
            "total_face_value": total_face_value,
            "total_estimated_recovery": total_recovery_value,
            "implied_recovery_rate": total_recovery_value / total_face_value if total_face_value > 0 else 0,
            "active_pools": sum(1 for p in self.pools.values() if p.status == "open"),
            "closed_pools": sum(1 for p in self.pools.values() if p.status == "closed"),
            "securitized_products": total_products,
            "pools_by_asset_class": pools_by_class,
            "assets_by_rating": rating_dist,
            "total_trades_executed": len(self.trades),
            "total_trade_volume": sum(t["total_value"] for t in self.trades)
        }

    def get_investor_opportunities(self) -> list[dict[str, Any]]:
        """Get available investment opportunities"""
        opportunities = []

        for product in self.products.values():
            for tranche in product.tranches:
                if tranche.status in ["available", "partially_sold"]:
                    available = tranche.face_value - tranche.sold_amount

                    opportunities.append({
                        "product_id": product.product_id,
                        "product_name": product.product_name,
                        "tranche_id": tranche.tranche_id,
                        "tranche_type": tranche.tranche_type.value,
                        "risk_rating": tranche.risk_rating.value,
                        "face_value_available": available,
                        "purchase_price": tranche.purchase_price * (available / tranche.face_value),
                        "expected_yield": tranche.expected_yield,
                        "subordination": tranche.subordination_level,
                        "priority_order": tranche.priority_order,
                        "maturity": product.maturity_date.isoformat() if product.maturity_date else None
                    })

        # Sort by yield (highest first)
        opportunities.sort(key=lambda x: x["expected_yield"], reverse=True)

        return opportunities

    def _classify_asset(
        self,
        category: str,
        shadow_score: int,
        creditor_type: str
    ) -> AssetClass:
        """Classify asset into standardized class"""
        if "bnpl" in category.lower():
            return AssetClass.BNPL_PRIME if shadow_score >= 600 else AssetClass.BNPL_SUBPRIME
        elif "subscription" in category.lower():
            return AssetClass.SUBSCRIPTION_TECH if "tech" in creditor_type.lower() else AssetClass.SUBSCRIPTION_MEDIA
        elif "gig" in category.lower() or "advance" in category.lower():
            return AssetClass.GIG_ECONOMY
        elif "utility" in category.lower() or "telecom" in category.lower():
            return AssetClass.UTILITY_TELECOM
        else:
            return AssetClass.MIXED_MICRO

    def _rate_asset(
        self,
        recovery_prob: float,
        shadow_score: int,
        days_dpd: int
    ) -> RiskRating:
        """Assign risk rating based on characteristics"""
        # Composite score
        score = (
            recovery_prob * 40 +
            (shadow_score / 850) * 40 +
            max(0, (180 - days_dpd) / 180) * 20
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

    def _tranche_rating(
        self,
        pool_rating: RiskRating,
        tranche_type: TrancheType
    ) -> RiskRating:
        """Determine tranche rating based on pool rating and seniority"""
        ratings = list(RiskRating)
        pool_idx = ratings.index(pool_rating)

        adjustments = {
            TrancheType.SENIOR: -2,     # 2 notches better
            TrancheType.MEZZANINE: 0,   # Same as pool
            TrancheType.JUNIOR: 2,      # 2 notches worse
            TrancheType.EQUITY: 4       # 4 notches worse
        }

        new_idx = pool_idx + adjustments[tranche_type]
        new_idx = max(0, min(len(ratings) - 1, new_idx))

        return ratings[new_idx]

    def _recalculate_pool_metrics(self, pool: AssetPool) -> None:
        """Recalculate pool-level metrics"""
        if not pool.assets:
            return

        # Weighted averages
        total_value = sum(a.face_value for a in pool.assets)
        pool.weighted_avg_recovery_prob = sum(
            a.recovery_probability * a.face_value for a in pool.assets
        ) / total_value
        pool.weighted_avg_shadow_score = sum(
            a.shadow_score * a.face_value for a in pool.assets
        ) / total_value

        # Diversification
        pool.unique_creditors = len(set(a.creditor_type for a in pool.assets))
        pool.unique_categories = len(set(a.category for a in pool.assets))
        pool.geographic_spread = len(set(a.geo_region for a in pool.assets))

        # Pool rating
        pool.pool_risk_rating = self._rate_asset(
            pool.weighted_avg_recovery_prob,
            int(pool.weighted_avg_shadow_score),
            int(sum(a.days_since_charge_off for a in pool.assets) / len(pool.assets))
        )

    def _match_order(self, order: MarketOrder) -> None:
        """Attempt to match an order with available inventory"""
        # In production, this would match against order book
        # For now, auto-match if inventory available

        if order.asset_type == "tranche":
            for product in self.products.values():
                for tranche in product.tranches:
                    if tranche.tranche_id == order.asset_id:
                        available = tranche.face_value - tranche.sold_amount
                        if available >= order.quantity:
                            order.status = "matched"
                            order.ask_price = tranche.purchase_price / tranche.face_value
                            return


# Demonstration
if __name__ == "__main__":
    marketplace = DistressedAssetMarketplace()

    print("=== DISTRESSED ASSET MARKETPLACE DEMO ===\n")

    # Standardize some debts
    print("Standardizing Debts...")
    assets = []
    for i in range(50):
        asset = marketplace.standardize_debt(
            record_id=f"DEBT{i:04d}",
            face_value=random.uniform(25, 500),
            recovery_probability=random.uniform(0.3, 0.7),
            shadow_score=random.randint(400, 750),
            days_since_charge_off=random.randint(30, 180),
            category=random.choice(["bnpl", "subscription", "gig_advance", "utility"]),
            creditor_type=random.choice(["tech", "retail", "finance"]),
            geo_region=random.choice(["CA", "TX", "NY", "FL"])
        )
        assets.append(asset)

    print(f"  Standardized {len(assets)} debt assets")

    # Create and fill pool
    print("\nCreating Asset Pool...")
    pool = marketplace.create_pool("BNPL Q1 2026", AssetClass.BNPL_SUBPRIME, 500000)
    for asset in assets:
        marketplace.add_to_pool(pool.pool_id, asset.asset_id)

    print(f"  Pool: {pool.pool_name}")
    print(f"  Total Face Value: ${pool.total_face_value:,.2f}")
    print(f"  Estimated Recovery: ${pool.total_estimated_recovery:,.2f}")

    # Close and securitize
    print("\nSecuritizing Pool...")
    marketplace.close_pool(pool.pool_id)
    product = marketplace.securitize_pool(pool.pool_id, "QUAN BNPL 2026-1")

    print(f"  Product: {product.product_name}")
    print(f"  SPV: {product.spv_name}")
    print(f"  Total Issue: ${product.total_issue_amount:,.2f}")
    print("\n  Tranches:")
    for t in product.tranches:
        print(f"    {t.tranche_type.value.upper()}: ${t.face_value:,.2f} @ {t.expected_yield:.1%} yield ({t.risk_rating.value})")

    # Show investment opportunities
    print("\nAvailable Investment Opportunities:")
    opps = marketplace.get_investor_opportunities()
    for opp in opps[:3]:
        print(f"  {opp['tranche_type'].upper()} - {opp['risk_rating']}")
        print(f"    Available: ${opp['face_value_available']:,.2f}")
        print(f"    Yield: {opp['expected_yield']:.1%}")

    # Market summary
    print("\nMarketplace Summary:")
    summary = marketplace.get_market_summary()
    print(f"  Total Assets: {summary['total_standardized_assets']}")
    print(f"  Total Face Value: ${summary['total_face_value']:,.2f}")
    print(f"  Implied Recovery: {summary['implied_recovery_rate']:.1%}")
    print(f"  Products Issued: {summary['securitized_products']}")
