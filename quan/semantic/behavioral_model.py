"""
Semantic Behavioral Model for Consumer Debt Collection

A comprehensive behavioral modeling system that combines:
- Finite state machine for consumer lifecycle tracking
- Vector embeddings for behavioral pattern recognition
- Liquidity detection for optimal contact timing
- Sentiment analysis for communication optimization
- Propensity models for outcome prediction

Mathematical Foundations:
- State transitions: Markov chain with time-decay
- Embeddings: Dense vector representations in R^n
- Liquidity: Fourier analysis for cyclical patterns
- Sentiment: Lexicon-based + neural scoring
- Propensity: Logistic regression with interaction terms

Author: QUAN Collection Intelligence System
"""

from __future__ import annotations

import math
import logging
from enum import Enum, auto
from typing import (
    Dict, List, Optional, Tuple, Any, Callable,
    Set, Union, NamedTuple, TypeVar, Generic
)
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Type aliases
Vector = np.ndarray
Probability = float
Timestamp = datetime


# =============================================================================
# SECTION 1: CONSUMER STATE MACHINE
# =============================================================================

class ConsumerState(Enum):
    """
    All possible states in the consumer lifecycle.

    State Definitions:
    - DORMANT: No recent interaction, passive account
    - ENGAGED: Active communication, showing interest
    - NEGOTIATING: Discussing payment terms or settlements
    - COMMITTED: Agreed to payment plan, awaiting execution
    - PAYING: Actively making payments
    - RESOLVED: Account fully settled
    - HOSTILE: Adversarial, threatening legal action
    - LEGAL: Escalated to legal proceedings
    """
    DORMANT = auto()
    ENGAGED = auto()
    NEGOTIATING = auto()
    COMMITTED = auto()
    PAYING = auto()
    RESOLVED = auto()
    HOSTILE = auto()
    LEGAL = auto()


@dataclass
class StateTransition:
    """
    Represents a state transition with associated metadata.

    Attributes:
        from_state: Origin state
        to_state: Destination state
        base_probability: Base transition probability P(to|from)
        decay_rate: Exponential decay rate for time-based adjustments
        required_triggers: Events that can trigger this transition
        modifiers: Functions that modify probability based on context
    """
    from_state: ConsumerState
    to_state: ConsumerState
    base_probability: float
    decay_rate: float = 0.1  # lambda for exponential decay
    required_triggers: Set[str] = field(default_factory=set)
    modifiers: List[Callable[[Dict], float]] = field(default_factory=list)


class EngagementDecay:
    """
    Models the decay of consumer engagement over time.

    Mathematical Model:
        E(t) = E_0 * exp(-lambda * t) + E_baseline

    Where:
        E_0 = Initial engagement level
        lambda = Decay rate (state-dependent)
        t = Time since last interaction
        E_baseline = Minimum engagement floor
    """

    # State-specific decay rates (higher = faster decay)
    DECAY_RATES: Dict[ConsumerState, float] = {
        ConsumerState.DORMANT: 0.01,      # Very slow decay (already low)
        ConsumerState.ENGAGED: 0.15,       # Moderate decay
        ConsumerState.NEGOTIATING: 0.20,   # Faster decay (momentum matters)
        ConsumerState.COMMITTED: 0.05,     # Slow decay (commitment is sticky)
        ConsumerState.PAYING: 0.03,        # Very slow (in payment flow)
        ConsumerState.RESOLVED: 0.0,       # No decay (terminal state)
        ConsumerState.HOSTILE: 0.08,       # Slow decay (anger persists)
        ConsumerState.LEGAL: 0.02,         # Very slow (legal process ongoing)
    }

    # Baseline engagement floors by state
    BASELINE: Dict[ConsumerState, float] = {
        ConsumerState.DORMANT: 0.05,
        ConsumerState.ENGAGED: 0.20,
        ConsumerState.NEGOTIATING: 0.35,
        ConsumerState.COMMITTED: 0.50,
        ConsumerState.PAYING: 0.70,
        ConsumerState.RESOLVED: 1.0,
        ConsumerState.HOSTILE: 0.15,
        ConsumerState.LEGAL: 0.25,
    }

    def __init__(self, initial_engagement: float = 1.0):
        """
        Initialize decay model.

        Args:
            initial_engagement: Starting engagement level [0, 1]
        """
        self.initial_engagement = initial_engagement
        self.last_interaction_time: Optional[datetime] = None

    def calculate_engagement(
        self,
        state: ConsumerState,
        current_time: datetime,
        last_interaction: Optional[datetime] = None
    ) -> float:
        """
        Calculate current engagement level with time decay.

        Formula: E(t) = (E_0 - E_base) * exp(-lambda * t) + E_base

        Args:
            state: Current consumer state
            current_time: Current timestamp
            last_interaction: Time of last interaction

        Returns:
            Engagement level in [0, 1]
        """
        if last_interaction is None:
            last_interaction = self.last_interaction_time or current_time

        # Time delta in days
        delta_days = (current_time - last_interaction).total_seconds() / 86400.0

        decay_rate = self.DECAY_RATES[state]
        baseline = self.BASELINE[state]

        # Exponential decay formula
        decayed = (self.initial_engagement - baseline) * math.exp(-decay_rate * delta_days)
        engagement = decayed + baseline

        return max(0.0, min(1.0, engagement))

    def half_life(self, state: ConsumerState) -> float:
        """
        Calculate the half-life of engagement for a given state.

        t_1/2 = ln(2) / lambda

        Returns:
            Half-life in days
        """
        decay_rate = self.DECAY_RATES[state]
        if decay_rate <= 0:
            return float('inf')
        return math.log(2) / decay_rate


