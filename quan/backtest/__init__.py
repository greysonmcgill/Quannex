"""
QUAN Backtest Module

End-to-end lifecycle backtesting and process mapping for:
- Efficiency analysis
- Scale testing
- Scope validation
"""

from .lifecycle_orchestrator import (
    LifecycleOrchestrator,
    LifecyclePhase,
    ScaleLevel,
    EfficiencyGrade,
    ProcessMap,
    BacktestResult,
    EfficiencyReport,
    ScaleReport,
    ScopeReport,
    PhaseMetrics,
    run_lifecycle_backtest,
)

__all__ = [
    "LifecycleOrchestrator",
    "LifecyclePhase",
    "ScaleLevel",
    "EfficiencyGrade",
    "ProcessMap",
    "BacktestResult",
    "EfficiencyReport",
    "ScaleReport",
    "ScopeReport",
    "PhaseMetrics",
    "run_lifecycle_backtest",
]
