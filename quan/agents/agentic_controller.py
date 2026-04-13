"""
QUAN Agentic AI Controller

Autonomous AI architecture for intelligent debt collection implementing:
1. Orchestrator LLM Layer - Conversation context and strategy management
2. RAG Integration - Real-time debtor profile and compliance retrieval
3. Compliance Monitor (Constitutional AI) - FDCPA/TCPA violation prevention
4. Voice Synthesis Control - Sub-800ms latency voice interactions
5. Negotiation Engine - Settlement and payment plan optimization
6. Autonomy Levels - From scripted (L1) to self-improving (L5)
7. Multi-Agent Coordination - Parallel consumer engagement
8. Learning Loop - Outcome tracking and strategy refinement
9. Cost Tracking - Per-conversation ROI calculation

This implements the thesis architecture for autonomous debt collection
while maintaining strict regulatory compliance.
"""

import asyncio
import hashlib
import json
import logging
import random
import re
import statistics
import threading
import time
import traceback
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum, auto
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

from quan.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class AutonomyLevel(Enum):
    """
    Autonomy levels for the agentic AI system.

    Level 1: Scripted responses only - No deviation from pre-approved scripts
    Level 2: Template-based with variables - Fill-in-the-blank personalization
    Level 3: Guided autonomy - Free-form within guardrails
    Level 4: Full autonomy - Complete freedom with monitoring
    Level 5: Self-improving - Autonomous strategy optimization
    """
    LEVEL_1_SCRIPTED = 1
    LEVEL_2_TEMPLATE = 2
    LEVEL_3_GUIDED = 3
    LEVEL_4_AUTONOMOUS = 4
    LEVEL_5_SELF_IMPROVING = 5


class ConversationPhase(Enum):
    """Phases of a collection conversation"""
    OPENING = "opening"
    VERIFICATION = "verification"
    DISCLOSURE = "disclosure"
    NEGOTIATION = "negotiation"
    OBJECTION_HANDLING = "objection_handling"
    COMMITMENT = "commitment"
    CLOSING = "closing"
    ESCALATION = "escalation"


class IntentType(Enum):
    """Consumer intent categories"""
    PAYMENT_READY = "payment_ready"
    PAYMENT_PLAN_REQUEST = "payment_plan_request"
    SETTLEMENT_INQUIRY = "settlement_inquiry"
    HARDSHIP_CLAIM = "hardship_claim"
    DISPUTE = "dispute"
    CEASE_DESIST = "cease_desist"
    VERIFICATION_REQUEST = "verification_request"
    CALLBACK_REQUEST = "callback_request"
    HANG_UP = "hang_up"
    CONFUSION = "confusion"
    ANGER = "anger"
    AGREEMENT = "agreement"
    STALLING = "stalling"
    UNKNOWN = "unknown"


class ViolationType(Enum):
    """Types of compliance violations"""
    FDCPA_HARASSMENT = "fdcpa_harassment"
    FDCPA_FALSE_REPRESENTATION = "fdcpa_false_representation"
    FDCPA_UNFAIR_PRACTICE = "fdcpa_unfair_practice"
    FDCPA_MISSING_DISCLOSURE = "fdcpa_missing_disclosure"
    TCPA_NO_CONSENT = "tcpa_no_consent"
    TCPA_TIME_VIOLATION = "tcpa_time_violation"
    REG_F_FREQUENCY = "reg_f_frequency"
    STATE_SPECIFIC = "state_specific"
    THREAT_VIOLATION = "threat_violation"
    HALLUCINATION = "hallucination"


class AgentState(Enum):
    """State of an individual agent"""
    IDLE = "idle"
    ENGAGED = "engaged"
    WAITING = "waiting"
    ESCALATED = "escalated"
    TERMINATED = "terminated"


class VoicePersona(Enum):
    """Available voice personas"""
    PROFESSIONAL_MALE = "professional_male"
    PROFESSIONAL_FEMALE = "professional_female"
    EMPATHETIC_MALE = "empathetic_male"
    EMPATHETIC_FEMALE = "empathetic_female"
    FIRM_MALE = "firm_male"
    FIRM_FEMALE = "firm_female"


class EmotionTone(Enum):
    """Emotion/tone modulation options"""
    NEUTRAL = "neutral"
    EMPATHETIC = "empathetic"
    URGENT = "urgent"
    REASSURING = "reassuring"
    FIRM = "firm"
    APOLOGETIC = "apologetic"


# FDCPA prohibited phrases and patterns
FDCPA_PROHIBITED_PATTERNS = [
    r"\b(arrest|jail|prison|incarcerat)\w*\b",
    r"\b(criminal|prosecut)\w*\b",
    r"\bgarnish\w*\b(?!.*court\s+order)",  # garnishment without court order
    r"\bseize\s+(your\s+)?(property|assets|home|car)\b",
    r"\b(sue|lawsuit|legal\s+action)\b(?!.*if\s+authorized)",
    r"\b(deadbeat|loser|criminal)\b",
    r"\bcontact\s+(your\s+)?(employer|boss|work)\b(?!.*with\s+consent)",
    r"\bpublish\s+(your\s+)?name\b",
    r"\bdisgrace\b",
]

# Required mini-miranda disclosure patterns
MINI_MIRANDA_PATTERNS = [
    r"debt\s+collector",
    r"attempt(ing)?\s+to\s+collect\s+(a\s+)?debt",
    r"information\s+(obtained|received)\s+will\s+be\s+used",
]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ConversationContext:
    """Complete context for a conversation"""
    conversation_id: str
    account_id: str
    debtor_profile: Dict[str, Any]

    # Conversation state
    phase: ConversationPhase = ConversationPhase.OPENING
    turn_count: int = 0
    start_time: datetime = field(default_factory=datetime.utcnow)

    # Dialogue history
    messages: List[Dict[str, Any]] = field(default_factory=list)
    intents_detected: List[IntentType] = field(default_factory=list)

    # Negotiation state
    current_offer: Optional[Decimal] = None
    offers_made: List[Dict] = field(default_factory=list)
    counter_offers: List[Dict] = field(default_factory=list)

    # Compliance state
    mini_miranda_delivered: bool = False
    verification_requested: bool = False
    cease_desist_requested: bool = False

    # Strategy state
    active_strategy: Optional[str] = None
    autonomy_level: AutonomyLevel = AutonomyLevel.LEVEL_3_GUIDED

    # Voice state
    voice_persona: VoicePersona = VoicePersona.PROFESSIONAL_FEMALE
    current_tone: EmotionTone = EmotionTone.NEUTRAL

    # Metadata
    channel: str = "voice"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationState:
    """Simplified conversation state for external access"""
    conversation_id: str
    phase: str
    turn_count: int
    mini_miranda_delivered: bool
    current_offer: Optional[float]
    active_strategy: str
    compliance_status: str

    @classmethod
    def from_context(cls, ctx: ConversationContext) -> "ConversationState":
        return cls(
            conversation_id=ctx.conversation_id,
            phase=ctx.phase.value,
            turn_count=ctx.turn_count,
            mini_miranda_delivered=ctx.mini_miranda_delivered,
            current_offer=float(ctx.current_offer) if ctx.current_offer else None,
            active_strategy=ctx.active_strategy or "default",
            compliance_status="compliant" if not ctx.cease_desist_requested else "restricted",
        )


@dataclass
class AgentResponse:
    """Response generated by the agent"""
    text: str
    intent: str
    phase: ConversationPhase
    suggested_action: Optional[str] = None
    offer: Optional[Dict] = None
    requires_human: bool = False
    confidence: float = 0.8
    latency_ms: float = 0.0
    cost_tokens: int = 0
    compliance_checked: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComplianceResult:
    """Result of compliance check"""
    is_compliant: bool
    violations: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    modified_text: Optional[str] = None
    kill_switch_triggered: bool = False
    requires_human_review: bool = False


@dataclass
class NegotiationOffer:
    """Settlement or payment plan offer"""
    offer_id: str
    offer_type: str  # "settlement", "pif", "payment_plan"
    amount: Decimal
    percentage_of_balance: float
    expiration: datetime
    terms: Dict[str, Any] = field(default_factory=dict)
    is_final: bool = False


@dataclass
class CostRecord:
    """Cost tracking for a conversation/interaction"""
    conversation_id: str
    llm_tokens_input: int = 0
    llm_tokens_output: int = 0
    voice_seconds: float = 0.0
    api_calls: int = 0
    total_cost_usd: float = 0.0
    revenue_generated: float = 0.0

    @property
    def roi(self) -> float:
        if self.total_cost_usd == 0:
            return 0.0
        return (self.revenue_generated - self.total_cost_usd) / self.total_cost_usd


@dataclass
class LearningOutcome:
    """Outcome record for learning loop"""
    conversation_id: str
    strategy_used: str
    autonomy_level: int
    initial_balance: float
    amount_collected: float
    collection_rate: float
    turn_count: int
    duration_seconds: float
    outcome_type: str  # "full_payment", "settlement", "payment_plan", "no_payment", "dispute", "cease"
    consumer_sentiment: str
    cost: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# 1. ORCHESTRATOR LLM LAYER
# =============================================================================

