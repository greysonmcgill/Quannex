"""
QUAN Reporting Module - Credit Bureau Integration

Bridges the gap between modern debt data and legacy bureau systems.
"""

from .metro2_bridge import (
    Metro2Bridge,
    Metro2BaseSegment,
    Metro2J1Segment,
    Metro2J2Segment,
    Metro2KSegment,
    Metro2LSegment,
    Metro2BatchProcessor,
    EOscarIntegration,
    RealTimeBridge,
    Metro2Validator,
    ReportingAnalytics,
)

__all__ = [
    "Metro2Bridge",
    "Metro2BaseSegment",
    "Metro2J1Segment",
    "Metro2J2Segment",
    "Metro2KSegment",
    "Metro2LSegment",
    "Metro2BatchProcessor",
    "EOscarIntegration",
    "RealTimeBridge",
    "Metro2Validator",
    "ReportingAnalytics",
]
