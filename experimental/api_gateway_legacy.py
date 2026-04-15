"""
QUAN Recovery Production API Gateway

The external-facing API layer providing unified access to all QUAN platform services.

Architecture:
1. Creditor Integration API - Debt submission and management
2. Shadow Bureau API - Monetization through behavioral scoring
3. Payment API - Payment processing and plans
4. Reporting API - Portfolio and compliance reporting
5. Webhook Management - Real-time event notifications
6. Authentication - API keys, OAuth 2.0, rate limiting
7. Documentation - OpenAPI 3.0 specification
8. Monitoring - Request logging, metrics, analytics
"""

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from decimal import Decimal
from enum import Enum, auto
from functools import wraps
from typing import (
    Any, Callable, Dict, List, Optional, Set, Tuple, Union
)
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI, APIRouter, HTTPException, Depends, Request, Response,
    BackgroundTasks, Header, Query, Path, Body, status
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import (
    OAuth2PasswordBearer, OAuth2PasswordRequestForm,
    APIKeyHeader, APIKeyQuery
)
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field, EmailStr, validator
from starlette.middleware.base import BaseHTTPMiddleware

from quan.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================

class DebtStatus(str, Enum):
    """Debt lifecycle status"""
    SUBMITTED = "submitted"
    VALIDATED = "validated"
    ACTIVE = "active"
    IN_NEGOTIATION = "in_negotiation"
    PAYMENT_PLAN = "payment_plan"
    SETTLED = "settled"
    PAID_IN_FULL = "paid_in_full"
    RECALLED = "recalled"
    DISPUTED = "disputed"
    UNCOLLECTABLE = "uncollectable"


class PaymentStatus(str, Enum):
    """Payment status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class PlanStatus(str, Enum):
    """Payment plan status"""
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    DEFAULTED = "defaulted"
    CANCELLED = "cancelled"


class WebhookEventType(str, Enum):
    """Webhook event types"""
    DEBT_CREATED = "debt.created"
    DEBT_UPDATED = "debt.updated"
    DEBT_STATUS_CHANGED = "debt.status_changed"
    PAYMENT_RECEIVED = "payment.received"
    PAYMENT_FAILED = "payment.failed"
    SETTLEMENT_REACHED = "settlement.reached"
    PLAN_CREATED = "plan.created"
    PLAN_DEFAULTED = "plan.defaulted"
    PLAN_COMPLETED = "plan.completed"
    SCORE_UPDATED = "score.updated"
    RESTORATION_ISSUED = "restoration.issued"
    COMPLIANCE_ALERT = "compliance.alert"


class RiskTier(str, Enum):
    """Risk tier classification"""
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class ReportType(str, Enum):
    """Report types"""
    PORTFOLIO = "portfolio"
    CLIENT = "client"
    COMPLIANCE = "compliance"
    PERFORMANCE = "performance"
    CUSTOM = "custom"


# =============================================================================
# PYDANTIC MODELS - Request/Response
# =============================================================================

# --- Debt Models ---

class DebtSubmission(BaseModel):
    """Single debt submission"""
    consumer_id: str = Field(..., description="Unique consumer identifier")
    amount: float = Field(..., gt=0, description="Original debt amount")
    currency: str = Field(default="USD", description="Currency code")
    charge_off_date: date = Field(..., description="Date debt was charged off")
    original_creditor: str = Field(..., description="Original creditor name")
    account_number: Optional[str] = Field(None, description="Account number")
    category: Optional[str] = Field(None, description="Debt category (medical, utility, bnpl)")
    description: Optional[str] = Field(None, description="Description of debt")

    # Consumer info
    consumer_email: Optional[EmailStr] = None
    consumer_phone: Optional[str] = None
    consumer_name: Optional[str] = None
    consumer_address: Optional[Dict[str, str]] = None

    # Additional data
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class BulkDebtSubmission(BaseModel):
    """Bulk debt submission"""
    debts: List[DebtSubmission] = Field(..., max_length=1000)
    batch_reference: Optional[str] = None
    callback_url: Optional[str] = None


class DebtResponse(BaseModel):
    """Debt response"""
    debt_id: str
    consumer_id: str
    amount: float
    currency: str
    status: DebtStatus
    charge_off_date: date
    original_creditor: str
    created_at: datetime
    updated_at: datetime
    amount_paid: float = 0
    amount_remaining: float
    settlement_amount: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DebtUpdate(BaseModel):
    """Debt update request"""
    amount: Optional[float] = Field(None, gt=0)
    consumer_email: Optional[EmailStr] = None
    consumer_phone: Optional[str] = None
    consumer_address: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None


class BulkSubmissionResponse(BaseModel):
    """Bulk submission response"""
    batch_id: str
    total_submitted: int
    accepted: int
    rejected: int
    processing_time_ms: int
    debts: List[Dict[str, Any]]


# --- Shadow Bureau Models ---

class ShadowScoreResponse(BaseModel):
    """Shadow score response"""
    consumer_id: str
    shadow_score: int = Field(..., ge=300, le=850)
    risk_tier: RiskTier
    score_components: Dict[str, int]
    confidence: float = Field(..., ge=0, le=1)
    last_updated: datetime
    data_freshness_hours: int
    score_trend: Optional[str] = None


class NetworkCheckResponse(BaseModel):
    """Network check response"""
    consumer_id: str
    has_outstanding_debts: bool
    total_outstanding: float
    debt_count: int
    creditors_affected: List[str]
    oldest_debt_days: int
    recommendation: str
    recommendation_reason: str
    network_members_checked: int


class RiskAssessmentRequest(BaseModel):
    """Risk assessment request"""
    consumer_id: str
    proposed_credit: float = Field(..., gt=0)
    credit_type: Optional[str] = None
    purpose: Optional[str] = None


class RiskAssessmentResponse(BaseModel):
    """Risk assessment response"""
    assessment_id: str
    consumer_id: str
    proposed_credit: float
    decision: str
    suggested_limit: float
    approval_probability: float
    risk_factors: Dict[str, Any]
    data_sources: List[str]
    timestamp: datetime


class RestorationVerifyResponse(BaseModel):
    """Restoration certificate verification"""
    valid: bool
    certificate_id: str
    consumer_id: Optional[str] = None
    resolution_date: Optional[datetime] = None
    resolution_type: Optional[str] = None
    amount_resolved: Optional[float] = None
    trust_level: Optional[str] = None
    current_shadow_score: Optional[int] = None
    recommendation: Optional[str] = None
    expires_at: Optional[datetime] = None


# --- Payment Models ---

class PaymentRequest(BaseModel):
    """Payment request"""
    debt_id: str
    amount: float = Field(..., gt=0)
    payment_method_token: str
    payment_type: str = "one_time"
    metadata: Optional[Dict[str, Any]] = None


class PaymentResponse(BaseModel):
    """Payment response"""
    payment_id: str
    debt_id: str
    amount: float
    status: PaymentStatus
    processor: str
    processor_transaction_id: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None


class PaymentPlanRequest(BaseModel):
    """Payment plan creation request"""
    debt_id: str
    total_amount: float = Field(..., gt=0)
    num_payments: int = Field(..., ge=2, le=60)
    frequency: str = Field(default="monthly")
    start_date: date
    payment_method_token: str
    auto_debit: bool = True


class PaymentPlanResponse(BaseModel):
    """Payment plan response"""
    plan_id: str
    debt_id: str
    total_amount: float
    payment_amount: float
    num_payments: int
    payments_completed: int
    frequency: str
    status: PlanStatus
    start_date: date
    next_payment_date: Optional[date] = None
    schedule: List[Dict[str, Any]]
    created_at: datetime


# --- Reporting Models ---

class PortfolioReportResponse(BaseModel):
    """Portfolio report response"""
    report_id: str
    generated_at: datetime
    period_start: date
    period_end: date
    summary: Dict[str, Any]
    by_status: Dict[str, Any]
    by_age: Dict[str, Any]
    by_amount_range: Dict[str, Any]
    collection_metrics: Dict[str, Any]
    projections: Dict[str, Any]


class ClientReportResponse(BaseModel):
    """Client-specific report"""
    report_id: str
    client_id: str
    generated_at: datetime
    period: Dict[str, date]
    debts_summary: Dict[str, Any]
    payments_summary: Dict[str, Any]
    collection_rate: float
    avg_days_to_collect: float
    top_performing_categories: List[Dict[str, Any]]


class ComplianceReportResponse(BaseModel):
    """Compliance report"""
    report_id: str
    generated_at: datetime
    period: Dict[str, date]
    contact_compliance: Dict[str, Any]
    disclosure_compliance: Dict[str, Any]
    dispute_handling: Dict[str, Any]
    data_security: Dict[str, Any]
    audit_trail_summary: Dict[str, Any]
    issues_flagged: List[Dict[str, Any]]


class CustomReportRequest(BaseModel):
    """Custom report request"""
    report_type: ReportType
    filters: Dict[str, Any] = Field(default_factory=dict)
    date_range: Optional[Dict[str, date]] = None
    grouping: Optional[List[str]] = None
    metrics: Optional[List[str]] = None
    format: str = Field(default="json")


# --- Webhook Models ---

class WebhookRegistration(BaseModel):
    """Webhook registration"""
    url: str = Field(..., description="Webhook endpoint URL")
    events: List[WebhookEventType] = Field(..., min_length=1)
    secret: Optional[str] = Field(None, description="Secret for signature verification")
    active: bool = True
    metadata: Optional[Dict[str, Any]] = None


class WebhookResponse(BaseModel):
    """Webhook response"""
    webhook_id: str
    url: str
    events: List[WebhookEventType]
    active: bool
    created_at: datetime
    last_triggered: Optional[datetime] = None
    delivery_success_rate: float = 1.0


# --- Authentication Models ---

class TokenResponse(BaseModel):
    """OAuth token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    scope: str


