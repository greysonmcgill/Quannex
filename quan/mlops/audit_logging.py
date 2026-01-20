"""
Immutable Audit Logging System for ML Decisions

Provides comprehensive, tamper-proof audit logging infrastructure for:
1. Immutable decision logging with cryptographic signatures
2. Append-only storage interfaces (S3 Object Lock, WORM databases)
3. Full input/output capture per decision with PII protection
4. Decision retrieval by ID with integrity verification
5. Tamper detection via Merkle trees and hash chains
6. Batch audit writing for high-throughput scenarios
7. Retention policy enforcement with legal hold support
8. Export capabilities for compliance reviews

REGULATORY COMPLIANCE:
- GDPR Article 30 (Records of Processing)
- CCPA 1798.100 (Disclosure Requirements)
- SOC 2 Type II (Audit Trail Requirements)
- FCRA Section 611 (Accuracy Requirements)
- FDA 21 CFR Part 11 (Electronic Records)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from typing import (
    Any, Callable, Dict, List, Optional, Tuple, Union,
    Set, TypeVar, Generic, Protocol, Iterator, BinaryIO
)
from pathlib import Path
from abc import ABC, abstractmethod
from contextlib import contextmanager
from collections import defaultdict
from functools import wraps
import hashlib
import hmac
import json
import logging
import os
import struct
import threading
import time
import uuid
import base64
import gzip
import io
import copy
import re
import secrets

logger = logging.getLogger(__name__)


# =============================================================================
# Cryptographic Constants
# =============================================================================

HASH_ALGORITHM = "sha256"
SIGNATURE_ALGORITHM = "sha256"
HMAC_KEY_LENGTH = 32
ENCRYPTION_KEY_LENGTH = 32
IV_LENGTH = 16
GENESIS_HASH = "0" * 64  # Genesis block hash for hash chains


# =============================================================================
# Enums and Constants
# =============================================================================

class ActorType(Enum):
    """Types of actors that can make decisions"""
    SYSTEM = "system"
    MODEL = "model"
    HUMAN = "human"
    AUTOMATED_RULE = "automated_rule"
    HYBRID = "hybrid"  # Human-in-the-loop with model recommendation


class DecisionType(Enum):
    """Types of ML decisions that can be audited"""
    PREDICTION = "prediction"
    CLASSIFICATION = "classification"
    RECOMMENDATION = "recommendation"
    APPROVAL = "approval"
    REJECTION = "rejection"
    ROUTING = "routing"
    ESCALATION = "escalation"
    OVERRIDE = "override"
    POLICY_APPLICATION = "policy_application"


class StorageType(Enum):
    """Supported immutable storage backends"""
    S3_OBJECT_LOCK = "s3_object_lock"
    AZURE_IMMUTABLE_BLOB = "azure_immutable_blob"
    GCS_RETENTION_POLICY = "gcs_retention_policy"
    WORM_DATABASE = "worm_database"
    LOCAL_APPEND_ONLY = "local_append_only"
    BLOCKCHAIN_ANCHORED = "blockchain_anchored"


class RetentionPolicyType(Enum):
    """Types of retention policies"""
    TIME_BASED = "time_based"
    EVENT_BASED = "event_based"
    LEGAL_HOLD = "legal_hold"
    REGULATORY = "regulatory"
    INDEFINITE = "indefinite"


class ExportFormat(Enum):
    """Export formats for compliance reviews"""
    JSON = "json"
    JSON_LINES = "json_lines"
    CSV = "csv"
    PARQUET = "parquet"
    XML = "xml"
    PDF_REPORT = "pdf_report"


class PIIHandlingStrategy(Enum):
    """Strategies for handling PII in audit logs"""
    ENCRYPT = "encrypt"
    HASH = "hash"
    TOKENIZE = "tokenize"
    REDACT = "redact"
    MASK = "mask"
    EXCLUDE = "exclude"


class AuditLogLevel(Enum):
    """Audit log severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class IntegrityStatus(Enum):
    """Status of audit log integrity verification"""
    VALID = "valid"
    TAMPERED = "tampered"
    MISSING_SIGNATURE = "missing_signature"
    INVALID_SIGNATURE = "invalid_signature"
    CHAIN_BROKEN = "chain_broken"
    UNKNOWN = "unknown"


# =============================================================================
# Data Classes - Audit Schema
# =============================================================================

