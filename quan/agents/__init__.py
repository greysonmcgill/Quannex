"""
QUAN Agentic AI System

Autonomous AI architecture for intelligent debt collection with:
- Multi-agent coordination
- Constitutional AI compliance
- Adaptive negotiation strategies
- Self-improving learning loops

Hierarchical Agent System (v2):
- QuannexSupervisor: top-level orchestrator with ML + LLM reasoning
- QuannexMemoryManager: structured state with auto-compression
- LLMWrapper: provider-agnostic async LLM calls (Claude / OpenAI)
- Specialists: Planner, Outreach, Verifier, Simulator, MemoryManager
"""

from quan.agents.agentic_controller import (
    AgenticController,
    AutonomyLevel,
    ConversationState,
    ComplianceMonitor,
    NegotiationEngine,
    VoiceSynthesisController,
    MultiAgentCoordinator,
    LearningLoop,
    CostTracker,
    RAGIntegration,
)

from quan.agents.memory import (
    QuannexAgentState,
    QuannexMemoryManager,
    QuannexMLCacheEntry,
    QuannexComplianceNote,
    QuannexObservation,
)
from quan.agents.llm_wrapper import AgentOutput, LLMWrapper
from quan.agents.supervisor import (
    QuannexSupervisor,
    BaseSpecialist,
    PlannerSpecialist,
    VerifierSpecialist,
    SimulatorSpecialist,
    MemoryManagerSpecialist,
)
from quan.agents.outreach_specialist import OutreachSpecialist

__all__ = [
    # Legacy agentic controller
    "AgenticController",
    "AutonomyLevel",
    "ConversationState",
    "ComplianceMonitor",
    "NegotiationEngine",
    "VoiceSynthesisController",
    "MultiAgentCoordinator",
    "LearningLoop",
    "CostTracker",
    "RAGIntegration",
    # Hierarchical agent system (v2)
    "QuannexAgentState",
    "QuannexMemoryManager",
    "QuannexMLCacheEntry",
    "QuannexComplianceNote",
    "QuannexObservation",
    "AgentOutput",
    "LLMWrapper",
    "QuannexSupervisor",
    "BaseSpecialist",
    "PlannerSpecialist",
    "VerifierSpecialist",
    "SimulatorSpecialist",
    "MemoryManagerSpecialist",
    "OutreachSpecialist",
]
