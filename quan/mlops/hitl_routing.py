"""
Human-in-the-Loop (HITL) Policy and Decision Routing Engine

Provides intelligent routing of ML decisions based on confidence thresholds:
1. Auto-approve: High confidence decisions (>auto_approve_threshold)
2. HITL Queue: Medium confidence requiring human review
3. Auto-block: High risk decisions (>risk_block_threshold)

Features:
- Policy document generation
- Complete audit trail for all decisions
- Priority queue management
- Reviewer assignment with load balancing
- SLA tracking and escalation
- Feedback loop for model improvement
- Conservative decision policy enforcement
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Optional
from collections import defaultdict
import uuid
import json
import heapq


class RoutingDecision(Enum):
    """Possible routing outcomes"""
    AUTO_APPROVE = "auto_approve"
    HITL_REVIEW = "hitl_review"
    AUTO_BLOCK = "auto_block"
    ESCALATE = "escalate"


class ReviewPriority(Enum):
    """Priority levels for HITL queue"""
    CRITICAL = 1  # Must be reviewed within 1 hour
    HIGH = 2      # Must be reviewed within 4 hours
    MEDIUM = 3    # Must be reviewed within 24 hours
    LOW = 4       # Must be reviewed within 72 hours


class ReviewerStatus(Enum):
    """Reviewer availability status"""
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"
    ON_BREAK = "on_break"


class ReviewOutcome(Enum):
    """Outcomes of human review"""
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_MORE_INFO = "needs_more_info"
    ESCALATED = "escalated"
    EXPIRED = "expired"


@dataclass
class PolicyThresholds:
    """Configurable thresholds for routing decisions"""
    # Auto-approve if confidence >= this AND risk < risk_block_threshold
    auto_approve_confidence: float = 0.85

    # Route to HITL if confidence is between these values
    hitl_lower_bound: float = 0.50
    hitl_upper_bound: float = 0.85

    # Auto-block if risk score >= this
    risk_block_threshold: float = 0.75

    # Escalate if uncertainty >= this
    escalation_uncertainty: float = 0.40

    # Minimum samples required for auto-approve
    min_samples_for_auto: int = 100

    # Conservative mode: prefer HITL over auto-approve for edge cases
    conservative_mode: bool = True

    # Maximum amount that can be auto-approved
    max_auto_approve_amount: float = 500.0

    def validate(self) -> list[str]:
        """Validate threshold configuration"""
        errors = []
        if self.hitl_lower_bound >= self.hitl_upper_bound:
            errors.append("hitl_lower_bound must be less than hitl_upper_bound")
        if self.auto_approve_confidence < self.hitl_upper_bound:
            errors.append("auto_approve_confidence should be >= hitl_upper_bound")
        if not 0 <= self.risk_block_threshold <= 1:
            errors.append("risk_block_threshold must be between 0 and 1")
        return errors


@dataclass
class AuditEntry:
    """Single audit trail entry"""
    entry_id: str
    timestamp: datetime
    decision_id: str
    event_type: str
    actor: str  # 'system', 'reviewer_id', 'escalation_engine'
    action: str
    details: dict[str, Any]
    previous_state: Optional[str] = None
    new_state: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat(),
            "decision_id": self.decision_id,
            "event_type": self.event_type,
            "actor": self.actor,
            "action": self.action,
            "details": self.details,
            "previous_state": self.previous_state,
            "new_state": self.new_state
        }


@dataclass
class Decision:
    """A decision requiring routing"""
    decision_id: str
    decision_type: str  # 'settlement', 'payment_plan', 'contact', etc.
    account_id: str
    payload: dict[str, Any]

    # ML model outputs
    confidence: float
    risk_score: float
    uncertainty: float
    model_version: str

    # Routing result
    routing_decision: Optional[RoutingDecision] = None
    routing_reason: str = ""

    # Review tracking
    priority: ReviewPriority = ReviewPriority.MEDIUM
    assigned_reviewer: Optional[str] = None
    review_outcome: Optional[ReviewOutcome] = None
    review_notes: str = ""

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    routed_at: Optional[datetime] = None
    claimed_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    sla_deadline: Optional[datetime] = None

    # Metadata
    escalation_count: int = 0
    feedback_recorded: bool = False

    def get_wait_time(self) -> Optional[timedelta]:
        """Get time spent waiting for review"""
        if not self.routed_at:
            return None
        end_time = self.claimed_at or datetime.now()
        return end_time - self.routed_at

    def get_review_time(self) -> Optional[timedelta]:
        """Get time spent in review"""
        if not self.claimed_at:
            return None
        end_time = self.resolved_at or datetime.now()
        return end_time - self.claimed_at

    def is_sla_breached(self) -> bool:
        """Check if SLA has been breached"""
        if not self.sla_deadline:
            return False
        if self.resolved_at:
            return self.resolved_at > self.sla_deadline
        return datetime.now() > self.sla_deadline


@dataclass
class Reviewer:
    """Human reviewer for HITL queue"""
    reviewer_id: str
    name: str
    email: str
    status: ReviewerStatus = ReviewerStatus.AVAILABLE

    # Capabilities
    can_review: list[str] = field(default_factory=list)  # Decision types
    max_authority_amount: float = 1000.0
    can_escalate: bool = True

    # Load tracking
    current_load: int = 0
    max_load: int = 10
    total_reviewed: int = 0

    # Performance
    avg_review_time_minutes: float = 15.0
    accuracy_rate: float = 0.95
    escalation_rate: float = 0.05

    # Timestamps
    last_active: datetime = field(default_factory=datetime.now)
    shift_start: Optional[datetime] = None
    shift_end: Optional[datetime] = None

    def is_available(self) -> bool:
        """Check if reviewer can take new items"""
        if self.status != ReviewerStatus.AVAILABLE:
            return False
        if self.current_load >= self.max_load:
            return False
        return True

    def can_handle(self, decision: Decision) -> bool:
        """Check if reviewer can handle this decision type"""
        if decision.decision_type not in self.can_review:
            return False
        amount = decision.payload.get("amount", 0)
        if amount > self.max_authority_amount:
            return False
        return True


@dataclass
class PolicyDocument:
    """Generated policy document for audit and compliance"""
    document_id: str
    generated_at: datetime
    policy_version: str
    thresholds: PolicyThresholds
    decision_rules: list[dict[str, Any]]
    escalation_paths: list[dict[str, Any]]
    reviewer_guidelines: list[str]
    audit_requirements: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "generated_at": self.generated_at.isoformat(),
            "policy_version": self.policy_version,
            "thresholds": {
                "auto_approve_confidence": self.thresholds.auto_approve_confidence,
                "hitl_lower_bound": self.thresholds.hitl_lower_bound,
                "hitl_upper_bound": self.thresholds.hitl_upper_bound,
                "risk_block_threshold": self.thresholds.risk_block_threshold,
                "escalation_uncertainty": self.thresholds.escalation_uncertainty,
                "conservative_mode": self.thresholds.conservative_mode,
                "max_auto_approve_amount": self.thresholds.max_auto_approve_amount
            },
            "decision_rules": self.decision_rules,
            "escalation_paths": self.escalation_paths,
            "reviewer_guidelines": self.reviewer_guidelines,
            "audit_requirements": self.audit_requirements
        }

    def to_markdown(self) -> str:
        """Generate markdown documentation"""
        md = f"""# HITL Policy Document

## Document Information
- **Document ID**: {self.document_id}
- **Generated**: {self.generated_at.isoformat()}
- **Policy Version**: {self.policy_version}

## Routing Thresholds

| Threshold | Value | Description |
|-----------|-------|-------------|
| Auto-Approve Confidence | {self.thresholds.auto_approve_confidence:.0%} | Minimum confidence for auto-approval |
| HITL Lower Bound | {self.thresholds.hitl_lower_bound:.0%} | Below this routes to auto-block |
| HITL Upper Bound | {self.thresholds.hitl_upper_bound:.0%} | Above this may auto-approve |
| Risk Block Threshold | {self.thresholds.risk_block_threshold:.0%} | Above this auto-blocks |
| Escalation Uncertainty | {self.thresholds.escalation_uncertainty:.0%} | Above this triggers escalation |
| Max Auto-Approve Amount | ${self.thresholds.max_auto_approve_amount:,.2f} | Maximum value for auto-approval |
| Conservative Mode | {"Enabled" if self.thresholds.conservative_mode else "Disabled"} | Prefer human review for edge cases |

## Decision Rules