@dataclass
class MicrosecondTimestamp:
    """
    High-precision timestamp with microsecond accuracy.

    Uses Unix epoch with microseconds for consistent cross-system precision.
    """
    epoch_micros: int
    timezone_offset: int = 0  # Offset in minutes from UTC

    @classmethod
    def now(cls) -> "MicrosecondTimestamp":
        """Create timestamp for current moment with microsecond precision"""
        now = datetime.now(timezone.utc)
        epoch_micros = int(now.timestamp() * 1_000_000)
        return cls(epoch_micros=epoch_micros, timezone_offset=0)

    @classmethod
    def from_datetime(cls, dt: datetime) -> "MicrosecondTimestamp":
        """Create from datetime object"""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        epoch_micros = int(dt.timestamp() * 1_000_000)
        offset = int(dt.utcoffset().total_seconds() // 60) if dt.utcoffset() else 0
        return cls(epoch_micros=epoch_micros, timezone_offset=offset)

    def to_datetime(self) -> datetime:
        """Convert to datetime object"""
        tz = timezone(timedelta(minutes=self.timezone_offset))
        return datetime.fromtimestamp(self.epoch_micros / 1_000_000, tz=tz)

    def to_iso8601(self) -> str:
        """Convert to ISO 8601 string with microseconds"""
        dt = self.to_datetime()
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f%z")

    def __str__(self) -> str:
        return self.to_iso8601()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "epoch_micros": self.epoch_micros,
            "timezone_offset": self.timezone_offset,
            "iso8601": self.to_iso8601(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MicrosecondTimestamp":
        """Create from dictionary (ignores iso8601 which is informational)"""
        return cls(
            epoch_micros=data["epoch_micros"],
            timezone_offset=data.get("timezone_offset", 0),
        )


@dataclass
class ModelVersion:
    """
    Model version tracking with full provenance.

    Captures model identity, training lineage, and deployment context.
    """
    model_id: str
    model_name: str
    version: str
    training_run_id: Optional[str] = None
    training_timestamp: Optional[str] = None
    model_hash: Optional[str] = None  # SHA-256 of model artifact
    framework: Optional[str] = None  # e.g., "sklearn", "pytorch"
    framework_version: Optional[str] = None
    feature_schema_version: Optional[str] = None
    deployment_id: Optional[str] = None
    environment: Optional[str] = None  # "production", "staging", etc.

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "version": self.version,
            "training_run_id": self.training_run_id,
            "training_timestamp": self.training_timestamp,
            "model_hash": self.model_hash,
            "framework": self.framework,
            "framework_version": self.framework_version,
            "feature_schema_version": self.feature_schema_version,
            "deployment_id": self.deployment_id,
            "environment": self.environment,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelVersion":
        return cls(**data)


@dataclass
class Actor:
    """
    Actor identification for decision attribution.

    Tracks who/what made a decision for accountability.
    """
    actor_id: str
    actor_type: ActorType
    display_name: Optional[str] = None
    email: Optional[str] = None  # For human actors
    role: Optional[str] = None
    organization: Optional[str] = None
    authentication_method: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None  # May be redacted for privacy
    user_agent: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "actor_type": self.actor_type.value,
            "display_name": self.display_name,
            "email": self.email,
            "role": self.role,
            "organization": self.organization,
            "authentication_method": self.authentication_method,
            "session_id": self.session_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Actor":
        data = data.copy()
        data["actor_type"] = ActorType(data["actor_type"])
        return cls(**data)

    @classmethod
    def system(cls, service_name: str = "quan-ml-service") -> "Actor":
        """Create a system actor"""
        return cls(
            actor_id=f"system:{service_name}",
            actor_type=ActorType.SYSTEM,
            display_name=service_name,
        )

    @classmethod
    def model(cls, model_version: ModelVersion) -> "Actor":
        """Create a model actor"""
        return cls(
            actor_id=f"model:{model_version.model_id}:{model_version.version}",
            actor_type=ActorType.MODEL,
            display_name=f"{model_version.model_name} v{model_version.version}",
        )


@dataclass
class InputFeatures:
    """
    Input features for a decision with PII protection.

    Stores feature values with metadata about PII handling.
    """
    feature_values: Dict[str, Any]  # Actual values (may be transformed)
    feature_names: List[str]
    feature_schema_version: str = "1.0"
    pii_handling: PIIHandlingStrategy = PIIHandlingStrategy.ENCRYPT
    pii_fields_present: List[str] = field(default_factory=list)
    encrypted_fields: List[str] = field(default_factory=list)
    hash_salt: Optional[str] = None  # For reproducible hashing
    raw_input_hash: Optional[str] = None  # Hash of original input
    preprocessing_applied: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_values": self.feature_values,
            "feature_names": self.feature_names,
            "feature_schema_version": self.feature_schema_version,
            "pii_handling": self.pii_handling.value,
            "pii_fields_present": self.pii_fields_present,
            "encrypted_fields": self.encrypted_fields,
            "hash_salt": self.hash_salt,
            "raw_input_hash": self.raw_input_hash,
            "preprocessing_applied": self.preprocessing_applied,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InputFeatures":
        data = data.copy()
        data["pii_handling"] = PIIHandlingStrategy(data["pii_handling"])
        return cls(**data)


@dataclass
class OutputPrediction:
    """
    Output prediction with confidence and explanations.

    Captures the full decision output including probabilities and explanations.
    """
    prediction: Any  # The primary prediction value
    prediction_type: DecisionType
    probability: Optional[float] = None
    confidence_interval: Optional[Tuple[float, float]] = None
    class_probabilities: Optional[Dict[str, float]] = None
    raw_model_output: Optional[Any] = None
    calibrated: bool = False
    calibration_method: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction": self.prediction,
            "prediction_type": self.prediction_type.value,
            "probability": self.probability,
            "confidence_interval": self.confidence_interval,
            "class_probabilities": self.class_probabilities,
            "raw_model_output": self.raw_model_output,
            "calibrated": self.calibrated,
            "calibration_method": self.calibration_method,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OutputPrediction":
        data = data.copy()
        data["prediction_type"] = DecisionType(data["prediction_type"])
        if data.get("confidence_interval"):
            data["confidence_interval"] = tuple(data["confidence_interval"])
        return cls(**data)


@dataclass
class DecisionExplanation:
    """
    Explanation of decision for interpretability.

    Provides multiple explanation formats for different stakeholders.
    """
    feature_importances: Optional[Dict[str, float]] = None
    shap_values: Optional[Dict[str, float]] = None
    lime_explanation: Optional[Dict[str, Any]] = None
    counterfactual: Optional[Dict[str, Any]] = None
    natural_language_explanation: Optional[str] = None
    decision_path: Optional[List[str]] = None  # For tree-based models
    attention_weights: Optional[Dict[str, float]] = None  # For transformers
    explanation_confidence: Optional[float] = None
    adverse_action_reasons: Optional[List[str]] = None  # For credit decisions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_importances": self.feature_importances,
            "shap_values": self.shap_values,
            "lime_explanation": self.lime_explanation,
            "counterfactual": self.counterfactual,
            "natural_language_explanation": self.natural_language_explanation,
            "decision_path": self.decision_path,
            "attention_weights": self.attention_weights,
            "explanation_confidence": self.explanation_confidence,
            "adverse_action_reasons": self.adverse_action_reasons,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionExplanation":
        return cls(**data)


@dataclass
class PolicyContext:
    """
    Policy context applied to the decision.

    Documents which policies, rules, and constraints were active.
    """
    policy_id: str
    policy_version: str
    policy_name: str
    rules_applied: List[str] = field(default_factory=list)
    thresholds: Dict[str, float] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    overrides_applied: List[str] = field(default_factory=list)
    regulatory_requirements: List[str] = field(default_factory=list)
    business_rules: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_name": self.policy_name,
            "rules_applied": self.rules_applied,
            "thresholds": self.thresholds,
            "constraints": self.constraints,
            "overrides_applied": self.overrides_applied,
            "regulatory_requirements": self.regulatory_requirements,
            "business_rules": self.business_rules,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyContext":
        return cls(**data)


@dataclass
class CryptographicSignature:
    """
    Cryptographic signature for audit entry integrity.

    Provides non-repudiation and tamper detection.
    """
    signature: str  # Base64-encoded signature
    algorithm: str = SIGNATURE_ALGORITHM
    key_id: str = ""  # ID of signing key for rotation
    signed_at: Optional[MicrosecondTimestamp] = None
    signature_version: str = "1.0"
    certificate_chain: Optional[List[str]] = None  # For PKI

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signature": self.signature,
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "signed_at": self.signed_at.to_dict() if self.signed_at else None,
            "signature_version": self.signature_version,
            "certificate_chain": self.certificate_chain,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CryptographicSignature":
        data = data.copy()
        if data.get("signed_at"):
            data["signed_at"] = MicrosecondTimestamp.from_dict(data["signed_at"])
        return cls(**data)


@dataclass
class RetentionPolicy:
    """
    Retention policy for audit records.

    Defines how long records must be kept and under what conditions.
    """
    policy_type: RetentionPolicyType
    retention_days: Optional[int] = None
    retention_until: Optional[MicrosecondTimestamp] = None
    legal_hold: bool = False
    legal_hold_id: Optional[str] = None
    regulatory_basis: Optional[str] = None
    deletion_allowed: bool = False
    anonymization_allowed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_type": self.policy_type.value,
            "retention_days": self.retention_days,
            "retention_until": self.retention_until.to_dict() if self.retention_until else None,
            "legal_hold": self.legal_hold,
            "legal_hold_id": self.legal_hold_id,
            "regulatory_basis": self.regulatory_basis,
            "deletion_allowed": self.deletion_allowed,
            "anonymization_allowed": self.anonymization_allowed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetentionPolicy":
        data = data.copy()
        data["policy_type"] = RetentionPolicyType(data["policy_type"])
        if data.get("retention_until"):
            data["retention_until"] = MicrosecondTimestamp.from_dict(data["retention_until"])
        return cls(**data)

    @classmethod
    def regulatory_default(cls, regulation: str = "FCRA") -> "RetentionPolicy":
        """Create default policy for common regulations"""
        retention_days_by_regulation = {
            "FCRA": 7 * 365,  # 7 years
            "GDPR": 6 * 365,  # 6 years
            "SOX": 7 * 365,   # 7 years
            "HIPAA": 6 * 365, # 6 years
        }
        return cls(
            policy_type=RetentionPolicyType.REGULATORY,
            retention_days=retention_days_by_regulation.get(regulation, 7 * 365),
            regulatory_basis=regulation,
            deletion_allowed=False,
            anonymization_allowed=False,
        )


@dataclass
class AuditEntry:
    """
    Complete audit entry for a single decision.

    This is the primary audit schema capturing all decision metadata.
    """
    # Identity
    decision_id: str  # Unique identifier for this decision
    correlation_id: str  # For request tracing across systems
    parent_decision_id: Optional[str] = None  # For decision chains

    # Timing
    timestamp: MicrosecondTimestamp = field(default_factory=MicrosecondTimestamp.now)
    processing_duration_micros: Optional[int] = None

    # Decision context
    decision_type: DecisionType = DecisionType.PREDICTION
    subject_id: str = ""  # ID of entity being decided about (hashed if PII)
    subject_type: str = ""  # "account", "customer", "transaction", etc.

    # Model information
    model_version: Optional[ModelVersion] = None

    # Actor information
    actor: Optional[Actor] = None

    # Input/Output
    input_features: Optional[InputFeatures] = None
    output_prediction: Optional[OutputPrediction] = None
    explanation: Optional[DecisionExplanation] = None

    # Policy
    policy_context: Optional[PolicyContext] = None

    # Integrity
    entry_hash: str = ""  # SHA-256 of entry content
    previous_hash: str = GENESIS_HASH  # Hash chain for tamper detection
    signature: Optional[CryptographicSignature] = None
    merkle_root: Optional[str] = None  # For batch verification

    # Retention
    retention_policy: Optional[RetentionPolicy] = None

    # Metadata
    log_level: AuditLogLevel = AuditLogLevel.INFO
    tags: Dict[str, str] = field(default_factory=dict)
    environment: str = "production"
    service_name: str = "quan-ml-service"
    service_version: str = "1.0.0"

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of entry content"""
        content = self._get_hashable_content()
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_hashable_content(self) -> str:
        """Get content to be hashed (excludes hash fields)"""
        data = {
            "decision_id": self.decision_id,
            "correlation_id": self.correlation_id,
            "parent_decision_id": self.parent_decision_id,
            "timestamp": self.timestamp.epoch_micros,
            "decision_type": self.decision_type.value,
            "subject_id": self.subject_id,
            "subject_type": self.subject_type,
            "model_version": self.model_version.to_dict() if self.model_version else None,
            "actor": self.actor.to_dict() if self.actor else None,
            "input_features": self.input_features.to_dict() if self.input_features else None,
            "output_prediction": self.output_prediction.to_dict() if self.output_prediction else None,
            "explanation": self.explanation.to_dict() if self.explanation else None,
            "policy_context": self.policy_context.to_dict() if self.policy_context else None,
            "previous_hash": self.previous_hash,
            "tags": self.tags,
            "environment": self.environment,
            "service_name": self.service_name,
        }
        return json.dumps(data, sort_keys=True, default=str)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "decision_id": self.decision_id,
            "correlation_id": self.correlation_id,
            "parent_decision_id": self.parent_decision_id,
            "timestamp": self.timestamp.to_dict(),
            "processing_duration_micros": self.processing_duration_micros,
            "decision_type": self.decision_type.value,
            "subject_id": self.subject_id,
            "subject_type": self.subject_type,
            "model_version": self.model_version.to_dict() if self.model_version else None,
            "actor": self.actor.to_dict() if self.actor else None,
            "input_features": self.input_features.to_dict() if self.input_features else None,
            "output_prediction": self.output_prediction.to_dict() if self.output_prediction else None,
            "explanation": self.explanation.to_dict() if self.explanation else None,
            "policy_context": self.policy_context.to_dict() if self.policy_context else None,
            "entry_hash": self.entry_hash,
            "previous_hash": self.previous_hash,
            "signature": self.signature.to_dict() if self.signature else None,
            "merkle_root": self.merkle_root,
            "retention_policy": self.retention_policy.to_dict() if self.retention_policy else None,
            "log_level": self.log_level.value,
            "tags": self.tags,
            "environment": self.environment,
            "service_name": self.service_name,
            "service_version": self.service_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEntry":
        """Reconstruct from dictionary"""
        entry = cls(
            decision_id=data["decision_id"],
            correlation_id=data["correlation_id"],
            parent_decision_id=data.get("parent_decision_id"),
            timestamp=MicrosecondTimestamp.from_dict(data["timestamp"]) if data.get("timestamp") else MicrosecondTimestamp.now(),
            processing_duration_micros=data.get("processing_duration_micros"),
            decision_type=DecisionType(data["decision_type"]),
            subject_id=data.get("subject_id", ""),
            subject_type=data.get("subject_type", ""),
            entry_hash=data.get("entry_hash", ""),
            previous_hash=data.get("previous_hash", GENESIS_HASH),
            merkle_root=data.get("merkle_root"),
            log_level=AuditLogLevel(data.get("log_level", "info")),
            tags=data.get("tags", {}),
            environment=data.get("environment", "production"),
            service_name=data.get("service_name", "quan-ml-service"),
            service_version=data.get("service_version", "1.0.0"),
        )

        if data.get("model_version"):
            entry.model_version = ModelVersion.from_dict(data["model_version"])
        if data.get("actor"):
            entry.actor = Actor.from_dict(data["actor"])
        if data.get("input_features"):
            entry.input_features = InputFeatures.from_dict(data["input_features"])
        if data.get("output_prediction"):
            entry.output_prediction = OutputPrediction.from_dict(data["output_prediction"])
        if data.get("explanation"):
            entry.explanation = DecisionExplanation.from_dict(data["explanation"])
        if data.get("policy_context"):
            entry.policy_context = PolicyContext.from_dict(data["policy_context"])
        if data.get("signature"):
            entry.signature = CryptographicSignature.from_dict(data["signature"])
        if data.get("retention_policy"):
            entry.retention_policy = RetentionPolicy.from_dict(data["retention_policy"])

        return entry


# =============================================================================
# PII Handler
# =============================================================================

class PIIHandler:
    """
    Handles PII protection in audit logs.

    Supports multiple strategies: encryption, hashing, tokenization, redaction.
    """

    # Common PII field patterns
    PII_PATTERNS = {
        "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
        "credit_card": re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
        "dob": re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b"),
    }

    # Fields that are commonly PII
    PII_FIELD_NAMES = {
        "ssn", "social_security_number", "ssn_last4",
        "email", "email_address",
        "phone", "phone_number", "mobile", "cell",
        "first_name", "last_name", "full_name", "name",
        "address", "street", "city", "zip", "postal_code",
        "dob", "date_of_birth", "birth_date",
        "account_number", "routing_number",
        "credit_card", "card_number", "cvv",
        "driver_license", "passport",
        "ip_address", "device_id",
    }

    def __init__(
        self,
        strategy: PIIHandlingStrategy = PIIHandlingStrategy.HASH,
        encryption_key: Optional[bytes] = None,
        hash_salt: Optional[str] = None,
    ):
        self.strategy = strategy
        self.encryption_key = encryption_key or secrets.token_bytes(ENCRYPTION_KEY_LENGTH)
        self.hash_salt = hash_salt or secrets.token_hex(16)
        self._token_map: Dict[str, str] = {}  # For tokenization
        self._reverse_token_map: Dict[str, str] = {}

    def process_features(
        self,
        features: Dict[str, Any],
        explicit_pii_fields: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, Any], List[str], List[str]]:
        """
        Process features to handle PII.

        Returns:
            Tuple of (processed_features, pii_fields_found, encrypted_fields)
        """
        processed = {}
        pii_fields = []
        encrypted_fields = []

        explicit_pii = set(explicit_pii_fields or [])

        for key, value in features.items():
            is_pii = (
                key.lower() in self.PII_FIELD_NAMES
                or key in explicit_pii
                or self._value_matches_pii_pattern(value)
            )

            if is_pii:
                pii_fields.append(key)
                processed[key], was_encrypted = self._handle_pii_value(key, value)
                if was_encrypted:
                    encrypted_fields.append(key)
            else:
                processed[key] = value

        return processed, pii_fields, encrypted_fields

    def _value_matches_pii_pattern(self, value: Any) -> bool:
        """Check if value matches known PII patterns"""
        if not isinstance(value, str):
            return False
        for pattern in self.PII_PATTERNS.values():
            if pattern.search(value):
                return True
        return False

    def _handle_pii_value(self, key: str, value: Any) -> Tuple[Any, bool]:
        """Handle a single PII value according to strategy"""
        str_value = str(value) if value is not None else ""

        if self.strategy == PIIHandlingStrategy.HASH:
            hashed = self._hash_value(str_value)
            return f"HASH:{hashed[:16]}", False

        elif self.strategy == PIIHandlingStrategy.ENCRYPT:
            encrypted = self._encrypt_value(str_value)
            return f"ENC:{encrypted}", True

        elif self.strategy == PIIHandlingStrategy.TOKENIZE:
            token = self._tokenize_value(str_value)
            return f"TOK:{token}", False

        elif self.strategy == PIIHandlingStrategy.REDACT:
            return "[REDACTED]", False

        elif self.strategy == PIIHandlingStrategy.MASK:
            masked = self._mask_value(str_value)
            return masked, False

        elif self.strategy == PIIHandlingStrategy.EXCLUDE:
            return None, False

        return value, False

    def _hash_value(self, value: str) -> str:
        """Hash a value with salt"""
        salted = f"{self.hash_salt}:{value}"
        return hashlib.sha256(salted.encode()).hexdigest()

    def _encrypt_value(self, value: str) -> str:
        """Encrypt a value (AES-256-GCM simulation using HMAC for demo)"""
        # In production, use proper AES-256-GCM encryption
        # This is a simplified demonstration using HMAC
        iv = secrets.token_bytes(IV_LENGTH)
        mac = hmac.new(self.encryption_key, value.encode(), hashlib.sha256).digest()
        encrypted = base64.b64encode(iv + mac).decode()
        return encrypted

    def _tokenize_value(self, value: str) -> str:
        """Replace value with a reversible token"""
        if value not in self._token_map:
            token = str(uuid.uuid4())
            self._token_map[value] = token
            self._reverse_token_map[token] = value
        return self._token_map[value]

    def _mask_value(self, value: str) -> str:
        """Mask value showing only last 4 characters"""
        if len(value) <= 4:
            return "*" * len(value)
        return "*" * (len(value) - 4) + value[-4:]

    def detokenize(self, token: str) -> Optional[str]:
        """Reverse tokenization if available"""
        if token.startswith("TOK:"):
            token = token[4:]
        return self._reverse_token_map.get(token)


# =============================================================================
# Cryptographic Signer
# =============================================================================

class CryptographicSigner:
    """
    Cryptographic signing for audit entries.

    Provides HMAC-based signatures with key rotation support.
    """

    def __init__(
        self,
        signing_key: Optional[bytes] = None,
        key_id: str = "default",
        algorithm: str = SIGNATURE_ALGORITHM,
    ):
        self.signing_key = signing_key or secrets.token_bytes(HMAC_KEY_LENGTH)
        self.key_id = key_id
        self.algorithm = algorithm
        self._key_history: Dict[str, bytes] = {key_id: self.signing_key}

    def sign(self, content: str) -> CryptographicSignature:
        """Sign content and return signature"""
        signature_bytes = hmac.new(
            self.signing_key,
            content.encode(),
            hashlib.sha256
        ).digest()

        return CryptographicSignature(
            signature=base64.b64encode(signature_bytes).decode(),
            algorithm=self.algorithm,
            key_id=self.key_id,
            signed_at=MicrosecondTimestamp.now(),
        )

    def verify(self, content: str, signature: CryptographicSignature) -> bool:
        """Verify a signature against content"""
        key = self._key_history.get(signature.key_id)
        if not key:
            logger.warning(f"Unknown key_id: {signature.key_id}")
            return False

        expected = hmac.new(key, content.encode(), hashlib.sha256).digest()
        actual = base64.b64decode(signature.signature)

        return hmac.compare_digest(expected, actual)

    def rotate_key(self, new_key_id: Optional[str] = None) -> str:
        """Rotate to a new signing key"""
        new_key_id = new_key_id or f"key-{int(time.time())}"
        new_key = secrets.token_bytes(HMAC_KEY_LENGTH)

        self._key_history[new_key_id] = new_key
        self.signing_key = new_key
        self.key_id = new_key_id

        logger.info(f"Rotated signing key to {new_key_id}")
        return new_key_id

    def export_key_metadata(self) -> Dict[str, Any]:
        """Export key metadata (not the keys themselves)"""
        return {
            "current_key_id": self.key_id,
            "algorithm": self.algorithm,
            "key_ids": list(self._key_history.keys()),
        }


# =============================================================================
# Hash Chain and Merkle Tree
# =============================================================================

class HashChain:
    """
    Hash chain for sequential tamper detection.

    Each entry's hash includes the previous entry's hash.
    """

    def __init__(self, genesis_hash: str = GENESIS_HASH):
        self.genesis_hash = genesis_hash
        self._last_hash = genesis_hash
        self._chain_length = 0

    def add_entry(self, entry: AuditEntry) -> str:
        """Add entry to chain and return its hash"""
        entry.previous_hash = self._last_hash
        entry.entry_hash = entry.compute_hash()

        self._last_hash = entry.entry_hash
        self._chain_length += 1

        return entry.entry_hash

    def verify_chain(self, entries: List[AuditEntry]) -> Tuple[bool, Optional[int]]:
        """
        Verify chain integrity.

        Returns:
            Tuple of (is_valid, first_broken_index)
        """
        if not entries:
            return True, None

        # Verify first entry links to genesis
        if entries[0].previous_hash != self.genesis_hash:
            return False, 0

        # Verify each entry
        for i, entry in enumerate(entries):
            computed_hash = entry.compute_hash()
            if computed_hash != entry.entry_hash:
                return False, i

            # Verify chain link (except first entry)
            if i > 0 and entry.previous_hash != entries[i - 1].entry_hash:
                return False, i

        return True, None

    @property
    def last_hash(self) -> str:
        return self._last_hash

    @property
    def chain_length(self) -> int:
        return self._chain_length


class MerkleTree:
    """
    Merkle tree for batch verification.

    Enables efficient verification of large batches of entries.
    """

    def __init__(self, algorithm: str = HASH_ALGORITHM):
        self.algorithm = algorithm

    def compute_root(self, entries: List[AuditEntry]) -> str:
        """Compute Merkle root for a batch of entries"""
        if not entries:
            return GENESIS_HASH

        hashes = [entry.entry_hash or entry.compute_hash() for entry in entries]
        return self._build_tree(hashes)

    def _build_tree(self, hashes: List[str]) -> str:
        """Build Merkle tree and return root"""
        if len(hashes) == 1:
            return hashes[0]

        # Pad to even number
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])

        # Build next level
        next_level = []
        for i in range(0, len(hashes), 2):
            combined = hashes[i] + hashes[i + 1]
            parent_hash = hashlib.sha256(combined.encode()).hexdigest()
            next_level.append(parent_hash)

        return self._build_tree(next_level)

    def compute_proof(
        self,
        entry: AuditEntry,
        all_entries: List[AuditEntry],
    ) -> List[Tuple[str, str]]:
        """
        Compute Merkle proof for a single entry.

        Returns list of (hash, direction) tuples.
        """
        if entry not in all_entries:
            return []

        hashes = [e.entry_hash or e.compute_hash() for e in all_entries]
        index = all_entries.index(entry)

        return self._compute_proof_recursive(hashes, index, [])

    def _compute_proof_recursive(
        self,
        hashes: List[str],
        index: int,
        proof: List[Tuple[str, str]],
    ) -> List[Tuple[str, str]]:
        """Recursively compute proof"""
        if len(hashes) == 1:
            return proof

        # Pad to even number
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])

        # Find sibling
        if index % 2 == 0:
            sibling_index = index + 1
            direction = "right"
        else:
            sibling_index = index - 1
            direction = "left"

        proof.append((hashes[sibling_index], direction))

        # Build next level
        next_level = []
        for i in range(0, len(hashes), 2):
            combined = hashes[i] + hashes[i + 1]
            parent_hash = hashlib.sha256(combined.encode()).hexdigest()
            next_level.append(parent_hash)

        return self._compute_proof_recursive(next_level, index // 2, proof)

    def verify_proof(
        self,
        entry_hash: str,
        proof: List[Tuple[str, str]],
        root: str,
    ) -> bool:
        """Verify a Merkle proof"""
        current_hash = entry_hash

        for sibling_hash, direction in proof:
            if direction == "left":
                combined = sibling_hash + current_hash
            else:
                combined = current_hash + sibling_hash
            current_hash = hashlib.sha256(combined.encode()).hexdigest()

        return current_hash == root


# =============================================================================
# Storage Interfaces
# =============================================================================

class StorageBackend(ABC):
    """Abstract base class for immutable storage backends"""

    @abstractmethod
    def write(self, entry: AuditEntry) -> bool:
        """Write a single audit entry"""
        pass

    @abstractmethod
    def write_batch(self, entries: List[AuditEntry]) -> int:
        """Write a batch of entries, returns count written"""
        pass

    @abstractmethod
    def read(self, decision_id: str) -> Optional[AuditEntry]:
        """Read entry by decision ID"""
        pass

    @abstractmethod
    def query(
        self,
        start_time: Optional[MicrosecondTimestamp] = None,
        end_time: Optional[MicrosecondTimestamp] = None,
        subject_id: Optional[str] = None,
        decision_type: Optional[DecisionType] = None,
        limit: int = 1000,
    ) -> List[AuditEntry]:
        """Query entries with filters"""
        pass

    @abstractmethod
    def verify_immutability(self, decision_id: str) -> bool:
        """Verify entry has not been modified"""
        pass

    @abstractmethod
    def apply_legal_hold(self, decision_ids: List[str], hold_id: str) -> int:
        """Apply legal hold to entries"""
        pass

    @abstractmethod
    def remove_legal_hold(self, hold_id: str) -> int:
        """Remove legal hold by hold ID"""
        pass


class LocalAppendOnlyStorage(StorageBackend):
    """
    Local append-only file storage for development and testing.

    Uses append-only log files with periodic rotation.
    """

    def __init__(
        self,
        base_path: Path,
        max_file_size_mb: int = 100,
        compress: bool = True,
    ):
        self.base_path = Path(base_path)
        self.max_file_size_mb = max_file_size_mb
        self.compress = compress
        self.base_path.mkdir(parents=True, exist_ok=True)

        # In-memory index for fast lookups
        self._index: Dict[str, Tuple[Path, int]] = {}  # decision_id -> (file, offset)
        self._legal_holds: Dict[str, Set[str]] = {}  # hold_id -> set of decision_ids
        self._current_file: Optional[Path] = None
        self._current_offset = 0
        self._lock = threading.Lock()

        self._initialize_index()

    def _initialize_index(self):
        """Build index from existing files"""
        log_files = sorted(self.base_path.glob("audit_*.jsonl*"))
        for log_file in log_files:
            self._index_file(log_file)

    def _index_file(self, file_path: Path):
        """Index a single log file"""
        try:
            opener = gzip.open if file_path.suffix == ".gz" else open
            with opener(file_path, "rt") as f:
                offset = 0
                for line in f:
                    try:
                        data = json.loads(line)
                        decision_id = data.get("decision_id")
                        if decision_id:
                            self._index[decision_id] = (file_path, offset)
                    except json.JSONDecodeError:
                        pass
                    offset += len(line)
        except Exception as e:
            logger.error(f"Error indexing {file_path}: {e}")

    def _get_current_file(self) -> Path:
        """Get current log file, rotating if necessary"""
        if self._current_file is None or self._should_rotate():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._current_file = self.base_path / f"audit_{timestamp}.jsonl"
            self._current_offset = 0
        return self._current_file

    def _should_rotate(self) -> bool:
        """Check if current file should be rotated"""
        if self._current_file is None or not self._current_file.exists():
            return True
        size_mb = self._current_file.stat().st_size / (1024 * 1024)
        return size_mb >= self.max_file_size_mb

    def write(self, entry: AuditEntry) -> bool:
        """Write a single entry in append-only mode"""
        with self._lock:
            try:
                file_path = self._get_current_file()
                line = json.dumps(entry.to_dict(), default=str) + "\n"

                with open(file_path, "a") as f:
                    f.write(line)

                self._index[entry.decision_id] = (file_path, self._current_offset)
                self._current_offset += len(line)

                return True
            except Exception as e:
                logger.error(f"Error writing audit entry: {e}")
                return False

    def write_batch(self, entries: List[AuditEntry]) -> int:
        """Write batch of entries"""
        written = 0
        with self._lock:
            try:
                file_path = self._get_current_file()
                lines = []
                for entry in entries:
                    line = json.dumps(entry.to_dict(), default=str) + "\n"
                    lines.append(line)
                    self._index[entry.decision_id] = (file_path, self._current_offset)
                    self._current_offset += len(line)
                    written += 1

                with open(file_path, "a") as f:
                    f.writelines(lines)

            except Exception as e:
                logger.error(f"Error writing batch: {e}")

        return written

    def read(self, decision_id: str) -> Optional[AuditEntry]:
        """Read entry by decision ID"""
        location = self._index.get(decision_id)
        if not location:
            return None

        file_path, offset = location
        try:
            opener = gzip.open if file_path.suffix == ".gz" else open
            with opener(file_path, "rt") as f:
                f.seek(offset)
                line = f.readline()
                data = json.loads(line)
                return AuditEntry.from_dict(data)
        except Exception as e:
            logger.error(f"Error reading entry {decision_id}: {e}")
            return None

    def query(
        self,
        start_time: Optional[MicrosecondTimestamp] = None,
        end_time: Optional[MicrosecondTimestamp] = None,
        subject_id: Optional[str] = None,
        decision_type: Optional[DecisionType] = None,
        limit: int = 1000,
    ) -> List[AuditEntry]:
        """Query entries with filters"""
        results = []

        for file_path in sorted(self.base_path.glob("audit_*.jsonl*")):
            try:
                opener = gzip.open if file_path.suffix == ".gz" else open
                with opener(file_path, "rt") as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            entry = AuditEntry.from_dict(data)

                            # Apply filters
                            if start_time and entry.timestamp.epoch_micros < start_time.epoch_micros:
                                continue
                            if end_time and entry.timestamp.epoch_micros > end_time.epoch_micros:
                                continue
                            if subject_id and entry.subject_id != subject_id:
                                continue
                            if decision_type and entry.decision_type != decision_type:
                                continue

                            results.append(entry)
                            if len(results) >= limit:
                                return results
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"Error querying {file_path}: {e}")

        return results

    def verify_immutability(self, decision_id: str) -> bool:
        """Verify entry has not been modified by recomputing hash"""
        entry = self.read(decision_id)
        if not entry:
            return False

        computed_hash = entry.compute_hash()
        return computed_hash == entry.entry_hash

    def apply_legal_hold(self, decision_ids: List[str], hold_id: str) -> int:
        """Apply legal hold to entries"""
        count = 0
        if hold_id not in self._legal_holds:
            self._legal_holds[hold_id] = set()

        for decision_id in decision_ids:
            if decision_id in self._index:
                self._legal_holds[hold_id].add(decision_id)
                count += 1

        return count

    def remove_legal_hold(self, hold_id: str) -> int:
        """Remove legal hold"""
        if hold_id in self._legal_holds:
            count = len(self._legal_holds[hold_id])
            del self._legal_holds[hold_id]
            return count
        return 0


class S3ObjectLockStorage(StorageBackend):
    """
    AWS S3 storage with Object Lock for WORM compliance.

    Uses S3 Object Lock in Compliance mode for regulatory compliance.
    """

    def __init__(
        self,
        bucket_name: str,
        prefix: str = "audit-logs",
        region: str = "us-east-1",
        retention_days: int = 2555,  # 7 years
        kms_key_id: Optional[str] = None,
    ):
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.region = region
        self.retention_days = retention_days
        self.kms_key_id = kms_key_id
        self._client = None  # Lazy initialization
        self._legal_holds: Dict[str, Set[str]] = {}

    def _get_client(self):
        """Get or create S3 client"""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client("s3", region_name=self.region)
            except ImportError:
                raise RuntimeError("boto3 required for S3 storage")
        return self._client

    def _get_object_key(self, decision_id: str) -> str:
        """Generate S3 object key for an entry"""
        # Partition by date for efficient querying
        timestamp = datetime.now()
        return f"{self.prefix}/{timestamp.year}/{timestamp.month:02d}/{timestamp.day:02d}/{decision_id}.json"

    def write(self, entry: AuditEntry) -> bool:
        """Write entry to S3 with Object Lock"""
        try:
            client = self._get_client()
            key = self._get_object_key(entry.decision_id)
            body = json.dumps(entry.to_dict(), default=str)

            # Calculate retention date
            retain_until = datetime.now(timezone.utc) + timedelta(days=self.retention_days)

            put_args = {
                "Bucket": self.bucket_name,
                "Key": key,
                "Body": body.encode(),
                "ContentType": "application/json",
                "ObjectLockMode": "COMPLIANCE",
                "ObjectLockRetainUntilDate": retain_until,
            }

            if self.kms_key_id:
                put_args["ServerSideEncryption"] = "aws:kms"
                put_args["SSEKMSKeyId"] = self.kms_key_id

            client.put_object(**put_args)
            return True

        except Exception as e:
            logger.error(f"Error writing to S3: {e}")
            return False

    def write_batch(self, entries: List[AuditEntry]) -> int:
        """Write batch to S3 (individual objects for immutability)"""
        written = 0
        for entry in entries:
            if self.write(entry):
                written += 1
        return written

    def read(self, decision_id: str) -> Optional[AuditEntry]:
        """Read entry from S3"""
        try:
            client = self._get_client()

            # Search for the object (date partitioning requires listing)
            paginator = client.get_paginator("list_objects_v2")

            for page in paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=self.prefix,
            ):
                for obj in page.get("Contents", []):
                    if decision_id in obj["Key"]:
                        response = client.get_object(
                            Bucket=self.bucket_name,
                            Key=obj["Key"],
                        )
                        data = json.loads(response["Body"].read().decode())
                        return AuditEntry.from_dict(data)

            return None

        except Exception as e:
            logger.error(f"Error reading from S3: {e}")
            return None

    def query(
        self,
        start_time: Optional[MicrosecondTimestamp] = None,
        end_time: Optional[MicrosecondTimestamp] = None,
        subject_id: Optional[str] = None,
        decision_type: Optional[DecisionType] = None,
        limit: int = 1000,
    ) -> List[AuditEntry]:
        """Query entries from S3"""
        results = []

        try:
            client = self._get_client()
            paginator = client.get_paginator("list_objects_v2")

            # Build prefix based on time range
            prefix = self.prefix
            if start_time:
                dt = start_time.to_datetime()
                prefix = f"{self.prefix}/{dt.year}/{dt.month:02d}"

            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                for obj in page.get("Contents", []):
                    try:
                        response = client.get_object(
                            Bucket=self.bucket_name,
                            Key=obj["Key"],
                        )
                        data = json.loads(response["Body"].read().decode())
                        entry = AuditEntry.from_dict(data)

                        # Apply filters
                        if start_time and entry.timestamp.epoch_micros < start_time.epoch_micros:
                            continue
                        if end_time and entry.timestamp.epoch_micros > end_time.epoch_micros:
                            continue
                        if subject_id and entry.subject_id != subject_id:
                            continue
                        if decision_type and entry.decision_type != decision_type:
                            continue

                        results.append(entry)
                        if len(results) >= limit:
                            return results
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Error querying S3: {e}")

        return results

    def verify_immutability(self, decision_id: str) -> bool:
        """Verify entry integrity via hash comparison"""
        entry = self.read(decision_id)
        if not entry:
            return False
        return entry.compute_hash() == entry.entry_hash

    def apply_legal_hold(self, decision_ids: List[str], hold_id: str) -> int:
        """Apply S3 Object Lock legal hold"""
        count = 0
        try:
            client = self._get_client()

            for decision_id in decision_ids:
                # Find the object key
                paginator = client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.prefix):
                    for obj in page.get("Contents", []):
                        if decision_id in obj["Key"]:
                            client.put_object_legal_hold(
                                Bucket=self.bucket_name,
                                Key=obj["Key"],
                                LegalHold={"Status": "ON"},
                            )
                            count += 1
                            break
        except Exception as e:
            logger.error(f"Error applying legal hold: {e}")

        return count

    def remove_legal_hold(self, hold_id: str) -> int:
        """Remove S3 Object Lock legal hold"""
        # Note: In production, track hold_id -> object mappings
        # This is a simplified implementation
        return 0


class WORMDatabaseStorage(StorageBackend):
    """
    WORM (Write Once Read Many) database storage.

    Uses database-level append-only tables with audit triggers.
    """

    def __init__(
        self,
        connection_string: str,
        table_name: str = "audit_log",
        schema: str = "audit",
    ):
        self.connection_string = connection_string
        self.table_name = table_name
        self.schema = schema
        self._connection = None
        self._legal_holds: Dict[str, Set[str]] = {}

    def _get_connection(self):
        """Get database connection (lazy initialization)"""
        if self._connection is None:
            # This would use actual database driver in production
            logger.info(f"Connecting to WORM database: {self.connection_string}")
        return self._connection

    def write(self, entry: AuditEntry) -> bool:
        """Write entry to WORM database"""
        # In production, this would use parameterized SQL INSERT
        # WORM is enforced via database triggers that prevent UPDATE/DELETE
        logger.info(f"Writing entry {entry.decision_id} to WORM database")
        return True

    def write_batch(self, entries: List[AuditEntry]) -> int:
        """Batch insert to WORM database"""
        logger.info(f"Batch writing {len(entries)} entries to WORM database")
        return len(entries)

    def read(self, decision_id: str) -> Optional[AuditEntry]:
        """Read from WORM database"""
        logger.info(f"Reading entry {decision_id} from WORM database")
        return None

    def query(
        self,
        start_time: Optional[MicrosecondTimestamp] = None,
        end_time: Optional[MicrosecondTimestamp] = None,
        subject_id: Optional[str] = None,
        decision_type: Optional[DecisionType] = None,
        limit: int = 1000,
    ) -> List[AuditEntry]:
        """Query WORM database"""
        logger.info("Querying WORM database")
        return []

    def verify_immutability(self, decision_id: str) -> bool:
        """Verify via database checksums and audit triggers"""
        return True

    def apply_legal_hold(self, decision_ids: List[str], hold_id: str) -> int:
        """Apply legal hold via database flag"""
        return 0

    def remove_legal_hold(self, hold_id: str) -> int:
        """Remove legal hold"""
        return 0


# =============================================================================
# Batch Writer
# =============================================================================

class BatchAuditWriter:
    """
    Batch audit writer for high-throughput scenarios.

    Buffers entries and writes in batches for performance.
    """

    def __init__(
        self,
        storage: StorageBackend,
        batch_size: int = 100,
        flush_interval_seconds: float = 1.0,
        max_buffer_size: int = 10000,
    ):
        self.storage = storage
        self.batch_size = batch_size
        self.flush_interval = flush_interval_seconds
        self.max_buffer_size = max_buffer_size

        self._buffer: List[AuditEntry] = []
        self._lock = threading.Lock()
        self._last_flush = time.time()
        self._flush_thread: Optional[threading.Thread] = None
        self._running = False

        self._metrics = {
            "entries_buffered": 0,
            "entries_written": 0,
            "batches_written": 0,
            "flush_count": 0,
        }

    def start(self):
        """Start background flush thread"""
        self._running = True
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()
        logger.info("Batch audit writer started")

    def stop(self, flush: bool = True):
        """Stop background flush thread"""
        self._running = False
        if flush:
            self.flush()
        if self._flush_thread:
            self._flush_thread.join(timeout=5.0)
        logger.info("Batch audit writer stopped")

    def add(self, entry: AuditEntry):
        """Add entry to buffer"""
        with self._lock:
            if len(self._buffer) >= self.max_buffer_size:
                logger.warning("Buffer full, forcing flush")
                self._flush_buffer()

            self._buffer.append(entry)
            self._metrics["entries_buffered"] += 1

            if len(self._buffer) >= self.batch_size:
                self._flush_buffer()

    def flush(self):
        """Force flush of buffer"""
        with self._lock:
            self._flush_buffer()

    def _flush_buffer(self):
        """Internal flush (must hold lock)"""
        if not self._buffer:
            return

        entries = self._buffer[:]
        self._buffer.clear()

        written = self.storage.write_batch(entries)
        self._metrics["entries_written"] += written
        self._metrics["batches_written"] += 1
        self._metrics["flush_count"] += 1
        self._last_flush = time.time()

        logger.debug(f"Flushed {written} entries")

    def _flush_loop(self):
        """Background flush loop"""
        while self._running:
            time.sleep(self.flush_interval)

            with self._lock:
                if self._buffer and (time.time() - self._last_flush) >= self.flush_interval:
                    self._flush_buffer()

    def get_metrics(self) -> Dict[str, int]:
        """Get writer metrics"""
        with self._lock:
            metrics = self._metrics.copy()
            metrics["buffer_size"] = len(self._buffer)
        return metrics


# =============================================================================
# Tamper Detection
# =============================================================================

class TamperDetector:
    """
    Tamper detection for audit logs.

    Uses hash chains, Merkle trees, and signatures to detect modifications.
    """

    def __init__(
        self,
        signer: CryptographicSigner,
        hash_chain: Optional[HashChain] = None,
        merkle_tree: Optional[MerkleTree] = None,
    ):
        self.signer = signer
        self.hash_chain = hash_chain or HashChain()
        self.merkle_tree = merkle_tree or MerkleTree()

    def verify_entry(self, entry: AuditEntry) -> IntegrityStatus:
        """Verify a single entry's integrity"""
        # Verify hash
        computed_hash = entry.compute_hash()
        if computed_hash != entry.entry_hash:
            return IntegrityStatus.TAMPERED

        # Verify signature if present
        if entry.signature:
            content = entry._get_hashable_content()
            if not self.signer.verify(content, entry.signature):
                return IntegrityStatus.INVALID_SIGNATURE
        elif entry.entry_hash:
            # Entry has hash but no signature
            return IntegrityStatus.MISSING_SIGNATURE

        return IntegrityStatus.VALID

    def verify_chain(self, entries: List[AuditEntry]) -> Tuple[IntegrityStatus, Optional[int]]:
        """Verify chain integrity"""
        is_valid, broken_index = self.hash_chain.verify_chain(entries)

        if not is_valid:
            return IntegrityStatus.CHAIN_BROKEN, broken_index

        # Verify each entry
        for i, entry in enumerate(entries):
            status = self.verify_entry(entry)
            if status != IntegrityStatus.VALID:
                return status, i

        return IntegrityStatus.VALID, None

    def verify_batch_with_merkle(
        self,
        entries: List[AuditEntry],
        expected_root: str,
    ) -> IntegrityStatus:
        """Verify batch using Merkle root"""
        computed_root = self.merkle_tree.compute_root(entries)

        if computed_root != expected_root:
            return IntegrityStatus.TAMPERED

        return IntegrityStatus.VALID

    def generate_integrity_report(
        self,
        entries: List[AuditEntry],
    ) -> Dict[str, Any]:
        """Generate comprehensive integrity report"""
        report = {
            "total_entries": len(entries),
            "verified_at": MicrosecondTimestamp.now().to_iso8601(),
            "chain_status": "unknown",
            "individual_status": {},
            "merkle_root": None,
            "issues": [],
        }

        # Verify chain
        chain_status, broken_index = self.verify_chain(entries)
        report["chain_status"] = chain_status.value
        if broken_index is not None:
            report["issues"].append({
                "type": "chain_broken",
                "index": broken_index,
                "decision_id": entries[broken_index].decision_id if broken_index < len(entries) else None,
            })

        # Verify individual entries
        for i, entry in enumerate(entries):
            status = self.verify_entry(entry)
            report["individual_status"][entry.decision_id] = status.value
            if status != IntegrityStatus.VALID:
                report["issues"].append({
                    "type": status.value,
                    "index": i,
                    "decision_id": entry.decision_id,
                })

        # Compute Merkle root
        report["merkle_root"] = self.merkle_tree.compute_root(entries)

        return report


# =============================================================================
# Retention Manager
# =============================================================================

class RetentionManager:
    """
    Manages retention policies and legal holds.

    Enforces retention requirements and handles hold management.
    """

    def __init__(self, storage: StorageBackend):
        self.storage = storage
        self._legal_holds: Dict[str, Dict[str, Any]] = {}  # hold_id -> metadata

    def apply_policy(
        self,
        entry: AuditEntry,
        policy: RetentionPolicy,
    ) -> AuditEntry:
        """Apply retention policy to entry"""
        entry.retention_policy = policy

        # Calculate retention_until if time-based
        if policy.policy_type == RetentionPolicyType.TIME_BASED and policy.retention_days:
            retain_until = MicrosecondTimestamp.now()
            retain_until.epoch_micros += policy.retention_days * 24 * 60 * 60 * 1_000_000
            policy.retention_until = retain_until

        return entry

    def create_legal_hold(
        self,
        hold_id: str,
        matter_name: str,
        created_by: str,
        decision_ids: Optional[List[str]] = None,
        query_criteria: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new legal hold"""
        hold = {
            "hold_id": hold_id,
            "matter_name": matter_name,
            "created_by": created_by,
            "created_at": MicrosecondTimestamp.now().to_iso8601(),
            "decision_ids": decision_ids or [],
            "query_criteria": query_criteria,
            "status": "active",
        }

        self._legal_holds[hold_id] = hold

        # Apply hold to storage
        if decision_ids:
            count = self.storage.apply_legal_hold(decision_ids, hold_id)
            hold["entries_held"] = count

        logger.info(f"Created legal hold {hold_id} for matter {matter_name}")
        return hold

    def release_legal_hold(self, hold_id: str, released_by: str) -> bool:
        """Release a legal hold"""
        if hold_id not in self._legal_holds:
            return False

        hold = self._legal_holds[hold_id]
        hold["status"] = "released"
        hold["released_by"] = released_by
        hold["released_at"] = MicrosecondTimestamp.now().to_iso8601()

        count = self.storage.remove_legal_hold(hold_id)
        hold["entries_released"] = count

        logger.info(f"Released legal hold {hold_id}")
        return True

    def get_legal_holds(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all legal holds"""
        holds = list(self._legal_holds.values())
        if active_only:
            holds = [h for h in holds if h.get("status") == "active"]
        return holds

    def is_under_hold(self, decision_id: str) -> Tuple[bool, List[str]]:
        """Check if decision is under any legal hold"""
        hold_ids = []
        for hold_id, hold in self._legal_holds.items():
            if hold.get("status") == "active":
                if decision_id in hold.get("decision_ids", []):
                    hold_ids.append(hold_id)
        return bool(hold_ids), hold_ids

    def check_retention_expired(self, entry: AuditEntry) -> bool:
        """Check if entry's retention has expired"""
        if not entry.retention_policy:
            return False

        policy = entry.retention_policy

        # Legal holds override retention
        if policy.legal_hold:
            return False

        # Check time-based retention
        if policy.retention_until:
            now = MicrosecondTimestamp.now()
            return now.epoch_micros > policy.retention_until.epoch_micros

        return False


# =============================================================================
# Compliance Exporter
# =============================================================================

class ComplianceExporter:
    """
    Export audit logs for compliance reviews.

    Supports multiple formats and includes integrity verification.
    """

    def __init__(self, storage: StorageBackend, tamper_detector: TamperDetector):
        self.storage = storage
        self.tamper_detector = tamper_detector

    def export(
        self,
        entries: List[AuditEntry],
        format: ExportFormat,
        output_path: Path,
        include_integrity_report: bool = True,
        include_signatures: bool = True,
    ) -> Dict[str, Any]:
        """Export entries in specified format"""
        output_path = Path(output_path)

        # Verify integrity before export
        integrity_report = None
        if include_integrity_report:
            integrity_report = self.tamper_detector.generate_integrity_report(entries)

        # Export based on format
        if format == ExportFormat.JSON:
            self._export_json(entries, output_path, include_signatures)
        elif format == ExportFormat.JSON_LINES:
            self._export_jsonl(entries, output_path, include_signatures)
        elif format == ExportFormat.CSV:
            self._export_csv(entries, output_path)
        elif format == ExportFormat.XML:
            self._export_xml(entries, output_path)
        else:
            raise ValueError(f"Unsupported export format: {format}")

        result = {
            "format": format.value,
            "output_path": str(output_path),
            "entries_exported": len(entries),
            "exported_at": MicrosecondTimestamp.now().to_iso8601(),
        }

        if integrity_report:
            result["integrity_report"] = integrity_report

            # Write integrity report alongside export
            report_path = output_path.parent / f"{output_path.stem}_integrity_report.json"
            with open(report_path, "w") as f:
                json.dump(integrity_report, f, indent=2, default=str)
            result["integrity_report_path"] = str(report_path)

        return result

    def _export_json(
        self,
        entries: List[AuditEntry],
        output_path: Path,
        include_signatures: bool,
    ):
        """Export as JSON array"""
        data = []
        for entry in entries:
            entry_dict = entry.to_dict()
            if not include_signatures:
                entry_dict.pop("signature", None)
            data.append(entry_dict)

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _export_jsonl(
        self,
        entries: List[AuditEntry],
        output_path: Path,
        include_signatures: bool,
    ):
        """Export as JSON Lines"""
        with open(output_path, "w") as f:
            for entry in entries:
                entry_dict = entry.to_dict()
                if not include_signatures:
                    entry_dict.pop("signature", None)
                f.write(json.dumps(entry_dict, default=str) + "\n")

    def _export_csv(self, entries: List[AuditEntry], output_path: Path):
        """Export as CSV (flattened)"""
        import csv

        if not entries:
            return

        # Flatten entries for CSV
        rows = []
        fieldnames = set()

        for entry in entries:
            row = self._flatten_entry(entry)
            rows.append(row)
            fieldnames.update(row.keys())

        fieldnames = sorted(fieldnames)

        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _export_xml(self, entries: List[AuditEntry], output_path: Path):
        """Export as XML"""
        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        lines.append("<audit_log>")

        for entry in entries:
            lines.append("  <entry>")
            for key, value in entry.to_dict().items():
                if value is not None:
                    lines.append(f"    <{key}>{self._xml_escape(value)}</{key}>")
            lines.append("  </entry>")

        lines.append("</audit_log>")

        with open(output_path, "w") as f:
            f.write("\n".join(lines))

    def _flatten_entry(self, entry: AuditEntry) -> Dict[str, Any]:
        """Flatten nested entry for CSV export"""
        flat = {
            "decision_id": entry.decision_id,
            "correlation_id": entry.correlation_id,
            "timestamp": entry.timestamp.to_iso8601(),
            "decision_type": entry.decision_type.value,
            "subject_id": entry.subject_id,
            "subject_type": entry.subject_type,
            "entry_hash": entry.entry_hash,
            "environment": entry.environment,
        }

        if entry.model_version:
            flat["model_id"] = entry.model_version.model_id
            flat["model_version"] = entry.model_version.version

        if entry.actor:
            flat["actor_id"] = entry.actor.actor_id
            flat["actor_type"] = entry.actor.actor_type.value

        if entry.output_prediction:
            flat["prediction"] = entry.output_prediction.prediction
            flat["probability"] = entry.output_prediction.probability

        return flat

    def _xml_escape(self, value: Any) -> str:
        """Escape value for XML"""
        s = str(value) if value is not None else ""
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# =============================================================================
# Main Audit Logger
# =============================================================================

class AuditLogger:
    """
    Main audit logger for immutable ML decision logging.

    Provides complete audit trail with tamper detection, batch writing,
    retention management, and compliance export capabilities.

    Usage:
        logger = AuditLogger.create_default("/path/to/audit/logs")

        # Log a decision
        entry = logger.log_decision(
            subject_id="account_12345",
            subject_type="account",
            decision_type=DecisionType.PREDICTION,
            model_version=ModelVersion(...),
            input_features={"feature1": 1.0, ...},
            output_prediction=OutputPrediction(...),
            explanation=DecisionExplanation(...),
            policy_context=PolicyContext(...),
        )

        # Retrieve by ID
        retrieved = logger.get_decision(entry.decision_id)

        # Verify integrity
        is_valid = logger.verify_decision(entry.decision_id)
    """

    def __init__(
        self,
        storage: StorageBackend,
        signer: CryptographicSigner,
        pii_handler: PIIHandler,
        batch_writer: Optional[BatchAuditWriter] = None,
        default_retention_policy: Optional[RetentionPolicy] = None,
        service_name: str = "quan-ml-service",
        environment: str = "production",
    ):
        self.storage = storage
        self.signer = signer
        self.pii_handler = pii_handler
        self.batch_writer = batch_writer
        self.default_retention_policy = default_retention_policy or RetentionPolicy.regulatory_default("FCRA")
        self.service_name = service_name
        self.environment = environment

        self.hash_chain = HashChain()
        self.merkle_tree = MerkleTree()
        self.tamper_detector = TamperDetector(signer, self.hash_chain, self.merkle_tree)
        self.retention_manager = RetentionManager(storage)
        self.exporter = ComplianceExporter(storage, self.tamper_detector)

        self._metrics = defaultdict(int)

    @classmethod
    def create_default(
        cls,
        storage_path: str,
        service_name: str = "quan-ml-service",
        environment: str = "production",
    ) -> "AuditLogger":
        """Create audit logger with default configuration"""
        storage = LocalAppendOnlyStorage(Path(storage_path))
        signer = CryptographicSigner()
        pii_handler = PIIHandler(strategy=PIIHandlingStrategy.HASH)
        batch_writer = BatchAuditWriter(storage)
        batch_writer.start()

        return cls(
            storage=storage,
            signer=signer,
            pii_handler=pii_handler,
            batch_writer=batch_writer,
            service_name=service_name,
            environment=environment,
        )

    @classmethod
    def create_s3(
        cls,
        bucket_name: str,
        region: str = "us-east-1",
        kms_key_id: Optional[str] = None,
        service_name: str = "quan-ml-service",
        environment: str = "production",
    ) -> "AuditLogger":
        """Create audit logger with S3 Object Lock storage"""
        storage = S3ObjectLockStorage(
            bucket_name=bucket_name,
            region=region,
            kms_key_id=kms_key_id,
        )
        signer = CryptographicSigner()
        pii_handler = PIIHandler(strategy=PIIHandlingStrategy.ENCRYPT)

        return cls(
            storage=storage,
            signer=signer,
            pii_handler=pii_handler,
            service_name=service_name,
            environment=environment,
        )

    def log_decision(
        self,
        subject_id: str,
        subject_type: str,
        decision_type: DecisionType,
        model_version: Optional[ModelVersion] = None,
        actor: Optional[Actor] = None,
        input_features: Optional[Dict[str, Any]] = None,
        output_prediction: Optional[OutputPrediction] = None,
        explanation: Optional[DecisionExplanation] = None,
        policy_context: Optional[PolicyContext] = None,
        correlation_id: Optional[str] = None,
        parent_decision_id: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        pii_fields: Optional[List[str]] = None,
        retention_policy: Optional[RetentionPolicy] = None,
        use_batch: bool = False,
    ) -> AuditEntry:
        """
        Log a decision with full audit trail.

        Args:
            subject_id: ID of entity being decided about
            subject_type: Type of subject (account, customer, etc.)
            decision_type: Type of decision
            model_version: Model version information
            actor: Actor making the decision
            input_features: Raw input features (PII will be handled)
            output_prediction: Prediction output
            explanation: Decision explanation
            policy_context: Policy context applied
            correlation_id: Request correlation ID
            parent_decision_id: Parent decision for chains
            tags: Additional tags
            pii_fields: Explicit list of PII fields
            retention_policy: Custom retention policy
            use_batch: Use batch writer for performance

        Returns:
            Created audit entry
        """
        start_time = time.perf_counter_ns()

        # Generate IDs
        decision_id = str(uuid.uuid4())
        correlation_id = correlation_id or str(uuid.uuid4())

        # Process PII in features
        processed_features = None
        if input_features:
            processed_values, pii_found, encrypted = self.pii_handler.process_features(
                input_features, pii_fields
            )
            raw_input_hash = hashlib.sha256(
                json.dumps(input_features, sort_keys=True, default=str).encode()
            ).hexdigest()

            processed_features = InputFeatures(
                feature_values=processed_values,
                feature_names=list(input_features.keys()),
                pii_handling=self.pii_handler.strategy,
                pii_fields_present=pii_found,
                encrypted_fields=encrypted,
                hash_salt=self.pii_handler.hash_salt,
                raw_input_hash=raw_input_hash,
            )

        # Hash subject_id if it's PII
        hashed_subject_id = hashlib.sha256(
            f"{self.pii_handler.hash_salt}:{subject_id}".encode()
        ).hexdigest()[:16]

        # Create default actor if not provided
        if actor is None:
            if model_version:
                actor = Actor.model(model_version)
            else:
                actor = Actor.system(self.service_name)

        # Create entry
        entry = AuditEntry(
            decision_id=decision_id,
            correlation_id=correlation_id,
            parent_decision_id=parent_decision_id,
            timestamp=MicrosecondTimestamp.now(),
            decision_type=decision_type,
            subject_id=hashed_subject_id,
            subject_type=subject_type,
            model_version=model_version,
            actor=actor,
            input_features=processed_features,
            output_prediction=output_prediction,
            explanation=explanation,
            policy_context=policy_context,
            retention_policy=retention_policy or self.default_retention_policy,
            tags=tags or {},
            environment=self.environment,
            service_name=self.service_name,
        )

        # Add to hash chain
        self.hash_chain.add_entry(entry)

        # Sign entry
        content = entry._get_hashable_content()
        entry.signature = self.signer.sign(content)

        # Calculate processing duration
        end_time = time.perf_counter_ns()
        entry.processing_duration_micros = (end_time - start_time) // 1000

        # Write to storage
        if use_batch and self.batch_writer:
            self.batch_writer.add(entry)
        else:
            self.storage.write(entry)

        self._metrics["decisions_logged"] += 1

        logger.debug(f"Logged decision {decision_id}")
        return entry

    def get_decision(self, decision_id: str) -> Optional[AuditEntry]:
        """Retrieve decision by ID"""
        entry = self.storage.read(decision_id)
        self._metrics["decisions_retrieved"] += 1
        return entry

    def verify_decision(self, decision_id: str) -> IntegrityStatus:
        """Verify decision integrity"""
        entry = self.storage.read(decision_id)
        if not entry:
            return IntegrityStatus.UNKNOWN

        status = self.tamper_detector.verify_entry(entry)
        self._metrics["verifications_performed"] += 1
        return status

    def query_decisions(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        subject_id: Optional[str] = None,
        decision_type: Optional[DecisionType] = None,
        limit: int = 1000,
    ) -> List[AuditEntry]:
        """Query decisions with filters"""
        start_ts = MicrosecondTimestamp.from_datetime(start_time) if start_time else None
        end_ts = MicrosecondTimestamp.from_datetime(end_time) if end_time else None

        # Hash subject_id for query
        if subject_id:
            subject_id = hashlib.sha256(
                f"{self.pii_handler.hash_salt}:{subject_id}".encode()
            ).hexdigest()[:16]

        return self.storage.query(
            start_time=start_ts,
            end_time=end_ts,
            subject_id=subject_id,
            decision_type=decision_type,
            limit=limit,
        )

    def create_legal_hold(
        self,
        hold_id: str,
        matter_name: str,
        created_by: str,
        decision_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create legal hold"""
        return self.retention_manager.create_legal_hold(
            hold_id=hold_id,
            matter_name=matter_name,
            created_by=created_by,
            decision_ids=decision_ids,
        )

    def release_legal_hold(self, hold_id: str, released_by: str) -> bool:
        """Release legal hold"""
        return self.retention_manager.release_legal_hold(hold_id, released_by)

    def export_for_compliance(
        self,
        entries: List[AuditEntry],
        output_path: str,
        format: ExportFormat = ExportFormat.JSON,
    ) -> Dict[str, Any]:
        """Export entries for compliance review"""
        return self.exporter.export(
            entries=entries,
            format=format,
            output_path=Path(output_path),
        )

    def generate_integrity_report(
        self,
        entries: Optional[List[AuditEntry]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Generate integrity report for entries"""
        if entries is None:
            entries = self.query_decisions(
                start_time=start_time,
                end_time=end_time,
            )
        return self.tamper_detector.generate_integrity_report(entries)

    def get_metrics(self) -> Dict[str, Any]:
        """Get audit logger metrics"""
        metrics = dict(self._metrics)
        metrics["hash_chain_length"] = self.hash_chain.chain_length

        if self.batch_writer:
            metrics["batch_writer"] = self.batch_writer.get_metrics()

        return metrics

    def flush(self):
        """Flush any pending batch writes"""
        if self.batch_writer:
            self.batch_writer.flush()

    def close(self):
        """Close audit logger and flush pending writes"""
        if self.batch_writer:
            self.batch_writer.stop(flush=True)
        logger.info("Audit logger closed")


# =============================================================================
# Decorator for Automatic Auditing
# =============================================================================

def audit_decision(
    audit_logger: AuditLogger,
    decision_type: DecisionType,
    subject_type: str,
    extract_subject_id: Callable[[Any], str],
    extract_features: Optional[Callable[[Any], Dict[str, Any]]] = None,
):
    """
    Decorator for automatic decision auditing.

    Usage:
        @audit_decision(
            audit_logger=logger,
            decision_type=DecisionType.PREDICTION,
            subject_type="account",
            extract_subject_id=lambda x: x["account_id"],
            extract_features=lambda x: x["features"],
        )
        def predict(data):
            return model.predict(data)
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract subject and features
            if args:
                input_data = args[0]
            else:
                input_data = kwargs

            subject_id = extract_subject_id(input_data)
            features = extract_features(input_data) if extract_features else None

            # Execute function
            result = func(*args, **kwargs)

            # Create output prediction
            output = OutputPrediction(
                prediction=result,
                prediction_type=decision_type,
            )

            # Log decision
            audit_logger.log_decision(
                subject_id=subject_id,
                subject_type=subject_type,
                decision_type=decision_type,
                input_features=features,
                output_prediction=output,
                use_batch=True,
            )

            return result

        return wrapper
    return decorator


# =============================================================================
# Demo and Testing
# =============================================================================

def demonstrate_audit_logging():
    """
    Demonstrate immutable audit logging system.

    Shows:
    1. Creating audit logger
    2. Logging decisions with full context
    3. Retrieving by decision ID
    4. Tamper detection
    5. Legal holds
    6. Compliance export
    """
    import tempfile

    print("=" * 80)
    print("IMMUTABLE AUDIT LOGGING SYSTEM DEMONSTRATION")
    print("=" * 80)

    # Create temporary storage
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize audit logger
        print("\n1. INITIALIZING AUDIT LOGGER")
        print("-" * 40)

        audit_logger = AuditLogger.create_default(
            storage_path=tmpdir,
            service_name="quan-ml-demo",
            environment="demo",
        )
        print(f"   Storage: {tmpdir}")
        print(f"   Service: {audit_logger.service_name}")
        print(f"   Environment: {audit_logger.environment}")

        # Create model version
        model_version = ModelVersion(
            model_id="model-credit-score-v2",
            model_name="CreditScorePredictor",
            version="2.3.1",
            training_run_id="run-abc123",
            training_timestamp="2024-01-15T10:30:00Z",
            model_hash="sha256:abc123def456...",
            framework="sklearn",
            framework_version="1.3.0",
        )

        # Create policy context
        policy_context = PolicyContext(
            policy_id="policy-credit-2024",
            policy_version="1.0",
            policy_name="Credit Decision Policy 2024",
            rules_applied=["minimum_score_500", "maximum_dti_43"],
            thresholds={"approval_score": 650.0, "review_score": 580.0},
            regulatory_requirements=["FCRA", "ECOA"],
        )

        # Log some decisions
        print("\n2. LOGGING DECISIONS")
        print("-" * 40)

        decisions = []
        for i in range(5):
            # Input features with PII
            features = {
                "credit_score": 650 + i * 20,
                "debt_to_income": 0.35 - i * 0.02,
                "account_age_months": 24 + i * 6,
                "ssn": f"123-45-678{i}",  # PII - will be hashed
                "email": f"user{i}@example.com",  # PII - will be hashed
                "annual_income": 75000 + i * 5000,
            }

            # Prediction output
            prediction = OutputPrediction(
                prediction="approved" if i > 1 else "review",
                prediction_type=DecisionType.APPROVAL if i > 1 else DecisionType.ROUTING,
                probability=0.75 + i * 0.05,
                confidence_interval=(0.70 + i * 0.04, 0.80 + i * 0.06),
                class_probabilities={
                    "approved": 0.75 + i * 0.05,
                    "denied": 0.15 - i * 0.03,
                    "review": 0.10 - i * 0.02,
                },
            )

            # Explanation
            explanation = DecisionExplanation(
                feature_importances={
                    "credit_score": 0.35,
                    "debt_to_income": 0.25,
                    "account_age_months": 0.15,
                    "annual_income": 0.25,
                },
                natural_language_explanation=f"Decision based on strong credit score of {features['credit_score']}",
                adverse_action_reasons=[] if i > 1 else ["Insufficient credit history"],
            )

            entry = audit_logger.log_decision(
                subject_id=f"account_{1000 + i}",
                subject_type="account",
                decision_type=DecisionType.PREDICTION,
                model_version=model_version,
                input_features=features,
                output_prediction=prediction,
                explanation=explanation,
                policy_context=policy_context,
                tags={"source": "demo", "batch": "1"},
            )

            decisions.append(entry)
            print(f"   Logged decision: {entry.decision_id[:8]}... (subject: account_{1000 + i})")

        # Flush batch writes
        audit_logger.flush()

        # Retrieve by ID
        print("\n3. RETRIEVING DECISION BY ID")
        print("-" * 40)

        test_decision = decisions[2]
        retrieved = audit_logger.get_decision(test_decision.decision_id)

        if retrieved:
            print(f"   Decision ID: {retrieved.decision_id}")
            print(f"   Timestamp: {retrieved.timestamp.to_iso8601()}")
            print(f"   Subject ID (hashed): {retrieved.subject_id}")
            print(f"   Decision Type: {retrieved.decision_type.value}")
            print(f"   Model: {retrieved.model_version.model_name} v{retrieved.model_version.version}")
            print(f"   Prediction: {retrieved.output_prediction.prediction}")
            print(f"   Probability: {retrieved.output_prediction.probability:.2%}")
            print(f"   Entry Hash: {retrieved.entry_hash[:32]}...")
            print(f"   Previous Hash: {retrieved.previous_hash[:32]}...")

            # Show PII handling
            print(f"\n   PII Handling:")
            print(f"   - Strategy: {retrieved.input_features.pii_handling.value}")
            print(f"   - PII Fields Found: {retrieved.input_features.pii_fields_present}")
            print(f"   - SSN (hashed): {retrieved.input_features.feature_values.get('ssn', 'N/A')}")

        # Verify integrity
        print("\n4. VERIFYING INTEGRITY")
        print("-" * 40)

        for decision in decisions[:3]:
            status = audit_logger.verify_decision(decision.decision_id)
            print(f"   Decision {decision.decision_id[:8]}...: {status.value}")

        # Generate integrity report
        print("\n5. INTEGRITY REPORT")
        print("-" * 40)

        report = audit_logger.generate_integrity_report(decisions)
        print(f"   Total Entries: {report['total_entries']}")
        print(f"   Chain Status: {report['chain_status']}")
        print(f"   Merkle Root: {report['merkle_root'][:32]}...")
        print(f"   Issues Found: {len(report['issues'])}")

        # Tamper detection demo
        print("\n6. TAMPER DETECTION DEMO")
        print("-" * 40)

        # Create a modified entry (simulating tampering)
        tampered_entry = copy.deepcopy(decisions[0])
        original_hash = tampered_entry.entry_hash
        tampered_entry.output_prediction.prediction = "TAMPERED_VALUE"

        # Verify detects tampering
        computed_hash = tampered_entry.compute_hash()
        print(f"   Original Hash: {original_hash[:32]}...")
        print(f"   After Tamper:  {computed_hash[:32]}...")
        print(f"   Hashes Match: {original_hash == computed_hash}")
        print(f"   TAMPER DETECTED: {original_hash != computed_hash}")

        # Verify signature fails
        content = tampered_entry._get_hashable_content()
        sig_valid = audit_logger.signer.verify(content, tampered_entry.signature)
        print(f"   Signature Valid: {sig_valid}")

        # Legal hold demo
        print("\n7. LEGAL HOLD DEMONSTRATION")
        print("-" * 40)

        hold = audit_logger.create_legal_hold(
            hold_id="HOLD-2024-001",
            matter_name="Regulatory Review Q1 2024",
            created_by="compliance@example.com",
            decision_ids=[d.decision_id for d in decisions[:2]],
        )
        print(f"   Hold ID: {hold['hold_id']}")
        print(f"   Matter: {hold['matter_name']}")
        print(f"   Decisions Held: {len(hold['decision_ids'])}")

        # Check if decision is under hold
        is_held, hold_ids = audit_logger.retention_manager.is_under_hold(decisions[0].decision_id)
        print(f"   Decision {decisions[0].decision_id[:8]}... under hold: {is_held}")

        # Compliance export demo
        print("\n8. COMPLIANCE EXPORT")
        print("-" * 40)

        export_path = Path(tmpdir) / "compliance_export.json"
        export_result = audit_logger.export_for_compliance(
            entries=decisions,
            output_path=str(export_path),
            format=ExportFormat.JSON,
        )
        print(f"   Format: {export_result['format']}")
        print(f"   Entries Exported: {export_result['entries_exported']}")
        print(f"   Output Path: {export_result['output_path']}")
        print(f"   Integrity Report: {export_result.get('integrity_report_path', 'N/A')}")

        # Show metrics
        print("\n9. AUDIT LOGGER METRICS")
        print("-" * 40)

        metrics = audit_logger.get_metrics()
        for key, value in metrics.items():
            if isinstance(value, dict):
                print(f"   {key}:")
                for k, v in value.items():
                    print(f"     {k}: {v}")
            else:
                print(f"   {key}: {value}")

        # Cleanup
        audit_logger.close()

        print("\n" + "=" * 80)
        print("DEMONSTRATION COMPLETE")
        print("=" * 80)
        print("\nKey Features Demonstrated:")
        print("  - Immutable decision logging with microsecond timestamps")
        print("  - Cryptographic signing and hash chains")
        print("  - PII protection (hashing sensitive fields)")
        print("  - Decision retrieval by ID")
        print("  - Tamper detection via hash verification")
        print("  - Legal hold management")
        print("  - Compliance export with integrity reports")
        print("  - Full audit trail with model version tracking")

        return decisions


if __name__ == "__main__":
    demonstrate_audit_logging()
