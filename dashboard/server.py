"""
Standalone Dashboard API Server.

Serves the same database-backed dashboard data as the FastAPI backend.
Run with: python server.py
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json

from quan.analytics.live_dashboard import build_full_dashboard
from quan.database import SessionLocal


def generate_dashboard_data() -> dict:
    """Return the current dashboard payload from the operational database."""

    with SessionLocal() as db:
        return build_full_dashboard(db)


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.rstrip("/")

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
                    "accounts_processing": sum(
                        stage["count"] for stage in data["operations"]["pipeline"].values()
                    ),
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
            "/api/v1/dashboard/queues": {
                "queues": data["operations"]["queues"],
                "generated_at": data["generated_at"],
            },
            "/api/v1/dashboard/investors": {
                "investor_metrics": data["tokenization"]["investor_metrics"],
                "secondary_market": data["tokenization"]["secondary_market"],
                "generated_at": data["generated_at"],
            },
            "/api/v1/dashboard/pools": {
                "pools": data["tokenization"]["pools"],
                "portfolio_summary": data["tokenization"]["portfolio_summary"],
                "generated_at": data["generated_at"],
            },
            "/health": {"status": "healthy"},
            "": {"service": "QUAN Recovery", "version": "0.1.0", "status": "operational"},
        }

        response = routes.get(path, {"error": "Not found"})
        self.wfile.write(json.dumps(response, indent=2).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()


def run(port: int = 8001):
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"Dashboard API server running on http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
