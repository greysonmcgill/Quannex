"""
QUAN Finance Module - Financial Reconciliation, Accounting, and Tokenization

Comprehensive financial pipeline with:
- Payment reconciliation and matching
- Settlement accounting and write-offs
- Trust accounting (FDCPA-compliant)
- Creditor remittance and fee management
- Portfolio accounting and valuations
- Bank/processor reconciliation
- SOX-compliant audit trails
- Comprehensive reporting suite
- RWA (Real-World Asset) Tokenization
- Centrifuge/Tinlake tranche structure
"""

# Import reconciliation pipeline
from quan.finance.reconciliation import (
    # Core Pipeline
    FinancialReconciliationPipeline,

    # Payment Reconciliation
    PaymentReconciliationEngine,
    Payment,
    PaymentPlan,
    PaymentStatus,

    # Settlement Accounting
    SettlementAccountingEngine,
    Settlement,

    # Trust Accounting
    TrustAccountingEngine,
    TrustAccount,

    # Creditor Remittance
    CreditorRemittanceEngine,
    RemittanceReport,

    # Portfolio Accounting
    PortfolioAccountingEngine,

    # Reconciliation Engine
    ReconciliationEngine,
    ReconciliationException,
    ReconciliationStatus,

    # Audit Trail
    AuditTrail,
    AuditEntry,
    AuditEventType,

    # Reporting
    FinancialReportingEngine,

    # Data Structures
    Account,
    TransactionType,
    FeeStructure,
)
_RECONCILIATION_AVAILABLE = True

# Import tokenization module
from quan.finance.tokenization import (
    # Enumerations
    AssetClass,
    RiskRating,
    TokenStandard,
    TrancheType,
    PoolStatus,
    OrderSide,
    OrderType,
    # Data Models - Asset Tokenization
    PaymentHistoryEntry,
    DebtMetadata,
    DebtNFT,
    BatchTokenization,
    # Data Models - Pool Management
    PoolMetrics,
    DebtPool,
    # Data Models - Tranche Structure
    TrancheToken,
    WaterfallDistribution,
    # Data Models - Liquidity
    AssetValuation,
    OrderBookEntry,
    LiquidityMetrics,
    # Data Models - Investor
    InvestorPosition,
    YieldDistribution,
    NAVCalculation,
    RedemptionRequest,
    # Data Models - Blockchain
    BlockchainTransaction,
    SmartContractState,
    ComplianceRecord,
    # Core Engines
    CryptoUtils,
    AssetTokenizer,
    PoolManager,
    TrancheManager,
    LiquidityEngine,
    InvestorPortal,
    BlockchainSimulator,
    # Unified Platform
    RWATokenizationPlatform,
)

__all__ = [
    # Core Reconciliation Pipeline
    "FinancialReconciliationPipeline",
    # Payment Reconciliation
    "PaymentReconciliationEngine",
    "Payment",
    "PaymentPlan",
    "PaymentStatus",
    # Settlement Accounting
    "SettlementAccountingEngine",
    "Settlement",
    # Trust Accounting
    "TrustAccountingEngine",
    "TrustAccount",
    # Creditor Remittance
    "CreditorRemittanceEngine",
    "RemittanceReport",
    # Portfolio Accounting
    "PortfolioAccountingEngine",
    # Reconciliation Engine
    "ReconciliationEngine",
    "ReconciliationException",
    "ReconciliationStatus",
    # Audit Trail
    "AuditTrail",
    "AuditEntry",
    "AuditEventType",
    # Reporting
    "FinancialReportingEngine",
    # Data Structures
    "Account",
    "TransactionType",
    "FeeStructure",
    # Tokenization Enumerations
    "AssetClass",
    "RiskRating",
    "TokenStandard",
    "TrancheType",
    "PoolStatus",
    "OrderSide",
    "OrderType",
    # Tokenization Data Models
    "PaymentHistoryEntry",
    "DebtMetadata",
    "DebtNFT",
    "BatchTokenization",
    "PoolMetrics",
    "DebtPool",
    "TrancheToken",
    "WaterfallDistribution",
    "AssetValuation",
    "OrderBookEntry",
    "LiquidityMetrics",
    "InvestorPosition",
    "YieldDistribution",
    "NAVCalculation",
    "RedemptionRequest",
    "BlockchainTransaction",
    "SmartContractState",
    "ComplianceRecord",
    # Tokenization Engines
    "CryptoUtils",
    "AssetTokenizer",
    "PoolManager",
    "TrancheManager",
    "LiquidityEngine",
    "InvestorPortal",
    "BlockchainSimulator",
    "RWATokenizationPlatform",
]