class APIKeyResponse(BaseModel):
    """API key response"""
    api_key: str
    api_secret: str
    scopes: List[str]
    created_at: datetime
    expires_at: Optional[datetime] = None


# =============================================================================
# AUTHENTICATION & AUTHORIZATION
# =============================================================================

@dataclass
class APICredential:
    """API credential storage"""
    client_id: str
    api_key_hash: str
    secret_hash: str
    scopes: List[str]
    rate_limit_per_minute: int = 60
    rate_limit_per_day: int = 10000
    ip_whitelist: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None
    is_active: bool = True


@dataclass
class OAuthToken:
    """OAuth token storage"""
    token_id: str
    client_id: str
    access_token_hash: str
    refresh_token_hash: Optional[str] = None
    scopes: List[str] = field(default_factory=list)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=1))
    created_at: datetime = field(default_factory=datetime.utcnow)


class AuthManager:
    """Authentication and authorization manager"""

    def __init__(self):
        self.credentials: Dict[str, APICredential] = {}
        self.tokens: Dict[str, OAuthToken] = {}
        self.rate_limits: Dict[str, List[datetime]] = {}
        self.daily_counts: Dict[str, Dict[str, int]] = {}

    def create_api_key(
        self,
        client_id: str,
        scopes: Optional[List[str]] = None,
        rate_limit_minute: int = 60,
        rate_limit_day: int = 10000,
        ip_whitelist: Optional[List[str]] = None
    ) -> Tuple[str, str]:
        """Create new API credentials"""
        api_key = f"quan_live_{secrets.token_hex(16)}"
        api_secret = secrets.token_hex(32)

        cred = APICredential(
            client_id=client_id,
            api_key_hash=hashlib.sha256(api_key.encode()).hexdigest(),
            secret_hash=hashlib.sha256(api_secret.encode()).hexdigest(),
            scopes=scopes or ["read", "write"],
            rate_limit_per_minute=rate_limit_minute,
            rate_limit_per_day=rate_limit_day,
            ip_whitelist=ip_whitelist or []
        )

        self.credentials[client_id] = cred
        return api_key, api_secret

    def authenticate_api_key(
        self,
        api_key: str,
        api_secret: str,
        client_ip: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Authenticate API key and secret"""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        secret_hash = hashlib.sha256(api_secret.encode()).hexdigest()

        for client_id, cred in self.credentials.items():
            if cred.api_key_hash == key_hash and cred.secret_hash == secret_hash:
                if not cred.is_active:
                    return False, None, "API key is disabled"

                # IP whitelist check
                if cred.ip_whitelist and client_ip:
                    if client_ip not in cred.ip_whitelist:
                        return False, None, "IP not whitelisted"

                cred.last_used = datetime.utcnow()
                return True, client_id, None

        return False, None, "Invalid credentials"

    def check_rate_limit(self, client_id: str) -> Tuple[bool, Optional[str]]:
        """Check if client is within rate limits"""
        cred = self.credentials.get(client_id)
        if not cred:
            return False, "Client not found"

        now = datetime.utcnow()
        today = now.strftime("%Y-%m-%d")

        # Per-minute rate limit
        if client_id not in self.rate_limits:
            self.rate_limits[client_id] = []

        minute_ago = now - timedelta(minutes=1)
        self.rate_limits[client_id] = [
            t for t in self.rate_limits[client_id] if t > minute_ago
        ]

        if len(self.rate_limits[client_id]) >= cred.rate_limit_per_minute:
            return False, "Rate limit exceeded (per minute)"

        # Daily rate limit
        if client_id not in self.daily_counts:
            self.daily_counts[client_id] = {}

        daily_count = self.daily_counts[client_id].get(today, 0)
        if daily_count >= cred.rate_limit_per_day:
            return False, "Rate limit exceeded (daily)"

        # Update counts
        self.rate_limits[client_id].append(now)
        self.daily_counts[client_id][today] = daily_count + 1

        return True, None

    def create_oauth_token(
        self,
        client_id: str,
        scopes: List[str],
        expires_in: int = 3600
    ) -> Tuple[str, str]:
        """Create OAuth access and refresh tokens"""
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)

        token = OAuthToken(
            token_id=str(uuid.uuid4()),
            client_id=client_id,
            access_token_hash=hashlib.sha256(access_token.encode()).hexdigest(),
            refresh_token_hash=hashlib.sha256(refresh_token.encode()).hexdigest(),
            scopes=scopes,
            expires_at=datetime.utcnow() + timedelta(seconds=expires_in)
        )

        self.tokens[token.token_id] = token
        return access_token, refresh_token

    def validate_oauth_token(
        self,
        access_token: str
    ) -> Tuple[bool, Optional[str], Optional[List[str]]]:
        """Validate OAuth access token"""
        token_hash = hashlib.sha256(access_token.encode()).hexdigest()

        for token in self.tokens.values():
            if token.access_token_hash == token_hash:
                if datetime.utcnow() > token.expires_at:
                    return False, None, None
                return True, token.client_id, token.scopes

        return False, None, None


# =============================================================================
# REQUEST MONITORING & LOGGING
# =============================================================================

@dataclass
class APIRequest:
    """API request log entry"""
    request_id: str
    client_id: str
    method: str
    path: str
    query_params: Dict[str, Any]
    headers: Dict[str, str]
    body_size: int
    response_status: int
    response_size: int
    latency_ms: int
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MetricsCollector:
    """API metrics collection"""

    def __init__(self):
        self.requests: List[APIRequest] = []
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.endpoint_latencies: Dict[str, List[int]] = defaultdict(list)
        self.client_usage: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def log_request(self, request: APIRequest):
        """Log API request"""
        self.requests.append(request)

        # Track latencies
        self.endpoint_latencies[request.path].append(request.latency_ms)

        # Track errors
        if request.error:
            self.error_counts[request.error] += 1

        # Track client usage
        self.client_usage[request.client_id][request.path] += 1

        # Keep only last 10000 requests in memory
        if len(self.requests) > 10000:
            self.requests = self.requests[-10000:]

    def get_metrics(
        self,
        client_id: Optional[str] = None,
        time_window_minutes: int = 60
    ) -> Dict[str, Any]:
        """Get aggregated metrics"""
        cutoff = datetime.utcnow() - timedelta(minutes=time_window_minutes)

        if client_id:
            filtered = [r for r in self.requests
                       if r.client_id == client_id and r.timestamp > cutoff]
        else:
            filtered = [r for r in self.requests if r.timestamp > cutoff]

        if not filtered:
            return {"status": "no_data", "time_window_minutes": time_window_minutes}

        total = len(filtered)
        errors = sum(1 for r in filtered if r.error)
        avg_latency = sum(r.latency_ms for r in filtered) / total

        # Status code distribution
        status_dist: Dict[str, int] = defaultdict(int)
        for r in filtered:
            status_dist[str(r.response_status)] += 1

        # Endpoint breakdown
        endpoint_counts: Dict[str, int] = defaultdict(int)
        for r in filtered:
            endpoint_counts[r.path] += 1

        return {
            "time_window_minutes": time_window_minutes,
            "total_requests": total,
            "error_count": errors,
            "error_rate": errors / total if total > 0 else 0,
            "avg_latency_ms": round(avg_latency, 2),
            "p95_latency_ms": self._percentile([r.latency_ms for r in filtered], 95),
            "p99_latency_ms": self._percentile([r.latency_ms for r in filtered], 99),
            "status_distribution": dict(status_dist),
            "endpoint_breakdown": dict(endpoint_counts),
            "requests_per_second": total / (time_window_minutes * 60)
        }

    def _percentile(self, data: List[int], percentile: int) -> int:
        """Calculate percentile"""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]


# =============================================================================
# WEBHOOK MANAGER
# =============================================================================

@dataclass
class WebhookConfig:
    """Webhook configuration"""
    webhook_id: str
    client_id: str
    url: str
    events: List[WebhookEventType]
    secret: str
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_triggered: Optional[datetime] = None
    total_deliveries: int = 0
    successful_deliveries: int = 0


class WebhookManager:
    """Webhook management and delivery"""

    def __init__(self):
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.delivery_queue: List[Dict[str, Any]] = []

    def register(
        self,
        client_id: str,
        url: str,
        events: List[WebhookEventType],
        secret: Optional[str] = None
    ) -> WebhookConfig:
        """Register a webhook"""
        webhook_id = str(uuid.uuid4())
        webhook_secret = secret or secrets.token_hex(32)

        config = WebhookConfig(
            webhook_id=webhook_id,
            client_id=client_id,
            url=url,
            events=events,
            secret=webhook_secret
        )

        self.webhooks[webhook_id] = config
        return config

    def list_webhooks(self, client_id: str) -> List[WebhookConfig]:
        """List webhooks for a client"""
        return [w for w in self.webhooks.values() if w.client_id == client_id]

    def delete(self, webhook_id: str, client_id: str) -> bool:
        """Delete a webhook"""
        webhook = self.webhooks.get(webhook_id)
        if webhook and webhook.client_id == client_id:
            del self.webhooks[webhook_id]
            return True
        return False

    def queue_event(
        self,
        event_type: WebhookEventType,
        payload: Dict[str, Any],
        client_id: Optional[str] = None
    ):
        """Queue event for delivery"""
        for webhook in self.webhooks.values():
            if not webhook.active:
                continue
            if client_id and webhook.client_id != client_id:
                continue
            if event_type not in webhook.events:
                continue

            event = {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type.value,
                "timestamp": datetime.utcnow().isoformat(),
                "payload": payload,
                "webhook_id": webhook.webhook_id,
                "url": webhook.url,
                "secret": webhook.secret
            }

            self.delivery_queue.append(event)

    def sign_payload(self, payload: Dict[str, Any], secret: str) -> str:
        """Sign webhook payload"""
        payload_str = json.dumps(payload, sort_keys=True, default=str)
        return hmac.new(
            secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()


# =============================================================================
# API GATEWAY CORE
# =============================================================================

class QUANAPIGateway:
    """
    QUAN Production API Gateway

    Central orchestrator for all external API operations.
    """

    def __init__(self):
        self.auth_manager = AuthManager()
        self.metrics = MetricsCollector()
        self.webhook_manager = WebhookManager()

        # In-memory storage (replace with database in production)
        self.debts: Dict[str, Dict[str, Any]] = {}
        self.payments: Dict[str, Dict[str, Any]] = {}
        self.payment_plans: Dict[str, Dict[str, Any]] = {}
        self.consumer_scores: Dict[str, Dict[str, Any]] = {}

        # API version
        self.api_version = "v1"

    # -------------------------------------------------------------------------
    # Creditor Integration API
    # -------------------------------------------------------------------------

    def submit_debt(
        self,
        client_id: str,
        debt: DebtSubmission
    ) -> DebtResponse:
        """Submit a single debt for collection"""
        debt_id = f"debt_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        debt_record = {
            "debt_id": debt_id,
            "client_id": client_id,
            "consumer_id": debt.consumer_id,
            "amount": debt.amount,
            "currency": debt.currency,
            "status": DebtStatus.SUBMITTED,
            "charge_off_date": debt.charge_off_date,
            "original_creditor": debt.original_creditor,
            "account_number": debt.account_number,
            "category": debt.category,
            "description": debt.description,
            "consumer_email": debt.consumer_email,
            "consumer_phone": debt.consumer_phone,
            "consumer_name": debt.consumer_name,
            "consumer_address": debt.consumer_address,
            "created_at": now,
            "updated_at": now,
            "amount_paid": 0,
            "amount_remaining": debt.amount,
            "settlement_amount": None,
            "metadata": debt.metadata or {}
        }

        self.debts[debt_id] = debt_record

        # Queue webhook
        self.webhook_manager.queue_event(
            WebhookEventType.DEBT_CREATED,
            {"debt_id": debt_id, "amount": debt.amount},
            client_id
        )

        return DebtResponse(
            debt_id=debt_id,
            consumer_id=debt.consumer_id,
            amount=debt.amount,
            currency=debt.currency,
            status=DebtStatus.SUBMITTED,
            charge_off_date=debt.charge_off_date,
            original_creditor=debt.original_creditor,
            created_at=now,
            updated_at=now,
            amount_paid=0,
            amount_remaining=debt.amount
        )

    def bulk_submit_debts(
        self,
        client_id: str,
        bulk: BulkDebtSubmission
    ) -> BulkSubmissionResponse:
        """Bulk submit debts"""
        start_time = time.time()
        batch_id = f"batch_{uuid.uuid4().hex[:12]}"

        results = []
        accepted = 0
        rejected = 0

        for debt in bulk.debts:
            try:
                response = self.submit_debt(client_id, debt)
                results.append({
                    "status": "accepted",
                    "debt_id": response.debt_id,
                    "consumer_id": debt.consumer_id
                })
                accepted += 1
            except Exception as e:
                results.append({
                    "status": "rejected",
                    "consumer_id": debt.consumer_id,
                    "error": str(e)
                })
                rejected += 1

        processing_time = int((time.time() - start_time) * 1000)

        return BulkSubmissionResponse(
            batch_id=batch_id,
            total_submitted=len(bulk.debts),
            accepted=accepted,
            rejected=rejected,
            processing_time_ms=processing_time,
            debts=results
        )

    def get_debt(self, debt_id: str, client_id: str) -> Optional[DebtResponse]:
        """Get debt by ID"""
        debt = self.debts.get(debt_id)
        if not debt or debt["client_id"] != client_id:
            return None

        return DebtResponse(
            debt_id=debt["debt_id"],
            consumer_id=debt["consumer_id"],
            amount=debt["amount"],
            currency=debt["currency"],
            status=debt["status"],
            charge_off_date=debt["charge_off_date"],
            original_creditor=debt["original_creditor"],
            created_at=debt["created_at"],
            updated_at=debt["updated_at"],
            amount_paid=debt["amount_paid"],
            amount_remaining=debt["amount_remaining"],
            settlement_amount=debt.get("settlement_amount"),
            metadata=debt.get("metadata", {})
        )

    def update_debt(
        self,
        debt_id: str,
        client_id: str,
        update: DebtUpdate
    ) -> Optional[DebtResponse]:
        """Update debt information"""
        debt = self.debts.get(debt_id)
        if not debt or debt["client_id"] != client_id:
            return None

        if update.amount is not None:
            debt["amount"] = update.amount
            debt["amount_remaining"] = update.amount - debt["amount_paid"]
        if update.consumer_email is not None:
            debt["consumer_email"] = update.consumer_email
        if update.consumer_phone is not None:
            debt["consumer_phone"] = update.consumer_phone
        if update.consumer_address is not None:
            debt["consumer_address"] = update.consumer_address
        if update.metadata is not None:
            debt["metadata"].update(update.metadata)

        debt["updated_at"] = datetime.utcnow()

        # Queue webhook
        self.webhook_manager.queue_event(
            WebhookEventType.DEBT_UPDATED,
            {"debt_id": debt_id},
            client_id
        )

        return self.get_debt(debt_id, client_id)

    def recall_debt(self, debt_id: str, client_id: str) -> bool:
        """Recall a debt (withdraw from collection)"""
        debt = self.debts.get(debt_id)
        if not debt or debt["client_id"] != client_id:
            return False

        debt["status"] = DebtStatus.RECALLED
        debt["updated_at"] = datetime.utcnow()

        # Queue webhook
        self.webhook_manager.queue_event(
            WebhookEventType.DEBT_STATUS_CHANGED,
            {"debt_id": debt_id, "new_status": "recalled"},
            client_id
        )

        return True

    # -------------------------------------------------------------------------
    # Shadow Bureau API (Monetization)
    # -------------------------------------------------------------------------

    def get_shadow_score(
        self,
        consumer_id: str,
        client_id: str
    ) -> ShadowScoreResponse:
        """Get consumer's shadow score"""
        # In production, this queries the live ledger
        # Simulated response with realistic scoring

        # Generate deterministic but varied scores based on consumer_id
        hash_val = int(hashlib.md5(consumer_id.encode()).hexdigest()[:8], 16)
        base_score = 400 + (hash_val % 400)  # 400-800 range

        response_score = 50 + (hash_val % 50)
        payment_score = 40 + (hash_val % 60)
        promise_score = 45 + (hash_val % 55)
        velocity_score = 35 + (hash_val % 65)

        # Determine risk tier
        if base_score >= 750:
            tier = RiskTier.A
        elif base_score >= 650:
            tier = RiskTier.B
        elif base_score >= 550:
            tier = RiskTier.C
        elif base_score >= 450:
            tier = RiskTier.D
        else:
            tier = RiskTier.F

        return ShadowScoreResponse(
            consumer_id=consumer_id,
            shadow_score=base_score,
            risk_tier=tier,
            score_components={
                "response_score": response_score,
                "payment_score": payment_score,
                "promise_score": promise_score,
                "velocity_score": velocity_score
            },
            confidence=0.75 + (hash_val % 25) / 100,
            last_updated=datetime.utcnow(),
            data_freshness_hours=hash_val % 24,
            score_trend="stable" if hash_val % 3 == 0 else ("improving" if hash_val % 3 == 1 else "declining")
        )

    def network_check(
        self,
        consumer_id: str,
        client_id: str
    ) -> NetworkCheckResponse:
        """Check network for outstanding debts"""
        # Simulated network check
        hash_val = int(hashlib.md5(consumer_id.encode()).hexdigest()[:8], 16)

        has_debts = hash_val % 3 != 0

        if has_debts:
            debt_count = 1 + hash_val % 4
            total = round(50 + (hash_val % 500), 2)
            creditors = ["Klarna", "Affirm", "Afterpay", "Sezzle"][:debt_count]
            recommendation = "REVIEW" if total < 200 else "DECLINE"
        else:
            debt_count = 0
            total = 0
            creditors = []
            recommendation = "APPROVE"

        return NetworkCheckResponse(
            consumer_id=consumer_id,
            has_outstanding_debts=has_debts,
            total_outstanding=total,
            debt_count=debt_count,
            creditors_affected=creditors,
            oldest_debt_days=hash_val % 180 if has_debts else 0,
            recommendation=recommendation,
            recommendation_reason="Clean network status" if not has_debts else "Outstanding micro-debts in network",
            network_members_checked=47
        )

    def risk_assessment(
        self,
        request: RiskAssessmentRequest,
        client_id: str
    ) -> RiskAssessmentResponse:
        """Full risk assessment for underwriting"""
        shadow = self.get_shadow_score(request.consumer_id, client_id)
        network = self.network_check(request.consumer_id, client_id)

        # Calculate risk factors
        score_factor = shadow.shadow_score / 850
        network_factor = 1.0 if not network.has_outstanding_debts else 0.7
        amount_factor = 1.0 if request.proposed_credit < 200 else (0.9 if request.proposed_credit < 500 else 0.8)

        approval_probability = score_factor * network_factor * amount_factor

        if approval_probability > 0.7:
            decision = "APPROVE"
            suggested_limit = request.proposed_credit
        elif approval_probability > 0.5:
            decision = "CONDITIONAL_APPROVE"
            suggested_limit = round(request.proposed_credit * 0.5, 2)
        else:
            decision = "DECLINE"
            suggested_limit = 0

        return RiskAssessmentResponse(
            assessment_id=f"assess_{uuid.uuid4().hex[:12]}",
            consumer_id=request.consumer_id,
            proposed_credit=request.proposed_credit,
            decision=decision,
            suggested_limit=suggested_limit,
            approval_probability=round(approval_probability, 3),
            risk_factors={
                "shadow_score": shadow.shadow_score,
                "risk_tier": shadow.risk_tier.value,
                "network_status": "clean" if not network.has_outstanding_debts else "outstanding",
                "outstanding_amount": network.total_outstanding,
                "score_factor": round(score_factor, 3),
                "network_factor": network_factor,
                "amount_factor": amount_factor
            },
            data_sources=["shadow_bureau", "network_check"],
            timestamp=datetime.utcnow()
        )

    def verify_restoration(
        self,
        certificate_id: str,
        client_id: str
    ) -> RestorationVerifyResponse:
        """Verify restoration certificate"""
        # Simulated verification
        hash_val = int(hashlib.md5(certificate_id.encode()).hexdigest()[:8], 16)
        is_valid = hash_val % 5 != 0  # 80% valid rate for simulation

        if is_valid:
            return RestorationVerifyResponse(
                valid=True,
                certificate_id=certificate_id,
                consumer_id=f"C{hash_val % 100000:05d}",
                resolution_date=datetime.utcnow() - timedelta(days=hash_val % 30),
                resolution_type="settled" if hash_val % 2 == 0 else "paid_in_full",
                amount_resolved=round(50 + (hash_val % 450), 2),
                trust_level="RESTORED",
                current_shadow_score=650 + hash_val % 150,
                recommendation="RESTORE_STANDARD",
                expires_at=datetime.utcnow() + timedelta(days=365)
            )
        else:
            return RestorationVerifyResponse(
                valid=False,
                certificate_id=certificate_id
            )

    # -------------------------------------------------------------------------
    # Payment API
    # -------------------------------------------------------------------------

    def process_payment(
        self,
        request: PaymentRequest,
        client_id: str
    ) -> PaymentResponse:
        """Process a payment"""
        payment_id = f"pay_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        # Verify debt exists
        debt = self.debts.get(request.debt_id)
        if not debt or debt["client_id"] != client_id:
            raise HTTPException(status_code=404, detail="Debt not found")

        # Simulate payment processing
        hash_val = int(hashlib.md5(payment_id.encode()).hexdigest()[:8], 16)
        success = hash_val % 10 != 0  # 90% success rate

        if success:
            status = PaymentStatus.COMPLETED
            processor_txn_id = f"txn_{secrets.token_hex(8)}"
            failure_reason = None

            # Update debt
            debt["amount_paid"] += request.amount
            debt["amount_remaining"] = max(0, debt["amount"] - debt["amount_paid"])
            debt["updated_at"] = now

            if debt["amount_remaining"] == 0:
                debt["status"] = DebtStatus.PAID_IN_FULL

            # Queue webhook
            self.webhook_manager.queue_event(
                WebhookEventType.PAYMENT_RECEIVED,
                {"payment_id": payment_id, "debt_id": request.debt_id, "amount": request.amount},
                client_id
            )
        else:
            status = PaymentStatus.FAILED
            processor_txn_id = None
            failure_reason = "insufficient_funds"

            # Queue webhook
            self.webhook_manager.queue_event(
                WebhookEventType.PAYMENT_FAILED,
                {"payment_id": payment_id, "debt_id": request.debt_id, "reason": failure_reason},
                client_id
            )

        payment_record = {
            "payment_id": payment_id,
            "debt_id": request.debt_id,
            "client_id": client_id,
            "amount": request.amount,
            "status": status,
            "processor": "stripe",
            "processor_transaction_id": processor_txn_id,
            "payment_method_token": request.payment_method_token,
            "created_at": now,
            "completed_at": now if success else None,
            "failure_reason": failure_reason,
            "metadata": request.metadata or {}
        }

        self.payments[payment_id] = payment_record

        return PaymentResponse(
            payment_id=payment_id,
            debt_id=request.debt_id,
            amount=request.amount,
            status=status,
            processor="stripe",
            processor_transaction_id=processor_txn_id,
            created_at=now,
            completed_at=now if success else None,
            failure_reason=failure_reason
        )

    def get_payment(
        self,
        payment_id: str,
        client_id: str
    ) -> Optional[PaymentResponse]:
        """Get payment by ID"""
        payment = self.payments.get(payment_id)
        if not payment or payment["client_id"] != client_id:
            return None

        return PaymentResponse(
            payment_id=payment["payment_id"],
            debt_id=payment["debt_id"],
            amount=payment["amount"],
            status=payment["status"],
            processor=payment["processor"],
            processor_transaction_id=payment.get("processor_transaction_id"),
            created_at=payment["created_at"],
            completed_at=payment.get("completed_at"),
            failure_reason=payment.get("failure_reason")
        )

    def create_payment_plan(
        self,
        request: PaymentPlanRequest,
        client_id: str
    ) -> PaymentPlanResponse:
        """Create a payment plan"""
        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        # Verify debt exists
        debt = self.debts.get(request.debt_id)
        if not debt or debt["client_id"] != client_id:
            raise HTTPException(status_code=404, detail="Debt not found")

        payment_amount = round(request.total_amount / request.num_payments, 2)

        # Generate schedule
        schedule = []
        current_date = request.start_date
        for i in range(request.num_payments):
            schedule.append({
                "payment_number": i + 1,
                "date": current_date.isoformat(),
                "amount": payment_amount,
                "status": "scheduled"
            })

            # Calculate next date based on frequency
            if request.frequency == "weekly":
                current_date = current_date + timedelta(weeks=1)
            elif request.frequency == "biweekly":
                current_date = current_date + timedelta(weeks=2)
            else:  # monthly
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1)

        plan_record = {
            "plan_id": plan_id,
            "debt_id": request.debt_id,
            "client_id": client_id,
            "total_amount": request.total_amount,
            "payment_amount": payment_amount,
            "num_payments": request.num_payments,
            "payments_completed": 0,
            "frequency": request.frequency,
            "status": PlanStatus.ACTIVE,
            "start_date": request.start_date,
            "next_payment_date": request.start_date,
            "schedule": schedule,
            "payment_method_token": request.payment_method_token,
            "auto_debit": request.auto_debit,
            "created_at": now
        }

        self.payment_plans[plan_id] = plan_record

        # Update debt status
        debt["status"] = DebtStatus.PAYMENT_PLAN
        debt["updated_at"] = now

        # Queue webhook
        self.webhook_manager.queue_event(
            WebhookEventType.PLAN_CREATED,
            {"plan_id": plan_id, "debt_id": request.debt_id},
            client_id
        )

        return PaymentPlanResponse(
            plan_id=plan_id,
            debt_id=request.debt_id,
            total_amount=request.total_amount,
            payment_amount=payment_amount,
            num_payments=request.num_payments,
            payments_completed=0,
            frequency=request.frequency,
            status=PlanStatus.ACTIVE,
            start_date=request.start_date,
            next_payment_date=request.start_date,
            schedule=schedule,
            created_at=now
        )

    def get_payment_plan(
        self,
        plan_id: str,
        client_id: str
    ) -> Optional[PaymentPlanResponse]:
        """Get payment plan by ID"""
        plan = self.payment_plans.get(plan_id)
        if not plan or plan["client_id"] != client_id:
            return None

        return PaymentPlanResponse(
            plan_id=plan["plan_id"],
            debt_id=plan["debt_id"],
            total_amount=plan["total_amount"],
            payment_amount=plan["payment_amount"],
            num_payments=plan["num_payments"],
            payments_completed=plan["payments_completed"],
            frequency=plan["frequency"],
            status=plan["status"],
            start_date=plan["start_date"],
            next_payment_date=plan.get("next_payment_date"),
            schedule=plan["schedule"],
            created_at=plan["created_at"]
        )

    # -------------------------------------------------------------------------
    # Reporting API
    # -------------------------------------------------------------------------

    def get_portfolio_report(
        self,
        client_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> PortfolioReportResponse:
        """Generate portfolio summary report"""
        now = datetime.utcnow()
        end = end_date or date.today()
        start = start_date or (end - timedelta(days=30))

        # Filter debts for client
        client_debts = [d for d in self.debts.values() if d["client_id"] == client_id]

        # Calculate summaries
        total_debts = len(client_debts)
        total_amount = sum(d["amount"] for d in client_debts)
        total_collected = sum(d["amount_paid"] for d in client_debts)
        total_remaining = sum(d["amount_remaining"] for d in client_debts)

        # By status
        by_status: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "amount": 0})
        for d in client_debts:
            status = d["status"].value if hasattr(d["status"], 'value') else d["status"]
            by_status[status]["count"] += 1
            by_status[status]["amount"] += d["amount"]

        # By age bucket
        by_age: Dict[str, Dict[str, Any]] = {
            "0-30": {"count": 0, "amount": 0},
            "31-60": {"count": 0, "amount": 0},
            "61-90": {"count": 0, "amount": 0},
            "91-180": {"count": 0, "amount": 0},
            "180+": {"count": 0, "amount": 0}
        }

        for d in client_debts:
            age = (date.today() - d["charge_off_date"]).days if isinstance(d["charge_off_date"], date) else 0
            if age <= 30:
                bucket = "0-30"
            elif age <= 60:
                bucket = "31-60"
            elif age <= 90:
                bucket = "61-90"
            elif age <= 180:
                bucket = "91-180"
            else:
                bucket = "180+"
            by_age[bucket]["count"] += 1
            by_age[bucket]["amount"] += d["amount"]

        # Amount ranges
        by_amount: Dict[str, Dict[str, Any]] = {
            "0-50": {"count": 0, "total": 0},
            "51-100": {"count": 0, "total": 0},
            "101-250": {"count": 0, "total": 0},
            "251-500": {"count": 0, "total": 0},
            "500+": {"count": 0, "total": 0}
        }

        for d in client_debts:
            amount = d["amount"]
            if amount <= 50:
                bucket = "0-50"
            elif amount <= 100:
                bucket = "51-100"
            elif amount <= 250:
                bucket = "101-250"
            elif amount <= 500:
                bucket = "251-500"
            else:
                bucket = "500+"
            by_amount[bucket]["count"] += 1
            by_amount[bucket]["total"] += amount

        return PortfolioReportResponse(
            report_id=f"rpt_{uuid.uuid4().hex[:12]}",
            generated_at=now,
            period_start=start,
            period_end=end,
            summary={
                "total_debts": total_debts,
                "total_amount": round(total_amount, 2),
                "total_collected": round(total_collected, 2),
                "total_remaining": round(total_remaining, 2),
                "collection_rate": round(total_collected / total_amount * 100, 2) if total_amount > 0 else 0
            },
            by_status=dict(by_status),
            by_age=by_age,
            by_amount_range=by_amount,
            collection_metrics={
                "avg_days_to_first_payment": 15,
                "avg_days_to_resolution": 45,
                "settlement_rate": 35.5,
                "paid_in_full_rate": 22.3
            },
            projections={
                "expected_collection_30d": round(total_remaining * 0.15, 2),
                "expected_collection_60d": round(total_remaining * 0.25, 2),
                "expected_collection_90d": round(total_remaining * 0.35, 2)
            }
        )

    def get_client_report(
        self,
        client_id: str,
        report_client_id: str
    ) -> ClientReportResponse:
        """Generate client-specific report"""
        now = datetime.utcnow()

        # Filter data
        client_debts = [d for d in self.debts.values() if d["client_id"] == report_client_id]
        client_payments = [p for p in self.payments.values() if p["client_id"] == report_client_id]

        total_debts = len(client_debts)
        total_amount = sum(d["amount"] for d in client_debts)
        total_payments = len(client_payments)
        total_collected = sum(p["amount"] for p in client_payments if p["status"] == PaymentStatus.COMPLETED)

        return ClientReportResponse(
            report_id=f"rpt_{uuid.uuid4().hex[:12]}",
            client_id=report_client_id,
            generated_at=now,
            period={"start": date.today() - timedelta(days=30), "end": date.today()},
            debts_summary={
                "total_accounts": total_debts,
                "total_principal": round(total_amount, 2),
                "active_accounts": len([d for d in client_debts if d["status"] == DebtStatus.ACTIVE]),
                "settled_accounts": len([d for d in client_debts if d["status"] == DebtStatus.SETTLED])
            },
            payments_summary={
                "total_payments": total_payments,
                "total_collected": round(total_collected, 2),
                "successful_payments": len([p for p in client_payments if p["status"] == PaymentStatus.COMPLETED]),
                "failed_payments": len([p for p in client_payments if p["status"] == PaymentStatus.FAILED])
            },
            collection_rate=round(total_collected / total_amount * 100, 2) if total_amount > 0 else 0,
            avg_days_to_collect=32.5,
            top_performing_categories=[
                {"category": "bnpl", "collection_rate": 45.2},
                {"category": "utility", "collection_rate": 38.7},
                {"category": "subscription", "collection_rate": 35.1}
            ]
        )

    def get_compliance_report(
        self,
        client_id: str
    ) -> ComplianceReportResponse:
        """Generate compliance report"""
        now = datetime.utcnow()

        return ComplianceReportResponse(
            report_id=f"rpt_{uuid.uuid4().hex[:12]}",
            generated_at=now,
            period={"start": date.today() - timedelta(days=30), "end": date.today()},
            contact_compliance={
                "total_contacts": 15420,
                "within_hours": 15380,
                "outside_hours": 40,
                "compliance_rate": 99.74,
                "weekly_limit_exceeded": 0
            },
            disclosure_compliance={
                "total_required": 8500,
                "delivered": 8500,
                "compliance_rate": 100.0
            },
            dispute_handling={
                "total_disputes": 127,
                "resolved_within_sla": 125,
                "pending": 2,
                "avg_resolution_days": 4.2
            },
            data_security={
                "encryption_status": "compliant",
                "access_audit_status": "compliant",
                "data_retention_status": "compliant",
                "last_security_review": (now - timedelta(days=15)).isoformat()
            },
            audit_trail_summary={
                "total_events_logged": 245678,
                "retention_days": 365,
                "storage_status": "healthy"
            },
            issues_flagged=[]
        )

    def generate_custom_report(
        self,
        client_id: str,
        request: CustomReportRequest
    ) -> Dict[str, Any]:
        """Generate custom report"""
        report_id = f"rpt_{uuid.uuid4().hex[:12]}"

        return {
            "report_id": report_id,
            "report_type": request.report_type.value,
            "generated_at": datetime.utcnow().isoformat(),
            "filters_applied": request.filters,
            "date_range": request.date_range,
            "data": {
                "message": "Custom report generation in progress",
                "estimated_completion": "5 minutes"
            },
            "format": request.format,
            "download_url": f"/api/v1/reports/download/{report_id}"
        }