class OrchestratorLLM:
    """
    Central orchestration layer for conversation management.

    Responsibilities:
    - Conversation context management
    - Strategy decision engine
    - Multi-turn dialogue state tracking
    - Goal-oriented planning
    """

    # System prompts for different autonomy levels
    SYSTEM_PROMPTS = {
        AutonomyLevel.LEVEL_1_SCRIPTED: """You are a debt collection assistant operating in SCRIPTED mode.
You MUST only use the exact pre-approved scripts provided. Do not deviate from the script.
Always include required disclosures. Never make promises not in the script.""",

        AutonomyLevel.LEVEL_2_TEMPLATE: """You are a debt collection assistant operating in TEMPLATE mode.
Use the provided templates but personalize with the consumer's information.
Fill in variables like {name}, {amount}, {creditor} from the profile.
Stay within the template structure but make it natural.""",

        AutonomyLevel.LEVEL_3_GUIDED: """You are a debt collection assistant operating in GUIDED AUTONOMY mode.
You may engage in natural conversation within these guardrails:
- Always maintain professional tone
- Never threaten actions you won't take
- Always include required disclosures
- Stay focused on resolution
- Escalate disputes and hardship claims appropriately""",

        AutonomyLevel.LEVEL_4_AUTONOMOUS: """You are an autonomous debt collection agent.
You have full freedom to conduct the conversation naturally while:
- Maximizing collection probability
- Maintaining regulatory compliance
- Adapting to consumer emotional state
- Using psychological principles ethically
All responses are monitored for compliance.""",

        AutonomyLevel.LEVEL_5_SELF_IMPROVING: """You are a self-improving debt collection agent.
Beyond autonomous operation, you:
- Experiment with new approaches (within compliance)
- Track outcomes for strategy optimization
- Propose improvements to scripts and strategies
- Balance exploration vs exploitation
Your innovations will be evaluated and may be adopted system-wide.""",
    }

    def __init__(self, model_name: str = "gpt-4"):
        self.model_name = model_name
        self._conversations: Dict[str, ConversationContext] = {}
        self._strategy_cache: Dict[str, Dict] = {}
        self._lock = threading.Lock()

        # Goal planning state
        self._active_goals: Dict[str, List[str]] = {}

        # Dialogue state machine
        self._state_transitions = self._build_state_machine()

        logger.info(f"OrchestratorLLM initialized with model: {model_name}")

    def _build_state_machine(self) -> Dict[ConversationPhase, List[ConversationPhase]]:
        """Build valid state transitions for dialogue"""
        return {
            ConversationPhase.OPENING: [
                ConversationPhase.VERIFICATION,
                ConversationPhase.DISCLOSURE,
                ConversationPhase.ESCALATION,
            ],
            ConversationPhase.VERIFICATION: [
                ConversationPhase.DISCLOSURE,
                ConversationPhase.ESCALATION,
            ],
            ConversationPhase.DISCLOSURE: [
                ConversationPhase.NEGOTIATION,
                ConversationPhase.OBJECTION_HANDLING,
                ConversationPhase.ESCALATION,
            ],
            ConversationPhase.NEGOTIATION: [
                ConversationPhase.COMMITMENT,
                ConversationPhase.OBJECTION_HANDLING,
                ConversationPhase.ESCALATION,
                ConversationPhase.CLOSING,
            ],
            ConversationPhase.OBJECTION_HANDLING: [
                ConversationPhase.NEGOTIATION,
                ConversationPhase.COMMITMENT,
                ConversationPhase.ESCALATION,
                ConversationPhase.CLOSING,
            ],
            ConversationPhase.COMMITMENT: [
                ConversationPhase.CLOSING,
                ConversationPhase.NEGOTIATION,  # If commitment fails
            ],
            ConversationPhase.CLOSING: [],  # Terminal state
            ConversationPhase.ESCALATION: [],  # Terminal state
        }

    async def start_conversation(
        self,
        account_id: str,
        debtor_profile: Dict[str, Any],
        channel: str = "voice",
        autonomy_level: AutonomyLevel = AutonomyLevel.LEVEL_3_GUIDED,
    ) -> ConversationContext:
        """Initialize a new conversation"""
        conversation_id = f"conv_{uuid.uuid4().hex[:12]}"

        context = ConversationContext(
            conversation_id=conversation_id,
            account_id=account_id,
            debtor_profile=debtor_profile,
            channel=channel,
            autonomy_level=autonomy_level,
        )

        # Set initial strategy based on profile
        context.active_strategy = await self._select_initial_strategy(debtor_profile)

        # Select appropriate voice persona
        context.voice_persona = await self._select_voice_persona(debtor_profile)

        # Set initial goals
        self._active_goals[conversation_id] = [
            "deliver_mini_miranda",
            "verify_identity",
            "present_settlement_options",
            "secure_commitment",
        ]

        with self._lock:
            self._conversations[conversation_id] = context

        logger.info(f"Started conversation {conversation_id} for account {account_id}")
        return context

    async def _select_initial_strategy(self, profile: Dict) -> str:
        """Select initial negotiation strategy based on profile"""
        recovery_prob = profile.get("recovery_probability", 0.5)
        balance = float(profile.get("balance", 500))
        payment_history = profile.get("payment_history", [])

        # Strategy selection logic
        if recovery_prob > 0.7:
            return "aggressive_full"  # Push for full payment
        elif recovery_prob > 0.5:
            if balance < 300:
                return "quick_settlement"  # Fast resolution
            else:
                return "graduated_concession"  # Negotiated settlement
        elif recovery_prob > 0.3:
            return "payment_plan_focus"  # Emphasize affordability
        else:
            return "immediate_settlement"  # Deep discount to close

    async def _select_voice_persona(self, profile: Dict) -> VoicePersona:
        """Select appropriate voice persona based on debtor profile"""
        age = profile.get("age", 40)
        gender_preference = profile.get("agent_gender_preference")
        segment = profile.get("segment", "general")

        # Match persona to consumer preferences and segment
        if gender_preference == "male":
            if segment == "hardship":
                return VoicePersona.EMPATHETIC_MALE
            elif segment == "professional":
                return VoicePersona.PROFESSIONAL_MALE
            else:
                return VoicePersona.FIRM_MALE
        else:
            if segment == "hardship":
                return VoicePersona.EMPATHETIC_FEMALE
            elif segment == "professional":
                return VoicePersona.PROFESSIONAL_FEMALE
            else:
                return VoicePersona.PROFESSIONAL_FEMALE

    async def process_turn(
        self,
        conversation_id: str,
        consumer_input: str,
        audio_features: Optional[Dict] = None,
    ) -> Tuple[AgentResponse, ConversationContext]:
        """
        Process a conversation turn.

        Args:
            conversation_id: Active conversation ID
            consumer_input: Text from consumer (ASR output or text)
            audio_features: Optional voice analysis features (pitch, pace, emotion)

        Returns:
            Tuple of (agent response, updated context)
        """
        start_time = time.time()

        with self._lock:
            context = self._conversations.get(conversation_id)

        if not context:
            raise ValueError(f"Unknown conversation: {conversation_id}")

        # Record consumer message
        context.messages.append({
            "role": "consumer",
            "content": consumer_input,
            "timestamp": datetime.utcnow().isoformat(),
            "audio_features": audio_features,
        })
        context.turn_count += 1

        # Detect intent
        intent = await self._detect_intent(consumer_input, context)
        context.intents_detected.append(intent)

        # Update emotional tone based on audio features and intent
        context.current_tone = await self._determine_tone(intent, audio_features, context)

        # Determine phase transition
        new_phase = await self._determine_phase_transition(intent, context)
        if new_phase:
            context.phase = new_phase

        # Generate response based on autonomy level
        response_text = await self._generate_response(intent, context)

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        # Build response object
        response = AgentResponse(
            text=response_text,
            intent=intent.value,
            phase=context.phase,
            confidence=0.85,  # Would come from model
            latency_ms=latency_ms,
            cost_tokens=len(response_text.split()) * 2,  # Rough estimate
        )

        # Record agent message
        context.messages.append({
            "role": "agent",
            "content": response_text,
            "timestamp": datetime.utcnow().isoformat(),
            "phase": context.phase.value,
            "tone": context.current_tone.value,
        })

        # Update goals
        await self._update_goals(conversation_id, intent, context)

        return response, context

    async def _detect_intent(
        self,
        text: str,
        context: ConversationContext,
    ) -> IntentType:
        """Detect consumer intent from text"""
        text_lower = text.lower().strip()

        # Intent patterns (would use ML model in production)
        intent_patterns = {
            IntentType.PAYMENT_READY: [
                r"\b(pay|paying|make\s+payment|ready\s+to\s+pay)\b",
                r"\b(take\s+my\s+card|credit\s+card|debit)\b",
            ],
            IntentType.PAYMENT_PLAN_REQUEST: [
                r"\b(payment\s+plan|monthly|installment|split)\b",
                r"\b(can't\s+afford|afford\s+to|afford\s+it)\b.*\b(once|full)\b",
            ],
            IntentType.SETTLEMENT_INQUIRY: [
                r"\b(settle|settlement|less\s+than|reduce|discount)\b",
                r"\b(what.+offer|best.+offer|can\s+you\s+do)\b",
            ],
            IntentType.HARDSHIP_CLAIM: [
                r"\b(hardship|unemployed|lost\s+job|disabled|sick|hospital)\b",
                r"\b(can't\s+pay|no\s+money|no\s+income|broke)\b",
            ],
            IntentType.DISPUTE: [
                r"\b(dispute|not\s+mine|don't\s+owe|fraud|identity\s+theft)\b",
                r"\b(never\s+had|didn't\s+open|wrong\s+person)\b",
            ],
            IntentType.CEASE_DESIST: [
                r"\b(stop\s+calling|cease|desist|don't\s+contact|lawyer|attorney)\b",
                r"\b(harassment|sue\s+you|report\s+you)\b",
            ],
            IntentType.VERIFICATION_REQUEST: [
                r"\b(verify|validation|proof|documentation|send\s+me)\b",
                r"\b(who\s+are\s+you|what\s+company|where.+calling\s+from)\b",
            ],
            IntentType.CALLBACK_REQUEST: [
                r"\b(call\s+(me\s+)?back|not\s+a\s+good\s+time|busy|at\s+work)\b",
                r"\b(later|tomorrow|next\s+week)\b",
            ],
            IntentType.AGREEMENT: [
                r"\b(yes|okay|ok|sure|fine|agree|sounds\s+good|deal)\b",
                r"\b(let's\s+do\s+it|i'll\s+take\s+it|accepted)\b",
            ],
            IntentType.ANGER: [
                r"\b(angry|pissed|furious|damn|hell|leave\s+me\s+alone)\b",
                r"[!]{2,}",
            ],
            IntentType.HANG_UP: [
                r"\b(hanging\s+up|goodbye|bye|click)\b",
            ],
        }

        for intent, patterns in intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return intent

        return IntentType.UNKNOWN

    async def _determine_tone(
        self,
        intent: IntentType,
        audio_features: Optional[Dict],
        context: ConversationContext,
    ) -> EmotionTone:
        """Determine appropriate emotional tone for response"""

        # Default tone mapping by intent
        intent_tone_map = {
            IntentType.HARDSHIP_CLAIM: EmotionTone.EMPATHETIC,
            IntentType.ANGER: EmotionTone.REASSURING,
            IntentType.DISPUTE: EmotionTone.NEUTRAL,
            IntentType.PAYMENT_READY: EmotionTone.REASSURING,
            IntentType.CEASE_DESIST: EmotionTone.NEUTRAL,
            IntentType.STALLING: EmotionTone.FIRM,
        }

        base_tone = intent_tone_map.get(intent, EmotionTone.NEUTRAL)

        # Adjust based on audio features if available
        if audio_features:
            consumer_stress = audio_features.get("stress_level", 0.5)
            consumer_pace = audio_features.get("speech_pace", "normal")

            if consumer_stress > 0.7:
                base_tone = EmotionTone.EMPATHETIC
            elif consumer_pace == "fast" and intent == IntentType.ANGER:
                base_tone = EmotionTone.REASSURING

        # Adjust based on conversation progress
        if context.turn_count > 10 and not context.current_offer:
            base_tone = EmotionTone.URGENT

        return base_tone

    async def _determine_phase_transition(
        self,
        intent: IntentType,
        context: ConversationContext,
    ) -> Optional[ConversationPhase]:
        """Determine if conversation should transition to new phase"""

        current_phase = context.phase
        valid_transitions = self._state_transitions.get(current_phase, [])

        # Intent-based transitions
        if intent == IntentType.CEASE_DESIST:
            return ConversationPhase.ESCALATION

        if intent == IntentType.DISPUTE:
            return ConversationPhase.ESCALATION

        if intent == IntentType.VERIFICATION_REQUEST:
            if current_phase == ConversationPhase.OPENING:
                return ConversationPhase.VERIFICATION

        if intent in [IntentType.PAYMENT_READY, IntentType.SETTLEMENT_INQUIRY,
                      IntentType.PAYMENT_PLAN_REQUEST]:
            if ConversationPhase.NEGOTIATION in valid_transitions:
                return ConversationPhase.NEGOTIATION

        if intent == IntentType.AGREEMENT and context.current_offer:
            if ConversationPhase.COMMITMENT in valid_transitions:
                return ConversationPhase.COMMITMENT

        # Phase-based auto-transitions
        if current_phase == ConversationPhase.OPENING and context.turn_count >= 2:
            if context.mini_miranda_delivered:
                return ConversationPhase.DISCLOSURE

        return None

    async def _generate_response(
        self,
        intent: IntentType,
        context: ConversationContext,
    ) -> str:
        """Generate response based on autonomy level and context"""

        autonomy = context.autonomy_level

        if autonomy == AutonomyLevel.LEVEL_1_SCRIPTED:
            return await self._generate_scripted_response(intent, context)
        elif autonomy == AutonomyLevel.LEVEL_2_TEMPLATE:
            return await self._generate_template_response(intent, context)
        elif autonomy == AutonomyLevel.LEVEL_3_GUIDED:
            return await self._generate_guided_response(intent, context)
        elif autonomy == AutonomyLevel.LEVEL_4_AUTONOMOUS:
            return await self._generate_autonomous_response(intent, context)
        else:  # LEVEL_5_SELF_IMPROVING
            return await self._generate_self_improving_response(intent, context)

    async def _generate_scripted_response(
        self,
        intent: IntentType,
        context: ConversationContext,
    ) -> str:
        """Level 1: Pure scripted responses"""

        scripts = {
            ConversationPhase.OPENING: {
                "default": "Hello, this is QUAN Recovery calling about a personal business matter. "
                          "Is this {debtor_name}?",
            },
            ConversationPhase.DISCLOSURE: {
                "default": "This is an attempt to collect a debt, and any information obtained "
                          "will be used for that purpose. This call is from QUAN Recovery, "
                          "a debt collector. We are calling about your {creditor} account "
                          "with a balance of ${balance}.",
            },
            ConversationPhase.NEGOTIATION: {
                IntentType.SETTLEMENT_INQUIRY: "I can offer you a settlement of ${settlement_amount}, "
                                               "which is {settlement_percent}% of your balance. "
                                               "This offer is valid for 30 days.",
                IntentType.PAYMENT_PLAN_REQUEST: "We can set up a payment plan of ${monthly_payment} "
                                                 "per month over {plan_months} months.",
                "default": "How would you like to resolve this account today?",
            },
        }

        phase_scripts = scripts.get(context.phase, {})
        script = phase_scripts.get(intent, phase_scripts.get("default", ""))

        # Variable substitution
        profile = context.debtor_profile
        script = script.format(
            debtor_name=profile.get("name", "there"),
            creditor=profile.get("original_creditor", "your creditor"),
            balance=profile.get("balance", 0),
            settlement_amount=float(profile.get("balance", 0)) * 0.6,
            settlement_percent=60,
            monthly_payment=float(profile.get("balance", 0)) / 6,
            plan_months=6,
        )

        return script

    async def _generate_template_response(
        self,
        intent: IntentType,
        context: ConversationContext,
    ) -> str:
        """Level 2: Template-based with personalization"""

        base_response = await self._generate_scripted_response(intent, context)

        # Add personalization based on tone
        tone_prefixes = {
            EmotionTone.EMPATHETIC: "I understand this can be difficult. ",
            EmotionTone.URGENT: "This is a time-sensitive matter. ",
            EmotionTone.REASSURING: "I'm here to help you resolve this. ",
            EmotionTone.FIRM: "It's important we address this today. ",
        }

        prefix = tone_prefixes.get(context.current_tone, "")

        return prefix + base_response

    async def _generate_guided_response(
        self,
        intent: IntentType,
        context: ConversationContext,
    ) -> str:
        """Level 3: Guided autonomy within guardrails"""

        # Build prompt with constraints
        guardrails = [
            "Stay professional and respectful",
            "Never threaten actions not authorized",
            "Always provide accurate balance information",
            "Offer realistic settlement options",
            "Acknowledge hardship when claimed",
        ]

        # Generate based on intent
        if intent == IntentType.HARDSHIP_CLAIM:
            base = "I understand you're going through a difficult time. "
            options = "We do have hardship programs available. Can you tell me more about your situation so I can see what options we might have?"
        elif intent == IntentType.ANGER:
            base = "I apologize if this call has come at a bad time. "
            options = "My goal is to help you resolve this account. Would you like to hear about some options that might work for your situation?"
        elif intent == IntentType.SETTLEMENT_INQUIRY:
            settlement_pct = self._calculate_settlement_offer(context)
            settlement_amt = float(context.debtor_profile.get("balance", 500)) * settlement_pct
            base = f"Yes, I can offer you a settlement. "
            options = f"We can settle this account today for ${settlement_amt:.2f}, which is {settlement_pct*100:.0f}% of your balance. This is a significant savings."
        else:
            base = ""
            options = await self._generate_template_response(intent, context)

        return base + options

    async def _generate_autonomous_response(
        self,
        intent: IntentType,
        context: ConversationContext,
    ) -> str:
        """Level 4: Full autonomy with monitoring"""

        # Would call actual LLM here
        # For demo, use enhanced guided response

        response = await self._generate_guided_response(intent, context)

        # Add autonomous enhancements
        if context.turn_count > 5 and intent == IntentType.STALLING:
            response += " I want to make sure we find a solution today that works for you."

        return response

    async def _generate_self_improving_response(
        self,
        intent: IntentType,
        context: ConversationContext,
    ) -> str:
        """Level 5: Self-improving with experimentation"""

        # Get base response
        response = await self._generate_autonomous_response(intent, context)

        # Potentially experiment with variations (A/B testing)
        if random.random() < 0.1:  # 10% exploration rate
            # Try alternative phrasings
            alternatives = [
                "What would make this work for you today?",
                "I have some flexibility here - what would help?",
                "Let me see what the best option I can offer is.",
            ]
            if intent == IntentType.STALLING:
                response += " " + random.choice(alternatives)

        return response

    def _calculate_settlement_offer(self, context: ConversationContext) -> float:
        """Calculate appropriate settlement percentage"""
        profile = context.debtor_profile

        recovery_prob = profile.get("recovery_probability", 0.5)
        dpd = profile.get("days_past_due", 60)
        offers_made = len(context.offers_made)

        # Base settlement
        base_pct = 0.70

        # Adjust for recovery probability
        if recovery_prob < 0.3:
            base_pct = 0.40
        elif recovery_prob < 0.5:
            base_pct = 0.55

        # Adjust for DPD
        if dpd > 180:
            base_pct -= 0.10
        elif dpd > 90:
            base_pct -= 0.05

        # Adjust for offers made
        base_pct -= (offers_made * 0.05)

        return max(0.30, min(0.90, base_pct))

    async def _update_goals(
        self,
        conversation_id: str,
        intent: IntentType,
        context: ConversationContext,
    ) -> None:
        """Update conversation goals based on progress"""
        goals = self._active_goals.get(conversation_id, [])

        # Check off completed goals
        if context.mini_miranda_delivered and "deliver_mini_miranda" in goals:
            goals.remove("deliver_mini_miranda")

        if intent == IntentType.AGREEMENT and "secure_commitment" in goals:
            goals.remove("secure_commitment")
            goals.append("process_payment")

        self._active_goals[conversation_id] = goals

    def get_conversation(self, conversation_id: str) -> Optional[ConversationContext]:
        """Get conversation context"""
        with self._lock:
            return self._conversations.get(conversation_id)

    async def end_conversation(
        self,
        conversation_id: str,
        outcome: str,
    ) -> Dict[str, Any]:
        """End a conversation and return summary"""
        with self._lock:
            context = self._conversations.pop(conversation_id, None)

        if not context:
            return {"error": "Conversation not found"}

        # Clean up goals
        self._active_goals.pop(conversation_id, None)

        duration = (datetime.utcnow() - context.start_time).total_seconds()

        return {
            "conversation_id": conversation_id,
            "account_id": context.account_id,
            "duration_seconds": duration,
            "turn_count": context.turn_count,
            "final_phase": context.phase.value,
            "outcome": outcome,
            "offers_made": len(context.offers_made),
            "mini_miranda_delivered": context.mini_miranda_delivered,
        }


