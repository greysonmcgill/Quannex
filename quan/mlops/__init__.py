"""
MLOps Module for QUAN

Provides ML operations infrastructure including:
- Deterministic, reproducible training pipelines
- Environment capture and Docker generation
- Checkpoint-based training resumption
- Multi-model training (GradientBoost, Neural Net, Bayesian)
- Cross-validation with stratification
- Uncertainty estimation and quantification
- Model calibration
- Conformal prediction
- OOD detection
- Decision routing
- Fairness and bias auditing
- Mitigation strategies for algorithmic bias
- Human-in-the-Loop (HITL) decision routing
- Policy-based approval/rejection workflows
- Audit trail management
- Reviewer load balancing
- SLA tracking and escalation
- Data contracts and canonical datasets
- PII redaction and tokenization
- Dataset versioning and lineage tracking
- Drift detection and observability
- Feature and label drift monitoring (PSI, KS test)
- Concept drift identification
- Prometheus/Grafana integration for ML metrics
- Immutable audit logging with cryptographic signing
- Tamper detection via hash chains and Merkle trees
- Legal hold and retention policy management
- Compliance export for regulatory reviews
- Production inference service with model serving
- FastAPI/BentoML compatible inference endpoints
- Model versioning and hot-swapping
- Rate limiting and circuit breakers
- Batch prediction with autoscaling
- Prometheus metrics export
- Kubernetes deployment manifests
"""

from quan.mlops.uncertainty_estimation import (
    UncertaintyEstimator,
    UncertaintyType,
    ConfidenceLevel,
    DecisionRoute,
    PredictionInterval,
    ConfidenceInterval,
    UncertaintyMetrics,
    UncertaintyAwarePrediction,
    EnsembleUncertaintyEstimator,
    MonteCarloDropoutEstimator,
    VariationalBayesianEstimator,
    ConformalPredictor,
    UncertaintySeparator,
    UncertaintyCalibrator,
    OODDetector,
    UncertaintyDecisionRouter,
    UncertaintyEstimatorTests,
)

from quan.mlops.fairness_audit import (
    FairnessAuditor,
    FairnessMetricsCalculator,
    SensitiveFeatureDetector,
    PerformanceGapDetector,
    FairnessTestSuite,
    ReweighingMitigation,
    ThresholdOptimizer,
    CalibratedEqualizedOddsMitigation,
    AdversarialDebiasingHooks,
    ProtectedAttribute,
    BiasType,
    MitigationStrategy,
    FairnessMetricType,
    FAIRNESS_THRESHOLDS,
    GroupStatistics,
    FairnessMetric,
    BiasAlert,
    MitigationResult,
    FairnessReport,
)

from quan.mlops.hitl_routing import (
    # Core classes
    HITLRouter,
    PolicyEngine,
    HITLQueue,
    ReviewerPool,
    EscalationEngine,
    FeedbackLoop,
    AuditTrail,
    # Data classes
    Decision,
    Reviewer,
    PolicyThresholds,
    PolicyDocument,
    AuditEntry,
    # Enums
    RoutingDecision,
    ReviewPriority,
    ReviewerStatus,
    ReviewOutcome,
)

from quan.mlops.training_pipeline import (
    # Configuration
    TrainingConfig,
    EnvironmentSpec,
    DependencySpec,
    TrainingMetrics,
    Checkpoint,
    # Enums
    ModelType,
    DeviceType,
    CheckpointType,
    # Core trainers
    DeterministicTrainer,
    MultiModelTrainer,
    # Managers
    SeedManager,
    EnvironmentManager,
    DeviceManager,
    CheckpointManager,
    # Utilities
    CrossValidator,
    EarlyStopping,
    BatchIterator,
    # Checksum functions
    compute_file_checksum,
    compute_model_checksum,
    verify_artifact_checksum,
)

try:
    from quan.mlops.test_harness import (
        # Core test harness
        TestHarness,
        TestResult,
        TestMetrics,
        TestAccount,
        # State machine
        AccountState,
        VALID_TRANSITIONS,
        # Mocking utilities
        MockExternalService,
        MockPaymentGateway,
        MockSkipTraceService,
        MockCommunicationService,
        create_mock_context,
    )
    TEST_HARNESS_AVAILABLE = True
except ImportError:
    TEST_HARNESS_AVAILABLE = False
    TestHarness = None
    TestResult = None
    TestMetrics = None
    TestAccount = None
    AccountState = None
    VALID_TRANSITIONS = None
    MockExternalService = None
    MockPaymentGateway = None
    MockSkipTraceService = None
    MockCommunicationService = None
    create_mock_context = None

