"""
Model Governance Framework for QUAN MLOps

Comprehensive governance infrastructure ensuring every production model has:
- Signed charter with clear objectives and constraints
- Assigned ownership with clear accountability
- Risk classification and appropriate controls
- Approval workflow with legal sign-off
- Retrain cadence management
- Compliance audit trail

Key Components:
- GovernanceFramework: Main orchestration class
- ModelCharter: Template and generation for model documentation
- DecisionRiskMatrix: Risk assessment and classification
- RetrainCadenceManager: Scheduling and monitoring of model updates
- ApprovalWorkflowEngine: Multi-stage approval process
- LegalSignOffTracker: Legal review and compliance sign-off

Compliance Standards:
- ECOA (Equal Credit Opportunity Act)
- FCRA (Fair Credit Reporting Act)
- UDAAP (Unfair, Deceptive, or Abusive Acts or Practices)
- State-level lending regulations
- Internal model risk management policies
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar, Generic

logger = logging.getLogger(__name__)


# =============================================================================
# Enumerations and Constants
# =============================================================================

class RiskLevel(Enum):
    """Risk classification levels for models"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def review_frequency_days(self) -> int:
        """Required review frequency based on risk level"""
        return {
            RiskLevel.LOW: 365,
            RiskLevel.MEDIUM: 180,
            RiskLevel.HIGH: 90,
            RiskLevel.CRITICAL: 30
        }[self]

    @property
    def required_approvers(self) -> int:
        """Minimum number of approvers required"""
        return {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4
        }[self]


