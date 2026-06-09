# quan/api/recovery_router.py
"""
Recovery API — agent-assisted collection actions.

Provides endpoints for:
- Getting AI-recommended next actions for an account
- Executing agent-supervised outreach (draft → verify → optionally send)
- Compliance audit trail queries

All outreach passes through the ComplianceGuard kill-switch before execution.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from quan.database import get_db
from quan.logging_config import get_logger
from quan.models.database import Account, ComplianceEvent, ContactAttempt
from quan.utils import get_account_or_404, to_iso, utc_now, CONTACT_COSTS

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/recovery", tags=["Recovery"])


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------


class AgentActionRequest(BaseModel):
    """Request for AI-recommended action."""

    goal: str = Field(
        default="maximize recovery while maintaining compliance",
        description="The collection goal for this account",
    )


class OutreachRequest(BaseModel):
    """Request to generate and optionally send outreach."""

    channel: str = Field(..., pattern="^(sms|email|voice|mail|digital)$")
    goal: str = Field(
        default="initial_notice",
        description="Message goal: initial_notice, reminder, settlement_offer, etc.",
    )
    offer_pct: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Settlement offer percentage"
    )
    dry_run: bool = Field(
        default=True, description="If True, draft only; if False, send after compliance check"
    )


class AgentActionResponse(BaseModel):
    """Response with AI-recommended action."""

    account_id: str
    action: str
    reasoning: str
    payload: dict[str, Any]
    next_steps: list[str]
    ml_scores: dict[str, Any]
    compliance_status: str
    token_estimate: int


class OutreachResponse(BaseModel):
    """Response from outreach generation/execution."""

    account_id: str
    channel: str
    status: str  # "drafted", "approved", "sent", "blocked"
    message_text: str | None
    subject: str | None
    compliance_passed: bool
    violations: list[dict[str, Any]]
    warnings: list[str]
    contact_attempt_id: str | None = None


class ComplianceCheckRequest(BaseModel):
    """Request to check compliance of a proposed action."""

    action_type: str = Field(..., description="Type of action: outreach, settlement, etc.")
    channel: str | None = None
    message_text: str | None = None
    contact_time: datetime | None = None


class ComplianceCheckResponse(BaseModel):
    """Response from compliance check."""

    passed: bool
    violations: list[dict[str, Any]]
    warnings: list[str]
    rule_summary: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
#
# Each HTTP request is a single agent step: the supervisor gets a fresh
# ephemeral AgentSessionMemory (no persistence argument), so nothing is
# carried across requests.


@router.post("/{account_id}/suggest", response_model=AgentActionResponse)
async def get_suggested_action(
    account_id: str,
    request: AgentActionRequest,
    db: Session = Depends(get_db),
) -> AgentActionResponse:
    """
    Get AI-recommended next action for an account.

    Runs the QuannexSupervisor for one step without executing any action.
    Returns the recommendation with ML scores and compliance status.
    """
    account = get_account_or_404(db, account_id)

    # Convert ORM to dict for agent
    account_dict = _account_to_dict(account)

    # Run supervisor (lazy import to avoid circular deps)
    from quan.agents.supervisor import QuannexSupervisor
    from quan.agents.outreach_specialist import OutreachSpecialist

    supervisor = QuannexSupervisor()
    supervisor.register_specialist("outreach", OutreachSpecialist())

    try:
        result = await supervisor.step(account=account_dict, goal=request.goal)
    except Exception as e:
        logger.error(f"Supervisor error for {account_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Agent error: {str(e)}"
        )

    # Check if action would be compliant
    compliance_status = "pending"
    if result.action in ("outreach", "draft"):
        from quan.agents.compliance_guard import get_compliance_guard

        guard = get_compliance_guard()
        msg_text = result.payload.get("message_text", "")
        channel = result.payload.get("channel", "email")
        check = guard.check_outreach(msg_text, channel, account_dict)
        compliance_status = "compliant" if check.passed else "blocked"

    ml_cache = supervisor.memory.state.ml_cache
    ml_scores = {
        "account_id": ml_cache.account_id,
        "recovery_probability": ml_cache.recovery_probability,
        "settlement_threshold": ml_cache.settlement_threshold,
        "optimal_channels": ml_cache.optimal_channels,
        "confidence": ml_cache.confidence,
    }

    return AgentActionResponse(
        account_id=account_id,
        action=result.action,
        reasoning=result.reasoning,
        payload=result.payload,
        next_steps=result.next_steps,
        ml_scores=ml_scores,
        compliance_status=compliance_status,
        token_estimate=result.token_estimate,
    )


@router.post("/{account_id}/outreach", response_model=OutreachResponse)
async def generate_outreach(
    account_id: str,
    request: OutreachRequest,
    db: Session = Depends(get_db),
) -> OutreachResponse:
    """
    Generate compliant outreach for an account.

    By default (dry_run=True), only drafts the message and returns it.
    If dry_run=False and compliance passes, records the contact attempt.

    The ComplianceGuard kill-switch runs on ALL outputs, blocking any
    non-compliant message regardless of what the LLM generated.
    """
    account = get_account_or_404(db, account_id)
    account_dict = _account_to_dict(account)

    # Run outreach specialist directly
    from quan.agents.supervisor import QuannexSupervisor
    from quan.agents.outreach_specialist import OutreachSpecialist
    from quan.agents.compliance_guard import get_compliance_guard

    supervisor = QuannexSupervisor()
    outreach = OutreachSpecialist()
    supervisor.register_specialist("outreach", outreach)

    # Build payload for outreach
    payload = {
        "channel": request.channel,
        "account": account_dict,
        "goal": request.goal,
    }
    if request.offer_pct is not None:
        payload["offer_pct"] = request.offer_pct

    try:
        result = await outreach.execute(
            memory=supervisor.memory,
            payload=payload,
            llm=supervisor.llm,
        )
    except Exception as e:
        logger.error(f"Outreach error for {account_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Outreach generation error: {str(e)}")

    # If outreach was blocked at preflight
    if result.action == "block":
        return OutreachResponse(
            account_id=account_id,
            channel=request.channel,
            status="blocked",
            message_text=None,
            subject=None,
            compliance_passed=False,
            violations=[{"type": "preflight_block", "description": result.reasoning}],
            warnings=[],
        )

    # Run deterministic compliance guard (kill-switch)
    msg_text = result.payload.get("message_text", "")
    subject = result.payload.get("subject")
    guard = get_compliance_guard()
    check = guard.check_outreach(
        message_text=msg_text,
        channel=request.channel,
        account=account_dict,
        contact_time=utc_now() if not request.dry_run else None,
    )

    status = "drafted"
    contact_attempt_id = None

    if not check.passed:
        status = "blocked"
        # Log compliance event
        db.add(
            ComplianceEvent(
                event_id=str(uuid.uuid4()),
                account_db_id=account.id,
                event_type="outreach_blocked",
                severity="warning",
                message=f"Outreach blocked by compliance guard: {request.channel}",
                resolution="; ".join(v.description for v in check.violations),
                state=account.state,
                resolved=False,
            )
        )
        db.commit()
    elif not request.dry_run:
        # Compliance passed and not dry run — record the contact
        status = "sent"
        cost = CONTACT_COSTS.get(request.channel, Decimal("0.01"))
        attempt = ContactAttempt(
            attempt_id=str(uuid.uuid4()),
            account_db_id=account.id,
            channel=request.channel,
            outcome="message_sent",
            compliant=True,
            cost=cost,
            agent_name="quannex_agent",
            notes=f"Goal: {request.goal}; Subject: {subject or 'N/A'}",
        )
        db.add(attempt)

        # Update account rollups
        account.total_contact_attempts += 1
        account.last_contact_at = utc_now()
        if account.status in {"scored", "enriched", "ingested"}:
            account.status = "contacted"

        db.commit()
        db.refresh(attempt)
        contact_attempt_id = attempt.attempt_id
    else:
        status = "approved" if check.passed else "blocked"

    return OutreachResponse(
        account_id=account_id,
        channel=request.channel,
        status=status,
        message_text=msg_text,
        subject=subject,
        compliance_passed=check.passed,
        violations=[v.to_dict() if hasattr(v, "to_dict") else {
            "type": v.violation_type.value,
            "severity": v.severity,
            "rule": v.rule,
            "description": v.description,
        } for v in check.violations],
        warnings=check.warnings,
        contact_attempt_id=contact_attempt_id,
    )


@router.post("/{account_id}/compliance-check", response_model=ComplianceCheckResponse)
def check_compliance(
    account_id: str,
    request: ComplianceCheckRequest,
    db: Session = Depends(get_db),
) -> ComplianceCheckResponse:
    """
    Pre-check compliance for a proposed action without executing it.

    Useful for UI validation before submission.
    """
    account = get_account_or_404(db, account_id)
    account_dict = _account_to_dict(account)

    from quan.agents.compliance_guard import get_compliance_guard

    guard = get_compliance_guard()

    if request.action_type == "outreach" and request.message_text:
        check = guard.check_outreach(
            message_text=request.message_text,
            channel=request.channel or "email",
            account=account_dict,
            contact_time=request.contact_time,
        )
        rule_summary = "FDCPA § 1692, TCPA, Reg F"
    else:
        # For non-outreach, just check account flags
        violations = guard._check_account_flags(account_dict, request.channel or "email")
        check_passed = len(violations) == 0
        from quan.agents.compliance_guard import GuardResult
        check = GuardResult(passed=check_passed, violations=violations)
        rule_summary = "Account compliance flags"

    return ComplianceCheckResponse(
        passed=check.passed,
        violations=[{
            "type": v.violation_type.value,
            "severity": v.severity,
            "rule": v.rule,
            "description": v.description,
        } for v in check.violations],
        warnings=check.warnings,
        rule_summary=rule_summary,
    )


@router.get("/{account_id}/compliance-history")
def get_compliance_history(
    account_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Get compliance event history for an account.
    """
    account = get_account_or_404(db, account_id)

    events = (
        db.query(ComplianceEvent)
        .filter(ComplianceEvent.account_db_id == account.id)
        .order_by(ComplianceEvent.occurred_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "account_id": account_id,
        "total_events": len(events),
        "events": [
            {
                "event_id": e.event_id,
                "event_type": e.event_type,
                "severity": e.severity,
                "message": e.message,
                "resolution": e.resolution,
                "resolved": e.resolved,
                "occurred_at": to_iso(e.occurred_at),
            }
            for e in events
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _account_to_dict(account: Account) -> dict[str, Any]:
    """Convert ORM Account to dict for agent consumption."""
    return {
        "account_id": account.account_id,
        "debtor_name": account.debtor_name,
        "debtor_first_name": (account.debtor_name or "").split()[0] if account.debtor_name else None,
        "current_balance": float(account.balance),
        "balance": float(account.balance),
        "original_balance": float(account.original_balance),
        "original_creditor": account.original_creditor,
        "debt_type": account.debt_type,
        "days_past_due": account.days_past_due,
        "state": account.state,
        "phone": account.phone,
        "email": account.email,
        "status": account.status,
        "recovery_probability": account.recovery_probability,
        "optimal_channels": account.optimal_channels,
        "settlement_threshold": account.settlement_threshold,
        "total_paid": float(account.total_paid),
        "total_contact_attempts": account.total_contact_attempts,
        "last_contact_at": to_iso(account.last_contact_at),
        "last_payment_at": to_iso(account.last_payment_at),
        # Compliance flags (default False if not present)
        "do_not_call": getattr(account, "do_not_call", False),
        "do_not_email": getattr(account, "do_not_email", False),
        "do_not_mail": getattr(account, "do_not_mail", False),
        "bankruptcy_flag": getattr(account, "bankruptcy_flag", False),
        "deceased_flag": getattr(account, "deceased_flag", False),
        "disputed": getattr(account, "disputed", False),
        "attorney_represented": getattr(account, "attorney_represented", False),
        "statute_of_limitations_expired": getattr(account, "statute_of_limitations_expired", False),
    }