from quan.mlops.data_contracts import (
    # Schema classes
    DataSchema,
    FeatureSchema,
    LabelSchema,
    # Dataset builder
    CanonicalDatasetBuilder,
    # PII handling
    PIIRedactor,
    PIIType,
    RedactionStrategy,
    PIIToken,
    # Contract enforcement
    DataContractEnforcer,
    ValidationResult,
    # Versioning
    DatasetVersionManager,
    # Sampling
    SamplingStrategy,
    HashBasedSampler,
    TimeWindowSampler,
    CohortStratifier,
    # Labeling
    LabelingRules,
    # Lineage
    DataLineageTracker,
    LineageNode,
    LineageEdge,
    # Enums
    DatasetSplit,
    FeatureType,
    LabelType,
    # Build functions
    build_canonical_datasets,
    generate_schema_yaml,
)

__all__ = [
    # Uncertainty estimation
    "UncertaintyEstimator",
    "UncertaintyType",
    "ConfidenceLevel",
    "DecisionRoute",
    "PredictionInterval",
    "ConfidenceInterval",
    "UncertaintyMetrics",
    "UncertaintyAwarePrediction",
    "EnsembleUncertaintyEstimator",
    "MonteCarloDropoutEstimator",
    "VariationalBayesianEstimator",
    "ConformalPredictor",
    "UncertaintySeparator",
    "UncertaintyCalibrator",
    "OODDetector",
    "UncertaintyDecisionRouter",
    "UncertaintyEstimatorTests",
    # Fairness auditing
    "FairnessAuditor",
    "FairnessMetricsCalculator",
    "SensitiveFeatureDetector",
    "PerformanceGapDetector",
    "FairnessTestSuite",
    "ReweighingMitigation",
    "ThresholdOptimizer",
    "CalibratedEqualizedOddsMitigation",
    "AdversarialDebiasingHooks",
    "ProtectedAttribute",
    "BiasType",
    "MitigationStrategy",
    "FairnessMetricType",
    "FAIRNESS_THRESHOLDS",
    "GroupStatistics",
    "FairnessMetric",
    "BiasAlert",
    "MitigationResult",
    "FairnessReport",
    # HITL routing
    "HITLRouter",
    "PolicyEngine",
    "HITLQueue",
    "ReviewerPool",
    "EscalationEngine",
    "FeedbackLoop",
    "AuditTrail",
    "Decision",
    "Reviewer",
    "PolicyThresholds",
    "PolicyDocument",
    "AuditEntry",
    "RoutingDecision",
    "ReviewPriority",
    "ReviewerStatus",
    "ReviewOutcome",
    # Training pipeline - Configuration
    "TrainingConfig",
    "EnvironmentSpec",
    "DependencySpec",
    "TrainingMetrics",
    "Checkpoint",
    # Training pipeline - Enums
    "ModelType",
    "DeviceType",
    "CheckpointType",
    # Training pipeline - Core trainers
    "DeterministicTrainer",
    "MultiModelTrainer",
    # Training pipeline - Managers
    "SeedManager",
    "EnvironmentManager",
    "DeviceManager",
    "CheckpointManager",
    # Training pipeline - Utilities
    "CrossValidator",
    "EarlyStopping",
    "BatchIterator",
    # Training pipeline - Checksum functions
    "compute_file_checksum",
    "compute_model_checksum",
    "verify_artifact_checksum",
    # Test harness
    "TestHarness",
    "TestResult",
    "TestMetrics",
    "TestAccount",
    "AccountState",
    "VALID_TRANSITIONS",
    "MockExternalService",
    "MockPaymentGateway",
    "MockSkipTraceService",
    "MockCommunicationService",
    "create_mock_context",
    # Data contracts - Schema classes
    "DataSchema",
    "FeatureSchema",
    "LabelSchema",
    # Data contracts - Dataset builder
    "CanonicalDatasetBuilder",
    # Data contracts - PII handling
    "PIIRedactor",
    "PIIType",
    "RedactionStrategy",
    "PIIToken",
    # Data contracts - Contract enforcement
    "DataContractEnforcer",
    "ValidationResult",
    # Data contracts - Versioning
    "DatasetVersionManager",
    # Data contracts - Sampling
    "SamplingStrategy",
    "HashBasedSampler",
    "TimeWindowSampler",
    "CohortStratifier",
    # Data contracts - Labeling
    "LabelingRules",
    # Data contracts - Lineage
    "DataLineageTracker",
    "LineageNode",
    "LineageEdge",
    # Data contracts - Enums
    "DatasetSplit",
    "FeatureType",
    "LabelType",
    # Data contracts - Build functions
    "build_canonical_datasets",
    "generate_schema_yaml",
]

