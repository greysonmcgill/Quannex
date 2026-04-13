"""
Dashboard API Router

Exposes dashboard data via REST endpoints for the frontend UI.
Supports WebSocket connections for real-time updates.
"""

from datetime import datetime
from typing import Optional
import asyncio
import json

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from quan.analytics.live_dashboard import (
    build_compliance_snapshot,
    build_executive_snapshot,
    build_full_dashboard,
    build_operations_snapshot,
    build_system_health,
    build_tokenization_snapshot,
)
from quan.database import SessionLocal, get_db
from quan.analytics.dashboard import (
    QUANDashboard,
    TimeGranularity,
    MetricType,
)

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])

# Global dashboard instance
_dashboard: Optional[QUANDashboard] = None


def get_dashboard() -> QUANDashboard:
    """Get or create dashboard instance"""
    global _dashboard
    if _dashboard is None:
        _dashboard = QUANDashboard()
    return _dashboard


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


# ==================== REST Endpoints ====================


@router.get("/")
def get_full_dashboard_route(db: Session = Depends(get_db)):
    """Get complete dashboard with all sections"""
    return build_full_dashboard(db)


@router.get("/executive")
def get_executive_dashboard(db: Session = Depends(get_db)):
    """Get executive dashboard snapshot"""
    return build_executive_snapshot(db)


@router.get("/operations")
def get_operations_dashboard(db: Session = Depends(get_db)):
    """Get operations dashboard snapshot"""
    return build_operations_snapshot(db)


@router.get("/compliance")
def get_compliance_dashboard(db: Session = Depends(get_db)):
    """Get compliance dashboard snapshot"""
    return build_compliance_snapshot(db)


@router.get("/tokenization")
def get_tokenization_dashboard(db: Session = Depends(get_db)):
    """Get tokenization dashboard snapshot"""
    return build_tokenization_snapshot(db)


@router.get("/health")
def get_system_health(db: Session = Depends(get_db)):
    """Get system health status"""
    full = build_full_dashboard(db)
    return {
        "system_health": full["system_health"],
        "alerts": full["alerts"],
    }


@router.get("/metrics/{metric_name}")
async def get_metric(
    metric_name: str,
    granularity: str = Query("hour", enum=["minute", "hour", "day", "week", "month"]),
    operation: str = Query("avg", enum=["avg", "sum", "min", "max", "count"]),
):
    """Get time series data for a specific metric"""
    dashboard = get_dashboard()
    granularity_map = {
        "minute": TimeGranularity.MINUTE,
        "hour": TimeGranularity.HOUR,
        "day": TimeGranularity.DAY,
        "week": TimeGranularity.WEEK,
        "month": TimeGranularity.MONTH,
    }

    series = dashboard.metrics_store.aggregate(
        metric_name,
        granularity_map.get(granularity, TimeGranularity.HOUR),
        operation,
    )

    current = dashboard.metrics_store.get(metric_name)

    return {
        "metric": metric_name,
        "current_value": current.value if current else None,
        "unit": current.unit if current else None,
        "series": [{"timestamp": ts, "value": val} for ts, val in series],
    }


@router.get("/alerts")
def get_alerts(db: Session = Depends(get_db)):
    """Get all active alerts"""
    full = build_full_dashboard(db)
    return {"alerts": full["alerts"], "generated_at": datetime.now().isoformat()}


@router.get("/pipeline")
def get_pipeline_status(db: Session = Depends(get_db)):
    """Get detailed pipeline stage breakdown"""
    ops = build_operations_snapshot(db)
    return {
        "pipeline": ops["pipeline"],
        "bottlenecks": ops["bottlenecks"],
        "throughput": ops["throughput"],
    }


@router.get("/channels")
def get_channel_performance(db: Session = Depends(get_db)):
    """Get channel performance metrics"""
    ops = build_operations_snapshot(db)
    return {"channels": ops["channels"], "generated_at": datetime.now().isoformat()}


@router.get("/queues")
def get_queue_status(db: Session = Depends(get_db)):
    """Get queue depths and processing rates"""
    ops = build_operations_snapshot(db)
    return {"queues": ops["queues"], "generated_at": datetime.now().isoformat()}