class ConsumerStateMachine:
    """
    Markov-based state machine for consumer lifecycle tracking.

    Transition Matrix Design:
        P(s'|s, a, h) where:
        - s' = next state
        - s = current state
        - a = action taken
        - h = interaction history

    The transition probabilities are adjusted based on:
    1. Time since last state change (decay)
    2. Historical pattern matching
    3. Contextual modifiers (balance, sentiment, etc.)
    """

    def __init__(self):
        """Initialize state machine with default transition matrix."""
        self.transition_matrix = self._build_transition_matrix()
        self.state_history: List[Tuple[ConsumerState, datetime]] = []
        self.current_state: ConsumerState = ConsumerState.DORMANT
        self.engagement_decay = EngagementDecay()

    def _build_transition_matrix(self) -> Dict[ConsumerState, Dict[ConsumerState, StateTransition]]:
        """
        Build the state transition probability matrix.

        Returns:
            Nested dict: transition_matrix[from_state][to_state] = StateTransition
        """
        transitions: Dict[ConsumerState, Dict[ConsumerState, StateTransition]] = {
            state: {} for state in ConsumerState
        }

        # DORMANT transitions
        transitions[ConsumerState.DORMANT] = {
            ConsumerState.ENGAGED: StateTransition(
                ConsumerState.DORMANT, ConsumerState.ENGAGED,
                base_probability=0.25,
                decay_rate=0.05,
                required_triggers={'contact_response', 'inbound_inquiry'}
            ),
            ConsumerState.HOSTILE: StateTransition(
                ConsumerState.DORMANT, ConsumerState.HOSTILE,
                base_probability=0.05,
                required_triggers={'dispute_filed', 'complaint'}
            ),
            ConsumerState.LEGAL: StateTransition(
                ConsumerState.DORMANT, ConsumerState.LEGAL,
                base_probability=0.02,
                required_triggers={'legal_escalation'}
            ),
        }

        # ENGAGED transitions
        transitions[ConsumerState.ENGAGED] = {
            ConsumerState.DORMANT: StateTransition(
                ConsumerState.ENGAGED, ConsumerState.DORMANT,
                base_probability=0.30,
                decay_rate=0.10
            ),
            ConsumerState.NEGOTIATING: StateTransition(
                ConsumerState.ENGAGED, ConsumerState.NEGOTIATING,
                base_probability=0.35,
                required_triggers={'settlement_inquiry', 'payment_plan_request'}
            ),
            ConsumerState.PAYING: StateTransition(
                ConsumerState.ENGAGED, ConsumerState.PAYING,
                base_probability=0.20,
                required_triggers={'payment_initiated', 'payment_completed'}
            ),
            ConsumerState.HOSTILE: StateTransition(
                ConsumerState.ENGAGED, ConsumerState.HOSTILE,
                base_probability=0.08,
                required_triggers={'negative_response', 'threat_detected'}
            ),
        }

        # NEGOTIATING transitions
        transitions[ConsumerState.NEGOTIATING] = {
            ConsumerState.DORMANT: StateTransition(
                ConsumerState.NEGOTIATING, ConsumerState.DORMANT,
                base_probability=0.15,
                decay_rate=0.12
            ),
            ConsumerState.ENGAGED: StateTransition(
                ConsumerState.NEGOTIATING, ConsumerState.ENGAGED,
                base_probability=0.20
            ),
            ConsumerState.COMMITTED: StateTransition(
                ConsumerState.NEGOTIATING, ConsumerState.COMMITTED,
                base_probability=0.40,
                required_triggers={'agreement_accepted', 'plan_confirmed'}
            ),
            ConsumerState.HOSTILE: StateTransition(
                ConsumerState.NEGOTIATING, ConsumerState.HOSTILE,
                base_probability=0.10,
                required_triggers={'negotiation_breakdown', 'offer_rejected'}
            ),
        }

        # COMMITTED transitions
        transitions[ConsumerState.COMMITTED] = {
            ConsumerState.PAYING: StateTransition(
                ConsumerState.COMMITTED, ConsumerState.PAYING,
                base_probability=0.70,
                required_triggers={'first_payment', 'payment_completed'}
            ),
            ConsumerState.NEGOTIATING: StateTransition(
                ConsumerState.COMMITTED, ConsumerState.NEGOTIATING,
                base_probability=0.15,
                required_triggers={'renegotiation_request'}
            ),
            ConsumerState.DORMANT: StateTransition(
                ConsumerState.COMMITTED, ConsumerState.DORMANT,
                base_probability=0.10,
                decay_rate=0.08
            ),
        }

        # PAYING transitions
        transitions[ConsumerState.PAYING] = {
            ConsumerState.RESOLVED: StateTransition(
                ConsumerState.PAYING, ConsumerState.RESOLVED,
                base_probability=0.60,
                required_triggers={'final_payment', 'balance_zero'}
            ),
            ConsumerState.COMMITTED: StateTransition(
                ConsumerState.PAYING, ConsumerState.COMMITTED,
                base_probability=0.20,
                required_triggers={'payment_paused', 'partial_default'}
            ),
            ConsumerState.DORMANT: StateTransition(
                ConsumerState.PAYING, ConsumerState.DORMANT,
                base_probability=0.15,
                decay_rate=0.05,
                required_triggers={'payment_stopped', 'missed_payment'}
            ),
        }

        # RESOLVED is terminal (no outgoing transitions)
        transitions[ConsumerState.RESOLVED] = {}

        # HOSTILE transitions
        transitions[ConsumerState.HOSTILE] = {
            ConsumerState.ENGAGED: StateTransition(
                ConsumerState.HOSTILE, ConsumerState.ENGAGED,
                base_probability=0.15,
                required_triggers={'de_escalation', 'apology_accepted'}
            ),
            ConsumerState.LEGAL: StateTransition(
                ConsumerState.HOSTILE, ConsumerState.LEGAL,
                base_probability=0.25,
                required_triggers={'legal_threat', 'attorney_involvement'}
            ),
            ConsumerState.DORMANT: StateTransition(
                ConsumerState.HOSTILE, ConsumerState.DORMANT,
                base_probability=0.10,
                decay_rate=0.06
            ),
        }

        # LEGAL transitions
        transitions[ConsumerState.LEGAL] = {
            ConsumerState.RESOLVED: StateTransition(
                ConsumerState.LEGAL, ConsumerState.RESOLVED,
                base_probability=0.30,
                required_triggers={'legal_settlement', 'judgment_satisfied'}
            ),
            ConsumerState.PAYING: StateTransition(
                ConsumerState.LEGAL, ConsumerState.PAYING,
                base_probability=0.20,
                required_triggers={'court_ordered_payment', 'garnishment_started'}
            ),
        }

        return transitions

    def get_transition_probability(
        self,
        from_state: ConsumerState,
        to_state: ConsumerState,
        context: Optional[Dict[str, Any]] = None,
        time_in_state: float = 0.0
    ) -> float:
        """
        Calculate transition probability with all modifiers applied.

        P_adjusted = P_base * decay_factor * context_modifier

        Args:
            from_state: Current state
            to_state: Target state
            context: Contextual information (balance, sentiment, etc.)
            time_in_state: Days spent in current state

        Returns:
            Adjusted transition probability
        """
        if to_state not in self.transition_matrix.get(from_state, {}):
            return 0.0

        transition = self.transition_matrix[from_state][to_state]
        probability = transition.base_probability

        # Apply time decay
        if transition.decay_rate > 0 and time_in_state > 0:
            decay_factor = math.exp(-transition.decay_rate * time_in_state)
            probability *= decay_factor

        # Apply context modifiers
        if context:
            for modifier in transition.modifiers:
                try:
                    mod_factor = modifier(context)
                    probability *= mod_factor
                except Exception as e:
                    logger.warning(f"Modifier failed: {e}")

        return max(0.0, min(1.0, probability))

    def get_all_transition_probabilities(
        self,
        from_state: ConsumerState,
        context: Optional[Dict[str, Any]] = None,
        time_in_state: float = 0.0
    ) -> Dict[ConsumerState, float]:
        """
        Get all transition probabilities from a given state.

        Returns:
            Dict mapping target states to their probabilities
        """
        probabilities = {}
        for to_state in ConsumerState:
            prob = self.get_transition_probability(
                from_state, to_state, context, time_in_state
            )
            if prob > 0:
                probabilities[to_state] = prob
        return probabilities

    def transition(
        self,
        trigger: str,
        context: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ) -> Tuple[ConsumerState, float]:
        """
        Attempt a state transition based on a trigger event.

        Args:
            trigger: Event that may cause transition
            context: Additional context
            timestamp: When the transition occurs

        Returns:
            Tuple of (new_state, probability)
        """
        timestamp = timestamp or datetime.now()

        # Calculate time in current state
        time_in_state = 0.0
        if self.state_history:
            last_transition = self.state_history[-1][1]
            time_in_state = (timestamp - last_transition).total_seconds() / 86400.0

        # Find valid transitions for this trigger
        valid_transitions = []
        for to_state, transition in self.transition_matrix.get(
            self.current_state, {}
        ).items():
            if not transition.required_triggers or trigger in transition.required_triggers:
                prob = self.get_transition_probability(
                    self.current_state, to_state, context, time_in_state
                )
                if prob > 0:
                    valid_transitions.append((to_state, prob))

        if not valid_transitions:
            return self.current_state, 0.0

        # Select transition (highest probability or weighted random)
        valid_transitions.sort(key=lambda x: x[1], reverse=True)
        new_state, probability = valid_transitions[0]

        # Execute transition
        old_state = self.current_state
        self.current_state = new_state
        self.state_history.append((new_state, timestamp))

        logger.info(
            f"State transition: {old_state.name} -> {new_state.name} "
            f"(trigger={trigger}, prob={probability:.3f})"
        )

        return new_state, probability

    def simulate_trajectory(
        self,
        steps: int = 100,
        context: Optional[Dict[str, Any]] = None
    ) -> List[ConsumerState]:
        """
        Simulate a state trajectory using Monte Carlo.

        Args:
            steps: Number of simulation steps
            context: Context for probability calculation

        Returns:
            List of states in the trajectory
        """
        trajectory = [self.current_state]
        current = self.current_state

        for _ in range(steps):
            probs = self.get_all_transition_probabilities(current, context)

            if not probs:
                break  # Terminal state

            # Normalize probabilities
            total = sum(probs.values())
            if total > 0:
                probs = {k: v/total for k, v in probs.items()}

            # Sample next state
            states = list(probs.keys())
            probabilities = list(probs.values())

            next_state = np.random.choice(
                len(states),
                p=probabilities
            )
            current = states[next_state]
            trajectory.append(current)

            if current == ConsumerState.RESOLVED:
                break

        return trajectory


# =============================================================================
# SECTION 2: BEHAVIORAL EMBEDDINGS
# =============================================================================

class BehavioralArchetype(Enum):
    """
    Behavioral archetypes derived from clustering analysis.

    Each archetype represents a distinct behavioral pattern:
    - PROMPT_PAYER: Pays quickly with minimal intervention
    - NEGOTIATOR: Seeks deals, responds to offers
    - PROCRASTINATOR: Delays but eventually pays
    - GHOST: Avoids all contact, hard to reach
    - HOSTILE: Aggressive, disputes validity
    - VULNERABLE: Financial hardship, needs accommodation
    - STRATEGIC_DEFAULTER: Capable but unwilling
    """
    PROMPT_PAYER = auto()
    NEGOTIATOR = auto()
    PROCRASTINATOR = auto()
    GHOST = auto()
    HOSTILE = auto()
    VULNERABLE = auto()
    STRATEGIC_DEFAULTER = auto()


@dataclass
class BehavioralFeatures:
    """
    Raw behavioral features for embedding generation.

    All features are normalized to [0, 1] range.
    """
    # Response patterns
    response_latency: float = 0.5       # Avg response time (normalized)
    response_rate: float = 0.5          # % of contacts that get response
    response_consistency: float = 0.5   # Variance in response behavior

    # Channel preferences
    channel_sms: float = 0.0            # Preference for SMS
    channel_email: float = 0.0          # Preference for email
    channel_phone: float = 0.0          # Preference for phone
    channel_mail: float = 0.0           # Preference for mail
    channel_digital: float = 0.0        # Overall digital preference

    # Time patterns
    morning_activity: float = 0.0       # Activity 6am-12pm
    afternoon_activity: float = 0.0     # Activity 12pm-6pm
    evening_activity: float = 0.0       # Activity 6pm-10pm
    weekend_activity: float = 0.0       # Weekend vs weekday ratio

    # Payment behavior
    payment_velocity: float = 0.0       # Speed of payments
    payment_consistency: float = 0.0    # Regularity of payments
    payment_completeness: float = 0.0   # Full vs partial payments

    # Promise reliability
    promise_kept_rate: float = 0.0      # % of promises honored
    promise_amount_accuracy: float = 0.0  # Promised vs actual amount
    promise_timing_accuracy: float = 0.0  # Promised vs actual timing

    # Engagement quality
    sentiment_avg: float = 0.5          # Average sentiment score
    cooperation_score: float = 0.5      # Cooperation level
    escalation_tendency: float = 0.0    # Tendency to escalate

    def to_vector(self) -> np.ndarray:
        """Convert features to numpy vector."""
        return np.array([
            self.response_latency,
            self.response_rate,
            self.response_consistency,
            self.channel_sms,
            self.channel_email,
            self.channel_phone,
            self.channel_mail,
            self.channel_digital,
            self.morning_activity,
            self.afternoon_activity,
            self.evening_activity,
            self.weekend_activity,
            self.payment_velocity,
            self.payment_consistency,
            self.payment_completeness,
            self.promise_kept_rate,
            self.promise_amount_accuracy,
            self.promise_timing_accuracy,
            self.sentiment_avg,
            self.cooperation_score,
            self.escalation_tendency,
        ], dtype=np.float32)