# Explainability and interpretability
from quan.mlops.explainability import (
    # Main engine
    ExplainabilityEngine,
    # Enums
    ExplanationType,
    ModelCategory,
    VisualizationType,
    # Data classes
    Explanation,
    FeatureContribution,
    CounterfactualExplanation,
    FeatureInteraction,
    GlobalImportanceReport,
    Visualization,
    AuditLogEntry,
    # Explainers
    SHAPExplainer,
    LIMEExplainer,
    IntegratedGradientsExplainer,
    CounterfactualExplainer,
    FeatureInteractionDetector,
    GlobalFeatureImportance,
    # Utilities
    VisualizationGenerator,
    ExplanationCache,
    ExplanationStorage,
    AuditLogStorage,
    BatchExplanationProcessor,
    ExplanationTemplates,
)

# Add to __all__
__all__.extend([
    # Explainability - Main engine
    "ExplainabilityEngine",
    # Explainability - Enums
    "ExplanationType",
    "ModelCategory",
    "VisualizationType",
    # Explainability - Data classes
    "Explanation",
    "FeatureContribution",
    "CounterfactualExplanation",
    "FeatureInteraction",
    "GlobalImportanceReport",
    "Visualization",
    "AuditLogEntry",
    # Explainability - Explainers
    "SHAPExplainer",
    "LIMEExplainer",
    "IntegratedGradientsExplainer",
    "CounterfactualExplainer",
    "FeatureInteractionDetector",
    "GlobalFeatureImportance",
    # Explainability - Utilities
    "VisualizationGenerator",
    "ExplanationCache",
    "ExplanationStorage",
    "AuditLogStorage",
    "BatchExplanationProcessor",
    "ExplanationTemplates",
])

# Immutable Audit Logging
from quan.mlops.audit_logging import (
    # Main logger
    AuditLogger,
    # Enums
    ActorType,
    DecisionType,
    StorageType,
    RetentionPolicyType,
    ExportFormat,
    PIIHandlingStrategy,
    AuditLogLevel,
    IntegrityStatus,
    # Data classes - Core audit schema
    MicrosecondTimestamp,
    ModelVersion,
    Actor,
    InputFeatures,
    OutputPrediction,
    DecisionExplanation,
    PolicyContext,
    CryptographicSignature,
    RetentionPolicy,
    AuditEntry as ImmutableAuditEntry,  # Alias to avoid conflict with HITL AuditEntry
    # PII handling
    PIIHandler,
    # Cryptographic components
    CryptographicSigner,
    HashChain,
    MerkleTree,
    # Storage backends
    StorageBackend,
    LocalAppendOnlyStorage,
    S3ObjectLockStorage,
    WORMDatabaseStorage,
    # Batch writing
    BatchAuditWriter,
    # Tamper detection
    TamperDetector,
    # Retention management
    RetentionManager,
    # Compliance export
    ComplianceExporter,
    # Decorator
    audit_decision,
    # Demo function
    demonstrate_audit_logging,
)

# Add audit logging to __all__
__all__.extend([
    # Audit Logging - Main logger
    "AuditLogger",
    # Audit Logging - Enums
    "ActorType",
    "DecisionType",
    "StorageType",
    "RetentionPolicyType",
    "ExportFormat",
    "PIIHandlingStrategy",
    "AuditLogLevel",
    "IntegrityStatus",
    # Audit Logging - Data classes
    "MicrosecondTimestamp",
    "ModelVersion",
    "Actor",
    "InputFeatures",
    "OutputPrediction",
    "DecisionExplanation",
    "PolicyContext",
    "CryptographicSignature",
    "RetentionPolicy",
    "ImmutableAuditEntry",
    # Audit Logging - PII handling
    "PIIHandler",
    # Audit Logging - Cryptographic components
    "CryptographicSigner",
    "HashChain",
    "MerkleTree",
    # Audit Logging - Storage backends
    "StorageBackend",
    "LocalAppendOnlyStorage",
    "S3ObjectLockStorage",
    "WORMDatabaseStorage",
    # Audit Logging - Batch writing
    "BatchAuditWriter",
    # Audit Logging - Tamper detection
    "TamperDetector",
    # Audit Logging - Retention management
    "RetentionManager",
    # Audit Logging - Compliance export
    "ComplianceExporter",
    # Audit Logging - Decorator
    "audit_decision",
    # Audit Logging - Demo
    "demonstrate_audit_logging",
])