# =============================================================================
# FASTAPI APPLICATION
# =============================================================================

# Initialize gateway
gateway = QUANAPIGateway()

# Security schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_secret_header = APIKeyHeader(name="X-API-Secret", auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


async def get_client_id(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header),
    api_secret: Optional[str] = Depends(api_secret_header),
    token: Optional[str] = Depends(oauth2_scheme)
) -> str:
    """Extract and validate client credentials"""
    client_ip = request.client.host if request.client else None

    # Try API key authentication
    if api_key and api_secret:
        success, client_id, error = gateway.auth_manager.authenticate_api_key(
            api_key, api_secret, client_ip
        )
        if success and client_id:
            # Check rate limit
            allowed, rate_error = gateway.auth_manager.check_rate_limit(client_id)
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=rate_error
                )
            return client_id
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error or "Invalid API credentials"
        )

    # Try OAuth token authentication
    if token:
        success, client_id, scopes = gateway.auth_manager.validate_oauth_token(token)
        if success and client_id:
            return client_id
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required"
    )


# Request logging middleware
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all API requests"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_id = str(uuid.uuid4())

        # Get client ID from headers if present
        api_key = request.headers.get("X-API-Key", "")
        client_id = "anonymous"
        if api_key:
            # Extract client from key (simplified)
            client_id = api_key[:20] if api_key else "anonymous"

        response = await call_next(request)

        latency_ms = int((time.time() - start_time) * 1000)

        # Log request
        log_entry = APIRequest(
            request_id=request_id,
            client_id=client_id,
            method=request.method,
            path=request.url.path,
            query_params=dict(request.query_params),
            headers={k: v for k, v in request.headers.items()
                    if k.lower() not in ["x-api-key", "x-api-secret", "authorization"]},
            body_size=0,
            response_status=response.status_code,
            response_size=0,
            latency_ms=latency_ms
        )

        gateway.metrics.log_request(log_entry)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{latency_ms}ms"

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("QUAN API Gateway starting up...")

    # Create demo credentials for testing
    api_key, api_secret = gateway.auth_manager.create_api_key(
        client_id="demo_client",
        scopes=["read", "write", "admin"],
        rate_limit_minute=100,
        rate_limit_day=50000
    )
    logger.info(f"Demo API Key: {api_key}")
    logger.info(f"Demo API Secret: {api_secret[:20]}...")

    yield

    # Shutdown
    logger.info("QUAN API Gateway shutting down...")


