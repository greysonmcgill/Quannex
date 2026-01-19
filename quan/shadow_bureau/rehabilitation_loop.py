"""
Rehabilitation Loop - Gamified Credit Restoration System

The "Carrot" to the traditional "Stick" of collections.

Key Innovation: Consumers pay not out of FEAR but to UNLOCK access.
Upon settlement, they receive instant restoration to originating services.

This closes the loop: Debt → Resolution → Restored Access → Future Revenue
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any
import hashlib
import json


class TrustLevel(Enum):
    """Consumer trust level progression"""
    UNTRUSTED = 0       # Default for new/defaulted consumers
    RECOVERING = 1      # Started payment plan
    REBUILDING = 2      # Kept 2+ promises
    RESTORED = 3        # Debt resolved
    TRUSTED = 4         # 90+ days post-resolution, no new issues
    PREMIUM = 5         # High performer, eligible for credit increases


class RestoreStatus(Enum):
    """Service restoration status"""
    BLOCKED = "blocked"
    PENDING = "pending"
    CONDITIONAL = "conditional"
    RESTORED = "restored"
    ENHANCED = "enhanced"


class AchievementType(Enum):
    """Gamification achievements"""
    FIRST_PAYMENT = "first_payment"
    PROMISE_KEEPER = "promise_keeper"
    STREAK_3 = "streak_3"
    STREAK_5 = "streak_5"
    FULL_RESOLUTION = "full_resolution"
    EARLY_RESOLUTION = "early_resolution"
    MULTI_DEBT_CLEAR = "multi_debt_clear"
    RAPID_RESPONSE = "rapid_response"


@dataclass
class TrustScore:
    """
    Proprietary Trust Score - Fed back to merchants in real-time

    This is the "Instant Restoration" mechanism that incentivizes payment.
    """
    consumer_id: str
    current_level: TrustLevel = TrustLevel.UNTRUSTED
    numeric_score: int = 0  # 0-1000

    # Score components
    payment_consistency: float = 0.0  # 0-100
    promise_reliability: float = 0.0  # 0-100
    response_engagement: float = 0.0  # 0-100
    resolution_velocity: float = 0.0  # 0-100

    # Progression tracking
    payments_made: int = 0
    payments_on_time: int = 0
    current_streak: int = 0
    longest_streak: int = 0

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    last_level_change: datetime = field(default_factory=datetime.now)


@dataclass
class Achievement:
    """Gamification achievement"""
    achievement_id: str
    consumer_id: str
    achievement_type: AchievementType
    earned_at: datetime
    display_name: str
    description: str
    points_awarded: int
    badge_icon: str  # URL or icon name


@dataclass
class RestorationCertificate:
    """
    Digital certificate proving debt resolution

    This is sent to the originating creditor via API to
    instantly restore consumer access.
    """
    certificate_id: str
    consumer_id: str
    creditor_id: str
    creditor_name: str

    # Resolution details
    original_debt_amount: float
    resolved_amount: float
    resolution_type: str  # paid_full, settled, payment_plan_complete
    resolution_date: datetime

    # Trust data
    trust_score: int
    trust_level: TrustLevel

    # Verification
    verification_hash: str
    expires_at: datetime
    revocable: bool = False


@dataclass
class ServiceAccess:
    """Consumer access status per creditor/service"""
    consumer_id: str
    creditor_id: str
    service_name: str
    status: RestoreStatus
    conditions: list[str] = field(default_factory=list)
    credit_limit: float | None = None
    access_granted_at: datetime | None = None
    next_review_date: datetime | None = None


class RehabilitationLoop:
    """
    Gamified Credit Rehabilitation System

    The Loop:
    1. Consumer defaults → Trust Score = 0
    2. Consumer enters payment plan → Trust rises
    3. Each payment → Points, achievements, score increase
    4. Resolution → Instant Restoration Certificate issued
    5. Certificate sent to creditor → Access restored
    6. Consumer behavior tracked → Informs future credit decisions
    """

    def __init__(self):
        self.trust_scores: dict[str, TrustScore] = {}
        self.achievements: dict[str, list[Achievement]] = {}
        self.certificates: dict[str, RestorationCertificate] = {}
        self.service_access: dict[str, dict[str, ServiceAccess]] = {}

        # Achievement definitions
        self.achievement_defs = {
            AchievementType.FIRST_PAYMENT: {
                "name": "First Step",
                "description": "Made your first payment",
                "points": 50,
                "icon": "step_forward"
            },
            AchievementType.PROMISE_KEEPER: {
                "name": "Promise Keeper",
                "description": "Kept a payment promise",
                "points": 75,
                "icon": "handshake"
            },
            AchievementType.STREAK_3: {
                "name": "On a Roll",
                "description": "3 on-time payments in a row",
                "points": 100,
                "icon": "fire_3"
            },
            AchievementType.STREAK_5: {
                "name": "Consistency Champion",
                "description": "5 on-time payments in a row",
                "points": 200,
                "icon": "trophy"
            },
            AchievementType.FULL_RESOLUTION: {
                "name": "Debt Free",
                "description": "Fully resolved a debt",
                "points": 500,
                "icon": "checkmark_circle"
            },
            AchievementType.EARLY_RESOLUTION: {
                "name": "Speed Demon",
                "description": "Resolved debt ahead of schedule",
                "points": 250,
                "icon": "lightning"
            },
            AchievementType.MULTI_DEBT_CLEAR: {
                "name": "Clean Slate",
                "description": "Resolved multiple debts",
                "points": 750,
                "icon": "star"
            },
            AchievementType.RAPID_RESPONSE: {
                "name": "Quick Responder",
                "description": "Responded within 1 hour",
                "points": 25,
                "icon": "clock"
            }
        }

    def initialize_consumer(self, consumer_id: str) -> TrustScore:
        """Initialize trust score for a new defaulted consumer"""
        score = TrustScore(consumer_id=consumer_id)
        self.trust_scores[consumer_id] = score
        self.achievements[consumer_id] = []
        self.service_access[consumer_id] = {}
        return score

    def record_payment(
        self,
        consumer_id: str,
        amount: float,
        on_time: bool,
        resolves_debt: bool = False,
        creditor_id: str | None = None
    ) -> dict[str, Any]:
        """
        Record a payment and update trust score

        Returns achievements earned and new status
        """
        if consumer_id not in self.trust_scores:
            self.initialize_consumer(consumer_id)

        score = self.trust_scores[consumer_id]
        new_achievements = []

        # Update payment tracking
        score.payments_made += 1
        if on_time:
            score.payments_on_time += 1
            score.current_streak += 1
            score.longest_streak = max(score.longest_streak, score.current_streak)
        else:
            score.current_streak = 0

        # Check for achievements
        if score.payments_made == 1:
            ach = self._award_achievement(consumer_id, AchievementType.FIRST_PAYMENT)
            new_achievements.append(ach)

        if on_time and score.current_streak == 3:
            ach = self._award_achievement(consumer_id, AchievementType.STREAK_3)
            new_achievements.append(ach)

        if on_time and score.current_streak == 5:
            ach = self._award_achievement(consumer_id, AchievementType.STREAK_5)
            new_achievements.append(ach)

        if resolves_debt:
            ach = self._award_achievement(consumer_id, AchievementType.FULL_RESOLUTION)
            new_achievements.append(ach)

        # Recalculate scores
        self._recalculate_trust_score(consumer_id)

        # Update trust level
        old_level = score.current_level
        new_level = self._determine_trust_level(score)
        if new_level != old_level:
            score.current_level = new_level
            score.last_level_change = datetime.now()

        score.last_updated = datetime.now()

        return {
            "consumer_id": consumer_id,
            "trust_score": score.numeric_score,
            "trust_level": score.current_level.name,
            "level_changed": new_level != old_level,
            "current_streak": score.current_streak,
            "new_achievements": [a.display_name for a in new_achievements],
            "total_points": sum(a.points_awarded for a in self.achievements.get(consumer_id, []))
        }

    def issue_restoration_certificate(
        self,
        consumer_id: str,
        creditor_id: str,
        creditor_name: str,
        original_amount: float,
        resolved_amount: float,
        resolution_type: str
    ) -> RestorationCertificate:
        """
        Issue restoration certificate upon debt resolution

        This certificate is the "key" that unlocks access restoration
        """
        score = self.trust_scores.get(consumer_id)
        if not score:
            score = self.initialize_consumer(consumer_id)

        cert_id = hashlib.sha256(
            f"{consumer_id}{creditor_id}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:24]

        # Generate verification hash
        verification_data = f"{cert_id}{consumer_id}{creditor_id}{resolved_amount}{resolution_type}"
        verification_hash = hashlib.sha256(verification_data.encode()).hexdigest()

        certificate = RestorationCertificate(
            certificate_id=cert_id,
            consumer_id=consumer_id,
            creditor_id=creditor_id,
            creditor_name=creditor_name,
            original_debt_amount=original_amount,
            resolved_amount=resolved_amount,
            resolution_type=resolution_type,
            resolution_date=datetime.now(),
            trust_score=score.numeric_score,
            trust_level=score.current_level,
            verification_hash=verification_hash,
            expires_at=datetime.now() + timedelta(days=365)
        )

        self.certificates[cert_id] = certificate

        # Update service access
        self._update_service_access(
            consumer_id,
            creditor_id,
            creditor_name,
            RestoreStatus.RESTORED,
            certificate
        )

        return certificate

    def get_consumer_dashboard(self, consumer_id: str) -> dict[str, Any]:
        """
        Get consumer-facing rehabilitation dashboard

        Designed to motivate continued engagement
        """
        score = self.trust_scores.get(consumer_id)
        if not score:
            return {"status": "not_found"}

        achievements = self.achievements.get(consumer_id, [])
        services = self.service_access.get(consumer_id, {})

        # Calculate next level requirements
        next_level = self._get_next_level_requirements(score)

        return {
            "trust_score": score.numeric_score,
            "trust_level": score.current_level.name,
            "level_display": self._get_level_display(score.current_level),

            # Progress visualization
            "progress_to_next_level": next_level["progress_percent"],
            "points_to_next_level": next_level["points_needed"],
            "next_level_benefits": next_level["benefits"],

            # Streak and consistency
            "current_streak": score.current_streak,
            "longest_streak": score.longest_streak,
            "payments_on_time_rate": (
                score.payments_on_time / score.payments_made * 100
                if score.payments_made > 0 else 0
            ),

            # Achievements
            "total_achievements": len(achievements),
            "total_points": sum(a.points_awarded for a in achievements),
            "recent_achievements": [
                {
                    "name": a.display_name,
                    "description": a.description,
                    "points": a.points_awarded,
                    "earned": a.earned_at.isoformat()
                }
                for a in sorted(achievements, key=lambda x: x.earned_at, reverse=True)[:5]
            ],

            # Service access
            "services": [
                {
                    "name": s.service_name,
                    "status": s.status.value,
                    "conditions": s.conditions
                }
                for s in services.values()
            ],

            # Motivational messaging
            "motivational_message": self._get_motivational_message(score)
        }

    def verify_certificate(self, certificate_id: str) -> dict[str, Any]:
        """
        Verify restoration certificate (API endpoint for creditors)

        Creditors call this to validate a consumer's restoration status
        """
        cert = self.certificates.get(certificate_id)
        if not cert:
            return {"valid": False, "reason": "certificate_not_found"}

        if datetime.now() > cert.expires_at:
            return {"valid": False, "reason": "certificate_expired"}

        # Re-verify hash
        verification_data = f"{cert.certificate_id}{cert.consumer_id}{cert.creditor_id}{cert.resolved_amount}{cert.resolution_type}"
        expected_hash = hashlib.sha256(verification_data.encode()).hexdigest()

        if expected_hash != cert.verification_hash:
            return {"valid": False, "reason": "verification_failed"}

        # Get current trust score
        current_score = self.trust_scores.get(cert.consumer_id)

        return {
            "valid": True,
            "certificate_id": cert.certificate_id,
            "consumer_id": cert.consumer_id,
            "creditor_verified": cert.creditor_id,
            "resolution_date": cert.resolution_date.isoformat(),
            "resolution_type": cert.resolution_type,
            "amount_resolved": cert.resolved_amount,
            "trust_score_at_resolution": cert.trust_score,
            "current_trust_score": current_score.numeric_score if current_score else None,
            "trust_level": cert.trust_level.name,
            "recommendation": self._get_restoration_recommendation(cert, current_score)
        }

    def _award_achievement(
        self,
        consumer_id: str,
        achievement_type: AchievementType
    ) -> Achievement:
        """Award an achievement to a consumer"""
        defn = self.achievement_defs[achievement_type]

        achievement_id = hashlib.sha256(
            f"{consumer_id}{achievement_type.value}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        achievement = Achievement(
            achievement_id=achievement_id,
            consumer_id=consumer_id,
            achievement_type=achievement_type,
            earned_at=datetime.now(),
            display_name=defn["name"],
            description=defn["description"],
            points_awarded=defn["points"],
            badge_icon=defn["icon"]
        )

        if consumer_id not in self.achievements:
            self.achievements[consumer_id] = []
        self.achievements[consumer_id].append(achievement)

        return achievement

    def _recalculate_trust_score(self, consumer_id: str) -> None:
        """Recalculate trust score components"""
        score = self.trust_scores.get(consumer_id)
        if not score:
            return

        # Payment consistency (weight: 40%)
        if score.payments_made > 0:
            score.payment_consistency = (score.payments_on_time / score.payments_made) * 100
        else:
            score.payment_consistency = 0

        # Promise reliability (weight: 30%) - derived from streak
        streak_factor = min(score.current_streak / 5, 1.0)  # Cap at 5
        score.promise_reliability = streak_factor * 100

        # Response engagement (weight: 15%) - placeholder
        score.response_engagement = 50 + (score.payments_made * 5)
        score.response_engagement = min(score.response_engagement, 100)

        # Resolution velocity (weight: 15%) - placeholder
        score.resolution_velocity = 50

        # Calculate numeric score (0-1000)
        score.numeric_score = int(
            score.payment_consistency * 4.0 +
            score.promise_reliability * 3.0 +
            score.response_engagement * 1.5 +
            score.resolution_velocity * 1.5
        )

        # Add achievement bonus
        total_points = sum(a.points_awarded for a in self.achievements.get(consumer_id, []))
        score.numeric_score += min(total_points // 10, 100)  # Cap bonus at 100

        score.numeric_score = min(1000, score.numeric_score)

    def _determine_trust_level(self, score: TrustScore) -> TrustLevel:
        """Determine trust level based on score"""
        if score.numeric_score >= 900:
            return TrustLevel.PREMIUM
        elif score.numeric_score >= 750:
            return TrustLevel.TRUSTED
        elif score.numeric_score >= 500:
            return TrustLevel.RESTORED
        elif score.numeric_score >= 300:
            return TrustLevel.REBUILDING
        elif score.numeric_score >= 100:
            return TrustLevel.RECOVERING
        else:
            return TrustLevel.UNTRUSTED

    def _get_level_display(self, level: TrustLevel) -> dict[str, str]:
        """Get display info for trust level"""
        displays = {
            TrustLevel.UNTRUSTED: {"name": "Getting Started", "color": "#DC2626", "icon": "alert"},
            TrustLevel.RECOVERING: {"name": "On the Path", "color": "#F59E0B", "icon": "walking"},
            TrustLevel.REBUILDING: {"name": "Building Momentum", "color": "#EAB308", "icon": "hammer"},
            TrustLevel.RESTORED: {"name": "Restored", "color": "#22C55E", "icon": "checkmark"},
            TrustLevel.TRUSTED: {"name": "Trusted Member", "color": "#3B82F6", "icon": "star"},
            TrustLevel.PREMIUM: {"name": "Premium Status", "color": "#8B5CF6", "icon": "crown"}
        }
        return displays.get(level, displays[TrustLevel.UNTRUSTED])

    def _get_next_level_requirements(self, score: TrustScore) -> dict[str, Any]:
        """Get requirements for next trust level"""
        thresholds = {
            TrustLevel.UNTRUSTED: (100, TrustLevel.RECOVERING),
            TrustLevel.RECOVERING: (300, TrustLevel.REBUILDING),
            TrustLevel.REBUILDING: (500, TrustLevel.RESTORED),
            TrustLevel.RESTORED: (750, TrustLevel.TRUSTED),
            TrustLevel.TRUSTED: (900, TrustLevel.PREMIUM),
            TrustLevel.PREMIUM: (1000, TrustLevel.PREMIUM)
        }

        target_score, next_level = thresholds[score.current_level]
        points_needed = max(0, target_score - score.numeric_score)
        progress = min(100, (score.numeric_score / target_score) * 100) if target_score > 0 else 100

        benefits = {
            TrustLevel.RECOVERING: ["Start rebuilding your profile"],
            TrustLevel.REBUILDING: ["Visible progress to creditors"],
            TrustLevel.RESTORED: ["Full service restoration", "Access to credit"],
            TrustLevel.TRUSTED: ["Priority service", "Higher limits"],
            TrustLevel.PREMIUM: ["Premium rates", "Instant approvals"]
        }

        return {
            "next_level": next_level.name,
            "points_needed": points_needed,
            "progress_percent": progress,
            "benefits": benefits.get(next_level, [])
        }

    def _get_motivational_message(self, score: TrustScore) -> str:
        """Generate motivational message based on current status"""
        if score.current_streak >= 5:
            return "Amazing! Your consistency is paying off. Keep it up!"
        elif score.current_streak >= 3:
            return "Great streak! Just 2 more payments to unlock a bonus achievement."
        elif score.current_level == TrustLevel.RESTORED:
            return "Congratulations on your restored status! Maintain it to unlock premium benefits."
        elif score.payments_made == 0:
            return "Take the first step today. Your first payment unlocks an achievement!"
        else:
            return "Every payment brings you closer to full restoration. You've got this!"

    def _update_service_access(
        self,
        consumer_id: str,
        creditor_id: str,
        service_name: str,
        status: RestoreStatus,
        certificate: RestorationCertificate | None
    ) -> None:
        """Update service access status"""
        if consumer_id not in self.service_access:
            self.service_access[consumer_id] = {}

        access = ServiceAccess(
            consumer_id=consumer_id,
            creditor_id=creditor_id,
            service_name=service_name,
            status=status,
            access_granted_at=datetime.now() if status == RestoreStatus.RESTORED else None,
            next_review_date=datetime.now() + timedelta(days=90)
        )

        if certificate and certificate.trust_level in [TrustLevel.TRUSTED, TrustLevel.PREMIUM]:
            access.status = RestoreStatus.ENHANCED
            access.credit_limit = 500.0  # Higher limit for trusted users

        self.service_access[consumer_id][creditor_id] = access

    def _get_restoration_recommendation(
        self,
        cert: RestorationCertificate,
        current_score: TrustScore | None
    ) -> str:
        """Generate restoration recommendation for creditor"""
        if not current_score:
            return "RESTORE_STANDARD"

        if current_score.current_level == TrustLevel.PREMIUM:
            return "RESTORE_PREMIUM_FULL_ACCESS"
        elif current_score.current_level == TrustLevel.TRUSTED:
            return "RESTORE_ENHANCED_LIMIT"
        elif current_score.current_level == TrustLevel.RESTORED:
            return "RESTORE_STANDARD"
        elif current_score.current_level == TrustLevel.REBUILDING:
            return "RESTORE_CONDITIONAL"
        else:
            return "RESTORE_LIMITED"


# Demonstration
if __name__ == "__main__":
    loop = RehabilitationLoop()

    print("=== REHABILITATION LOOP DEMO ===\n")

    # Initialize consumer
    consumer_id = "C001"
    loop.initialize_consumer(consumer_id)

    # Simulate payment journey
    print("Payment Journey:")
    for i in range(1, 6):
        result = loop.record_payment(
            consumer_id=consumer_id,
            amount=25.0,
            on_time=True,
            resolves_debt=(i == 5)
        )
        print(f"  Payment {i}: Score={result['trust_score']}, Level={result['trust_level']}, Streak={result['current_streak']}")
        if result['new_achievements']:
            print(f"    Achievements: {result['new_achievements']}")

    # Issue restoration certificate
    print("\nIssuing Restoration Certificate...")
    cert = loop.issue_restoration_certificate(
        consumer_id=consumer_id,
        creditor_id="KLARNA",
        creditor_name="Klarna",
        original_amount=147.50,
        resolved_amount=125.00,
        resolution_type="settled"
    )
    print(f"  Certificate ID: {cert.certificate_id}")
    print(f"  Trust Level: {cert.trust_level.name}")

    # Verify certificate
    print("\nVerifying Certificate...")
    verification = loop.verify_certificate(cert.certificate_id)
    print(f"  Valid: {verification['valid']}")
    print(f"  Recommendation: {verification['recommendation']}")

    # Get dashboard
    print("\nConsumer Dashboard:")
    dashboard = loop.get_consumer_dashboard(consumer_id)
    print(f"  Trust Score: {dashboard['trust_score']}")
    print(f"  Trust Level: {dashboard['trust_level']}")
    print(f"  Total Achievements: {dashboard['total_achievements']}")
    print(f"  Total Points: {dashboard['total_points']}")
    print(f"  Message: {dashboard['motivational_message']}")
