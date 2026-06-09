# tests/unit/test_tokenization.py
"""
RWA Tokenization Platform test harness.

Exercises the Centrifuge/Tinlake-style tokenization stack:
NFT minting, pool lifecycle, DROP/TIN tranche structure, waterfall
distribution, epoch execution, and the investor portal.

All tests are deterministic: debt amounts and risk inputs are fixed,
date fields use fixed offsets from "now" (only whole-day deltas matter),
and assertions on cash flows use exact Decimal arithmetic or
conservation invariants rather than wall-clock-sensitive values.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from quan.finance.tokenization import (
    AssetClass,
    AssetTokenizer,
    DebtMetadata,
    PoolStatus,
    RWATokenizationPlatform,
    TrancheType,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_debt_metadata(
    idx: int = 0,
    face_value: Decimal = Decimal("60000"),
    recovery_probability: float = 0.65,
    shadow_bureau_score: int = 650,
    debt_category: str = "BNPL - Klarna",
    creditor: str = "Klarna",
) -> DebtMetadata:
    """Factory for deterministic BNPL debt metadata."""
    now = datetime.now()
    return DebtMetadata(
        original_creditor=creditor,
        debt_category=debt_category,
        origination_date=now - timedelta(days=120),
        original_amount=face_value,
        charge_off_date=now - timedelta(days=60),
        charge_off_amount=face_value,
        total_payments_made=Decimal("0"),
        longest_delinquency_days=60,
        payment_velocity=0.0,
        quan_risk_score=60.0,
        shadow_bureau_score=shadow_bureau_score,
        recovery_probability=recovery_probability,
        consumer_hash=f"hash-{idx:04d}",
        geo_region="CA",
        age_bucket="25-34",
    )


@pytest.fixture
def sample_debt_metadata() -> DebtMetadata:
    """Single deterministic BNPL debt record."""
    return make_debt_metadata()


@pytest.fixture
def platform() -> RWATokenizationPlatform:
    """Fresh tokenization platform."""
    return RWATokenizationPlatform()


@pytest.fixture
def active_pool(platform: RWATokenizationPlatform) -> dict:
    """
    Fully provisioned pool:

    - 20 tokenized BNPL debts of $60k face each ($1.2M, above the $1M minimum)
    - Pool closed and activated
    - DROP/TIN tranches created (80/20 split on current value of $780k)
    - One DROP investor ($100k) and one TIN investor ($30k) subscribed
    """
    records = [(f"DEBT-{i:04d}", make_debt_metadata(i)) for i in range(20)]
    batch = platform.tokenizer.batch_tokenize(records)

    pool = platform.pool_manager.create_pool(
        pool_name="Test BNPL Pool",
        asset_class=AssetClass.BNPL_PRIME,
    )
    added = platform.pool_manager.add_assets_batch(pool.pool_id, batch.token_ids)
    assert added == 20

    assert platform.pool_manager.close_pool(pool.pool_id)
    assert platform.pool_manager.activate_pool(pool.pool_id)

    drop, tin = platform.tranche_manager.create_tranches(pool.pool_id)

    platform.investor_portal.subscribe(
        "INV-DROP", pool.pool_id, TrancheType.DROP, Decimal("100000")
    )
    platform.investor_portal.subscribe(
        "INV-TIN", pool.pool_id, TrancheType.TIN, Decimal("30000")
    )

    return {
        "platform": platform,
        "pool_id": pool.pool_id,
        "pool": pool,
        "drop": drop,
        "tin": tin,
        "drop_investor": "INV-DROP",
        "tin_investor": "INV-TIN",
    }


# ---------------------------------------------------------------------------
# Asset Tokenizer Tests
# ---------------------------------------------------------------------------


class TestAssetTokenizer:
    """Tests for NFT minting and batch tokenization."""

    def test_mint_nft_basic_fields(self, sample_debt_metadata: DebtMetadata):
        """mint_nft should populate token ID, face value, and valuation."""
        tokenizer = AssetTokenizer()
        nft = tokenizer.mint_nft("DEBT-0001", sample_debt_metadata)

        assert nft.token_id
        assert len(nft.token_id) == 64  # sha3-256 hex digest
        assert nft.face_value == sample_debt_metadata.charge_off_amount
        # Current value = face * recovery probability (exact Decimal math)
        assert nft.current_value == nft.face_value * Decimal("0.65")
        assert nft.integrity_hash
        assert tokenizer.get_token(nft.token_id) is nft
        assert tokenizer.get_token_by_record("DEBT-0001") is nft
        assert tokenizer.total_minted == 1

    def test_risk_rating_responds_to_recovery_probability(self):
        """Higher recovery probability must yield a better risk rating."""
        tokenizer = AssetTokenizer()
        high = tokenizer.mint_nft(
            "DEBT-HI", make_debt_metadata(recovery_probability=0.90)
        )
        low = tokenizer.mint_nft(
            "DEBT-LO", make_debt_metadata(recovery_probability=0.20)
        )

        # Better rating = higher expected recovery band
        assert high.risk_rating.recovery_low > low.risk_rating.recovery_low

    def test_batch_tokenize_returns_batch_with_merkle_root(self):
        """batch_tokenize should mint N tokens and compute a Merkle root."""
        tokenizer = AssetTokenizer()
        records = [(f"DEBT-{i:04d}", make_debt_metadata(i)) for i in range(5)]
        batch = tokenizer.batch_tokenize(records)

        assert batch.status == "completed"
        assert batch.total_tokens == 5
        assert len(batch.token_ids) == 5
        assert batch.merkle_root
        assert batch.total_face_value == Decimal("60000") * 5
        assert tokenizer.total_minted == 5

    def test_asset_class_bnpl_prime_vs_subprime(self):
        """BNPL classification splits on shadow bureau score (>=600 prime)."""
        tokenizer = AssetTokenizer()
        prime = tokenizer.mint_nft(
            "DEBT-P", make_debt_metadata(shadow_bureau_score=650)
        )
        subprime = tokenizer.mint_nft(
            "DEBT-S", make_debt_metadata(shadow_bureau_score=500)
        )

        assert prime.asset_class == AssetClass.BNPL_PRIME
        assert subprime.asset_class == AssetClass.BNPL_SUBPRIME

    def test_asset_class_from_debt_category(self):
        """Non-BNPL categories map to the matching asset class."""
        tokenizer = AssetTokenizer()
        cases = [
            ("Subscription - SaaS Tech", AssetClass.SUBSCRIPTION_TECH),
            ("Medical - LabCorp", AssetClass.MEDICAL_MICRO),
            ("Rent arrears", AssetClass.RENT_ARREARS),
            ("Something unknown", AssetClass.MIXED_MICRO),
        ]
        for i, (category, expected) in enumerate(cases):
            nft = tokenizer.mint_nft(
                f"DEBT-C{i}", make_debt_metadata(i, debt_category=category)
            )
            assert nft.asset_class == expected, f"Category {category!r}"

    def test_metadata_hash_deterministic(self):
        """Identical metadata inputs must produce identical hashes."""
        a = make_debt_metadata(1)
        b = make_debt_metadata(1)
        # Align datetime fields (factory calls datetime.now() per instance)
        b.origination_date = a.origination_date
        b.charge_off_date = a.charge_off_date

        assert a.metadata_hash
        assert a._compute_hash() == b._compute_hash()


# ---------------------------------------------------------------------------
# Pool Manager Tests
# ---------------------------------------------------------------------------


class TestPoolManager:
    """Tests for pool creation, asset aggregation, and lifecycle."""

    def test_create_pool_initial_state(self, platform: RWATokenizationPlatform):
        """New pool should be OPEN with complementary tranche ratios."""
        pool = platform.pool_manager.create_pool(
            "Pool A", AssetClass.BNPL_PRIME, drop_ratio=Decimal("0.75")
        )

        assert pool.status == PoolStatus.OPEN
        assert pool.drop_ratio == Decimal("0.75")
        assert pool.tin_ratio == Decimal("0.25")
        assert pool.min_pool_size == Decimal("1000000")
        assert platform.pool_manager.get_pool(pool.pool_id) is pool

    def test_add_asset_updates_pool_metrics(self, platform: RWATokenizationPlatform):
        """Adding an asset should lock the token and update metrics."""
        nft = platform.tokenizer.mint_nft("DEBT-0001", make_debt_metadata())
        pool = platform.pool_manager.create_pool("Pool B", AssetClass.BNPL_PRIME)

        assert platform.pool_manager.add_asset_to_pool(pool.pool_id, nft.token_id)

        assert nft.is_locked
        assert nft.pool_id == pool.pool_id
        assert pool.metrics.total_assets == 1
        assert pool.metrics.total_face_value == Decimal("60000")
        assert pool.metrics.total_current_value == Decimal("60000") * Decimal("0.65")

    def test_status_transitions_open_closed_active(self, active_pool: dict):
        """Pool from fixture has gone OPEN -> CLOSED -> ACTIVE."""
        pool = active_pool["pool"]
        assert pool.status == PoolStatus.ACTIVE
        assert pool.closed_at is not None
        assert pool.activated_at is not None
        assert pool.maturity_date is not None

    def test_activate_without_close_rejected(self, platform: RWATokenizationPlatform):
        """OPEN -> ACTIVE is an invalid transition and must be rejected."""
        pool = platform.pool_manager.create_pool("Pool C", AssetClass.BNPL_PRIME)

        assert not platform.pool_manager.activate_pool(pool.pool_id)
        assert pool.status == PoolStatus.OPEN

    def test_close_below_minimum_size_rejected(self, platform: RWATokenizationPlatform):
        """Pool below the $1M minimum face value cannot be closed."""
        nft = platform.tokenizer.mint_nft("DEBT-0001", make_debt_metadata())
        pool = platform.pool_manager.create_pool("Pool D", AssetClass.BNPL_PRIME)
        platform.pool_manager.add_asset_to_pool(pool.pool_id, nft.token_id)

        assert not platform.pool_manager.close_pool(pool.pool_id)
        assert pool.status == PoolStatus.OPEN

    def test_add_asset_to_closed_pool_rejected(self, active_pool: dict):
        """Non-OPEN pools must not accept new assets."""
        platform = active_pool["platform"]
        nft = platform.tokenizer.mint_nft("DEBT-LATE", make_debt_metadata(99))

        assert not platform.pool_manager.add_asset_to_pool(
            active_pool["pool_id"], nft.token_id
        )
        assert nft.token_id not in active_pool["pool"].asset_token_ids

    def test_close_active_pool_rejected(self, active_pool: dict):
        """ACTIVE -> CLOSED is an invalid backward transition."""
        platform = active_pool["platform"]
        pool = active_pool["pool"]
        assert pool.status == PoolStatus.ACTIVE

        assert not platform.pool_manager.close_pool(active_pool["pool_id"])
        assert pool.status == PoolStatus.ACTIVE


# ---------------------------------------------------------------------------
# Tranche Structure Tests
# ---------------------------------------------------------------------------


class TestTranches:
    """Tests for DROP/TIN tranche creation and waterfall execution."""

    def test_create_tranches_supply_split_and_priority(self, active_pool: dict):
        """DROP is senior (priority 1) at 80%, TIN junior (priority 2) at 20%."""
        drop, tin = active_pool["drop"], active_pool["tin"]
        pool = active_pool["pool"]
        total_value = pool.metrics.total_current_value  # $780k

        assert drop.tranche_type == TrancheType.DROP
        assert tin.tranche_type == TrancheType.TIN
        assert drop.priority == 1
        assert tin.priority == 2
        assert drop.total_supply == total_value * Decimal("0.80")
        assert tin.total_supply == total_value * Decimal("0.20")
        # TIN subordination protects DROP; TIN itself is first-loss
        assert drop.subordination_ratio == Decimal("0.20")
        assert tin.subordination_ratio == Decimal("0")

    def test_create_tranches_requires_closed_pool(
        self, platform: RWATokenizationPlatform
    ):
        """Tranche creation on an OPEN pool must raise."""
        pool = platform.pool_manager.create_pool("Pool E", AssetClass.BNPL_PRIME)

        with pytest.raises(ValueError):
            platform.tranche_manager.create_tranches(pool.pool_id)

    def test_waterfall_ample_collections_no_shortfall(self, active_pool: dict):
        """With ample cash, both tranches receive full interest."""
        platform = active_pool["platform"]
        dist = platform.tranche_manager.execute_waterfall(
            active_pool["pool_id"], collections=Decimal("100000")
        )

        assert dist.status == "completed"
        assert dist.drop_shortfall == Decimal("0")
        assert dist.tin_shortfall == Decimal("0")
        assert dist.drop_interest > Decimal("0")
        assert dist.tin_interest > Decimal("0")

    def test_waterfall_tin_takes_shortfall_before_drop(self, active_pool: dict):
        """When cash covers DROP interest but not TIN, only TIN is short."""
        platform = active_pool["platform"]
        drop, tin = active_pool["drop"], active_pool["tin"]

        # Daily interest due: DROP = 100k * 6.5%/365 ~ $17.81,
        # TIN = 30k * 16%/365 ~ $13.15. $20 covers DROP only.
        drop_due = drop.circulating_supply * drop.current_yield / Decimal("365")
        tin_due = tin.circulating_supply * tin.current_yield / Decimal("365")
        collections = Decimal("20")
        assert drop_due < collections < drop_due + tin_due  # sanity

        dist = platform.tranche_manager.execute_waterfall(
            active_pool["pool_id"], collections=collections
        )

        assert dist.drop_shortfall == Decimal("0")
        assert dist.drop_interest == drop_due
        assert dist.tin_shortfall > Decimal("0")
        assert dist.tin_interest == collections - drop_due

    def test_waterfall_expenses_exceeding_inflow_floors_at_zero(
        self, active_pool: dict
    ):
        """Expenses above inflow must not produce negative allocations."""
        platform = active_pool["platform"]
        dist = platform.tranche_manager.execute_waterfall(
            active_pool["pool_id"],
            collections=Decimal("10"),
            operating_expenses=Decimal("100"),
        )

        assert dist.drop_interest >= Decimal("0")
        assert dist.tin_interest >= Decimal("0")
        assert dist.drop_shortfall > Decimal("0")
        assert dist.tin_shortfall > Decimal("0")

    def test_waterfall_conservation_of_cash(self, active_pool: dict):
        """Allocations + expenses must never exceed total cash inflow."""
        platform = active_pool["platform"]
        dist = platform.tranche_manager.execute_waterfall(
            active_pool["pool_id"],
            collections=Decimal("50000"),
            recoveries=Decimal("5000"),
            operating_expenses=Decimal("500"),
        )

        allocated = (
            dist.drop_interest
            + dist.drop_principal
            + dist.tin_interest
            + dist.tin_principal
            + dist.reserve_contribution
            + dist.operating_expenses
        )
        assert allocated <= dist.total_cash_inflow
        assert dist.total_cash_inflow == Decimal("55000")


# ---------------------------------------------------------------------------
# Epoch Execution Tests
# ---------------------------------------------------------------------------


class TestRunEpoch:
    """Tests for the platform-level epoch cycle."""

    def test_run_epoch_returns_expected_keys(self, active_pool: dict):
        """run_epoch result must contain epoch/pool_id/waterfall/nav keys."""
        platform = active_pool["platform"]
        result = platform.run_epoch(active_pool["pool_id"], Decimal("50000"))

        assert set(result.keys()) >= {"epoch", "pool_id", "waterfall", "nav"}
        assert result["pool_id"] == active_pool["pool_id"]
        assert set(result["waterfall"].keys()) >= {
            "total_inflow",
            "drop_interest",
            "tin_interest",
            "reserve_contribution",
        }
        assert set(result["nav"].keys()) >= {"total", "drop_per_token", "tin_per_token"}

    def test_collections_and_recoveries_flow_into_inflow(self, active_pool: dict):
        """total_inflow == collections + recoveries."""
        platform = active_pool["platform"]
        result = platform.run_epoch(
            active_pool["pool_id"],
            collections=Decimal("40000"),
            recoveries=Decimal("2500"),
        )

        assert result["waterfall"]["total_inflow"] == 42500.0

    def test_consecutive_epochs_increment_counter(self, active_pool: dict):
        """Each run_epoch advances the epoch counter by one."""
        platform = active_pool["platform"]
        first = platform.run_epoch(active_pool["pool_id"], Decimal("50000"))
        second = platform.run_epoch(active_pool["pool_id"], Decimal("50000"))

        assert first["epoch"] == 1
        assert second["epoch"] == 2

    def test_zero_collections_epoch_does_not_crash(self, active_pool: dict):
        """A dry epoch should complete with zero inflow and no exceptions."""
        platform = active_pool["platform"]
        result = platform.run_epoch(active_pool["pool_id"], Decimal("0"))

        assert result["epoch"] == 1
        assert result["waterfall"]["total_inflow"] == 0.0
        assert result["waterfall"]["drop_interest"] == 0.0
        assert result["waterfall"]["tin_interest"] == 0.0
        # The unpaid interest shows up as shortfall on the recorded waterfall
        waterfall = platform.tranche_manager.waterfalls[-1]
        assert waterfall.drop_shortfall > Decimal("0")
        assert waterfall.tin_shortfall > Decimal("0")

    def test_nav_non_negative_and_drop_stable(self, active_pool: dict):
        """NAV totals stay non-negative; DROP NAV/token holds at par when
        pool assets comfortably exceed the DROP liability."""
        platform = active_pool["platform"]
        for _ in range(3):
            result = platform.run_epoch(active_pool["pool_id"], Decimal("60000"))
            assert result["nav"]["total"] >= 0.0
            assert result["nav"]["drop_per_token"] == 1.0
            assert result["nav"]["tin_per_token"] >= 0.0

    def test_run_epoch_conservation(self, active_pool: dict):
        """drop_interest + tin_interest + reserve + expenses <= inflow."""
        platform = active_pool["platform"]
        platform.run_epoch(
            active_pool["pool_id"],
            collections=Decimal("80000"),
            recoveries=Decimal("4000"),
        )

        waterfall = platform.tranche_manager.waterfalls[-1]
        allocated = (
            waterfall.drop_interest
            + waterfall.tin_interest
            + waterfall.drop_principal
            + waterfall.tin_principal
            + waterfall.reserve_contribution
            + waterfall.operating_expenses
        )
        assert allocated <= waterfall.total_cash_inflow


# ---------------------------------------------------------------------------
# Investor Portal Tests
# ---------------------------------------------------------------------------


class TestInvestorPortal:
    """Tests for subscriptions, NAV, and yield distribution."""

    def test_subscribe_creates_position_with_token_amount(self, active_pool: dict):
        """Tokens received = amount / token price ($1.00 at issuance)."""
        portal = active_pool["platform"].investor_portal
        position = portal.get_position(
            active_pool["drop_investor"], active_pool["pool_id"]
        )

        assert position is not None
        assert position.drop_tokens == Decimal("100000")
        assert position.drop_cost_basis == Decimal("100000")
        assert active_pool["drop"].circulating_supply == Decimal("100000")
        assert active_pool["tin"].circulating_supply == Decimal("30000")

    def test_subscribe_insufficient_supply_raises(self, active_pool: dict):
        """Subscriptions beyond remaining tranche supply must be rejected."""
        portal = active_pool["platform"].investor_portal
        oversized = active_pool["tin"].total_supply * 2

        with pytest.raises(ValueError):
            portal.subscribe(
                "INV-WHALE", active_pool["pool_id"], TrancheType.TIN, oversized
            )

    def test_calculate_nav_totals(self, active_pool: dict):
        """NAV must split into DROP + TIN, with DROP capped at its liability."""
        portal = active_pool["platform"].investor_portal
        nav = portal.calculate_nav(active_pool["pool_id"])

        assert nav.total_nav == nav.drop_nav + nav.tin_nav
        assert nav.total_nav >= Decimal("0")
        assert nav.drop_nav <= nav.drop_liability
        # Assets ($780k) far exceed DROP liability ($100k) -> DROP at par
        assert nav.drop_nav_per_token == Decimal("1.0")

    def test_distribute_yield_count_matches_investors(self, active_pool: dict):
        """One distribution per invested investor; amounts match waterfall."""
        platform = active_pool["platform"]
        waterfall = platform.tranche_manager.execute_waterfall(
            active_pool["pool_id"], collections=Decimal("100000")
        )

        distributions = platform.investor_portal.distribute_yield(
            active_pool["pool_id"], waterfall
        )

        assert len(distributions) == 2  # INV-DROP and INV-TIN
        total_distributed = sum(d.total_yield for d in distributions)
        assert total_distributed == waterfall.drop_interest + waterfall.tin_interest

    def test_get_position_unknown_investor_is_none(self, active_pool: dict):
        """Unknown investor/pool combinations return None."""
        portal = active_pool["platform"].investor_portal

        assert portal.get_position("INV-NOBODY", active_pool["pool_id"]) is None
        assert portal.get_position(active_pool["drop_investor"], "POOL-MISSING") is None


# ---------------------------------------------------------------------------
# Blockchain Simulator / Platform Tests
# ---------------------------------------------------------------------------


class TestBlockchainSimulator:
    """Tests for the simulated on-chain layer."""

    def test_deploy_pool_contracts(self, active_pool: dict):
        """Deploying a pool registers pool, DROP, and TIN contracts."""
        platform = active_pool["platform"]
        pool = active_pool["pool"]
        contracts = platform.blockchain.deploy_pool_contracts(pool)

        assert set(contracts.keys()) == {"pool", "drop", "tin"}
        for address in contracts.values():
            assert address in platform.blockchain.contracts
        assert platform.blockchain.current_block >= 1

    def test_investor_compliance_verification(self, active_pool: dict):
        """Compliance record enforces accreditation, jurisdiction, and KYC."""
        blockchain = active_pool["platform"].blockchain
        pool_id = active_pool["pool_id"]
        blockchain.create_compliance_record(pool_id)

        ok, _ = blockchain.verify_investor_compliance(
            pool_id, "0xabc", is_accredited=True, jurisdiction="US", kyc_verified=True
        )
        assert ok

        not_accredited, reason = blockchain.verify_investor_compliance(
            pool_id, "0xabc", is_accredited=False, jurisdiction="US", kyc_verified=True
        )
        assert not not_accredited
        assert "accredited" in reason.lower()

        blocked, _ = blockchain.verify_investor_compliance(
            pool_id, "0xabc", is_accredited=True, jurisdiction="IR", kyc_verified=True
        )
        assert not blocked

    def test_platform_metrics_reflect_active_pool(self, active_pool: dict):
        """Platform-wide metrics aggregate minted tokens and active pools."""
        metrics = active_pool["platform"].get_platform_metrics()

        assert metrics["total_tokens_minted"] == 20
        assert metrics["total_face_value"] == 1200000.0
        assert metrics["active_pools"] == 1
        assert metrics["total_tranches"] == 2
