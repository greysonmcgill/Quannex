"""
Dashboard API Router

Exposes dashboard data via REST endpoints for the frontend UI.
Supports WebSocket connections for real-time updates.

Uses database-backed DashboardService for real data.
Falls back to in-memory QUANDashboard if database unavailable.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
from typing import Optional
import asyncio
import json

from sqlalchemy.ext.asyncio import AsyncSession

from quan.analytics.dashboard import (
    QUANDashboard,
    MetricsStore,
    TimeGranularity,
    MetricType,
)
from quan.database import get_db
from quan.api.dashboard_service import DashboardService

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])

# Global in-memory dashboard instance (fallback)
_dashboard: Optional[QUANDashboard] = None


def get_in_memory_dashboard() -> QUANDashboard:
    """Get or create in-memory dashboard instance (fallback)"""
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
async def get_full_dashboard(db: AsyncSession = Depends(get_db)):
    """Get complete dashboard with all sections"""
    try:
        service = DashboardService(db)
        return await service.get_full_dashboard()
    except Exception:
        # Fallback to in-memory
        dashboard = get_in_memory_dashboard()
        return dashboard.get_full_dashboard()


@router.get("/executive")
async def get_executive_dashboard(db: AsyncSession = Depends(get_db)):
    """Get executive dashboard snapshot"""
    try:
        service = DashboardService(db)
        return await service.get_executive_snapshot()
    except Exception:
        dashboard = get_in_memory_dashboard()
        return dashboard.executive.get_snapshot()


@router.get("/operations")
async def get_operations_dashboard(db: AsyncSession = Depends(get_db)):
    """Get operations dashboard snapshot"""
    try:
        service = DashboardService(db)
        return await service.get_operations_snapshot()
    except Exception:
        dashboard = get_in_memory_dashboard()
        return dashboard.operations.get_snapshot()


@router.get("/compliance")
async def get_compliance_dashboard(db: AsyncSession = Depends(get_db)):
    """Get compliance dashboard snapshot"""
    try:
        service = DashboardService(db)
        return await service.get_compliance_snapshot()
    except Exception:
        dashboard = get_in_memory_dashboard()
        return dashboard.compliance.get_snapshot()


@router.get("/tokenization")
async def get_tokenization_dashboard(db: AsyncSession = Depends(get_db)):
    """Get tokenization dashboard snapshot"""
    try:
        service = DashboardService(db)
        return await service.get_tokenization_snapshot()
    except Exception:
        dashboard = get_in_memory_dashboard()
        return dashboard.tokenization.get_snapshot()


@router.get("/health")
async def get_system_health(db: AsyncSession = Depends(get_db)):
    """Get system health status"""
    try:
        service = DashboardService(db)
        full = await service.get_full_dashboard()
        return {
            "system_health": full["system_health"],
            "alerts": full["alerts"],
        }
    except Exception:
        dashboard = get_in_memory_dashboard()
    full = dashboard.get_full_dashboard()
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
    dashboard = get_in_memory_dashboard()
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
async def get_alerts(db: AsyncSession = Depends(get_db)):
    """Get all active alerts"""
    try:
        service = DashboardService(db)
        full = await service.get_full_dashboard()
        return {"alerts": full["alerts"], "generated_at": datetime.now().isoformat()}
    except Exception:
        dashboard = get_in_memory_dashboard()
        full = dashboard.get_full_dashboard()
        return {"alerts": full["alerts"], "generated_at": datetime.now().isoformat()}


@router.get("/pipeline")
async def get_pipeline_status(db: AsyncSession = Depends(get_db)):
    """Get detailed pipeline stage breakdown"""
    try:
        service = DashboardService(db)
        ops = await service.get_operations_snapshot()
        return {
            "pipeline": ops["pipeline"],
            "bottlenecks": ops["bottlenecks"],
            "throughput": ops["throughput"],
        }
    except Exception:
        dashboard = get_in_memory_dashboard()
        ops = dashboard.operations.get_snapshot()
        return {
            "pipeline": ops["pipeline"],
            "bottlenecks": ops["bottlenecks"],
            "throughput": ops["throughput"],
        }


@router.get("/channels")
async def get_channel_performance(db: AsyncSession = Depends(get_db)):
    """Get channel performance metrics"""
    try:
        service = DashboardService(db)
        ops = await service.get_operations_snapshot()
        return {"channels": ops["channels"], "generated_at": datetime.now().isoformat()}
    except Exception:
        dashboard = get_in_memory_dashboard()
        ops = dashboard.operations.get_snapshot()
        return {"channels": ops["channels"], "generated_at": datetime.now().isoformat()}


@router.get("/queues")
async def get_queue_status(db: AsyncSession = Depends(get_db)):
    """Get queue depths and processing rates"""
    try:
        service = DashboardService(db)
        ops = await service.get_operations_snapshot()
        return {"queues": ops["queues"], "generated_at": datetime.now().isoformat()}
    except Exception:
        dashboard = get_in_memory_dashboard()
        ops = dashboard.operations.get_snapshot()
        return {"queues": ops["queues"], "generated_at": datetime.now().isoformat()}


@router.get("/violations")
async def get_violations(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get compliance violations"""
    try:
        service = DashboardService(db)
        compliance = await service.get_compliance_snapshot()
        return {
            "violations": compliance["violations"],
            "regulation_status": compliance["regulation_status"],
            "generated_at": datetime.now().isoformat(),
        }
    except Exception:
        dashboard = get_in_memory_dashboard()
        compliance = dashboard.compliance.get_snapshot()
        return {
            "violations": compliance["violations"],
            "regulation_status": compliance["regulation_status"],
            "generated_at": datetime.now().isoformat(),
        }