# Production Inference Service
from quan.mlops.inference_service import (
    # Main service class
    InferenceService,
    # Enums
    ModelStatus,
    ServiceStatus,
    CircuitState,
    PredictionType,
    ExplanationLevel,
    # Request/Response models
    PredictionRequest,
    PredictionResponse,
    BatchPredictionRequest,
    BatchPredictionResponse,
    UncertaintyEstimate,
    FeatureExplanation,
    PredictionExplanation,
    # Health check models
    HealthCheck,
    ReadinessCheck,
    LivenessCheck,
    # Metrics
    MetricsCollector,
    # Rate limiting
    TokenBucketRateLimiter,
    SlidingWindowRateLimiter,
    # Circuit breaker
    CircuitBreaker,
    # Model management
    ModelVersion as InferenceModelVersion,
    ModelRegistry,
    ModelLoader,
    # Batch processing
    BatchProcessor,
    # Inference engine
    InferenceEngine,
    # FastAPI factory
    create_fastapi_app,
    # Configuration constants
    SLA_P95_LATENCY_MS,
    SLA_P99_LATENCY_MS,
    HPA_MIN_REPLICAS,
    HPA_MAX_REPLICAS,
    # Kubernetes manifests
    KUBERNETES_DEPLOYMENT_MANIFEST,
    DOCKERFILE,
    # Tests
    InferenceServiceTests,
)

# Add inference service to __all__
__all__.extend([
    # Inference Service - Main class
    "InferenceService",
    # Inference Service - Enums
    "ModelStatus",
    "ServiceStatus",
    "CircuitState",
    "PredictionType",
    "ExplanationLevel",
    # Inference Service - Request/Response
    "PredictionRequest",
    "PredictionResponse",
    "BatchPredictionRequest",
    "BatchPredictionResponse",
    "UncertaintyEstimate",
    "FeatureExplanation",
    "PredictionExplanation",
    # Inference Service - Health checks
    "HealthCheck",
    "ReadinessCheck",
    "LivenessCheck",
    # Inference Service - Metrics
    "MetricsCollector",
    # Inference Service - Rate limiting
    "TokenBucketRateLimiter",
    "SlidingWindowRateLimiter",
    # Inference Service - Circuit breaker
    "CircuitBreaker",
    # Inference Service - Model management
    "InferenceModelVersion",
    "ModelRegistry",
    "ModelLoader",
    # Inference Service - Batch processing
    "BatchProcessor",
    # Inference Service - Engine
    "InferenceEngine",
    # Inference Service - FastAPI
    "create_fastapi_app",
    # Inference Service - Configuration
    "SLA_P95_LATENCY_MS",
    "SLA_P99_LATENCY_MS",
    "HPA_MIN_REPLICAS",
    "HPA_MAX_REPLICAS",
    # Inference Service - Kubernetes
    "KUBERNETES_DEPLOYMENT_MANIFEST",
    "DOCKERFILE",
    # Inference Service - Tests
    "InferenceServiceTests",
])

# Drift detection and observability
from quan.mlops.drift_detection import (
    # Enums
    DriftType,
    DriftSeverity,
    DriftTestType,
    AlertChannel,
    # Data classes
    DriftTestResult,
    FeatureHistogram,
    DriftAlert,
    PredictionMetrics,
    DriftReport,
    # Calculators
    PSICalculator,
    KSTestCalculator,
    JensenShannonCalculator,
    # Trackers
    FeatureHistogramTracker,
    LabelDriftDetector,
    ConceptDriftDetector,
    # Main detector
    DriftDetector,
    # Integrations
    EvidentlyIntegration,
    AlibiDetectIntegration,
    # Constants
    PSI_THRESHOLD_WARNING,
    PSI_THRESHOLD_CRITICAL,
    KS_PVALUE_THRESHOLD,
    DRIFT_DETECTION_SLA_HOURS,
    # Dashboard specs
    PROMETHEUS_ALERT_RULES,
    GRAFANA_DRIFT_DASHBOARD,
    # Tests
    DriftDetectionTests,
    # Utilities
    create_drift_detector_from_config,
    export_prometheus_rules,
    export_grafana_dashboard,
)