# =============================================================================
# 2. RAG INTEGRATION
# =============================================================================

class RAGIntegration:
    """
    Retrieval-Augmented Generation for real-time context.

    Provides:
    - Real-time debtor profile retrieval
    - State-specific compliance rules lookup
    - Historical interaction context
    - Settlement history and patterns
    """

    def __init__(self):
        # Vector store connections (would use Pinecone/Weaviate in production)
        self._debtor_store: Dict[str, Dict] = {}
        self._compliance_store: Dict[str, Dict] = {}
        self._interaction_store: Dict[str, List] = {}
        self._settlement_patterns: Dict[str, Dict] = {}

        # Embedding cache
        self._embedding_cache: Dict[str, List[float]] = {}

        # Initialize compliance rules
        self._load_compliance_rules()

        logger.info("RAGIntegration initialized")

    def _load_compliance_rules(self) -> None:
        """Load state-specific compliance rules"""
        self._compliance_store = {
            "CA": {
                "sol_years": 4,
                "requires_license": True,
                "additional_disclosures": [
                    "California law requires us to notify you that a negative credit report "
                    "may be submitted to a credit reporting agency."
                ],
                "max_interest": 0.10,
                "wage_garnishment_limit": 0.25,
            },
            "NY": {
                "sol_years": 6,
                "requires_license": True,
                "additional_disclosures": [
                    "New York law gives you certain rights. Please visit our website for details."
                ],
                "time_barred_notice_required": True,
            },
            "TX": {
                "sol_years": 4,
                "requires_license": False,
                "community_property_state": True,
            },
            "FL": {
                "sol_years": 5,
                "requires_license": True,
                "exempt_head_of_household": True,
            },
            "DEFAULT": {
                "sol_years": 6,
                "requires_license": False,
                "additional_disclosures": [],
            },
        }

    async def get_debtor_profile(
        self,
        account_id: str,
        include_history: bool = True,
    ) -> Dict[str, Any]:
        """
        Retrieve comprehensive debtor profile.

        Combines:
        - Account data
        - Payment history
        - Interaction history
        - Behavioral signals
        - Contact preferences
        """
        # Would query actual database/vector store
        profile = self._debtor_store.get(account_id, {})

        if include_history:
            profile["interaction_history"] = await self.get_interaction_history(account_id)
            profile["settlement_patterns"] = await self.get_settlement_patterns(account_id)

        # Enrich with inferred data
        profile["computed"] = {
            "days_since_last_contact": self._calculate_days_since_contact(account_id),
            "recommended_channel": self._infer_preferred_channel(profile),
            "best_contact_time": self._infer_best_contact_time(profile),
            "sentiment_history": self._compute_sentiment_trend(account_id),
        }

        return profile

    async def get_compliance_rules(
        self,
        state: str,
        debt_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get state-specific compliance rules.

        Returns relevant rules for the consumer's state including:
        - Statute of limitations
        - Required disclosures
        - Licensing requirements
        - Collection restrictions
        """
        state_upper = state.upper()
        rules = self._compliance_store.get(state_upper, self._compliance_store["DEFAULT"]).copy()

        # Add debt-type specific rules
        if debt_type:
            debt_rules = self._get_debt_type_rules(debt_type)
            rules.update(debt_rules)

        # Add federal rules (always apply)
        rules["federal"] = {
            "fdcpa_applies": True,
            "tcpa_applies": True,
            "reg_f_applies": True,
            "cfpb_rules": True,
        }

        return rules

    def _get_debt_type_rules(self, debt_type: str) -> Dict[str, Any]:
        """Get rules specific to debt type"""
        debt_rules = {
            "medical": {
                "special_protections": True,
                "credit_reporting_delay_days": 365,  # 1 year delay
                "hipaa_applies": True,
            },
            "student": {
                "federal_rules": True,
                "rehabilitation_options": True,
            },
            "credit_card": {
                "standard_rules": True,
            },
        }
        return debt_rules.get(debt_type, {})

    async def get_interaction_history(
        self,
        account_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get historical interactions for context"""
        history = self._interaction_store.get(account_id, [])
        return history[-limit:]

    async def get_settlement_patterns(
        self,
        account_id: str,
    ) -> Dict[str, Any]:
        """
        Get settlement patterns for similar accounts.

        Returns:
        - Average settlement percentage for similar profiles
        - Common objection patterns
        - Successful resolution strategies
        """
        # Would use ML model to find similar accounts
        patterns = self._settlement_patterns.get(account_id, {})

        if not patterns:
            # Default patterns
            patterns = {
                "avg_settlement_pct": 0.55,
                "avg_turns_to_settle": 8,
                "common_objections": ["can't afford", "not mine", "need time"],
                "successful_approaches": ["payment plan", "hardship review"],
            }

        return patterns

    async def store_interaction(
        self,
        account_id: str,
        interaction: Dict[str, Any],
    ) -> None:
        """Store interaction for future retrieval"""
        if account_id not in self._interaction_store:
            self._interaction_store[account_id] = []

        interaction["timestamp"] = datetime.utcnow().isoformat()
        self._interaction_store[account_id].append(interaction)

    async def semantic_search(
        self,
        query: str,
        collection: str = "knowledge_base",
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search for relevant information.

        Used for:
        - Finding relevant compliance information
        - Retrieving similar case resolutions
        - Looking up policy/procedure information
        """
        # Would use actual embedding model and vector search
        # Demo implementation returns mock results

        results = []

        if "hardship" in query.lower():
            results.append({
                "content": "Hardship programs: We offer reduced payment plans for consumers "
                          "experiencing financial hardship. Documentation may be required.",
                "relevance": 0.92,
            })

        if "dispute" in query.lower():
            results.append({
                "content": "Dispute handling: All disputes must be acknowledged in writing. "
                          "Collection activities must cease during verification period.",
                "relevance": 0.89,
            })

        return results[:top_k]

    def _calculate_days_since_contact(self, account_id: str) -> int:
        """Calculate days since last contact"""
        history = self._interaction_store.get(account_id, [])
        if not history:
            return 999

        last = history[-1]
        last_date = datetime.fromisoformat(last.get("timestamp", datetime.utcnow().isoformat()))
        return (datetime.utcnow() - last_date).days

    def _infer_preferred_channel(self, profile: Dict) -> str:
        """Infer preferred contact channel from profile"""
        # Would use ML model
        if profile.get("has_mobile_app"):
            return "push"
        elif profile.get("is_digital_native", True):
            return "sms"
        elif profile.get("email_valid"):
            return "email"
        else:
            return "voice"

    def _infer_best_contact_time(self, profile: Dict) -> str:
        """Infer best time to contact"""
        # Would use behavioral analysis
        return profile.get("preferred_contact_time", "afternoon")

    def _compute_sentiment_trend(self, account_id: str) -> str:
        """Compute sentiment trend from interactions"""
        history = self._interaction_store.get(account_id, [])
        if not history:
            return "neutral"

        sentiments = [h.get("sentiment", "neutral") for h in history[-5:]]

        # Simple trend detection
        if sentiments and sentiments[-1] == "positive":
            return "improving"
        elif sentiments and sentiments[-1] == "negative":
            return "declining"
        return "stable"


# =============================================================================
# 3. COMPLIANCE MONITOR (Constitutional AI)
# =============================================================================

class ComplianceMonitor:
    """
    Real-time compliance monitoring using Constitutional AI principles.

    Implements:
    - Real-time conversation monitoring
    - FDCPA violation detection
    - Mini-Miranda enforcement
    - Kill-switch for hallucination detection
    - Threat validation (can't threaten what you won't do)
    """

    def __init__(self):
        self._violation_log: List[Dict] = []
        self._active_monitors: Dict[str, Dict] = {}
        self._threat_registry: Set[str] = set()  # Actions we're authorized to take

        # Initialize authorized threats
        self._initialize_authorized_actions()

        logger.info("ComplianceMonitor initialized")

    def _initialize_authorized_actions(self) -> None:
        """Initialize actions we're actually authorized to take"""
        self._threat_registry = {
            "report_credit_bureaus",
            "continue_collection_efforts",
            "offer_settlement",
            "refer_to_legal_review",  # Not the same as threatening lawsuit
        }

    async def check_response(
        self,
        response_text: str,
        context: ConversationContext,
        check_hallucination: bool = True,
    ) -> ComplianceResult:
        """
        Check response for compliance before delivery.

        This is the primary compliance gate - all responses must pass.
        """
        violations = []
        warnings = []
        modified_text = response_text
        kill_switch = False

        # 1. Check for FDCPA prohibited content
        fdcpa_result = await self._check_fdcpa_compliance(response_text, context)
        violations.extend(fdcpa_result.get("violations", []))
        if fdcpa_result.get("modified_text"):
            modified_text = fdcpa_result["modified_text"]

        # 2. Check mini-miranda requirements
        if not context.mini_miranda_delivered and context.phase in [
            ConversationPhase.OPENING,
            ConversationPhase.DISCLOSURE,
        ]:
            miranda_result = await self._check_mini_miranda(modified_text, context)
            if not miranda_result["has_disclosure"]:
                warnings.append("Mini-Miranda not yet delivered")

        # 3. Check threat validation
        threat_result = await self._validate_threats(modified_text, context)
        violations.extend(threat_result.get("violations", []))
        if threat_result.get("modified_text"):
            modified_text = threat_result["modified_text"]

        # 4. Check for hallucinations
        if check_hallucination:
            hallucination_result = await self._detect_hallucinations(
                modified_text, context
            )
            if hallucination_result["has_hallucination"]:
                violations.append({
                    "type": ViolationType.HALLUCINATION.value,
                    "description": hallucination_result["description"],
                    "severity": "critical",
                })
                kill_switch = True

        # 5. State-specific compliance
        state = context.debtor_profile.get("state", "")
        state_result = await self._check_state_compliance(modified_text, state, context)
        violations.extend(state_result.get("violations", []))
        warnings.extend(state_result.get("warnings", []))

        # Determine if human review needed
        requires_human = (
            kill_switch or
            any(v.get("severity") == "critical" for v in violations) or
            context.cease_desist_requested
        )

        result = ComplianceResult(
            is_compliant=len(violations) == 0,
            violations=violations,
            warnings=warnings,
            modified_text=modified_text if modified_text != response_text else None,
            kill_switch_triggered=kill_switch,
            requires_human_review=requires_human,
        )

        # Log if violations found
        if violations:
            await self._log_violation(context.conversation_id, result)

        return result

    async def _check_fdcpa_compliance(
        self,
        text: str,
        context: ConversationContext,
    ) -> Dict[str, Any]:
        """Check for FDCPA violations"""
        violations = []
        modified_text = text

        for pattern in FDCPA_PROHIBITED_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                violations.append({
                    "type": ViolationType.FDCPA_FALSE_REPRESENTATION.value,
                    "description": f"Prohibited content detected: {matches[0]}",
                    "severity": "high",
                    "pattern": pattern,
                })
                # Remove prohibited content
                modified_text = re.sub(pattern, "[REMOVED]", modified_text, flags=re.IGNORECASE)

        return {
            "violations": violations,
            "modified_text": modified_text if modified_text != text else None,
        }

    async def _check_mini_miranda(
        self,
        text: str,
        context: ConversationContext,
    ) -> Dict[str, Any]:
        """Check for mini-miranda disclosure"""
        has_disclosure = False

        for pattern in MINI_MIRANDA_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                has_disclosure = True
                break

        return {"has_disclosure": has_disclosure}

    async def _validate_threats(
        self,
        text: str,
        context: ConversationContext,
    ) -> Dict[str, Any]:
        """
        Validate that we only threaten actions we're authorized to take.

        Constitutional AI principle: Don't threaten what you won't do.
        """
        violations = []
        modified_text = text

        # Threat patterns and their required authorizations
        threat_patterns = {
            r"\b(will|going to)\s+(sue|file\s+lawsuit|take\s+legal\s+action)\b": "legal_action",
            r"\bgarnish(ment)?\s+(your\s+)?wages\b": "wage_garnishment",
            r"\bseize\s+(your\s+)?(property|assets|home)\b": "asset_seizure",
            r"\barrest\b": "criminal_referral",
            r"\breport\s+(to|your)\s+(employer|work)\b": "employer_contact",
        }

        for pattern, required_auth in threat_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                if required_auth not in self._threat_registry:
                    violations.append({
                        "type": ViolationType.THREAT_VIOLATION.value,
                        "description": f"Unauthorized threat: {required_auth}",
                        "severity": "critical",
                    })
                    # Remove the threat
                    modified_text = re.sub(pattern, "[REMOVED]", modified_text, flags=re.IGNORECASE)

        return {
            "violations": violations,
            "modified_text": modified_text if modified_text != text else None,
        }

    async def _detect_hallucinations(
        self,
        text: str,
        context: ConversationContext,
    ) -> Dict[str, Any]:
        """
        Detect potential hallucinations in generated responses.

        Checks for:
        - Incorrect account information
        - Made-up settlement offers not in authority
        - False claims about creditor or debt
        - Incorrect legal statements
        """
        profile = context.debtor_profile
        has_hallucination = False
        description = ""

        # Check balance accuracy
        balance = profile.get("balance", 0)
        balance_patterns = re.findall(r'\$([0-9,]+(?:\.[0-9]{2})?)', text)
        for amount_str in balance_patterns:
            amount = float(amount_str.replace(",", ""))
            # If mentioned amount is way off from actual balance
            if amount > float(balance) * 1.5 or amount < float(balance) * 0.2:
                if "settlement" not in text.lower():  # Allow settlement amounts
                    has_hallucination = True
                    description = f"Incorrect balance mentioned: ${amount} vs actual ${balance}"
                    break

        # Check creditor name
        creditor = profile.get("original_creditor", "")
        if creditor:
            creditor_lower = creditor.lower()
            # Look for creditor mentions that don't match
            creditor_patterns = re.findall(r'(?:from|with|for)\s+(\w+(?:\s+\w+)?)\s+(?:account|debt|balance)', text, re.IGNORECASE)
            for mentioned in creditor_patterns:
                if mentioned.lower() not in creditor_lower and creditor_lower not in mentioned.lower():
                    has_hallucination = True
                    description = f"Incorrect creditor mentioned: {mentioned} vs actual {creditor}"
                    break

        return {
            "has_hallucination": has_hallucination,
            "description": description,
        }

    async def _check_state_compliance(
        self,
        text: str,
        state: str,
        context: ConversationContext,
    ) -> Dict[str, Any]:
        """Check state-specific compliance requirements"""
        violations = []
        warnings = []

        # State-specific rules would be loaded from RAG
        state_rules = {
            "CA": {
                "required_disclosures": [
                    "The law limits how long you can be sued on a debt"
                ],
                "time_barred_warning": True,
            },
            "NY": {
                "required_disclosures": [],
                "time_barred_warning": True,
            },
        }

        rules = state_rules.get(state.upper(), {})

        # Check time-barred debt warning
        if rules.get("time_barred_warning"):
            profile = context.debtor_profile
            charge_off_date = profile.get("charge_off_date")
            if charge_off_date:
                # Would check if debt is time-barred
                warnings.append(f"Verify debt is not time-barred in {state}")

        return {
            "violations": violations,
            "warnings": warnings,
        }

    async def _log_violation(
        self,
        conversation_id: str,
        result: ComplianceResult,
    ) -> None:
        """Log compliance violation for audit"""
        log_entry = {
            "conversation_id": conversation_id,
            "timestamp": datetime.utcnow().isoformat(),
            "violations": result.violations,
            "warnings": result.warnings,
            "kill_switch": result.kill_switch_triggered,
        }
        self._violation_log.append(log_entry)

        if result.kill_switch_triggered:
            logger.critical(f"KILL SWITCH TRIGGERED: {conversation_id}")
        elif result.violations:
            logger.warning(f"Compliance violations in {conversation_id}: {len(result.violations)}")

    async def monitor_conversation(
        self,
        conversation_id: str,
        context: ConversationContext,
    ) -> Dict[str, Any]:
        """
        Real-time conversation monitoring.

        Returns monitoring state and any alerts.
        """
        alerts = []

        # Check conversation duration
        duration = (datetime.utcnow() - context.start_time).total_seconds()
        if duration > 600:  # 10 minutes
            alerts.append({
                "type": "duration_warning",
                "message": "Conversation exceeding 10 minutes",
            })

        # Check turn count
        if context.turn_count > 20:
            alerts.append({
                "type": "turn_count_warning",
                "message": "High turn count - consider escalation",
            })

        # Check for repeated objections
        intent_counts = defaultdict(int)
        for intent in context.intents_detected:
            intent_counts[intent] += 1

        for intent, count in intent_counts.items():
            if count >= 3 and intent in [IntentType.HARDSHIP_CLAIM, IntentType.DISPUTE]:
                alerts.append({
                    "type": "repeated_objection",
                    "message": f"Consumer has stated {intent.value} {count} times",
                    "action": "Consider escalation",
                })

        # Check for anger escalation
        anger_count = intent_counts.get(IntentType.ANGER, 0)
        if anger_count >= 2:
            alerts.append({
                "type": "anger_escalation",
                "message": "Consumer showing signs of anger",
                "action": "Use de-escalation techniques",
            })

        return {
            "conversation_id": conversation_id,
            "status": "monitoring",
            "alerts": alerts,
            "duration_seconds": duration,
            "turn_count": context.turn_count,
        }

    def get_violation_history(
        self,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """Get recent violation history"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [
            v for v in self._violation_log
            if datetime.fromisoformat(v["timestamp"]) > cutoff
        ]


# =============================================================================
# 4. VOICE SYNTHESIS CONTROL
# =============================================================================

class VoiceSynthesisController:
    """
    Voice synthesis control for natural conversation.

    Implements:
    - Sub-800ms latency targeting
    - Persona voice selection
    - Emotion/tone modulation
    - Natural conversation flow
    """

    # Latency targets in milliseconds
    TARGET_LATENCY_MS = 800
    MAX_LATENCY_MS = 1500

    # Voice configuration by persona
    VOICE_CONFIGS = {
        VoicePersona.PROFESSIONAL_MALE: {
            "voice_id": "en-US-Standard-J",
            "pitch": 0.0,
            "speaking_rate": 1.0,
            "style": "professional",
        },
        VoicePersona.PROFESSIONAL_FEMALE: {
            "voice_id": "en-US-Standard-H",
            "pitch": 0.0,
            "speaking_rate": 1.0,
            "style": "professional",
        },
        VoicePersona.EMPATHETIC_MALE: {
            "voice_id": "en-US-Standard-J",
            "pitch": -1.0,
            "speaking_rate": 0.95,
            "style": "empathetic",
        },
        VoicePersona.EMPATHETIC_FEMALE: {
            "voice_id": "en-US-Standard-H",
            "pitch": -1.0,
            "speaking_rate": 0.95,
            "style": "empathetic",
        },
        VoicePersona.FIRM_MALE: {
            "voice_id": "en-US-Standard-J",
            "pitch": 1.0,
            "speaking_rate": 1.05,
            "style": "firm",
        },
        VoicePersona.FIRM_FEMALE: {
            "voice_id": "en-US-Standard-H",
            "pitch": 1.0,
            "speaking_rate": 1.05,
            "style": "firm",
        },
    }

    # Emotion modulation parameters
    EMOTION_MODULATION = {
        EmotionTone.NEUTRAL: {"pitch_shift": 0, "rate_shift": 0, "emphasis": "none"},
        EmotionTone.EMPATHETIC: {"pitch_shift": -0.5, "rate_shift": -0.05, "emphasis": "moderate"},
        EmotionTone.URGENT: {"pitch_shift": 0.5, "rate_shift": 0.1, "emphasis": "strong"},
        EmotionTone.REASSURING: {"pitch_shift": -0.3, "rate_shift": -0.05, "emphasis": "moderate"},
        EmotionTone.FIRM: {"pitch_shift": 0.3, "rate_shift": 0, "emphasis": "strong"},
        EmotionTone.APOLOGETIC: {"pitch_shift": -0.5, "rate_shift": -0.1, "emphasis": "none"},
    }

    def __init__(self):
        self._tts_client = None
        self._latency_history: List[float] = []
        self._audio_cache: Dict[str, bytes] = {}

        logger.info("VoiceSynthesisController initialized")

    async def synthesize_speech(
        self,
        text: str,
        persona: VoicePersona,
        emotion: EmotionTone,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Synthesize speech with persona and emotion modulation.

        Returns audio data and synthesis metadata.
        """
        start_time = time.time()

        # Check cache for common phrases
        cache_key = self._get_cache_key(text, persona, emotion)
        if use_cache and cache_key in self._audio_cache:
            latency = (time.time() - start_time) * 1000
            return {
                "audio": self._audio_cache[cache_key],
                "latency_ms": latency,
                "cached": True,
                "duration_seconds": self._estimate_duration(text),
            }

        # Get voice configuration
        voice_config = self.VOICE_CONFIGS.get(
            persona, self.VOICE_CONFIGS[VoicePersona.PROFESSIONAL_FEMALE]
        )

        # Apply emotion modulation
        emotion_mod = self.EMOTION_MODULATION.get(emotion, self.EMOTION_MODULATION[EmotionTone.NEUTRAL])

        final_config = {
            "voice_id": voice_config["voice_id"],
            "pitch": voice_config["pitch"] + emotion_mod["pitch_shift"],
            "speaking_rate": voice_config["speaking_rate"] + emotion_mod["rate_shift"],
            "emphasis": emotion_mod["emphasis"],
        }

        # Synthesize (would use actual TTS service)
        audio_data = await self._call_tts_service(text, final_config)

        latency = (time.time() - start_time) * 1000
        self._latency_history.append(latency)

        # Cache common phrases
        if len(text) < 200 and use_cache:
            self._audio_cache[cache_key] = audio_data

        # Log if latency exceeds target
        if latency > self.TARGET_LATENCY_MS:
            logger.warning(f"TTS latency {latency:.0f}ms exceeds target {self.TARGET_LATENCY_MS}ms")

        return {
            "audio": audio_data,
            "latency_ms": latency,
            "cached": False,
            "duration_seconds": self._estimate_duration(text),
            "config": final_config,
        }

    async def _call_tts_service(
        self,
        text: str,
        config: Dict[str, Any],
    ) -> bytes:
        """Call TTS service (mock implementation)"""
        # Would call actual TTS service (Google Cloud TTS, Amazon Polly, etc.)
        # Simulating with delay
        await asyncio.sleep(0.1)  # Simulated API call

        # Return mock audio data
        return b"MOCK_AUDIO_DATA"

    def _get_cache_key(
        self,
        text: str,
        persona: VoicePersona,
        emotion: EmotionTone,
    ) -> str:
        """Generate cache key for audio"""
        content = f"{text}:{persona.value}:{emotion.value}"
        return hashlib.md5(content.encode()).hexdigest()

    def _estimate_duration(self, text: str) -> float:
        """Estimate audio duration in seconds"""
        # Average speaking rate is ~150 words per minute
        word_count = len(text.split())
        return word_count / 150 * 60

    async def process_speech_input(
        self,
        audio_data: bytes,
    ) -> Dict[str, Any]:
        """
        Process incoming speech (ASR + features).

        Returns:
        - Transcribed text
        - Audio features (pitch, pace, emotion)
        - Confidence score
        """
        start_time = time.time()

        # Would call actual ASR service
        # Mock implementation
        await asyncio.sleep(0.05)

        latency = (time.time() - start_time) * 1000

        return {
            "text": "Mock transcription",
            "confidence": 0.95,
            "audio_features": {
                "pitch": "normal",
                "pace": "normal",
                "stress_level": 0.3,
                "emotion": "neutral",
            },
            "latency_ms": latency,
        }

    def get_latency_stats(self) -> Dict[str, float]:
        """Get latency statistics"""
        if not self._latency_history:
            return {"avg": 0, "p95": 0, "p99": 0, "max": 0}

        sorted_latencies = sorted(self._latency_history)
        n = len(sorted_latencies)

        return {
            "avg": statistics.mean(sorted_latencies),
            "p95": sorted_latencies[int(n * 0.95)] if n > 20 else sorted_latencies[-1],
            "p99": sorted_latencies[int(n * 0.99)] if n > 100 else sorted_latencies[-1],
            "max": max(sorted_latencies),
            "under_target_pct": sum(1 for l in sorted_latencies if l < self.TARGET_LATENCY_MS) / n,
        }

    def get_natural_pause_duration(
        self,
        context: str,
    ) -> float:
        """Get natural pause duration based on context"""
        # Natural pauses for conversational flow
        if context == "question":
            return 0.3  # Short pause after question
        elif context == "statement":
            return 0.5  # Medium pause
        elif context == "important":
            return 0.8  # Longer pause for emphasis
        elif context == "waiting":
            return 2.0  # Long pause while waiting
        return 0.4


# =============================================================================
# 5. NEGOTIATION ENGINE
# =============================================================================

class NegotiationEngine:
    """
    AI-powered negotiation engine.

    Implements:
    - Settlement offer generation
    - Counter-offer evaluation
    - Micro-payment plan proposals
    - Escalation triggers
    """

    # Settlement authority levels
    SETTLEMENT_AUTHORITY = {
        "tier_1": 0.80,  # Up to 80% of balance
        "tier_2": 0.60,  # Up to 60% of balance
        "tier_3": 0.40,  # Up to 40% of balance
        "supervisor": 0.30,  # Up to 30% (requires approval)
    }

    # Payment plan configurations
    PAYMENT_PLAN_CONFIGS = {
        "micro": {
            "min_payment": 25,
            "max_months": 24,
            "interest_rate": 0.0,
        },
        "standard": {
            "min_payment": 50,
            "max_months": 12,
            "interest_rate": 0.0,
        },
        "accelerated": {
            "min_payment": 100,
            "max_months": 6,
            "interest_rate": 0.0,
        },
    }

    def __init__(self, authority_tier: str = "tier_1"):
        self.authority_tier = authority_tier
        self.max_settlement_pct = self.SETTLEMENT_AUTHORITY.get(authority_tier, 0.80)

        # Negotiation state tracking
        self._active_negotiations: Dict[str, Dict] = {}
        self._offer_history: Dict[str, List] = {}

        logger.info(f"NegotiationEngine initialized with authority: {authority_tier}")

    async def generate_initial_offer(
        self,
        context: ConversationContext,
    ) -> NegotiationOffer:
        """Generate initial settlement/payment offer"""
        profile = context.debtor_profile
        balance = Decimal(str(profile.get("balance", 500)))
        recovery_prob = profile.get("recovery_probability", 0.5)

        # Determine offer strategy
        if recovery_prob > 0.7:
            # High probability - start with higher offer
            offer_pct = 0.90
            offer_type = "pif"  # Payment in full
        elif recovery_prob > 0.5:
            # Medium probability - settlement offer
            offer_pct = 0.70
            offer_type = "settlement"
        else:
            # Low probability - aggressive settlement
            offer_pct = 0.50
            offer_type = "settlement"

        # Ensure within authority
        offer_pct = min(offer_pct, self.max_settlement_pct)
        offer_amount = balance * Decimal(str(offer_pct))

        offer = NegotiationOffer(
            offer_id=f"offer_{uuid.uuid4().hex[:8]}",
            offer_type=offer_type,
            amount=offer_amount,
            percentage_of_balance=offer_pct,
            expiration=datetime.utcnow() + timedelta(days=30),
            terms={
                "valid_days": 30,
                "payment_methods": ["card", "ach", "check"],
            },
        )

        # Track offer
        await self._track_offer(context.conversation_id, offer)

        return offer

    async def evaluate_counter_offer(
        self,
        context: ConversationContext,
        counter_amount: Decimal,
    ) -> Dict[str, Any]:
        """Evaluate a consumer's counter-offer"""
        profile = context.debtor_profile
        balance = Decimal(str(profile.get("balance", 500)))

        counter_pct = float(counter_amount / balance)
        min_acceptable = 1.0 - self.max_settlement_pct  # Minimum we can accept

        # Decision logic
        if counter_pct >= min_acceptable:
            decision = "accept"
            response_offer = counter_amount
        elif counter_pct >= min_acceptable - 0.10:
            decision = "counter"
            # Meet halfway
            our_last = context.current_offer or balance * Decimal(str(self.max_settlement_pct))
            response_offer = (counter_amount + our_last) / 2
        else:
            decision = "reject"
            response_offer = None

        return {
            "decision": decision,
            "counter_percentage": counter_pct,
            "min_acceptable": min_acceptable,
            "response_offer": float(response_offer) if response_offer else None,
            "reasoning": self._get_negotiation_reasoning(decision, counter_pct, min_acceptable),
        }

    def _get_negotiation_reasoning(
        self,
        decision: str,
        counter_pct: float,
        min_acceptable: float,
    ) -> str:
        """Get human-readable reasoning for negotiation decision"""
        if decision == "accept":
            return f"Counter-offer of {counter_pct:.0%} is within acceptable range."
        elif decision == "counter":
            return f"Counter-offer of {counter_pct:.0%} is close to acceptable ({min_acceptable:.0%}). Meeting halfway."
        else:
            return f"Counter-offer of {counter_pct:.0%} is below minimum acceptable ({min_acceptable:.0%})."

    async def generate_payment_plan(
        self,
        context: ConversationContext,
        monthly_budget: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """Generate micro-payment plan options"""
        profile = context.debtor_profile
        balance = Decimal(str(profile.get("balance", 500)))

        plans = []

        for plan_type, config in self.PAYMENT_PLAN_CONFIGS.items():
            min_payment = Decimal(str(config["min_payment"]))
            max_months = config["max_months"]

            # Calculate plan
            if monthly_budget and monthly_budget >= min_payment:
                payment = monthly_budget
            else:
                payment = min_payment

            num_payments = int((balance / payment).to_integral_value()) + 1
            num_payments = min(num_payments, max_months)

            actual_payment = balance / num_payments

            if actual_payment >= min_payment:
                plans.append({
                    "type": plan_type,
                    "monthly_payment": float(actual_payment),
                    "num_payments": num_payments,
                    "total_amount": float(balance),
                    "first_payment_due": (datetime.utcnow() + timedelta(days=14)).isoformat(),
                })

        # Sort by monthly payment (lowest first)
        plans.sort(key=lambda p: p["monthly_payment"])

        return {
            "plans": plans,
            "balance": float(balance),
            "recommended_plan": plans[0] if plans else None,
        }

    async def check_escalation_triggers(
        self,
        context: ConversationContext,
    ) -> Dict[str, Any]:
        """Check if negotiation should be escalated"""
        triggers = []
        should_escalate = False

        # Check for dispute
        if IntentType.DISPUTE in context.intents_detected:
            triggers.append("dispute_claimed")
            should_escalate = True

        # Check for cease and desist
        if context.cease_desist_requested:
            triggers.append("cease_desist_requested")
            should_escalate = True

        # Check for exceeded authority
        if context.current_offer:
            offer_pct = float(context.current_offer / Decimal(str(context.debtor_profile.get("balance", 1))))
            if offer_pct < (1 - self.max_settlement_pct):
                triggers.append("below_authority")
                should_escalate = True

        # Check for stalled negotiation
        if len(context.offers_made) >= 4:
            triggers.append("negotiation_stalled")
            should_escalate = True

        # Check for high-value account
        balance = float(context.debtor_profile.get("balance", 0))
        if balance > 1000:
            triggers.append("high_value_account")

        return {
            "should_escalate": should_escalate,
            "triggers": triggers,
            "escalation_type": "supervisor" if should_escalate else None,
        }

    async def _track_offer(
        self,
        conversation_id: str,
        offer: NegotiationOffer,
    ) -> None:
        """Track offer in negotiation history"""
        if conversation_id not in self._offer_history:
            self._offer_history[conversation_id] = []

        self._offer_history[conversation_id].append({
            "offer_id": offer.offer_id,
            "amount": float(offer.amount),
            "percentage": offer.percentage_of_balance,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def get_negotiation_summary(
        self,
        conversation_id: str,
    ) -> Dict[str, Any]:
        """Get summary of negotiation for a conversation"""
        history = self._offer_history.get(conversation_id, [])

        if not history:
            return {"status": "no_offers", "offers_count": 0}

        return {
            "status": "active",
            "offers_count": len(history),
            "first_offer": history[0],
            "last_offer": history[-1],
            "total_concession": history[0]["percentage"] - history[-1]["percentage"],
        }


# =============================================================================
# 6. AUTONOMY LEVELS (Integrated in OrchestratorLLM)
# =============================================================================

# Autonomy levels are implemented as part of the OrchestratorLLM class
# See: _generate_scripted_response, _generate_template_response, etc.


# =============================================================================
# 7. MULTI-AGENT COORDINATION
# =============================================================================

class MultiAgentCoordinator:
    """
    Coordinates multiple concurrent agent instances.

    Implements:
    - Parallel consumer engagement
    - Resource allocation (compute, channels)
    - Load balancing
    - Handoff protocols
    """

    # Resource limits
    MAX_CONCURRENT_VOICE = 100
    MAX_CONCURRENT_SMS = 1000
    MAX_CONCURRENT_EMAIL = 5000

    def __init__(self, max_agents: int = 100):
        self.max_agents = max_agents

        # Agent pool
        self._agents: Dict[str, Dict] = {}
        self._agent_states: Dict[str, AgentState] = {}

        # Resource tracking
        self._resource_usage = {
            "voice": 0,
            "sms": 0,
            "email": 0,
            "compute_units": 0,
        }

        # Queue management
        self._conversation_queue: asyncio.Queue = asyncio.Queue()
        self._priority_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()

        # Handoff tracking
        self._pending_handoffs: Dict[str, Dict] = {}

        # Load balancing
        self._agent_load: Dict[str, int] = {}

        self._lock = threading.Lock()

        logger.info(f"MultiAgentCoordinator initialized with max_agents={max_agents}")

    async def allocate_agent(
        self,
        account_id: str,
        channel: str,
        priority: int = 5,
    ) -> Optional[str]:
        """
        Allocate an agent for a new conversation.

        Returns agent_id if successful, None if no capacity.
        """
        # Check resource availability
        if not self._check_resource_availability(channel):
            logger.warning(f"No {channel} resources available")
            return None

        # Find available agent
        agent_id = await self._find_available_agent()

        if not agent_id:
            # Queue the request
            await self._priority_queue.put((priority, account_id, channel))
            logger.info(f"Queued account {account_id} with priority {priority}")
            return None

        # Allocate resources
        with self._lock:
            self._resource_usage[channel] = self._resource_usage.get(channel, 0) + 1
            self._agent_states[agent_id] = AgentState.ENGAGED
            self._agent_load[agent_id] = self._agent_load.get(agent_id, 0) + 1

            self._agents[agent_id] = {
                "account_id": account_id,
                "channel": channel,
                "start_time": datetime.utcnow().isoformat(),
            }

        return agent_id

    async def release_agent(
        self,
        agent_id: str,
    ) -> None:
        """Release an agent after conversation ends"""
        with self._lock:
            if agent_id in self._agents:
                agent_info = self._agents.pop(agent_id)
                channel = agent_info.get("channel")

                if channel:
                    self._resource_usage[channel] = max(0, self._resource_usage.get(channel, 0) - 1)

                self._agent_states[agent_id] = AgentState.IDLE
                self._agent_load[agent_id] = max(0, self._agent_load.get(agent_id, 0) - 1)

        # Process queue
        await self._process_queue()

    async def initiate_handoff(
        self,
        agent_id: str,
        target_type: str,  # "supervisor", "human", "specialist"
        reason: str,
    ) -> str:
        """Initiate handoff to another agent/human"""
        handoff_id = f"handoff_{uuid.uuid4().hex[:8]}"

        with self._lock:
            agent_info = self._agents.get(agent_id, {})

            self._pending_handoffs[handoff_id] = {
                "source_agent": agent_id,
                "target_type": target_type,
                "reason": reason,
                "account_id": agent_info.get("account_id"),
                "channel": agent_info.get("channel"),
                "initiated_at": datetime.utcnow().isoformat(),
                "status": "pending",
            }

            # Mark agent as waiting
            self._agent_states[agent_id] = AgentState.WAITING

        logger.info(f"Handoff initiated: {handoff_id} to {target_type}")
        return handoff_id

    async def complete_handoff(
        self,
        handoff_id: str,
        accepted_by: str,
    ) -> Dict[str, Any]:
        """Complete a pending handoff"""
        with self._lock:
            handoff = self._pending_handoffs.get(handoff_id)
            if not handoff:
                return {"error": "Handoff not found"}

            handoff["status"] = "completed"
            handoff["accepted_by"] = accepted_by
            handoff["completed_at"] = datetime.utcnow().isoformat()

            # Release original agent
            source_agent = handoff.get("source_agent")
            if source_agent:
                self._agent_states[source_agent] = AgentState.IDLE

        return handoff

    def _check_resource_availability(self, channel: str) -> bool:
        """Check if resources are available for channel"""
        limits = {
            "voice": self.MAX_CONCURRENT_VOICE,
            "sms": self.MAX_CONCURRENT_SMS,
            "email": self.MAX_CONCURRENT_EMAIL,
        }

        limit = limits.get(channel, 100)
        current = self._resource_usage.get(channel, 0)

        return current < limit

    async def _find_available_agent(self) -> Optional[str]:
        """Find an available agent using load balancing"""
        with self._lock:
            # Find agent with lowest load
            available = [
                (agent_id, load)
                for agent_id, load in self._agent_load.items()
                if self._agent_states.get(agent_id) == AgentState.IDLE
            ]

            if not available:
                # Create new agent if under limit
                if len(self._agents) < self.max_agents:
                    new_agent_id = f"agent_{uuid.uuid4().hex[:8]}"
                    self._agent_load[new_agent_id] = 0
                    self._agent_states[new_agent_id] = AgentState.IDLE
                    return new_agent_id
                return None

            # Return least loaded agent
            available.sort(key=lambda x: x[1])
            return available[0][0]

    async def _process_queue(self) -> None:
        """Process queued requests"""
        try:
            if not self._priority_queue.empty():
                priority, account_id, channel = await asyncio.wait_for(
                    self._priority_queue.get(),
                    timeout=0.1,
                )

                # Try to allocate again
                agent_id = await self.allocate_agent(account_id, channel, priority)
                if not agent_id:
                    # Re-queue
                    await self._priority_queue.put((priority, account_id, channel))
        except asyncio.TimeoutError:
            pass

    def get_capacity_status(self) -> Dict[str, Any]:
        """Get current capacity and load status"""
        with self._lock:
            active_agents = sum(
                1 for s in self._agent_states.values()
                if s in [AgentState.ENGAGED, AgentState.WAITING]
            )

            return {
                "total_agents": len(self._agent_states),
                "active_agents": active_agents,
                "max_agents": self.max_agents,
                "utilization": active_agents / self.max_agents if self.max_agents > 0 else 0,
                "resource_usage": self._resource_usage.copy(),
                "queue_size": self._priority_queue.qsize(),
                "pending_handoffs": len(self._pending_handoffs),
            }

    def get_agent_assignments(self) -> Dict[str, Dict]:
        """Get current agent assignments"""
        with self._lock:
            return {
                agent_id: {
                    "state": self._agent_states.get(agent_id, AgentState.IDLE).value,
                    "load": self._agent_load.get(agent_id, 0),
                    "info": self._agents.get(agent_id, {}),
                }
                for agent_id in self._agent_load
            }


# =============================================================================
# 8. LEARNING LOOP
# =============================================================================

class LearningLoop:
    """
    Continuous learning and improvement system.

    Implements:
    - Outcome tracking per strategy
    - A/B test management
    - Strategy refinement
    - Model fine-tuning triggers
    """

    # Minimum samples before learning
    MIN_SAMPLES_FOR_LEARNING = 100

    # Confidence threshold for strategy changes
    CONFIDENCE_THRESHOLD = 0.95

    def __init__(self):
        # Outcome tracking
        self._outcomes: List[LearningOutcome] = []
        self._strategy_outcomes: Dict[str, List[LearningOutcome]] = defaultdict(list)

        # A/B test management
        self._active_experiments: Dict[str, Dict] = {}
        self._experiment_results: Dict[str, Dict] = {}

        # Strategy performance
        self._strategy_performance: Dict[str, Dict] = {}

        # Fine-tuning triggers
        self._fine_tune_queue: List[Dict] = []

        self._lock = threading.Lock()

        logger.info("LearningLoop initialized")

    async def record_outcome(
        self,
        outcome: LearningOutcome,
    ) -> None:
        """Record conversation outcome for learning"""
        with self._lock:
            self._outcomes.append(outcome)
            self._strategy_outcomes[outcome.strategy_used].append(outcome)

        # Update strategy performance
        await self._update_strategy_performance(outcome)

        # Check for fine-tuning triggers
        await self._check_fine_tune_triggers()

        # Update active experiments
        await self._update_experiments(outcome)

    async def _update_strategy_performance(
        self,
        outcome: LearningOutcome,
    ) -> None:
        """Update rolling performance metrics for strategy"""
        strategy = outcome.strategy_used

        with self._lock:
            if strategy not in self._strategy_performance:
                self._strategy_performance[strategy] = {
                    "total_conversations": 0,
                    "total_collected": 0.0,
                    "total_balance": 0.0,
                    "collection_rate": 0.0,
                    "avg_turns": 0.0,
                    "success_rate": 0.0,
                    "roi": 0.0,
                }

            perf = self._strategy_performance[strategy]
            perf["total_conversations"] += 1
            perf["total_collected"] += outcome.amount_collected
            perf["total_balance"] += outcome.initial_balance

            # Update rates
            if perf["total_balance"] > 0:
                perf["collection_rate"] = perf["total_collected"] / perf["total_balance"]

            # Update averages
            outcomes = self._strategy_outcomes[strategy]
            perf["avg_turns"] = statistics.mean([o.turn_count for o in outcomes])
            perf["success_rate"] = sum(
                1 for o in outcomes if o.outcome_type in ["full_payment", "settlement", "payment_plan"]
            ) / len(outcomes)

    async def start_experiment(
        self,
        experiment_id: str,
        control_strategy: str,
        treatment_strategy: str,
        allocation_pct: float = 0.1,  # 10% to treatment
    ) -> Dict[str, Any]:
        """Start an A/B test experiment"""
        experiment = {
            "experiment_id": experiment_id,
            "control_strategy": control_strategy,
            "treatment_strategy": treatment_strategy,
            "allocation_pct": allocation_pct,
            "started_at": datetime.utcnow().isoformat(),
            "status": "active",
            "control_outcomes": [],
            "treatment_outcomes": [],
        }

        with self._lock:
            self._active_experiments[experiment_id] = experiment

        logger.info(f"Started experiment {experiment_id}: {control_strategy} vs {treatment_strategy}")
        return experiment

    async def get_experiment_assignment(
        self,
        experiment_id: str,
    ) -> str:
        """Get strategy assignment for experiment"""
        with self._lock:
            experiment = self._active_experiments.get(experiment_id)
            if not experiment or experiment["status"] != "active":
                return None

        # Random assignment
        if random.random() < experiment["allocation_pct"]:
            return experiment["treatment_strategy"]
        return experiment["control_strategy"]

    async def _update_experiments(
        self,
        outcome: LearningOutcome,
    ) -> None:
        """Update experiment results with new outcome"""
        with self._lock:
            for exp_id, experiment in self._active_experiments.items():
                if experiment["status"] != "active":
                    continue

                if outcome.strategy_used == experiment["control_strategy"]:
                    experiment["control_outcomes"].append(outcome)
                elif outcome.strategy_used == experiment["treatment_strategy"]:
                    experiment["treatment_outcomes"].append(outcome)

                # Check if experiment has enough data
                if (len(experiment["control_outcomes"]) >= self.MIN_SAMPLES_FOR_LEARNING and
                    len(experiment["treatment_outcomes"]) >= self.MIN_SAMPLES_FOR_LEARNING):
                    await self._analyze_experiment(exp_id)

    async def _analyze_experiment(
        self,
        experiment_id: str,
    ) -> Dict[str, Any]:
        """Analyze experiment results"""
        with self._lock:
            experiment = self._active_experiments.get(experiment_id)
            if not experiment:
                return {}

        control = experiment["control_outcomes"]
        treatment = experiment["treatment_outcomes"]

        # Calculate metrics
        control_rate = sum(o.collection_rate for o in control) / len(control) if control else 0
        treatment_rate = sum(o.collection_rate for o in treatment) / len(treatment) if treatment else 0

        # Simple significance test (would use proper statistical test in production)
        lift = (treatment_rate - control_rate) / control_rate if control_rate > 0 else 0

        results = {
            "experiment_id": experiment_id,
            "control_rate": control_rate,
            "treatment_rate": treatment_rate,
            "lift": lift,
            "control_n": len(control),
            "treatment_n": len(treatment),
            "significant": abs(lift) > 0.05 and len(control) >= 100,  # Simplified
        }

        with self._lock:
            self._experiment_results[experiment_id] = results

        # Auto-conclude if significant
        if results["significant"]:
            winner = experiment["treatment_strategy"] if lift > 0 else experiment["control_strategy"]
            logger.info(f"Experiment {experiment_id} concluded. Winner: {winner} (lift: {lift:.2%})")
            experiment["status"] = "concluded"
            experiment["winner"] = winner

        return results

    async def _check_fine_tune_triggers(self) -> None:
        """Check if fine-tuning should be triggered"""
        with self._lock:
            if len(self._outcomes) < self.MIN_SAMPLES_FOR_LEARNING:
                return

            recent = self._outcomes[-1000:]  # Last 1000 outcomes

        # Check for performance degradation
        early = recent[:500]
        late = recent[500:]

        early_rate = sum(o.collection_rate for o in early) / len(early) if early else 0
        late_rate = sum(o.collection_rate for o in late) / len(late) if late else 0

        if late_rate < early_rate * 0.9:  # 10% degradation
            self._fine_tune_queue.append({
                "trigger": "performance_degradation",
                "early_rate": early_rate,
                "late_rate": late_rate,
                "timestamp": datetime.utcnow().isoformat(),
            })
            logger.warning(f"Fine-tuning triggered: performance dropped from {early_rate:.2%} to {late_rate:.2%}")

    def get_strategy_rankings(self) -> List[Dict[str, Any]]:
        """Get strategies ranked by performance"""
        with self._lock:
            rankings = []
            for strategy, perf in self._strategy_performance.items():
                rankings.append({
                    "strategy": strategy,
                    **perf,
                })

            rankings.sort(key=lambda x: x["collection_rate"], reverse=True)
            return rankings

    def get_learning_summary(self) -> Dict[str, Any]:
        """Get summary of learning system state"""
        with self._lock:
            return {
                "total_outcomes": len(self._outcomes),
                "strategies_tracked": len(self._strategy_performance),
                "active_experiments": len([e for e in self._active_experiments.values() if e["status"] == "active"]),
                "concluded_experiments": len([e for e in self._active_experiments.values() if e["status"] == "concluded"]),
                "fine_tune_queue_size": len(self._fine_tune_queue),
                "strategy_rankings": self.get_strategy_rankings()[:5],
            }


# =============================================================================
# 9. COST TRACKING
# =============================================================================

class CostTracker:
    """
    Comprehensive cost tracking and ROI calculation.

    Tracks:
    - Per-conversation cost calculation
    - Token usage monitoring
    - Voice minute tracking
    - ROI per interaction
    """

    # Cost rates
    COSTS = {
        "llm_input_token": 0.00001,    # $0.01 per 1K tokens
        "llm_output_token": 0.00003,   # $0.03 per 1K tokens
        "voice_minute": 0.05,          # $0.05 per minute
        "sms": 0.01,                   # $0.01 per SMS
        "email": 0.001,                # $0.001 per email
        "api_call": 0.001,             # $0.001 per API call
    }

    def __init__(self):
        self._conversation_costs: Dict[str, CostRecord] = {}
        self._aggregate_costs: Dict[str, float] = defaultdict(float)
        self._daily_costs: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

        self._lock = threading.Lock()

        logger.info("CostTracker initialized")

    async def start_tracking(
        self,
        conversation_id: str,
    ) -> None:
        """Start cost tracking for a conversation"""
        with self._lock:
            self._conversation_costs[conversation_id] = CostRecord(
                conversation_id=conversation_id,
            )

    async def record_llm_usage(
        self,
        conversation_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Record LLM token usage"""
        cost = (
            input_tokens * self.COSTS["llm_input_token"] +
            output_tokens * self.COSTS["llm_output_token"]
        )

        with self._lock:
            if conversation_id in self._conversation_costs:
                record = self._conversation_costs[conversation_id]
                record.llm_tokens_input += input_tokens
                record.llm_tokens_output += output_tokens
                record.total_cost_usd += cost

            self._aggregate_costs["llm"] += cost
            self._daily_costs[datetime.utcnow().date().isoformat()]["llm"] += cost

        return cost

    async def record_voice_usage(
        self,
        conversation_id: str,
        seconds: float,
    ) -> float:
        """Record voice usage"""
        minutes = seconds / 60
        cost = minutes * self.COSTS["voice_minute"]

        with self._lock:
            if conversation_id in self._conversation_costs:
                record = self._conversation_costs[conversation_id]
                record.voice_seconds += seconds
                record.total_cost_usd += cost

            self._aggregate_costs["voice"] += cost
            self._daily_costs[datetime.utcnow().date().isoformat()]["voice"] += cost

        return cost

    async def record_channel_usage(
        self,
        conversation_id: str,
        channel: str,
        count: int = 1,
    ) -> float:
        """Record channel usage (SMS, email)"""
        cost = self.COSTS.get(channel, 0) * count

        with self._lock:
            if conversation_id in self._conversation_costs:
                record = self._conversation_costs[conversation_id]
                record.api_calls += count
                record.total_cost_usd += cost

            self._aggregate_costs[channel] += cost
            self._daily_costs[datetime.utcnow().date().isoformat()][channel] += cost

        return cost

    async def record_revenue(
        self,
        conversation_id: str,
        amount: float,
    ) -> None:
        """Record revenue from collection"""
        with self._lock:
            if conversation_id in self._conversation_costs:
                self._conversation_costs[conversation_id].revenue_generated += amount

            self._aggregate_costs["revenue"] += amount
            self._daily_costs[datetime.utcnow().date().isoformat()]["revenue"] += amount

    async def finalize_conversation(
        self,
        conversation_id: str,
    ) -> CostRecord:
        """Finalize and return cost record for conversation"""
        with self._lock:
            record = self._conversation_costs.get(conversation_id)
            if record:
                return record
            return CostRecord(conversation_id=conversation_id)

    def get_conversation_roi(
        self,
        conversation_id: str,
    ) -> float:
        """Get ROI for a specific conversation"""
        with self._lock:
            record = self._conversation_costs.get(conversation_id)
            if record:
                return record.roi
            return 0.0

    def get_aggregate_metrics(self) -> Dict[str, Any]:
        """Get aggregate cost metrics"""
        with self._lock:
            total_cost = sum(
                v for k, v in self._aggregate_costs.items()
                if k != "revenue"
            )
            total_revenue = self._aggregate_costs.get("revenue", 0)

            return {
                "total_cost": total_cost,
                "total_revenue": total_revenue,
                "roi": (total_revenue - total_cost) / total_cost if total_cost > 0 else 0,
                "cost_breakdown": {
                    k: v for k, v in self._aggregate_costs.items()
                    if k != "revenue"
                },
                "conversations_tracked": len(self._conversation_costs),
            }

    def get_daily_metrics(
        self,
        date: Optional[str] = None,
    ) -> Dict[str, float]:
        """Get metrics for a specific day"""
        if date is None:
            date = datetime.utcnow().date().isoformat()

        with self._lock:
            return dict(self._daily_costs.get(date, {}))

    def get_cost_per_dollar_collected(self) -> float:
        """Get cost per dollar collected"""
        metrics = self.get_aggregate_metrics()
        revenue = metrics["total_revenue"]
        cost = metrics["total_cost"]

        if revenue == 0:
            return float("inf")
        return cost / revenue


# =============================================================================
# MAIN AGENTIC CONTROLLER
# =============================================================================

class AgenticController:
    """
    Main controller integrating all agentic AI components.

    This is the primary interface for the autonomous collection system.
    """

    def __init__(
        self,
        default_autonomy: AutonomyLevel = AutonomyLevel.LEVEL_3_GUIDED,
        max_concurrent_agents: int = 100,
    ):
        self.default_autonomy = default_autonomy

        # Initialize all components
        self.orchestrator = OrchestratorLLM()
        self.rag = RAGIntegration()
        self.compliance = ComplianceMonitor()
        self.voice = VoiceSynthesisController()
        self.negotiation = NegotiationEngine()
        self.coordinator = MultiAgentCoordinator(max_agents=max_concurrent_agents)
        self.learning = LearningLoop()
        self.cost_tracker = CostTracker()

        # Active sessions
        self._sessions: Dict[str, Dict] = {}

        logger.info("AgenticController initialized")

    async def start_session(
        self,
        account_id: str,
        channel: str = "voice",
        autonomy_level: Optional[AutonomyLevel] = None,
    ) -> Dict[str, Any]:
        """
        Start an autonomous collection session.

        This is the main entry point for initiating contact with a consumer.
        """
        autonomy = autonomy_level or self.default_autonomy

        # Get debtor profile from RAG
        profile = await self.rag.get_debtor_profile(account_id)

        # Get compliance rules for consumer's state
        state = profile.get("state", "")
        compliance_rules = await self.rag.get_compliance_rules(state)

        # Allocate agent
        agent_id = await self.coordinator.allocate_agent(account_id, channel)
        if not agent_id:
            return {
                "status": "queued",
                "message": "All agents busy, request queued",
            }

        # Start conversation
        context = await self.orchestrator.start_conversation(
            account_id=account_id,
            debtor_profile=profile,
            channel=channel,
            autonomy_level=autonomy,
        )

        # Start cost tracking
        await self.cost_tracker.start_tracking(context.conversation_id)

        # Store session
        self._sessions[context.conversation_id] = {
            "agent_id": agent_id,
            "account_id": account_id,
            "context": context,
            "compliance_rules": compliance_rules,
            "started_at": datetime.utcnow().isoformat(),
        }

        # Generate opening message
        opening_response, _ = await self.process_turn(
            context.conversation_id,
            "",  # No consumer input for opening
        )

        return {
            "status": "started",
            "conversation_id": context.conversation_id,
            "agent_id": agent_id,
            "autonomy_level": autonomy.value,
            "opening_message": opening_response.text,
            "voice_config": {
                "persona": context.voice_persona.value,
                "tone": context.current_tone.value,
            },
        }

    async def process_turn(
        self,
        conversation_id: str,
        consumer_input: str,
        audio_features: Optional[Dict] = None,
    ) -> Tuple[AgentResponse, ConversationState]:
        """
        Process a conversation turn with full compliance checking.
        """
        start_time = time.time()

        session = self._sessions.get(conversation_id)
        if not session:
            raise ValueError(f"Unknown session: {conversation_id}")

        # Process through orchestrator
        response, context = await self.orchestrator.process_turn(
            conversation_id,
            consumer_input,
            audio_features,
        )

        # Compliance check
        compliance_result = await self.compliance.check_response(
            response.text,
            context,
        )

        # Handle compliance issues
        if not compliance_result.is_compliant:
            if compliance_result.kill_switch_triggered:
                # Emergency escalation
                await self._emergency_escalation(conversation_id, compliance_result)
                response.requires_human = True
                response.text = "I need to transfer you to a supervisor. Please hold."
            elif compliance_result.modified_text:
                response.text = compliance_result.modified_text

        response.compliance_checked = True

        # Track mini-miranda delivery
        if not context.mini_miranda_delivered:
            for pattern in MINI_MIRANDA_PATTERNS:
                if re.search(pattern, response.text, re.IGNORECASE):
                    context.mini_miranda_delivered = True
                    break

        # Record costs
        await self.cost_tracker.record_llm_usage(
            conversation_id,
            len(consumer_input.split()) * 1.5,  # Rough token estimate
            response.cost_tokens,
        )

        # Monitor conversation
        monitoring = await self.compliance.monitor_conversation(conversation_id, context)
        if monitoring.get("alerts"):
            response.metadata["compliance_alerts"] = monitoring["alerts"]

        # Calculate latency
        response.latency_ms = (time.time() - start_time) * 1000

        # Update session
        session["context"] = context

        return response, ConversationState.from_context(context)

    async def generate_offer(
        self,
        conversation_id: str,
    ) -> Dict[str, Any]:
        """Generate a negotiation offer"""
        session = self._sessions.get(conversation_id)
        if not session:
            raise ValueError(f"Unknown session: {conversation_id}")

        context = session["context"]

        # Generate offer through negotiation engine
        offer = await self.negotiation.generate_initial_offer(context)

        # Update context
        context.current_offer = offer.amount
        context.offers_made.append({
            "offer_id": offer.offer_id,
            "amount": float(offer.amount),
            "timestamp": datetime.utcnow().isoformat(),
        })

        return {
            "offer_id": offer.offer_id,
            "type": offer.offer_type,
            "amount": float(offer.amount),
            "percentage": offer.percentage_of_balance,
            "expires": offer.expiration.isoformat(),
            "script": f"I can offer you a settlement of ${offer.amount:.2f}, which is "
                     f"{offer.percentage_of_balance*100:.0f}% of your balance. This offer "
                     f"is valid for {(offer.expiration - datetime.utcnow()).days} days.",
        }

    async def generate_payment_plan(
        self,
        conversation_id: str,
        monthly_budget: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Generate payment plan options"""
        session = self._sessions.get(conversation_id)
        if not session:
            raise ValueError(f"Unknown session: {conversation_id}")

        context = session["context"]
        budget = Decimal(str(monthly_budget)) if monthly_budget else None

        return await self.negotiation.generate_payment_plan(context, budget)

    async def synthesize_voice(
        self,
        conversation_id: str,
        text: str,
    ) -> Dict[str, Any]:
        """Synthesize voice response"""
        session = self._sessions.get(conversation_id)
        if not session:
            raise ValueError(f"Unknown session: {conversation_id}")

        context = session["context"]

        result = await self.voice.synthesize_speech(
            text,
            context.voice_persona,
            context.current_tone,
        )

        # Track voice costs
        if result.get("duration_seconds"):
            await self.cost_tracker.record_voice_usage(
                conversation_id,
                result["duration_seconds"],
            )

        return result

    async def end_session(
        self,
        conversation_id: str,
        outcome: str,
        amount_collected: float = 0.0,
    ) -> Dict[str, Any]:
        """End a collection session and record outcomes"""
        session = self._sessions.pop(conversation_id, None)
        if not session:
            return {"error": "Session not found"}

        context = session["context"]
        agent_id = session["agent_id"]

        # Record revenue
        if amount_collected > 0:
            await self.cost_tracker.record_revenue(conversation_id, amount_collected)

        # Get final costs
        cost_record = await self.cost_tracker.finalize_conversation(conversation_id)

        # End orchestrator conversation
        summary = await self.orchestrator.end_conversation(conversation_id, outcome)

        # Release agent
        await self.coordinator.release_agent(agent_id)

        # Store interaction in RAG
        await self.rag.store_interaction(
            context.account_id,
            {
                "conversation_id": conversation_id,
                "outcome": outcome,
                "amount_collected": amount_collected,
                "turn_count": context.turn_count,
                "duration_seconds": summary.get("duration_seconds", 0),
            },
        )

        # Record learning outcome
        learning_outcome = LearningOutcome(
            conversation_id=conversation_id,
            strategy_used=context.active_strategy or "default",
            autonomy_level=context.autonomy_level.value,
            initial_balance=float(context.debtor_profile.get("balance", 0)),
            amount_collected=amount_collected,
            collection_rate=amount_collected / float(context.debtor_profile.get("balance", 1)),
            turn_count=context.turn_count,
            duration_seconds=summary.get("duration_seconds", 0),
            outcome_type=outcome,
            consumer_sentiment="neutral",  # Would analyze from conversation
            cost=cost_record.total_cost_usd,
        )
        await self.learning.record_outcome(learning_outcome)

        return {
            "conversation_id": conversation_id,
            "outcome": outcome,
            "amount_collected": amount_collected,
            "cost": cost_record.total_cost_usd,
            "roi": cost_record.roi,
            **summary,
        }

    async def _emergency_escalation(
        self,
        conversation_id: str,
        compliance_result: ComplianceResult,
    ) -> None:
        """Handle emergency escalation due to compliance issues"""
        session = self._sessions.get(conversation_id)
        if not session:
            return

        agent_id = session["agent_id"]

        # Initiate handoff
        handoff_id = await self.coordinator.initiate_handoff(
            agent_id,
            "supervisor",
            f"Compliance violation: {compliance_result.violations}",
        )

        logger.critical(f"Emergency escalation for {conversation_id}: {handoff_id}")

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            "active_sessions": len(self._sessions),
            "capacity": self.coordinator.get_capacity_status(),
            "voice_latency": self.voice.get_latency_stats(),
            "learning": self.learning.get_learning_summary(),
            "costs": self.cost_tracker.get_aggregate_metrics(),
            "compliance_violations_24h": len(self.compliance.get_violation_history(24)),
        }


# =============================================================================
# DEMONSTRATION
# =============================================================================

async def demo_agentic_controller():
    """Demonstrate the agentic AI controller capabilities"""

    print("\n" + "=" * 80)
    print("  QUAN AGENTIC AI CONTROLLER DEMONSTRATION")
    print("  Autonomous Debt Collection with Compliance Guardrails")
    print("=" * 80)

    # Initialize controller
    controller = AgenticController(
        default_autonomy=AutonomyLevel.LEVEL_3_GUIDED,
        max_concurrent_agents=10,
    )

    # Mock debtor profile
    mock_profile = {
        "account_id": "DEMO-001",
        "name": "John Smith",
        "balance": 450.00,
        "original_creditor": "Example Credit",
        "state": "CA",
        "phone": "+15551234567",
        "email": "john.smith@example.com",
        "recovery_probability": 0.65,
        "days_past_due": 45,
        "payment_history": [],
        "is_digital_native": True,
    }

    # Store mock profile in RAG
    controller.rag._debtor_store["DEMO-001"] = mock_profile

    print("\n" + "-" * 80)
    print("  1. STARTING COLLECTION SESSION")
    print("-" * 80)

    # Start session
    session = await controller.start_session(
        account_id="DEMO-001",
        channel="voice",
        autonomy_level=AutonomyLevel.LEVEL_3_GUIDED,
    )

    print(f"\n  Session Status: {session['status']}")
    print(f"  Conversation ID: {session['conversation_id']}")
    print(f"  Agent ID: {session['agent_id']}")
    print(f"  Autonomy Level: {session['autonomy_level']}")
    print(f"\n  Opening Message:")
    print(f"  '{session['opening_message']}'")

    conversation_id = session['conversation_id']

    print("\n" + "-" * 80)
    print("  2. SIMULATING CONVERSATION TURNS")
    print("-" * 80)

    # Simulated conversation
    conversation_turns = [
        "Yes, this is John.",
        "What's this about?",
        "I don't have that kind of money right now. Can you do something about the amount?",
        "What's the lowest you can go?",
        "Can I pay that in two payments?",
        "Okay, let me think about it.",
    ]

    for i, consumer_input in enumerate(conversation_turns, 1):
        print(f"\n  Turn {i}:")
        print(f"    Consumer: '{consumer_input}'")

        response, state = await controller.process_turn(
            conversation_id,
            consumer_input,
        )

        print(f"    Agent ({state.phase}): '{response.text}'")
        print(f"    Intent: {response.intent}, Confidence: {response.confidence:.2f}")
        print(f"    Latency: {response.latency_ms:.1f}ms, Compliance: {'OK' if response.compliance_checked else 'CHECK'}")

        # Generate offer when in negotiation
        if state.phase == "negotiation" and not state.current_offer:
            offer = await controller.generate_offer(conversation_id)
            print(f"\n    [OFFER GENERATED]")
            print(f"    Type: {offer['type']}, Amount: ${offer['amount']:.2f} ({offer['percentage']*100:.0f}%)")

        await asyncio.sleep(0.1)  # Simulate real-time

    print("\n" + "-" * 80)
    print("  3. COMPLIANCE TESTING")
    print("-" * 80)

    # Test compliance with problematic input
    print("\n  Testing compliance monitor with violation...")

    test_context = controller.orchestrator.get_conversation(conversation_id)
    test_text = "If you don't pay, we'll have you arrested and garnish your wages tomorrow."

    compliance_result = await controller.compliance.check_response(test_text, test_context)

    print(f"\n  Original text: '{test_text}'")
    print(f"  Compliant: {compliance_result.is_compliant}")
    print(f"  Violations found: {len(compliance_result.violations)}")
    for v in compliance_result.violations:
        print(f"    - {v['type']}: {v['description']}")
    if compliance_result.modified_text:
        print(f"  Modified text: '{compliance_result.modified_text}'")

    print("\n" + "-" * 80)
    print("  4. VOICE SYNTHESIS")
    print("-" * 80)

    # Test voice synthesis
    voice_result = await controller.synthesize_voice(
        conversation_id,
        "I understand this is a difficult situation. Let me see what options we have."
    )

    print(f"\n  Voice synthesis latency: {voice_result['latency_ms']:.1f}ms")
    print(f"  Estimated duration: {voice_result['duration_seconds']:.1f}s")
    print(f"  Cached: {voice_result.get('cached', False)}")
    print(f"  Target latency (<800ms): {'MET' if voice_result['latency_ms'] < 800 else 'EXCEEDED'}")

    print("\n" + "-" * 80)
    print("  5. PAYMENT PLAN GENERATION")
    print("-" * 80)

    # Generate payment plans
    plans = await controller.generate_payment_plan(conversation_id, monthly_budget=75)

    print(f"\n  Available payment plans for ${plans['balance']:.2f} balance:")
    for plan in plans['plans']:
        print(f"    - {plan['type'].upper()}: ${plan['monthly_payment']:.2f}/mo x {plan['num_payments']} months")

    print("\n" + "-" * 80)
    print("  6. ENDING SESSION")
    print("-" * 80)

    # End session with outcome
    result = await controller.end_session(
        conversation_id,
        outcome="settlement",
        amount_collected=270.00,
    )

    print(f"\n  Outcome: {result['outcome']}")
    print(f"  Amount Collected: ${result['amount_collected']:.2f}")
    print(f"  Total Cost: ${result['cost']:.4f}")
    print(f"  ROI: {result['roi']:.1%}")
    print(f"  Duration: {result['duration_seconds']:.1f}s")
    print(f"  Total Turns: {result['turn_count']}")

    print("\n" + "-" * 80)
    print("  7. SYSTEM STATUS")
    print("-" * 80)

    status = controller.get_system_status()

    print(f"\n  Active Sessions: {status['active_sessions']}")
    print(f"  Agent Utilization: {status['capacity']['utilization']:.1%}")
    print(f"  Voice Latency (avg): {status['voice_latency']['avg']:.1f}ms")
    print(f"  Total Revenue: ${status['costs']['total_revenue']:.2f}")
    print(f"  Overall ROI: {status['costs']['roi']:.1%}")
    print(f"  Compliance Violations (24h): {status['compliance_violations_24h']}")

    print("\n" + "-" * 80)
    print("  8. AUTONOMY LEVELS DEMONSTRATION")
    print("-" * 80)

    print("\n  Available Autonomy Levels:")
    for level in AutonomyLevel:
        print(f"    Level {level.value}: {level.name.replace('LEVEL_', '').replace('_', ' ').title()}")

    print("\n  Autonomy Level Descriptions:")
    print("    L1 SCRIPTED: Pre-approved scripts only, zero deviation")
    print("    L2 TEMPLATE: Fill-in-blank personalization within templates")
    print("    L3 GUIDED:   Natural conversation within compliance guardrails")
    print("    L4 AUTONOMOUS: Full freedom with real-time monitoring")
    print("    L5 SELF-IMPROVING: Experiments with new strategies, proposes improvements")

    print("\n" + "=" * 80)
    print("  DEMONSTRATION COMPLETE")
    print("=" * 80 + "\n")

    return controller


if __name__ == "__main__":
    asyncio.run(demo_agentic_controller())