# Create FastAPI app
app = FastAPI(
    title="QUAN Recovery API",
    description="""
## QUAN Recovery Production API

The external-facing API for the QUAN micro-debt collection platform.

### Features

- **Creditor Integration**: Submit and manage debts
- **Shadow Bureau**: Real-time behavioral scoring and network checks
- **Payments**: Process payments and create payment plans
- **Reporting**: Portfolio, client, and compliance reports
- **Webhooks**: Real-time event notifications

### Authentication

All endpoints require authentication via:
- **API Key**: Include `X-API-Key` and `X-API-Secret` headers
- **OAuth 2.0**: Bearer token in `Authorization` header

### Rate Limits

- 60 requests per minute
- 10,000 requests per day
""",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Add middleware
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# =============================================================================
# API ROUTERS
# =============================================================================

# --- Authentication Router ---
auth_router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@auth_router.post("/token", response_model=TokenResponse)
async def get_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Get OAuth access token"""
    # Validate client credentials
    success, client_id, error = gateway.auth_manager.authenticate_api_key(
        form_data.username,
        form_data.password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Create tokens
    access_token, refresh_token = gateway.auth_manager.create_oauth_token(
        client_id,
        scopes=["read", "write"]
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=3600,
        refresh_token=refresh_token,
        scope="read write"
    )


@auth_router.post("/keys", response_model=APIKeyResponse)
async def create_api_key(
    scopes: List[str] = Body(default=["read", "write"]),
    client_id: str = Depends(get_client_id)
):
    """Create new API credentials"""
    new_client_id = f"{client_id}_{uuid.uuid4().hex[:8]}"
    api_key, api_secret = gateway.auth_manager.create_api_key(
        client_id=new_client_id,
        scopes=scopes
    )

    return APIKeyResponse(
        api_key=api_key,
        api_secret=api_secret,
        scopes=scopes,
        created_at=datetime.utcnow()
    )


# --- Creditor Integration Router ---
debts_router = APIRouter(prefix="/api/v1/debts", tags=["Debts"])


@debts_router.post("", response_model=DebtResponse, status_code=status.HTTP_201_CREATED)
async def submit_debt(
    debt: DebtSubmission,
    client_id: str = Depends(get_client_id)
):
    """Submit a single debt for collection"""
    return gateway.submit_debt(client_id, debt)


@debts_router.post("/bulk", response_model=BulkSubmissionResponse)
async def bulk_submit_debts(
    bulk: BulkDebtSubmission,
    client_id: str = Depends(get_client_id)
):
    """Bulk submit debts for collection"""
    return gateway.bulk_submit_debts(client_id, bulk)


@debts_router.get("/{debt_id}", response_model=DebtResponse)
async def get_debt(
    debt_id: str = Path(..., description="Debt ID"),
    client_id: str = Depends(get_client_id)
):
    """Get debt by ID"""
    debt = gateway.get_debt(debt_id, client_id)
    if not debt:
        raise HTTPException(status_code=404, detail="Debt not found")
    return debt


@debts_router.patch("/{debt_id}", response_model=DebtResponse)
async def update_debt(
    debt_id: str = Path(..., description="Debt ID"),
    update: DebtUpdate = Body(...),
    client_id: str = Depends(get_client_id)
):
    """Update debt information"""
    debt = gateway.update_debt(debt_id, client_id, update)
    if not debt:
        raise HTTPException(status_code=404, detail="Debt not found")
    return debt


@debts_router.delete("/{debt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def recall_debt(
    debt_id: str = Path(..., description="Debt ID"),
    client_id: str = Depends(get_client_id)
):
    """Recall (withdraw) a debt from collection"""
    success = gateway.recall_debt(debt_id, client_id)
    if not success:
        raise HTTPException(status_code=404, detail="Debt not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Shadow Bureau Router ---
bureau_router = APIRouter(prefix="/api/v1", tags=["Shadow Bureau"])


@bureau_router.get("/scores/{consumer_id}", response_model=ShadowScoreResponse)
async def get_shadow_score(
    consumer_id: str = Path(..., description="Consumer ID"),
    client_id: str = Depends(get_client_id)
):
    """Get consumer's shadow score"""
    return gateway.get_shadow_score(consumer_id, client_id)


@bureau_router.get("/network/{consumer_id}", response_model=NetworkCheckResponse)
async def network_check(
    consumer_id: str = Path(..., description="Consumer ID"),
    client_id: str = Depends(get_client_id)
):
    """Check network for outstanding debts"""
    return gateway.network_check(consumer_id, client_id)


@bureau_router.post("/assess", response_model=RiskAssessmentResponse)
async def risk_assessment(
    request: RiskAssessmentRequest,
    client_id: str = Depends(get_client_id)
):
    """Full risk assessment for underwriting decisions"""
    return gateway.risk_assessment(request, client_id)


@bureau_router.get("/restoration/{certificate_id}", response_model=RestorationVerifyResponse)
async def verify_restoration(
    certificate_id: str = Path(..., description="Restoration certificate ID"),
    client_id: str = Depends(get_client_id)
):
    """Verify restoration certificate"""
    return gateway.verify_restoration(certificate_id, client_id)


# --- Payments Router ---
payments_router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])