@router.get("/violations")
def get_violations(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Get compliance violations"""
    compliance = build_compliance_snapshot(db)
    return {
        "violations": compliance["violations"],
        "regulation_status": compliance["regulation_status"],
        "generated_at": datetime.now().isoformat(),
    }


@router.get("/pools")
def get_pool_performance(db: Session = Depends(get_db)):
    """Get tokenization pool performance"""
    tokenization = build_tokenization_snapshot(db)
    return {
        "pools": tokenization["pools"],
        "portfolio_summary": tokenization["portfolio_summary"],
        "generated_at": datetime.now().isoformat(),
    }


@router.get("/investors")
def get_investor_metrics(db: Session = Depends(get_db)):
    """Get investor metrics and secondary market data"""
    tokenization = build_tokenization_snapshot(db)
    return {
        "investor_metrics": tokenization["investor_metrics"],
        "secondary_market": tokenization["secondary_market"],
        "generated_at": datetime.now().isoformat(),
    }


@router.post("/metrics/{metric_name}")
async def record_metric(
    metric_name: str,
    value: float,
    unit: str = "",
    metric_type: str = "gauge",
):
    """Record a new metric value"""
    dashboard = get_dashboard()

    type_map = {
        "counter": MetricType.COUNTER,
        "gauge": MetricType.GAUGE,
        "histogram": MetricType.HISTOGRAM,
        "rate": MetricType.RATE,
        "percentage": MetricType.PERCENTAGE,
    }

    dashboard.metrics_store.record(
        metric_name,
        value,
        type_map.get(metric_type, MetricType.GAUGE),
        unit,
    )

    # Broadcast update to WebSocket clients
    await manager.broadcast(
        {
            "type": "metric_update",
            "metric": metric_name,
            "value": value,
            "timestamp": datetime.now().isoformat(),
        }
    )

    return {"success": True, "metric": metric_name, "value": value}


# ==================== WebSocket Endpoint ====================


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates"""
    await manager.connect(websocket)

    try:
        # Send initial dashboard data
        with SessionLocal() as db:
            await websocket.send_json(
                {"type": "initial", "data": build_full_dashboard(db)}
            )

        # Keep connection alive and send periodic updates
        while True:
            try:
                # Wait for messages or timeout
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)

                # Handle client messages
                message = json.loads(data)
                if message.get("type") == "subscribe":
                    # Client subscribing to specific metrics
                    pass
                elif message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

            except asyncio.TimeoutError:
                # Send heartbeat/update
                with SessionLocal() as db:
                    dashboard = build_full_dashboard(db)
                    await websocket.send_json(
                        {
                            "type": "update",
                            "data": {
                                "health": dashboard["system_health"],
                                "alerts": dashboard["alerts"],
                            },
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


# ==================== Summary Stats ====================


@router.get("/summary")
def get_summary_stats(db: Session = Depends(get_db)):
    """Get summary statistics for dashboard cards"""
    full = build_full_dashboard(db)

    exec_data = full["executive"]
    ops_data = full["operations"]
    compliance_data = full["compliance"]
    token_data = full["tokenization"]

    return {
        "generated_at": datetime.now().isoformat(),
        "executive": {
            "total_revenue": exec_data["kpis"]["total_revenue"]["value"],
            "recovery_rate": exec_data["kpis"]["recovery_rate"]["value"],
            "roi": exec_data["kpis"]["roi"]["value"],
            "cost_per_dollar": exec_data["kpis"]["cost_per_dollar"]["value"],
        },
        "operations": {
            "accounts_processing": sum(
                stage.get("count", 0) for stage in ops_data["pipeline"].values()
            ),
            "capacity_utilization": ops_data["throughput"][
                "current_capacity_utilization"
            ],
            "bottleneck_count": len(ops_data["bottlenecks"]),
        },
        "compliance": {
            "score": compliance_data["overall_score"]["score"],
            "violations_30d": compliance_data["violations"]["total_30d"],
            "audit_readiness": compliance_data["audit_readiness"]["score"],
        },
        "tokenization": {
            "total_nav": token_data["portfolio_summary"]["total_nav"],
            "avg_yield": token_data["portfolio_summary"]["avg_yield"],
            "active_pools": token_data["portfolio_summary"]["total_pools"],
        },
        "alert_count": len(full["alerts"]),
    }