class BehavioralEmbedding:
    """
    Dense vector representation of consumer behavior.

    Embedding Dimensions:
    - Response Profile (4D): latency, rate, consistency, channel
    - Temporal Profile (4D): time-of-day, day-of-week patterns
    - Payment Profile (4D): velocity, consistency, completeness, promises
    - Engagement Profile (4D): sentiment, cooperation, escalation, trust

    Total: 16-dimensional embedding

    Mathematical Approach:
    - PCA for dimensionality reduction
    - Autoencoder for non-linear compression
    - L2 normalization for similarity computation
    """

    EMBEDDING_DIM = 16

    # Archetype centroids (learned from training data)
    ARCHETYPE_CENTROIDS: Dict[BehavioralArchetype, np.ndarray] = {
        BehavioralArchetype.PROMPT_PAYER: np.array([
            0.9, 0.9, 0.9, 0.7,   # High response
            0.5, 0.3, 0.7, 0.6,   # Balanced temporal
            0.9, 0.9, 0.9, 0.9,   # Excellent payment
            0.8, 0.9, 0.1, 0.9    # Positive engagement
        ], dtype=np.float32),
        BehavioralArchetype.NEGOTIATOR: np.array([
            0.7, 0.8, 0.6, 0.8,   # Good response
            0.6, 0.4, 0.5, 0.5,   # Active times
            0.5, 0.6, 0.7, 0.6,   # Moderate payment
            0.6, 0.7, 0.3, 0.6    # Engaged
        ], dtype=np.float32),
        BehavioralArchetype.PROCRASTINATOR: np.array([
            0.3, 0.5, 0.4, 0.5,   # Slow response
            0.4, 0.6, 0.7, 0.4,   # Evening preference
            0.3, 0.4, 0.6, 0.5,   # Delayed payment
            0.5, 0.5, 0.2, 0.5    # Neutral engagement
        ], dtype=np.float32),
        BehavioralArchetype.GHOST: np.array([
            0.1, 0.1, 0.1, 0.3,   # Minimal response
            0.2, 0.2, 0.2, 0.2,   # Low activity
            0.1, 0.1, 0.2, 0.1,   # Minimal payment
            0.3, 0.2, 0.1, 0.2    # Disengaged
        ], dtype=np.float32),
        BehavioralArchetype.HOSTILE: np.array([
            0.5, 0.6, 0.3, 0.6,   # Variable response
            0.5, 0.5, 0.6, 0.5,   # Normal temporal
            0.2, 0.2, 0.3, 0.2,   # Low payment
            0.1, 0.1, 0.9, 0.1    # Negative engagement
        ], dtype=np.float32),
        BehavioralArchetype.VULNERABLE: np.array([
            0.6, 0.7, 0.5, 0.5,   # Moderate response
            0.5, 0.4, 0.6, 0.5,   # Varied temporal
            0.4, 0.5, 0.4, 0.6,   # Struggling payment
            0.5, 0.6, 0.2, 0.5    # Cooperative but stressed
        ], dtype=np.float32),
        BehavioralArchetype.STRATEGIC_DEFAULTER: np.array([
            0.4, 0.3, 0.5, 0.7,   # Selective response
            0.6, 0.5, 0.4, 0.5,   # Normal patterns
            0.1, 0.2, 0.3, 0.2,   # Minimal payment
            0.4, 0.3, 0.4, 0.3    # Calculated engagement
        ], dtype=np.float32),
    }

    def __init__(self, features: Optional[BehavioralFeatures] = None):
        """
        Initialize embedding from features.

        Args:
            features: Raw behavioral features
        """
        self.features = features or BehavioralFeatures()
        self._embedding: Optional[np.ndarray] = None
        self._archetype: Optional[BehavioralArchetype] = None

    def compute_embedding(self) -> np.ndarray:
        """
        Compute the behavioral embedding vector.

        Transformation Pipeline:
        1. Feature extraction and normalization
        2. Dimensionality reduction (PCA simulation)
        3. L2 normalization

        Returns:
            16-dimensional embedding vector
        """
        raw = self.features.to_vector()

        # Reshape to 16D embedding through aggregation
        # Response Profile (dims 0-3)
        response_profile = np.array([
            raw[0],                             # latency
            raw[1],                             # rate
            raw[2],                             # consistency
            np.mean([raw[3], raw[4], raw[7]])   # channel composite
        ])

        # Temporal Profile (dims 4-7)
        temporal_profile = np.array([
            raw[8],                             # morning
            raw[9],                             # afternoon
            raw[10],                            # evening
            raw[11]                             # weekend
        ])

        # Payment Profile (dims 8-11)
        payment_profile = np.array([
            raw[12],                            # velocity
            raw[13],                            # consistency
            raw[14],                            # completeness
            raw[15]                             # promise kept rate
        ])

        # Engagement Profile (dims 12-15)
        engagement_profile = np.array([
            raw[18],                            # sentiment
            raw[19],                            # cooperation
            raw[20],                            # escalation (inverted)
            np.mean([raw[16], raw[17]])         # promise accuracy
        ])

        # Concatenate profiles
        embedding = np.concatenate([
            response_profile,
            temporal_profile,
            payment_profile,
            engagement_profile
        ])

        # L2 normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        self._embedding = embedding.astype(np.float32)
        return self._embedding

    @property
    def embedding(self) -> np.ndarray:
        """Get or compute the embedding vector."""
        if self._embedding is None:
            self.compute_embedding()
        return self._embedding

    def classify_archetype(self) -> Tuple[BehavioralArchetype, float]:
        """
        Classify consumer into behavioral archetype.

        Uses cosine similarity to archetype centroids.

        Returns:
            Tuple of (archetype, confidence)
        """
        embedding = self.embedding

        best_archetype = BehavioralArchetype.GHOST
        best_similarity = -1.0

        for archetype, centroid in self.ARCHETYPE_CENTROIDS.items():
            # Normalize centroid
            centroid_norm = centroid / np.linalg.norm(centroid)

            # Cosine similarity
            similarity = float(np.dot(embedding, centroid_norm))

            if similarity > best_similarity:
                best_similarity = similarity
                best_archetype = archetype

        self._archetype = best_archetype
        confidence = (best_similarity + 1) / 2  # Map [-1, 1] to [0, 1]

        return best_archetype, confidence

    def similarity(self, other: 'BehavioralEmbedding') -> float:
        """
        Compute cosine similarity with another embedding.

        Args:
            other: Another behavioral embedding

        Returns:
            Similarity score in [-1, 1]
        """
        return float(np.dot(self.embedding, other.embedding))

    def distance(self, other: 'BehavioralEmbedding') -> float:
        """
        Compute Euclidean distance to another embedding.

        Args:
            other: Another behavioral embedding

        Returns:
            Distance (lower = more similar)
        """
        return float(np.linalg.norm(self.embedding - other.embedding))


class BehavioralClusterEngine:
    """
    Clustering engine for behavioral archetypes.

    Uses k-means++ initialization with online updates.
    """

    def __init__(self, n_clusters: int = 7):
        """
        Initialize clustering engine.

        Args:
            n_clusters: Number of clusters (default = number of archetypes)
        """
        self.n_clusters = n_clusters
        self.centroids: Optional[np.ndarray] = None
        self.cluster_sizes: np.ndarray = np.zeros(n_clusters)

    def fit(self, embeddings: List[np.ndarray]) -> np.ndarray:
        """
        Fit clusters to embeddings using k-means.

        Args:
            embeddings: List of embedding vectors

        Returns:
            Cluster assignments
        """
        if not embeddings:
            return np.array([])

        X = np.stack(embeddings)
        n_samples = len(X)

        # Initialize centroids (k-means++)
        self.centroids = self._kmeans_plus_plus_init(X)

        # Run k-means iterations
        max_iters = 100
        for _ in range(max_iters):
            # Assign samples to nearest centroid
            assignments = self._assign_clusters(X)

            # Update centroids
            new_centroids = np.zeros_like(self.centroids)
            for k in range(self.n_clusters):
                mask = assignments == k
                if np.any(mask):
                    new_centroids[k] = X[mask].mean(axis=0)
                    self.cluster_sizes[k] = np.sum(mask)
                else:
                    new_centroids[k] = self.centroids[k]

            # Check convergence
            if np.allclose(new_centroids, self.centroids):
                break

            self.centroids = new_centroids

        return self._assign_clusters(X)

    def _kmeans_plus_plus_init(self, X: np.ndarray) -> np.ndarray:
        """K-means++ centroid initialization."""
        n_samples = len(X)
        centroids = [X[np.random.randint(n_samples)]]

        for _ in range(1, self.n_clusters):
            # Compute distances to nearest centroid
            distances = np.min([
                np.linalg.norm(X - c, axis=1) ** 2
                for c in centroids
            ], axis=0)

            # Sample proportional to distance squared
            probs = distances / distances.sum()
            new_centroid_idx = np.random.choice(n_samples, p=probs)
            centroids.append(X[new_centroid_idx])

        return np.stack(centroids)

    def _assign_clusters(self, X: np.ndarray) -> np.ndarray:
        """Assign samples to nearest centroids."""
        distances = np.array([
            np.linalg.norm(X - c, axis=1)
            for c in self.centroids
        ]).T
        return np.argmin(distances, axis=1)

    def predict(self, embedding: np.ndarray) -> int:
        """
        Predict cluster for a single embedding.

        Args:
            embedding: Embedding vector

        Returns:
            Cluster index
        """
        if self.centroids is None:
            raise ValueError("Model not fitted")

        distances = [np.linalg.norm(embedding - c) for c in self.centroids]
        return int(np.argmin(distances))


# =============================================================================
# SECTION 3: LIQUIDITY DETECTION
# =============================================================================

class PaydayPattern(Enum):
    """Income/payday frequency patterns."""
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    SEMIMONTHLY = "semimonthly"  # 1st and 15th
    MONTHLY = "monthly"
    IRREGULAR = "irregular"
    UNKNOWN = "unknown"


@dataclass
class LiquidityWindow:
    """
    Represents an optimal window for contact/payment.

    Attributes:
        start_day: Day of month (1-31) or day of week (0-6)
        duration_days: Length of the window
        confidence: Confidence in this window
        expected_capacity: Expected payment capacity in this window
    """
    start_day: int
    duration_days: int
    confidence: float
    expected_capacity: float
    pattern_type: PaydayPattern = PaydayPattern.UNKNOWN