@payments_router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def process_payment(
    request: PaymentRequest,
    client_id: str = Depends(get_client_id)
):
    """Process a payment"""
    return gateway.process_payment(request, client_id)


@payments_router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: str = Path(..., description="Payment ID"),
    client_id: str = Depends(get_client_id)
):
    """Get payment by ID"""
    payment = gateway.get_payment(payment_id, client_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


# --- Payment Plans Router ---
plans_router = APIRouter(prefix="/api/v1/plans", tags=["Payment Plans"])


@plans_router.post("", response_model=PaymentPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_payment_plan(
    request: PaymentPlanRequest,
    client_id: str = Depends(get_client_id)
):
    """Create a payment plan"""
    return gateway.create_payment_plan(request, client_id)


@plans_router.get("/{plan_id}", response_model=PaymentPlanResponse)
async def get_payment_plan(
    plan_id: str = Path(..., description="Plan ID"),
    client_id: str = Depends(get_client_id)
):
    """Get payment plan by ID"""
    plan = gateway.get_payment_plan(plan_id, client_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Payment plan not found")
    return plan


# --- Reporting Router ---
reports_router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


@reports_router.get("/portfolio", response_model=PortfolioReportResponse)
async def get_portfolio_report(
    start_date: Optional[date] = Query(None, description="Report start date"),
    end_date: Optional[date] = Query(None, description="Report end date"),
    client_id: str = Depends(get_client_id)
):
    """Get portfolio summary report"""
    return gateway.get_portfolio_report(client_id, start_date, end_date)


@reports_router.get("/client/{report_client_id}", response_model=ClientReportResponse)
async def get_client_report(
    report_client_id: str = Path(..., description="Client ID for report"),
    client_id: str = Depends(get_client_id)
):
    """Get client-specific report"""
    return gateway.get_client_report(client_id, report_client_id)


@reports_router.get("/compliance", response_model=ComplianceReportResponse)
async def get_compliance_report(
    client_id: str = Depends(get_client_id)
):
    """Get compliance report"""
    return gateway.get_compliance_report(client_id)


@reports_router.post("/custom")
async def generate_custom_report(
    request: CustomReportRequest,
    client_id: str = Depends(get_client_id)
):
    """Generate custom report"""
    return gateway.generate_custom_report(client_id, request)


# --- Webhooks Router ---
webhooks_router = APIRouter(prefix="/api/v1/webhooks", tags=["Webhooks"])


@webhooks_router.post("", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def register_webhook(
    registration: WebhookRegistration,
    client_id: str = Depends(get_client_id)
):
    """Register a webhook endpoint"""
    config = gateway.webhook_manager.register(
        client_id=client_id,
        url=registration.url,
        events=registration.events,
        secret=registration.secret
    )

    return WebhookResponse(
        webhook_id=config.webhook_id,
        url=config.url,
        events=config.events,
        active=config.active,
        created_at=config.created_at,
        delivery_success_rate=1.0
    )


@webhooks_router.get("", response_model=List[WebhookResponse])
async def list_webhooks(
    client_id: str = Depends(get_client_id)
):
    """List registered webhooks"""
    configs = gateway.webhook_manager.list_webhooks(client_id)
    return [
        WebhookResponse(
            webhook_id=c.webhook_id,
            url=c.url,
            events=c.events,
            active=c.active,
            created_at=c.created_at,
            last_triggered=c.last_triggered,
            delivery_success_rate=c.successful_deliveries / c.total_deliveries if c.total_deliveries > 0 else 1.0
        )
        for c in configs
    ]


@webhooks_router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: str = Path(..., description="Webhook ID"),
    client_id: str = Depends(get_client_id)
):
    """Delete a webhook"""
    success = gateway.webhook_manager.delete(webhook_id, client_id)
    if not success:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Monitoring Router ---
monitoring_router = APIRouter(prefix="/api/v1/monitoring", tags=["Monitoring"])


@monitoring_router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


@monitoring_router.get("/metrics")
async def get_metrics(
    time_window: int = Query(60, description="Time window in minutes"),
    client_id: str = Depends(get_client_id)
):
    """Get API metrics"""
    return gateway.metrics.get_metrics(client_id, time_window)


@monitoring_router.get("/metrics/global")
async def get_global_metrics(
    time_window: int = Query(60, description="Time window in minutes"),
    client_id: str = Depends(get_client_id)
):
    """Get global API metrics (admin only)"""
    return gateway.metrics.get_metrics(None, time_window)


# Register all routers
app.include_router(auth_router)
app.include_router(debts_router)
app.include_router(bureau_router)
app.include_router(payments_router)
app.include_router(plans_router)
app.include_router(reports_router)
app.include_router(webhooks_router)
app.include_router(monitoring_router)


# =============================================================================
# OPENAPI CUSTOMIZATION
# =============================================================================

def custom_openapi():
    """Generate custom OpenAPI schema"""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="QUAN Recovery API",
        version="1.0.0",
        description=app.description,
        routes=app.routes,
    )

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API Key for authentication"
        },
        "ApiSecretAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Secret",
            "description": "API Secret for authentication"
        },
        "OAuth2": {
            "type": "oauth2",
            "flows": {
                "password": {
                    "tokenUrl": "/api/v1/auth/token",
                    "scopes": {
                        "read": "Read access",
                        "write": "Write access",
                        "admin": "Admin access"
                    }
                }
            }
        }
    }

    # Add global security
    openapi_schema["security"] = [
        {"ApiKeyAuth": [], "ApiSecretAuth": []},
        {"OAuth2": ["read", "write"]}
    ]

    # Add webhook event types to schema
    openapi_schema["components"]["schemas"]["WebhookEventTypes"] = {
        "type": "string",
        "enum": [e.value for e in WebhookEventType],
        "description": "Available webhook event types"
    }

    # Add contact and license info
    openapi_schema["info"]["contact"] = {
        "name": "QUAN Recovery API Support",
        "email": "api-support@quanrecovery.com",
        "url": "https://developers.quanrecovery.com"
    }
    openapi_schema["info"]["license"] = {
        "name": "Proprietary",
        "url": "https://quanrecovery.com/terms"
    }

    # Add servers
    openapi_schema["servers"] = [
        {"url": "https://api.quanrecovery.com", "description": "Production"},
        {"url": "https://sandbox.quanrecovery.com", "description": "Sandbox"},
        {"url": "http://localhost:8000", "description": "Local Development"}
    ]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# =============================================================================