# Add drift detection to __all__
__all__.extend([
    # Drift detection - Enums
    "DriftType",
    "DriftSeverity",
    "DriftTestType",
    "AlertChannel",
    # Drift detection - Data classes
    "DriftTestResult",
    "FeatureHistogram",
    "DriftAlert",
    "PredictionMetrics",
    "DriftReport",
    # Drift detection - Calculators
    "PSICalculator",
    "KSTestCalculator",
    "JensenShannonCalculator",
    # Drift detection - Trackers
    "FeatureHistogramTracker",
    "LabelDriftDetector",
    "ConceptDriftDetector",
    # Drift detection - Main detector
    "DriftDetector",
    # Drift detection - Integrations
    "EvidentlyIntegration",
    "AlibiDetectIntegration",
    # Drift detection - Constants
    "PSI_THRESHOLD_WARNING",
    "PSI_THRESHOLD_CRITICAL",
    "KS_PVALUE_THRESHOLD",
    "DRIFT_DETECTION_SLA_HOURS",
    # Drift detection - Dashboard specs
    "PROMETHEUS_ALERT_RULES",
    "GRAFANA_DRIFT_DASHBOARD",
    # Drift detection - Tests
    "DriftDetectionTests",
    # Drift detection - Utilities
    "create_drift_detector_from_config",
    "export_prometheus_rules",
    "export_grafana_dashboard",
])

# Deployment Orchestrator - Canary and Shadow Deployments
from quan.mlops.deployment_orchestrator import (
    # Main orchestrator
    DeploymentOrchestrator,
    # Enums
    DeploymentState,
    DeploymentType,
    RollbackReason,
    ApprovalStatus,
    MetricType,
    TrafficSplitMethod,
    # Data classes
    ModelVersion as DeploymentModelVersion,
    MetricSample,
    MetricComparison,
    RollbackTrigger,
    TrafficConfig,
    ApprovalGate,
    DeploymentConfig,
    DeploymentEvent,
    Deployment,
    RollbackPlaybook,
    # Traffic routing
    TrafficRouter,
    # Statistical analysis
    StatisticalAnalyzer,
    # Metric collection
    MetricCollector,
    # Health checking
    HealthChecker,
    # Kubernetes integration
    KubernetesTrafficManager,
    # CI/CD integration
    CICDIntegration,
    # Rollback playbook
    RollbackPlaybookExecutor,
    # Shadow deployment
    ShadowDeploymentManager,
    # Constants
    CANARY_STAGES,
    VALID_TRANSITIONS as DEPLOYMENT_TRANSITIONS,
    DEFAULT_ROLLBACK_THRESHOLDS,
    # Tests
    DeploymentOrchestratorTests,
)

# Add deployment orchestrator to __all__
__all__.extend([
    # Deployment Orchestrator - Main class
    "DeploymentOrchestrator",
    # Deployment Orchestrator - Enums
    "DeploymentState",
    "DeploymentType",
    "RollbackReason",
    "ApprovalStatus",
    "MetricType",
    "TrafficSplitMethod",
    # Deployment Orchestrator - Data classes
    "DeploymentModelVersion",
    "MetricSample",
    "MetricComparison",
    "RollbackTrigger",
    "TrafficConfig",
    "ApprovalGate",
    "DeploymentConfig",
    "DeploymentEvent",
    "Deployment",
    "RollbackPlaybook",
    # Deployment Orchestrator - Traffic routing
    "TrafficRouter",
    # Deployment Orchestrator - Statistical analysis
    "StatisticalAnalyzer",
    # Deployment Orchestrator - Metric collection
    "MetricCollector",
    # Deployment Orchestrator - Health checking
    "HealthChecker",
    # Deployment Orchestrator - Kubernetes integration
    "KubernetesTrafficManager",
    # Deployment Orchestrator - CI/CD integration
    "CICDIntegration",
    # Deployment Orchestrator - Rollback playbook
    "RollbackPlaybookExecutor",
    # Deployment Orchestrator - Shadow deployment
    "ShadowDeploymentManager",
    # Deployment Orchestrator - Constants
    "CANARY_STAGES",
    "DEPLOYMENT_TRANSITIONS",
    "DEFAULT_ROLLBACK_THRESHOLDS",
    # Deployment Orchestrator - Tests
    "DeploymentOrchestratorTests",
])
