"""Dashboard API router.

Exposes operator, executive, and compliance reporting backed by the live
database via :mod:`quan.analytics.live_dashboard`. The tokenization / investor
surface that previously lived here was removed as part of the collections-OS
refocus — it was never a pilot requirement.

A lightweight WebSocket endpoint is retained for dashboards that want live
heartbeats without polling.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from quan.analytics.live_dashboard import (
    build_alerts,
    build_compliance_snapshot,
    build_executive_snapshot,
    build_full_dashboard,
    build_operations_snapshot,
    build_system_health,
)
from quan.database import SessionLocal, get_db

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@router.get("/")
def get_full_dashboard(db: Session = Depends(get_db)) -> dict:
    """Full dashboard payload (executive, operations, compliance, health, alerts)."""

    return build_full_dashboard(db)


@router.get("/executive")
def get_executive(db: Session = Depends(get_db)) -> dict:
    """Executive KPI snapshot."""

    return build_executive_snapshot(db)


@router.get("/operations")
def get_operations(db: Session = Depends(get_db)) -> dict:
    """Operations pipeline, channels, queues, and throughput."""

    return build_operations_snapshot(db)


@router.get("/compliance")
def get_compliance(db: Session = Depends(get_db)) -> dict:
    """Compliance score, violations, state posture, regulation readiness."""

    return build_compliance_snapshot(db)


@router.get("/health")
def get_health(db: Session = Depends(get_db)) -> dict:
    """Module-level health view plus active alerts."""

    return {
        "system_health": build_system_health(db),
        "alerts": build_alerts(db),
    }


@router.get("/alerts")
def get_alerts(db: Session = Depends(get_db)) -> dict:
    """Currently active operational alerts."""

    return {
        "alerts": build_alerts(db),
        "generated_at": _iso_now(),
    }


@router.get("/pipeline")
def get_pipeline(db: Session = Depends(get_db)) -> dict:
    """Pipeline stages, bottlenecks, and throughput subset of operations."""

    operations = build_operations_snapshot(db)
    return {
        "pipeline": operations["pipeline"],
        "bottlenecks": operations["bottlenecks"],
        "throughput": operations["throughput"],
    }


@router.get("/channels")
def get_channels(db: Session = Depends(get_db)) -> dict:
    """Channel-level metrics (attempts, response, cost)."""

    operations = build_operations_snapshot(db)
    return {
        "channels": operations["channels"],
        "generated_at": _iso_now(),
    }


@router.get("/queues")
def get_queues(db: Session = Depends(get_db)) -> dict:
    """Queue depths and processing rates."""

    operations = build_operations_snapshot(db)
    return {
        "queues": operations["queues"],
        "generated_at": _iso_now(),
    }


@router.get("/violations")
def get_violations(
    days: int = Query(30, ge=1, le=365),  # noqa: ARG001 - reserved for filtering
    db: Session = Depends(get_db),
) -> dict:
    """Compliance violations and regulation posture."""

    compliance = build_compliance_snapshot(db)
    return {
        "violations": compliance["violations"],
        "regulation_status": compliance["regulation_status"],
        "generated_at": _iso_now(),
    }


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)) -> dict:
    """Flat KPI summary for dashboard header cards."""

    full = build_full_dashboard(db)
    exec_kpis = full["executive"]["kpis"]
    pipeline = full["operations"]["pipeline"]
    compliance = full["compliance"]

    return {
        "generated_at": _iso_now(),
        "executive": {
            "total_revenue": exec_kpis["total_revenue"]["value"],
            "recovery_rate": exec_kpis["recovery_rate"]["value"],
            "cost_per_dollar": exec_kpis["cost_per_dollar"]["value"],
        },
        "operations": {
            "accounts_processing": sum(
                stage.get("count", 0) for stage in pipeline.values()
            ),
            "capacity_utilization": full["operations"]["throughput"][
                "current_capacity_utilization"
            ],
            "bottleneck_count": len(full["operations"]["bottlenecks"]),
        },
        "compliance": {
            "score": compliance["overall_score"]["score"],
            "violations_30d": compliance["violations"]["total_30d"],
            "audit_readiness": compliance["audit_readiness"]["score"],
        },
        "alert_count": len(full["alerts"]),
    }


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------


class _ConnectionManager:
    """Minimal connection registry for the dashboard WebSocket."""

    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active:
            self.active.remove(websocket)


manager = _ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Stream periodic dashboard updates to the browser."""

    await manager.connect(websocket)
    try:
        with SessionLocal() as db:
            await websocket.send_json(
                {"type": "initial", "data": build_full_dashboard(db)}
            )

        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_text(), timeout=30.0
                )
            except asyncio.TimeoutError:
                with SessionLocal() as db:
                    await websocket.send_json(
                        {
                            "type": "update",
                            "data": {
                                "health": build_system_health(db),
                                "alerts": build_alerts(db),
                            },
                            "timestamp": _iso_now(),
                        }
                    )
                continue

            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                continue
            if payload.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:  # pragma: no cover - defensive
        manager.disconnect(websocket)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()
