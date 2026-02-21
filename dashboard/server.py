"""
Standalone Dashboard API Server

Serves dashboard data with realistic mock data for development/demo.
Run with: python server.py
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from datetime import datetime, timedelta
import random


def generate_dashboard_data():
    """Generate full dashboard data with realistic values."""
    now = datetime.now()

    # Generate trend data
    revenue_trend = []
    collections_trend = []
    recovery_trend = []
    base_revenue = 70000
    base_collections = 60000
    base_recovery = 0.44

    for i in range(14):
        d = (now - timedelta(days=13 - i)).strftime("%Y-%m-%d")
        r = base_revenue + random.uniform(-5000, 15000) + i * 3000
        c = base_collections + random.uniform(-5000, 12000) + i * 2500
        rr = base_recovery + random.uniform(-0.01, 0.02) + i * 0.003
        revenue_trend.append([d, round(r)])
        collections_trend.append([d, round(c)])
        recovery_trend.append([d, round(min(rr, 0.55), 3)])

    return {
        "generated_at": now.isoformat(),
        "executive": {
            "generated_at": now.isoformat(),
            "period": "30d",
            "kpis": {
                "total_revenue": {"value": 2500000, "unit": "USD", "change": {"value": 0.12, "direction": "up"}},
                "gross_margin": {"value": 0.80, "unit": "%", "change": {"value": 0.05, "direction": "up"}},
                "recovery_rate": {"value": 0.49, "unit": "%", "change": {"value": 0.03, "direction": "up"}},
                "roi": {"value": 4.0, "unit": "%", "change": {"value": 0.15, "direction": "up"}},
                "cost_per_dollar": {"value": 0.20, "unit": "USD", "change": {"value": -0.02, "direction": "down"}},
            },
            "trends": {
                "revenue": revenue_trend,
                "collections": collections_trend,
                "recovery_rate": recovery_trend,
            },
            "alerts": [
                {
                    "severity": "warning",
                    "metric": "roi",
                    "message": "ROI trending below target this week",
                    "recommendation": "Review settlement acceptance rates",
                }
            ],
        },
        "operations": {
            "generated_at": now.isoformat(),
            "pipeline": {
                "ingested": {"count": 150000, "conversion_rate": 0.95, "avg_time_in_stage": "2 minutes"},
                "enriched": {"count": 142500, "conversion_rate": 0.90, "avg_time_in_stage": "5 minutes"},
                "scored": {"count": 128250, "conversion_rate": 0.88, "avg_time_in_stage": "1 minute"},
                "contacted": {"count": 112860, "conversion_rate": 0.35, "avg_time_in_stage": "3 days"},
                "negotiating": {"count": 39501, "conversion_rate": 0.65, "avg_time_in_stage": "7 days"},
                "payment_pending": {"count": 25675, "conversion_rate": 0.80, "avg_time_in_stage": "14 days"},
                "resolved": {"count": 73500, "conversion_rate": 1.0, "avg_time_in_stage": "N/A"},
            },
            "channels": {
                "sms": {"attempts": 250000, "responses": 37500, "conversions": 20000, "response_rate": 0.15, "conversion_rate": 0.08, "cost_per_contact": 0.02},
                "email": {"attempts": 500000, "responses": 60000, "conversions": 25000, "response_rate": 0.12, "conversion_rate": 0.05, "cost_per_contact": 0.01},
                "voice": {"attempts": 75000, "responses": 18750, "conversions": 11250, "response_rate": 0.25, "conversion_rate": 0.15, "cost_per_contact": 0.15},
                "digital": {"attempts": 100000, "responses": 18000, "conversions": 10000, "response_rate": 0.18, "conversion_rate": 0.10, "cost_per_contact": 0.03},
            },
            "queues": {
                "contact_queue": {"depth": 15000, "processing_rate": 500, "estimated_clear_time": "30 minutes"},
                "payment_queue": {"depth": 2500, "processing_rate": 100, "estimated_clear_time": "25 minutes"},
                "enrichment_queue": {"depth": 5000, "processing_rate": 1000, "estimated_clear_time": "5 minutes"},
            },
            "bottlenecks": [
                {"location": "contact_queue", "severity": "warning", "issue": "Queue depth elevated - 15,000 accounts pending", "recommendation": "Scale outreach capacity"},
            ],
            "throughput": {
                "accounts_per_hour": 5000,
                "contacts_per_hour": 15000,
                "resolutions_per_hour": 500,
                "payments_per_hour": 200,
                "current_capacity_utilization": 0.72,
            },
        },
        "compliance": {
            "generated_at": now.isoformat(),
            "overall_score": {
                "score": 98.5,
                "rating": "Excellent",
                "trend": "stable",
                "components": {"fdcpa": 99.2, "tcpa": 97.8, "regulation_f": 99.0, "state_laws": 98.0},
            },
            "audit_readiness": {
                "overall_readiness": "high",
                "score": 95,
                "checklist": {
                    "interaction_logs": {"status": "complete", "coverage": 100},
                    "consent_records": {"status": "complete", "coverage": 100},
                    "disclosure_delivery": {"status": "complete", "coverage": 99.8},
                    "dispute_handling": {"status": "complete", "coverage": 100},
                    "call_recordings": {"status": "complete", "coverage": 98.5},
                },
                "last_audit": "2025-11-15",
                "next_scheduled": "2026-05-15",
            },
            "violations": {
                "total_30d": 3,
                "total_90d": 8,
                "by_type": {"timing": 1, "disclosure": 1, "frequency": 1},
                "by_severity": {"critical": 0, "major": 1, "minor": 2},
                "recent": [
                    {"id": "V001", "date": "2026-01-15", "type": "timing", "description": "Contact attempt at 8:58 PM (within 2 min of cutoff)", "severity": "minor", "resolution": "System clock sync adjusted"},
                    {"id": "V002", "date": "2026-01-12", "type": "disclosure", "description": "Mini-Miranda missing from voicemail", "severity": "major", "resolution": "Script template updated"},
                    {"id": "V003", "date": "2026-01-08", "type": "frequency", "description": "8th contact attempt in 7-day period", "severity": "minor", "resolution": "Contact governor recalibrated"},
                ],
            },
            "state_compliance": {
                "fully_compliant": 47,
                "requires_attention": 3,
                "attention_states": ["CA", "NY", "MA"],
                "details": {
                    "CA": {"status": "compliant", "license_expiry": "2026-06-30"},
                    "NY": {"status": "review", "note": "New regulation effective 2026-03-01"},
                    "MA": {"status": "compliant", "license_expiry": "2026-04-15"},
                },
            },
            "regulation_status": {
                "fdcpa": {"status": "compliant", "last_review": "2026-01-01", "automation_coverage": 100},
                "tcpa": {"status": "compliant", "consent_rate": 99.5, "dnc_compliance": 100},
                "regulation_f": {"status": "compliant", "7_in_7_compliance": 100, "model_notice_usage": 100},
                "cfpb_guidance": {"status": "monitoring", "pending_changes": 2},
            },
        },
        "tokenization": {
            "generated_at": now.isoformat(),
            "portfolio_summary": {
                "total_face_value": 25000000,
                "total_nav": 18500000,
                "total_pools": 12,
                "active_tranches": 48,
                "total_investors": 156,
                "avg_yield": 0.18,
                "default_rate": 0.12,
            },
            "pools": [
                {"pool_id": "BNPL-2026-Q1", "asset_class": "BNPL Subprime", "face_value": 5000000, "nav": 3750000, "recovery_rate": 0.52, "yield": 0.22, "status": "performing"},
                {"pool_id": "SUB-2026-Q1", "asset_class": "Subscriptions", "face_value": 2000000, "nav": 1400000, "recovery_rate": 0.48, "yield": 0.19, "status": "performing"},
                {"pool_id": "MIXED-2025-Q4", "asset_class": "Mixed Micro", "face_value": 3500000, "nav": 2450000, "recovery_rate": 0.45, "yield": 0.17, "status": "performing"},
                {"pool_id": "MED-2025-Q4", "asset_class": "Medical Debt", "face_value": 4000000, "nav": 2800000, "recovery_rate": 0.42, "yield": 0.16, "status": "performing"},
                {"pool_id": "UTIL-2025-Q3", "asset_class": "Utility Arrears", "face_value": 1500000, "nav": 1050000, "recovery_rate": 0.55, "yield": 0.21, "status": "performing"},
            ],
            "tranches": {
                "senior": {"total_value": 12000000, "avg_yield": 0.10, "default_rate": 0.02, "rating": "AA"},
                "mezzanine": {"total_value": 5000000, "avg_yield": 0.18, "default_rate": 0.08, "rating": "BBB"},
                "junior": {"total_value": 2000000, "avg_yield": 0.28, "default_rate": 0.15, "rating": "BB"},
                "equity": {"total_value": 1000000, "avg_yield": 0.42, "default_rate": 0.25, "rating": "NR"},
            },
            "investor_metrics": {
                "total_invested": 18000000,
                "distributions_ytd": 2500000,
                "realized_yield_ytd": 0.14,
                "investor_retention": 0.95,
                "new_investors_30d": 12,
                "pending_redemptions": 150000,
            },
            "secondary_market": {
                "volume_30d": 500000,
                "avg_discount": 0.05,
                "bid_ask_spread": 0.02,
                "active_listings": 25,
                "recent_trades": [
                    {"date": "2026-02-15", "tranche": "BNPL-2026-Q1-M", "amount": 50000, "price": 0.97},
                    {"date": "2026-02-14", "tranche": "SUB-2026-Q1-S", "amount": 100000, "price": 0.99},
                    {"date": "2026-02-13", "tranche": "MIXED-2025-Q4-J", "amount": 25000, "price": 0.92},
                    {"date": "2026-02-12", "tranche": "BNPL-2026-Q1-S", "amount": 75000, "price": 0.995},
                ],
            },
        },
        "system_health": {
            "status": "healthy",
            "uptime": "99.97%",
            "modules": {
                "ingestion": "healthy",
                "shadow_bureau": "healthy",
                "empathy_engine": "healthy",
                "payment_processing": "healthy",
                "tokenization": "healthy",
                "reporting": "healthy",
            },
            "last_incident": "2026-01-10",
            "mttr": "15 minutes",
        },
        "alerts": [
            {
                "severity": "warning",
                "source": "operations",
                "message": "Contact queue depth elevated - 15,000 accounts pending",
                "recommendation": "Consider scaling outreach capacity",
            },
        ],
    }


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.rstrip("/")

        # CORS headers
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

        data = generate_dashboard_data()

        routes = {
            "/api/v1/dashboard": data,
            "/api/v1/dashboard/executive": data["executive"],
            "/api/v1/dashboard/operations": data["operations"],
            "/api/v1/dashboard/compliance": data["compliance"],
            "/api/v1/dashboard/tokenization": data["tokenization"],
            "/api/v1/dashboard/health": {
                "system_health": data["system_health"],
                "alerts": data["alerts"],
            },
            "/api/v1/dashboard/alerts": {
                "alerts": data["alerts"],
                "generated_at": data["generated_at"],
            },
            "/api/v1/dashboard/summary": {
                "generated_at": data["generated_at"],
                "executive": {
                    "total_revenue": data["executive"]["kpis"]["total_revenue"]["value"],
                    "recovery_rate": data["executive"]["kpis"]["recovery_rate"]["value"],
                    "roi": data["executive"]["kpis"]["roi"]["value"],
                    "cost_per_dollar": data["executive"]["kpis"]["cost_per_dollar"]["value"],
                },
                "operations": {
                    "accounts_processing": sum(s["count"] for s in data["operations"]["pipeline"].values()),
                    "capacity_utilization": data["operations"]["throughput"]["current_capacity_utilization"],
                    "bottleneck_count": len(data["operations"]["bottlenecks"]),
                },
                "compliance": {
                    "score": data["compliance"]["overall_score"]["score"],
                    "violations_30d": data["compliance"]["violations"]["total_30d"],
                    "audit_readiness": data["compliance"]["audit_readiness"]["score"],
                },
                "tokenization": {
                    "total_nav": data["tokenization"]["portfolio_summary"]["total_nav"],
                    "avg_yield": data["tokenization"]["portfolio_summary"]["avg_yield"],
                    "active_pools": data["tokenization"]["portfolio_summary"]["total_pools"],
                },
                "alert_count": len(data["alerts"]),
            },
            "/api/v1/dashboard/pipeline": {
                "pipeline": data["operations"]["pipeline"],
                "bottlenecks": data["operations"]["bottlenecks"],
                "throughput": data["operations"]["throughput"],
            },
            "/api/v1/dashboard/channels": {
                "channels": data["operations"]["channels"],
                "generated_at": data["generated_at"],
            },
            "/health": {"status": "healthy"},
            "": {"service": "QUAN Recovery", "version": "0.1.0", "status": "operational"},
        }

        response = routes.get(path, {"error": "Not found"})
        self.wfile.write(json.dumps(response, indent=2).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[API] {args[0]}")


if __name__ == "__main__":
    port = 8000
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"QUAN Dashboard API running on http://localhost:{port}")
    print(f"Dashboard endpoints:")
    print(f"  GET /api/v1/dashboard/          - Full dashboard")
    print(f"  GET /api/v1/dashboard/executive  - Executive metrics")
    print(f"  GET /api/v1/dashboard/operations - Operations data")
    print(f"  GET /api/v1/dashboard/compliance - Compliance status")
    print(f"  GET /api/v1/dashboard/tokenization - Tokenization data")
    print(f"  GET /api/v1/dashboard/health     - System health")
    print(f"  GET /api/v1/dashboard/summary    - Summary stats")
    print()
    server.serve_forever()
