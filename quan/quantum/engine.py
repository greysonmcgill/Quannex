"""Core quantum-inspired intelligence system"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
import networkx as nx
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Conditional torch import
try:
    import torch
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available, using NumPy fallback")


@dataclass
class QuantumState:
    """Represents quantum state of a debt portfolio"""

    superposition: np.ndarray  # Probability amplitudes
    entanglement: nx.Graph  # Correlation graph
    coherence: float  # System coherence level
    metadata: Dict[str, Any] = field(default_factory=dict)

    def collapse(self) -> np.ndarray:
        """Collapse superposition to classical probabilities"""
        return np.abs(self.superposition) ** 2


@dataclass
class CollectionStrategy:
    """Optimal collection strategy for an account"""

    account_id: str
    recovery_probability: float
    optimal_channels: List[str]
    settlement_authority: float
    contact_sequence: List[Dict[str, Any]]
    cluster_id: Optional[int] = None
    confidence: float = 0.0


class QuantumEngine:
    """Core quantum-inspired intelligence system for portfolio analysis"""

    # Feature dimensions
    FEATURE_DIM = 147
    HIDDEN_DIM = 256
    STATE_DIM = 64

    def __init__(self):
        self.device = self._get_device()
        self.models = self._initialize_models()
        self._feature_extractors = self._init_feature_extractors()

    def _get_device(self) -> str:
        """Get compute device"""
        if TORCH_AVAILABLE and torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def _initialize_models(self) -> Dict[str, Any]:
        """Initialize all ML models"""
        # Models would be loaded from registry in production
        return {
            "payment_probability": None,
            "optimal_strategy": None,
            "negotiation": None,
            "risk_assessment": None,
            "behavioral": None,
        }

    def _init_feature_extractors(self) -> Dict[str, callable]:
        """Initialize feature extraction functions"""
        return {
            "balance_features": self._extract_balance_features,
            "temporal_features": self._extract_temporal_features,
            "behavioral_features": self._extract_behavioral_features,
            "demographic_features": self._extract_demographic_features,
            "contact_features": self._extract_contact_features,
        }

    def quantum_analyze(self, portfolio: List[Dict]) -> QuantumState:
        """
        Apply quantum-inspired analysis to portfolio.
        Analyzes all accounts simultaneously as entangled system.
        """
        if not portfolio:
            return QuantumState(
                superposition=np.array([]),
                entanglement=nx.Graph(),
                coherence=0.0,
            )

        logger.info(f"Quantum analyzing portfolio of {len(portfolio)} accounts")

        # Create superposition of all possible recovery states
        superposition = self._create_superposition(portfolio)

        # Build entanglement graph (correlations between accounts)
        entanglement_graph = self._build_entanglement(portfolio)

        # Apply quantum gates (transformations)
        transformed = self._apply_quantum_gates(superposition, entanglement_graph)

        # Measure coherence (system stability)
        coherence = self._measure_coherence(transformed)

        return QuantumState(
            superposition=transformed,
            entanglement=entanglement_graph,
            coherence=coherence,
            metadata={
                "n_accounts": len(portfolio),
                "analyzed_at": datetime.utcnow().isoformat(),
            },
        )

    def _create_superposition(self, portfolio: List[Dict]) -> np.ndarray:
        """Create quantum superposition of recovery states"""

        n_accounts = len(portfolio)
        # Limit states for computational feasibility
        n_states = 2 ** min(n_accounts, 10)

        # Initialize probability amplitudes
        amplitudes = np.zeros((n_accounts, n_states), dtype=complex)

        for i, account in enumerate(portfolio):
            # Extract features
            features = self._extract_features(account)

            # Calculate probability amplitude for each possible state
            # Using sigmoid of feature dot product as base probability
            base_prob = self._calculate_base_probability(features)

            # Create superposition of pay/no-pay states
            pay_amplitude = np.sqrt(base_prob) * np.exp(1j * np.random.uniform(0, 2 * np.pi))
            no_pay_amplitude = np.sqrt(1 - base_prob)

            # Distribute across state space
            for j in range(n_states):
                bit = (j >> (i % 10)) & 1
                if bit:
                    amplitudes[i, j] = pay_amplitude
                else:
                    amplitudes[i, j] = no_pay_amplitude

        # Normalize
        norm = np.linalg.norm(amplitudes)
        if norm > 0:
            amplitudes = amplitudes / norm

        return amplitudes

    def _build_entanglement(self, portfolio: List[Dict]) -> nx.Graph:
        """Build correlation graph between accounts"""

        G = nx.Graph()

        for i, account_i in enumerate(portfolio):
            G.add_node(i, **{
                "account_id": account_i.get("account_id"),
                "balance": account_i.get("balance", 0),
            })

            for j, account_j in enumerate(portfolio[i + 1:], i + 1):
                # Calculate entanglement strength based on correlations
                correlation = self._calculate_correlation(account_i, account_j)

                if correlation > 0.3:  # Threshold for meaningful correlation
                    G.add_edge(i, j, weight=correlation)

        return G

    def _calculate_correlation(self, account_i: Dict, account_j: Dict) -> float:
        """Calculate correlation between two accounts"""

        score = 0.0

        # Same creditor
        if account_i.get("original_creditor") == account_j.get("original_creditor"):
            score += 0.3

        # Similar balance range
        bal_i = account_i.get("balance", 0)
        bal_j = account_j.get("balance", 0)
        if bal_i > 0 and bal_j > 0:
            ratio = min(bal_i, bal_j) / max(bal_i, bal_j)
            score += 0.2 * ratio

        # Similar days overdue
        days_i = account_i.get("days_overdue", 0)
        days_j = account_j.get("days_overdue", 0)
        if days_i > 0 and days_j > 0:
            ratio = min(days_i, days_j) / max(days_i, days_j)
            score += 0.2 * ratio

        # Same state
        if account_i.get("debtor_state") == account_j.get("debtor_state"):
            score += 0.15

        # Same source type
        if account_i.get("source_type") == account_j.get("source_type"):
            score += 0.15

        return min(score, 1.0)

    def _apply_quantum_gates(
        self,
        superposition: np.ndarray,
        entanglement: nx.Graph,
    ) -> np.ndarray:
        """Apply quantum gate operations to superposition"""

        if superposition.size == 0:
            return superposition

        # Hadamard-like mixing
        n_accounts, n_states = superposition.shape
        mixed = superposition.copy()

        # Apply entanglement-weighted phase shifts
        for i, j, data in entanglement.edges(data=True):
            weight = data.get("weight", 0)
            if i < n_accounts and j < n_accounts:
                # Controlled phase gate
                phase = np.exp(1j * np.pi * weight)
                mixed[i] *= phase
                mixed[j] *= np.conj(phase)

        # Apply amplitude amplification (Grover-like)
        mean_amplitude = np.mean(mixed)
        mixed = 2 * mean_amplitude - mixed

        # Normalize
        norm = np.linalg.norm(mixed)
        if norm > 0:
            mixed = mixed / norm

        return mixed

    def _measure_coherence(self, superposition: np.ndarray) -> float:
        """Measure quantum coherence of the system"""

        if superposition.size == 0:
            return 0.0

        # Calculate purity (tr(rho^2))
        probabilities = np.abs(superposition) ** 2
        purity = np.sum(probabilities ** 2)

        # Normalize to [0, 1]
        coherence = min(purity * superposition.shape[0], 1.0)

        return float(coherence)

    def collapse_to_strategy(self, quantum_state: QuantumState) -> List[CollectionStrategy]:
        """Collapse quantum state to optimal collection strategies"""

        if quantum_state.superposition.size == 0:
            return []

        # Perform quantum measurement (collapse superposition)
        probabilities = quantum_state.collapse()

        # Average across states to get per-account probabilities
        account_probs = np.mean(probabilities, axis=1)

        strategies = []

        # Use entanglement to identify account clusters
        try:
            clusters = list(nx.community.louvain_communities(quantum_state.entanglement))
        except Exception:
            # Fallback: each account is its own cluster
            clusters = [{i} for i in range(len(account_probs))]

        for cluster_id, cluster in enumerate(clusters):
            cluster_strategy = self._optimize_cluster_strategy(
                cluster,
                quantum_state,
                account_probs,
            )

            for account_idx in cluster:
                if account_idx < len(account_probs):
                    node_data = quantum_state.entanglement.nodes.get(account_idx, {})
                    prob = float(account_probs[account_idx])

                    strategies.append(CollectionStrategy(
                        account_id=node_data.get("account_id", str(account_idx)),
                        recovery_probability=prob,
                        optimal_channels=cluster_strategy["channels"],
                        settlement_authority=cluster_strategy["settlement"],
                        contact_sequence=cluster_strategy["sequence"],
                        cluster_id=cluster_id,
                        confidence=quantum_state.coherence,
                    ))

        return strategies

    def _optimize_cluster_strategy(
        self,
        cluster: set,
        quantum_state: QuantumState,
        probabilities: np.ndarray,
    ) -> Dict[str, Any]:
        """Optimize strategy for account cluster"""

        # Calculate cluster average probability
        cluster_probs = [probabilities[i] for i in cluster if i < len(probabilities)]
        avg_prob = np.mean(cluster_probs) if cluster_probs else 0.5

        # Determine optimal channels based on probability
        if avg_prob > 0.6:
            channels = ["sms", "email"]
            settlement = 0.7  # Minimal discount for high probability
            urgency = "low"
        elif avg_prob > 0.3:
            channels = ["sms", "email", "voice"]
            settlement = 0.5  # Moderate discount
            urgency = "medium"
        else:
            channels = ["email", "mail"]
            settlement = 0.3  # Deep discount for low probability
            urgency = "high"

        # Generate contact sequence
        sequence = self._generate_contact_sequence(channels, urgency)

        return {
            "channels": channels,
            "settlement": settlement,
            "sequence": sequence,
            "urgency": urgency,
        }

    def _generate_contact_sequence(
        self,
        channels: List[str],
        urgency: str,
    ) -> List[Dict[str, Any]]:
        """Generate optimal contact sequence"""

        delays = {"low": 72, "medium": 48, "high": 24}  # hours
        delay = delays.get(urgency, 48)

        sequence = []
        for i, channel in enumerate(channels):
            sequence.append({
                "step": i + 1,
                "channel": channel,
                "delay_hours": delay * i,
                "template": f"{channel}_collection_{urgency}",
            })

        return sequence

    def _extract_features(self, account: Dict) -> np.ndarray:
        """Extract feature vector from account"""

        features = []

        for extractor in self._feature_extractors.values():
            features.extend(extractor(account))

        # Pad or truncate to fixed dimension
        features = features[:self.FEATURE_DIM]
        while len(features) < self.FEATURE_DIM:
            features.append(0.0)

        return np.array(features, dtype=np.float32)

    def _extract_balance_features(self, account: Dict) -> List[float]:
        """Extract balance-related features"""
        balance = account.get("balance", 0)
        original = account.get("original_amount", balance)

        return [
            balance / 1000,  # Normalized balance
            np.log1p(balance),  # Log balance
            balance / max(original, 1),  # Balance ratio
            1 if balance < 500 else 0,  # Micro-debt flag
            1 if balance < 100 else 0,  # Ultra-micro flag
        ]

    def _extract_temporal_features(self, account: Dict) -> List[float]:
        """Extract time-related features"""
        days_overdue = account.get("days_overdue", 0)

        return [
            days_overdue / 365,  # Normalized days
            np.log1p(days_overdue),  # Log days
            1 if days_overdue < 30 else 0,  # Fresh
            1 if days_overdue < 90 else 0,  # Recent
            1 if days_overdue > 365 else 0,  # Stale
        ]

    def _extract_behavioral_features(self, account: Dict) -> List[float]:
        """Extract behavioral features"""
        return [
            account.get("previous_payments", 0) / 10,
            account.get("contact_attempts", 0) / 20,
            account.get("response_rate", 0),
            1 if account.get("has_email") else 0,
            1 if account.get("has_phone") else 0,
        ]

    def _extract_demographic_features(self, account: Dict) -> List[float]:
        """Extract demographic features"""
        return [
            account.get("credit_score", 600) / 850,
            account.get("income_estimate", 50000) / 100000,
            1 if account.get("employed") else 0,
            1 if account.get("homeowner") else 0,
        ]

    def _extract_contact_features(self, account: Dict) -> List[float]:
        """Extract contact-related features"""
        return [
            1 if account.get("phone_valid") else 0,
            1 if account.get("email_valid") else 0,
            1 if account.get("address_valid") else 0,
            account.get("contact_score", 0.5),
        ]

    def _calculate_base_probability(self, features: np.ndarray) -> float:
        """Calculate base recovery probability from features"""

        # Simple logistic model (would be ML model in production)
        # Key features: balance, days overdue, contact quality
        balance_norm = features[0] if len(features) > 0 else 0.5
        days_norm = features[5] if len(features) > 5 else 0.5
        contact_score = features[18] if len(features) > 18 else 0.5

        # Weighted combination
        logit = -1.0 + 0.5 * (1 - balance_norm) + 0.3 * (1 - days_norm) + 0.8 * contact_score

        # Sigmoid
        prob = 1 / (1 + np.exp(-logit))

        return float(np.clip(prob, 0.01, 0.99))
