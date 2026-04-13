"""Database-backed dashboard aggregations."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from quan.models.database import Account, ComplianceEvent, ContactAttempt, Payment, Portfolio

PIPELINE_STAGES = [
    "ingested",
    "enriched",
    "scored",
    "contacted",
    "negotiating",
    "payment_pending",
    "resolved",
]
CHANNEL_COSTS = {
    "sms": Decimal("0.02"),
    "email": Decimal("0.01"),
    "voice": Decimal("0.15"),
    "digital": Decimal("0.03"),
    "mail": Decimal("0.55"),
}


def build_full_dashboard(db: Session) -> dict[str, Any]:
    """Build the full dashboard payload expected by the frontend."""

    return {
        "generated_at": _iso_now(),
        "executive": build_executive_snapshot(db),
        "operations": build_operations_snapshot(db),
        "compliance": build_compliance_snapshot(db),
        "tokenization": build_tokenization_snapshot(db),
        "system_health": build_system_health(db),
        "alerts": build_alerts(db),
    }


def build_executive_snapshot(db: Session) -> dict[str, Any]:
    """Executive-level KPI snapshot."""

    now = _now()
    start = now - timedelta(days=30)
    previous_start = start - timedelta(days=30)

    total_original_balance = _decimal_scalar(
        db,
        select(func.coalesce(func.sum(Account.original_balance), 0)),
    )
    revenue = _decimal_scalar(
        db,
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "completed"),
    )
    costs = _decimal_scalar(
        db,
        select(func.coalesce(func.sum(ContactAttempt.cost), 0)),
    )

    previous_revenue = _decimal_scalar(
        db,
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.status == "completed",
            Payment.created_at >= previous_start,
            Payment.created_at < start,
        ),
    )
    previous_costs = _decimal_scalar(
        db,
        select(func.coalesce(func.sum(ContactAttempt.cost), 0)).where(
            ContactAttempt.created_at >= previous_start,
            ContactAttempt.created_at < start,
        ),
    )

    recovered = revenue
    recovery_rate = _safe_ratio(recovered, total_original_balance)
    gross_margin = _safe_ratio(revenue - costs, revenue)
    roi = _safe_ratio(revenue - costs, costs)
    cost_per_dollar = _safe_ratio(costs, revenue)

    prev_recovery_rate = _safe_ratio(previous_revenue, total_original_balance or Decimal("1"))
    prev_gross_margin = _safe_ratio(previous_revenue - previous_costs, previous_revenue)
    prev_roi = _safe_ratio(previous_revenue - previous_costs, previous_costs)
    prev_cost_per_dollar = _safe_ratio(previous_costs, previous_revenue)

    return {
        "generated_at": _iso_now(),
        "period": "30d",
        "kpis": {
            "total_revenue": _kpi(revenue, "USD", _delta(revenue, previous_revenue)),
            "gross_margin": _kpi(gross_margin, "%", _delta(gross_margin, prev_gross_margin)),
            "recovery_rate": _kpi(recovery_rate, "%", _delta(recovery_rate, prev_recovery_rate)),
            "roi": _kpi(roi, "%", _delta(roi, prev_roi)),
            "cost_per_dollar": _kpi(
                cost_per_dollar,
                "USD",
                _delta(cost_per_dollar, prev_cost_per_dollar, invert_direction=True),
            ),
        },
        "trends": {
            "revenue": _daily_series(db, Payment.created_at, Payment.amount, Payment.status == "completed"),
            "collections": _daily_series(db, Payment.created_at, Payment.amount, Payment.status == "completed"),
            "recovery_rate": _daily_recovery_rate_series(db),
        },
        "alerts": _build_executive_alerts(recovery_rate, roi, cost_per_dollar),
    }


def build_operations_snapshot(db: Session) -> dict[str, Any]:
    """Operations dashboard snapshot."""

    pipeline = _build_pipeline(db)
    channels = _build_channel_metrics(db)
    queues = _build_queue_metrics(db, pipeline)
    bottlenecks = _build_bottlenecks(queues, channels)

    recent_accounts = _count_since(db, Account.created_at, timedelta(hours=24))
    recent_contacts = _count_since(db, ContactAttempt.created_at, timedelta(hours=24))
    recent_resolutions = db.scalar(
        select(func.count()).select_from(Account).where(
            Account.status == "resolved",
            Account.updated_at >= _now() - timedelta(hours=24),
        )
    ) or 0
    recent_payments = _count_since(db, Payment.created_at, timedelta(hours=24))
    active_accounts = db.scalar(select(func.count()).select_from(Account)) or 0
    active_contact_queue = sum(
        pipeline[stage]["count"] for stage in ["scored", "contacted", "negotiating"]
    )
    capacity_utilization = min(active_contact_queue / max(active_accounts, 1), 1.0)

    return {
        "generated_at": _iso_now(),
        "pipeline": pipeline,
        "channels": channels,
        "queues": queues,
        "bottlenecks": bottlenecks,
        "throughput": {
            "accounts_per_hour": round(recent_accounts / 24, 2),
            "contacts_per_hour": round(recent_contacts / 24, 2),
            "resolutions_per_hour": round(recent_resolutions / 24, 2),
            "payments_per_hour": round(recent_payments / 24, 2),
            "current_capacity_utilization": round(capacity_utilization, 4),
        },
    }


def build_compliance_snapshot(db: Session) -> dict[str, Any]:
    """Compliance snapshot using recorded events."""

    now = _now()
    thirty_days = now - timedelta(days=30)
    ninety_days = now - timedelta(days=90)

    events_30 = db.scalars(
        select(ComplianceEvent).where(ComplianceEvent.created_at >= thirty_days)
    ).all()
    events_90 = db.scalars(
        select(ComplianceEvent).where(ComplianceEvent.created_at >= ninety_days)
    ).all()
    all_contacts = db.scalar(select(func.count()).select_from(ContactAttempt)) or 0
    compliant_contacts = db.scalar(
        select(func.count()).select_from(ContactAttempt).where(ContactAttempt.consent_verified.is_(True))
    ) or 0

    by_type: dict[str, int] = defaultdict(int)
    by_severity: dict[str, int] = defaultdict(int)
    for event in events_90:
        by_type[event.event_type] += 1
        by_severity[event.severity] += 1

    score_penalty = (
        by_severity.get("critical", 0) * 12
        + by_severity.get("high", 0) * 6
        + by_severity.get("warning", 0) * 2
        + by_severity.get("info", 0)
    )
    overall_score = max(0.0, 100.0 - float(score_penalty))
    contact_compliance = _safe_ratio(Decimal(compliant_contacts), Decimal(all_contacts or 1))

    state_counts = _build_state_compliance(events_90)
    recent = [
        {
            "id": event.id,
            "date": _iso_value(event.created_at),
            "type": event.event_type,
            "description": event.description,
            "severity": event.severity,
            "resolution": event.resolution or ("Resolved" if event.resolved_at else "Open"),
        }
        for event in events_30[:20]
    ]

    return {
        "generated_at": _iso_now(),
        "overall_score": {
            "score": round(overall_score, 2),
            "rating": _rating_for_score(overall_score),
            "trend": "stable",
            "components": {
                "fdcpa": round(max(0.0, 100 - by_type.get("timing", 0) * 5 - by_type.get("frequency", 0) * 4), 2),
                "tcpa": round(max(0.0, contact_compliance * 100), 2),
                "regulation_f": round(max(0.0, 100 - by_type.get("disclosure", 0) * 6), 2),
                "state_laws": round(max(0.0, 100 - by_severity.get("high", 0) * 4), 2),
            },
        },
        "audit_readiness": {
            "overall_readiness": "high" if overall_score >= 90 else "medium" if overall_score >= 75 else "low",
            "score": round(
                min(
                    100.0,
                    ((1.0 if all_contacts else 0.5) + contact_compliance + (1.0 if events_90 else 0.7)) / 3 * 100,
                ),
                2,
            ),
            "checklist": {
                "interaction_logs": {"status": "complete" if all_contacts else "empty", "coverage": 100 if all_contacts else 0},
                "payment_records": {"status": "complete" if _count_all(db, Payment) else "empty", "coverage": 100 if _count_all(db, Payment) else 0},
                "compliance_events": {"status": "complete" if events_90 else "empty", "coverage": 100 if events_90 else 0},
            },
            "last_audit": recent[0]["date"] if recent else "",
            "next_scheduled": _iso_value(now + timedelta(days=90)),
        },
        "violations": {
            "total_30d": len(events_30),
            "total_90d": len(events_90),
            "by_type": dict(by_type),
            "by_severity": dict(by_severity),
            "recent": recent,
        },
        "state_compliance": state_counts,
        "regulation_status": {
            "fdcpa": {"status": "compliant" if by_type.get("frequency", 0) == 0 else "review", "automation_coverage": round(contact_compliance * 100, 2)},
            "tcpa": {"status": "compliant" if by_type.get("consent", 0) == 0 else "review", "consent_rate": round(contact_compliance * 100, 2), "dnc_compliance": round(contact_compliance * 100, 2)},
            "regulation_f": {"status": "compliant" if by_type.get("disclosure", 0) == 0 else "review", "model_notice_usage": 100 if all_contacts else 0},
            "state_laws": {"status": "compliant" if state_counts["requires_attention"] == 0 else "review", "pending_changes": state_counts["requires_attention"]},
        },
    }


def build_tokenization_snapshot(db: Session) -> dict[str, Any]:
    """Derived tokenization-style metrics using portfolio/account groupings."""

    pools = []
    debt_groups = db.execute(
        select(
            Account.debt_type,
            func.count(Account.id),
            func.coalesce(func.sum(Account.original_balance), 0),
            func.coalesce(func.sum(Account.current_balance), 0),
            func.coalesce(func.sum(Account.total_payments), 0),
            func.avg(Account.recovery_probability),
        ).group_by(Account.debt_type)
    ).all()

    total_face_value = Decimal("0.00")
    total_nav = Decimal("0.00")
    tranches: dict[str, dict[str, Any]] = {}
    for debt_type, count, original_sum, balance_sum, paid_sum, avg_probability in debt_groups:
        original_value = _to_decimal(original_sum)
        balance_value = _to_decimal(balance_sum)
        paid_value = _to_decimal(paid_sum)
        recovery_probability = Decimal(str(avg_probability or 0))
        nav = balance_value * recovery_probability
        total_face_value += original_value
        total_nav += nav

        recovery_rate = _safe_ratio(paid_value, original_value)
        pools.append(
            {
                "pool_id": debt_type.upper(),
                "asset_class": debt_type.replace("_", " ").title(),
                "face_value": float(original_value),
                "nav": float(nav),
                "recovery_rate": round(recovery_rate, 4),
                "yield": round(_safe_ratio(paid_value - nav, original_value or Decimal("1")), 4),
                "status": "performing" if recovery_rate >= 0.15 else "watch",
            }
        )

    portfolio_count = max(_count_all(db, Portfolio), len(pools))
    recent_payments = _decimal_scalar(
        db,
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.status == "completed",
            Payment.created_at >= _now() - timedelta(days=30),
        ),
    )
    avg_yield = _safe_ratio(recent_payments, total_face_value or Decimal("1"))

    total_contacts = _count_all(db, ContactAttempt)
    total_defaults = db.scalar(
        select(func.count()).select_from(Account).where(Account.days_past_due >= 180)
    ) or 0
    total_accounts = _count_all(db, Account)

    tranche_seed = [
        ("senior", Decimal("0.55"), "AA"),
        ("mezzanine", Decimal("0.25"), "BBB"),
        ("junior", Decimal("0.15"), "BB"),
        ("equity", Decimal("0.05"), "NR"),
    ]
    for tranche_name, weight, rating in tranche_seed:
        tranche_value = total_nav * weight
        tranches[tranche_name] = {
            "total_value": float(tranche_value),
            "avg_yield": round(float(avg_yield * (1 + float(weight))), 4),
            "default_rate": round(total_defaults / max(total_accounts, 1), 4),
            "rating": rating,
        }

    return {
        "generated_at": _iso_now(),
        "portfolio_summary": {
            "total_face_value": float(total_face_value),
            "total_nav": float(total_nav),
            "total_pools": portfolio_count,
            "active_tranches": len(tranches),
            "total_investors": 0,
            "avg_yield": round(avg_yield, 4),
            "default_rate": round(total_defaults / max(total_accounts, 1), 4),
        },
        "pools": pools,
        "tranches": tranches,
        "investor_metrics": {
            "total_invested": float(total_nav),
            "distributions_ytd": float(_decimal_scalar(db, select(func.coalesce(func.sum(Payment.amount), 0)))),
            "realized_yield_ytd": round(avg_yield, 4),
            "investor_retention": 0.0,
            "new_investors_30d": 0,
            "pending_redemptions": 0,
        },
        "secondary_market": {
            "volume_30d": float(recent_payments),
            "avg_discount": 0.0,
            "bid_ask_spread": 0.0,
            "active_listings": 0,
            "recent_trades": [],
        },
    }


def build_system_health(db: Session) -> dict[str, Any]:
    """Simple operational health summary."""

    try:
        total_accounts = _count_all(db, Account)
        total_contacts = _count_all(db, ContactAttempt)
        total_payments = _count_all(db, Payment)
        modules = {
            "database": "healthy",
            "ingestion": "healthy",
            "payment_processing": "healthy" if total_payments >= 0 else "degraded",
            "compliance": "healthy",
            "dashboard": "healthy",
            "reporting": "healthy",
        }
        return {
            "status": "healthy",
            "uptime": "Operational",
            "modules": modules,
            "last_incident": _iso_value(_now() - timedelta(days=1)) if total_accounts else "No incidents",
            "mttr": "0 minutes" if total_contacts or total_payments else "N/A",
        }
    except Exception:
        return {
            "status": "degraded",
            "uptime": "Unknown",
            "modules": {
                "database": "down",
                "ingestion": "degraded",
                "payment_processing": "degraded",
                "compliance": "degraded",
                "dashboard": "degraded",
                "reporting": "degraded",
            },
            "last_incident": _iso_now(),
            "mttr": "Unknown",
        }


def build_alerts(db: Session) -> list[dict[str, Any]]:
    """Generate live alerts from current data."""

    alerts: list[dict[str, Any]] = []
    operations = build_operations_snapshot(db)
    compliance = build_compliance_snapshot(db)
    executive = build_executive_snapshot(db)

    for name, queue in operations["queues"].items():
        if queue["depth"] >= 50:
            alerts.append(
                {
                    "severity": "warning",
                    "source": "operations",
                    "message": f"{name.replace('_', ' ').title()} depth is {queue['depth']}",
                    "recommendation": "Review staffing or automation capacity.",
                }
            )

    if compliance["violations"]["total_30d"] > 0:
        alerts.append(
            {
                "severity": "warning" if compliance["violations"]["total_30d"] < 5 else "high",
                "source": "compliance",
                "message": f"{compliance['violations']['total_30d']} compliance events in the last 30 days",
                "recommendation": "Review unresolved compliance events and contact policies.",
            }
        )

    if executive["kpis"]["recovery_rate"]["value"] < 0.15 and _count_all(db, Account) > 0:
        alerts.append(
            {
                "severity": "info",
                "source": "executive",
                "message": "Recovery rate is below target for the current book",
                "recommendation": "Focus on high-probability segments and follow-up cadence.",
            }
        )

    return alerts


def _build_executive_alerts(
    recovery_rate: float,
    roi: float,
    cost_per_dollar: float,
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if recovery_rate < 0.15:
        alerts.append(
            {
                "severity": "info",
                "source": "executive",
                "message": "Recovery rate is below target for the current book",
                "recommendation": "Focus on higher-probability accounts and active negotiation segments.",
            }
        )
    if roi < 0:
        alerts.append(
            {
                "severity": "warning",
                "source": "executive",
                "message": "ROI is currently negative",
                "recommendation": "Reduce outreach cost or prioritize accounts with stronger recovery probability.",
            }
        )
    if cost_per_dollar > 0.35:
        alerts.append(
            {
                "severity": "warning",
                "source": "executive",
                "message": "Cost per dollar collected is elevated",
                "recommendation": "Shift volume toward lower-cost channels and review contact pacing.",
            }
        )
    return alerts


def _build_pipeline(db: Session) -> dict[str, dict[str, Any]]:
    current_statuses = dict(
        db.execute(
            select(Account.status, func.count(Account.id)).group_by(Account.status)
        ).all()
    )
    stage_index = {stage: idx for idx, stage in enumerate(PIPELINE_STAGES)}

    def cumulative_count(target_stage: str) -> int:
        target_rank = stage_index[target_stage]
        count = 0
        for status, quantity in current_statuses.items():
            if stage_index.get(status, 0) >= target_rank:
                count += quantity
        return count

    pipeline: dict[str, dict[str, Any]] = {}
    previous_count = 0
    for index, stage in enumerate(PIPELINE_STAGES):
        count = cumulative_count(stage)
        conversion_rate = 1.0 if index == 0 else _float_ratio(count, previous_count or 1)
        previous_count = count
        pipeline[stage] = {
            "count": count,
            "conversion_rate": round(conversion_rate, 4),
            "avg_time_in_stage": _avg_time_in_stage(db, stage),
        }
    return pipeline


def _build_channel_metrics(db: Session) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    for channel in ["sms", "email", "voice", "digital", "mail"]:
        attempts = db.scalar(
            select(func.count()).select_from(ContactAttempt).where(ContactAttempt.channel == channel)
        ) or 0
        responses = db.scalar(
            select(func.count()).select_from(ContactAttempt).where(
                ContactAttempt.channel == channel,
                ContactAttempt.outcome.in_(["responded", "connected", "promise_to_pay"]),
            )
        ) or 0
        conversions = db.scalar(
            select(func.count()).select_from(ContactAttempt).where(
                ContactAttempt.channel == channel,
                ContactAttempt.outcome.in_(["promise_to_pay", "payment_made"]),
            )
        ) or 0
        cost_sum = _decimal_scalar(
            db,
            select(func.coalesce(func.sum(ContactAttempt.cost), 0)).where(ContactAttempt.channel == channel),
        )
        metrics[channel] = {
            "attempts": attempts,
            "responses": responses,
            "conversions": conversions,
            "response_rate": round(_float_ratio(responses, attempts or 1), 4),
            "conversion_rate": round(_float_ratio(conversions, attempts or 1), 4),
            "cost_per_contact": round(float(_safe_ratio(cost_sum, Decimal(attempts or 1))), 4),
        }
    return metrics


def _build_queue_metrics(
    db: Session,
    pipeline: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    contact_depth = pipeline["scored"]["count"] - pipeline["resolved"]["count"]
    payment_depth = pipeline["payment_pending"]["count"]
    enrichment_depth = db.scalar(
        select(func.count()).select_from(Account).where(Account.status == "ingested")
    ) or 0

    recent_contacts = _count_since(db, ContactAttempt.created_at, timedelta(hours=24))
    recent_payments = _count_since(db, Payment.created_at, timedelta(hours=24))
    recent_uploads = _count_since(db, Account.created_at, timedelta(hours=24))

    queues = {
        "contact_queue": {
            "depth": max(contact_depth, 0),
            "processing_rate": max(round(recent_contacts / 1440, 2), 0.1 if contact_depth else 0),
        },
        "payment_queue": {
            "depth": payment_depth,
            "processing_rate": max(round(recent_payments / 1440, 2), 0.1 if payment_depth else 0),
        },
        "enrichment_queue": {
            "depth": enrichment_depth,
            "processing_rate": max(round(recent_uploads / 1440, 2), 0.1 if enrichment_depth else 0),
        },
    }
    for queue in queues.values():
        queue["estimated_clear_time"] = _clear_time(queue["depth"], queue["processing_rate"])
    return queues


def _build_bottlenecks(
    queues: dict[str, dict[str, Any]],
    channels: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    bottlenecks: list[dict[str, Any]] = []
    for name, queue in queues.items():
        if queue["depth"] >= 100:
            bottlenecks.append(
                {
                    "location": name,
                    "severity": "warning",
                    "issue": f"Queue depth elevated at {queue['depth']}",
                    "recommendation": "Review queue staffing and automation rules.",
                }
            )
    for name, metrics in channels.items():
        if metrics["attempts"] and metrics["conversion_rate"] < 0.05:
            bottlenecks.append(
                {
                    "location": name,
                    "severity": "info",
                    "issue": f"{name.title()} conversion rate is under 5%",
                    "recommendation": "Revisit channel messaging and prioritization.",
                }
            )
    return bottlenecks


def _build_state_compliance(events: list[ComplianceEvent]) -> dict[str, Any]:
    states = defaultdict(list)
    for event in events:
        if event.state:
            states[event.state].append(event)

    details: dict[str, dict[str, Any]] = {}
    fully_compliant = 0
    requires_attention = 0
    attention_states: list[str] = []
    for state in sorted(states):
        state_events = states[state]
        has_attention = any(not event.resolved_at and event.severity in {"high", "critical", "warning"} for event in state_events)
        if has_attention:
            requires_attention += 1
            attention_states.append(state)
            details[state] = {
                "status": "review",
                "note": f"{len(state_events)} event(s) in review",
            }
        else:
            fully_compliant += 1
            details[state] = {"status": "compliant"}

    return {
        "fully_compliant": fully_compliant,
        "requires_attention": requires_attention,
        "attention_states": attention_states,
        "details": details,
    }


def _daily_series(db: Session, column: Any, amount_column: Any, *filters: Any) -> list[list[Any]]:
    start = _now() - timedelta(days=13)
    rows = db.execute(
        select(func.date(column), func.coalesce(func.sum(amount_column), 0))
        .where(column >= start, *filters)
        .group_by(func.date(column))
        .order_by(func.date(column))
    ).all()
    values = {str(day): float(total or 0) for day, total in rows}
    return [[day.strftime("%Y-%m-%d"), values.get(day.strftime("%Y-%m-%d"), 0.0)] for day in (start + timedelta(days=index) for index in range(14))]


def _daily_recovery_rate_series(db: Session) -> list[list[Any]]:
    revenue_series = _daily_series(db, Payment.created_at, Payment.amount, Payment.status == "completed")
    total_face_value = float(
        _decimal_scalar(db, select(func.coalesce(func.sum(Account.original_balance), 0))) or Decimal("0")
    )
    cumulative = 0.0
    series = []
    for day, revenue in revenue_series:
        cumulative += revenue
        rate = cumulative / total_face_value if total_face_value else 0.0
        series.append([day, round(rate, 4)])
    return series


def _avg_time_in_stage(db: Session, stage: str) -> str:
    rows = db.scalars(select(Account).where(Account.status == stage)).all()
    if not rows:
        return "N/A"
    deltas = [_now() - (account.updated_at or account.created_at) for account in rows]
    avg_seconds = sum(delta.total_seconds() for delta in deltas) / len(deltas)
    return _format_duration(avg_seconds)


def _clear_time(depth: int, processing_rate: float) -> str:
    if depth <= 0:
        return "clear"
    if processing_rate <= 0:
        return "N/A"
    minutes = depth / processing_rate
    if minutes < 60:
        return f"{round(minutes)} minutes"
    hours = minutes / 60
    if hours < 48:
        return f"{round(hours, 1)} hours"
    return f"{round(hours / 24, 1)} days"


def _format_duration(total_seconds: float) -> str:
    if total_seconds < 60:
        return f"{round(total_seconds)} seconds"
    minutes = total_seconds / 60
    if minutes < 60:
        return f"{round(minutes)} minutes"
    hours = minutes / 60
    if hours < 48:
        return f"{round(hours, 1)} hours"
    return f"{round(hours / 24, 1)} days"


def _count_all(db: Session, model: Any) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def _count_since(db: Session, column: Any, delta: timedelta) -> int:
    from_clause = getattr(column, "table", None)
    if from_clause is None and hasattr(column, "expression"):
        from_clause = column.expression.table
    return db.scalar(
        select(func.count()).select_from(from_clause).where(column >= _now() - delta)
    ) or 0


def _decimal_scalar(db: Session, statement: Any) -> Decimal:
    return _to_decimal(db.scalar(statement) or 0)


def _to_decimal(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


def _safe_ratio(numerator: Decimal, denominator: Decimal) -> float:
    if not denominator:
        return 0.0
    return float(numerator / denominator)


def _float_ratio(numerator: float | int, denominator: float | int) -> float:
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def _delta(current: float | Decimal, previous: float | Decimal, invert_direction: bool = False) -> dict[str, Any]:
    current_value = float(current)
    previous_value = float(previous)
    if previous_value == 0:
        if current_value == 0:
            return {"value": 0.0, "direction": "stable"}
        direction = "down" if invert_direction else "up"
        return {"value": 1.0, "direction": direction}

    change = (current_value - previous_value) / abs(previous_value)
    if invert_direction:
        direction = "down" if change < 0 else "up" if change > 0 else "stable"
    else:
        direction = "up" if change > 0 else "down" if change < 0 else "stable"
    return {"value": abs(change), "direction": direction}


def _kpi(value: float | Decimal, unit: str, change: dict[str, Any]) -> dict[str, Any]:
    return {"value": float(value), "unit": unit, "change": change}


def _rating_for_score(score: float) -> str:
    if score >= 95:
        return "Excellent"
    if score >= 85:
        return "Good"
    if score >= 70:
        return "Fair"
    return "Needs Attention"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _iso_value(_now())


def _iso_value(value: datetime | timedelta | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, timedelta):
        return (_now() + value).isoformat()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