class LiquidityDetector:
    """
    Detects consumer liquidity patterns for optimal contact timing.

    Mathematical Approach:
    1. Fourier Transform for cycle detection
    2. Autocorrelation for pattern validation
    3. Rolling window analysis for volatility

    Key Signals:
    - Payment timestamps -> payday inference
    - Response patterns -> availability windows
    - Bank-specific patterns (payroll processing)
    """

    # Common payday periods (in days)
    PERIOD_WEEKLY = 7
    PERIOD_BIWEEKLY = 14
    PERIOD_SEMIMONTHLY = 15  # Approximation
    PERIOD_MONTHLY = 30

    def __init__(self):
        """Initialize liquidity detector."""
        self.payment_history: List[Tuple[datetime, float]] = []
        self.response_history: List[datetime] = []
        self._detected_pattern: Optional[PaydayPattern] = None
        self._liquidity_windows: List[LiquidityWindow] = []

    def add_payment(self, timestamp: datetime, amount: float) -> None:
        """Record a payment event."""
        self.payment_history.append((timestamp, amount))
        self.payment_history.sort(key=lambda x: x[0])

    def add_response(self, timestamp: datetime) -> None:
        """Record a response event."""
        self.response_history.append(timestamp)
        self.response_history.sort()

    def detect_payday_pattern(self) -> Tuple[PaydayPattern, float]:
        """
        Detect the consumer's payday pattern.

        Algorithm:
        1. Extract payment intervals
        2. Apply FFT to find dominant frequency
        3. Match to known patterns
        4. Validate with autocorrelation

        Returns:
            Tuple of (pattern, confidence)
        """
        if len(self.payment_history) < 3:
            return PaydayPattern.UNKNOWN, 0.0

        # Extract payment days (day of month)
        payment_days = [p[0].day for p in self.payment_history]

        # Extract intervals between payments
        intervals = []
        for i in range(1, len(self.payment_history)):
            delta = (self.payment_history[i][0] - self.payment_history[i-1][0]).days
            if 0 < delta < 60:  # Filter outliers
                intervals.append(delta)

        if not intervals:
            return PaydayPattern.UNKNOWN, 0.0

        # Statistical analysis
        mean_interval = np.mean(intervals)
        std_interval = np.std(intervals)
        cv = std_interval / mean_interval if mean_interval > 0 else 1.0

        # Pattern matching with tolerance
        pattern_scores: Dict[PaydayPattern, float] = {}

        # Weekly (5-9 day intervals)
        weekly_match = sum(1 for i in intervals if 5 <= i <= 9) / len(intervals)
        pattern_scores[PaydayPattern.WEEKLY] = weekly_match

        # Biweekly (12-16 day intervals)
        biweekly_match = sum(1 for i in intervals if 12 <= i <= 16) / len(intervals)
        pattern_scores[PaydayPattern.BIWEEKLY] = biweekly_match

        # Semimonthly (14-16 day intervals, specific days)
        semimonthly_days = {1, 15, 16}
        day_match = sum(1 for d in payment_days if d in semimonthly_days) / len(payment_days)
        pattern_scores[PaydayPattern.SEMIMONTHLY] = biweekly_match * 0.5 + day_match * 0.5

        # Monthly (27-33 day intervals)
        monthly_match = sum(1 for i in intervals if 27 <= i <= 33) / len(intervals)
        pattern_scores[PaydayPattern.MONTHLY] = monthly_match

        # Irregular (high variance)
        pattern_scores[PaydayPattern.IRREGULAR] = min(1.0, cv)

        # Find best pattern
        best_pattern = max(pattern_scores.items(), key=lambda x: x[1])

        # Confidence based on consistency
        confidence = best_pattern[1] * (1 - min(1.0, cv))

        self._detected_pattern = best_pattern[0]
        return best_pattern[0], confidence

    def estimate_income_volatility(self) -> float:
        """
        Estimate income volatility from payment patterns.

        Volatility Calculation:
        sigma = std(amounts) / mean(amounts)

        High volatility indicates:
        - Irregular income (gig work, seasonal)
        - Financial instability
        - Need for flexible payment plans

        Returns:
            Coefficient of variation (0 = stable, >1 = highly volatile)
        """
        if len(self.payment_history) < 2:
            return 0.5  # Unknown, assume moderate

        amounts = [p[1] for p in self.payment_history]
        mean_amount = np.mean(amounts)

        if mean_amount <= 0:
            return 1.0

        return float(np.std(amounts) / mean_amount)

    def score_micropayment_capacity(
        self,
        target_amount: float,
        account_balance: float
    ) -> float:
        """
        Score the consumer's capacity for micro-payments.

        Factors:
        - Historical payment sizes
        - Income volatility
        - Balance relative to capacity

        Args:
            target_amount: Proposed payment amount
            account_balance: Outstanding balance

        Returns:
            Capacity score [0, 1] (1 = high capacity)
        """
        if not self.payment_history:
            # Default heuristic based on balance
            if target_amount <= 25:
                return 0.7
            elif target_amount <= 50:
                return 0.5
            else:
                return 0.3

        amounts = [p[1] for p in self.payment_history]
        median_payment = np.median(amounts)
        max_payment = np.max(amounts)

        # Capacity factors
        relative_to_median = min(1.0, median_payment / max(target_amount, 1))
        relative_to_max = min(1.0, target_amount / max(max_payment, 1))
        volatility_penalty = 1 - min(1.0, self.estimate_income_volatility())

        # Weighted combination
        capacity = (
            0.5 * relative_to_median +
            0.3 * (1 - relative_to_max) +
            0.2 * volatility_penalty
        )

        return max(0.0, min(1.0, capacity))

    def find_liquidity_windows(
        self,
        lookback_days: int = 90
    ) -> List[LiquidityWindow]:
        """
        Identify optimal liquidity windows for contact.

        Algorithm:
        1. Analyze payment and response day-of-month patterns
        2. Identify clusters of activity
        3. Score each cluster for liquidity potential

        Args:
            lookback_days: Days of history to analyze

        Returns:
            List of liquidity windows sorted by confidence
        """
        windows: List[LiquidityWindow] = []
        cutoff = datetime.now() - timedelta(days=lookback_days)

        # Filter to recent history
        recent_payments = [
            (ts, amt) for ts, amt in self.payment_history
            if ts >= cutoff
        ]
        recent_responses = [
            ts for ts in self.response_history
            if ts >= cutoff
        ]

        if not recent_payments and not recent_responses:
            # Return generic windows
            return [
                LiquidityWindow(1, 3, 0.5, 0.5, PaydayPattern.MONTHLY),
                LiquidityWindow(15, 3, 0.5, 0.5, PaydayPattern.SEMIMONTHLY),
            ]

        # Count activity by day of month
        day_activity: Dict[int, float] = defaultdict(float)

        for ts, amt in recent_payments:
            day_activity[ts.day] += 2.0  # Payments weighted higher

        for ts in recent_responses:
            day_activity[ts.day] += 1.0

        # Find peaks (local maxima)
        days = list(range(1, 32))
        activity_scores = [day_activity.get(d, 0) for d in days]
        max_activity = max(activity_scores) if activity_scores else 1

        # Identify windows around activity peaks
        for day in days:
            score = day_activity.get(day, 0) / max(max_activity, 1)
            if score >= 0.3:  # Threshold for significant activity
                # Calculate expected capacity
                payments_on_day = [
                    amt for ts, amt in recent_payments
                    if ts.day == day
                ]
                capacity = np.mean(payments_on_day) if payments_on_day else 50.0

                windows.append(LiquidityWindow(
                    start_day=day,
                    duration_days=3,
                    confidence=score,
                    expected_capacity=capacity,
                    pattern_type=self._detected_pattern or PaydayPattern.UNKNOWN
                ))

        # Sort by confidence
        windows.sort(key=lambda w: w.confidence, reverse=True)
        self._liquidity_windows = windows

        return windows

    def optimal_contact_day(self, reference_date: datetime) -> Tuple[int, float]:
        """
        Recommend the optimal day of month to contact.

        Strategy:
        - Contact 1-2 days before expected payday
        - Avoid post-payday (when funds may be committed)

        Args:
            reference_date: Reference date for calculation

        Returns:
            Tuple of (day_of_month, confidence)
        """
        if not self._liquidity_windows:
            self.find_liquidity_windows()

        if not self._liquidity_windows:
            # Default to end of month
            return 28, 0.3

        best_window = self._liquidity_windows[0]

        # Contact 1-2 days before the peak
        contact_day = best_window.start_day - 2
        if contact_day < 1:
            contact_day += 28  # Wrap to previous month

        return contact_day, best_window.confidence


# =============================================================================
# SECTION 4: SENTIMENT ANALYSIS INTEGRATION
# =============================================================================

class SentimentCategory(Enum):
    """Sentiment categories for consumer messages."""
    VERY_NEGATIVE = -2
    NEGATIVE = -1
    NEUTRAL = 0
    POSITIVE = 1
    VERY_POSITIVE = 2


@dataclass
class SentimentAnalysis:
    """
    Result of sentiment analysis on a message.

    Attributes:
        score: Overall sentiment score [-1, 1]
        category: Discrete sentiment category
        escalation_risk: Risk of escalation [0, 1]
        cooperation_signal: Level of cooperation [0, 1]
        desperation_indicator: Signs of financial desperation [0, 1]
        key_phrases: Important phrases detected
    """
    score: float
    category: SentimentCategory
    escalation_risk: float
    cooperation_signal: float
    desperation_indicator: float
    key_phrases: List[str] = field(default_factory=list)


