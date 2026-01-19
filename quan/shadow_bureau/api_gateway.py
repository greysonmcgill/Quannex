"""
Shadow Bureau API Gateway - The Integration Layer

Phase 1: The Trojan Horse
- Direct ERP/Accounting integration via API
- Auto-inject debts at 90 days past due
- Zero friction for creditors

Phase 2: The Network Query API
- Real-time consumer creditworthiness checks
- Cross-creditor default intelligence
- "Pay the platform, or get blocked everywhere"
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any
import hashlib
import json
import time


class IntegrationType(Enum):
    """Creditor integration types"""
    REST_API = "rest_api"
    WEBHOOK = "webhook"
    SFTP_BATCH = "sftp_batch"
    DIRECT_DB = "direct_db"
    ERP_PLUGIN = "erp_plugin"


class ERPSystem(Enum):
    """Supported ERP systems"""
    QUICKBOOKS = "quickbooks"
    NETSUITE = "netsuite"
    SAGE = "sage"
    XERO = "xero"
    SAP = "sap"
    STRIPE_BILLING = "stripe"
    CHARGEBEE = "chargebee"
    RECURLY = "recurly"
    CUSTOM = "custom"


class QueryType(Enum):
    """Network query types"""
    SHADOW_SCORE = "shadow_score"        # Get consumer's shadow score
    NETWORK_CHECK = "network_check"      # Check for outstanding debts
    FULL_PROFILE = "full_profile"        # Complete behavioral profile
    RISK_ASSESSMENT = "risk_assessment"  # Underwriting decision support
    RESTORATION_VERIFY = "restoration"   # Verify restoration certificate


@dataclass
class APICredential:
    """Creditor API credentials"""
    creditor_id: str
    api_key_hash: str
    secret_hash: str
    scopes: list[str]
    rate_limit_per_minute: int = 60
    rate_limit_per_day: int = 10000
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime | None = None
    is_active: bool = True


@dataclass
class Integration:
    """Creditor integration configuration"""
    integration_id: str
    creditor_id: str
    integration_type: IntegrationType
    erp_system: ERPSystem | None = None

    # Configuration
    endpoint_url: str | None = None
    webhook_secret: str | None = None
    sync_frequency_hours: int = 24
    auto_placement_enabled: bool = True
    auto_placement_threshold_days: int = 90

    # Mapping
    field_mapping: dict[str, str] = field(default_factory=dict)

    # Status
    is_active: bool = True
    last_sync: datetime | None = None
    accounts_synced: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class APIRequest:
    """Logged API request"""
    request_id: str
    creditor_id: str
    query_type: QueryType
    consumer_id: str | None
    request_params: dict[str, Any]
    response_data: dict[str, Any] | None = None
    latency_ms: int = 0
    status_code: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class WebhookEvent:
    """Webhook event for creditor notifications"""
    event_id: str
    creditor_id: str
    event_type: str
    payload: dict[str, Any]
    delivered: bool = False
    delivery_attempts: int = 0
    last_attempt: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)


class ShadowBureauAPI:
    """
    The Shadow Bureau API Gateway

    Two primary functions:
    1. INGEST: Receive debts from creditors (push or pull)
    2. QUERY: Provide real-time consumer intelligence
    """

    def __init__(self):
        self.credentials: dict[str, APICredential] = {}
        self.integrations: dict[str, Integration] = {}
        self.requests: list[APIRequest] = []
        self.webhooks: list[WebhookEvent] = []
        self.rate_limits: dict[str, list[datetime]] = {}

        # API versioning
        self.current_version = "v1"
        self.supported_versions = ["v1"]

    # =========================================================================
    # AUTHENTICATION & AUTHORIZATION
    # =========================================================================

    def create_credentials(
        self,
        creditor_id: str,
        scopes: list[str] | None = None
    ) -> tuple[str, str]:
        """
        Create API credentials for a creditor

        Returns: (api_key, api_secret)
        """
        import secrets

        api_key = f"quan_live_{secrets.token_hex(16)}"
        api_secret = secrets.token_hex(32)

        cred = APICredential(
            creditor_id=creditor_id,
            api_key_hash=hashlib.sha256(api_key.encode()).hexdigest(),
            secret_hash=hashlib.sha256(api_secret.encode()).hexdigest(),
            scopes=scopes or ["read:score", "read:network", "write:debt"]
        )

        self.credentials[creditor_id] = cred

        return api_key, api_secret

    def authenticate(self, api_key: str, api_secret: str) -> tuple[bool, str | None]:
        """Authenticate API request"""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        secret_hash = hashlib.sha256(api_secret.encode()).hexdigest()

        for creditor_id, cred in self.credentials.items():
            if cred.api_key_hash == key_hash and cred.secret_hash == secret_hash:
                if not cred.is_active:
                    return False, None
                cred.last_used = datetime.now()
                return True, creditor_id

        return False, None

    def check_rate_limit(self, creditor_id: str) -> bool:
        """Check if creditor is within rate limits"""
        cred = self.credentials.get(creditor_id)
        if not cred:
            return False

        now = datetime.now()
        if creditor_id not in self.rate_limits:
            self.rate_limits[creditor_id] = []

        # Clean old entries
        minute_ago = now - timedelta(minutes=1)
        self.rate_limits[creditor_id] = [
            t for t in self.rate_limits[creditor_id] if t > minute_ago
        ]

        if len(self.rate_limits[creditor_id]) >= cred.rate_limit_per_minute:
            return False

        self.rate_limits[creditor_id].append(now)
        return True

    # =========================================================================
    # INTEGRATION SETUP
    # =========================================================================

    def setup_integration(
        self,
        creditor_id: str,
        integration_type: IntegrationType,
        erp_system: ERPSystem | None = None,
        config: dict[str, Any] | None = None
    ) -> Integration:
        """
        Set up creditor integration

        This is the "Trojan Horse" - seamless integration into creditor systems
        """
        integration_id = hashlib.sha256(
            f"{creditor_id}{integration_type.value}{datetime.now()}".encode()
        ).hexdigest()[:16]

        # Default field mappings for common ERPs
        field_mapping = self._get_default_mapping(erp_system)
        if config and "field_mapping" in config:
            field_mapping.update(config["field_mapping"])

        integration = Integration(
            integration_id=integration_id,
            creditor_id=creditor_id,
            integration_type=integration_type,
            erp_system=erp_system,
            endpoint_url=config.get("endpoint_url") if config else None,
            webhook_secret=config.get("webhook_secret") if config else None,
            field_mapping=field_mapping,
            auto_placement_enabled=config.get("auto_placement", True) if config else True,
            auto_placement_threshold_days=config.get("threshold_days", 90) if config else 90
        )

        self.integrations[integration_id] = integration

        return integration

    def _get_default_mapping(self, erp: ERPSystem | None) -> dict[str, str]:
        """Get default field mapping for ERP system"""
        mappings = {
            ERPSystem.STRIPE_BILLING: {
                "consumer_id": "customer.id",
                "email": "customer.email",
                "amount": "invoice.amount_due",
                "currency": "invoice.currency",
                "due_date": "invoice.due_date",
                "description": "invoice.description"
            },
            ERPSystem.QUICKBOOKS: {
                "consumer_id": "Customer.Id",
                "email": "Customer.PrimaryEmailAddr.Address",
                "amount": "Invoice.TotalAmt",
                "due_date": "Invoice.DueDate"
            },
            ERPSystem.CHARGEBEE: {
                "consumer_id": "customer.id",
                "email": "customer.email",
                "amount": "invoice.amount_due",
                "due_date": "invoice.due_date"
            }
        }
        return mappings.get(erp, {})

    # =========================================================================
    # DEBT INGESTION API
    # =========================================================================

    def ingest_debt(
        self,
        creditor_id: str,
        debt_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Ingest a single debt record

        POST /v1/debts
        """
        start_time = time.time()

        required_fields = ["consumer_id", "amount", "charge_off_date"]
        for field in required_fields:
            if field not in debt_data:
                return {
                    "success": False,
                    "error": f"Missing required field: {field}",
                    "status_code": 400
                }

        # Generate record ID
        record_id = hashlib.sha256(
            f"{creditor_id}{debt_data['consumer_id']}{debt_data['charge_off_date']}".encode()
        ).hexdigest()[:16]

        result = {
            "success": True,
            "record_id": record_id,
            "status": "accepted",
            "message": "Debt record accepted for processing"
        }

        # Log request
        self._log_request(
            creditor_id=creditor_id,
            query_type=QueryType.SHADOW_SCORE,  # Using as placeholder
            consumer_id=debt_data.get("consumer_id"),
            request_params={"action": "ingest_debt"},
            response_data=result,
            latency_ms=int((time.time() - start_time) * 1000),
            status_code=201
        )

        return result

    def bulk_ingest(
        self,
        creditor_id: str,
        debts: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Bulk ingest multiple debt records

        POST /v1/debts/bulk
        """
        start_time = time.time()

        results = []
        success_count = 0
        error_count = 0

        for debt in debts:
            result = self.ingest_debt(creditor_id, debt)
            if result["success"]:
                success_count += 1
            else:
                error_count += 1
            results.append(result)

        return {
            "success": True,
            "total_submitted": len(debts),
            "accepted": success_count,
            "rejected": error_count,
            "processing_time_ms": int((time.time() - start_time) * 1000)
        }

    # =========================================================================
    # NETWORK QUERY API
    # =========================================================================

    def query_shadow_score(
        self,
        creditor_id: str,
        consumer_id: str
    ) -> dict[str, Any]:
        """
        Query consumer's Shadow Score

        GET /v1/scores/{consumer_id}

        This is the core monetization endpoint - sold to lenders
        for risk assessment.
        """
        start_time = time.time()

        # In production, this queries the Live Ledger
        # Simulated response
        result = {
            "consumer_id": consumer_id,
            "shadow_score": 625,
            "risk_tier": "B",
            "score_components": {
                "response_score": 72,
                "payment_score": 58,
                "promise_score": 65,
                "velocity_score": 55
            },
            "confidence": 0.85,
            "last_updated": datetime.now().isoformat(),
            "data_freshness_hours": 2
        }

        latency = int((time.time() - start_time) * 1000)

        self._log_request(
            creditor_id=creditor_id,
            query_type=QueryType.SHADOW_SCORE,
            consumer_id=consumer_id,
            request_params={},
            response_data=result,
            latency_ms=latency,
            status_code=200
        )

        return result

    def query_network_check(
        self,
        creditor_id: str,
        consumer_id: str
    ) -> dict[str, Any]:
        """
        Network-wide debt check

        GET /v1/network/{consumer_id}

        THE NETWORK EFFECT: Check if consumer has outstanding debts
        with ANY creditor in the network.
        """
        start_time = time.time()

        # Simulated response
        result = {
            "consumer_id": consumer_id,
            "has_outstanding_debts": True,
            "total_outstanding": 275.50,
            "debt_count": 2,
            "creditors_affected": ["Klarna", "Afterpay"],
            "oldest_debt_days": 67,
            "recommendation": "REVIEW",
            "recommendation_reason": "Outstanding micro-debts in network",
            "network_members_checked": 47
        }

        latency = int((time.time() - start_time) * 1000)

        self._log_request(
            creditor_id=creditor_id,
            query_type=QueryType.NETWORK_CHECK,
            consumer_id=consumer_id,
            request_params={},
            response_data=result,
            latency_ms=latency,
            status_code=200
        )

        return result

    def query_risk_assessment(
        self,
        creditor_id: str,
        consumer_id: str,
        proposed_credit: float
    ) -> dict[str, Any]:
        """
        Full risk assessment for underwriting

        POST /v1/assess

        Used by lenders to make credit decisions in real-time.
        """
        start_time = time.time()

        # Get shadow score and network status
        shadow = self.query_shadow_score(creditor_id, consumer_id)
        network = self.query_network_check(creditor_id, consumer_id)

        # Calculate risk factors
        score_factor = shadow["shadow_score"] / 850
        network_factor = 1.0 if not network["has_outstanding_debts"] else 0.7
        amount_factor = 1.0 if proposed_credit < 200 else 0.8

        approval_probability = score_factor * network_factor * amount_factor

        if approval_probability > 0.7:
            decision = "APPROVE"
            suggested_limit = proposed_credit
        elif approval_probability > 0.5:
            decision = "CONDITIONAL_APPROVE"
            suggested_limit = proposed_credit * 0.5
        else:
            decision = "DECLINE"
            suggested_limit = 0

        result = {
            "consumer_id": consumer_id,
            "proposed_credit": proposed_credit,
            "decision": decision,
            "suggested_limit": suggested_limit,
            "approval_probability": approval_probability,
            "risk_factors": {
                "shadow_score": shadow["shadow_score"],
                "network_status": "clean" if not network["has_outstanding_debts"] else "outstanding",
                "outstanding_amount": network["total_outstanding"]
            },
            "data_sources": ["shadow_bureau", "network_check"],
            "assessment_id": hashlib.sha256(f"{consumer_id}{datetime.now()}".encode()).hexdigest()[:12]
        }

        latency = int((time.time() - start_time) * 1000)

        self._log_request(
            creditor_id=creditor_id,
            query_type=QueryType.RISK_ASSESSMENT,
            consumer_id=consumer_id,
            request_params={"proposed_credit": proposed_credit},
            response_data=result,
            latency_ms=latency,
            status_code=200
        )

        return result

    def verify_restoration(
        self,
        creditor_id: str,
        certificate_id: str
    ) -> dict[str, Any]:
        """
        Verify restoration certificate

        GET /v1/restoration/{certificate_id}

        Used by creditors to verify consumer has resolved debt
        and should have access restored.
        """
        start_time = time.time()

        # Simulated verification
        result = {
            "valid": True,
            "certificate_id": certificate_id,
            "consumer_id": "C12345",
            "resolution_date": (datetime.now() - timedelta(days=7)).isoformat(),
            "resolution_type": "settled",
            "amount_resolved": 147.50,
            "trust_level": "RESTORED",
            "current_shadow_score": 680,
            "recommendation": "RESTORE_STANDARD",
            "expires_at": (datetime.now() + timedelta(days=358)).isoformat()
        }

        latency = int((time.time() - start_time) * 1000)

        self._log_request(
            creditor_id=creditor_id,
            query_type=QueryType.RESTORATION_VERIFY,
            consumer_id=None,
            request_params={"certificate_id": certificate_id},
            response_data=result,
            latency_ms=latency,
            status_code=200
        )

        return result

    # =========================================================================
    # WEBHOOKS
    # =========================================================================

    def register_webhook(
        self,
        creditor_id: str,
        events: list[str],
        endpoint_url: str,
        secret: str
    ) -> dict[str, Any]:
        """Register webhook for real-time notifications"""
        webhook_id = hashlib.sha256(
            f"{creditor_id}{endpoint_url}{datetime.now()}".encode()
        ).hexdigest()[:16]

        return {
            "webhook_id": webhook_id,
            "creditor_id": creditor_id,
            "events": events,
            "endpoint": endpoint_url,
            "status": "active",
            "created_at": datetime.now().isoformat()
        }

    def send_webhook(
        self,
        creditor_id: str,
        event_type: str,
        payload: dict[str, Any]
    ) -> WebhookEvent:
        """Queue webhook for delivery"""
        event_id = hashlib.sha256(
            f"{creditor_id}{event_type}{datetime.now()}".encode()
        ).hexdigest()[:16]

        event = WebhookEvent(
            event_id=event_id,
            creditor_id=creditor_id,
            event_type=event_type,
            payload=payload
        )

        self.webhooks.append(event)
        return event

    # =========================================================================
    # ANALYTICS
    # =========================================================================

    def get_api_analytics(
        self,
        creditor_id: str | None = None
    ) -> dict[str, Any]:
        """Get API usage analytics"""
        if creditor_id:
            requests = [r for r in self.requests if r.creditor_id == creditor_id]
        else:
            requests = self.requests

        if not requests:
            return {"status": "no_data"}

        # Query type breakdown
        by_type: dict[str, int] = {}
        for r in requests:
            t = r.query_type.value
            by_type[t] = by_type.get(t, 0) + 1

        # Average latency
        avg_latency = sum(r.latency_ms for r in requests) / len(requests)

        # Success rate
        success = sum(1 for r in requests if r.status_code == 200)
        success_rate = success / len(requests)

        return {
            "total_requests": len(requests),
            "requests_by_type": by_type,
            "avg_latency_ms": avg_latency,
            "success_rate": success_rate,
            "time_range": {
                "start": min(r.timestamp for r in requests).isoformat(),
                "end": max(r.timestamp for r in requests).isoformat()
            }
        }

    def _log_request(
        self,
        creditor_id: str,
        query_type: QueryType,
        consumer_id: str | None,
        request_params: dict[str, Any],
        response_data: dict[str, Any] | None,
        latency_ms: int,
        status_code: int
    ) -> None:
        """Log API request for analytics"""
        request_id = hashlib.sha256(
            f"{creditor_id}{datetime.now()}{latency_ms}".encode()
        ).hexdigest()[:16]

        request = APIRequest(
            request_id=request_id,
            creditor_id=creditor_id,
            query_type=query_type,
            consumer_id=consumer_id,
            request_params=request_params,
            response_data=response_data,
            latency_ms=latency_ms,
            status_code=status_code
        )

        self.requests.append(request)


# =========================================================================
# API SPECIFICATION (OpenAPI format)
# =========================================================================

OPENAPI_SPEC = """
openapi: 3.0.0
info:
  title: QUAN Shadow Bureau API
  version: 1.0.0
  description: |
    Real-time micro-credit behavioral data and network intelligence.

    ## Authentication
    All requests require API key authentication via headers:
    - X-API-Key: Your API key
    - X-API-Secret: Your API secret

    ## Rate Limits
    - 60 requests per minute
    - 10,000 requests per day

paths:
  /v1/scores/{consumer_id}:
    get:
      summary: Get Shadow Score
      description: Retrieve consumer's behavioral credit score
      parameters:
        - name: consumer_id
          in: path
          required: true
          schema:
            type: string
      responses:
        200:
          description: Shadow score data
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ShadowScore'

  /v1/network/{consumer_id}:
    get:
      summary: Network Check
      description: Check for outstanding debts across network
      parameters:
        - name: consumer_id
          in: path
          required: true
          schema:
            type: string
      responses:
        200:
          description: Network status
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/NetworkCheck'

  /v1/assess:
    post:
      summary: Risk Assessment
      description: Full risk assessment for underwriting decisions
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                consumer_id:
                  type: string
                proposed_credit:
                  type: number
      responses:
        200:
          description: Assessment result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/RiskAssessment'

  /v1/debts:
    post:
      summary: Submit Debt
      description: Submit a debt record for collection
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/DebtRecord'
      responses:
        201:
          description: Debt accepted

  /v1/restoration/{certificate_id}:
    get:
      summary: Verify Restoration
      description: Verify a restoration certificate
      parameters:
        - name: certificate_id
          in: path
          required: true
          schema:
            type: string
      responses:
        200:
          description: Verification result

components:
  schemas:
    ShadowScore:
      type: object
      properties:
        consumer_id:
          type: string
        shadow_score:
          type: integer
          minimum: 300
          maximum: 850
        risk_tier:
          type: string
          enum: [A, B, C, D, F]
        score_components:
          type: object
        confidence:
          type: number

    NetworkCheck:
      type: object
      properties:
        consumer_id:
          type: string
        has_outstanding_debts:
          type: boolean
        total_outstanding:
          type: number
        recommendation:
          type: string
          enum: [APPROVE, REVIEW, DECLINE]

    RiskAssessment:
      type: object
      properties:
        consumer_id:
          type: string
        decision:
          type: string
          enum: [APPROVE, CONDITIONAL_APPROVE, DECLINE]
        suggested_limit:
          type: number
        approval_probability:
          type: number

    DebtRecord:
      type: object
      required:
        - consumer_id
        - amount
        - charge_off_date
      properties:
        consumer_id:
          type: string
        amount:
          type: number
        charge_off_date:
          type: string
          format: date
        category:
          type: string
        description:
          type: string
"""


# Demonstration
if __name__ == "__main__":
    api = ShadowBureauAPI()

    print("=== SHADOW BUREAU API DEMO ===\n")

    # Create credentials
    print("Creating API Credentials...")
    key, secret = api.create_credentials("KLARNA", ["read:score", "read:network", "write:debt"])
    print(f"  API Key: {key[:20]}...")
    print(f"  API Secret: {secret[:20]}...")

    # Authenticate
    success, creditor = api.authenticate(key, secret)
    print(f"\nAuthentication: {'Success' if success else 'Failed'} (Creditor: {creditor})")

    # Set up integration
    print("\nSetting up Stripe Integration...")
    integration = api.setup_integration(
        creditor_id="KLARNA",
        integration_type=IntegrationType.REST_API,
        erp_system=ERPSystem.STRIPE_BILLING,
        config={"auto_placement": True, "threshold_days": 60}
    )
    print(f"  Integration ID: {integration.integration_id}")
    print(f"  Auto-placement: {integration.auto_placement_enabled}")

    # Query Shadow Score
    print("\nQuerying Shadow Score...")
    score = api.query_shadow_score("KLARNA", "C12345")
    print(f"  Shadow Score: {score['shadow_score']}")
    print(f"  Risk Tier: {score['risk_tier']}")

    # Network Check
    print("\nNetwork Check...")
    network = api.query_network_check("KLARNA", "C12345")
    print(f"  Outstanding: ${network['total_outstanding']:.2f}")
    print(f"  Recommendation: {network['recommendation']}")

    # Risk Assessment
    print("\nRisk Assessment for $150 credit...")
    assessment = api.query_risk_assessment("KLARNA", "C12345", 150.0)
    print(f"  Decision: {assessment['decision']}")
    print(f"  Suggested Limit: ${assessment['suggested_limit']:.2f}")
    print(f"  Approval Probability: {assessment['approval_probability']:.1%}")

    # Analytics
    print("\nAPI Analytics:")
    analytics = api.get_api_analytics("KLARNA")
    print(f"  Total Requests: {analytics['total_requests']}")
    print(f"  Avg Latency: {analytics['avg_latency_ms']:.1f}ms")
    print(f"  Success Rate: {analytics['success_rate']:.1%}")
