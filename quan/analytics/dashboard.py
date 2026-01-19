"""
QUAN Analytics Dashboard

Comprehensive visibility into all system operations with real-time
metrics, historical trending, and predictive analytics.

Designed for:
1. Executive visibility (P&L, ROI, portfolio health)
2. Operations management (throughput, efficiency, bottlenecks)
3. Compliance monitoring (audit readiness, violation tracking)
4. Investor reporting (tokenization, tranche performance)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any
from collections import defaultdict
import json


class MetricType(Enum):
    """Types of metrics tracked"""
    COUNTER = auto()      # Cumulative count
    GAUGE = auto()        # Point-in-time value
    HISTOGRAM = auto()    # Distribution
    RATE = auto()         # Per-time-period rate
    PERCENTAGE = auto()   # Ratio as percentage


class TimeGranularity(Enum):
    """Time granularity for aggregations"""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


@dataclass
class Metric:
    """Single metric definition"""
    name: str
    metric_type: MetricType
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)
    dimensions: dict[str, str] = field(default_factory=dict)
    previous_value: float | None = None


@dataclass
class DashboardPanel:
    """Single dashboard panel configuration"""
    panel_id: str
    title: str
    metric_names: list[str]
    visualization_type: str  # line, bar, pie, gauge, table, kpi
    time_range: str  # 1h, 24h, 7d, 30d, custom
    dimensions: list[str] = field(default_factory=list)
    thresholds: dict[str, float] = field(default_factory=dict)


class MetricsStore:
    """
    In-memory metrics store with time-series capabilities

    Production would use InfluxDB, TimescaleDB, or similar
    """

    def __init__(self):
        self.current_values: dict[str, Metric] = {}
        self.time_series: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
        self.aggregations: dict[str, dict[str, float]] = {}

    def record(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        unit: str = "",
        dimensions: dict[str, str] | None = None
    ) -> None:
        """Record a metric value"""
        now = datetime.now()

        # Store current value
        metric = Metric(
            name=name,
            metric_type=metric_type,
            value=value,
            unit=unit,
            timestamp=now,
            dimensions=dimensions or {},
            previous_value=self.current_values.get(name, Metric(name, metric_type, 0, "")).value
        )
        self.current_values[name] = metric

        # Add to time series
        self.time_series[name].append((now, value))

        # Trim old data (keep last 7 days)
        cutoff = now - timedelta(days=7)
        self.time_series[name] = [
            (ts, v) for ts, v in self.time_series[name] if ts > cutoff
        ]

    def get(self, name: str) -> Metric | None:
        """Get current metric value"""
        return self.current_values.get(name)

    def get_series(
        self,
        name: str,
        start: datetime | None = None,
        end: datetime | None = None
    ) -> list[tuple[datetime, float]]:
        """Get time series data"""
        series = self.time_series.get(name, [])

        if start:
            series = [(ts, v) for ts, v in series if ts >= start]
        if end:
            series = [(ts, v) for ts, v in series if ts <= end]

        return series

    def aggregate(
        self,
        name: str,
        granularity: TimeGranularity,
        operation: str = "avg"  # avg, sum, min, max, count
    ) -> list[tuple[str, float]]:
        """Aggregate time series data"""
        series = self.time_series.get(name, [])
        if not series:
            return []

        buckets: dict[str, list[float]] = defaultdict(list)

        for ts, value in series:
            if granularity == TimeGranularity.MINUTE:
                key = ts.strftime("%Y-%m-%d %H:%M")
            elif granularity == TimeGranularity.HOUR:
                key = ts.strftime("%Y-%m-%d %H:00")
            elif granularity == TimeGranularity.DAY:
                key = ts.strftime("%Y-%m-%d")
            elif granularity == TimeGranularity.WEEK:
                key = ts.strftime("%Y-W%W")
            else:
                key = ts.strftime("%Y-%m")

            buckets[key].append(value)

        results = []
        for key, values in sorted(buckets.items()):
            if operation == "avg":
                agg = sum(values) / len(values)
            elif operation == "sum":
                agg = sum(values)
            elif operation == "min":
                agg = min(values)
            elif operation == "max":
                agg = max(values)
            else:  # count
                agg = len(values)
            results.append((key, agg))

        return results


class ExecutiveDashboard:
    """
    Executive-level dashboard for high-level KPIs

    Focus: Revenue, ROI, portfolio health, strategic metrics
    """

    def __init__(self, metrics_store: MetricsStore):
        self.metrics = metrics_store
        self.panels = self._create_panels()

    def _create_panels(self) -> list[DashboardPanel]:
        """Create executive dashboard panels"""
        return [
            DashboardPanel(
                panel_id="revenue_kpi",
                title="Revenue & Margin",
                metric_names=["total_revenue", "gross_margin", "net_margin"],
                visualization_type="kpi",
                time_range="30d"
            ),
            DashboardPanel(
                panel_id="portfolio_value",
                title="Portfolio Value",
                metric_names=["total_face_value", "total_recovery_value", "recovery_rate"],
                visualization_type="kpi",
                time_range="30d"
            ),
            DashboardPanel(
                panel_id="roi_trend",
                title="ROI Trending",
                metric_names=["roi_percent"],
                visualization_type="line",
                time_range="90d",
                thresholds={"target": 400, "minimum": 200}
            ),
            DashboardPanel(
                panel_id="unit_economics",
                title="Unit Economics",
                metric_names=["cost_per_dollar_collected", "cost_to_collect", "avg_recovery"],
                visualization_type="gauge",
                time_range="30d",
                thresholds={"cost_per_dollar": 0.25, "ctc": 0.50}
            ),
            DashboardPanel(
                panel_id="cash_flow",
                title="Cash Flow",
                metric_names=["daily_collections", "daily_costs", "net_cash_flow"],
                visualization_type="bar",
                time_range="30d"
            )
        ]

    def get_snapshot(self) -> dict[str, Any]:
        """Get executive dashboard snapshot"""
        return {
            "generated_at": datetime.now().isoformat(),
            "period": "30d",
            "kpis": self._calculate_kpis(),
            "trends": self._calculate_trends(),
            "alerts": self._check_alerts()
        }

    def _calculate_kpis(self) -> dict[str, Any]:
        """Calculate key performance indicators"""
        # Get current values (simulated for demo)
        total_revenue = self.metrics.get("total_revenue")
        total_cost = self.metrics.get("total_cost")
        total_collected = self.metrics.get("total_collected")
        total_face_value = self.metrics.get("total_face_value")

        revenue = total_revenue.value if total_revenue else 0
        cost = total_cost.value if total_cost else 0
        collected = total_collected.value if total_collected else 0
        face_value = total_face_value.value if total_face_value else 1

        return {
            "total_revenue": {
                "value": revenue,
                "unit": "USD",
                "change": self._calculate_change("total_revenue")
            },
            "gross_margin": {
                "value": (revenue - cost) / revenue if revenue > 0 else 0,
                "unit": "%",
                "change": self._calculate_change("gross_margin")
            },
            "recovery_rate": {
                "value": collected / face_value if face_value > 0 else 0,
                "unit": "%",
                "change": self._calculate_change("recovery_rate")
            },
            "roi": {
                "value": (collected - cost) / cost if cost > 0 else 0,
                "unit": "%",
                "change": self._calculate_change("roi")
            },
            "cost_per_dollar": {
                "value": cost / collected if collected > 0 else 0,
                "unit": "USD",
                "change": self._calculate_change("cost_per_dollar")
            }
        }

    def _calculate_trends(self) -> dict[str, list[tuple[str, float]]]:
        """Calculate trending data"""
        return {
            "revenue": self.metrics.aggregate("total_revenue", TimeGranularity.DAY, "sum"),
            "collections": self.metrics.aggregate("total_collected", TimeGranularity.DAY, "sum"),
            "recovery_rate": self.metrics.aggregate("recovery_rate", TimeGranularity.DAY, "avg")
        }

    def _calculate_change(self, metric_name: str) -> dict[str, Any]:
        """Calculate period-over-period change"""
        current = self.metrics.get(metric_name)
        if not current or current.previous_value is None:
            return {"value": 0, "direction": "flat"}

        if current.previous_value == 0:
            return {"value": 100 if current.value > 0 else 0, "direction": "up"}

        change = (current.value - current.previous_value) / current.previous_value
        direction = "up" if change > 0 else "down" if change < 0 else "flat"

        return {"value": abs(change), "direction": direction}

    def _check_alerts(self) -> list[dict[str, Any]]:
        """Check for alert conditions"""
        alerts = []

        # Check ROI threshold
        roi = self.metrics.get("roi")
        if roi and roi.value < 2.0:  # Less than 200% ROI
            alerts.append({
                "severity": "warning",
                "metric": "roi",
                "message": f"ROI at {roi.value:.0%}, below 200% target",
                "recommendation": "Review cost structure or settlement rates"
            })

        # Check cost per dollar
        cpd = self.metrics.get("cost_per_dollar")
        if cpd and cpd.value > 0.30:  # More than $0.30 per dollar
            alerts.append({
                "severity": "critical",
                "metric": "cost_per_dollar",
                "message": f"Cost per dollar at ${cpd.value:.2f}, above $0.30 threshold",
                "recommendation": "Increase automation, reduce manual intervention"
            })

        return alerts


class OperationsDashboard:
    """
    Operations dashboard for day-to-day management

    Focus: Throughput, efficiency, queue management, channel performance
    """

    def __init__(self, metrics_store: MetricsStore):
        self.metrics = metrics_store

    def get_snapshot(self) -> dict[str, Any]:
        """Get operations dashboard snapshot"""
        return {
            "generated_at": datetime.now().isoformat(),
            "pipeline": self._get_pipeline_status(),
            "channels": self._get_channel_performance(),
            "queues": self._get_queue_status(),
            "bottlenecks": self._identify_bottlenecks(),
            "throughput": self._get_throughput_metrics()
        }

    def _get_pipeline_status(self) -> dict[str, Any]:
        """Get status of each pipeline stage"""
        stages = [
            "ingested", "enriched", "scored", "contacted",
            "negotiating", "payment_pending", "resolved"
        ]

        status = {}
        for stage in stages:
            count_metric = self.metrics.get(f"accounts_{stage}")
            status[stage] = {
                "count": count_metric.value if count_metric else 0,
                "conversion_rate": self._get_stage_conversion(stage),
                "avg_time_in_stage": self._get_stage_duration(stage)
            }

        return status

    def _get_channel_performance(self) -> dict[str, Any]:
        """Get performance by channel"""
        channels = ["sms", "email", "voice", "digital"]

        performance = {}
        for channel in channels:
            performance[channel] = {
                "attempts": self.metrics.get(f"{channel}_attempts"),
                "responses": self.metrics.get(f"{channel}_responses"),
                "conversions": self.metrics.get(f"{channel}_conversions"),
                "response_rate": 0.15,  # Placeholder
                "conversion_rate": 0.08,  # Placeholder
                "cost_per_contact": 0.02 if channel == "sms" else 0.01 if channel == "email" else 0.15
            }

        return performance

    def _get_queue_status(self) -> dict[str, Any]:
        """Get queue depths and processing rates"""
        return {
            "contact_queue": {
                "depth": 15000,
                "processing_rate": 500,  # per minute
                "estimated_clear_time": "30 minutes"
            },
            "payment_queue": {
                "depth": 2500,
                "processing_rate": 100,
                "estimated_clear_time": "25 minutes"
            },
            "enrichment_queue": {
                "depth": 5000,
                "processing_rate": 1000,
                "estimated_clear_time": "5 minutes"
            }
        }

    def _identify_bottlenecks(self) -> list[dict[str, Any]]:
        """Identify current bottlenecks"""
        bottlenecks = []

        # Check queue depths
        queues = self._get_queue_status()
        for queue_name, queue_data in queues.items():
            if queue_data["depth"] > queue_data["processing_rate"] * 60:  # > 1 hour
                bottlenecks.append({
                    "location": queue_name,
                    "severity": "high",
                    "issue": f"Queue depth ({queue_data['depth']}) exceeds 1 hour capacity",
                    "recommendation": "Scale up processing or reduce inflow"
                })

        return bottlenecks

    def _get_throughput_metrics(self) -> dict[str, Any]:
        """Get throughput metrics"""
        return {
            "accounts_per_hour": 5000,
            "contacts_per_hour": 15000,
            "resolutions_per_hour": 500,
            "payments_per_hour": 200,
            "current_capacity_utilization": 0.72
        }

    def _get_stage_conversion(self, stage: str) -> float:
        """Get conversion rate for a stage"""
        # Would calculate from actual data
        conversions = {
            "ingested": 0.95,
            "enriched": 0.90,
            "scored": 0.88,
            "contacted": 0.35,
            "negotiating": 0.65,
            "payment_pending": 0.80,
            "resolved": 1.0
        }
        return conversions.get(stage, 0.5)

    def _get_stage_duration(self, stage: str) -> str:
        """Get average time in stage"""
        durations = {
            "ingested": "2 minutes",
            "enriched": "5 minutes",
            "scored": "1 minute",
            "contacted": "3 days",
            "negotiating": "7 days",
            "payment_pending": "14 days",
            "resolved": "N/A"
        }
        return durations.get(stage, "unknown")


class ComplianceDashboard:
    """
    Compliance dashboard for regulatory monitoring

    Focus: Audit readiness, violation tracking, state compliance
    """

    def __init__(self, metrics_store: MetricsStore):
        self.metrics = metrics_store

    def get_snapshot(self) -> dict[str, Any]:
        """Get compliance dashboard snapshot"""
        return {
            "generated_at": datetime.now().isoformat(),
            "overall_score": self._calculate_compliance_score(),
            "audit_readiness": self._assess_audit_readiness(),
            "violations": self._get_violations(),
            "state_compliance": self._get_state_compliance(),
            "regulation_status": self._get_regulation_status()
        }

    def _calculate_compliance_score(self) -> dict[str, Any]:
        """Calculate overall compliance score"""
        return {
            "score": 98.5,
            "rating": "Excellent",
            "trend": "stable",
            "components": {
                "fdcpa": 99.2,
                "tcpa": 97.8,
                "regulation_f": 99.0,
                "state_laws": 98.0
            }
        }

    def _assess_audit_readiness(self) -> dict[str, Any]:
        """Assess audit readiness"""
        return {
            "overall_readiness": "high",
            "score": 95,
            "checklist": {
                "interaction_logs": {"status": "complete", "coverage": 100},
                "consent_records": {"status": "complete", "coverage": 100},
                "disclosure_delivery": {"status": "complete", "coverage": 99.8},
                "dispute_handling": {"status": "complete", "coverage": 100},
                "call_recordings": {"status": "complete", "coverage": 98.5}
            },
            "last_audit": "2025-11-15",
            "next_scheduled": "2026-05-15"
        }

    def _get_violations(self) -> dict[str, Any]:
        """Get violation tracking"""
        return {
            "total_30d": 3,
            "total_90d": 8,
            "by_type": {
                "timing": 1,
                "disclosure": 1,
                "frequency": 1
            },
            "by_severity": {
                "critical": 0,
                "major": 1,
                "minor": 2
            },
            "recent": [
                {
                    "id": "V001",
                    "date": "2026-01-15",
                    "type": "timing",
                    "description": "Contact attempt at 8:58 PM (within 2 min of cutoff)",
                    "severity": "minor",
                    "resolution": "System clock sync adjusted"
                }
            ]
        }

    def _get_state_compliance(self) -> dict[str, Any]:
        """Get compliance status by state"""
        return {
            "fully_compliant": 47,
            "requires_attention": 3,
            "attention_states": ["CA", "NY", "MA"],
            "details": {
                "CA": {"status": "compliant", "license_expiry": "2026-06-30"},
                "NY": {"status": "review", "note": "New regulation effective 2026-03-01"},
                "MA": {"status": "compliant", "license_expiry": "2026-04-15"}
            }
        }

    def _get_regulation_status(self) -> dict[str, Any]:
        """Get status for each regulation"""
        return {
            "fdcpa": {
                "status": "compliant",
                "last_review": "2026-01-01",
                "automation_coverage": 100
            },
            "tcpa": {
                "status": "compliant",
                "consent_rate": 99.5,
                "dnc_compliance": 100
            },
            "regulation_f": {
                "status": "compliant",
                "7_in_7_compliance": 100,
                "model_notice_usage": 100
            },
            "cfpb_guidance": {
                "status": "monitoring",
                "pending_changes": 2
            }
        }


class TokenizationDashboard:
    """
    Tokenization dashboard for asset management

    Focus: Pool performance, tranche yields, NAV, investor metrics
    """

    def __init__(self, metrics_store: MetricsStore):
        self.metrics = metrics_store

    def get_snapshot(self) -> dict[str, Any]:
        """Get tokenization dashboard snapshot"""
        return {
            "generated_at": datetime.now().isoformat(),
            "portfolio_summary": self._get_portfolio_summary(),
            "pools": self._get_pool_performance(),
            "tranches": self._get_tranche_performance(),
            "investor_metrics": self._get_investor_metrics(),
            "secondary_market": self._get_secondary_market()
        }

    def _get_portfolio_summary(self) -> dict[str, Any]:
        """Get overall portfolio summary"""
        return {
            "total_face_value": 25000000,
            "total_nav": 18500000,
            "total_pools": 12,
            "active_tranches": 48,
            "total_investors": 156,
            "avg_yield": 0.18,
            "default_rate": 0.12
        }

    def _get_pool_performance(self) -> list[dict[str, Any]]:
        """Get performance by pool"""
        return [
            {
                "pool_id": "BNPL-2026-Q1",
                "asset_class": "BNPL Subprime",
                "face_value": 5000000,
                "nav": 3750000,
                "recovery_rate": 0.52,
                "yield": 0.22,
                "status": "performing"
            },
            {
                "pool_id": "SUB-2026-Q1",
                "asset_class": "Subscriptions",
                "face_value": 2000000,
                "nav": 1400000,
                "recovery_rate": 0.48,
                "yield": 0.19,
                "status": "performing"
            },
            {
                "pool_id": "MIXED-2025-Q4",
                "asset_class": "Mixed Micro",
                "face_value": 3500000,
                "nav": 2450000,
                "recovery_rate": 0.45,
                "yield": 0.17,
                "status": "performing"
            }
        ]

    def _get_tranche_performance(self) -> dict[str, Any]:
        """Get performance by tranche type"""
        return {
            "senior": {
                "total_value": 12000000,
                "avg_yield": 0.10,
                "default_rate": 0.02,
                "rating": "AA"
            },
            "mezzanine": {
                "total_value": 5000000,
                "avg_yield": 0.18,
                "default_rate": 0.08,
                "rating": "BBB"
            },
            "junior": {
                "total_value": 2000000,
                "avg_yield": 0.28,
                "default_rate": 0.15,
                "rating": "BB"
            },
            "equity": {
                "total_value": 1000000,
                "avg_yield": 0.42,
                "default_rate": 0.25,
                "rating": "NR"
            }
        }

    def _get_investor_metrics(self) -> dict[str, Any]:
        """Get investor-level metrics"""
        return {
            "total_invested": 18000000,
            "distributions_ytd": 2500000,
            "realized_yield_ytd": 0.14,
            "investor_retention": 0.95,
            "new_investors_30d": 12,
            "pending_redemptions": 150000
        }

    def _get_secondary_market(self) -> dict[str, Any]:
        """Get secondary market activity"""
        return {
            "volume_30d": 500000,
            "avg_discount": 0.05,
            "bid_ask_spread": 0.02,
            "active_listings": 25,
            "recent_trades": [
                {"date": "2026-01-18", "tranche": "BNPL-2026-Q1-M", "amount": 50000, "price": 0.97},
                {"date": "2026-01-17", "tranche": "SUB-2026-Q1-S", "amount": 100000, "price": 0.99}
            ]
        }


class QUANDashboard:
    """
    Master dashboard aggregating all sub-dashboards

    Single pane of glass for entire QUAN operation
    """

    def __init__(self):
        self.metrics_store = MetricsStore()
        self.executive = ExecutiveDashboard(self.metrics_store)
        self.operations = OperationsDashboard(self.metrics_store)
        self.compliance = ComplianceDashboard(self.metrics_store)
        self.tokenization = TokenizationDashboard(self.metrics_store)

        # Initialize with sample data
        self._initialize_sample_data()

    def _initialize_sample_data(self) -> None:
        """Initialize with sample metrics"""
        # Revenue metrics
        self.metrics_store.record("total_revenue", 2500000, MetricType.COUNTER, "USD")
        self.metrics_store.record("total_cost", 500000, MetricType.COUNTER, "USD")
        self.metrics_store.record("total_collected", 2000000, MetricType.COUNTER, "USD")
        self.metrics_store.record("total_face_value", 5000000, MetricType.COUNTER, "USD")

        # Efficiency metrics
        self.metrics_store.record("cost_per_dollar", 0.20, MetricType.GAUGE, "USD")
        self.metrics_store.record("roi", 4.0, MetricType.GAUGE, "ratio")
        self.metrics_store.record("recovery_rate", 0.49, MetricType.PERCENTAGE, "%")

        # Operations metrics
        self.metrics_store.record("accounts_ingested", 150000, MetricType.COUNTER)
        self.metrics_store.record("accounts_resolved", 73500, MetricType.COUNTER)
        self.metrics_store.record("accounts_contacted", 120000, MetricType.COUNTER)

    def get_full_dashboard(self) -> dict[str, Any]:
        """Get complete dashboard data"""
        return {
            "generated_at": datetime.now().isoformat(),
            "executive": self.executive.get_snapshot(),
            "operations": self.operations.get_snapshot(),
            "compliance": self.compliance.get_snapshot(),
            "tokenization": self.tokenization.get_snapshot(),
            "system_health": self._get_system_health(),
            "alerts": self._aggregate_alerts()
        }

    def _get_system_health(self) -> dict[str, Any]:
        """Get overall system health"""
        return {
            "status": "healthy",
            "uptime": "99.97%",
            "modules": {
                "ingestion": "healthy",
                "shadow_bureau": "healthy",
                "empathy_engine": "healthy",
                "payment_processing": "healthy",
                "tokenization": "healthy",
                "reporting": "healthy"
            },
            "last_incident": "2026-01-10",
            "mttr": "15 minutes"
        }

    def _aggregate_alerts(self) -> list[dict[str, Any]]:
        """Aggregate alerts from all dashboards"""
        alerts = []

        # Get executive alerts
        exec_snapshot = self.executive.get_snapshot()
        alerts.extend(exec_snapshot.get("alerts", []))

        # Get compliance alerts
        compliance_snapshot = self.compliance.get_snapshot()
        violations = compliance_snapshot.get("violations", {})
        if violations.get("total_30d", 0) > 5:
            alerts.append({
                "severity": "warning",
                "source": "compliance",
                "message": f"{violations['total_30d']} violations in last 30 days"
            })

        # Get operations alerts
        ops_snapshot = self.operations.get_snapshot()
        for bottleneck in ops_snapshot.get("bottlenecks", []):
            alerts.append({
                "severity": bottleneck["severity"],
                "source": "operations",
                "message": bottleneck["issue"]
            })

        return alerts

    def export_report(self, report_type: str = "executive") -> dict[str, Any]:
        """Export formatted report"""
        if report_type == "executive":
            return self.executive.get_snapshot()
        elif report_type == "operations":
            return self.operations.get_snapshot()
        elif report_type == "compliance":
            return self.compliance.get_snapshot()
        elif report_type == "tokenization":
            return self.tokenization.get_snapshot()
        else:
            return self.get_full_dashboard()


# Demonstration
if __name__ == "__main__":
    print("=== QUAN ANALYTICS DASHBOARD DEMO ===\n")

    dashboard = QUANDashboard()

    # Get full dashboard
    full = dashboard.get_full_dashboard()

    print("EXECUTIVE SUMMARY")
    print("=" * 50)
    kpis = full["executive"]["kpis"]
    print(f"  Total Revenue: ${kpis['total_revenue']['value']:,.0f}")
    print(f"  Recovery Rate: {kpis['recovery_rate']['value']:.1%}")
    print(f"  ROI: {kpis['roi']['value']:.0%}")
    print(f"  Cost per Dollar: ${kpis['cost_per_dollar']['value']:.2f}")

    print("\nOPERATIONS STATUS")
    print("=" * 50)
    pipeline = full["operations"]["pipeline"]
    for stage, data in list(pipeline.items())[:4]:
        print(f"  {stage}: {data['count']:,} accounts ({data['conversion_rate']:.0%} conversion)")

    print("\nCOMPLIANCE STATUS")
    print("=" * 50)
    compliance = full["compliance"]
    print(f"  Overall Score: {compliance['overall_score']['score']}")
    print(f"  Audit Readiness: {compliance['audit_readiness']['overall_readiness']}")
    print(f"  Violations (30d): {compliance['violations']['total_30d']}")

    print("\nTOKENIZATION PORTFOLIO")
    print("=" * 50)
    tokenization = full["tokenization"]
    summary = tokenization["portfolio_summary"]
    print(f"  Total Face Value: ${summary['total_face_value']:,}")
    print(f"  Total NAV: ${summary['total_nav']:,}")
    print(f"  Active Pools: {summary['total_pools']}")
    print(f"  Avg Yield: {summary['avg_yield']:.0%}")

    print("\nSYSTEM HEALTH")
    print("=" * 50)
    health = full["system_health"]
    print(f"  Status: {health['status'].upper()}")
    print(f"  Uptime: {health['uptime']}")

    if full["alerts"]:
        print("\nALERTS")
        print("=" * 50)
        for alert in full["alerts"][:3]:
            print(f"  [{alert['severity'].upper()}] {alert['message']}")