class ModelStatus(Enum):
    """Model lifecycle status"""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PENDING_APPROVAL = "pending_approval"
    PENDING_LEGAL = "pending_legal"
    APPROVED = "approved"
    DEPLOYED = "deployed"
    MONITORING = "monitoring"
    PENDING_RETRAIN = "pending_retrain"
    RETRAINING = "retraining"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class ApprovalStatus(Enum):
    """Approval workflow status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CONDITIONAL = "conditional"
    EXPIRED = "expired"
    ESCALATED = "escalated"


class BoardRole(Enum):
    """Governance board roles"""
    DATA_SCIENTIST = "data_scientist"
    ML_ENGINEER = "ml_engineer"
    COMPLIANCE_OFFICER = "compliance_officer"
    PRODUCT_OWNER = "product_owner"
    LEGAL_COUNSEL = "legal_counsel"
    RISK_MANAGER = "risk_manager"
    EXECUTIVE_SPONSOR = "executive_sponsor"
    MODEL_VALIDATOR = "model_validator"


class ChangeType(Enum):
    """Types of model changes"""
    NEW_MODEL = "new_model"
    RETRAIN = "retrain"
    HYPERPARAMETER_UPDATE = "hyperparameter_update"
    FEATURE_ADDITION = "feature_addition"
    FEATURE_REMOVAL = "feature_removal"
    THRESHOLD_ADJUSTMENT = "threshold_adjustment"
    BUG_FIX = "bug_fix"
    DEPRECATION = "deprecation"
    ROLLBACK = "rollback"


class AuditEventType(Enum):
    """Types of audit events"""
    CHARTER_CREATED = "charter_created"
    CHARTER_UPDATED = "charter_updated"
    OWNER_ASSIGNED = "owner_assigned"
    OWNER_CHANGED = "owner_changed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    LEGAL_REVIEW_REQUESTED = "legal_review_requested"
    LEGAL_SIGNOFF = "legal_signoff"
    LEGAL_REJECTION = "legal_rejection"
    DEPLOYMENT_APPROVED = "deployment_approved"
    DEPLOYED = "deployed"
    RETRAIN_SCHEDULED = "retrain_scheduled"
    RETRAIN_STARTED = "retrain_started"
    RETRAIN_COMPLETED = "retrain_completed"
    DEPRECATION_INITIATED = "deprecation_initiated"
    MODEL_RETIRED = "model_retired"
    RISK_LEVEL_CHANGED = "risk_level_changed"
    COMPLIANCE_VIOLATION = "compliance_violation"
    EMERGENCY_OVERRIDE = "emergency_override"


class MessageRuleType(Enum):
    """Types of messaging rules requiring legal review"""
    COLLECTION_INITIAL = "collection_initial"
    COLLECTION_FOLLOWUP = "collection_followup"
    PAYMENT_REMINDER = "payment_reminder"
    SETTLEMENT_OFFER = "settlement_offer"
    HARDSHIP_PROGRAM = "hardship_program"
    VALIDATION_NOTICE = "validation_notice"
    CEASE_COMMUNICATION = "cease_communication"
    DISPUTE_ACKNOWLEDGMENT = "dispute_acknowledgment"


# Risk decision factors
RISK_FACTORS = {
    "consumer_impact": {
        "high": ["credit_decisioning", "payment_amount", "settlement_terms"],
        "medium": ["communication_timing", "channel_selection", "contact_frequency"],
        "low": ["reporting_format", "internal_analytics"]
    },
    "regulatory_exposure": {
        "high": ["fdcpa_compliance", "tcpa_compliance", "ecoa_compliance"],
        "medium": ["state_regulations", "bureau_reporting"],
        "low": ["internal_policies"]
    },
    "data_sensitivity": {
        "high": ["pii_direct", "financial_data", "health_information"],
        "medium": ["behavioral_data", "contact_preferences"],
        "low": ["aggregated_metrics", "anonymized_data"]
    }
}

# Approval checklist templates by risk level
APPROVAL_CHECKLISTS = {
    RiskLevel.LOW: [
        "model_documentation_complete",
        "unit_tests_passed",
        "performance_baseline_met",
        "owner_sign_off"
    ],
    RiskLevel.MEDIUM: [
        "model_documentation_complete",
        "unit_tests_passed",
        "integration_tests_passed",
        "performance_baseline_met",
        "fairness_audit_passed",
        "data_scientist_review",
        "owner_sign_off"
    ],
    RiskLevel.HIGH: [
        "model_documentation_complete",
        "unit_tests_passed",
        "integration_tests_passed",
        "stress_tests_passed",
        "performance_baseline_met",
        "fairness_audit_passed",
        "explainability_review",
        "data_scientist_review",
        "ml_engineer_review",
        "compliance_review",
        "legal_review",
        "owner_sign_off"
    ],
    RiskLevel.CRITICAL: [
        "model_documentation_complete",
        "unit_tests_passed",
        "integration_tests_passed",
        "stress_tests_passed",
        "chaos_tests_passed",
        "performance_baseline_met",
        "fairness_audit_passed",
        "explainability_review",
        "bias_mitigation_verified",
        "data_scientist_review",
        "ml_engineer_review",
        "compliance_review",
        "legal_review",
        "risk_manager_review",
        "executive_sponsor_approval",
        "model_validator_sign_off",
        "owner_sign_off"
    ]
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class GovernanceBoardMember:
    """Member of the governance board"""
    member_id: str
    name: str
    email: str
    role: BoardRole
    department: str
    is_active: bool = True
    can_approve: bool = True
    approval_limit_risk_level: RiskLevel = RiskLevel.HIGH
    delegate_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def can_approve_risk_level(self, risk_level: RiskLevel) -> bool:
        """Check if member can approve given risk level"""
        risk_order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        return (
            self.can_approve and
            self.is_active and
            risk_order.index(risk_level) <= risk_order.index(self.approval_limit_risk_level)
        )


@dataclass
class ModelOwnership:
    """Model ownership assignment"""
    model_id: str
    primary_owner_id: str
    secondary_owner_id: Optional[str] = None
    team_id: str = ""
    department: str = ""
    cost_center: str = ""
    assigned_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_review_date: Optional[datetime] = None
    next_review_date: Optional[datetime] = None
    escalation_path: list[str] = field(default_factory=list)

    def is_owner(self, member_id: str) -> bool:
        """Check if member is an owner"""
        return member_id in [self.primary_owner_id, self.secondary_owner_id]


@dataclass
class ModelCharter:
    """Model charter document"""
    charter_id: str
    model_id: str
    model_name: str
    version: str

    # Purpose and scope
    business_objective: str
    use_case_description: str
    target_population: str
    expected_outcomes: list[str]

    # Technical specifications
    model_type: str
    input_features: list[str]
    output_description: str
    performance_thresholds: dict[str, float]

    # Risk and compliance
    risk_level: RiskLevel
    risk_factors: list[str]
    regulatory_requirements: list[str]
    fairness_requirements: list[str]

    # Constraints and limitations
    known_limitations: list[str]
    prohibited_uses: list[str]
    geographic_scope: list[str]

    # Governance
    ownership: ModelOwnership
    retrain_cadence_days: int
    review_frequency_days: int
    approval_requirements: list[str]

    # Metadata
    created_by: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: ModelStatus = ModelStatus.DRAFT
    signatures: dict[str, datetime] = field(default_factory=dict)

    @property
    def is_signed(self) -> bool:
        """Check if charter has required signatures"""
        required_roles = ["primary_owner", "compliance_officer"]
        if self.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            required_roles.extend(["legal_counsel", "executive_sponsor"])
        return all(role in self.signatures for role in required_roles)

    def sign(self, role: str, signer_id: str) -> None:
        """Add signature to charter"""
        self.signatures[role] = datetime.now(timezone.utc)
        self.last_updated = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """Convert charter to dictionary"""
        return {
            "charter_id": self.charter_id,
            "model_id": self.model_id,
            "model_name": self.model_name,
            "version": self.version,
            "business_objective": self.business_objective,
            "use_case_description": self.use_case_description,
            "target_population": self.target_population,
            "expected_outcomes": self.expected_outcomes,
            "model_type": self.model_type,
            "input_features": self.input_features,
            "output_description": self.output_description,
            "performance_thresholds": self.performance_thresholds,
            "risk_level": self.risk_level.value,
            "risk_factors": self.risk_factors,
            "regulatory_requirements": self.regulatory_requirements,
            "fairness_requirements": self.fairness_requirements,
            "known_limitations": self.known_limitations,
            "prohibited_uses": self.prohibited_uses,
            "geographic_scope": self.geographic_scope,
            "ownership": asdict(self.ownership),
            "retrain_cadence_days": self.retrain_cadence_days,
            "review_frequency_days": self.review_frequency_days,
            "approval_requirements": self.approval_requirements,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "status": self.status.value,
            "signatures": {k: v.isoformat() for k, v in self.signatures.items()}
        }


@dataclass
class ApprovalRequest:
    """Approval workflow request"""
    request_id: str
    model_id: str
    charter_id: str
    change_type: ChangeType
    requested_by: str
    request_reason: str

    # Approval tracking
    required_approvers: list[str]
    current_approvals: dict[str, ApprovalStatus] = field(default_factory=dict)
    approval_comments: dict[str, str] = field(default_factory=dict)

    # Checklist
    checklist_items: dict[str, bool] = field(default_factory=dict)

    # Timing
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Status
    status: ApprovalStatus = ApprovalStatus.PENDING
    escalation_count: int = 0

    @property
    def is_complete(self) -> bool:
        """Check if all approvals received"""
        return all(
            status == ApprovalStatus.APPROVED
            for status in self.current_approvals.values()
        )

    @property
    def is_rejected(self) -> bool:
        """Check if any approval was rejected"""
        return any(
            status == ApprovalStatus.REJECTED
            for status in self.current_approvals.values()
        )

    @property
    def is_expired(self) -> bool:
        """Check if approval request has expired"""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def checklist_complete(self) -> bool:
        """Check if all checklist items are complete"""
        return all(self.checklist_items.values())


@dataclass
class LegalReview:
    """Legal sign-off tracking"""
    review_id: str
    model_id: str
    charter_id: str
    review_type: str

    # Review details
    submitted_by: str
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Legal assessment
    reviewer_id: Optional[str] = None
    review_started_at: Optional[datetime] = None
    review_completed_at: Optional[datetime] = None

    # Outcome
    status: ApprovalStatus = ApprovalStatus.PENDING
    legal_opinion: str = ""
    conditions: list[str] = field(default_factory=list)
    required_changes: list[str] = field(default_factory=list)

    # Regulatory mapping
    applicable_regulations: list[str] = field(default_factory=list)
    compliance_attestation: bool = False

    # Sign-off
    signed_by: Optional[str] = None
    signed_at: Optional[datetime] = None
    signature_hash: Optional[str] = None


@dataclass
class MessageRuleLegalReview:
    """Legal review for messaging rules"""
    review_id: str
    rule_id: str
    rule_type: MessageRuleType
    rule_content: str

    # Context
    target_segment: str
    communication_channel: str
    frequency_limit: Optional[str] = None

    # Regulatory requirements
    fdcpa_compliant: Optional[bool] = None
    tcpa_compliant: Optional[bool] = None
    state_requirements: dict[str, bool] = field(default_factory=dict)

    # Review tracking
    submitted_by: str = ""
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    # Outcome
    status: ApprovalStatus = ApprovalStatus.PENDING
    required_modifications: list[str] = field(default_factory=list)
    approved_text: Optional[str] = None
    legal_notes: str = ""


@dataclass
class RetrainSchedule:
    """Retrain cadence management"""
    schedule_id: str
    model_id: str

    # Cadence
    retrain_frequency_days: int
    last_retrain_date: Optional[datetime] = None
    next_retrain_date: Optional[datetime] = None

    # Windows
    preferred_window_start: int = 2  # Hour of day (UTC)
    preferred_window_end: int = 6
    blackout_dates: list[datetime] = field(default_factory=list)

    # Triggers
    auto_retrain_enabled: bool = True
    performance_threshold_trigger: Optional[float] = None
    drift_threshold_trigger: Optional[float] = None
    data_volume_trigger: Optional[int] = None

    # Status
    is_active: bool = True
    consecutive_failures: int = 0
    max_consecutive_failures: int = 3

    def calculate_next_retrain(self) -> datetime:
        """Calculate next retrain date"""
        base_date = self.last_retrain_date or datetime.now(timezone.utc)
        next_date = base_date + timedelta(days=self.retrain_frequency_days)

        # Avoid blackout dates
        while next_date.date() in [d.date() for d in self.blackout_dates]:
            next_date += timedelta(days=1)

        return next_date

    def is_retrain_due(self) -> bool:
        """Check if retrain is due"""
        if not self.is_active:
            return False
        if self.next_retrain_date is None:
            return True
        return datetime.now(timezone.utc) >= self.next_retrain_date


@dataclass
class ChangeRequest:
    """Change management request"""
    request_id: str
    model_id: str
    change_type: ChangeType

    # Change details
    title: str
    description: str
    justification: str
    impact_assessment: str
    rollback_plan: str

    # Risk assessment
    risk_level: RiskLevel
    affected_systems: list[str]
    affected_consumers: str

    # Testing
    test_plan: str
    test_results: dict[str, Any] = field(default_factory=dict)

    # Approval
    requested_by: str = ""
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    approval_request_id: Optional[str] = None

    # Execution
    scheduled_date: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    executed_by: Optional[str] = None
    status: str = "pending"

    # Outcome
    success: Optional[bool] = None
    post_change_validation: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeprecationWorkflow:
    """Model deprecation workflow"""
    workflow_id: str
    model_id: str
    model_name: str

    # Deprecation details
    reason: str
    replacement_model_id: Optional[str] = None
    initiated_by: str = ""
    initiated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Timeline
    deprecation_notice_date: Optional[datetime] = None
    end_of_support_date: Optional[datetime] = None
    retirement_date: Optional[datetime] = None

    # Migration
    migration_plan: str = ""
    affected_consumers: list[str] = field(default_factory=list)
    migration_status: dict[str, str] = field(default_factory=dict)

    # Communication
    notifications_sent: list[dict[str, Any]] = field(default_factory=list)

    # Status
    status: str = "initiated"
    completed_at: Optional[datetime] = None


@dataclass
class AuditEntry:
    """Audit trail entry"""
    entry_id: str
    timestamp: datetime
    event_type: AuditEventType
    model_id: str
    actor_id: str
    actor_role: str

    # Event details
    description: str
    details: dict[str, Any] = field(default_factory=dict)

    # Context
    ip_address: Optional[str] = None
    session_id: Optional[str] = None

    # Integrity
    previous_hash: Optional[str] = None
    entry_hash: Optional[str] = None

    def compute_hash(self, previous_hash: str = "") -> str:
        """Compute entry hash for chain integrity"""
        content = json.dumps({
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "model_id": self.model_id,
            "actor_id": self.actor_id,
            "description": self.description,
            "previous_hash": previous_hash
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class RiskAssessment:
    """Risk assessment for a model"""
    assessment_id: str
    model_id: str
    assessed_by: str
    assessed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Factor scores (1-5)
    consumer_impact_score: int = 1
    regulatory_exposure_score: int = 1
    data_sensitivity_score: int = 1
    model_complexity_score: int = 1
    operational_risk_score: int = 1

    # Calculated risk
    overall_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW

    # Justification
    factor_justifications: dict[str, str] = field(default_factory=dict)
    mitigating_controls: list[str] = field(default_factory=list)
    residual_risks: list[str] = field(default_factory=list)

    def calculate_overall_risk(self) -> RiskLevel:
        """Calculate overall risk level from factor scores"""
        weights = {
            "consumer_impact": 0.25,
            "regulatory_exposure": 0.25,
            "data_sensitivity": 0.20,
            "model_complexity": 0.15,
            "operational_risk": 0.15
        }

        self.overall_score = (
            self.consumer_impact_score * weights["consumer_impact"] +
            self.regulatory_exposure_score * weights["regulatory_exposure"] +
            self.data_sensitivity_score * weights["data_sensitivity"] +
            self.model_complexity_score * weights["model_complexity"] +
            self.operational_risk_score * weights["operational_risk"]
        )

        if self.overall_score >= 4.0:
            self.risk_level = RiskLevel.CRITICAL
        elif self.overall_score >= 3.0:
            self.risk_level = RiskLevel.HIGH
        elif self.overall_score >= 2.0:
            self.risk_level = RiskLevel.MEDIUM
        else:
            self.risk_level = RiskLevel.LOW

        return self.risk_level


@dataclass
class DashboardMetrics:
    """Governance dashboard metrics"""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Model counts
    total_models: int = 0
    models_with_charter: int = 0
    models_with_owner: int = 0
    models_pending_approval: int = 0
    models_pending_legal: int = 0

    # Risk distribution
    low_risk_models: int = 0
    medium_risk_models: int = 0
    high_risk_models: int = 0
    critical_risk_models: int = 0

    # Compliance status
    models_overdue_retrain: int = 0
    models_overdue_review: int = 0
    expired_approvals: int = 0
    pending_legal_reviews: int = 0

    # Audit metrics
    audit_entries_today: int = 0
    compliance_violations_month: int = 0

    @property
    def charter_coverage(self) -> float:
        """Percentage of models with signed charters"""
        return self.models_with_charter / self.total_models if self.total_models > 0 else 0.0

    @property
    def ownership_coverage(self) -> float:
        """Percentage of models with assigned owners"""
        return self.models_with_owner / self.total_models if self.total_models > 0 else 0.0


# =============================================================================
# Decision Risk Matrix
# =============================================================================

class DecisionRiskMatrix:
    """
    Risk assessment matrix for model decisions

    Evaluates models across multiple dimensions to determine
    appropriate governance controls and approval requirements.
    """

    def __init__(self):
        self.risk_factors = RISK_FACTORS
        self.assessments: dict[str, RiskAssessment] = {}

    def assess_model(
        self,
        model_id: str,
        assessed_by: str,
        consumer_impact: str,
        regulatory_exposure: str,
        data_sensitivity: str,
        model_complexity: int = 3,
        operational_risk: int = 3,
        justifications: Optional[dict[str, str]] = None
    ) -> RiskAssessment:
        """
        Assess model risk level

        Args:
            model_id: Unique model identifier
            assessed_by: ID of the assessor
            consumer_impact: Impact category (high/medium/low use case)
            regulatory_exposure: Regulatory category
            data_sensitivity: Data sensitivity category
            model_complexity: Complexity score (1-5)
            operational_risk: Operational risk score (1-5)
            justifications: Justification for each factor

        Returns:
            RiskAssessment with calculated risk level
        """
        assessment = RiskAssessment(
            assessment_id=str(uuid.uuid4()),
            model_id=model_id,
            assessed_by=assessed_by
        )

        # Map categories to scores
        assessment.consumer_impact_score = self._score_category(
            consumer_impact, self.risk_factors["consumer_impact"]
        )
        assessment.regulatory_exposure_score = self._score_category(
            regulatory_exposure, self.risk_factors["regulatory_exposure"]
        )
        assessment.data_sensitivity_score = self._score_category(
            data_sensitivity, self.risk_factors["data_sensitivity"]
        )
        assessment.model_complexity_score = model_complexity
        assessment.operational_risk_score = operational_risk

        if justifications:
            assessment.factor_justifications = justifications

        assessment.calculate_overall_risk()
        self.assessments[model_id] = assessment

        logger.info(
            f"Risk assessment for model {model_id}: "
            f"{assessment.risk_level.value} (score: {assessment.overall_score:.2f})"
        )

        return assessment

    def _score_category(self, item: str, category_map: dict[str, list[str]]) -> int:
        """Convert category item to numeric score"""
        if item in category_map.get("high", []):
            return 5
        elif item in category_map.get("medium", []):
            return 3
        elif item in category_map.get("low", []):
            return 1
        return 3  # Default to medium

    def get_required_controls(self, risk_level: RiskLevel) -> list[str]:
        """Get required controls for a risk level"""
        base_controls = [
            "model_documentation",
            "version_control",
            "basic_monitoring"
        ]

        if risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]:
            base_controls.extend([
                "fairness_audit",
                "explainability_report",
                "drift_monitoring"
            ])

        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            base_controls.extend([
                "legal_review",
                "compliance_attestation",
                "independent_validation",
                "enhanced_monitoring"
            ])

        if risk_level == RiskLevel.CRITICAL:
            base_controls.extend([
                "executive_oversight",
                "board_notification",
                "external_audit",
                "real_time_alerting"
            ])

        return base_controls

    def get_approval_requirements(self, risk_level: RiskLevel) -> dict[str, Any]:
        """Get approval requirements for a risk level"""
        return {
            "checklist": APPROVAL_CHECKLISTS[risk_level],
            "min_approvers": risk_level.required_approvers,
            "review_frequency_days": risk_level.review_frequency_days,
            "legal_review_required": risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL],
            "executive_approval_required": risk_level == RiskLevel.CRITICAL
        }


# =============================================================================
# Charter Template and Generation
# =============================================================================

class ModelCharterGenerator:
    """
    Generates and manages model charters

    Ensures every production model has comprehensive documentation
    of its purpose, constraints, and governance requirements.
    """

    CHARTER_TEMPLATE = """