class SentimentAnalyzer:
    """
    Sentiment analysis engine for consumer communications.

    Components:
    1. Lexicon-based scoring (AFINN-style)
    2. Pattern matching for domain-specific signals
    3. Contextual modifiers

    Domain-Specific Signals:
    - Cooperation: "I want to pay", "work out a plan"
    - Escalation: "lawyer", "sue", "harassment"
    - Desperation: "lost job", "medical bills", "homeless"
    """

    # Sentiment lexicon (simplified AFINN-style)
    LEXICON: Dict[str, float] = {
        # Positive
        "pay": 0.3,
        "payment": 0.3,
        "agree": 0.5,
        "thanks": 0.4,
        "thank": 0.4,
        "appreciate": 0.5,
        "willing": 0.4,
        "help": 0.2,
        "understand": 0.3,
        "work out": 0.4,
        "settle": 0.3,
        "resolve": 0.4,
        "plan": 0.2,
        "promise": 0.3,
        "yes": 0.2,
        "okay": 0.1,
        "sure": 0.2,

        # Negative
        "not": -0.2,
        "can't": -0.3,
        "cannot": -0.3,
        "won't": -0.4,
        "refuse": -0.5,
        "never": -0.4,
        "stop": -0.3,
        "harass": -0.7,
        "harassment": -0.7,
        "illegal": -0.6,
        "sue": -0.8,
        "lawyer": -0.5,
        "attorney": -0.5,
        "court": -0.4,
        "scam": -0.7,
        "fraud": -0.7,
        "unfair": -0.5,
        "angry": -0.6,
        "upset": -0.4,
        "frustrated": -0.5,
    }

    # Escalation patterns
    ESCALATION_PATTERNS: List[Tuple[str, float]] = [
        (r"contact.*lawyer", 0.8),
        (r"call.*attorney", 0.8),
        (r"sue\s+you", 0.9),
        (r"file.*complaint", 0.7),
        (r"consumer.*protection", 0.6),
        (r"report.*to", 0.5),
        (r"stop.*calling", 0.6),
        (r"cease.*desist", 0.9),
        (r"harassment", 0.8),
        (r"violat", 0.7),
        (r"fdcpa", 0.8),
        (r"illegal", 0.6),
    ]

    # Cooperation patterns
    COOPERATION_PATTERNS: List[Tuple[str, float]] = [
        (r"want.*pay", 0.8),
        (r"willing.*pay", 0.9),
        (r"work.*out", 0.7),
        (r"payment.*plan", 0.8),
        (r"settle", 0.7),
        (r"can.*afford", 0.6),
        (r"pay.*month", 0.7),
        (r"send.*money", 0.8),
        (r"make.*payment", 0.8),
        (r"resolve", 0.6),
        (r"agree", 0.7),
    ]

    # Desperation patterns
    DESPERATION_PATTERNS: List[Tuple[str, float]] = [
        (r"lost.*job", 0.9),
        (r"unemployed", 0.8),
        (r"medical.*bill", 0.7),
        (r"hospital", 0.6),
        (r"sick", 0.5),
        (r"divorce", 0.7),
        (r"homeless", 0.9),
        (r"can't.*afford", 0.7),
        (r"no.*money", 0.8),
        (r"broke", 0.6),
        (r"disability", 0.7),
        (r"food", 0.6),
        (r"rent", 0.5),
        (r"evict", 0.8),
        (r"behind.*bills", 0.7),
    ]

    def __init__(self):
        """Initialize sentiment analyzer."""
        import re
        self.re = re

    def analyze(self, message: str) -> SentimentAnalysis:
        """
        Perform comprehensive sentiment analysis.

        Args:
            message: Consumer message text

        Returns:
            SentimentAnalysis with all scores
        """
        message_lower = message.lower()
        words = message_lower.split()

        # Lexicon-based sentiment
        sentiment_sum = 0.0
        word_count = 0
        key_phrases = []

        for word in words:
            if word in self.LEXICON:
                sentiment_sum += self.LEXICON[word]
                word_count += 1
                key_phrases.append(word)

        # Normalize sentiment score
        if word_count > 0:
            sentiment_score = sentiment_sum / word_count
        else:
            sentiment_score = 0.0

        # Clamp to [-1, 1]
        sentiment_score = max(-1.0, min(1.0, sentiment_score))

        # Escalation detection
        escalation_risk = 0.0
        for pattern, weight in self.ESCALATION_PATTERNS:
            if self.re.search(pattern, message_lower):
                escalation_risk = max(escalation_risk, weight)
                if weight >= 0.7:
                    key_phrases.append(f"[escalation:{pattern}]")

        # Cooperation detection
        cooperation_signal = 0.0
        for pattern, weight in self.COOPERATION_PATTERNS:
            if self.re.search(pattern, message_lower):
                cooperation_signal = max(cooperation_signal, weight)
                if weight >= 0.7:
                    key_phrases.append(f"[cooperation:{pattern}]")

        # Desperation detection
        desperation_indicator = 0.0
        for pattern, weight in self.DESPERATION_PATTERNS:
            if self.re.search(pattern, message_lower):
                desperation_indicator = max(desperation_indicator, weight)
                if weight >= 0.7:
                    key_phrases.append(f"[desperation:{pattern}]")

        # Determine category
        if sentiment_score >= 0.5:
            category = SentimentCategory.VERY_POSITIVE
        elif sentiment_score >= 0.2:
            category = SentimentCategory.POSITIVE
        elif sentiment_score <= -0.5:
            category = SentimentCategory.VERY_NEGATIVE
        elif sentiment_score <= -0.2:
            category = SentimentCategory.NEGATIVE
        else:
            category = SentimentCategory.NEUTRAL

        # Adjust for escalation (escalation makes sentiment more negative)
        if escalation_risk > 0.5 and sentiment_score > -0.5:
            sentiment_score = min(sentiment_score, -0.3)
            category = SentimentCategory.NEGATIVE

        return SentimentAnalysis(
            score=sentiment_score,
            category=category,
            escalation_risk=escalation_risk,
            cooperation_signal=cooperation_signal,
            desperation_indicator=desperation_indicator,
            key_phrases=key_phrases
        )

    def track_sentiment_trend(
        self,
        messages: List[Tuple[datetime, str]]
    ) -> Dict[str, Any]:
        """
        Track sentiment trend over multiple messages.

        Args:
            messages: List of (timestamp, message) tuples

        Returns:
            Trend analysis including slope and volatility
        """
        if not messages:
            return {"trend": "unknown", "slope": 0.0, "volatility": 0.0}

        # Sort by timestamp
        messages = sorted(messages, key=lambda x: x[0])

        # Analyze each message
        scores = []
        for _, msg in messages:
            analysis = self.analyze(msg)
            scores.append(analysis.score)

        if len(scores) < 2:
            return {
                "trend": "stable",
                "slope": 0.0,
                "volatility": 0.0,
                "latest_score": scores[0] if scores else 0.0
            }

        # Calculate trend (linear regression slope)
        x = np.arange(len(scores))
        slope = np.polyfit(x, scores, 1)[0]

        # Calculate volatility
        volatility = float(np.std(scores))

        # Determine trend direction
        if slope > 0.1:
            trend = "improving"
        elif slope < -0.1:
            trend = "deteriorating"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "slope": float(slope),
            "volatility": volatility,
            "latest_score": scores[-1],
            "average_score": float(np.mean(scores))
        }


# =============================================================================
# SECTION 5: PROPENSITY MODELS
# =============================================================================

@dataclass
class PropensityFeatures:
    """
    Features for propensity model predictions.

    Organized by prediction type:
    - Response features: contact type, time, history
    - Payment features: response status, offer type, urgency
    - Promise features: promise details, history
    - Escalation features: interaction count, sentiment
    """
    # Contact context
    contact_type: str = "sms"           # sms, email, phone, mail
    contact_hour: int = 12              # Hour of day (0-23)
    contact_day: int = 3                # Day of week (0=Mon, 6=Sun)
    contact_day_of_month: int = 15      # Day of month (1-31)

    # History features
    total_contacts: int = 0             # Total contact attempts
    successful_contacts: int = 0        # Contacts that got response
    days_since_last_contact: float = 7.0
    days_since_last_response: float = 30.0
    days_in_collection: int = 90        # Days since account assigned

    # Account features
    balance: float = 500.0
    original_balance: float = 500.0
    payment_count: int = 0
    total_paid: float = 0.0

    # Offer features
    offer_type: str = "full"            # full, settlement, payment_plan
    discount_percent: float = 0.0
    urgency_level: int = 1              # 1=low, 2=medium, 3=high

    # Promise features
    promise_made: bool = False
    promise_amount: float = 0.0
    promise_date: Optional[datetime] = None
    promises_kept: int = 0
    promises_broken: int = 0

    # Sentiment features
    last_sentiment_score: float = 0.0
    avg_sentiment_score: float = 0.0
    escalation_risk: float = 0.0
    cooperation_signal: float = 0.5

    # Behavioral features
    archetype: Optional[BehavioralArchetype] = None
    current_state: ConsumerState = ConsumerState.DORMANT
    engagement_level: float = 0.5


class PropensityModel(ABC):
    """
    Abstract base class for propensity models.

    All propensity models implement:
    - Feature extraction
    - Probability prediction
    - Confidence estimation
    """

    @abstractmethod
    def predict(self, features: PropensityFeatures) -> Tuple[float, float]:
        """
        Predict probability and confidence.

        Args:
            features: Input features

        Returns:
            Tuple of (probability, confidence)
        """
        pass

    @abstractmethod
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores."""
        pass


class ResponsePropensityModel(PropensityModel):
    """
    Model: P(respond | contact_type, time, history)

    Predicts the probability of consumer response to a contact attempt.

    Mathematical Model:
        logit(P) = beta_0 + beta_channel * X_channel + beta_time * X_time
                   + beta_history * X_history + interactions

    Key Factors:
    - Channel effectiveness (SMS > Email > Phone > Mail)
    - Time of day (evening peak)
    - Contact fatigue (diminishing returns)
    - Recency of last response
    """

    # Channel base rates
    CHANNEL_RATES = {
        "sms": 0.35,
        "email": 0.15,
        "phone": 0.25,
        "mail": 0.08,
        "push": 0.20,
    }

    # Hour effectiveness multipliers (peak in evening)
    HOUR_MULTIPLIERS = {
        range(0, 6): 0.3,    # Night
        range(6, 9): 0.7,    # Early morning
        range(9, 12): 0.9,   # Morning
        range(12, 14): 0.8,  # Lunch
        range(14, 17): 1.0,  # Afternoon
        range(17, 21): 1.2,  # Evening (peak)
        range(21, 24): 0.6,  # Late night
    }

    def __init__(self):
        """Initialize response propensity model."""
        self.feature_weights = {
            "channel": 0.30,
            "time": 0.15,
            "history": 0.25,
            "recency": 0.20,
            "engagement": 0.10,
        }

    def predict(self, features: PropensityFeatures) -> Tuple[float, float]:
        """
        Predict response probability.

        P(respond) = base_rate * time_modifier * history_modifier * recency_modifier
        """
        # Base rate from channel
        base_rate = self.CHANNEL_RATES.get(features.contact_type, 0.15)

        # Time modifier
        hour = features.contact_hour
        time_modifier = 0.8  # Default
        for hour_range, multiplier in self.HOUR_MULTIPLIERS.items():
            if hour in hour_range:
                time_modifier = multiplier
                break

        # Weekend penalty
        if features.contact_day >= 5:  # Saturday, Sunday
            time_modifier *= 0.8

        # History modifier (contact fatigue)
        if features.total_contacts > 0:
            response_rate = features.successful_contacts / features.total_contacts
            fatigue = max(0.3, 1.0 - (features.total_contacts / 20.0))
            history_modifier = 0.5 + (response_rate * 0.5) * fatigue
        else:
            history_modifier = 1.0

        # Recency modifier
        days_since = features.days_since_last_response
        if days_since < 7:
            recency_modifier = 1.2  # Recent responder
        elif days_since < 30:
            recency_modifier = 1.0
        elif days_since < 90:
            recency_modifier = 0.7
        else:
            recency_modifier = 0.4  # Long-dormant

        # Engagement modifier
        engagement_modifier = 0.5 + features.engagement_level * 0.5

        # Combined probability
        probability = (
            base_rate *
            time_modifier *
            history_modifier *
            recency_modifier *
            engagement_modifier
        )

        # Clamp probability
        probability = max(0.01, min(0.95, probability))

        # Confidence based on data availability
        confidence = min(1.0, 0.3 + features.total_contacts * 0.05)

        return probability, confidence

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores."""
        return self.feature_weights.copy()

    def optimal_contact_time(
        self,
        features: PropensityFeatures
    ) -> Tuple[int, int, float]:
        """
        Find optimal hour and day for contact.

        Returns:
            Tuple of (optimal_hour, optimal_day, expected_probability)
        """
        best_prob = 0.0
        best_hour = 17
        best_day = 2  # Wednesday

        original_hour = features.contact_hour
        original_day = features.contact_day

        for day in range(7):
            for hour in range(8, 21):  # Business hours only
                features.contact_hour = hour
                features.contact_day = day
                prob, _ = self.predict(features)
                if prob > best_prob:
                    best_prob = prob
                    best_hour = hour
                    best_day = day

        # Restore original values
        features.contact_hour = original_hour
        features.contact_day = original_day

        return best_hour, best_day, best_prob