@router.get("/pools")
async def get_pool_performance(db: AsyncSession = Depends(get_db)):
    """Get tokenization pool performance"""
    try:
        service = DashboardService(db)
        tokenization = await service.get_tokenization_snapshot()
        return {
            "pools": tokenization["pools"],
            "portfolio_summary": tokenization["portfolio_summary"],
            "generated_at": datetime.now().isoformat(),
        }
    except Exception:
        dashboard = get_in_memory_dashboard()
        tokenization = dashboard.tokenization.get_snapshot()
        return {
            "pools": tokenization["pools"],
            "portfolio_summary": tokenization["portfolio_summary"],
            "generated_at": datetime.now().isoformat(),
        }


@router.get("/investors")
async def get_investor_metrics(db: AsyncSession = Depends(get_db)):
    """Get investor metrics and secondary market data"""
    try:
        service = DashboardService(db)
        tokenization = await service.get_tokenization_snapshot()
        return {
            "investor_metrics": tokenization["investor_metrics"],
            "secondary_market": tokenization["secondary_market"],
            "generated_at": datetime.now().isoformat(),
        }
    except Exception:
        dashboard = get_in_memory_dashboard()
        tokenization = dashboard.tokenization.get_snapshot()
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
    dashboard = get_in_memory_dashboard()

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
        dashboard = get_in_memory_dashboard()
        await websocket.send_json(
            {"type": "initial", "data": dashboard.get_full_dashboard()}
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
                dashboard = get_in_memory_dashboard()
                await websocket.send_json(
                    {
                        "type": "update",
                        "data": {
                            "health": dashboard.get_full_dashboard()["system_health"],
                            "alerts": dashboard.get_full_dashboard()["alerts"],
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
async def get_summary_stats(db: AsyncSession = Depends(get_db)):
    """Get summary statistics for dashboard cards"""
    try:
        service = DashboardService(db)
        return await service.get_summary_stats()
    except Exception:
        dashboard = get_in_memory_dashboard()
        full = dashboard.get_full_dashboard()

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