"""
        for i, rule in enumerate(self.decision_rules, 1):
            md += f"### Rule {i}: {rule.get('name', 'Unnamed')}\n"
            md += f"- **Condition**: {rule.get('condition', 'N/A')}\n"
            md += f"- **Action**: {rule.get('action', 'N/A')}\n"
            md += f"- **Rationale**: {rule.get('rationale', 'N/A')}\n\n"

        md += "## Escalation Paths\n\n"
        for path in self.escalation_paths:
            md += f"- **{path.get('trigger', 'Unknown')}**: {path.get('action', 'N/A')}\n"

        md += "\n## Reviewer Guidelines\n\n"
        for guideline in self.reviewer_guidelines:
            md += f"- {guideline}\n"

        md += "\n## Audit Requirements\n\n"
        for req in self.audit_requirements:
            md += f"- {req}\n"

        return md


class AuditTrail:
    """Complete audit trail for all routing decisions"""

    def __init__(self):
        self.entries: list[AuditEntry] = []
        self._entries_by_decision: dict[str, list[AuditEntry]] = defaultdict(list)

    def record(
        self,
        decision_id: str,
        event_type: str,
        actor: str,
        action: str,
        details: dict[str, Any],
        previous_state: Optional[str] = None,
        new_state: Optional[str] = None
    ) -> AuditEntry:
        """Record an audit entry"""
        entry = AuditEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            decision_id=decision_id,
            event_type=event_type,
            actor=actor,
            action=action,
            details=details,
            previous_state=previous_state,
            new_state=new_state
        )
        self.entries.append(entry)
        self._entries_by_decision[decision_id].append(entry)
        return entry

    def get_decision_history(self, decision_id: str) -> list[AuditEntry]:
        """Get complete history for a decision"""
        return self._entries_by_decision.get(decision_id, [])

    def get_entries_by_actor(self, actor: str) -> list[AuditEntry]:
        """Get all entries by a specific actor"""
        return [e for e in self.entries if e.actor == actor]

    def get_entries_in_range(
        self,
        start: datetime,
        end: datetime
    ) -> list[AuditEntry]:
        """Get entries within a time range"""
        return [
            e for e in self.entries
            if start <= e.timestamp <= end
        ]

    def export_json(self) -> str:
        """Export audit trail as JSON"""
        return json.dumps(
            [e.to_dict() for e in self.entries],
            indent=2
        )


class PolicyEngine:
    """
    Core policy engine for routing decisions

    Implements conservative decision-making with clear thresholds
    and comprehensive audit trailing.
    """

    def __init__(self, thresholds: Optional[PolicyThresholds] = None):
        self.thresholds = thresholds or PolicyThresholds()
        self.audit_trail = AuditTrail()
        self._decision_stats: dict[str, int] = defaultdict(int)
        self._model_performance: dict[str, list[float]] = defaultdict(list)

        # Validate thresholds
        errors = self.thresholds.validate()
        if errors:
            raise ValueError(f"Invalid thresholds: {errors}")

    def route_decision(self, decision: Decision) -> RoutingDecision:
        """
        Route a decision based on confidence, risk, and policy

        Routing logic (in order of precedence):
        1. High risk -> AUTO_BLOCK
        2. High uncertainty -> ESCALATE
        3. Low confidence -> AUTO_BLOCK (conservative)
        4. High confidence + low risk + within limits -> AUTO_APPROVE
        5. Everything else -> HITL_REVIEW
        """
        reasons = []

        # Record initial state
        self.audit_trail.record(
            decision_id=decision.decision_id,
            event_type="routing_started",
            actor="system",
            action="evaluate_decision",
            details={
                "confidence": decision.confidence,
                "risk_score": decision.risk_score,
                "uncertainty": decision.uncertainty,
                "decision_type": decision.decision_type,
                "model_version": decision.model_version
            }
        )

        # Rule 1: High risk auto-block
        if decision.risk_score >= self.thresholds.risk_block_threshold:
            routing = RoutingDecision.AUTO_BLOCK
            reasons.append(
                f"Risk score {decision.risk_score:.2%} exceeds "
                f"block threshold {self.thresholds.risk_block_threshold:.2%}"
            )

        # Rule 2: High uncertainty escalation
        elif decision.uncertainty >= self.thresholds.escalation_uncertainty:
            routing = RoutingDecision.ESCALATE
            reasons.append(
                f"Uncertainty {decision.uncertainty:.2%} exceeds "
                f"escalation threshold {self.thresholds.escalation_uncertainty:.2%}"
            )

        # Rule 3: Low confidence auto-block (conservative)
        elif decision.confidence < self.thresholds.hitl_lower_bound:
            routing = RoutingDecision.AUTO_BLOCK
            reasons.append(
                f"Confidence {decision.confidence:.2%} below "
                f"minimum threshold {self.thresholds.hitl_lower_bound:.2%}"
            )

        # Rule 4: High confidence auto-approve (with additional checks)
        elif decision.confidence >= self.thresholds.auto_approve_confidence:
            # Additional checks for auto-approval
            amount = decision.payload.get("amount", 0)

            if amount > self.thresholds.max_auto_approve_amount:
                routing = RoutingDecision.HITL_REVIEW
                reasons.append(
                    f"Amount ${amount:,.2f} exceeds auto-approve limit "
                    f"${self.thresholds.max_auto_approve_amount:,.2f}"
                )
            elif self.thresholds.conservative_mode and decision.confidence < 0.95:
                # In conservative mode, only auto-approve very high confidence
                routing = RoutingDecision.HITL_REVIEW
                reasons.append(
                    f"Conservative mode: confidence {decision.confidence:.2%} "
                    f"below 95% threshold for auto-approve"
                )
            else:
                routing = RoutingDecision.AUTO_APPROVE
                reasons.append(
                    f"Confidence {decision.confidence:.2%} meets auto-approve "
                    f"threshold with acceptable risk {decision.risk_score:.2%}"
                )

        # Rule 5: Medium confidence -> HITL
        else:
            routing = RoutingDecision.HITL_REVIEW
            reasons.append(
                f"Confidence {decision.confidence:.2%} within HITL range "
                f"[{self.thresholds.hitl_lower_bound:.2%}, "
                f"{self.thresholds.hitl_upper_bound:.2%}]"
            )

        # Update decision
        decision.routing_decision = routing
        decision.routing_reason = "; ".join(reasons)
        decision.routed_at = datetime.now()

        # Set priority for HITL items
        if routing == RoutingDecision.HITL_REVIEW:
            decision.priority = self._calculate_priority(decision)
            decision.sla_deadline = self._calculate_sla_deadline(decision.priority)

        # Record routing result
        self.audit_trail.record(
            decision_id=decision.decision_id,
            event_type="routing_completed",
            actor="system",
            action="route_decision",
            details={
                "routing_decision": routing.value,
                "reasons": reasons,
                "priority": decision.priority.name if decision.priority else None,
                "sla_deadline": decision.sla_deadline.isoformat() if decision.sla_deadline else None
            },
            previous_state="pending",
            new_state=routing.value
        )

        # Update statistics
        self._decision_stats[routing.value] += 1

        return routing

    def _calculate_priority(self, decision: Decision) -> ReviewPriority:
        """Calculate review priority based on decision attributes"""
        amount = decision.payload.get("amount", 0)

        # Critical: High value or near threshold edge cases
        if amount > 1000 or decision.uncertainty > 0.35:
            return ReviewPriority.CRITICAL

        # High: Moderate value or elevated risk
        if amount > 500 or decision.risk_score > 0.5:
            return ReviewPriority.HIGH

        # Medium: Standard cases
        if decision.confidence > 0.6:
            return ReviewPriority.MEDIUM

        # Low: Lower priority cases
        return ReviewPriority.LOW

    def _calculate_sla_deadline(self, priority: ReviewPriority) -> datetime:
        """Calculate SLA deadline based on priority"""
        sla_hours = {
            ReviewPriority.CRITICAL: 1,
            ReviewPriority.HIGH: 4,
            ReviewPriority.MEDIUM: 24,
            ReviewPriority.LOW: 72
        }
        return datetime.now() + timedelta(hours=sla_hours[priority])

    def record_feedback(
        self,
        decision_id: str,
        actual_outcome: str,
        was_correct: bool
    ) -> None:
        """Record feedback for model improvement"""
        self.audit_trail.record(
            decision_id=decision_id,
            event_type="feedback_recorded",
            actor="system",
            action="record_outcome",
            details={
                "actual_outcome": actual_outcome,
                "routing_was_correct": was_correct
            }
        )

        # Track for model performance
        self._model_performance["accuracy"].append(1.0 if was_correct else 0.0)

    def get_statistics(self) -> dict[str, Any]:
        """Get routing statistics"""
        total = sum(self._decision_stats.values())
        return {
            "total_decisions": total,
            "by_routing": dict(self._decision_stats),
            "percentages": {
                k: v / total * 100 if total > 0 else 0
                for k, v in self._decision_stats.items()
            },
            "model_accuracy": (
                sum(self._model_performance["accuracy"]) /
                len(self._model_performance["accuracy"])
                if self._model_performance["accuracy"] else None
            )
        }


class HITLQueue:
    """
    Priority queue for human-in-the-loop review

    Supports:
    - Priority-based ordering
    - Claiming and releasing items
    - SLA tracking
    - Load balancing across reviewers
    """

    def __init__(self):
        self._queue: list[tuple[int, float, Decision]] = []  # (priority, timestamp, decision)
        self._pending: dict[str, Decision] = {}
        self._claimed: dict[str, Decision] = {}
        self._resolved: dict[str, Decision] = {}
        self.audit_trail = AuditTrail()

    def add(self, decision: Decision) -> None:
        """Add decision to queue"""
        if decision.routing_decision != RoutingDecision.HITL_REVIEW:
            raise ValueError("Only HITL_REVIEW decisions can be added to queue")

        # Use priority value and timestamp for ordering
        priority_value = decision.priority.value
        timestamp = decision.created_at.timestamp()

        heapq.heappush(self._queue, (priority_value, timestamp, decision))
        self._pending[decision.decision_id] = decision

        self.audit_trail.record(
            decision_id=decision.decision_id,
            event_type="queue_add",
            actor="system",
            action="add_to_queue",
            details={
                "priority": decision.priority.name,
                "queue_position": len(self._queue),
                "sla_deadline": decision.sla_deadline.isoformat() if decision.sla_deadline else None
            }
        )

    def claim(self, reviewer_id: str, decision_id: Optional[str] = None) -> Optional[Decision]:
        """
        Claim a decision for review

        If decision_id is provided, claims that specific decision.
        Otherwise, claims the highest priority item.
        """
        if decision_id:
            # Claim specific decision
            if decision_id not in self._pending:
                return None
            decision = self._pending.pop(decision_id)
            # Remove from heap (inefficient but necessary for specific claim)
            self._queue = [
                (p, t, d) for p, t, d in self._queue
                if d.decision_id != decision_id
            ]
            heapq.heapify(self._queue)
        else:
            # Claim highest priority
            if not self._queue:
                return None
            _, _, decision = heapq.heappop(self._queue)
            del self._pending[decision.decision_id]

        decision.assigned_reviewer = reviewer_id
        decision.claimed_at = datetime.now()
        self._claimed[decision.decision_id] = decision

        self.audit_trail.record(
            decision_id=decision.decision_id,
            event_type="queue_claim",
            actor=reviewer_id,
            action="claim_for_review",
            details={
                "reviewer_id": reviewer_id,
                "wait_time_seconds": decision.get_wait_time().total_seconds() if decision.get_wait_time() else 0
            },
            previous_state="pending",
            new_state="claimed"
        )

        return decision

    def release(self, decision_id: str, reason: str = "") -> bool:
        """Release a claimed decision back to queue"""
        if decision_id not in self._claimed:
            return False

        decision = self._claimed.pop(decision_id)
        old_reviewer = decision.assigned_reviewer
        decision.assigned_reviewer = None
        decision.claimed_at = None

        # Re-add to queue
        heapq.heappush(
            self._queue,
            (decision.priority.value, decision.created_at.timestamp(), decision)
        )
        self._pending[decision.decision_id] = decision

        self.audit_trail.record(
            decision_id=decision.decision_id,
            event_type="queue_release",
            actor=old_reviewer or "system",
            action="release_to_queue",
            details={"reason": reason},
            previous_state="claimed",
            new_state="pending"
        )

        return True

    def resolve(
        self,
        decision_id: str,
        outcome: ReviewOutcome,
        notes: str = ""
    ) -> bool:
        """Resolve a claimed decision"""
        if decision_id not in self._claimed:
            return False

        decision = self._claimed.pop(decision_id)
        decision.review_outcome = outcome
        decision.review_notes = notes
        decision.resolved_at = datetime.now()
        self._resolved[decision.decision_id] = decision

        self.audit_trail.record(
            decision_id=decision.decision_id,
            event_type="queue_resolve",
            actor=decision.assigned_reviewer or "system",
            action="resolve_review",
            details={
                "outcome": outcome.value,
                "notes": notes,
                "review_time_seconds": decision.get_review_time().total_seconds() if decision.get_review_time() else 0,
                "sla_breached": decision.is_sla_breached()
            },
            previous_state="claimed",
            new_state="resolved"
        )

        return True

    def get_pending_count(self) -> int:
        """Get number of pending items"""
        return len(self._pending)

    def get_claimed_count(self) -> int:
        """Get number of claimed items"""
        return len(self._claimed)

    def get_by_priority(self, priority: ReviewPriority) -> list[Decision]:
        """Get all pending decisions of a specific priority"""
        return [
            d for d in self._pending.values()
            if d.priority == priority
        ]

    def get_sla_breaches(self) -> list[Decision]:
        """Get decisions that have breached SLA"""
        breaches = []
        for decision in list(self._pending.values()) + list(self._claimed.values()):
            if decision.is_sla_breached():
                breaches.append(decision)
        return breaches

    def get_queue_stats(self) -> dict[str, Any]:
        """Get queue statistics"""
        now = datetime.now()

        pending_wait_times = [
            (now - d.routed_at).total_seconds()
            for d in self._pending.values()
            if d.routed_at
        ]

        resolved_review_times = [
            d.get_review_time().total_seconds()
            for d in self._resolved.values()
            if d.get_review_time()
        ]

        return {
            "pending_count": len(self._pending),
            "claimed_count": len(self._claimed),
            "resolved_count": len(self._resolved),
            "by_priority": {
                p.name: len(self.get_by_priority(p))
                for p in ReviewPriority
            },
            "sla_breaches": len(self.get_sla_breaches()),
            "avg_wait_time_seconds": (
                sum(pending_wait_times) / len(pending_wait_times)
                if pending_wait_times else 0
            ),
            "avg_review_time_seconds": (
                sum(resolved_review_times) / len(resolved_review_times)
                if resolved_review_times else 0
            )
        }


class ReviewerPool:
    """
    Manages pool of human reviewers with load balancing
    """

    def __init__(self):
        self.reviewers: dict[str, Reviewer] = {}
        self.audit_trail = AuditTrail()

    def add_reviewer(self, reviewer: Reviewer) -> None:
        """Add reviewer to pool"""
        self.reviewers[reviewer.reviewer_id] = reviewer

        self.audit_trail.record(
            decision_id="system",
            event_type="reviewer_added",
            actor="system",
            action="add_reviewer",
            details={
                "reviewer_id": reviewer.reviewer_id,
                "name": reviewer.name,
                "can_review": reviewer.can_review,
                "max_authority": reviewer.max_authority_amount
            }
        )

    def remove_reviewer(self, reviewer_id: str) -> bool:
        """Remove reviewer from pool"""
        if reviewer_id not in self.reviewers:
            return False

        del self.reviewers[reviewer_id]
        return True

    def update_status(self, reviewer_id: str, status: ReviewerStatus) -> bool:
        """Update reviewer status"""
        if reviewer_id not in self.reviewers:
            return False

        old_status = self.reviewers[reviewer_id].status
        self.reviewers[reviewer_id].status = status
        self.reviewers[reviewer_id].last_active = datetime.now()

        self.audit_trail.record(
            decision_id="system",
            event_type="reviewer_status_change",
            actor=reviewer_id,
            action="update_status",
            details={"old_status": old_status.value, "new_status": status.value}
        )

        return True

    def get_best_reviewer(self, decision: Decision) -> Optional[Reviewer]:
        """
        Find best available reviewer for a decision using load balancing

        Selection criteria (in order):
        1. Must be available
        2. Must be able to handle decision type and amount
        3. Prefer lowest current load
        4. Prefer higher accuracy rate
        """
        candidates = []

        for reviewer in self.reviewers.values():
            if not reviewer.is_available():
                continue
            if not reviewer.can_handle(decision):
                continue

            # Score: lower is better
            # Prioritize low load, then high accuracy
            load_score = reviewer.current_load / reviewer.max_load
            accuracy_score = 1 - reviewer.accuracy_rate
            combined_score = load_score * 0.7 + accuracy_score * 0.3

            candidates.append((combined_score, reviewer))

        if not candidates:
            return None

        # Sort by score (ascending) and return best
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    def assign_decision(self, decision: Decision) -> Optional[str]:
        """Assign decision to best available reviewer"""
        reviewer = self.get_best_reviewer(decision)

        if not reviewer:
            return None

        reviewer.current_load += 1
        decision.assigned_reviewer = reviewer.reviewer_id

        self.audit_trail.record(
            decision_id=decision.decision_id,
            event_type="reviewer_assigned",
            actor="system",
            action="assign_reviewer",
            details={
                "reviewer_id": reviewer.reviewer_id,
                "reviewer_load": reviewer.current_load,
                "decision_type": decision.decision_type
            }
        )

        return reviewer.reviewer_id

    def complete_review(self, reviewer_id: str) -> None:
        """Mark a review as complete, updating reviewer stats"""
        if reviewer_id in self.reviewers:
            self.reviewers[reviewer_id].current_load -= 1
            self.reviewers[reviewer_id].total_reviewed += 1
            self.reviewers[reviewer_id].last_active = datetime.now()

    def get_pool_stats(self) -> dict[str, Any]:
        """Get reviewer pool statistics"""
        available = [r for r in self.reviewers.values() if r.is_available()]
        total_capacity = sum(r.max_load - r.current_load for r in available)

        return {
            "total_reviewers": len(self.reviewers),
            "available_reviewers": len(available),
            "total_capacity": total_capacity,
            "by_status": {
                s.value: len([r for r in self.reviewers.values() if r.status == s])
                for s in ReviewerStatus
            },
            "avg_load": (
                sum(r.current_load for r in self.reviewers.values()) /
                len(self.reviewers) if self.reviewers else 0
            )
        }


class EscalationEngine:
    """
    Handles escalation paths for edge cases
    """

    def __init__(self):
        self.escalation_rules: list[dict[str, Any]] = []
        self.audit_trail = AuditTrail()
        self._setup_default_rules()

    def _setup_default_rules(self) -> None:
        """Setup default escalation rules"""
        self.escalation_rules = [
            {
                "name": "sla_breach",
                "condition": lambda d: d.is_sla_breached(),
                "action": "escalate_to_supervisor",
                "priority_boost": 1
            },
            {
                "name": "multiple_escalations",
                "condition": lambda d: d.escalation_count >= 2,
                "action": "escalate_to_manager",
                "priority_boost": 2
            },
            {
                "name": "high_value",
                "condition": lambda d: d.payload.get("amount", 0) > 5000,
                "action": "require_senior_review",
                "priority_boost": 1
            },
            {
                "name": "compliance_flag",
                "condition": lambda d: d.payload.get("compliance_flag", False),
                "action": "escalate_to_compliance",
                "priority_boost": 2
            }
        ]

    def check_escalation(self, decision: Decision) -> Optional[dict[str, Any]]:
        """Check if decision should be escalated"""
        for rule in self.escalation_rules:
            try:
                if rule["condition"](decision):
                    self.audit_trail.record(
                        decision_id=decision.decision_id,
                        event_type="escalation_triggered",
                        actor="system",
                        action="check_escalation",
                        details={
                            "rule_name": rule["name"],
                            "action": rule["action"]
                        }
                    )
                    return rule
            except Exception:
                continue
        return None

    def escalate(self, decision: Decision) -> RoutingDecision:
        """Escalate a decision"""
        decision.escalation_count += 1

        # Boost priority if not already critical
        if decision.priority != ReviewPriority.CRITICAL:
            current_value = decision.priority.value
            new_value = max(1, current_value - 1)
            decision.priority = ReviewPriority(new_value)

        # Extend SLA
        decision.sla_deadline = datetime.now() + timedelta(hours=2)

        self.audit_trail.record(
            decision_id=decision.decision_id,
            event_type="escalation_applied",
            actor="system",
            action="escalate",
            details={
                "escalation_count": decision.escalation_count,
                "new_priority": decision.priority.name,
                "new_sla_deadline": decision.sla_deadline.isoformat()
            },
            previous_state=decision.routing_decision.value if decision.routing_decision else None,
            new_state="escalated"
        )

        return RoutingDecision.ESCALATE


class FeedbackLoop:
    """
    Captures and processes feedback for model improvement
    """

    def __init__(self):
        self.feedback_records: list[dict[str, Any]] = []
        self.audit_trail = AuditTrail()

    def record_outcome(
        self,
        decision: Decision,
        actual_outcome: str,
        outcome_timestamp: datetime
    ) -> None:
        """Record actual outcome for a decision"""
        was_correct = self._evaluate_correctness(decision, actual_outcome)

        record = {
            "decision_id": decision.decision_id,
            "routing_decision": decision.routing_decision.value if decision.routing_decision else None,
            "review_outcome": decision.review_outcome.value if decision.review_outcome else None,
            "actual_outcome": actual_outcome,
            "was_correct": was_correct,
            "confidence": decision.confidence,
            "risk_score": decision.risk_score,
            "model_version": decision.model_version,
            "outcome_timestamp": outcome_timestamp.isoformat(),
            "latency_hours": (
                (outcome_timestamp - decision.created_at).total_seconds() / 3600
                if decision.created_at else None
            )
        }

        self.feedback_records.append(record)
        decision.feedback_recorded = True

        self.audit_trail.record(
            decision_id=decision.decision_id,
            event_type="feedback_recorded",
            actor="system",
            action="record_outcome",
            details=record
        )

    def _evaluate_correctness(self, decision: Decision, actual_outcome: str) -> bool:
        """Evaluate if routing decision was correct given outcome"""
        # Auto-approve should have resulted in positive outcome
        if decision.routing_decision == RoutingDecision.AUTO_APPROVE:
            return actual_outcome in ["success", "paid", "settled"]

        # Auto-block should have been justified
        if decision.routing_decision == RoutingDecision.AUTO_BLOCK:
            return actual_outcome in ["fraud", "default", "dispute"]

        # HITL review correctness based on reviewer accuracy
        if decision.routing_decision == RoutingDecision.HITL_REVIEW:
            if decision.review_outcome == ReviewOutcome.APPROVED:
                return actual_outcome in ["success", "paid", "settled"]
            elif decision.review_outcome == ReviewOutcome.REJECTED:
                return actual_outcome in ["fraud", "default", "dispute"]

        return True  # Default to correct for edge cases

    def get_accuracy_metrics(self) -> dict[str, Any]:
        """Get accuracy metrics from feedback"""
        if not self.feedback_records:
            return {"total": 0, "accuracy": None}

        total = len(self.feedback_records)
        correct = sum(1 for r in self.feedback_records if r["was_correct"])

        by_routing = defaultdict(lambda: {"total": 0, "correct": 0})
        for record in self.feedback_records:
            routing = record.get("routing_decision", "unknown")
            by_routing[routing]["total"] += 1
            if record["was_correct"]:
                by_routing[routing]["correct"] += 1

        return {
            "total": total,
            "correct": correct,
            "accuracy": correct / total,
            "by_routing": {
                k: {
                    "total": v["total"],
                    "accuracy": v["correct"] / v["total"] if v["total"] > 0 else None
                }
                for k, v in by_routing.items()
            }
        }

    def get_model_drift_indicators(self) -> dict[str, Any]:
        """Detect potential model drift from feedback"""
        if len(self.feedback_records) < 50:
            return {"sufficient_data": False}

        # Compare recent vs historical accuracy
        recent = self.feedback_records[-50:]
        historical = self.feedback_records[:-50] if len(self.feedback_records) > 50 else []

        recent_accuracy = sum(1 for r in recent if r["was_correct"]) / len(recent)
        historical_accuracy = (
            sum(1 for r in historical if r["was_correct"]) / len(historical)
            if historical else recent_accuracy
        )

        drift_detected = abs(recent_accuracy - historical_accuracy) > 0.1

        return {
            "sufficient_data": True,
            "recent_accuracy": recent_accuracy,
            "historical_accuracy": historical_accuracy,
            "drift_detected": drift_detected,
            "accuracy_change": recent_accuracy - historical_accuracy
        }


class HITLRouter:
    """
    Main Human-in-the-Loop routing system

    Integrates policy engine, queue management, reviewer assignment,
    SLA tracking, and feedback loops into a unified routing system.
    """

    def __init__(self, thresholds: Optional[PolicyThresholds] = None):
        self.policy_engine = PolicyEngine(thresholds)
        self.queue = HITLQueue()
        self.reviewer_pool = ReviewerPool()
        self.escalation_engine = EscalationEngine()
        self.feedback_loop = FeedbackLoop()

        # Unified audit trail
        self.audit_trail = AuditTrail()

        # Decision tracking
        self._decisions: dict[str, Decision] = {}
        self._auto_approved: dict[str, Decision] = {}
        self._auto_blocked: dict[str, Decision] = {}

    def route(self, decision: Decision) -> RoutingDecision:
        """
        Route a decision through the HITL system

        Returns the routing decision and updates the decision object.
        """
        self._decisions[decision.decision_id] = decision

        # Record routing start
        self.audit_trail.record(
            decision_id=decision.decision_id,
            event_type="routing_initiated",
            actor="system",
            action="start_routing",
            details={
                "decision_type": decision.decision_type,
                "account_id": decision.account_id,
                "confidence": decision.confidence,
                "risk_score": decision.risk_score
            }
        )

        # Get routing decision from policy engine
        routing = self.policy_engine.route_decision(decision)

        # Handle based on routing
        if routing == RoutingDecision.AUTO_APPROVE:
            self._auto_approved[decision.decision_id] = decision
            self.audit_trail.record(
                decision_id=decision.decision_id,
                event_type="auto_approved",
                actor="system",
                action="complete_routing",
                details={"reason": decision.routing_reason}
            )

        elif routing == RoutingDecision.AUTO_BLOCK:
            self._auto_blocked[decision.decision_id] = decision
            self.audit_trail.record(
                decision_id=decision.decision_id,
                event_type="auto_blocked",
                actor="system",
                action="complete_routing",
                details={"reason": decision.routing_reason}
            )

        elif routing in [RoutingDecision.HITL_REVIEW, RoutingDecision.ESCALATE]:
            # Add to queue
            decision.routing_decision = RoutingDecision.HITL_REVIEW
            self.queue.add(decision)

            # Try to assign reviewer
            reviewer_id = self.reviewer_pool.assign_decision(decision)

            if routing == RoutingDecision.ESCALATE:
                self.escalation_engine.escalate(decision)

            self.audit_trail.record(
                decision_id=decision.decision_id,
                event_type="queued_for_review",
                actor="system",
                action="complete_routing",
                details={
                    "priority": decision.priority.name,
                    "assigned_reviewer": reviewer_id,
                    "sla_deadline": decision.sla_deadline.isoformat() if decision.sla_deadline else None
                }
            )

        return routing

    def claim_next(self, reviewer_id: str) -> Optional[Decision]:
        """Claim next decision from queue for reviewer"""
        reviewer = self.reviewer_pool.reviewers.get(reviewer_id)
        if not reviewer or not reviewer.is_available():
            return None

        decision = self.queue.claim(reviewer_id)
        if decision:
            reviewer.current_load += 1

        return decision

    def resolve_review(
        self,
        decision_id: str,
        outcome: ReviewOutcome,
        notes: str = ""
    ) -> bool:
        """Resolve a review with outcome"""
        decision = self._decisions.get(decision_id)
        if not decision:
            return False

        success = self.queue.resolve(decision_id, outcome, notes)

        if success and decision.assigned_reviewer:
            self.reviewer_pool.complete_review(decision.assigned_reviewer)

        self.audit_trail.record(
            decision_id=decision_id,
            event_type="review_completed",
            actor=decision.assigned_reviewer or "system",
            action="resolve_review",
            details={
                "outcome": outcome.value,
                "notes": notes,
                "total_time_seconds": (
                    (decision.resolved_at - decision.created_at).total_seconds()
                    if decision.resolved_at and decision.created_at else None
                )
            }
        )

        return success

    def record_feedback(
        self,
        decision_id: str,
        actual_outcome: str
    ) -> None:
        """Record actual outcome feedback"""
        decision = self._decisions.get(decision_id)
        if decision:
            self.feedback_loop.record_outcome(
                decision,
                actual_outcome,
                datetime.now()
            )

    def check_sla_breaches(self) -> list[Decision]:
        """Check for SLA breaches and escalate"""
        breaches = self.queue.get_sla_breaches()

        for decision in breaches:
            escalation = self.escalation_engine.check_escalation(decision)
            if escalation:
                self.escalation_engine.escalate(decision)

        return breaches

    def generate_policy_document(self) -> PolicyDocument:
        """Generate policy document for audit"""
        thresholds = self.policy_engine.thresholds

        decision_rules = [
            {
                "name": "High Risk Auto-Block",
                "condition": f"risk_score >= {thresholds.risk_block_threshold:.0%}",
                "action": "AUTO_BLOCK",
                "rationale": "High risk decisions are automatically blocked to prevent losses"
            },
            {
                "name": "High Uncertainty Escalation",
                "condition": f"uncertainty >= {thresholds.escalation_uncertainty:.0%}",
                "action": "ESCALATE",
                "rationale": "Uncertain predictions require senior review"
            },
            {
                "name": "Low Confidence Block",
                "condition": f"confidence < {thresholds.hitl_lower_bound:.0%}",
                "action": "AUTO_BLOCK",
                "rationale": "Conservative approach blocks low confidence decisions"
            },
            {
                "name": "High Confidence Auto-Approve",
                "condition": (
                    f"confidence >= {thresholds.auto_approve_confidence:.0%} "
                    f"AND amount <= ${thresholds.max_auto_approve_amount:,.2f}"
                ),
                "action": "AUTO_APPROVE",
                "rationale": "High confidence decisions within limits can be auto-approved"
            },
            {
                "name": "Medium Confidence HITL",
                "condition": (
                    f"confidence in [{thresholds.hitl_lower_bound:.0%}, "
                    f"{thresholds.hitl_upper_bound:.0%}]"
                ),
                "action": "HITL_REVIEW",
                "rationale": "Medium confidence decisions require human judgment"
            }
        ]

        escalation_paths = [
            {"trigger": "SLA Breach", "action": "Escalate to supervisor with priority boost"},
            {"trigger": "Multiple Escalations (>=2)", "action": "Escalate to manager"},
            {"trigger": "High Value (>$5000)", "action": "Require senior reviewer"},
            {"trigger": "Compliance Flag", "action": "Route to compliance team"}
        ]

        reviewer_guidelines = [
            "Review all supporting documentation before making a decision",
            "Document reasoning in review notes for audit trail",
            "Escalate if uncertain - do not guess on edge cases",
            "Consider consumer protection regulations in all decisions",
            "Report any suspected fraud immediately",
            "Adhere to SLA deadlines; request extension if needed"
        ]

        audit_requirements = [
            "All routing decisions must be logged with timestamps",
            "Reviewer actions must be attributed with user ID",
            "Decision changes must record previous and new states",
            "Feedback outcomes must be linked to original decisions",
            "Audit trail must be immutable and tamper-evident",
            "Records must be retained for minimum 7 years"
        ]

        return PolicyDocument(
            document_id=str(uuid.uuid4()),
            generated_at=datetime.now(),
            policy_version="1.0.0",
            thresholds=thresholds,
            decision_rules=decision_rules,
            escalation_paths=escalation_paths,
            reviewer_guidelines=reviewer_guidelines,
            audit_requirements=audit_requirements
        )

    def get_decision_audit_trail(self, decision_id: str) -> list[dict[str, Any]]:
        """Get complete audit trail for a decision"""
        entries = []

        # Collect from all components
        entries.extend(self.audit_trail.get_decision_history(decision_id))
        entries.extend(self.policy_engine.audit_trail.get_decision_history(decision_id))
        entries.extend(self.queue.audit_trail.get_decision_history(decision_id))
        entries.extend(self.escalation_engine.audit_trail.get_decision_history(decision_id))
        entries.extend(self.feedback_loop.audit_trail.get_decision_history(decision_id))

        # Sort by timestamp
        entries.sort(key=lambda e: e.timestamp)

        return [e.to_dict() for e in entries]

    def get_system_stats(self) -> dict[str, Any]:
        """Get comprehensive system statistics"""
        return {
            "timestamp": datetime.now().isoformat(),
            "routing_stats": self.policy_engine.get_statistics(),
            "queue_stats": self.queue.get_queue_stats(),
            "reviewer_stats": self.reviewer_pool.get_pool_stats(),
            "feedback_stats": self.feedback_loop.get_accuracy_metrics(),
            "drift_indicators": self.feedback_loop.get_model_drift_indicators(),
            "totals": {
                "total_decisions": len(self._decisions),
                "auto_approved": len(self._auto_approved),
                "auto_blocked": len(self._auto_blocked),
                "in_review": self.queue.get_pending_count() + self.queue.get_claimed_count()
            }
        }


# =============================================================================
# TEST CASES
# =============================================================================

def test_routing_decisions():
    """Test correct routing based on confidence and risk thresholds"""
    print("\n" + "=" * 60)
    print("TEST: Routing Decisions")
    print("=" * 60)

    router = HITLRouter()
    results = []

    # Test Case 1: High confidence, low risk -> AUTO_APPROVE
    decision1 = Decision(
        decision_id="test_001",
        decision_type="settlement",
        account_id="ACC001",
        payload={"amount": 150.00},
        confidence=0.96,
        risk_score=0.10,
        uncertainty=0.05,
        model_version="v1.0"
    )
    routing1 = router.route(decision1)
    result1 = routing1 == RoutingDecision.AUTO_APPROVE
    results.append(("High confidence (96%), low risk (10%) -> AUTO_APPROVE", result1))
    print(f"  [{'PASS' if result1 else 'FAIL'}] {results[-1][0]}")
    print(f"         Actual: {routing1.value}, Reason: {decision1.routing_reason}")

    # Test Case 2: High risk -> AUTO_BLOCK
    decision2 = Decision(
        decision_id="test_002",
        decision_type="settlement",
        account_id="ACC002",
        payload={"amount": 200.00},
        confidence=0.90,
        risk_score=0.80,
        uncertainty=0.10,
        model_version="v1.0"
    )
    routing2 = router.route(decision2)
    result2 = routing2 == RoutingDecision.AUTO_BLOCK
    results.append(("High risk (80%) -> AUTO_BLOCK", result2))
    print(f"  [{'PASS' if result2 else 'FAIL'}] {results[-1][0]}")
    print(f"         Actual: {routing2.value}, Reason: {decision2.routing_reason}")

    # Test Case 3: Low confidence -> AUTO_BLOCK
    decision3 = Decision(
        decision_id="test_003",
        decision_type="settlement",
        account_id="ACC003",
        payload={"amount": 100.00},
        confidence=0.35,
        risk_score=0.20,
        uncertainty=0.30,
        model_version="v1.0"
    )
    routing3 = router.route(decision3)
    result3 = routing3 == RoutingDecision.AUTO_BLOCK
    results.append(("Low confidence (35%) -> AUTO_BLOCK", result3))
    print(f"  [{'PASS' if result3 else 'FAIL'}] {results[-1][0]}")
    print(f"         Actual: {routing3.value}, Reason: {decision3.routing_reason}")

    # Test Case 4: Medium confidence -> HITL_REVIEW
    decision4 = Decision(
        decision_id="test_004",
        decision_type="settlement",
        account_id="ACC004",
        payload={"amount": 250.00},
        confidence=0.70,
        risk_score=0.30,
        uncertainty=0.20,
        model_version="v1.0"
    )
    routing4 = router.route(decision4)
    result4 = routing4 == RoutingDecision.HITL_REVIEW
    results.append(("Medium confidence (70%) -> HITL_REVIEW", result4))
    print(f"  [{'PASS' if result4 else 'FAIL'}] {results[-1][0]}")
    print(f"         Actual: {routing4.value}, Reason: {decision4.routing_reason}")

    # Test Case 5: High uncertainty -> ESCALATE
    decision5 = Decision(
        decision_id="test_005",
        decision_type="settlement",
        account_id="ACC005",
        payload={"amount": 300.00},
        confidence=0.75,
        risk_score=0.25,
        uncertainty=0.45,
        model_version="v1.0"
    )
    routing5 = router.route(decision5)
    # Escalate routes to HITL_REVIEW but with escalation
    result5 = decision5.escalation_count > 0 or routing5 == RoutingDecision.ESCALATE
    results.append(("High uncertainty (45%) -> ESCALATE", result5))
    print(f"  [{'PASS' if result5 else 'FAIL'}] {results[-1][0]}")
    print(f"         Actual: {routing5.value}, Escalation count: {decision5.escalation_count}")

    # Test Case 6: High confidence but over amount limit -> HITL_REVIEW
    decision6 = Decision(
        decision_id="test_006",
        decision_type="settlement",
        account_id="ACC006",
        payload={"amount": 750.00},  # Over $500 limit
        confidence=0.96,
        risk_score=0.10,
        uncertainty=0.05,
        model_version="v1.0"
    )
    routing6 = router.route(decision6)
    result6 = routing6 == RoutingDecision.HITL_REVIEW
    results.append(("High confidence but over amount limit ($750) -> HITL_REVIEW", result6))
    print(f"  [{'PASS' if result6 else 'FAIL'}] {results[-1][0]}")
    print(f"         Actual: {routing6.value}, Reason: {decision6.routing_reason}")

    passed = sum(1 for _, r in results if r)
    print(f"\n  Results: {passed}/{len(results)} tests passed")

    return all(r for _, r in results)


def test_audit_trail_creation():
    """Test complete audit trail creation for decisions"""
    print("\n" + "=" * 60)
    print("TEST: Audit Trail Creation")
    print("=" * 60)

    router = HITLRouter()

    # Add a reviewer
    reviewer = Reviewer(
        reviewer_id="REV001",
        name="John Smith",
        email="john@example.com",
        can_review=["settlement", "payment_plan"],
        max_authority_amount=1000.0
    )
    router.reviewer_pool.add_reviewer(reviewer)

    # Create and route a decision
    decision = Decision(
        decision_id="audit_test_001",
        decision_type="settlement",
        account_id="ACC_AUDIT",
        payload={"amount": 200.00, "settlement_percent": 0.60},
        confidence=0.72,
        risk_score=0.25,
        uncertainty=0.18,
        model_version="v1.0"
    )

    # Route decision
    routing = router.route(decision)
    print(f"  Decision routed: {routing.value}")

    # Claim decision
    claimed = router.claim_next("REV001")
    print(f"  Decision claimed: {claimed is not None}")

    # Resolve decision
    resolved = router.resolve_review(
        "audit_test_001",
        ReviewOutcome.APPROVED,
        "Settlement amount is reasonable given account history"
    )
    print(f"  Decision resolved: {resolved}")

    # Record feedback
    router.record_feedback("audit_test_001", "paid")
    print(f"  Feedback recorded")

    # Get audit trail
    audit_trail = router.get_decision_audit_trail("audit_test_001")

    print(f"\n  Audit Trail Entries: {len(audit_trail)}")

    expected_events = [
        "routing_initiated",
        "routing_started",
        "routing_completed",
        "queue_add",
        "queued_for_review",
        "queue_claim",
        "queue_resolve",
        "review_completed",
        "feedback_recorded"
    ]

    actual_events = [entry["event_type"] for entry in audit_trail]

    results = []
    for event in expected_events:
        found = event in actual_events
        results.append((f"Event '{event}' in audit trail", found))
        print(f"  [{'PASS' if found else 'FAIL'}] {results[-1][0]}")

    # Verify audit trail completeness
    print("\n  Sample Audit Entry:")
    if audit_trail:
        sample = audit_trail[0]
        print(f"    Entry ID: {sample['entry_id']}")
        print(f"    Timestamp: {sample['timestamp']}")
        print(f"    Event Type: {sample['event_type']}")
        print(f"    Actor: {sample['actor']}")
        print(f"    Action: {sample['action']}")

    passed = sum(1 for _, r in results if r)
    print(f"\n  Results: {passed}/{len(results)} tests passed")

    return all(r for _, r in results)


def test_queue_management():
    """Test HITL queue operations"""
    print("\n" + "=" * 60)
    print("TEST: Queue Management")
    print("=" * 60)

    queue = HITLQueue()
    results = []

    # Create decisions with different priorities
    decisions = [
        Decision(
            decision_id=f"queue_test_{i}",
            decision_type="settlement",
            account_id=f"ACC_Q{i}",
            payload={"amount": 100 + i * 50},
            confidence=0.70,
            risk_score=0.25,
            uncertainty=0.15,
            model_version="v1.0",
            routing_decision=RoutingDecision.HITL_REVIEW,
            priority=priority,
            sla_deadline=datetime.now() + timedelta(hours=hours)
        )
        for i, (priority, hours) in enumerate([
            (ReviewPriority.LOW, 72),
            (ReviewPriority.MEDIUM, 24),
            (ReviewPriority.HIGH, 4),
            (ReviewPriority.CRITICAL, 1)
        ])
    ]

    # Add all to queue
    for d in decisions:
        d.routed_at = datetime.now()
        queue.add(d)

    result1 = queue.get_pending_count() == 4
    results.append(("Add 4 decisions to queue", result1))
    print(f"  [{'PASS' if result1 else 'FAIL'}] {results[-1][0]}")

    # Claim highest priority (should be CRITICAL)
    claimed = queue.claim("reviewer_1")
    result2 = claimed is not None and claimed.priority == ReviewPriority.CRITICAL
    results.append(("Claim returns CRITICAL priority first", result2))
    print(f"  [{'PASS' if result2 else 'FAIL'}] {results[-1][0]}")
    print(f"         Claimed priority: {claimed.priority.name if claimed else 'None'}")

    # Verify queue state
    result3 = queue.get_pending_count() == 3 and queue.get_claimed_count() == 1
    results.append(("Queue counts updated after claim", result3))
    print(f"  [{'PASS' if result3 else 'FAIL'}] {results[-1][0]}")

    # Resolve claimed decision
    resolved = queue.resolve(claimed.decision_id, ReviewOutcome.APPROVED, "Test resolution")
    result4 = resolved and queue.get_claimed_count() == 0
    results.append(("Resolve removes from claimed", result4))
    print(f"  [{'PASS' if result4 else 'FAIL'}] {results[-1][0]}")

    # Test release
    claimed2 = queue.claim("reviewer_2")
    released = queue.release(claimed2.decision_id, "Need more info")
    result5 = released and queue.get_pending_count() == 3
    results.append(("Release returns to pending queue", result5))
    print(f"  [{'PASS' if result5 else 'FAIL'}] {results[-1][0]}")

    # Get stats
    stats = queue.get_queue_stats()
    result6 = stats["pending_count"] == 3 and stats["resolved_count"] == 1
    results.append(("Queue stats accurate", result6))
    print(f"  [{'PASS' if result6 else 'FAIL'}] {results[-1][0]}")

    passed = sum(1 for _, r in results if r)
    print(f"\n  Results: {passed}/{len(results)} tests passed")

    return all(r for _, r in results)


def test_reviewer_load_balancing():
    """Test reviewer assignment and load balancing"""
    print("\n" + "=" * 60)
    print("TEST: Reviewer Load Balancing")
    print("=" * 60)

    pool = ReviewerPool()
    results = []

    # Add reviewers with different capacities
    reviewers = [
        Reviewer(
            reviewer_id="REV_A",
            name="Alice",
            email="alice@example.com",
            can_review=["settlement"],
            max_authority_amount=500.0,
            current_load=0,
            max_load=5,
            accuracy_rate=0.95
        ),
        Reviewer(
            reviewer_id="REV_B",
            name="Bob",
            email="bob@example.com",
            can_review=["settlement", "payment_plan"],
            max_authority_amount=1000.0,
            current_load=2,
            max_load=5,
            accuracy_rate=0.90
        ),
        Reviewer(
            reviewer_id="REV_C",
            name="Charlie",
            email="charlie@example.com",
            can_review=["settlement"],
            max_authority_amount=500.0,
            current_load=4,
            max_load=5,
            accuracy_rate=0.98
        )
    ]

    for r in reviewers:
        pool.add_reviewer(r)

    # Test: Should select Alice (lowest load)
    decision1 = Decision(
        decision_id="lb_test_1",
        decision_type="settlement",
        account_id="ACC_LB1",
        payload={"amount": 200.00},
        confidence=0.70,
        risk_score=0.25,
        uncertainty=0.15,
        model_version="v1.0"
    )

    best = pool.get_best_reviewer(decision1)
    result1 = best is not None and best.reviewer_id == "REV_A"
    results.append(("Selects reviewer with lowest load (Alice)", result1))
    print(f"  [{'PASS' if result1 else 'FAIL'}] {results[-1][0]}")
    print(f"         Selected: {best.name if best else 'None'} (load: {best.current_load if best else 'N/A'})")

    # Test: High amount requires Bob (higher authority)
    decision2 = Decision(
        decision_id="lb_test_2",
        decision_type="settlement",
        account_id="ACC_LB2",
        payload={"amount": 750.00},  # Over Alice's limit
        confidence=0.70,
        risk_score=0.25,
        uncertainty=0.15,
        model_version="v1.0"
    )

    best2 = pool.get_best_reviewer(decision2)
    result2 = best2 is not None and best2.reviewer_id == "REV_B"
    results.append(("High amount routed to higher authority (Bob)", result2))
    print(f"  [{'PASS' if result2 else 'FAIL'}] {results[-1][0]}")
    print(f"         Selected: {best2.name if best2 else 'None'} (authority: ${best2.max_authority_amount if best2 else 'N/A'})")

    # Test: Unavailable reviewer not selected
    pool.update_status("REV_A", ReviewerStatus.OFFLINE)
    best3 = pool.get_best_reviewer(decision1)
    result3 = best3 is not None and best3.reviewer_id != "REV_A"
    results.append(("Offline reviewer not selected", result3))
    print(f"  [{'PASS' if result3 else 'FAIL'}] {results[-1][0]}")

    # Test: Pool stats
    stats = pool.get_pool_stats()
    result4 = stats["total_reviewers"] == 3 and stats["available_reviewers"] == 2
    results.append(("Pool stats accurate", result4))
    print(f"  [{'PASS' if result4 else 'FAIL'}] {results[-1][0]}")

    passed = sum(1 for _, r in results if r)
    print(f"\n  Results: {passed}/{len(results)} tests passed")

    return all(r for _, r in results)


def test_sla_tracking():
    """Test SLA deadline tracking and escalation"""
    print("\n" + "=" * 60)
    print("TEST: SLA Tracking")
    print("=" * 60)

    router = HITLRouter()
    results = []

    # Create decision with past SLA deadline
    decision = Decision(
        decision_id="sla_test_001",
        decision_type="settlement",
        account_id="ACC_SLA",
        payload={"amount": 200.00},
        confidence=0.70,
        risk_score=0.25,
        uncertainty=0.15,
        model_version="v1.0",
        routing_decision=RoutingDecision.HITL_REVIEW,
        priority=ReviewPriority.CRITICAL,
        sla_deadline=datetime.now() - timedelta(hours=1)  # Already breached
    )
    decision.routed_at = datetime.now() - timedelta(hours=2)
    router.queue.add(decision)
    router._decisions[decision.decision_id] = decision

    # Check for SLA breach
    result1 = decision.is_sla_breached()
    results.append(("Detects SLA breach", result1))
    print(f"  [{'PASS' if result1 else 'FAIL'}] {results[-1][0]}")

    # Get breaches
    breaches = router.queue.get_sla_breaches()
    result2 = len(breaches) == 1 and breaches[0].decision_id == "sla_test_001"
    results.append(("get_sla_breaches returns breached decisions", result2))
    print(f"  [{'PASS' if result2 else 'FAIL'}] {results[-1][0]}")

    # Trigger escalation check
    router.check_sla_breaches()
    result3 = decision.escalation_count > 0
    results.append(("SLA breach triggers escalation", result3))
    print(f"  [{'PASS' if result3 else 'FAIL'}] {results[-1][0]}")
    print(f"         Escalation count: {decision.escalation_count}")

    passed = sum(1 for _, r in results if r)
    print(f"\n  Results: {passed}/{len(results)} tests passed")

    return all(r for _, r in results)


def test_feedback_loop():
    """Test feedback recording and accuracy tracking"""
    print("\n" + "=" * 60)
    print("TEST: Feedback Loop")
    print("=" * 60)

    feedback = FeedbackLoop()
    results = []

    # Create decisions with various outcomes
    test_cases = [
        (RoutingDecision.AUTO_APPROVE, "paid", True),
        (RoutingDecision.AUTO_APPROVE, "default", False),
        (RoutingDecision.AUTO_BLOCK, "fraud", True),
        (RoutingDecision.AUTO_BLOCK, "paid", False),
        (RoutingDecision.HITL_REVIEW, "settled", True),
    ]

    for i, (routing, outcome, expected_correct) in enumerate(test_cases):
        decision = Decision(
            decision_id=f"fb_test_{i}",
            decision_type="settlement",
            account_id=f"ACC_FB{i}",
            payload={"amount": 100.00},
            confidence=0.80,
            risk_score=0.20,
            uncertainty=0.10,
            model_version="v1.0",
            routing_decision=routing,
            review_outcome=ReviewOutcome.APPROVED if routing == RoutingDecision.HITL_REVIEW else None
        )

        feedback.record_outcome(decision, outcome, datetime.now())

    # Check accuracy metrics
    metrics = feedback.get_accuracy_metrics()
    result1 = metrics["total"] == 5
    results.append(("Records all feedback", result1))
    print(f"  [{'PASS' if result1 else 'FAIL'}] {results[-1][0]}")
    print(f"         Total records: {metrics['total']}")

    result2 = metrics["accuracy"] == 0.6  # 3 correct out of 5
    results.append(("Calculates accuracy correctly (60%)", result2))
    print(f"  [{'PASS' if result2 else 'FAIL'}] {results[-1][0]}")
    print(f"         Calculated accuracy: {metrics['accuracy']:.0%}")

    # Check by-routing breakdown
    result3 = "auto_approve" in metrics["by_routing"]
    results.append(("Tracks accuracy by routing type", result3))
    print(f"  [{'PASS' if result3 else 'FAIL'}] {results[-1][0]}")

    passed = sum(1 for _, r in results if r)
    print(f"\n  Results: {passed}/{len(results)} tests passed")

    return all(r for _, r in results)


def test_conservative_policy():
    """Test conservative decision policy enforcement"""
    print("\n" + "=" * 60)
    print("TEST: Conservative Policy Enforcement")
    print("=" * 60)

    results = []

    # Test with conservative mode enabled (default)
    conservative_router = HITLRouter(PolicyThresholds(conservative_mode=True))

    # 90% confidence should go to HITL in conservative mode
    decision1 = Decision(
        decision_id="cons_test_1",
        decision_type="settlement",
        account_id="ACC_CONS1",
        payload={"amount": 200.00},
        confidence=0.90,  # High but not 95%+
        risk_score=0.10,
        uncertainty=0.08,
        model_version="v1.0"
    )
    routing1 = conservative_router.route(decision1)
    result1 = routing1 == RoutingDecision.HITL_REVIEW
    results.append(("Conservative mode: 90% confidence -> HITL", result1))
    print(f"  [{'PASS' if result1 else 'FAIL'}] {results[-1][0]}")
    print(f"         Routing: {routing1.value}")

    # 96% confidence should auto-approve even in conservative mode
    decision2 = Decision(
        decision_id="cons_test_2",
        decision_type="settlement",
        account_id="ACC_CONS2",
        payload={"amount": 200.00},
        confidence=0.96,  # Very high
        risk_score=0.10,
        uncertainty=0.05,
        model_version="v1.0"
    )
    routing2 = conservative_router.route(decision2)
    result2 = routing2 == RoutingDecision.AUTO_APPROVE
    results.append(("Conservative mode: 96% confidence -> AUTO_APPROVE", result2))
    print(f"  [{'PASS' if result2 else 'FAIL'}] {results[-1][0]}")
    print(f"         Routing: {routing2.value}")

    # Test with conservative mode disabled
    liberal_router = HITLRouter(PolicyThresholds(conservative_mode=False))

    decision3 = Decision(
        decision_id="cons_test_3",
        decision_type="settlement",
        account_id="ACC_CONS3",
        payload={"amount": 200.00},
        confidence=0.90,  # Should auto-approve without conservative mode
        risk_score=0.10,
        uncertainty=0.08,
        model_version="v1.0"
    )
    routing3 = liberal_router.route(decision3)
    result3 = routing3 == RoutingDecision.AUTO_APPROVE
    results.append(("Non-conservative mode: 90% confidence -> AUTO_APPROVE", result3))
    print(f"  [{'PASS' if result3 else 'FAIL'}] {results[-1][0]}")
    print(f"         Routing: {routing3.value}")

    passed = sum(1 for _, r in results if r)
    print(f"\n  Results: {passed}/{len(results)} tests passed")

    return all(r for _, r in results)


def test_policy_document_generation():
    """Test policy document generation"""
    print("\n" + "=" * 60)
    print("TEST: Policy Document Generation")
    print("=" * 60)

    router = HITLRouter()
    results = []

    # Generate policy document
    doc = router.generate_policy_document()

    result1 = doc.document_id is not None and len(doc.document_id) > 0
    results.append(("Document ID generated", result1))
    print(f"  [{'PASS' if result1 else 'FAIL'}] {results[-1][0]}")

    result2 = len(doc.decision_rules) >= 5
    results.append(("Contains decision rules", result2))
    print(f"  [{'PASS' if result2 else 'FAIL'}] {results[-1][0]}")
    print(f"         Rules count: {len(doc.decision_rules)}")

    result3 = len(doc.escalation_paths) >= 4
    results.append(("Contains escalation paths", result3))
    print(f"  [{'PASS' if result3 else 'FAIL'}] {results[-1][0]}")

    result4 = len(doc.reviewer_guidelines) >= 5
    results.append(("Contains reviewer guidelines", result4))
    print(f"  [{'PASS' if result4 else 'FAIL'}] {results[-1][0]}")

    # Test export formats
    doc_dict = doc.to_dict()
    result5 = "thresholds" in doc_dict and "decision_rules" in doc_dict
    results.append(("Exports to dict correctly", result5))
    print(f"  [{'PASS' if result5 else 'FAIL'}] {results[-1][0]}")

    markdown = doc.to_markdown()
    result6 = "# HITL Policy Document" in markdown and "Auto-Approve Confidence" in markdown
    results.append(("Exports to markdown correctly", result6))
    print(f"  [{'PASS' if result6 else 'FAIL'}] {results[-1][0]}")

    passed = sum(1 for _, r in results if r)
    print(f"\n  Results: {passed}/{len(results)} tests passed")

    return all(r for _, r in results)


def run_all_tests():
    """Run all test cases"""
    print("\n" + "=" * 60)
    print("HITL ROUTING SYSTEM - TEST SUITE")
    print("=" * 60)

    test_functions = [
        ("Routing Decisions", test_routing_decisions),
        ("Audit Trail Creation", test_audit_trail_creation),
        ("Queue Management", test_queue_management),
        ("Reviewer Load Balancing", test_reviewer_load_balancing),
        ("SLA Tracking", test_sla_tracking),
        ("Feedback Loop", test_feedback_loop),
        ("Conservative Policy", test_conservative_policy),
        ("Policy Document Generation", test_policy_document_generation),
    ]

    all_passed = True
    summary = []

    for name, test_fn in test_functions:
        try:
            passed = test_fn()
            summary.append((name, passed))
            if not passed:
                all_passed = False
        except Exception as e:
            print(f"\n  ERROR in {name}: {e}")
            summary.append((name, False))
            all_passed = False

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for name, passed in summary:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")

    total_passed = sum(1 for _, p in summary if p)
    print(f"\n  Overall: {total_passed}/{len(summary)} test suites passed")

    if all_passed:
        print("\n  All tests PASSED!")
    else:
        print("\n  Some tests FAILED!")

    return all_passed


# =============================================================================
# DEMONSTRATION
# =============================================================================

if __name__ == "__main__":
    # Run all tests
    run_all_tests()

    print("\n" + "=" * 60)
    print("DEMONSTRATION: Complete HITL Workflow")
    print("=" * 60)

    # Initialize router with custom thresholds
    thresholds = PolicyThresholds(
        auto_approve_confidence=0.85,
        hitl_lower_bound=0.50,
        hitl_upper_bound=0.85,
        risk_block_threshold=0.75,
        conservative_mode=True,
        max_auto_approve_amount=500.00
    )

    router = HITLRouter(thresholds)

    # Add reviewers
    reviewers = [
        Reviewer(
            reviewer_id="REVIEW_001",
            name="Sarah Johnson",
            email="sarah@quan.com",
            can_review=["settlement", "payment_plan", "contact"],
            max_authority_amount=1000.0
        ),
        Reviewer(
            reviewer_id="REVIEW_002",
            name="Mike Chen",
            email="mike@quan.com",
            can_review=["settlement", "payment_plan"],
            max_authority_amount=500.0
        )
    ]

    for r in reviewers:
        router.reviewer_pool.add_reviewer(r)

    print("\n1. Processing Sample Decisions...")

    # Process various decisions
    sample_decisions = [
        {"id": "D001", "conf": 0.97, "risk": 0.08, "unc": 0.03, "amt": 150},  # Auto-approve
        {"id": "D002", "conf": 0.82, "risk": 0.15, "unc": 0.12, "amt": 300},  # HITL
        {"id": "D003", "conf": 0.45, "risk": 0.80, "unc": 0.25, "amt": 500},  # Block (high risk)
        {"id": "D004", "conf": 0.72, "risk": 0.22, "unc": 0.18, "amt": 200},  # HITL
        {"id": "D005", "conf": 0.35, "risk": 0.30, "unc": 0.35, "amt": 100},  # Block (low conf)
    ]

    for sd in sample_decisions:
        decision = Decision(
            decision_id=sd["id"],
            decision_type="settlement",
            account_id=f"ACC_{sd['id']}",
            payload={"amount": sd["amt"], "settlement_percent": 0.60},
            confidence=sd["conf"],
            risk_score=sd["risk"],
            uncertainty=sd["unc"],
            model_version="v2.1"
        )

        routing = router.route(decision)
        print(f"   {sd['id']}: conf={sd['conf']:.0%}, risk={sd['risk']:.0%} -> {routing.value}")

    print("\n2. System Statistics:")
    stats = router.get_system_stats()
    print(f"   Total decisions: {stats['totals']['total_decisions']}")
    print(f"   Auto-approved: {stats['totals']['auto_approved']}")
    print(f"   Auto-blocked: {stats['totals']['auto_blocked']}")
    print(f"   In review queue: {stats['totals']['in_review']}")

    print("\n3. Processing HITL Queue...")

    # Simulate reviewer workflow
    for _ in range(2):
        claimed = router.claim_next("REVIEW_001")
        if claimed:
            print(f"   Claimed: {claimed.decision_id} (priority: {claimed.priority.name})")
            router.resolve_review(
                claimed.decision_id,
                ReviewOutcome.APPROVED,
                "Manual review: approved based on account history"
            )
            router.record_feedback(claimed.decision_id, "paid")
            print(f"   Resolved: {claimed.decision_id} -> APPROVED")

    print("\n4. Generated Policy Document:")
    policy_doc = router.generate_policy_document()
    print(f"   Document ID: {policy_doc.document_id}")
    print(f"   Policy Version: {policy_doc.policy_version}")
    print(f"   Decision Rules: {len(policy_doc.decision_rules)}")
    print(f"   Escalation Paths: {len(policy_doc.escalation_paths)}")

    print("\n5. Sample Audit Trail (D002):")
    audit = router.get_decision_audit_trail("D002")
    for entry in audit[:5]:  # Show first 5 entries
        print(f"   [{entry['timestamp'][:19]}] {entry['event_type']}: {entry['action']}")

    print("\n" + "=" * 60)
    print("Demonstration complete.")