# Model Charter: {model_name}
## Version: {version}

### 1. Business Objective
{business_objective}

### 2. Use Case Description
{use_case_description}

### 3. Target Population
{target_population}

### 4. Expected Outcomes
{expected_outcomes}

### 5. Technical Specifications
- **Model Type:** {model_type}
- **Input Features:** {input_features}
- **Output:** {output_description}
- **Performance Thresholds:** {performance_thresholds}

### 6. Risk Classification
- **Risk Level:** {risk_level}
- **Risk Factors:** {risk_factors}

### 7. Regulatory Requirements
{regulatory_requirements}

### 8. Fairness Requirements
{fairness_requirements}

### 9. Known Limitations
{known_limitations}

### 10. Prohibited Uses
{prohibited_uses}

### 11. Geographic Scope
{geographic_scope}

### 12. Governance
- **Primary Owner:** {primary_owner}
- **Retrain Cadence:** Every {retrain_cadence_days} days
- **Review Frequency:** Every {review_frequency_days} days

### 13. Approval Requirements
{approval_requirements}

---
**Created:** {created_at}
**Last Updated:** {last_updated}
**Status:** {status}

### Signatures
{signatures}
"""

    def __init__(self):
        self.charters: dict[str, ModelCharter] = {}

    def create_charter(
        self,
        model_id: str,
        model_name: str,
        version: str,
        business_objective: str,
        use_case_description: str,
        target_population: str,
        expected_outcomes: list[str],
        model_type: str,
        input_features: list[str],
        output_description: str,
        performance_thresholds: dict[str, float],
        risk_level: RiskLevel,
        risk_factors: list[str],
        regulatory_requirements: list[str],
        fairness_requirements: list[str],
        known_limitations: list[str],
        prohibited_uses: list[str],
        geographic_scope: list[str],
        ownership: ModelOwnership,
        retrain_cadence_days: int,
        created_by: str
    ) -> ModelCharter:
        """Create a new model charter"""
        charter = ModelCharter(
            charter_id=str(uuid.uuid4()),
            model_id=model_id,
            model_name=model_name,
            version=version,
            business_objective=business_objective,
            use_case_description=use_case_description,
            target_population=target_population,
            expected_outcomes=expected_outcomes,
            model_type=model_type,
            input_features=input_features,
            output_description=output_description,
            performance_thresholds=performance_thresholds,
            risk_level=risk_level,
            risk_factors=risk_factors,
            regulatory_requirements=regulatory_requirements,
            fairness_requirements=fairness_requirements,
            known_limitations=known_limitations,
            prohibited_uses=prohibited_uses,
            geographic_scope=geographic_scope,
            ownership=ownership,
            retrain_cadence_days=retrain_cadence_days,
            review_frequency_days=risk_level.review_frequency_days,
            approval_requirements=APPROVAL_CHECKLISTS[risk_level],
            created_by=created_by
        )

        self.charters[charter.charter_id] = charter
        logger.info(f"Created charter {charter.charter_id} for model {model_id}")

        return charter

    def render_charter(self, charter: ModelCharter) -> str:
        """Render charter to markdown format"""
        signatures_text = "\n".join([
            f"- **{role}:** Signed on {date.strftime('%Y-%m-%d %H:%M UTC')}"
            for role, date in charter.signatures.items()
        ]) if charter.signatures else "No signatures yet"

        return self.CHARTER_TEMPLATE.format(
            model_name=charter.model_name,
            version=charter.version,
            business_objective=charter.business_objective,
            use_case_description=charter.use_case_description,
            target_population=charter.target_population,
            expected_outcomes="\n".join(f"- {o}" for o in charter.expected_outcomes),
            model_type=charter.model_type,
            input_features=", ".join(charter.input_features),
            output_description=charter.output_description,
            performance_thresholds=json.dumps(charter.performance_thresholds, indent=2),
            risk_level=charter.risk_level.value.upper(),
            risk_factors=", ".join(charter.risk_factors),
            regulatory_requirements="\n".join(f"- {r}" for r in charter.regulatory_requirements),
            fairness_requirements="\n".join(f"- {f}" for f in charter.fairness_requirements),
            known_limitations="\n".join(f"- {l}" for l in charter.known_limitations),
            prohibited_uses="\n".join(f"- {p}" for p in charter.prohibited_uses),
            geographic_scope=", ".join(charter.geographic_scope),
            primary_owner=charter.ownership.primary_owner_id,
            retrain_cadence_days=charter.retrain_cadence_days,
            review_frequency_days=charter.review_frequency_days,
            approval_requirements="\n".join(f"- {a}" for a in charter.approval_requirements),
            created_at=charter.created_at.strftime("%Y-%m-%d %H:%M UTC"),
            last_updated=charter.last_updated.strftime("%Y-%m-%d %H:%M UTC"),
            status=charter.status.value,
            signatures=signatures_text
        )

    def validate_charter(self, charter: ModelCharter) -> tuple[bool, list[str]]:
        """Validate charter completeness"""
        issues = []

        if not charter.business_objective:
            issues.append("Missing business objective")
        if not charter.use_case_description:
            issues.append("Missing use case description")
        if not charter.input_features:
            issues.append("No input features specified")
        if not charter.performance_thresholds:
            issues.append("No performance thresholds defined")
        if not charter.regulatory_requirements:
            issues.append("No regulatory requirements specified")
        if not charter.ownership.primary_owner_id:
            issues.append("No primary owner assigned")
        if charter.retrain_cadence_days <= 0:
            issues.append("Invalid retrain cadence")

        return len(issues) == 0, issues


# =============================================================================
# Retrain Cadence Manager
# =============================================================================

class RetrainCadenceManager:
    """
    Manages model retrain scheduling and monitoring

    Ensures models are retrained according to their risk level
    and performance requirements.
    """

    def __init__(self):
        self.schedules: dict[str, RetrainSchedule] = {}
        self.retrain_history: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def create_schedule(
        self,
        model_id: str,
        retrain_frequency_days: int,
        preferred_window_start: int = 2,
        preferred_window_end: int = 6,
        auto_retrain_enabled: bool = True,
        performance_threshold: Optional[float] = None,
        drift_threshold: Optional[float] = None
    ) -> RetrainSchedule:
        """Create retrain schedule for a model"""
        schedule = RetrainSchedule(
            schedule_id=str(uuid.uuid4()),
            model_id=model_id,
            retrain_frequency_days=retrain_frequency_days,
            preferred_window_start=preferred_window_start,
            preferred_window_end=preferred_window_end,
            auto_retrain_enabled=auto_retrain_enabled,
            performance_threshold_trigger=performance_threshold,
            drift_threshold_trigger=drift_threshold,
            next_retrain_date=datetime.now(timezone.utc) + timedelta(days=retrain_frequency_days)
        )

        self.schedules[model_id] = schedule
        logger.info(f"Created retrain schedule for model {model_id}")

        return schedule

    def get_models_due_for_retrain(self) -> list[str]:
        """Get list of models due for retraining"""
        due_models = []
        now = datetime.now(timezone.utc)

        for model_id, schedule in self.schedules.items():
            if schedule.is_active and schedule.is_retrain_due():
                due_models.append(model_id)

        return due_models

    def record_retrain(
        self,
        model_id: str,
        success: bool,
        metrics: dict[str, Any],
        executed_by: str
    ) -> None:
        """Record a retrain event"""
        schedule = self.schedules.get(model_id)
        if not schedule:
            logger.warning(f"No schedule found for model {model_id}")
            return

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": success,
            "metrics": metrics,
            "executed_by": executed_by
        }

        self.retrain_history[model_id].append(record)

        if success:
            schedule.last_retrain_date = datetime.now(timezone.utc)
            schedule.next_retrain_date = schedule.calculate_next_retrain()
            schedule.consecutive_failures = 0
            logger.info(f"Retrain successful for model {model_id}")
        else:
            schedule.consecutive_failures += 1
            if schedule.consecutive_failures >= schedule.max_consecutive_failures:
                schedule.is_active = False
                logger.error(
                    f"Model {model_id} schedule deactivated after "
                    f"{schedule.consecutive_failures} consecutive failures"
                )

    def add_blackout_date(self, model_id: str, date: datetime) -> None:
        """Add blackout date to schedule"""
        if model_id in self.schedules:
            self.schedules[model_id].blackout_dates.append(date)
            # Recalculate next retrain if affected
            schedule = self.schedules[model_id]
            if schedule.next_retrain_date and schedule.next_retrain_date.date() == date.date():
                schedule.next_retrain_date = schedule.calculate_next_retrain()

    def get_schedule_status(self, model_id: str) -> dict[str, Any]:
        """Get current schedule status"""
        schedule = self.schedules.get(model_id)
        if not schedule:
            return {"error": "No schedule found"}

        return {
            "model_id": model_id,
            "is_active": schedule.is_active,
            "retrain_frequency_days": schedule.retrain_frequency_days,
            "last_retrain": schedule.last_retrain_date.isoformat() if schedule.last_retrain_date else None,
            "next_retrain": schedule.next_retrain_date.isoformat() if schedule.next_retrain_date else None,
            "is_due": schedule.is_retrain_due(),
            "consecutive_failures": schedule.consecutive_failures,
            "auto_retrain_enabled": schedule.auto_retrain_enabled
        }


# =============================================================================
# Approval Workflow Engine
# =============================================================================

class ApprovalWorkflowEngine:
    """
    Multi-stage approval workflow management

    Enforces approval requirements based on model risk level
    and change type.
    """

    def __init__(self, board_members: Optional[dict[str, GovernanceBoardMember]] = None):
        self.board_members = board_members or {}
        self.approval_requests: dict[str, ApprovalRequest] = {}
        self.notification_callbacks: list[Callable] = []

    def register_board_member(self, member: GovernanceBoardMember) -> None:
        """Register a governance board member"""
        self.board_members[member.member_id] = member
        logger.info(f"Registered board member: {member.name} ({member.role.value})")

    def create_approval_request(
        self,
        model_id: str,
        charter_id: str,
        change_type: ChangeType,
        requested_by: str,
        request_reason: str,
        risk_level: RiskLevel,
        expiration_days: int = 14
    ) -> ApprovalRequest:
        """Create a new approval request"""
        # Determine required approvers based on risk level
        required_roles = self._get_required_approver_roles(risk_level, change_type)
        required_approvers = [
            member.member_id
            for member in self.board_members.values()
            if member.role in required_roles and member.can_approve_risk_level(risk_level)
        ]

        # Initialize checklist
        checklist = {item: False for item in APPROVAL_CHECKLISTS[risk_level]}

        request = ApprovalRequest(
            request_id=str(uuid.uuid4()),
            model_id=model_id,
            charter_id=charter_id,
            change_type=change_type,
            requested_by=requested_by,
            request_reason=request_reason,
            required_approvers=required_approvers,
            checklist_items=checklist,
            expires_at=datetime.now(timezone.utc) + timedelta(days=expiration_days)
        )

        self.approval_requests[request.request_id] = request
        self._notify_approvers(request)

        logger.info(
            f"Created approval request {request.request_id} for model {model_id} "
            f"with {len(required_approvers)} required approvers"
        )

        return request

    def _get_required_approver_roles(
        self,
        risk_level: RiskLevel,
        change_type: ChangeType
    ) -> list[BoardRole]:
        """Determine required approver roles"""
        roles = [BoardRole.DATA_SCIENTIST]

        if risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]:
            roles.append(BoardRole.ML_ENGINEER)

        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            roles.extend([BoardRole.COMPLIANCE_OFFICER, BoardRole.LEGAL_COUNSEL])

        if risk_level == RiskLevel.CRITICAL:
            roles.extend([BoardRole.RISK_MANAGER, BoardRole.EXECUTIVE_SPONSOR])

        if change_type == ChangeType.NEW_MODEL:
            roles.append(BoardRole.PRODUCT_OWNER)

        return list(set(roles))  # Remove duplicates

    def approve(
        self,
        request_id: str,
        approver_id: str,
        comment: str = ""
    ) -> tuple[bool, str]:
        """Record an approval"""
        request = self.approval_requests.get(request_id)
        if not request:
            return False, "Request not found"

        if request.is_expired:
            request.status = ApprovalStatus.EXPIRED
            return False, "Request has expired"

        if approver_id not in request.required_approvers:
            return False, "Approver not in required approvers list"

        if not request.checklist_complete:
            return False, "Checklist not complete"

        request.current_approvals[approver_id] = ApprovalStatus.APPROVED
        request.approval_comments[approver_id] = comment

        if request.is_complete:
            request.status = ApprovalStatus.APPROVED
            request.completed_at = datetime.now(timezone.utc)
            logger.info(f"Approval request {request_id} fully approved")

        return True, "Approval recorded"

    def reject(
        self,
        request_id: str,
        rejector_id: str,
        reason: str
    ) -> tuple[bool, str]:
        """Record a rejection"""
        request = self.approval_requests.get(request_id)
        if not request:
            return False, "Request not found"

        request.current_approvals[rejector_id] = ApprovalStatus.REJECTED
        request.approval_comments[rejector_id] = reason
        request.status = ApprovalStatus.REJECTED
        request.completed_at = datetime.now(timezone.utc)

        logger.info(f"Approval request {request_id} rejected by {rejector_id}")

        return True, "Rejection recorded"

    def complete_checklist_item(
        self,
        request_id: str,
        item: str,
        completed_by: str
    ) -> bool:
        """Mark a checklist item as complete"""
        request = self.approval_requests.get(request_id)
        if not request:
            return False

        if item in request.checklist_items:
            request.checklist_items[item] = True
            logger.debug(f"Checklist item '{item}' completed for request {request_id}")
            return True

        return False

    def escalate(self, request_id: str, reason: str) -> bool:
        """Escalate an approval request"""
        request = self.approval_requests.get(request_id)
        if not request:
            return False

        request.escalation_count += 1
        request.status = ApprovalStatus.ESCALATED

        # Extend expiration
        if request.expires_at:
            request.expires_at += timedelta(days=7)

        logger.warning(
            f"Approval request {request_id} escalated (count: {request.escalation_count})"
        )

        return True

    def _notify_approvers(self, request: ApprovalRequest) -> None:
        """Notify approvers of pending request"""
        for callback in self.notification_callbacks:
            try:
                callback(request, "new_request")
            except Exception as e:
                logger.error(f"Notification callback failed: {e}")

    def get_pending_approvals(self, approver_id: str) -> list[ApprovalRequest]:
        """Get pending approvals for an approver"""
        return [
            request for request in self.approval_requests.values()
            if (
                approver_id in request.required_approvers and
                approver_id not in request.current_approvals and
                request.status == ApprovalStatus.PENDING
            )
        ]

    def get_approval_status(self, request_id: str) -> dict[str, Any]:
        """Get detailed approval status"""
        request = self.approval_requests.get(request_id)
        if not request:
            return {"error": "Request not found"}

        return {
            "request_id": request.request_id,
            "model_id": request.model_id,
            "status": request.status.value,
            "change_type": request.change_type.value,
            "requested_by": request.requested_by,
            "created_at": request.created_at.isoformat(),
            "expires_at": request.expires_at.isoformat() if request.expires_at else None,
            "approvals": {
                k: v.value for k, v in request.current_approvals.items()
            },
            "pending_approvers": [
                a for a in request.required_approvers
                if a not in request.current_approvals
            ],
            "checklist_complete": request.checklist_complete,
            "checklist_items": request.checklist_items,
            "is_complete": request.is_complete,
            "escalation_count": request.escalation_count
        }


# =============================================================================
# Legal Sign-Off Tracker
# =============================================================================

class LegalSignOffTracker:
    """
    Tracks legal reviews and sign-offs for models and messaging rules

    Ensures compliance with regulatory requirements and maintains
    audit trail for legal approvals.
    """

    def __init__(self):
        self.legal_reviews: dict[str, LegalReview] = {}
        self.message_rule_reviews: dict[str, MessageRuleLegalReview] = {}
        self.legal_counsel: dict[str, GovernanceBoardMember] = {}

    def register_legal_counsel(self, member: GovernanceBoardMember) -> None:
        """Register a legal counsel member"""
        if member.role == BoardRole.LEGAL_COUNSEL:
            self.legal_counsel[member.member_id] = member
            logger.info(f"Registered legal counsel: {member.name}")

    def submit_for_legal_review(
        self,
        model_id: str,
        charter_id: str,
        review_type: str,
        submitted_by: str,
        applicable_regulations: list[str]
    ) -> LegalReview:
        """Submit model for legal review"""
        review = LegalReview(
            review_id=str(uuid.uuid4()),
            model_id=model_id,
            charter_id=charter_id,
            review_type=review_type,
            submitted_by=submitted_by,
            applicable_regulations=applicable_regulations
        )

        self.legal_reviews[review.review_id] = review
        logger.info(f"Submitted model {model_id} for legal review: {review.review_id}")

        return review

    def submit_message_rule_review(
        self,
        rule_id: str,
        rule_type: MessageRuleType,
        rule_content: str,
        target_segment: str,
        communication_channel: str,
        submitted_by: str,
        frequency_limit: Optional[str] = None
    ) -> MessageRuleLegalReview:
        """Submit messaging rule for legal review"""
        review = MessageRuleLegalReview(
            review_id=str(uuid.uuid4()),
            rule_id=rule_id,
            rule_type=rule_type,
            rule_content=rule_content,
            target_segment=target_segment,
            communication_channel=communication_channel,
            frequency_limit=frequency_limit,
            submitted_by=submitted_by
        )

        self.message_rule_reviews[review.review_id] = review
        logger.info(f"Submitted message rule {rule_id} for legal review: {review.review_id}")

        return review

    def assign_reviewer(
        self,
        review_id: str,
        reviewer_id: str,
        is_message_rule: bool = False
    ) -> bool:
        """Assign legal reviewer"""
        if reviewer_id not in self.legal_counsel:
            logger.error(f"Reviewer {reviewer_id} is not registered legal counsel")
            return False

        if is_message_rule:
            review = self.message_rule_reviews.get(review_id)
        else:
            review = self.legal_reviews.get(review_id)

        if not review:
            return False

        review.reviewer_id = reviewer_id
        review.review_started_at = datetime.now(timezone.utc)

        return True

    def complete_legal_review(
        self,
        review_id: str,
        approved: bool,
        legal_opinion: str,
        conditions: Optional[list[str]] = None,
        required_changes: Optional[list[str]] = None
    ) -> bool:
        """Complete legal review with sign-off"""
        review = self.legal_reviews.get(review_id)
        if not review or not review.reviewer_id:
            return False

        review.review_completed_at = datetime.now(timezone.utc)
        review.legal_opinion = legal_opinion
        review.conditions = conditions or []
        review.required_changes = required_changes or []

        if approved and not required_changes:
            review.status = ApprovalStatus.APPROVED
            review.compliance_attestation = True
            review.signed_by = review.reviewer_id
            review.signed_at = datetime.now(timezone.utc)

            # Generate signature hash
            signature_content = json.dumps({
                "review_id": review.review_id,
                "model_id": review.model_id,
                "signed_by": review.signed_by,
                "signed_at": review.signed_at.isoformat(),
                "legal_opinion": legal_opinion
            }, sort_keys=True)
            review.signature_hash = hashlib.sha256(signature_content.encode()).hexdigest()

            logger.info(f"Legal review {review_id} approved and signed")
        elif conditions:
            review.status = ApprovalStatus.CONDITIONAL
        else:
            review.status = ApprovalStatus.REJECTED

        return True

    def complete_message_rule_review(
        self,
        review_id: str,
        fdcpa_compliant: bool,
        tcpa_compliant: bool,
        state_requirements: dict[str, bool],
        approved: bool,
        approved_text: Optional[str] = None,
        required_modifications: Optional[list[str]] = None,
        legal_notes: str = ""
    ) -> bool:
        """Complete message rule legal review"""
        review = self.message_rule_reviews.get(review_id)
        if not review or not review.reviewed_by:
            return False

        review.reviewed_at = datetime.now(timezone.utc)
        review.fdcpa_compliant = fdcpa_compliant
        review.tcpa_compliant = tcpa_compliant
        review.state_requirements = state_requirements
        review.legal_notes = legal_notes

        if approved:
            review.status = ApprovalStatus.APPROVED
            review.approved_text = approved_text or review.rule_content
        else:
            review.status = ApprovalStatus.REJECTED
            review.required_modifications = required_modifications or []

        logger.info(f"Message rule review {review_id} completed: {review.status.value}")

        return True

    def get_pending_reviews(self, reviewer_id: Optional[str] = None) -> dict[str, list]:
        """Get pending legal reviews"""
        model_reviews = [
            r for r in self.legal_reviews.values()
            if r.status == ApprovalStatus.PENDING and
            (reviewer_id is None or r.reviewer_id == reviewer_id)
        ]

        message_reviews = [
            r for r in self.message_rule_reviews.values()
            if r.status == ApprovalStatus.PENDING and
            (reviewer_id is None or r.reviewed_by == reviewer_id)
        ]

        return {
            "model_reviews": model_reviews,
            "message_rule_reviews": message_reviews
        }

    def verify_signature(self, review_id: str) -> bool:
        """Verify legal review signature integrity"""
        review = self.legal_reviews.get(review_id)
        if not review or not review.signature_hash:
            return False

        signature_content = json.dumps({
            "review_id": review.review_id,
            "model_id": review.model_id,
            "signed_by": review.signed_by,
            "signed_at": review.signed_at.isoformat() if review.signed_at else None,
            "legal_opinion": review.legal_opinion
        }, sort_keys=True)

        computed_hash = hashlib.sha256(signature_content.encode()).hexdigest()
        return computed_hash == review.signature_hash


# =============================================================================
# Compliance Audit Trail
# =============================================================================

class ComplianceAuditTrail:
    """
    Maintains immutable audit trail for all governance activities

    Uses hash chaining to ensure integrity and non-repudiation
    of audit records.
    """

    def __init__(self):
        self.entries: list[AuditEntry] = []
        self.entries_by_model: dict[str, list[AuditEntry]] = defaultdict(list)
        self.last_hash: str = "genesis"

    def log(
        self,
        event_type: AuditEventType,
        model_id: str,
        actor_id: str,
        actor_role: str,
        description: str,
        details: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> AuditEntry:
        """Log an audit event"""
        entry = AuditEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            model_id=model_id,
            actor_id=actor_id,
            actor_role=actor_role,
            description=description,
            details=details or {},
            ip_address=ip_address,
            session_id=session_id,
            previous_hash=self.last_hash
        )

        entry.entry_hash = entry.compute_hash(self.last_hash)
        self.last_hash = entry.entry_hash

        self.entries.append(entry)
        self.entries_by_model[model_id].append(entry)

        logger.debug(f"Audit log: {event_type.value} for model {model_id}")

        return entry

    def get_model_history(
        self,
        model_id: str,
        event_types: Optional[list[AuditEventType]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> list[AuditEntry]:
        """Get audit history for a model"""
        entries = self.entries_by_model.get(model_id, [])

        if event_types:
            entries = [e for e in entries if e.event_type in event_types]

        if start_date:
            entries = [e for e in entries if e.timestamp >= start_date]

        if end_date:
            entries = [e for e in entries if e.timestamp <= end_date]

        return entries

    def verify_chain_integrity(self) -> tuple[bool, Optional[str]]:
        """Verify the integrity of the audit chain"""
        if not self.entries:
            return True, None

        expected_previous = "genesis"

        for entry in self.entries:
            if entry.previous_hash != expected_previous:
                return False, f"Chain broken at entry {entry.entry_id}"

            computed_hash = entry.compute_hash(expected_previous)
            if computed_hash != entry.entry_hash:
                return False, f"Hash mismatch at entry {entry.entry_id}"

            expected_previous = entry.entry_hash

        return True, None

    def export_audit_report(
        self,
        model_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> dict[str, Any]:
        """Export audit report"""
        entries = self.entries

        if model_id:
            entries = self.entries_by_model.get(model_id, [])

        if start_date:
            entries = [e for e in entries if e.timestamp >= start_date]

        if end_date:
            entries = [e for e in entries if e.timestamp <= end_date]

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_entries": len(entries),
            "chain_verified": self.verify_chain_integrity()[0],
            "entries": [
                {
                    "entry_id": e.entry_id,
                    "timestamp": e.timestamp.isoformat(),
                    "event_type": e.event_type.value,
                    "model_id": e.model_id,
                    "actor_id": e.actor_id,
                    "description": e.description,
                    "entry_hash": e.entry_hash
                }
                for e in entries
            ]
        }


# =============================================================================
# Change Management Process
# =============================================================================

class ChangeManagementProcess:
    """
    Manages model change requests and execution

    Ensures all changes follow proper approval workflow
    and maintain audit trail.
    """

    def __init__(
        self,
        approval_engine: ApprovalWorkflowEngine,
        audit_trail: ComplianceAuditTrail
    ):
        self.approval_engine = approval_engine
        self.audit_trail = audit_trail
        self.change_requests: dict[str, ChangeRequest] = {}

    def create_change_request(
        self,
        model_id: str,
        change_type: ChangeType,
        title: str,
        description: str,
        justification: str,
        impact_assessment: str,
        rollback_plan: str,
        risk_level: RiskLevel,
        affected_systems: list[str],
        affected_consumers: str,
        test_plan: str,
        requested_by: str
    ) -> ChangeRequest:
        """Create a new change request"""
        request = ChangeRequest(
            request_id=str(uuid.uuid4()),
            model_id=model_id,
            change_type=change_type,
            title=title,
            description=description,
            justification=justification,
            impact_assessment=impact_assessment,
            rollback_plan=rollback_plan,
            risk_level=risk_level,
            affected_systems=affected_systems,
            affected_consumers=affected_consumers,
            test_plan=test_plan,
            requested_by=requested_by
        )

        self.change_requests[request.request_id] = request

        self.audit_trail.log(
            event_type=AuditEventType.APPROVAL_REQUESTED,
            model_id=model_id,
            actor_id=requested_by,
            actor_role="requester",
            description=f"Change request created: {title}",
            details={"change_type": change_type.value, "risk_level": risk_level.value}
        )

        logger.info(f"Created change request {request.request_id} for model {model_id}")

        return request

    def submit_for_approval(
        self,
        request_id: str,
        charter_id: str
    ) -> Optional[ApprovalRequest]:
        """Submit change request for approval"""
        change_request = self.change_requests.get(request_id)
        if not change_request:
            return None

        approval_request = self.approval_engine.create_approval_request(
            model_id=change_request.model_id,
            charter_id=charter_id,
            change_type=change_request.change_type,
            requested_by=change_request.requested_by,
            request_reason=change_request.justification,
            risk_level=change_request.risk_level
        )

        change_request.approval_request_id = approval_request.request_id
        change_request.status = "pending_approval"

        return approval_request

    def record_test_results(
        self,
        request_id: str,
        test_results: dict[str, Any]
    ) -> bool:
        """Record test results for change request"""
        change_request = self.change_requests.get(request_id)
        if not change_request:
            return False

        change_request.test_results = test_results
        return True

    def execute_change(
        self,
        request_id: str,
        executed_by: str
    ) -> tuple[bool, str]:
        """Execute approved change"""
        change_request = self.change_requests.get(request_id)
        if not change_request:
            return False, "Change request not found"

        # Verify approval
        if change_request.approval_request_id:
            approval = self.approval_engine.approval_requests.get(
                change_request.approval_request_id
            )
            if not approval or approval.status != ApprovalStatus.APPROVED:
                return False, "Change not approved"

        change_request.executed_at = datetime.now(timezone.utc)
        change_request.executed_by = executed_by
        change_request.status = "executed"

        self.audit_trail.log(
            event_type=AuditEventType.DEPLOYED,
            model_id=change_request.model_id,
            actor_id=executed_by,
            actor_role="executor",
            description=f"Change executed: {change_request.title}",
            details={"change_type": change_request.change_type.value}
        )

        return True, "Change executed successfully"

    def record_validation(
        self,
        request_id: str,
        validation_results: dict[str, Any],
        success: bool
    ) -> bool:
        """Record post-change validation"""
        change_request = self.change_requests.get(request_id)
        if not change_request:
            return False

        change_request.post_change_validation = validation_results
        change_request.success = success
        change_request.status = "completed" if success else "failed"

        return True


# =============================================================================
# Model Deprecation Workflow
# =============================================================================

class ModelDeprecationWorkflow:
    """
    Manages model deprecation and retirement process

    Ensures orderly phase-out of models with proper notification
    and migration support.
    """

    def __init__(self, audit_trail: ComplianceAuditTrail):
        self.audit_trail = audit_trail
        self.workflows: dict[str, DeprecationWorkflow] = {}

    def initiate_deprecation(
        self,
        model_id: str,
        model_name: str,
        reason: str,
        initiated_by: str,
        replacement_model_id: Optional[str] = None,
        deprecation_notice_days: int = 30,
        end_of_support_days: int = 90,
        retirement_days: int = 180
    ) -> DeprecationWorkflow:
        """Initiate model deprecation"""
        now = datetime.now(timezone.utc)

        workflow = DeprecationWorkflow(
            workflow_id=str(uuid.uuid4()),
            model_id=model_id,
            model_name=model_name,
            reason=reason,
            replacement_model_id=replacement_model_id,
            initiated_by=initiated_by,
            deprecation_notice_date=now + timedelta(days=deprecation_notice_days),
            end_of_support_date=now + timedelta(days=end_of_support_days),
            retirement_date=now + timedelta(days=retirement_days)
        )

        self.workflows[model_id] = workflow

        self.audit_trail.log(
            event_type=AuditEventType.DEPRECATION_INITIATED,
            model_id=model_id,
            actor_id=initiated_by,
            actor_role="owner",
            description=f"Deprecation initiated for model {model_name}",
            details={
                "reason": reason,
                "replacement_model_id": replacement_model_id,
                "retirement_date": workflow.retirement_date.isoformat()
            }
        )

        logger.info(f"Initiated deprecation workflow for model {model_id}")

        return workflow

    def set_migration_plan(
        self,
        model_id: str,
        migration_plan: str,
        affected_consumers: list[str]
    ) -> bool:
        """Set migration plan for deprecated model"""
        workflow = self.workflows.get(model_id)
        if not workflow:
            return False

        workflow.migration_plan = migration_plan
        workflow.affected_consumers = affected_consumers
        workflow.migration_status = {consumer: "pending" for consumer in affected_consumers}

        return True

    def update_migration_status(
        self,
        model_id: str,
        consumer: str,
        status: str
    ) -> bool:
        """Update migration status for a consumer"""
        workflow = self.workflows.get(model_id)
        if not workflow or consumer not in workflow.migration_status:
            return False

        workflow.migration_status[consumer] = status
        return True

    def send_notification(
        self,
        model_id: str,
        notification_type: str,
        recipients: list[str],
        message: str
    ) -> bool:
        """Record notification sent"""
        workflow = self.workflows.get(model_id)
        if not workflow:
            return False

        notification = {
            "type": notification_type,
            "recipients": recipients,
            "message": message,
            "sent_at": datetime.now(timezone.utc).isoformat()
        }

        workflow.notifications_sent.append(notification)
        return True

    def complete_deprecation(
        self,
        model_id: str,
        completed_by: str
    ) -> tuple[bool, str]:
        """Complete deprecation and retire model"""
        workflow = self.workflows.get(model_id)
        if not workflow:
            return False, "Workflow not found"

        # Check if all consumers migrated
        pending_migrations = [
            c for c, s in workflow.migration_status.items()
            if s != "completed"
        ]

        if pending_migrations:
            return False, f"Pending migrations: {pending_migrations}"

        workflow.status = "completed"
        workflow.completed_at = datetime.now(timezone.utc)

        self.audit_trail.log(
            event_type=AuditEventType.MODEL_RETIRED,
            model_id=model_id,
            actor_id=completed_by,
            actor_role="owner",
            description=f"Model {workflow.model_name} retired",
            details={"replacement_model_id": workflow.replacement_model_id}
        )

        return True, "Model retired successfully"

    def get_deprecation_status(self, model_id: str) -> dict[str, Any]:
        """Get deprecation workflow status"""
        workflow = self.workflows.get(model_id)
        if not workflow:
            return {"error": "No deprecation workflow found"}

        return {
            "workflow_id": workflow.workflow_id,
            "model_id": workflow.model_id,
            "model_name": workflow.model_name,
            "status": workflow.status,
            "reason": workflow.reason,
            "replacement_model_id": workflow.replacement_model_id,
            "deprecation_notice_date": workflow.deprecation_notice_date.isoformat() if workflow.deprecation_notice_date else None,
            "end_of_support_date": workflow.end_of_support_date.isoformat() if workflow.end_of_support_date else None,
            "retirement_date": workflow.retirement_date.isoformat() if workflow.retirement_date else None,
            "migration_status": workflow.migration_status,
            "notifications_count": len(workflow.notifications_sent)
        }


# =============================================================================
# Governance Dashboard
# =============================================================================

class GovernanceDashboard:
    """
    Dashboard for governance metrics and status

    Provides visibility into model governance compliance
    and pending actions.
    """

    def __init__(
        self,
        charter_generator: ModelCharterGenerator,
        risk_matrix: DecisionRiskMatrix,
        retrain_manager: RetrainCadenceManager,
        approval_engine: ApprovalWorkflowEngine,
        legal_tracker: LegalSignOffTracker,
        audit_trail: ComplianceAuditTrail,
        deprecation_workflow: ModelDeprecationWorkflow
    ):
        self.charter_generator = charter_generator
        self.risk_matrix = risk_matrix
        self.retrain_manager = retrain_manager
        self.approval_engine = approval_engine
        self.legal_tracker = legal_tracker
        self.audit_trail = audit_trail
        self.deprecation_workflow = deprecation_workflow

    def get_metrics(self) -> DashboardMetrics:
        """Generate dashboard metrics"""
        metrics = DashboardMetrics()

        # Charter metrics
        charters = self.charter_generator.charters
        metrics.total_models = len(charters)
        metrics.models_with_charter = sum(1 for c in charters.values() if c.is_signed)
        metrics.models_with_owner = sum(
            1 for c in charters.values()
            if c.ownership.primary_owner_id
        )

        # Risk distribution
        for assessment in self.risk_matrix.assessments.values():
            if assessment.risk_level == RiskLevel.LOW:
                metrics.low_risk_models += 1
            elif assessment.risk_level == RiskLevel.MEDIUM:
                metrics.medium_risk_models += 1
            elif assessment.risk_level == RiskLevel.HIGH:
                metrics.high_risk_models += 1
            elif assessment.risk_level == RiskLevel.CRITICAL:
                metrics.critical_risk_models += 1

        # Approval metrics
        metrics.models_pending_approval = sum(
            1 for r in self.approval_engine.approval_requests.values()
            if r.status == ApprovalStatus.PENDING
        )

        # Legal metrics
        pending = self.legal_tracker.get_pending_reviews()
        metrics.pending_legal_reviews = (
            len(pending["model_reviews"]) +
            len(pending["message_rule_reviews"])
        )

        # Retrain metrics
        metrics.models_overdue_retrain = len(
            self.retrain_manager.get_models_due_for_retrain()
        )

        # Audit metrics
        today = datetime.now(timezone.utc).date()
        metrics.audit_entries_today = sum(
            1 for e in self.audit_trail.entries
            if e.timestamp.date() == today
        )

        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0)
        metrics.compliance_violations_month = sum(
            1 for e in self.audit_trail.entries
            if e.event_type == AuditEventType.COMPLIANCE_VIOLATION and
            e.timestamp >= month_start
        )

        return metrics

    def get_compliance_summary(self) -> dict[str, Any]:
        """Get compliance status summary"""
        metrics = self.get_metrics()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_health": self._calculate_health_score(metrics),
            "charter_coverage": f"{metrics.charter_coverage * 100:.1f}%",
            "ownership_coverage": f"{metrics.ownership_coverage * 100:.1f}%",
            "risk_distribution": {
                "low": metrics.low_risk_models,
                "medium": metrics.medium_risk_models,
                "high": metrics.high_risk_models,
                "critical": metrics.critical_risk_models
            },
            "pending_actions": {
                "approvals": metrics.models_pending_approval,
                "legal_reviews": metrics.pending_legal_reviews,
                "overdue_retrains": metrics.models_overdue_retrain
            },
            "audit_integrity": self.audit_trail.verify_chain_integrity()[0]
        }

    def _calculate_health_score(self, metrics: DashboardMetrics) -> str:
        """Calculate overall governance health score"""
        score = 100

        # Deductions
        if metrics.charter_coverage < 1.0:
            score -= 20 * (1 - metrics.charter_coverage)
        if metrics.ownership_coverage < 1.0:
            score -= 15 * (1 - metrics.ownership_coverage)
        if metrics.models_pending_approval > 5:
            score -= 10
        if metrics.pending_legal_reviews > 5:
            score -= 10
        if metrics.models_overdue_retrain > 0:
            score -= 5 * min(metrics.models_overdue_retrain, 5)
        if metrics.compliance_violations_month > 0:
            score -= 10 * min(metrics.compliance_violations_month, 3)

        if score >= 90:
            return "excellent"
        elif score >= 75:
            return "good"
        elif score >= 60:
            return "fair"
        elif score >= 40:
            return "poor"
        else:
            return "critical"

    def get_action_items(self, assignee_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Get prioritized action items"""
        items = []

        # Pending approvals
        if assignee_id:
            pending = self.approval_engine.get_pending_approvals(assignee_id)
        else:
            pending = [
                r for r in self.approval_engine.approval_requests.values()
                if r.status == ApprovalStatus.PENDING
            ]

        for request in pending:
            items.append({
                "type": "approval_required",
                "priority": "high" if request.escalation_count > 0 else "medium",
                "model_id": request.model_id,
                "request_id": request.request_id,
                "description": f"Approval needed for {request.change_type.value}",
                "expires_at": request.expires_at.isoformat() if request.expires_at else None
            })

        # Overdue retrains
        for model_id in self.retrain_manager.get_models_due_for_retrain():
            schedule = self.retrain_manager.schedules[model_id]
            items.append({
                "type": "retrain_overdue",
                "priority": "high",
                "model_id": model_id,
                "description": f"Model overdue for retraining",
                "last_retrain": schedule.last_retrain_date.isoformat() if schedule.last_retrain_date else None
            })

        # Pending legal reviews
        pending_legal = self.legal_tracker.get_pending_reviews()
        for review in pending_legal["model_reviews"]:
            items.append({
                "type": "legal_review_pending",
                "priority": "medium",
                "model_id": review.model_id,
                "review_id": review.review_id,
                "description": f"Legal review pending for model"
            })

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        items.sort(key=lambda x: priority_order.get(x["priority"], 99))

        return items

    def generate_report(
        self,
        report_type: str = "summary",
        model_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Generate governance report"""
        if report_type == "summary":
            return self.get_compliance_summary()

        elif report_type == "model" and model_id:
            return self._generate_model_report(model_id)

        elif report_type == "audit":
            return self.audit_trail.export_audit_report(model_id=model_id)

        else:
            return {"error": "Invalid report type"}

    def _generate_model_report(self, model_id: str) -> dict[str, Any]:
        """Generate detailed report for a model"""
        charter = None
        for c in self.charter_generator.charters.values():
            if c.model_id == model_id:
                charter = c
                break

        assessment = self.risk_matrix.assessments.get(model_id)
        schedule = self.retrain_manager.schedules.get(model_id)
        history = self.audit_trail.get_model_history(model_id)

        return {
            "model_id": model_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "charter": charter.to_dict() if charter else None,
            "risk_assessment": {
                "risk_level": assessment.risk_level.value if assessment else None,
                "overall_score": assessment.overall_score if assessment else None
            } if assessment else None,
            "retrain_status": self.retrain_manager.get_schedule_status(model_id),
            "audit_history_count": len(history),
            "recent_events": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "event_type": e.event_type.value,
                    "description": e.description
                }
                for e in history[-10:]  # Last 10 events
            ]
        }


# =============================================================================
# Main Governance Framework
# =============================================================================

class GovernanceFramework:
    """
    Main governance framework orchestrating all components

    Provides unified interface for model governance including:
    - Charter management
    - Risk assessment
    - Approval workflows
    - Legal sign-off
    - Retrain scheduling
    - Audit trail
    - Deprecation management

    Usage:
        framework = GovernanceFramework()

        # Register board members
        framework.register_board_member(member)

        # Create model charter
        charter = framework.create_model_charter(...)

        # Assess risk
        assessment = framework.assess_model_risk(...)

        # Submit for approval
        approval = framework.submit_for_approval(...)

        # Check dashboard
        metrics = framework.get_dashboard_metrics()
    """

    def __init__(self):
        # Initialize components
        self.charter_generator = ModelCharterGenerator()
        self.risk_matrix = DecisionRiskMatrix()
        self.retrain_manager = RetrainCadenceManager()
        self.approval_engine = ApprovalWorkflowEngine()
        self.legal_tracker = LegalSignOffTracker()
        self.audit_trail = ComplianceAuditTrail()
        self.deprecation_workflow = ModelDeprecationWorkflow(self.audit_trail)
        self.change_management = ChangeManagementProcess(
            self.approval_engine,
            self.audit_trail
        )

        # Initialize dashboard
        self.dashboard = GovernanceDashboard(
            self.charter_generator,
            self.risk_matrix,
            self.retrain_manager,
            self.approval_engine,
            self.legal_tracker,
            self.audit_trail,
            self.deprecation_workflow
        )

        # Track registered models
        self.registered_models: dict[str, dict[str, Any]] = {}

        logger.info("GovernanceFramework initialized")

    def register_board_member(self, member: GovernanceBoardMember) -> None:
        """Register a governance board member"""
        self.approval_engine.register_board_member(member)
        if member.role == BoardRole.LEGAL_COUNSEL:
            self.legal_tracker.register_legal_counsel(member)

    def create_model_charter(
        self,
        model_id: str,
        model_name: str,
        version: str,
        business_objective: str,
        use_case_description: str,
        target_population: str,
        expected_outcomes: list[str],
        model_type: str,
        input_features: list[str],
        output_description: str,
        performance_thresholds: dict[str, float],
        regulatory_requirements: list[str],
        fairness_requirements: list[str],
        known_limitations: list[str],
        prohibited_uses: list[str],
        geographic_scope: list[str],
        primary_owner_id: str,
        created_by: str,
        team_id: str = "",
        secondary_owner_id: Optional[str] = None
    ) -> ModelCharter:
        """Create a new model charter with ownership"""
        # Create ownership
        ownership = ModelOwnership(
            model_id=model_id,
            primary_owner_id=primary_owner_id,
            secondary_owner_id=secondary_owner_id,
            team_id=team_id
        )

        # Assess risk first
        assessment = self.risk_matrix.assess_model(
            model_id=model_id,
            assessed_by=created_by,
            consumer_impact="credit_decisioning",  # Default high impact
            regulatory_exposure="fdcpa_compliance",
            data_sensitivity="pii_direct"
        )

        # Create charter
        charter = self.charter_generator.create_charter(
            model_id=model_id,
            model_name=model_name,
            version=version,
            business_objective=business_objective,
            use_case_description=use_case_description,
            target_population=target_population,
            expected_outcomes=expected_outcomes,
            model_type=model_type,
            input_features=input_features,
            output_description=output_description,
            performance_thresholds=performance_thresholds,
            risk_level=assessment.risk_level,
            risk_factors=assessment.residual_risks,
            regulatory_requirements=regulatory_requirements,
            fairness_requirements=fairness_requirements,
            known_limitations=known_limitations,
            prohibited_uses=prohibited_uses,
            geographic_scope=geographic_scope,
            ownership=ownership,
            retrain_cadence_days=assessment.risk_level.review_frequency_days,
            created_by=created_by
        )

        # Create retrain schedule
        self.retrain_manager.create_schedule(
            model_id=model_id,
            retrain_frequency_days=charter.retrain_cadence_days
        )

        # Log audit event
        self.audit_trail.log(
            event_type=AuditEventType.CHARTER_CREATED,
            model_id=model_id,
            actor_id=created_by,
            actor_role="creator",
            description=f"Charter created for model {model_name}",
            details={"charter_id": charter.charter_id, "risk_level": assessment.risk_level.value}
        )

        # Register model
        self.registered_models[model_id] = {
            "charter_id": charter.charter_id,
            "assessment_id": assessment.assessment_id,
            "status": ModelStatus.DRAFT
        }

        return charter

    def assess_model_risk(
        self,
        model_id: str,
        assessed_by: str,
        consumer_impact: str,
        regulatory_exposure: str,
        data_sensitivity: str,
        model_complexity: int = 3,
        operational_risk: int = 3,
        justifications: Optional[dict[str, str]] = None
    ) -> RiskAssessment:
        """Assess model risk level"""
        assessment = self.risk_matrix.assess_model(
            model_id=model_id,
            assessed_by=assessed_by,
            consumer_impact=consumer_impact,
            regulatory_exposure=regulatory_exposure,
            data_sensitivity=data_sensitivity,
            model_complexity=model_complexity,
            operational_risk=operational_risk,
            justifications=justifications
        )

        self.audit_trail.log(
            event_type=AuditEventType.RISK_LEVEL_CHANGED,
            model_id=model_id,
            actor_id=assessed_by,
            actor_role="assessor",
            description=f"Risk assessed as {assessment.risk_level.value}",
            details={"overall_score": assessment.overall_score}
        )

        return assessment

    def submit_for_approval(
        self,
        model_id: str,
        charter_id: str,
        change_type: ChangeType,
        requested_by: str,
        request_reason: str
    ) -> ApprovalRequest:
        """Submit model for approval"""
        # Get risk level from charter
        charter = self.charter_generator.charters.get(charter_id)
        risk_level = charter.risk_level if charter else RiskLevel.MEDIUM

        return self.approval_engine.create_approval_request(
            model_id=model_id,
            charter_id=charter_id,
            change_type=change_type,
            requested_by=requested_by,
            request_reason=request_reason,
            risk_level=risk_level
        )

    def submit_for_legal_review(
        self,
        model_id: str,
        charter_id: str,
        review_type: str,
        submitted_by: str,
        applicable_regulations: list[str]
    ) -> LegalReview:
        """Submit model for legal review"""
        review = self.legal_tracker.submit_for_legal_review(
            model_id=model_id,
            charter_id=charter_id,
            review_type=review_type,
            submitted_by=submitted_by,
            applicable_regulations=applicable_regulations
        )

        self.audit_trail.log(
            event_type=AuditEventType.LEGAL_REVIEW_REQUESTED,
            model_id=model_id,
            actor_id=submitted_by,
            actor_role="submitter",
            description=f"Submitted for legal review: {review_type}",
            details={"review_id": review.review_id}
        )

        return review

    def submit_message_rule_for_review(
        self,
        rule_id: str,
        rule_type: MessageRuleType,
        rule_content: str,
        target_segment: str,
        communication_channel: str,
        submitted_by: str,
        frequency_limit: Optional[str] = None
    ) -> MessageRuleLegalReview:
        """Submit messaging rule for legal review"""
        return self.legal_tracker.submit_message_rule_review(
            rule_id=rule_id,
            rule_type=rule_type,
            rule_content=rule_content,
            target_segment=target_segment,
            communication_channel=communication_channel,
            submitted_by=submitted_by,
            frequency_limit=frequency_limit
        )

    def sign_charter(
        self,
        charter_id: str,
        role: str,
        signer_id: str
    ) -> bool:
        """Sign a model charter"""
        charter = self.charter_generator.charters.get(charter_id)
        if not charter:
            return False

        charter.sign(role, signer_id)

        self.audit_trail.log(
            event_type=AuditEventType.APPROVAL_GRANTED,
            model_id=charter.model_id,
            actor_id=signer_id,
            actor_role=role,
            description=f"Charter signed by {role}",
            details={"charter_id": charter_id}
        )

        if charter.is_signed:
            charter.status = ModelStatus.APPROVED

        return True

    def initiate_deprecation(
        self,
        model_id: str,
        model_name: str,
        reason: str,
        initiated_by: str,
        replacement_model_id: Optional[str] = None
    ) -> DeprecationWorkflow:
        """Initiate model deprecation"""
        return self.deprecation_workflow.initiate_deprecation(
            model_id=model_id,
            model_name=model_name,
            reason=reason,
            initiated_by=initiated_by,
            replacement_model_id=replacement_model_id
        )

    def create_change_request(
        self,
        model_id: str,
        change_type: ChangeType,
        title: str,
        description: str,
        justification: str,
        impact_assessment: str,
        rollback_plan: str,
        affected_systems: list[str],
        affected_consumers: str,
        test_plan: str,
        requested_by: str
    ) -> ChangeRequest:
        """Create a change request"""
        assessment = self.risk_matrix.assessments.get(model_id)
        risk_level = assessment.risk_level if assessment else RiskLevel.MEDIUM

        return self.change_management.create_change_request(
            model_id=model_id,
            change_type=change_type,
            title=title,
            description=description,
            justification=justification,
            impact_assessment=impact_assessment,
            rollback_plan=rollback_plan,
            risk_level=risk_level,
            affected_systems=affected_systems,
            affected_consumers=affected_consumers,
            test_plan=test_plan,
            requested_by=requested_by
        )

    def get_dashboard_metrics(self) -> DashboardMetrics:
        """Get dashboard metrics"""
        return self.dashboard.get_metrics()

    def get_compliance_summary(self) -> dict[str, Any]:
        """Get compliance summary"""
        return self.dashboard.get_compliance_summary()

    def get_action_items(self, assignee_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Get prioritized action items"""
        return self.dashboard.get_action_items(assignee_id)

    def generate_report(
        self,
        report_type: str = "summary",
        model_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Generate governance report"""
        return self.dashboard.generate_report(report_type, model_id)

    def verify_model_governance(self, model_id: str) -> dict[str, Any]:
        """Verify model has complete governance"""
        issues = []

        # Check charter
        charter = None
        for c in self.charter_generator.charters.values():
            if c.model_id == model_id:
                charter = c
                break

        if not charter:
            issues.append("No charter found")
        elif not charter.is_signed:
            issues.append("Charter not fully signed")

        # Check ownership
        if charter and not charter.ownership.primary_owner_id:
            issues.append("No primary owner assigned")

        # Check risk assessment
        if model_id not in self.risk_matrix.assessments:
            issues.append("No risk assessment")

        # Check retrain schedule
        if model_id not in self.retrain_manager.schedules:
            issues.append("No retrain schedule")

        # Check for overdue actions
        if model_id in self.retrain_manager.schedules:
            if self.retrain_manager.schedules[model_id].is_retrain_due():
                issues.append("Retrain overdue")

        return {
            "model_id": model_id,
            "is_compliant": len(issues) == 0,
            "issues": issues,
            "verified_at": datetime.now(timezone.utc).isoformat()
        }

    def export_governance_state(self) -> dict[str, Any]:
        """Export complete governance state for backup/audit"""
        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "registered_models": self.registered_models,
            "charters": {
                k: v.to_dict()
                for k, v in self.charter_generator.charters.items()
            },
            "risk_assessments": {
                k: {
                    "risk_level": v.risk_level.value,
                    "overall_score": v.overall_score
                }
                for k, v in self.risk_matrix.assessments.items()
            },
            "retrain_schedules": {
                k: self.retrain_manager.get_schedule_status(k)
                for k in self.retrain_manager.schedules
            },
            "audit_chain_valid": self.audit_trail.verify_chain_integrity()[0],
            "dashboard_metrics": asdict(self.dashboard.get_metrics())
        }


# =============================================================================
# Factory and Convenience Functions
# =============================================================================

def create_governance_framework() -> GovernanceFramework:
    """Create and initialize a governance framework instance"""
    return GovernanceFramework()


def create_default_board() -> list[GovernanceBoardMember]:
    """Create default governance board members"""
    return [
        GovernanceBoardMember(
            member_id="ds-001",
            name="Lead Data Scientist",
            email="datascience@quan.ai",
            role=BoardRole.DATA_SCIENTIST,
            department="Data Science"
        ),
        GovernanceBoardMember(
            member_id="mle-001",
            name="Lead ML Engineer",
            email="mleng@quan.ai",
            role=BoardRole.ML_ENGINEER,
            department="ML Engineering"
        ),
        GovernanceBoardMember(
            member_id="comp-001",
            name="Compliance Officer",
            email="compliance@quan.ai",
            role=BoardRole.COMPLIANCE_OFFICER,
            department="Compliance"
        ),
        GovernanceBoardMember(
            member_id="prod-001",
            name="Product Owner",
            email="product@quan.ai",
            role=BoardRole.PRODUCT_OWNER,
            department="Product"
        ),
        GovernanceBoardMember(
            member_id="legal-001",
            name="Legal Counsel",
            email="legal@quan.ai",
            role=BoardRole.LEGAL_COUNSEL,
            department="Legal"
        ),
        GovernanceBoardMember(
            member_id="risk-001",
            name="Risk Manager",
            email="risk@quan.ai",
            role=BoardRole.RISK_MANAGER,
            department="Risk Management",
            approval_limit_risk_level=RiskLevel.CRITICAL
        ),
        GovernanceBoardMember(
            member_id="exec-001",
            name="Executive Sponsor",
            email="exec@quan.ai",
            role=BoardRole.EXECUTIVE_SPONSOR,
            department="Executive",
            approval_limit_risk_level=RiskLevel.CRITICAL
        ),
        GovernanceBoardMember(
            member_id="val-001",
            name="Model Validator",
            email="validation@quan.ai",
            role=BoardRole.MODEL_VALIDATOR,
            department="Model Risk"
        )
    ]


# Export all public components
__all__ = [
    # Enums
    "RiskLevel",
    "ModelStatus",
    "ApprovalStatus",
    "BoardRole",
    "ChangeType",
    "AuditEventType",
    "MessageRuleType",
    # Data classes
    "GovernanceBoardMember",
    "ModelOwnership",
    "ModelCharter",
    "ApprovalRequest",
    "LegalReview",
    "MessageRuleLegalReview",
    "RetrainSchedule",
    "ChangeRequest",
    "DeprecationWorkflow",
    "AuditEntry",
    "RiskAssessment",
    "DashboardMetrics",
    # Core components
    "DecisionRiskMatrix",
    "ModelCharterGenerator",
    "RetrainCadenceManager",
    "ApprovalWorkflowEngine",
    "LegalSignOffTracker",
    "ComplianceAuditTrail",
    "ChangeManagementProcess",
    "ModelDeprecationWorkflow",
    "GovernanceDashboard",
    "GovernanceFramework",
    # Factory functions
    "create_governance_framework",
    "create_default_board",
    # Constants
    "RISK_FACTORS",
    "APPROVAL_CHECKLISTS",
]