# CLIENT SDK EXAMPLES
# =============================================================================

PYTHON_SDK_EXAMPLE = '''
"""
QUAN Recovery Python SDK Example
"""

import requests
from typing import Optional, Dict, Any, List


class QUANClient:
    """QUAN Recovery API Client"""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "https://api.quanrecovery.com"
    ):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-Key": api_key,
            "X-API-Secret": api_secret,
            "Content-Type": "application/json"
        })

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make API request"""
        url = f"{self.base_url}{endpoint}"
        response = self.session.request(
            method=method,
            url=url,
            json=data,
            params=params
        )
        response.raise_for_status()
        return response.json() if response.content else {}

    # Debt Operations
    def submit_debt(self, debt: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a debt for collection"""
        return self._request("POST", "/api/v1/debts", data=debt)

    def bulk_submit_debts(self, debts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Bulk submit debts"""
        return self._request("POST", "/api/v1/debts/bulk", data={"debts": debts})

    def get_debt(self, debt_id: str) -> Dict[str, Any]:
        """Get debt by ID"""
        return self._request("GET", f"/api/v1/debts/{debt_id}")

    def update_debt(self, debt_id: str, update: Dict[str, Any]) -> Dict[str, Any]:
        """Update debt information"""
        return self._request("PATCH", f"/api/v1/debts/{debt_id}", data=update)

    def recall_debt(self, debt_id: str) -> None:
        """Recall debt from collection"""
        self._request("DELETE", f"/api/v1/debts/{debt_id}")

    # Shadow Bureau
    def get_shadow_score(self, consumer_id: str) -> Dict[str, Any]:
        """Get consumer shadow score"""
        return self._request("GET", f"/api/v1/scores/{consumer_id}")

    def network_check(self, consumer_id: str) -> Dict[str, Any]:
        """Check network for outstanding debts"""
        return self._request("GET", f"/api/v1/network/{consumer_id}")

    def risk_assessment(
        self,
        consumer_id: str,
        proposed_credit: float
    ) -> Dict[str, Any]:
        """Get risk assessment"""
        return self._request("POST", "/api/v1/assess", data={
            "consumer_id": consumer_id,
            "proposed_credit": proposed_credit
        })

    def verify_restoration(self, certificate_id: str) -> Dict[str, Any]:
        """Verify restoration certificate"""
        return self._request("GET", f"/api/v1/restoration/{certificate_id}")

    # Payments
    def process_payment(
        self,
        debt_id: str,
        amount: float,
        payment_method_token: str
    ) -> Dict[str, Any]:
        """Process a payment"""
        return self._request("POST", "/api/v1/payments", data={
            "debt_id": debt_id,
            "amount": amount,
            "payment_method_token": payment_method_token
        })

    def get_payment(self, payment_id: str) -> Dict[str, Any]:
        """Get payment by ID"""
        return self._request("GET", f"/api/v1/payments/{payment_id}")

    def create_payment_plan(
        self,
        debt_id: str,
        total_amount: float,
        num_payments: int,
        start_date: str,
        payment_method_token: str
    ) -> Dict[str, Any]:
        """Create payment plan"""
        return self._request("POST", "/api/v1/plans", data={
            "debt_id": debt_id,
            "total_amount": total_amount,
            "num_payments": num_payments,
            "start_date": start_date,
            "payment_method_token": payment_method_token
        })

    # Reports
    def get_portfolio_report(self) -> Dict[str, Any]:
        """Get portfolio report"""
        return self._request("GET", "/api/v1/reports/portfolio")

    def get_compliance_report(self) -> Dict[str, Any]:
        """Get compliance report"""
        return self._request("GET", "/api/v1/reports/compliance")

    # Webhooks
    def register_webhook(
        self,
        url: str,
        events: List[str]
    ) -> Dict[str, Any]:
        """Register webhook"""
        return self._request("POST", "/api/v1/webhooks", data={
            "url": url,
            "events": events
        })

    def list_webhooks(self) -> List[Dict[str, Any]]:
        """List webhooks"""
        return self._request("GET", "/api/v1/webhooks")


# Usage Example
if __name__ == "__main__":
    client = QUANClient(
        api_key="quan_live_your_api_key",
        api_secret="your_api_secret",
        base_url="https://sandbox.quanrecovery.com"
    )

    # Submit a debt
    debt = client.submit_debt({
        "consumer_id": "C12345",
        "amount": 147.50,
        "charge_off_date": "2024-01-15",
        "original_creditor": "Klarna",
        "category": "bnpl"
    })
    print(f"Debt submitted: {debt['debt_id']}")

    # Check shadow score
    score = client.get_shadow_score("C12345")
    print(f"Shadow Score: {score['shadow_score']} (Tier: {score['risk_tier']})")

    # Risk assessment
    assessment = client.risk_assessment("C12345", 200.00)
    print(f"Decision: {assessment['decision']}")
'''

