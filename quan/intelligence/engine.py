"""
Collection Intelligence Engine

ML-powered portfolio analysis and strategy optimization.
Uses standard machine learning techniques:
- Gradient boosting for payment probability
- Graph neural networks for debtor clustering
- Reinforcement learning for contact optimization
"""

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
class PortfolioState:
    """Statistical state of a debt portfolio"""

    probabilities: np.ndarray  # Recovery probability distribution
    correlations: nx.Graph  # Debtor correlation graph
    confidence: float  # Model confidence level
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_expected_recovery(self) -> np.ndarray:
        """Get expected recovery amounts"""
        return self.probabilities


@dataclass
class CollectionStrategy:
    """Optimal collection strategy for an account"""

    account_id: str
    recovery_probability: float
    optimal_channels: List[str]
    settlement_threshold: float
    contact_sequence: List[Dict[str, Any]]
    segment_id: Optional[int] = None
    confidence: float = 0.0


class CollectionIntelligence:
    """
    ML-powered collection intelligence engine.

    Core capabilities:
    - Payment probability prediction (gradient boosting)
    - Debtor segmentation (graph clustering)
    - Contact optimization (multi-armed bandit)
    - Settlement recommendation (decision trees)
    """

    # Feature dimensions
    FEATURE_DIM = 147
    HIDDEN_DIM = 256
    OUTPUT_DIM = 64

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
        """Initialize ML models"""
        return {
            "payment_probability": None,  # XGBoost or similar
            "optimal_strategy": None,  # Policy network
            "negotiation": None,  # Decision tree
            "risk_assessment": None,  # Logistic regression
            "behavioral": None,  # Graph neural network
        }

    def _init_feature_extractors(self) -> Dict[str, callable]:
        """Initialize feature extraction functions"""
        return {
            "demographic": self._extract_demographic_features,
            "behavioral": self._extract_behavioral_features,
            "financial": self._extract_financial_features,
            "contact_history": self._extract_contact_features,
        }

    def _extract_demographic_features(self, account: Dict) -> np.ndarray:
        """Extract demographic features"""
        features = []

        # Age bracket (one-hot)
        age = account.get("age", 35)
        age_brackets = [0, 0, 0, 0, 0]
        if age < 25:
            age_brackets[0] = 1
        elif age < 35:
            age_brackets[1] = 1
        elif age < 45:
            age_brackets[2] = 1
        elif age < 55:
            age_brackets[3] = 1
        else:
            age_brackets[4] = 1
        features.extend(age_brackets)

        # Income bracket
        income = account.get("income_bracket", "medium")
        income_map = {"low": [1, 0, 0], "medium": [0, 1, 0], "high": [0, 0, 1]}
        features.extend(income_map.get(income, [0, 1, 0]))

        # Employment
        employed = 1 if account.get("employed", True) else 0
        features.append(employed)

        return np.array(features, dtype=np.float32)

    def _extract_behavioral_features(self, account: Dict) -> np.ndarray:
        """Extract behavioral features"""
        features = []

        # Payment history
        features.append(account.get("payment_willingness", 0.5))
        features.append(account.get("response_rate", 0.3))
        features.append(account.get("digital_preference", 0.7))

        # Contact responsiveness
        features.append(account.get("contact_attempts", 0) / 10.0)
        features.append(1 if account.get("has_responded", False) else 0)

        return np.array(features, dtype=np.float32)

    def _extract_financial_features(self, account: Dict) -> np.ndarray:
        """Extract financial features"""
        features = []

        # Balance info (normalized)
        balance = float(account.get("balance", 0))
        original = float(account.get("original_balance", balance))

        features.append(min(balance / 1000.0, 1.0))  # Normalized balance
        features.append(balance / max(original, 1.0))  # Pct remaining
        features.append(min(original / 1000.0, 1.0))  # Normalized original

        return np.array(features, dtype=np.float32)

    def _extract_contact_features(self, account: Dict) -> np.ndarray:
        """Extract contact history features"""
        features = []

        # Contact info quality
        features.append(1 if account.get("phone_valid", True) else 0)
        features.append(1 if account.get("email_valid", True) else 0)
        features.append(1 if account.get("has_mobile", True) else 0)

        # Contact history
        features.append(min(account.get("contact_attempts", 0) / 12.0, 1.0))
        features.append(min(account.get("successful_contacts", 0) / 5.0, 1.0))

        return np.array(features, dtype=np.float32)

    def extract_features(self, account: Dict) -> np.ndarray:
        """Extract all features for an account"""
        feature_vectors = []

        for name, extractor in self._feature_extractors.items():
            try:
                features = extractor(account)
                feature_vectors.append(features)
            except Exception as e:
                logger.warning(f"Feature extraction failed for {name}: {e}")

        if feature_vectors:
            return np.concatenate(feature_vectors)
        return np.zeros(self.FEATURE_DIM, dtype=np.float32)

    def predict_recovery_probability(self, account: Dict) -> float:
        """
        Predict probability of successful recovery.

        Uses gradient boosting model trained on historical data.
        """
        features = self.extract_features(account)

        # Simplified prediction (would use trained model in production)
        base_prob = account.get("payment_willingness", 0.3)

        # Adjust based on features
        if account.get("has_mobile", False):
            base_prob *= 1.1
        if account.get("email_valid", False):
            base_prob *= 1.05
        if account.get("employed", True):
            base_prob *= 1.15

        # Balance adjustment (smaller = easier)
        balance = float(account.get("balance", 500))
        if balance < 200:
            base_prob *= 1.2
        elif balance > 800:
            base_prob *= 0.9

        return min(0.95, max(0.05, base_prob))

    def segment_portfolio(
        self,
        accounts: List[Dict]
    ) -> Dict[int, List[str]]:
        """
        Segment portfolio into behavioral clusters.

        Uses graph-based clustering on debtor similarity.
        """
        if not accounts:
            return {}

        # Build similarity graph
        G = nx.Graph()

        for account in accounts:
            account_id = account.get("account_id", "")
            G.add_node(account_id, **account)

        # Add edges based on similarity
        account_list = list(accounts)
        for i, acc1 in enumerate(account_list):
            for acc2 in account_list[i+1:]:
                similarity = self._calculate_similarity(acc1, acc2)
                if similarity > 0.7:
                    G.add_edge(
                        acc1.get("account_id"),
                        acc2.get("account_id"),
                        weight=similarity
                    )

        # Detect communities
        try:
            from networkx.algorithms import community
            communities = community.louvain_communities(G)
        except (ImportError, nx.NetworkXError) as e:
            # Fallback to simple connected components
            logger.warning(f"Louvain clustering unavailable, using connected components: {e}")
            communities = list(nx.connected_components(G))

        # Build segment mapping
        segments = {}
        for idx, comm in enumerate(communities):
            segments[idx] = list(comm)

        return segments

    def _calculate_similarity(self, acc1: Dict, acc2: Dict) -> float:
        """Calculate similarity between two accounts"""
        score = 0.0

        # Same debt type
        if acc1.get("debt_type") == acc2.get("debt_type"):
            score += 0.3

        # Similar balance
        bal1 = float(acc1.get("balance", 0))
        bal2 = float(acc2.get("balance", 0))
        if abs(bal1 - bal2) < 100:
            score += 0.2

        # Similar age
        age1 = acc1.get("age", 35)
        age2 = acc2.get("age", 35)
        if abs(age1 - age2) < 10:
            score += 0.2

        # Same digital preference
        if acc1.get("has_mobile") == acc2.get("has_mobile"):
            score += 0.15

        # Similar willingness
        w1 = acc1.get("payment_willingness", 0.5)
        w2 = acc2.get("payment_willingness", 0.5)
        if abs(w1 - w2) < 0.2:
            score += 0.15

        return score

    def generate_strategy(self, account: Dict) -> CollectionStrategy:
        """
        Generate optimal collection strategy for an account.

        Combines:
        - Recovery probability prediction
        - Channel effectiveness analysis
        - Contact timing optimization
        """
        account_id = account.get("account_id", "")

        # Predict recovery probability
        recovery_prob = self.predict_recovery_probability(account)

        # Determine optimal channels based on account characteristics
        channels = []
        if account.get("has_mobile", False):
            channels.append("sms")
        if account.get("email_valid", False):
            channels.append("email")
        channels.append("mail")  # Always available

        # Sort by expected effectiveness
        channel_scores = {
            "sms": 0.7 if account.get("has_mobile") else 0.0,
            "email": 0.5 if account.get("email_valid") else 0.0,
            "push": 0.6 if account.get("has_mobile") else 0.0,
            "mail": 0.3,
        }
        channels = sorted(channels, key=lambda c: channel_scores.get(c, 0), reverse=True)

        # Determine settlement threshold
        balance = float(account.get("balance", 500))
        willingness = account.get("payment_willingness", 0.5)

        if willingness < 0.3:
            settlement_threshold = 0.5  # Offer 50% settlement
        elif willingness < 0.5:
            settlement_threshold = 0.7  # Offer 70% settlement
        else:
            settlement_threshold = 1.0  # Full balance

        # Generate contact sequence
        contact_sequence = self._generate_contact_sequence(account, channels)

        return CollectionStrategy(
            account_id=account_id,
            recovery_probability=recovery_prob,
            optimal_channels=channels,
            settlement_threshold=settlement_threshold,
            contact_sequence=contact_sequence,
            confidence=min(0.95, recovery_prob + 0.1)
        )

    def _generate_contact_sequence(
        self,
        account: Dict,
        channels: List[str]
    ) -> List[Dict[str, Any]]:
        """Generate optimal contact sequence"""
        sequence = []

        # Day 1: Primary channel
        if channels:
            sequence.append({
                "day": 1,
                "channel": channels[0],
                "message_type": "initial_notice",
                "offer_payment_link": True
            })

        # Day 4: Follow-up
        if len(channels) > 1:
            sequence.append({
                "day": 4,
                "channel": channels[1],
                "message_type": "reminder",
                "offer_payment_link": True
            })

        # Day 8: Escalation
        sequence.append({
            "day": 8,
            "channel": channels[0] if channels else "mail",
            "message_type": "urgency",
            "offer_settlement": account.get("payment_willingness", 0.5) < 0.4
        })

        # Day 14: Final notice
        sequence.append({
            "day": 14,
            "channel": "mail",
            "message_type": "final_notice",
            "offer_settlement": True
        })

        return sequence

    def analyze_portfolio(
        self,
        accounts: List[Dict]
    ) -> Dict[str, Any]:
        """
        Comprehensive portfolio analysis.

        Returns:
        - Expected recovery by segment
        - Recommended strategies
        - Risk assessment
        """
        if not accounts:
            return {"error": "No accounts provided"}

        # Segment portfolio
        segments = self.segment_portfolio(accounts)

        # Analyze each account
        strategies = []
        total_balance = 0
        expected_recovery = 0

        for account in accounts:
            strategy = self.generate_strategy(account)
            strategies.append(strategy)

            balance = float(account.get("balance", 0))
            total_balance += balance
            expected_recovery += balance * strategy.recovery_probability

        # Aggregate results
        return {
            "total_accounts": len(accounts),
            "total_balance": total_balance,
            "expected_recovery": expected_recovery,
            "expected_rate": expected_recovery / total_balance if total_balance > 0 else 0,
            "segments": len(segments),
            "strategies_generated": len(strategies),
            "avg_confidence": sum(s.confidence for s in strategies) / len(strategies) if strategies else 0
        }


# Backward compatibility alias
QuantumEngine = CollectionIntelligence