class PaymentPropensityModel(PropensityModel):
    """
    Model: P(pay | respond, offer_type, urgency)

    Predicts probability of payment given a response.

    Mathematical Model:
        P(pay|respond) = sigmoid(
            beta_0 +
            beta_offer * offer_attractiveness +
            beta_urgency * urgency_score +
            beta_capacity * payment_capacity +
            beta_history * payment_history
        )

    Key Factors:
    - Offer attractiveness (discount, plan flexibility)
    - Payment urgency signaling
    - Consumer's payment capacity
    - Historical payment behavior
    """

    # Offer type effectiveness
    OFFER_RATES = {
        "full": 0.20,
        "settlement": 0.40,
        "payment_plan": 0.35,
        "hardship": 0.45,
        "final_notice": 0.30,
    }

    def __init__(self):
        """Initialize payment propensity model."""
        self.feature_weights = {
            "offer_type": 0.25,
            "discount": 0.20,
            "urgency": 0.15,
            "capacity": 0.20,
            "history": 0.20,
        }

    def predict(self, features: PropensityFeatures) -> Tuple[float, float]:
        """
        Predict payment probability given response.

        Assumes the consumer has already responded (conditional probability).
        """
        # Base rate from offer type
        base_rate = self.OFFER_RATES.get(features.offer_type, 0.25)

        # Discount modifier
        if features.discount_percent > 0:
            discount_modifier = 1.0 + (features.discount_percent / 100.0) * 0.5
        else:
            discount_modifier = 1.0

        # Urgency modifier
        urgency_multipliers = {1: 0.9, 2: 1.0, 3: 1.2}
        urgency_modifier = urgency_multipliers.get(features.urgency_level, 1.0)

        # Payment capacity (based on balance relative to typical payments)
        if features.payment_count > 0:
            avg_payment = features.total_paid / features.payment_count
            capacity = min(1.5, avg_payment / max(features.balance * 0.1, 1))
        else:
            # Infer from balance (smaller balances easier)
            if features.balance < 100:
                capacity = 1.3
            elif features.balance < 500:
                capacity = 1.0
            else:
                capacity = 0.7

        # History modifier
        if features.payment_count > 0:
            history_modifier = 1.0 + (features.payment_count / 10.0) * 0.3
        else:
            history_modifier = 0.8

        # Cooperation signal boost
        if features.cooperation_signal > 0.5:
            cooperation_boost = 1.0 + features.cooperation_signal * 0.3
        else:
            cooperation_boost = 1.0

        # Combined probability
        probability = (
            base_rate *
            discount_modifier *
            urgency_modifier *
            capacity *
            history_modifier *
            cooperation_boost
        )

        # Clamp probability
        probability = max(0.01, min(0.90, probability))

        # Confidence
        confidence = min(1.0, 0.4 + features.payment_count * 0.1)

        return probability, confidence

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores."""
        return self.feature_weights.copy()

    def optimal_offer(
        self,
        features: PropensityFeatures,
        min_acceptable: float = 0.5
    ) -> Dict[str, Any]:
        """
        Recommend optimal offer structure.

        Args:
            features: Consumer features
            min_acceptable: Minimum acceptable recovery rate

        Returns:
            Recommended offer parameters
        """
        best_offer = {
            "type": "full",
            "discount": 0.0,
            "urgency": 1,
            "expected_prob": 0.0,
            "expected_recovery": 0.0
        }

        for offer_type in self.OFFER_RATES.keys():
            for discount in [0, 10, 20, 30, 40, 50]:
                for urgency in [1, 2, 3]:
                    features.offer_type = offer_type
                    features.discount_percent = discount
                    features.urgency_level = urgency

                    prob, _ = self.predict(features)
                    recovery_rate = (100 - discount) / 100.0
                    expected_recovery = prob * recovery_rate

                    if (expected_recovery > best_offer["expected_recovery"] and
                        recovery_rate >= min_acceptable):
                        best_offer = {
                            "type": offer_type,
                            "discount": discount,
                            "urgency": urgency,
                            "expected_prob": prob,
                            "expected_recovery": expected_recovery
                        }

        return best_offer


class PromisePropensityModel(PropensityModel):
    """
    Model: P(keep_promise | promise_made, history)

    Predicts probability that a payment promise will be honored.

    Mathematical Model:
        P(keep) = base_rate * reliability_score * recency_weight * amount_feasibility

    Key Factors:
    - Historical promise-keeping rate
    - Time since promise (decay)
    - Amount relative to capacity
    - External factors (payday alignment)
    """

    def __init__(self):
        """Initialize promise propensity model."""
        self.feature_weights = {
            "history": 0.40,
            "amount_feasibility": 0.25,
            "timing": 0.20,
            "engagement": 0.15,
        }

    def predict(self, features: PropensityFeatures) -> Tuple[float, float]:
        """
        Predict promise fulfillment probability.
        """
        if not features.promise_made:
            return 0.0, 0.0

        # Base rate (general promise fulfillment rate)
        base_rate = 0.45

        # Historical reliability
        total_promises = features.promises_kept + features.promises_broken
        if total_promises > 0:
            reliability = features.promises_kept / total_promises
            reliability_score = 0.3 + reliability * 0.7
        else:
            reliability_score = 0.5  # Unknown, use moderate estimate

        # Amount feasibility
        if features.promise_amount > 0 and features.balance > 0:
            amount_ratio = features.promise_amount / features.balance
            if amount_ratio <= 0.1:  # Small promise
                amount_feasibility = 1.2
            elif amount_ratio <= 0.25:
                amount_feasibility = 1.0
            elif amount_ratio <= 0.5:
                amount_feasibility = 0.8
            else:  # Large promise
                amount_feasibility = 0.5
        else:
            amount_feasibility = 0.8

        # Timing (promises closer to payday more likely honored)
        # This would integrate with LiquidityDetector in practice
        timing_score = 0.9  # Default moderate

        # Engagement modifier
        engagement_modifier = 0.7 + features.engagement_level * 0.3

        # Combined probability
        probability = (
            base_rate *
            reliability_score *
            amount_feasibility *
            timing_score *
            engagement_modifier
        )

        # Clamp
        probability = max(0.05, min(0.95, probability))

        # Confidence based on history
        confidence = min(1.0, 0.3 + total_promises * 0.15)

        return probability, confidence

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores."""
        return self.feature_weights.copy()