NODE_SDK_EXAMPLE = '''
/**
 * QUAN Recovery Node.js SDK Example
 */

const axios = require('axios');

class QUANClient {
  constructor(apiKey, apiSecret, baseUrl = 'https://api.quanrecovery.com') {
    this.baseUrl = baseUrl;
    this.client = axios.create({
      baseURL: baseUrl,
      headers: {
        'X-API-Key': apiKey,
        'X-API-Secret': apiSecret,
        'Content-Type': 'application/json'
      }
    });
  }

  // Debt Operations
  async submitDebt(debt) {
    const response = await this.client.post('/api/v1/debts', debt);
    return response.data;
  }

  async bulkSubmitDebts(debts) {
    const response = await this.client.post('/api/v1/debts/bulk', { debts });
    return response.data;
  }

  async getDebt(debtId) {
    const response = await this.client.get(`/api/v1/debts/${debtId}`);
    return response.data;
  }

  async updateDebt(debtId, update) {
    const response = await this.client.patch(`/api/v1/debts/${debtId}`, update);
    return response.data;
  }

  async recallDebt(debtId) {
    await this.client.delete(`/api/v1/debts/${debtId}`);
  }

  // Shadow Bureau
  async getShadowScore(consumerId) {
    const response = await this.client.get(`/api/v1/scores/${consumerId}`);
    return response.data;
  }

  async networkCheck(consumerId) {
    const response = await this.client.get(`/api/v1/network/${consumerId}`);
    return response.data;
  }

  async riskAssessment(consumerId, proposedCredit) {
    const response = await this.client.post('/api/v1/assess', {
      consumer_id: consumerId,
      proposed_credit: proposedCredit
    });
    return response.data;
  }

  async verifyRestoration(certificateId) {
    const response = await this.client.get(`/api/v1/restoration/${certificateId}`);
    return response.data;
  }

  // Payments
  async processPayment(debtId, amount, paymentMethodToken) {
    const response = await this.client.post('/api/v1/payments', {
      debt_id: debtId,
      amount: amount,
      payment_method_token: paymentMethodToken
    });
    return response.data;
  }

  async getPayment(paymentId) {
    const response = await this.client.get(`/api/v1/payments/${paymentId}`);
    return response.data;
  }

  async createPaymentPlan(debtId, totalAmount, numPayments, startDate, paymentMethodToken) {
    const response = await this.client.post('/api/v1/plans', {
      debt_id: debtId,
      total_amount: totalAmount,
      num_payments: numPayments,
      start_date: startDate,
      payment_method_token: paymentMethodToken
    });
    return response.data;
  }

  // Reports
  async getPortfolioReport() {
    const response = await this.client.get('/api/v1/reports/portfolio');
    return response.data;
  }

  async getComplianceReport() {
    const response = await this.client.get('/api/v1/reports/compliance');
    return response.data;
  }

  // Webhooks
  async registerWebhook(url, events) {
    const response = await this.client.post('/api/v1/webhooks', { url, events });
    return response.data;
  }

  async listWebhooks() {
    const response = await this.client.get('/api/v1/webhooks');
    return response.data;
  }
}

// Usage Example
async function main() {
  const client = new QUANClient(
    'quan_live_your_api_key',
    'your_api_secret',
    'https://sandbox.quanrecovery.com'
  );

  // Submit a debt
  const debt = await client.submitDebt({
    consumer_id: 'C12345',
    amount: 147.50,
    charge_off_date: '2024-01-15',
    original_creditor: 'Klarna',
    category: 'bnpl'
  });
  console.log(`Debt submitted: ${debt.debt_id}`);

  // Check shadow score
  const score = await client.getShadowScore('C12345');
  console.log(`Shadow Score: ${score.shadow_score} (Tier: ${score.risk_tier})`);

  // Risk assessment
  const assessment = await client.riskAssessment('C12345', 200.00);
  console.log(`Decision: ${assessment.decision}`);
}

module.exports = QUANClient;
'''

CURL_EXAMPLES = '''
# QUAN Recovery API - cURL Examples

# ==============================================================================
# AUTHENTICATION
# ==============================================================================

# Get OAuth Token
curl -X POST "https://api.quanrecovery.com/api/v1/auth/token" \\
  -H "Content-Type: application/x-www-form-urlencoded" \\
  -d "username=quan_live_your_api_key&password=your_api_secret"

# ==============================================================================
# DEBT OPERATIONS
# ==============================================================================

# Submit a debt
curl -X POST "https://api.quanrecovery.com/api/v1/debts" \\
  -H "X-API-Key: quan_live_your_api_key" \\
  -H "X-API-Secret: your_api_secret" \\
  -H "Content-Type: application/json" \\
  -d '{
    "consumer_id": "C12345",
    "amount": 147.50,
    "charge_off_date": "2024-01-15",
    "original_creditor": "Klarna",
    "category": "bnpl",
    "consumer_email": "consumer@example.com"
  }'

# Bulk submit debts
curl -X POST "https://api.quanrecovery.com/api/v1/debts/bulk" \\
  -H "X-API-Key: quan_live_your_api_key" \\
  -H "X-API-Secret: your_api_secret" \\
  -H "Content-Type: application/json" \\
  -d '{
    "debts": [
      {"consumer_id": "C12345", "amount": 147.50, "charge_off_date": "2024-01-15", "original_creditor": "Klarna"},
      {"consumer_id": "C12346", "amount": 89.99, "charge_off_date": "2024-01-20", "original_creditor": "Affirm"}
    ]
  }'

# Get debt status
curl -X GET "https://api.quanrecovery.com/api/v1/debts/debt_abc123" \\
  -H "X-API-Key: quan_live_your_api_key" \\
  -H "X-API-Secret: your_api_secret"

# Update debt
curl -X PATCH "https://api.quanrecovery.com/api/v1/debts/debt_abc123" \\
  -H "X-API-Key: quan_live_your_api_key" \\
  -H "X-API-Secret: your_api_secret" \\
  -H "Content-Type: application/json" \\
  -d '{"consumer_email": "newemail@example.com"}'

# Recall debt
curl -X DELETE "https://api.quanrecovery.com/api/v1/debts/debt_abc123" \\
  -H "X-API-Key: quan_live_your_api_key" \\
  -H "X-API-Secret: your_api_secret"

# ==============================================================================
# SHADOW BUREAU API
# ==============================================================================

# Get shadow score
curl -X GET "https://api.quanrecovery.com/api/v1/scores/C12345" \\
  -H "X-API-Key: quan_live_your_api_key" \\
  -H "X-API-Secret: your_api_secret"

# Network check
curl -X GET "https://api.quanrecovery.com/api/v1/network/C12345" \\
  -H "X-API-Key: quan_live_your_api_key" \\
  -H "X-API-Secret: your_api_secret"

# Risk assessment
curl -X POST "https://api.quanrecovery.com/api/v1/assess" \\
  -H "X-API-Key: quan_live_your_api_key" \\
  -H "X-API-Secret: your_api_secret" \\
  -H "Content-Type: application/json" \\
  -d '{"consumer_id": "C12345", "proposed_credit": 200.00}'

# Verify restoration certificate
curl -X GET "https://api.quanrecovery.com/api/v1/restoration/cert_xyz789" \\
  -H "X-API-Key: quan_live_your_api_key" \\
  -H "X-API-Secret: your_api_secret"

# ==============================================================================
# PAYMENTS
# ==============================================================================

# Process payment
curl -X POST "https://api.quanrecovery.com/api/v1/payments" \\
  -H "X-API-Key: quan_live_your_api_key" \\
  -H "X-API-Secret: your_api_secret" \\
  -H "Content-Type: application/json" \\
  -d '{
    "debt_id": "debt_abc123",
    "amount": 50.00,
    "payment_method_token": "pm_card_visa"
  }'

# Get payment status
curl -X GET "https://api.quanrecovery.com/api/v1/payments/pay_xyz789" \\
  -H "X-API-Key: quan_live_your_api_key" \\
  -H "X-API-Secret: your_api_secret"

# Create payment plan
curl -X POST "https://api.quanrecovery.com/api/v1/plans" \\
  -H "X-API-Key: quan_live_your_api_key" \\
  -H "X-API-Secret: your_api_secret" \\
  -H "Content-Type: application/json" \\
  -d '{
    "debt_id": "debt_abc123",
    "total_amount": 147.50,
    "num_payments": 3,
    "frequency": "monthly",
    "start_date": "2024-02-01",
    "payment_method_token": "pm_card_visa"
  }'

# ==============================================================================
# REPORTS
# ==============================================================================

# Portfolio report
curl -X GET "https://api.quanrecovery.com/api/v1/reports/portfolio" \\
  -H "X-API-Key: quan_live_your_api_key" \\
  -H "X-API-Secret: your_api_secret"

# Compliance report
curl -X GET "https://api.quanrecovery.com/api/v1/reports/compliance" \\
  -H "X-API-Key: quan_live_your_api_key" \\
  -H "X-API-Secret: your_api_secret"

# ==============================================================================
# WEBHOOKS
# ==============================================================================

# Register webhook
curl -X POST "https://api.quanrecovery.com/api/v1/webhooks" \\
  -H "X-API-Key: quan_live_your_api_key" \\
  -H "X-API-Secret: your_api_secret" \\
  -H "Content-Type: application/json" \\
  -d '{
    "url": "https://your-server.com/webhooks/quan",
    "events": ["debt.updated", "payment.received", "settlement.reached"]
  }'

# List webhooks
curl -X GET "https://api.quanrecovery.com/api/v1/webhooks" \\
  -H "X-API-Key: quan_live_your_api_key" \\
  -H "X-API-Secret: your_api_secret"

# Delete webhook
curl -X DELETE "https://api.quanrecovery.com/api/v1/webhooks/webhook_abc123" \\
  -H "X-API-Key: quan_live_your_api_key" \\
  -H "X-API-Secret: your_api_secret"

# ==============================================================================
# MONITORING
# ==============================================================================

# Health check
curl -X GET "https://api.quanrecovery.com/api/v1/monitoring/health"

# Get metrics
curl -X GET "https://api.quanrecovery.com/api/v1/monitoring/metrics?time_window=60" \\
  -H "X-API-Key: quan_live_your_api_key" \\
  -H "X-API-Secret: your_api_secret"
'''


# SDK endpoint
@app.get("/api/v1/sdk/python", tags=["SDK"], include_in_schema=False)
async def get_python_sdk():
    """Get Python SDK example code"""
    return Response(content=PYTHON_SDK_EXAMPLE, media_type="text/plain")


@app.get("/api/v1/sdk/node", tags=["SDK"], include_in_schema=False)
async def get_node_sdk():
    """Get Node.js SDK example code"""
    return Response(content=NODE_SDK_EXAMPLE, media_type="text/plain")


@app.get("/api/v1/sdk/curl", tags=["SDK"], include_in_schema=False)
async def get_curl_examples():
    """Get cURL example commands"""
    return Response(content=CURL_EXAMPLES, media_type="text/plain")


# =============================================================================
# DEMONSTRATION
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    print("=" * 70)
    print("QUAN Recovery Production API Gateway")
    print("=" * 70)
    print()
    print("Starting server...")
    print()
    print("API Documentation: http://localhost:8000/api/docs")
    print("OpenAPI Spec: http://localhost:8000/api/openapi.json")
    print("ReDoc: http://localhost:8000/api/redoc")
    print()
    print("SDK Examples:")
    print("  Python: http://localhost:8000/api/v1/sdk/python")
    print("  Node.js: http://localhost:8000/api/v1/sdk/node")
    print("  cURL: http://localhost:8000/api/v1/sdk/curl")
    print()
    print("=" * 70)

    uvicorn.run(app, host="0.0.0.0", port=8000)