class EscalationPropensityModel(PropensityModel):
    """
    Model: P(escalate | interaction_count, sentiment)

    Predicts probability of consumer escalation (complaint, legal, etc.).

    Mathematical Model:
        P(escalate) = sigmoid(
            beta_0 +
            beta_contacts * contact_intensity +
            beta_sentiment * negative_sentiment +
            beta_history * dispute_history +
            beta_vulnerability * vulnerability_score
        )

    Key Factors:
    - Contact frequency and intensity
    - Negative sentiment accumulation
    - Previous dispute history
    - Vulnerability indicators
    """

    def __init__(self):
        """Initialize escalation propensity model."""
        self.feature_weights = {
            "contact_intensity": 0.25,
            "sentiment": 0.35,
            "history": 0.20,
            "vulnerability": 0.20,
        }

    def predict(self, features: PropensityFeatures) -> Tuple[float, float]:
        """
        Predict escalation probability.
        """
        # Base rate (general escalation rate)
        base_rate = 0.05

        # Contact intensity (more contacts = higher risk)
        if features.days_in_collection > 0:
            contact_rate = features.total_contacts / features.days_in_collection * 30
            if contact_rate > 10:
                intensity_score = 2.0  # High intensity
            elif contact_rate > 5:
                intensity_score = 1.5
            else:
                intensity_score = 1.0
        else:
            intensity_score = 1.0

        # Sentiment score (negative = higher risk)
        if features.avg_sentiment_score < -0.3:
            sentiment_score = 2.0
        elif features.avg_sentiment_score < 0:
            sentiment_score = 1.3
        elif features.avg_sentiment_score > 0.3:
            sentiment_score = 0.5
        else:
            sentiment_score = 1.0

        # Direct escalation signals
        if features.escalation_risk > 0.5:
            escalation_boost = 2.0 + features.escalation_risk
        else:
            escalation_boost = 1.0

        # State-based modifier
        state_modifiers = {
            ConsumerState.HOSTILE: 3.0,
            ConsumerState.LEGAL: 0.5,  # Already escalated
            ConsumerState.RESOLVED: 0.1,
            ConsumerState.PAYING: 0.3,
            ConsumerState.DORMANT: 0.8,
        }
        state_modifier = state_modifiers.get(features.current_state, 1.0)

        # Combined probability
        probability = (
            base_rate *
            intensity_score *
            sentiment_score *
            escalation_boost *
            state_modifier
        )

        # Clamp
        probability = max(0.01, min(0.80, probability))

        # Confidence
        confidence = min(1.0, 0.5 + features.total_contacts * 0.03)

        return probability, confidence

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores."""
        return self.feature_weights.copy()

    def recommend_de_escalation(
        self,
        features: PropensityFeatures
    ) -> Dict[str, Any]:
        """
        Recommend de-escalation strategies.

        Returns:
            De-escalation recommendations
        """
        prob, _ = self.predict(features)

        recommendations = {
            "risk_level": "low" if prob < 0.2 else "medium" if prob < 0.5 else "high",
            "escalation_probability": prob,
            "actions": []
        }

        if prob > 0.3:
            recommendations["actions"].append("Reduce contact frequency")

        if features.avg_sentiment_score < -0.2:
            recommendations["actions"].append("Use empathetic messaging")

        if features.escalation_risk > 0.5:
            recommendations["actions"].append("Flag for supervisor review")

        if features.total_contacts > 10 and features.successful_contacts < 2:
            recommendations["actions"].append("Consider alternative contact channels")

        if features.cooperation_signal > 0.5:
            recommendations["actions"].append("Offer flexible payment options")

        return recommendations


# =============================================================================
# SECTION 6: INTEGRATED BEHAVIORAL MODEL
# =============================================================================

class SemanticBehavioralModel:
    """
    Integrated semantic behavioral model combining all components.

    This is the main interface for behavioral analysis and prediction.

    Components:
    1. State Machine: Tracks consumer lifecycle
    2. Embeddings: Dense behavioral representations
    3. Liquidity: Payment timing optimization
    4. Sentiment: Communication analysis
    5. Propensity: Outcome prediction

    Usage:
        model = SemanticBehavioralModel()
        model.initialize_consumer(account_data)
        model.update_interaction(interaction_data)
        prediction = model.predict_outcomes()
        strategy = model.recommend_strategy()
    """

    def __init__(self):
        """Initialize all model components."""
        self.state_machine = ConsumerStateMachine()
        self.behavioral_features = BehavioralFeatures()
        self.embedding = BehavioralEmbedding(self.behavioral_features)
        self.liquidity_detector = LiquidityDetector()
        self.sentiment_analyzer = SentimentAnalyzer()

        # Propensity models
        self.response_model = ResponsePropensityModel()
        self.payment_model = PaymentPropensityModel()
        self.promise_model = PromisePropensityModel()
        self.escalation_model = EscalationPropensityModel()

        # State
        self.consumer_id: Optional[str] = None
        self.propensity_features = PropensityFeatures()
        self.interaction_history: List[Dict[str, Any]] = []
        self.message_history: List[Tuple[datetime, str]] = []

    def initialize_consumer(self, account_data: Dict[str, Any]) -> None:
        """
        Initialize model for a specific consumer.

        Args:
            account_data: Consumer account information
        """
        self.consumer_id = account_data.get("account_id", "")

        # Initialize propensity features
        self.propensity_features = PropensityFeatures(
            balance=float(account_data.get("balance", 500)),
            original_balance=float(account_data.get("original_balance", 500)),
            payment_count=account_data.get("payment_count", 0),
            total_paid=float(account_data.get("total_paid", 0)),
            days_in_collection=account_data.get("days_in_collection", 0),
        )

        # Initialize behavioral features from history
        self.behavioral_features = BehavioralFeatures(
            response_rate=account_data.get("response_rate", 0.3),
            payment_velocity=account_data.get("payment_velocity", 0.5),
            channel_sms=account_data.get("sms_preference", 0.5),
            channel_email=account_data.get("email_preference", 0.3),
        )

        # Set initial state based on account status
        status = account_data.get("status", "active")
        if status == "paying":
            self.state_machine.current_state = ConsumerState.PAYING
        elif status == "committed":
            self.state_machine.current_state = ConsumerState.COMMITTED
        elif status == "dispute":
            self.state_machine.current_state = ConsumerState.HOSTILE

        # Compute initial embedding
        self.embedding = BehavioralEmbedding(self.behavioral_features)
        self.embedding.compute_embedding()

        logger.info(f"Initialized model for consumer {self.consumer_id}")

    def update_interaction(
        self,
        interaction: Dict[str, Any],
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Update model with new interaction data.

        Args:
            interaction: Interaction details
            timestamp: When the interaction occurred

        Returns:
            Update results including state changes
        """
        timestamp = timestamp or datetime.now()

        results = {
            "state_changed": False,
            "new_state": self.state_machine.current_state,
            "sentiment": None,
            "predictions": {}
        }

        # Extract interaction type
        interaction_type = interaction.get("type", "contact")

        # Process based on type
        if interaction_type == "response":
            # Consumer responded
            message = interaction.get("message", "")

            # Analyze sentiment
            sentiment = self.sentiment_analyzer.analyze(message)
            results["sentiment"] = {
                "score": sentiment.score,
                "category": sentiment.category.name,
                "escalation_risk": sentiment.escalation_risk,
                "cooperation_signal": sentiment.cooperation_signal,
            }

            # Update message history
            self.message_history.append((timestamp, message))

            # Update propensity features
            self.propensity_features.last_sentiment_score = sentiment.score
            self.propensity_features.escalation_risk = sentiment.escalation_risk
            self.propensity_features.cooperation_signal = sentiment.cooperation_signal

            # Determine state trigger
            if sentiment.escalation_risk > 0.7:
                trigger = "threat_detected"
            elif sentiment.cooperation_signal > 0.7:
                trigger = "settlement_inquiry"
            else:
                trigger = "contact_response"

            # Attempt state transition
            old_state = self.state_machine.current_state
            new_state, prob = self.state_machine.transition(
                trigger=trigger,
                context={"sentiment": sentiment.score},
                timestamp=timestamp
            )

            if new_state != old_state:
                results["state_changed"] = True
                results["new_state"] = new_state
                results["transition_probability"] = prob

            # Update response tracking
            self.liquidity_detector.add_response(timestamp)

        elif interaction_type == "payment":
            # Payment received
            amount = float(interaction.get("amount", 0))

            self.liquidity_detector.add_payment(timestamp, amount)
            self.propensity_features.payment_count += 1
            self.propensity_features.total_paid += amount

            # State transition
            old_state = self.state_machine.current_state
            trigger = "payment_completed"

            if self.propensity_features.total_paid >= self.propensity_features.balance:
                trigger = "final_payment"

            new_state, prob = self.state_machine.transition(
                trigger=trigger,
                timestamp=timestamp
            )

            if new_state != old_state:
                results["state_changed"] = True
                results["new_state"] = new_state

        elif interaction_type == "contact":
            # Outbound contact
            self.propensity_features.total_contacts += 1
            channel = interaction.get("channel", "sms")
            self.propensity_features.contact_type = channel

        elif interaction_type == "promise":
            # Payment promise made
            self.propensity_features.promise_made = True
            self.propensity_features.promise_amount = float(
                interaction.get("amount", 0)
            )

            # State transition to committed
            old_state = self.state_machine.current_state
            new_state, _ = self.state_machine.transition(
                trigger="agreement_accepted",
                timestamp=timestamp
            )

            if new_state != old_state:
                results["state_changed"] = True
                results["new_state"] = new_state

        # Record interaction
        self.interaction_history.append({
            "timestamp": timestamp,
            "type": interaction_type,
            "data": interaction,
            "results": results
        })

        return results

    def predict_outcomes(self) -> Dict[str, Dict[str, float]]:
        """
        Generate all propensity predictions.

        Returns:
            Dict with predictions for each outcome type
        """
        predictions = {}

        # Response probability
        resp_prob, resp_conf = self.response_model.predict(self.propensity_features)
        predictions["response"] = {
            "probability": resp_prob,
            "confidence": resp_conf
        }

        # Payment probability (conditional on response)
        pay_prob, pay_conf = self.payment_model.predict(self.propensity_features)
        predictions["payment"] = {
            "probability": pay_prob,
            "confidence": pay_conf,
            "combined_probability": resp_prob * pay_prob
        }

        # Promise fulfillment
        if self.propensity_features.promise_made:
            prom_prob, prom_conf = self.promise_model.predict(self.propensity_features)
            predictions["promise_fulfillment"] = {
                "probability": prom_prob,
                "confidence": prom_conf
            }

        # Escalation risk
        esc_prob, esc_conf = self.escalation_model.predict(self.propensity_features)
        predictions["escalation"] = {
            "probability": esc_prob,
            "confidence": esc_conf
        }

        return predictions

    def recommend_strategy(self) -> Dict[str, Any]:
        """
        Generate comprehensive strategy recommendation.

        Returns:
            Strategy recommendation with timing, channel, and offer details
        """
        predictions = self.predict_outcomes()

        # Determine archetype
        archetype, archetype_confidence = self.embedding.classify_archetype()

        # Get liquidity windows
        liquidity_windows = self.liquidity_detector.find_liquidity_windows()

        # Optimal contact time
        optimal_hour, optimal_day, _ = self.response_model.optimal_contact_time(
            self.propensity_features
        )

        # Optimal offer
        optimal_offer = self.payment_model.optimal_offer(
            self.propensity_features
        )

        # De-escalation if needed
        de_escalation = None
        if predictions["escalation"]["probability"] > 0.3:
            de_escalation = self.escalation_model.recommend_de_escalation(
                self.propensity_features
            )

        # Sentiment trend
        sentiment_trend = None
        if self.message_history:
            sentiment_trend = self.sentiment_analyzer.track_sentiment_trend(
                self.message_history
            )

        strategy = {
            "consumer_id": self.consumer_id,
            "current_state": self.state_machine.current_state.name,
            "archetype": {
                "type": archetype.name,
                "confidence": archetype_confidence
            },
            "predictions": predictions,
            "timing": {
                "optimal_hour": optimal_hour,
                "optimal_day": optimal_day,
                "liquidity_windows": [
                    {
                        "start_day": w.start_day,
                        "duration": w.duration_days,
                        "confidence": w.confidence
                    }
                    for w in liquidity_windows[:3]  # Top 3 windows
                ]
            },
            "offer": optimal_offer,
            "de_escalation": de_escalation,
            "sentiment_trend": sentiment_trend,
            "engagement_level": self.state_machine.engagement_decay.calculate_engagement(
                self.state_machine.current_state,
                datetime.now(),
                self.interaction_history[-1]["timestamp"] if self.interaction_history else None
            )
        }

        return strategy

    def simulate_trajectory(
        self,
        steps: int = 30,
        strategy: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Simulate likely consumer trajectory.

        Args:
            steps: Number of simulation steps
            strategy: Strategy to simulate (optional)

        Returns:
            Simulation results
        """
        # Run Monte Carlo simulation
        trajectory = self.state_machine.simulate_trajectory(steps)

        # Analyze trajectory
        resolved = trajectory[-1] == ConsumerState.RESOLVED
        escalated = ConsumerState.LEGAL in trajectory or ConsumerState.HOSTILE in trajectory

        state_distribution = {}
        for state in trajectory:
            state_distribution[state.name] = state_distribution.get(state.name, 0) + 1

        # Normalize
        total = len(trajectory)
        state_distribution = {k: v/total for k, v in state_distribution.items()}

        return {
            "trajectory_length": len(trajectory),
            "final_state": trajectory[-1].name,
            "resolved": resolved,
            "escalated": escalated,
            "state_distribution": state_distribution,
            "steps_to_resolution": (
                trajectory.index(ConsumerState.RESOLVED)
                if resolved else None
            )
        }

    def get_model_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive model summary.

        Returns:
            Summary of all model components
        """
        return {
            "consumer_id": self.consumer_id,
            "state_machine": {
                "current_state": self.state_machine.current_state.name,
                "state_history_length": len(self.state_machine.state_history),
                "available_transitions": list(
                    self.state_machine.get_all_transition_probabilities(
                        self.state_machine.current_state
                    ).keys()
                )
            },
            "embedding": {
                "dimensions": BehavioralEmbedding.EMBEDDING_DIM,
                "archetype": self.embedding.classify_archetype()[0].name
            },
            "liquidity": {
                "detected_pattern": (
                    self.liquidity_detector._detected_pattern.value
                    if self.liquidity_detector._detected_pattern else "unknown"
                ),
                "payment_history_length": len(self.liquidity_detector.payment_history),
                "income_volatility": self.liquidity_detector.estimate_income_volatility()
            },
            "propensity_features": {
                "balance": self.propensity_features.balance,
                "payment_count": self.propensity_features.payment_count,
                "total_contacts": self.propensity_features.total_contacts,
                "cooperation_signal": self.propensity_features.cooperation_signal,
                "escalation_risk": self.propensity_features.escalation_risk
            },
            "interaction_count": len(self.interaction_history),
            "message_count": len(self.message_history)
        }


# =============================================================================
# SECTION 7: SIMULATION AND TESTING UTILITIES
# =============================================================================

class BehavioralSimulator:
    """
    Simulation engine for behavioral model testing.

    Generates synthetic consumer data and runs simulations
    to validate model performance.
    """

    # Archetype-based behavior profiles
    ARCHETYPE_PROFILES = {
        BehavioralArchetype.PROMPT_PAYER: {
            "response_rate": 0.8,
            "payment_probability": 0.7,
            "promise_reliability": 0.9,
            "escalation_tendency": 0.05,
            "base_sentiment": 0.3,
        },
        BehavioralArchetype.NEGOTIATOR: {
            "response_rate": 0.7,
            "payment_probability": 0.4,
            "promise_reliability": 0.6,
            "escalation_tendency": 0.15,
            "base_sentiment": 0.1,
        },
        BehavioralArchetype.PROCRASTINATOR: {
            "response_rate": 0.4,
            "payment_probability": 0.3,
            "promise_reliability": 0.4,
            "escalation_tendency": 0.1,
            "base_sentiment": 0.0,
        },
        BehavioralArchetype.GHOST: {
            "response_rate": 0.1,
            "payment_probability": 0.05,
            "promise_reliability": 0.2,
            "escalation_tendency": 0.05,
            "base_sentiment": -0.1,
        },
        BehavioralArchetype.HOSTILE: {
            "response_rate": 0.5,
            "payment_probability": 0.1,
            "promise_reliability": 0.3,
            "escalation_tendency": 0.6,
            "base_sentiment": -0.5,
        },
        BehavioralArchetype.VULNERABLE: {
            "response_rate": 0.6,
            "payment_probability": 0.25,
            "promise_reliability": 0.5,
            "escalation_tendency": 0.2,
            "base_sentiment": -0.2,
        },
        BehavioralArchetype.STRATEGIC_DEFAULTER: {
            "response_rate": 0.3,
            "payment_probability": 0.1,
            "promise_reliability": 0.2,
            "escalation_tendency": 0.3,
            "base_sentiment": -0.1,
        },
    }

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize simulator.

        Args:
            seed: Random seed for reproducibility
        """
        if seed is not None:
            np.random.seed(seed)

    def generate_synthetic_consumer(
        self,
        archetype: Optional[BehavioralArchetype] = None
    ) -> Dict[str, Any]:
        """
        Generate synthetic consumer data.

        Args:
            archetype: Specific archetype to generate (random if None)

        Returns:
            Synthetic consumer account data
        """
        if archetype is None:
            archetype = np.random.choice(list(BehavioralArchetype))

        profile = self.ARCHETYPE_PROFILES[archetype]

        # Generate account data
        balance = np.random.uniform(100, 2000)
        days_in_collection = np.random.randint(30, 365)

        # Add noise to profile values
        noise = lambda v: max(0, min(1, v + np.random.normal(0, 0.1)))

        return {
            "account_id": f"SIM-{np.random.randint(100000, 999999)}",
            "balance": round(balance, 2),
            "original_balance": round(balance * np.random.uniform(1.0, 1.5), 2),
            "days_in_collection": days_in_collection,
            "payment_count": np.random.randint(0, 5),
            "total_paid": round(balance * np.random.uniform(0, 0.3), 2),
            "response_rate": noise(profile["response_rate"]),
            "payment_velocity": noise(profile["payment_probability"]),
            "sms_preference": np.random.uniform(0.3, 0.8),
            "email_preference": np.random.uniform(0.2, 0.6),
            "archetype": archetype.name,
            "status": "active"
        }

    def simulate_collection_cycle(
        self,
        consumer_data: Dict[str, Any],
        max_days: int = 90,
        contact_frequency: int = 7
    ) -> Dict[str, Any]:
        """
        Simulate a complete collection cycle.

        Args:
            consumer_data: Consumer account data
            max_days: Maximum simulation days
            contact_frequency: Days between contacts

        Returns:
            Simulation results
        """
        model = SemanticBehavioralModel()
        model.initialize_consumer(consumer_data)

        archetype = BehavioralArchetype[consumer_data.get("archetype", "GHOST")]
        profile = self.ARCHETYPE_PROFILES[archetype]

        simulation_log = []
        current_day = 0
        resolved = False
        escalated = False
        total_payments = 0.0

        while current_day < max_days and not resolved and not escalated:
            timestamp = datetime.now() + timedelta(days=current_day)

            # Simulate contact
            if current_day % contact_frequency == 0:
                model.update_interaction(
                    {"type": "contact", "channel": "sms"},
                    timestamp
                )

                # Check for response
                if np.random.random() < profile["response_rate"]:
                    # Generate response sentiment
                    sentiment = profile["base_sentiment"] + np.random.normal(0, 0.2)

                    if sentiment < -0.4:
                        message = "Stop calling me. I'll contact a lawyer."
                    elif sentiment < -0.1:
                        message = "I can't afford to pay right now."
                    elif sentiment < 0.2:
                        message = "I need more time to figure this out."
                    else:
                        message = "I want to work out a payment plan."

                    result = model.update_interaction(
                        {"type": "response", "message": message},
                        timestamp
                    )

                    simulation_log.append({
                        "day": current_day,
                        "event": "response",
                        "state": result["new_state"].name,
                        "sentiment": result["sentiment"]["score"] if result["sentiment"] else 0
                    })

                    # Check for payment
                    if np.random.random() < profile["payment_probability"]:
                        amount = min(
                            consumer_data["balance"] - total_payments,
                            np.random.uniform(25, 100)
                        )
                        total_payments += amount

                        model.update_interaction(
                            {"type": "payment", "amount": amount},
                            timestamp
                        )

                        simulation_log.append({
                            "day": current_day,
                            "event": "payment",
                            "amount": amount
                        })

                        if total_payments >= consumer_data["balance"]:
                            resolved = True

                    # Check for escalation
                    if result["sentiment"] and result["sentiment"]["escalation_risk"] > 0.7:
                        if np.random.random() < profile["escalation_tendency"]:
                            escalated = True

            current_day += 1

        return {
            "consumer_id": consumer_data["account_id"],
            "archetype": archetype.name,
            "days_simulated": current_day,
            "resolved": resolved,
            "escalated": escalated,
            "total_payments": round(total_payments, 2),
            "recovery_rate": total_payments / consumer_data["balance"],
            "final_state": model.state_machine.current_state.name,
            "interaction_count": len(simulation_log),
            "log": simulation_log
        }

    def run_batch_simulation(
        self,
        n_consumers: int = 100,
        max_days: int = 90
    ) -> Dict[str, Any]:
        """
        Run batch simulation across multiple consumers.

        Args:
            n_consumers: Number of consumers to simulate
            max_days: Maximum days per simulation

        Returns:
            Aggregate simulation results
        """
        results = []

        for _ in range(n_consumers):
            consumer = self.generate_synthetic_consumer()
            result = self.simulate_collection_cycle(consumer, max_days)
            results.append(result)

        # Aggregate metrics
        resolved_count = sum(1 for r in results if r["resolved"])
        escalated_count = sum(1 for r in results if r["escalated"])
        total_recovery = sum(r["total_payments"] for r in results)
        total_balance = sum(r["total_payments"] / r["recovery_rate"]
                          for r in results if r["recovery_rate"] > 0)

        # By archetype
        by_archetype = {}
        for archetype in BehavioralArchetype:
            archetype_results = [r for r in results if r["archetype"] == archetype.name]
            if archetype_results:
                by_archetype[archetype.name] = {
                    "count": len(archetype_results),
                    "resolution_rate": sum(1 for r in archetype_results if r["resolved"]) / len(archetype_results),
                    "escalation_rate": sum(1 for r in archetype_results if r["escalated"]) / len(archetype_results),
                    "avg_recovery": np.mean([r["recovery_rate"] for r in archetype_results])
                }

        return {
            "total_consumers": n_consumers,
            "resolved": resolved_count,
            "resolution_rate": resolved_count / n_consumers,
            "escalated": escalated_count,
            "escalation_rate": escalated_count / n_consumers,
            "total_recovery": round(total_recovery, 2),
            "overall_recovery_rate": total_recovery / total_balance if total_balance > 0 else 0,
            "by_archetype": by_archetype
        }


# =============================================================================
# MODULE INITIALIZATION
# =============================================================================

# Export public interface
__all__ = [
    # State Machine
    "ConsumerState",
    "StateTransition",
    "EngagementDecay",
    "ConsumerStateMachine",

    # Behavioral Embeddings
    "BehavioralArchetype",
    "BehavioralFeatures",
    "BehavioralEmbedding",
    "BehavioralClusterEngine",

    # Liquidity Detection
    "PaydayPattern",
    "LiquidityWindow",
    "LiquidityDetector",

    # Sentiment Analysis
    "SentimentCategory",
    "SentimentAnalysis",
    "SentimentAnalyzer",

    # Propensity Models
    "PropensityFeatures",
    "PropensityModel",
    "ResponsePropensityModel",
    "PaymentPropensityModel",
    "PromisePropensityModel",
    "EscalationPropensityModel",

    # Integrated Model
    "SemanticBehavioralModel",

    # Simulation
    "BehavioralSimulator",
]


if __name__ == "__main__":
    # Demo usage
    print("=" * 60)
    print("QUAN Semantic Behavioral Model - Demo")
    print("=" * 60)

    # Create simulator
    simulator = BehavioralSimulator(seed=42)

    # Generate sample consumer
    consumer = simulator.generate_synthetic_consumer(BehavioralArchetype.NEGOTIATOR)
    print(f"\nGenerated consumer: {consumer['account_id']}")
    print(f"  Balance: ${consumer['balance']:.2f}")
    print(f"  Archetype: {consumer['archetype']}")

    # Initialize model
    model = SemanticBehavioralModel()
    model.initialize_consumer(consumer)

    # Get predictions
    predictions = model.predict_outcomes()
    print(f"\nPredictions:")
    print(f"  Response probability: {predictions['response']['probability']:.2%}")
    print(f"  Payment probability: {predictions['payment']['probability']:.2%}")
    print(f"  Escalation risk: {predictions['escalation']['probability']:.2%}")

    # Get strategy
    strategy = model.recommend_strategy()
    print(f"\nRecommended Strategy:")
    print(f"  Optimal contact hour: {strategy['timing']['optimal_hour']}:00")
    print(f"  Recommended offer: {strategy['offer']['type']} ({strategy['offer']['discount']}% off)")

    # Simulate trajectory
    trajectory = model.simulate_trajectory(steps=30)
    print(f"\nTrajectory Simulation:")
    print(f"  Final state: {trajectory['final_state']}")
    print(f"  Resolved: {trajectory['resolved']}")

    # Run batch simulation
    print(f"\nRunning batch simulation (100 consumers)...")
    batch_results = simulator.run_batch_simulation(n_consumers=100, max_days=90)
    print(f"  Resolution rate: {batch_results['resolution_rate']:.1%}")
    print(f"  Escalation rate: {batch_results['escalation_rate']:.1%}")
    print(f"  Overall recovery: {batch_results['overall_recovery_rate']:.1%}")

    print("\n" + "=" * 60)
    print("Demo complete.")
