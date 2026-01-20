"""
QUAN Collections MLOps - Data Contracts and Canonical Datasets

This module provides comprehensive data contract management for ML training pipelines:
- Strict schema validation using Pydantic
- Canonical dataset definitions (train/val/calibration/test)
- PII redaction and tokenization
- DVC-compatible versioning interface
- Time-based and cohort-stratified sampling
- Hash-based deterministic splitting
- Full data lineage tracking

Author: QUAN MLOps Team
Version: 1.0.0
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
    ValidationError,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Type Variables and Constants
# ============================================================================

T = TypeVar("T", bound=BaseModel)

# Default hash salt for deterministic splitting (override in production)
DEFAULT_SPLIT_SALT = "quan-mlops-canonical-v1"

# PII patterns for detection and redaction
PII_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b"),
    "ssn_last4": re.compile(r"\b(?:SSN|ssn|last4)[\s:]*\d{4}\b"),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "bank_account": re.compile(r"\b\d{8,17}\b"),
    "dob": re.compile(r"\b(?:0[1-9]|1[0-2])/(?:0[1-9]|[12]\d|3[01])/(?:19|20)\d{2}\b"),
    "address": re.compile(r"\b\d+\s+[A-Za-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Way|Circle|Cir)\b", re.IGNORECASE),
}


# ============================================================================
# Enums and Type Definitions
# ============================================================================

class DatasetSplit(str, Enum):
    """Canonical dataset split types."""
    TRAIN = "train"
    VALIDATION = "validation"
    CALIBRATION = "calibration"
    TEST = "test"
    HOLDOUT = "holdout"


class PIIType(str, Enum):
    """Types of PII requiring protection."""
    SSN = "ssn"
    SSN_LAST4 = "ssn_last4"
    PHONE = "phone"
    EMAIL = "email"
    CREDIT_CARD = "credit_card"
    BANK_ACCOUNT = "bank_account"
    DOB = "dob"
    NAME = "name"
    ADDRESS = "address"


class RedactionStrategy(str, Enum):
    """PII redaction strategies."""
    HASH = "hash"           # One-way hash with salt
    TOKEN = "token"         # Reversible tokenization
    MASK = "mask"           # Partial masking (e.g., ***-**-1234)
    REMOVE = "remove"       # Complete removal
    SYNTHETIC = "synthetic"  # Replace with synthetic data


class FeatureType(str, Enum):
    """ML feature types for schema definition."""
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    TEXT = "text"
    EMBEDDING = "embedding"
    ARRAY = "array"


class LabelType(str, Enum):
    """Label types for supervised learning."""
    BINARY = "binary"
    MULTICLASS = "multiclass"
    REGRESSION = "regression"
    MULTILABEL = "multilabel"
    RANKING = "ranking"


# ============================================================================
# Schema Definition Classes
# ============================================================================

class FeatureSchema(BaseModel):
    """Schema definition for a single feature."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="Feature name")
    dtype: FeatureType = Field(..., description="Feature data type")
    description: str = Field("", description="Feature description")
    nullable: bool = Field(False, description="Whether nulls are allowed")

    # Numeric constraints
    min_value: Optional[float] = Field(None, description="Minimum value (numeric)")
    max_value: Optional[float] = Field(None, description="Maximum value (numeric)")

    # Categorical constraints
    allowed_values: Optional[List[str]] = Field(None, description="Allowed categorical values")

    # Array constraints
    array_shape: Optional[List[int]] = Field(None, description="Expected array shape")

    # PII markers
    contains_pii: bool = Field(False, description="Whether feature contains PII")
    pii_type: Optional[PIIType] = Field(None, description="Type of PII if applicable")

    # Feature metadata
    is_target: bool = Field(False, description="Whether this is a target/label")
    feature_group: Optional[str] = Field(None, description="Feature group for organization")
    source_table: Optional[str] = Field(None, description="Source table for lineage")
    transformation: Optional[str] = Field(None, description="Transformation applied")

    @field_validator("allowed_values")
    @classmethod
    def validate_allowed_values(cls, v, info):
        if v is not None and info.data.get("dtype") != FeatureType.CATEGORICAL:
            raise ValueError("allowed_values only valid for categorical features")
        return v

    @field_validator("min_value", "max_value")
    @classmethod
    def validate_numeric_constraints(cls, v, info):
        if v is not None and info.data.get("dtype") != FeatureType.NUMERIC:
            raise ValueError("min/max values only valid for numeric features")
        return v


class LabelSchema(BaseModel):
    """Schema definition for target/label."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="Label name")
    label_type: LabelType = Field(..., description="Label type")
    description: str = Field("", description="Label description")

    # Binary/multiclass
    classes: Optional[List[str]] = Field(None, description="Class names")
    positive_class: Optional[str] = Field(None, description="Positive class for binary")

    # Regression
    min_value: Optional[float] = Field(None, description="Min value for regression")
    max_value: Optional[float] = Field(None, description="Max value for regression")

    # Observation window
    observation_window_days: int = Field(
        90, description="Days after snapshot to observe outcome"
    )

    # Label definition
    definition: str = Field(
        "", description="Precise definition of label for documentation"
    )


class DataSchema(BaseModel):
    """
    Complete data schema for ML training data with strict validation.

    Labeling Rules Documentation:
    ----------------------------
    Payment Labels:
    - paid_in_full: Balance reduced to $0 within observation window
    - partial_payment: Any payment > $0 reducing balance
    - payment_plan_active: Active payment arrangement with at least 1 payment
    - promise_to_pay: Verbal/written commitment without payment yet
    - no_response: No payment or meaningful engagement

    Contact Labels:
    - right_party_contact: Verified contact with account holder
    - wrong_party_contact: Contact with non-account holder
    - voicemail_left: Left voicemail, no callback
    - no_contact: Unable to reach via any channel

    Risk Labels:
    - high_risk: Predicted probability of default > 0.7
    - medium_risk: Predicted probability 0.3 - 0.7
    - low_risk: Predicted probability < 0.3
    """

    model_config = ConfigDict(extra="forbid")

    # Schema metadata
    name: str = Field(..., description="Schema name/identifier")
    version: str = Field(..., description="Schema version (semver)")
    description: str = Field("", description="Schema description")
    owner: str = Field("mlops-team", description="Schema owner")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Feature definitions
    features: List[FeatureSchema] = Field(
        default_factory=list, description="Feature schemas"
    )

    # Label definitions
    labels: List[LabelSchema] = Field(
        default_factory=list, description="Label schemas"
    )

    # Data quality rules
    min_rows: int = Field(1000, description="Minimum expected rows")
    max_null_ratio: float = Field(0.1, description="Maximum null ratio per column")

    # Time boundaries for temporal validation
    min_date: Optional[datetime] = Field(None, description="Earliest allowed date")
    max_date: Optional[datetime] = Field(None, description="Latest allowed date")

    # Entity key for splitting
    entity_key: str = Field("account_id", description="Primary entity key")
    timestamp_key: str = Field("snapshot_date", description="Timestamp column")

    # Labeling rules (embedded documentation)
    labeling_rules: Dict[str, str] = Field(
        default_factory=lambda: {
            "paid_in_full": "Balance reduced to $0 within observation_window_days",
            "partial_payment": "Any payment > $0 that reduces balance",
            "payment_plan": "Active payment arrangement with >= 1 payment made",
            "promise_to_pay": "Verbal/written commitment, no payment yet",
            "no_response": "No payment or meaningful engagement in window",
            "right_party_contact": "Verified contact with account holder",
            "wrong_party_contact": "Contact made with non-account holder",
            "bankruptcy": "Debtor filed bankruptcy during observation window",
            "dispute": "Debtor disputed debt validity",
            "cease_desist": "Debtor requested cease and desist",
        },
        description="Label definition rules"
    )

    @model_validator(mode="after")
    def validate_schema(self) -> "DataSchema":
        """Validate schema consistency."""
        feature_names = {f.name for f in self.features}

        # Check for duplicate feature names
        if len(feature_names) != len(self.features):
            raise ValueError("Duplicate feature names detected")

        # Check entity and timestamp keys exist
        all_names = feature_names | {l.name for l in self.labels}
        if self.entity_key not in all_names and self.entity_key not in feature_names:
            # entity_key might be implicit, just warn
            logger.warning(f"Entity key '{self.entity_key}' not in features")

        return self

    def get_feature(self, name: str) -> Optional[FeatureSchema]:
        """Get feature schema by name."""
        for f in self.features:
            if f.name == name:
                return f
        return None

    def get_pii_features(self) -> List[FeatureSchema]:
        """Get all features marked as containing PII."""
        return [f for f in self.features if f.contains_pii]

    def get_feature_names(self) -> List[str]:
        """Get list of all feature names."""
        return [f.name for f in self.features]

    def get_label_names(self) -> List[str]:
        """Get list of all label names."""
        return [l.name for l in self.labels]

    def to_yaml(self) -> str:
        """Export schema as YAML."""
        return yaml.dump(
            self.model_dump(mode="json"),
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "DataSchema":
        """Load schema from YAML."""
        data = yaml.safe_load(yaml_str)
        return cls(**data)

    @classmethod
    def from_yaml_file(cls, path: Union[str, Path]) -> "DataSchema":
        """Load schema from YAML file."""
        with open(path, "r") as f:
            return cls.from_yaml(f.read())


# ============================================================================
# PII Redaction Engine
# ============================================================================

@dataclass
class PIIToken:
    """Token representing redacted PII."""
    token_id: str
    pii_type: PIIType
    created_at: datetime = field(default_factory=datetime.utcnow)


class PIIRedactor:
    """
    PII redaction engine with multiple strategies.

    Handles:
    - SSN (full and last 4)
    - Phone numbers
    - Email addresses
    - Credit card numbers
    - Bank account numbers
    - Dates of birth
    - Physical addresses
    - Names
    """

    def __init__(
        self,
        salt: str = DEFAULT_SPLIT_SALT,
        default_strategy: RedactionStrategy = RedactionStrategy.HASH,
    ):
        self.salt = salt
        self.default_strategy = default_strategy
        self._token_vault: Dict[str, str] = {}  # token -> original (if tokenizing)
        self._reverse_vault: Dict[str, str] = {}  # original_hash -> token

        # Strategy per PII type
        self.strategies: Dict[PIIType, RedactionStrategy] = {
            PIIType.SSN: RedactionStrategy.HASH,
            PIIType.SSN_LAST4: RedactionStrategy.MASK,
            PIIType.PHONE: RedactionStrategy.TOKEN,
            PIIType.EMAIL: RedactionStrategy.TOKEN,
            PIIType.CREDIT_CARD: RedactionStrategy.HASH,
            PIIType.BANK_ACCOUNT: RedactionStrategy.HASH,
            PIIType.DOB: RedactionStrategy.MASK,
            PIIType.NAME: RedactionStrategy.TOKEN,
            PIIType.ADDRESS: RedactionStrategy.REMOVE,
        }

        # Synthetic data generators
        self._synthetic_generators: Dict[PIIType, Callable[[], str]] = {
            PIIType.PHONE: lambda: f"+1555{secrets.randbelow(10000000):07d}",
            PIIType.EMAIL: lambda: f"user_{secrets.token_hex(4)}@redacted.quan",
            PIIType.NAME: lambda: f"REDACTED_{secrets.token_hex(4).upper()}",
        }

    def _hash_value(self, value: str, pii_type: PIIType) -> str:
        """Create salted hash of PII value."""
        combined = f"{self.salt}:{pii_type.value}:{value}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _tokenize_value(self, value: str, pii_type: PIIType) -> str:
        """Create reversible token for PII value."""
        value_hash = self._hash_value(value, pii_type)

        if value_hash in self._reverse_vault:
            return self._reverse_vault[value_hash]

        token = f"TOK_{pii_type.value.upper()}_{secrets.token_hex(8)}"
        self._token_vault[token] = value
        self._reverse_vault[value_hash] = token
        return token

    def _mask_value(self, value: str, pii_type: PIIType) -> str:
        """Partially mask PII value."""
        if pii_type == PIIType.SSN:
            # Show only last 4: ***-**-1234
            digits = re.sub(r"\D", "", value)
            return f"***-**-{digits[-4:]}" if len(digits) >= 4 else "***-**-****"

        elif pii_type == PIIType.SSN_LAST4:
            return "****"

        elif pii_type == PIIType.PHONE:
            # Show last 4: ***-***-1234
            digits = re.sub(r"\D", "", value)
            return f"***-***-{digits[-4:]}" if len(digits) >= 4 else "***-***-****"

        elif pii_type == PIIType.EMAIL:
            # Show domain: ****@domain.com
            parts = value.split("@")
            if len(parts) == 2:
                return f"****@{parts[1]}"
            return "****@****.***"

        elif pii_type == PIIType.DOB:
            # Show only year: **/*/1985
            match = re.search(r"(19|20)\d{2}", value)
            if match:
                return f"**/**/{match.group()}"
            return "**/**/****"

        elif pii_type == PIIType.CREDIT_CARD:
            # Show last 4: ****-****-****-1234
            digits = re.sub(r"\D", "", value)
            return f"****-****-****-{digits[-4:]}" if len(digits) >= 4 else "****"

        return "*" * len(value)

    def _generate_synthetic(self, pii_type: PIIType) -> str:
        """Generate synthetic replacement data."""
        generator = self._synthetic_generators.get(pii_type)
        if generator:
            return generator()
        return f"SYNTHETIC_{pii_type.value.upper()}"

    def redact(
        self,
        value: str,
        pii_type: PIIType,
        strategy: Optional[RedactionStrategy] = None,
    ) -> str:
        """
        Redact a single PII value.

        Args:
            value: The PII value to redact
            pii_type: Type of PII
            strategy: Override default strategy

        Returns:
            Redacted value
        """
        if not value:
            return value

        strategy = strategy or self.strategies.get(pii_type, self.default_strategy)

        if strategy == RedactionStrategy.HASH:
            return self._hash_value(value, pii_type)
        elif strategy == RedactionStrategy.TOKEN:
            return self._tokenize_value(value, pii_type)
        elif strategy == RedactionStrategy.MASK:
            return self._mask_value(value, pii_type)
        elif strategy == RedactionStrategy.REMOVE:
            return ""
        elif strategy == RedactionStrategy.SYNTHETIC:
            return self._generate_synthetic(pii_type)

        return self._hash_value(value, pii_type)

    def redact_record(
        self,
        record: Dict[str, Any],
        schema: DataSchema,
    ) -> Dict[str, Any]:
        """
        Redact all PII fields in a record based on schema.

        Args:
            record: Data record
            schema: Schema defining PII fields

        Returns:
            Record with PII redacted
        """
        redacted = record.copy()

        for feature in schema.get_pii_features():
            if feature.name in redacted and redacted[feature.name]:
                pii_type = feature.pii_type or PIIType.NAME
                redacted[feature.name] = self.redact(
                    str(redacted[feature.name]), pii_type
                )

        return redacted

    def detect_pii(self, text: str) -> List[Tuple[PIIType, str, int, int]]:
        """
        Detect PII in free text.

        Args:
            text: Text to scan

        Returns:
            List of (pii_type, matched_value, start_pos, end_pos)
        """
        findings = []

        for pii_type_str, pattern in PII_PATTERNS.items():
            pii_type = PIIType(pii_type_str) if pii_type_str in [e.value for e in PIIType] else None
            if pii_type is None:
                continue

            for match in pattern.finditer(text):
                findings.append((
                    pii_type,
                    match.group(),
                    match.start(),
                    match.end(),
                ))

        return findings

    def redact_text(self, text: str) -> str:
        """
        Redact all detected PII from free text.

        Args:
            text: Text containing potential PII

        Returns:
            Text with PII redacted
        """
        findings = self.detect_pii(text)

        # Sort by position descending to replace from end
        findings.sort(key=lambda x: x[2], reverse=True)

        result = text
        for pii_type, value, start, end in findings:
            redacted = self.redact(value, pii_type)
            result = result[:start] + redacted + result[end:]

        return result

    def detokenize(self, token: str) -> Optional[str]:
        """
        Reverse tokenization if token exists in vault.

        Args:
            token: Token to reverse

        Returns:
            Original value or None if not found
        """
        return self._token_vault.get(token)

    def export_token_vault(self) -> Dict[str, str]:
        """Export token vault for secure storage."""
        return self._token_vault.copy()

    def import_token_vault(self, vault: Dict[str, str]) -> None:
        """Import token vault from secure storage."""
        self._token_vault.update(vault)
        # Rebuild reverse vault
        for token, value in vault.items():
            # Extract PII type from token
            parts = token.split("_")
            if len(parts) >= 2:
                try:
                    pii_type = PIIType(parts[1].lower())
                    value_hash = self._hash_value(value, pii_type)
                    self._reverse_vault[value_hash] = token
                except ValueError:
                    pass


# ============================================================================
# Sampling Strategies
# ============================================================================

class SamplingStrategy(ABC):
    """Abstract base class for sampling strategies."""

    @abstractmethod
    def sample(
        self,
        records: List[Dict[str, Any]],
        n: int,
        seed: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Sample n records from the dataset."""
        pass


class HashBasedSampler(SamplingStrategy):
    """
    Deterministic hash-based sampling for reproducibility.

    Uses entity key hash to ensure same entity always maps to same split.
    """

    def __init__(
        self,
        entity_key: str = "account_id",
        salt: str = DEFAULT_SPLIT_SALT,
    ):
        self.entity_key = entity_key
        self.salt = salt

    def _hash_entity(self, entity_id: str) -> float:
        """Hash entity ID to value in [0, 1)."""
        combined = f"{self.salt}:{entity_id}"
        hash_bytes = hashlib.md5(combined.encode()).digest()
        hash_int = int.from_bytes(hash_bytes[:8], byteorder="big")
        return hash_int / (2 ** 64)

    def sample(
        self,
        records: List[Dict[str, Any]],
        n: int,
        seed: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Sample n records using hash-based selection."""
        # Sort by hash value and take top n
        sorted_records = sorted(
            records,
            key=lambda r: self._hash_entity(str(r.get(self.entity_key, "")))
        )
        return sorted_records[:n]

    def assign_split(
        self,
        entity_id: str,
        split_ratios: Dict[DatasetSplit, float],
    ) -> DatasetSplit:
        """
        Assign entity to a split based on hash.

        Args:
            entity_id: Entity identifier
            split_ratios: Dict of split -> ratio (must sum to 1.0)

        Returns:
            Assigned split
        """
        hash_value = self._hash_entity(entity_id)

        cumulative = 0.0
        for split, ratio in split_ratios.items():
            cumulative += ratio
            if hash_value < cumulative:
                return split

        return list(split_ratios.keys())[-1]


class TimeWindowSampler(SamplingStrategy):
    """
    Time-window based sampling to prevent data leakage.

    Ensures training data comes before validation/test data temporally.
    """

    def __init__(
        self,
        timestamp_key: str = "snapshot_date",
        buffer_days: int = 7,
    ):
        self.timestamp_key = timestamp_key
        self.buffer_days = buffer_days

    def _parse_timestamp(self, value: Any) -> datetime:
        """Parse timestamp from various formats."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            # Try common formats
            for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Cannot parse timestamp: {value}")
        raise TypeError(f"Invalid timestamp type: {type(value)}")

    def sample(
        self,
        records: List[Dict[str, Any]],
        n: int,
        seed: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Sample n records from time window."""
        sorted_records = sorted(
            records,
            key=lambda r: self._parse_timestamp(r.get(self.timestamp_key))
        )
        return sorted_records[:n]

    def split_by_time(
        self,
        records: List[Dict[str, Any]],
        train_end: datetime,
        val_end: datetime,
        test_end: Optional[datetime] = None,
    ) -> Dict[DatasetSplit, List[Dict[str, Any]]]:
        """
        Split records by time windows.

        Timeline:
        [--------TRAIN--------][GAP][---VAL---][GAP][---TEST---]

        Args:
            records: All records
            train_end: End of training window
            val_end: End of validation window
            test_end: End of test window (None = all remaining)

        Returns:
            Dict mapping split to records
        """
        buffer = timedelta(days=self.buffer_days)

        splits = {
            DatasetSplit.TRAIN: [],
            DatasetSplit.VALIDATION: [],
            DatasetSplit.TEST: [],
        }

        for record in records:
            ts = self._parse_timestamp(record.get(self.timestamp_key))

            if ts <= train_end:
                splits[DatasetSplit.TRAIN].append(record)
            elif ts > train_end + buffer and ts <= val_end:
                splits[DatasetSplit.VALIDATION].append(record)
            elif ts > val_end + buffer:
                if test_end is None or ts <= test_end:
                    splits[DatasetSplit.TEST].append(record)

        return splits


class CohortStratifier:
    """
    Stratified sampling across cohorts for balanced representation.

    Cohort dimensions:
    - Debt amount buckets
    - Account age buckets
    - Channel (BNPL, Bank, Subscription)
    - Risk tier
    - Geographic region
    """

    # Default bucket definitions
    DEBT_BUCKETS = [
        (0, 100, "micro"),
        (100, 500, "small"),
        (500, 1000, "medium"),
        (1000, 5000, "large"),
        (5000, float("inf"), "xlarge"),
    ]

    AGE_BUCKETS = [
        (0, 30, "fresh"),
        (30, 90, "aging"),
        (90, 180, "old"),
        (180, 365, "very_old"),
        (365, float("inf"), "ancient"),
    ]

    def __init__(
        self,
        debt_field: str = "balance",
        age_field: str = "days_overdue",
        channel_field: str = "account_type",
        region_field: str = "debtor_state",
    ):
        self.debt_field = debt_field
        self.age_field = age_field
        self.channel_field = channel_field
        self.region_field = region_field

    def _bucket_value(
        self,
        value: float,
        buckets: List[Tuple[float, float, str]],
    ) -> str:
        """Assign value to bucket."""
        for low, high, name in buckets:
            if low <= value < high:
                return name
        return "unknown"

    def get_cohort(self, record: Dict[str, Any]) -> str:
        """
        Get cohort identifier for a record.

        Returns:
            Cohort string like "medium_aging_bnpl_CA"
        """
        debt = self._bucket_value(
            record.get(self.debt_field, 0),
            self.DEBT_BUCKETS
        )
        age = self._bucket_value(
            record.get(self.age_field, 0),
            self.AGE_BUCKETS
        )
        channel = record.get(self.channel_field, "unknown")
        region = record.get(self.region_field, "XX")

        return f"{debt}_{age}_{channel}_{region}"

    def stratified_split(
        self,
        records: List[Dict[str, Any]],
        split_ratios: Dict[DatasetSplit, float],
        entity_key: str = "account_id",
        min_cohort_size: int = 10,
    ) -> Dict[DatasetSplit, List[Dict[str, Any]]]:
        """
        Perform stratified split maintaining cohort proportions.

        Args:
            records: All records
            split_ratios: Ratio per split (must sum to 1.0)
            entity_key: Entity identifier field
            min_cohort_size: Minimum records per cohort to stratify

        Returns:
            Dict mapping split to records
        """
        # Group by cohort
        cohorts: Dict[str, List[Dict[str, Any]]] = {}
        for record in records:
            cohort = self.get_cohort(record)
            if cohort not in cohorts:
                cohorts[cohort] = []
            cohorts[cohort].append(record)

        # Initialize splits
        splits = {split: [] for split in split_ratios.keys()}

        # Use hash-based assignment within each cohort
        hasher = HashBasedSampler(entity_key=entity_key)

        for cohort_name, cohort_records in cohorts.items():
            if len(cohort_records) < min_cohort_size:
                # Small cohort: all go to training
                splits[DatasetSplit.TRAIN].extend(cohort_records)
                continue

            # Assign each record to split
            for record in cohort_records:
                entity_id = str(record.get(entity_key, ""))
                assigned_split = hasher.assign_split(entity_id, split_ratios)
                splits[assigned_split].append(record)

        return splits

    def get_cohort_statistics(
        self,
        records: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, int]]:
        """
        Get statistics per cohort.

        Returns:
            Dict of cohort -> {count, ...stats}
        """
        stats: Dict[str, Dict[str, Any]] = {}

        for record in records:
            cohort = self.get_cohort(record)
            if cohort not in stats:
                stats[cohort] = {
                    "count": 0,
                    "total_balance": 0.0,
                    "total_age": 0,
                }

            stats[cohort]["count"] += 1
            stats[cohort]["total_balance"] += record.get(self.debt_field, 0)
            stats[cohort]["total_age"] += record.get(self.age_field, 0)

        # Calculate averages
        for cohort in stats:
            count = stats[cohort]["count"]
            if count > 0:
                stats[cohort]["avg_balance"] = stats[cohort]["total_balance"] / count
                stats[cohort]["avg_age"] = stats[cohort]["total_age"] / count

        return stats


# ============================================================================
# Data Contract Enforcement
# ============================================================================

@dataclass
class ValidationResult:
    """Result of schema validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


class DataContractEnforcer:
    """
    Enforces data contracts via schema validation.

    Validates:
    - Schema compliance (types, constraints)
    - Data quality (nulls, outliers)
    - PII handling
    - Temporal boundaries
    """

    def __init__(self, schema: DataSchema):
        self.schema = schema
        self._feature_map = {f.name: f for f in schema.features}

    def validate_record(self, record: Dict[str, Any]) -> ValidationResult:
        """
        Validate a single record against schema.

        Args:
            record: Data record

        Returns:
            Validation result
        """
        errors = []
        warnings = []

        for feature in self.schema.features:
            value = record.get(feature.name)

            # Check nulls
            if value is None:
                if not feature.nullable:
                    errors.append(f"Non-nullable field '{feature.name}' is null")
                continue

            # Type validation
            try:
                self._validate_type(value, feature)
            except ValueError as e:
                errors.append(f"Field '{feature.name}': {str(e)}")

            # Constraint validation
            constraint_errors = self._validate_constraints(value, feature)
            errors.extend(constraint_errors)

            # PII check
            if feature.contains_pii:
                if not self._is_redacted(value, feature):
                    warnings.append(f"PII field '{feature.name}' may not be redacted")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def _validate_type(self, value: Any, feature: FeatureSchema) -> None:
        """Validate value type matches schema."""
        if feature.dtype == FeatureType.NUMERIC:
            if not isinstance(value, (int, float)):
                raise ValueError(f"Expected numeric, got {type(value).__name__}")

        elif feature.dtype == FeatureType.CATEGORICAL:
            if not isinstance(value, str):
                raise ValueError(f"Expected string, got {type(value).__name__}")

        elif feature.dtype == FeatureType.BOOLEAN:
            if not isinstance(value, bool):
                raise ValueError(f"Expected boolean, got {type(value).__name__}")

        elif feature.dtype == FeatureType.DATETIME:
            if not isinstance(value, (datetime, str)):
                raise ValueError(f"Expected datetime, got {type(value).__name__}")

        elif feature.dtype == FeatureType.ARRAY:
            if not isinstance(value, (list, tuple)):
                raise ValueError(f"Expected array, got {type(value).__name__}")

    def _validate_constraints(
        self,
        value: Any,
        feature: FeatureSchema,
    ) -> List[str]:
        """Validate value against constraints."""
        errors = []

        if feature.dtype == FeatureType.NUMERIC:
            if feature.min_value is not None and value < feature.min_value:
                errors.append(
                    f"Field '{feature.name}' value {value} below min {feature.min_value}"
                )
            if feature.max_value is not None and value > feature.max_value:
                errors.append(
                    f"Field '{feature.name}' value {value} above max {feature.max_value}"
                )

        elif feature.dtype == FeatureType.CATEGORICAL:
            if feature.allowed_values and value not in feature.allowed_values:
                errors.append(
                    f"Field '{feature.name}' value '{value}' not in allowed values"
                )

        elif feature.dtype == FeatureType.ARRAY:
            if feature.array_shape:
                actual_shape = self._get_array_shape(value)
                if actual_shape != tuple(feature.array_shape):
                    errors.append(
                        f"Field '{feature.name}' shape {actual_shape} != expected {feature.array_shape}"
                    )

        return errors

    def _get_array_shape(self, arr: Any) -> Tuple[int, ...]:
        """Get shape of nested list/array."""
        if not isinstance(arr, (list, tuple)):
            return ()
        if len(arr) == 0:
            return (0,)
        return (len(arr),) + self._get_array_shape(arr[0])

    def _is_redacted(self, value: Any, feature: FeatureSchema) -> bool:
        """Check if PII value appears to be redacted."""
        if not isinstance(value, str):
            return False

        # Check for common redaction patterns
        redaction_patterns = [
            r"^TOK_",           # Token
            r"^[a-f0-9]{16}$",  # Hash
            r"\*{3,}",          # Masking
            r"^REDACTED",       # Explicit redaction
            r"^SYNTHETIC",      # Synthetic data
        ]

        return any(re.search(p, value) for p in redaction_patterns)

    def validate_dataset(
        self,
        records: List[Dict[str, Any]],
        sample_size: Optional[int] = None,
    ) -> ValidationResult:
        """
        Validate entire dataset against schema.

        Args:
            records: All records
            sample_size: Validate only a sample (None = all)

        Returns:
            Aggregated validation result
        """
        if sample_size and len(records) > sample_size:
            # Random sample for large datasets
            import random
            records = random.sample(records, sample_size)

        all_errors = []
        all_warnings = []
        invalid_count = 0
        null_counts: Dict[str, int] = {f.name: 0 for f in self.schema.features}

        for i, record in enumerate(records):
            result = self.validate_record(record)

            if not result.is_valid:
                invalid_count += 1
                # Limit error collection
                if len(all_errors) < 100:
                    for err in result.errors:
                        all_errors.append(f"Record {i}: {err}")

            all_warnings.extend(result.warnings[:10])

            # Count nulls
            for feature in self.schema.features:
                if record.get(feature.name) is None:
                    null_counts[feature.name] += 1

        # Check minimum rows
        if len(records) < self.schema.min_rows:
            all_errors.append(
                f"Dataset has {len(records)} rows, minimum is {self.schema.min_rows}"
            )

        # Check null ratios
        for feature_name, null_count in null_counts.items():
            null_ratio = null_count / len(records) if records else 0
            if null_ratio > self.schema.max_null_ratio:
                all_warnings.append(
                    f"Field '{feature_name}' has {null_ratio:.1%} nulls (max {self.schema.max_null_ratio:.1%})"
                )

        return ValidationResult(
            is_valid=invalid_count == 0 and len(all_errors) == 0,
            errors=all_errors,
            warnings=list(set(all_warnings))[:50],
            stats={
                "total_records": len(records),
                "invalid_records": invalid_count,
                "null_counts": null_counts,
            },
        )


# ============================================================================
# Data Lineage Tracking
# ============================================================================

@dataclass
class LineageNode:
    """Node in data lineage graph."""
    node_id: str
    node_type: str  # "source", "transform", "output"
    name: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LineageEdge:
    """Edge in data lineage graph."""
    source_id: str
    target_id: str
    transform_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataLineageTracker:
    """
    Track data lineage for reproducibility and auditing.

    Records:
    - Source datasets and versions
    - Transformations applied
    - Output artifacts
    - Hash checksums
    """

    def __init__(self, run_id: Optional[str] = None):
        self.run_id = run_id or f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        self.nodes: Dict[str, LineageNode] = {}
        self.edges: List[LineageEdge] = []
        self.checksums: Dict[str, str] = {}

    def add_source(
        self,
        name: str,
        path: str,
        version: Optional[str] = None,
        row_count: Optional[int] = None,
    ) -> str:
        """
        Register a source dataset.

        Returns:
            Node ID
        """
        node_id = f"source_{name}_{secrets.token_hex(4)}"

        self.nodes[node_id] = LineageNode(
            node_id=node_id,
            node_type="source",
            name=name,
            metadata={
                "path": path,
                "version": version,
                "row_count": row_count,
            },
        )

        return node_id

    def add_transform(
        self,
        name: str,
        source_ids: List[str],
        transform_type: str,
        parameters: Dict[str, Any],
    ) -> str:
        """
        Register a transformation.

        Returns:
            Node ID
        """
        node_id = f"transform_{name}_{secrets.token_hex(4)}"

        self.nodes[node_id] = LineageNode(
            node_id=node_id,
            node_type="transform",
            name=name,
            metadata={
                "transform_type": transform_type,
                "parameters": parameters,
            },
        )

        # Add edges from sources
        for source_id in source_ids:
            self.edges.append(LineageEdge(
                source_id=source_id,
                target_id=node_id,
                transform_type=transform_type,
            ))

        return node_id

    def add_output(
        self,
        name: str,
        source_ids: List[str],
        path: str,
        row_count: int,
        checksum: Optional[str] = None,
    ) -> str:
        """
        Register an output artifact.

        Returns:
            Node ID
        """
        node_id = f"output_{name}_{secrets.token_hex(4)}"

        self.nodes[node_id] = LineageNode(
            node_id=node_id,
            node_type="output",
            name=name,
            metadata={
                "path": path,
                "row_count": row_count,
            },
        )

        if checksum:
            self.checksums[node_id] = checksum

        # Add edges from sources
        for source_id in source_ids:
            self.edges.append(LineageEdge(
                source_id=source_id,
                target_id=node_id,
                transform_type="output",
            ))

        return node_id

    def compute_checksum(self, data: List[Dict[str, Any]]) -> str:
        """Compute deterministic checksum for dataset."""
        # Sort records for determinism
        sorted_data = sorted(data, key=lambda r: json.dumps(r, sort_keys=True, default=str))
        data_str = json.dumps(sorted_data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Export lineage to dictionary."""
        return {
            "run_id": self.run_id,
            "created_at": datetime.utcnow().isoformat(),
            "nodes": {
                nid: {
                    "node_id": n.node_id,
                    "node_type": n.node_type,
                    "name": n.name,
                    "metadata": n.metadata,
                    "created_at": n.created_at.isoformat(),
                }
                for nid, n in self.nodes.items()
            },
            "edges": [
                {
                    "source_id": e.source_id,
                    "target_id": e.target_id,
                    "transform_type": e.transform_type,
                    "metadata": e.metadata,
                }
                for e in self.edges
            ],
            "checksums": self.checksums,
        }

    def save(self, path: Union[str, Path]) -> None:
        """Save lineage to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    @classmethod
    def load(cls, path: Union[str, Path]) -> "DataLineageTracker":
        """Load lineage from JSON file."""
        with open(path, "r") as f:
            data = json.load(f)

        tracker = cls(run_id=data["run_id"])

        for nid, node_data in data["nodes"].items():
            tracker.nodes[nid] = LineageNode(
                node_id=node_data["node_id"],
                node_type=node_data["node_type"],
                name=node_data["name"],
                metadata=node_data["metadata"],
                created_at=datetime.fromisoformat(node_data["created_at"]),
            )

        for edge_data in data["edges"]:
            tracker.edges.append(LineageEdge(
                source_id=edge_data["source_id"],
                target_id=edge_data["target_id"],
                transform_type=edge_data["transform_type"],
                metadata=edge_data.get("metadata", {}),
            ))

        tracker.checksums = data.get("checksums", {})

        return tracker


# ============================================================================
# DVC-Compatible Dataset Versioning
# ============================================================================

class DatasetVersionManager:
    """
    DVC-compatible dataset versioning interface.

    Supports:
    - Version tagging
    - Checksum verification
    - .dvc file generation
    - Remote storage integration
    """

    def __init__(
        self,
        base_path: Union[str, Path],
        remote_url: Optional[str] = None,
    ):
        self.base_path = Path(base_path)
        self.remote_url = remote_url
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _compute_md5(self, file_path: Path) -> str:
        """Compute MD5 hash of file."""
        md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
        return md5.hexdigest()

    def _compute_data_md5(self, data: List[Dict[str, Any]]) -> str:
        """Compute MD5 hash of data."""
        data_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.md5(data_str.encode()).hexdigest()

    def create_version(
        self,
        name: str,
        data: List[Dict[str, Any]],
        schema: DataSchema,
        split: DatasetSplit,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new dataset version.

        Args:
            name: Dataset name
            data: Dataset records
            schema: Data schema
            split: Dataset split
            metadata: Additional metadata

        Returns:
            Version info dict
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        version_id = f"{name}_{split.value}_{timestamp}"

        # Create version directory
        version_dir = self.base_path / name / version_id
        version_dir.mkdir(parents=True, exist_ok=True)

        # Save data as JSON Lines
        data_path = version_dir / f"{split.value}.jsonl"
        with open(data_path, "w") as f:
            for record in data:
                f.write(json.dumps(record, default=str) + "\n")

        # Save schema
        schema_path = version_dir / "schema.yaml"
        with open(schema_path, "w") as f:
            f.write(schema.to_yaml())

        # Compute checksums
        data_md5 = self._compute_md5(data_path)
        schema_md5 = self._compute_md5(schema_path)

        # Create .dvc file
        dvc_content = {
            "outs": [
                {
                    "md5": data_md5,
                    "size": data_path.stat().st_size,
                    "path": str(data_path.relative_to(self.base_path)),
                }
            ],
            "meta": {
                "version_id": version_id,
                "name": name,
                "split": split.value,
                "schema_version": schema.version,
                "schema_md5": schema_md5,
                "row_count": len(data),
                "created_at": datetime.utcnow().isoformat(),
                **(metadata or {}),
            },
        }

        dvc_path = version_dir / f"{split.value}.jsonl.dvc"
        with open(dvc_path, "w") as f:
            yaml.dump(dvc_content, f, default_flow_style=False)

        # Create version manifest
        manifest = {
            "version_id": version_id,
            "name": name,
            "split": split.value,
            "schema_version": schema.version,
            "row_count": len(data),
            "data_md5": data_md5,
            "schema_md5": schema_md5,
            "created_at": datetime.utcnow().isoformat(),
            "paths": {
                "data": str(data_path),
                "schema": str(schema_path),
                "dvc": str(dvc_path),
            },
            "metadata": metadata or {},
        }

        manifest_path = version_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        logger.info(f"Created dataset version: {version_id} ({len(data)} records)")

        return manifest

    def list_versions(self, name: str) -> List[Dict[str, Any]]:
        """List all versions of a dataset."""
        dataset_dir = self.base_path / name
        if not dataset_dir.exists():
            return []

        versions = []
        for version_dir in sorted(dataset_dir.iterdir()):
            if version_dir.is_dir():
                manifest_path = version_dir / "manifest.json"
                if manifest_path.exists():
                    with open(manifest_path, "r") as f:
                        versions.append(json.load(f))

        return versions

    def get_version(self, name: str, version_id: str) -> Optional[Dict[str, Any]]:
        """Get specific version manifest."""
        manifest_path = self.base_path / name / version_id / "manifest.json"
        if not manifest_path.exists():
            return None

        with open(manifest_path, "r") as f:
            return json.load(f)

    def load_version(
        self,
        name: str,
        version_id: str,
    ) -> Tuple[List[Dict[str, Any]], DataSchema]:
        """
        Load dataset version.

        Returns:
            Tuple of (records, schema)
        """
        manifest = self.get_version(name, version_id)
        if not manifest:
            raise ValueError(f"Version not found: {name}/{version_id}")

        # Load data
        data_path = Path(manifest["paths"]["data"])
        records = []
        with open(data_path, "r") as f:
            for line in f:
                records.append(json.loads(line.strip()))

        # Verify checksum
        actual_md5 = self._compute_md5(data_path)
        if actual_md5 != manifest["data_md5"]:
            raise ValueError(
                f"Checksum mismatch: expected {manifest['data_md5']}, got {actual_md5}"
            )

        # Load schema
        schema_path = Path(manifest["paths"]["schema"])
        schema = DataSchema.from_yaml_file(schema_path)

        return records, schema

    def get_latest_version(self, name: str, split: Optional[DatasetSplit] = None) -> Optional[Dict[str, Any]]:
        """Get the latest version of a dataset."""
        versions = self.list_versions(name)

        if split:
            versions = [v for v in versions if v["split"] == split.value]

        if not versions:
            return None

        return max(versions, key=lambda v: v["created_at"])

    def generate_dvc_pipeline(self, name: str) -> str:
        """
        Generate DVC pipeline YAML for dataset.

        Returns:
            DVC pipeline YAML content
        """
        pipeline = {
            "stages": {
                f"build_{name}": {
                    "cmd": f"python -m quan.mlops.data_contracts build --name {name}",
                    "deps": [
                        "quan/mlops/data_contracts.py",
                        f"configs/{name}_schema.yaml",
                    ],
                    "outs": [
                        f"data/{name}/train.jsonl",
                        f"data/{name}/validation.jsonl",
                        f"data/{name}/test.jsonl",
                    ],
                    "metrics": [
                        {"path": f"data/{name}/metrics.json", "cache": False},
                    ],
                },
            },
        }

        return yaml.dump(pipeline, default_flow_style=False)


# ============================================================================
# Labeling Rules Documentation
# ============================================================================

class LabelingRules:
    """
    Embedded labeling rules documentation and validation.

    Provides clear definitions for all labels used in ML training.
    """

    # Payment outcome labels
    PAYMENT_LABELS = {
        "paid_in_full": {
            "definition": "Account balance reduced to $0 within observation window",
            "conditions": [
                "Balance == 0 at observation end",
                "At least one payment received",
            ],
            "observation_window_days": 90,
            "example": "Balance $500 -> Payments totaling $500 -> Balance $0",
        },
        "partial_payment": {
            "definition": "One or more payments received but balance not fully resolved",
            "conditions": [
                "Total payments > $0",
                "Final balance > $0",
            ],
            "observation_window_days": 90,
            "example": "Balance $500 -> Payment $200 -> Balance $300",
        },
        "payment_plan_active": {
            "definition": "Consumer on active payment plan with at least one payment made",
            "conditions": [
                "Active payment arrangement exists",
                "At least 1 scheduled payment completed",
                "Not defaulted on arrangement",
            ],
            "observation_window_days": 90,
            "example": "Agreed to $50/month plan, made 2 payments",
        },
        "promise_to_pay": {
            "definition": "Consumer committed to pay but no payment received yet",
            "conditions": [
                "Documented promise to pay",
                "No payment received in window",
                "Promise date within observation window",
            ],
            "observation_window_days": 30,
            "example": "Consumer said will pay on Friday, no payment yet",
        },
        "no_response": {
            "definition": "No payment or meaningful engagement within window",
            "conditions": [
                "No payments",
                "No payment plan",
                "No promise to pay",
                "Contacts attempted (not cease/desist)",
            ],
            "observation_window_days": 90,
            "example": "Multiple contact attempts, no response or payment",
        },
    }

    # Contact outcome labels
    CONTACT_LABELS = {
        "right_party_contact": {
            "definition": "Verified two-way contact with the account holder",
            "conditions": [
                "Identity verified (security questions or confirmation)",
                "Two-way communication occurred",
            ],
            "example": "Called number, debtor answered, verified identity",
        },
        "wrong_party_contact": {
            "definition": "Contact made with someone other than account holder",
            "conditions": [
                "Person answered/responded",
                "Confirmed not the account holder",
            ],
            "example": "Called, roommate answered, confirmed wrong person",
        },
        "voicemail_left": {
            "definition": "Call completed but went to voicemail",
            "conditions": [
                "Call connected",
                "Voicemail/answering machine detected",
                "Message left (compliant mini-miranda)",
            ],
            "example": "Called, got voicemail, left compliant message",
        },
        "no_contact": {
            "definition": "Unable to establish contact via attempted channel",
            "conditions": [
                "Contact attempted",
                "No response/connection",
            ],
            "example": "Called 3 times, no answer, no voicemail",
        },
    }

    # Risk tier labels
    RISK_LABELS = {
        "high_risk": {
            "definition": "High probability of non-payment or adverse outcome",
            "threshold": "predicted_probability > 0.7",
            "conditions": [
                "Model score > 0.7",
                "OR manual override for known bad actors",
            ],
        },
        "medium_risk": {
            "definition": "Moderate probability, outcome uncertain",
            "threshold": "0.3 <= predicted_probability <= 0.7",
            "conditions": [
                "Model score between 0.3 and 0.7",
            ],
        },
        "low_risk": {
            "definition": "Low probability of non-payment",
            "threshold": "predicted_probability < 0.3",
            "conditions": [
                "Model score < 0.3",
                "No adverse signals",
            ],
        },
    }

    # Special status labels
    STATUS_LABELS = {
        "bankruptcy": {
            "definition": "Consumer filed for bankruptcy protection",
            "conditions": [
                "Bankruptcy filing confirmed",
                "Collection activity must cease",
            ],
            "legal_requirement": "Stop all collection activity",
        },
        "dispute": {
            "definition": "Consumer disputed debt validity",
            "conditions": [
                "Written or verbal dispute received",
                "Must validate debt before continuing",
            ],
            "legal_requirement": "FDCPA validation requirements",
        },
        "cease_desist": {
            "definition": "Consumer requested no further contact",
            "conditions": [
                "Written cease and desist received",
                "OR verbal request documented",
            ],
            "legal_requirement": "Stop all contact except legal notices",
        },
        "deceased": {
            "definition": "Account holder confirmed deceased",
            "conditions": [
                "Death confirmed via records or family",
            ],
            "legal_requirement": "Stop contact, handle per estate rules",
        },
        "active_military": {
            "definition": "Account holder on active military duty",
            "conditions": [
                "Active duty confirmed via SCRA database",
            ],
            "legal_requirement": "SCRA protections apply",
        },
    }

    @classmethod
    def get_label_definition(cls, label_name: str) -> Optional[Dict[str, Any]]:
        """Get definition for a label."""
        all_labels = {
            **cls.PAYMENT_LABELS,
            **cls.CONTACT_LABELS,
            **cls.RISK_LABELS,
            **cls.STATUS_LABELS,
        }
        return all_labels.get(label_name)

    @classmethod
    def validate_label(
        cls,
        label_name: str,
        label_value: Any,
        record: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that label value is consistent with record data.

        Returns:
            Tuple of (is_valid, error_message)
        """
        definition = cls.get_label_definition(label_name)
        if not definition:
            return False, f"Unknown label: {label_name}"

        # Payment label validation
        if label_name == "paid_in_full":
            current_balance = record.get("current_balance", record.get("balance", 0))
            if label_value == 1 and current_balance > 0:
                return False, f"paid_in_full=1 but balance={current_balance}"

        elif label_name == "partial_payment":
            payments = record.get("total_payments", 0)
            current_balance = record.get("current_balance", 0)
            if label_value == 1 and (payments <= 0 or current_balance <= 0):
                return False, f"partial_payment requires payments>0 and balance>0"

        # Risk label validation
        elif label_name in cls.RISK_LABELS:
            score = record.get("risk_score", record.get("model_score"))
            if score is not None:
                expected_label = cls._get_expected_risk_label(score)
                if label_value != expected_label:
                    return False, f"Risk label {label_value} inconsistent with score {score}"

        return True, None

    @classmethod
    def _get_expected_risk_label(cls, score: float) -> str:
        """Get expected risk label for score."""
        if score > 0.7:
            return "high_risk"
        elif score >= 0.3:
            return "medium_risk"
        else:
            return "low_risk"

    @classmethod
    def generate_documentation(cls) -> str:
        """Generate markdown documentation for all labels."""
        doc = ["# QUAN Collections ML Labeling Rules\n"]
        doc.append("This document defines all labels used in ML training.\n")

        sections = [
            ("Payment Outcome Labels", cls.PAYMENT_LABELS),
            ("Contact Outcome Labels", cls.CONTACT_LABELS),
            ("Risk Tier Labels", cls.RISK_LABELS),
            ("Special Status Labels", cls.STATUS_LABELS),
        ]

        for section_name, labels in sections:
            doc.append(f"\n## {section_name}\n")

            for label_name, label_def in labels.items():
                doc.append(f"\n### {label_name}\n")
                doc.append(f"**Definition:** {label_def['definition']}\n")

                if "conditions" in label_def:
                    doc.append("\n**Conditions:**\n")
                    for cond in label_def["conditions"]:
                        doc.append(f"- {cond}\n")

                if "observation_window_days" in label_def:
                    doc.append(f"\n**Observation Window:** {label_def['observation_window_days']} days\n")

                if "threshold" in label_def:
                    doc.append(f"\n**Threshold:** `{label_def['threshold']}`\n")

                if "example" in label_def:
                    doc.append(f"\n**Example:** {label_def['example']}\n")

                if "legal_requirement" in label_def:
                    doc.append(f"\n**Legal Requirement:** {label_def['legal_requirement']}\n")

        return "".join(doc)


# ============================================================================
# Canonical Dataset Builder
# ============================================================================

class CanonicalDatasetBuilder:
    """
    Build reproducible canonical datasets for ML training.

    Produces:
    - Training set (historical data)
    - Validation set (time-separated)
    - Calibration holdout (for probability calibration)
    - Test set (future data, time-separated)

    Features:
    - Time-based splitting to prevent leakage
    - Cohort stratification for balance
    - PII redaction
    - Schema validation
    - Full lineage tracking
    - DVC-compatible versioning
    """

    def __init__(
        self,
        schema: DataSchema,
        output_path: Union[str, Path],
        split_salt: str = DEFAULT_SPLIT_SALT,
    ):
        self.schema = schema
        self.output_path = Path(output_path)
        self.split_salt = split_salt

        # Initialize components
        self.pii_redactor = PIIRedactor(salt=split_salt)
        self.contract_enforcer = DataContractEnforcer(schema)
        self.stratifier = CohortStratifier()
        self.time_sampler = TimeWindowSampler(
            timestamp_key=schema.timestamp_key,
            buffer_days=7,
        )
        self.hash_sampler = HashBasedSampler(
            entity_key=schema.entity_key,
            salt=split_salt,
        )
        self.version_manager = DatasetVersionManager(self.output_path)
        self.lineage = DataLineageTracker()

    def build(
        self,
        records: List[Dict[str, Any]],
        train_end: datetime,
        val_end: datetime,
        test_end: Optional[datetime] = None,
        split_ratios: Optional[Dict[DatasetSplit, float]] = None,
        use_time_split: bool = True,
        stratify: bool = True,
        redact_pii: bool = True,
        validate: bool = True,
        version_name: Optional[str] = None,
    ) -> Dict[DatasetSplit, List[Dict[str, Any]]]:
        """
        Build canonical datasets from raw records.

        Args:
            records: Raw data records
            train_end: End of training period
            val_end: End of validation period
            test_end: End of test period (None = all remaining)
            split_ratios: Custom split ratios (default: 70/15/10/5)
            use_time_split: Use time-based splitting
            stratify: Apply cohort stratification
            redact_pii: Redact PII fields
            validate: Validate against schema
            version_name: Name for versioned output

        Returns:
            Dict mapping split to records
        """
        logger.info(f"Building canonical datasets from {len(records)} records")

        # Track source
        source_id = self.lineage.add_source(
            name="raw_records",
            path="input",
            row_count=len(records),
        )

        # Default split ratios
        if split_ratios is None:
            split_ratios = {
                DatasetSplit.TRAIN: 0.70,
                DatasetSplit.VALIDATION: 0.15,
                DatasetSplit.CALIBRATION: 0.10,
                DatasetSplit.TEST: 0.05,
            }

        # Step 1: PII Redaction
        if redact_pii:
            logger.info("Redacting PII fields...")
            records = [
                self.pii_redactor.redact_record(r, self.schema)
                for r in records
            ]

            redact_id = self.lineage.add_transform(
                name="pii_redaction",
                source_ids=[source_id],
                transform_type="redaction",
                parameters={"strategy": "schema_based"},
            )
            source_id = redact_id

        # Step 2: Schema Validation
        if validate:
            logger.info("Validating schema compliance...")
            validation_result = self.contract_enforcer.validate_dataset(records)

            if not validation_result.is_valid:
                logger.warning(
                    f"Schema validation found {len(validation_result.errors)} errors"
                )
                for error in validation_result.errors[:10]:
                    logger.warning(f"  {error}")

            if validation_result.warnings:
                for warning in validation_result.warnings[:5]:
                    logger.warning(f"  Warning: {warning}")

        # Step 3: Splitting
        if use_time_split:
            logger.info("Applying time-based splitting...")
            splits = self.time_sampler.split_by_time(
                records, train_end, val_end, test_end
            )

            # Further split validation for calibration
            if DatasetSplit.CALIBRATION in split_ratios:
                val_records = splits.get(DatasetSplit.VALIDATION, [])
                cal_ratio = split_ratios[DatasetSplit.CALIBRATION] / (
                    split_ratios.get(DatasetSplit.VALIDATION, 0.15) +
                    split_ratios[DatasetSplit.CALIBRATION]
                )

                # Use hash to split validation into val + calibration
                cal_records = []
                new_val_records = []

                for record in val_records:
                    entity_id = str(record.get(self.schema.entity_key, ""))
                    hash_val = self.hash_sampler._hash_entity(entity_id)
                    if hash_val < cal_ratio:
                        cal_records.append(record)
                    else:
                        new_val_records.append(record)

                splits[DatasetSplit.VALIDATION] = new_val_records
                splits[DatasetSplit.CALIBRATION] = cal_records

            split_id = self.lineage.add_transform(
                name="time_split",
                source_ids=[source_id],
                transform_type="temporal_split",
                parameters={
                    "train_end": train_end.isoformat(),
                    "val_end": val_end.isoformat(),
                    "test_end": test_end.isoformat() if test_end else None,
                },
            )
        else:
            logger.info("Applying hash-based splitting...")
            if stratify:
                splits = self.stratifier.stratified_split(
                    records, split_ratios, self.schema.entity_key
                )
            else:
                splits = {split: [] for split in split_ratios.keys()}
                for record in records:
                    entity_id = str(record.get(self.schema.entity_key, ""))
                    assigned = self.hash_sampler.assign_split(entity_id, split_ratios)
                    splits[assigned].append(record)

            split_id = self.lineage.add_transform(
                name="hash_split",
                source_ids=[source_id],
                transform_type="deterministic_split",
                parameters={
                    "ratios": {k.value: v for k, v in split_ratios.items()},
                    "stratified": stratify,
                },
            )

        # Step 4: Cohort Stratification (validation)
        if stratify:
            logger.info("Validating cohort distributions...")
            for split_name, split_records in splits.items():
                stats = self.stratifier.get_cohort_statistics(split_records)
                logger.info(f"  {split_name.value}: {len(split_records)} records, {len(stats)} cohorts")

        # Step 5: Versioning
        if version_name:
            logger.info(f"Creating versioned outputs as '{version_name}'...")
            for split_name, split_records in splits.items():
                if split_records:
                    manifest = self.version_manager.create_version(
                        name=version_name,
                        data=split_records,
                        schema=self.schema,
                        split=split_name,
                        metadata={
                            "train_end": train_end.isoformat(),
                            "val_end": val_end.isoformat(),
                            "stratified": stratify,
                            "pii_redacted": redact_pii,
                        },
                    )

                    # Track output
                    self.lineage.add_output(
                        name=f"{version_name}_{split_name.value}",
                        source_ids=[split_id],
                        path=manifest["paths"]["data"],
                        row_count=len(split_records),
                        checksum=manifest["data_md5"],
                    )

        # Save lineage
        lineage_path = self.output_path / "lineage" / f"{self.lineage.run_id}.json"
        lineage_path.parent.mkdir(parents=True, exist_ok=True)
        self.lineage.save(lineage_path)
        logger.info(f"Saved lineage to {lineage_path}")

        # Log summary
        logger.info("Dataset build complete:")
        for split_name, split_records in splits.items():
            logger.info(f"  {split_name.value}: {len(split_records)} records")

        return splits

    def get_build_metrics(
        self,
        splits: Dict[DatasetSplit, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """
        Compute metrics for built datasets.

        Returns:
            Dict of metrics
        """
        metrics = {
            "build_timestamp": datetime.utcnow().isoformat(),
            "schema_name": self.schema.name,
            "schema_version": self.schema.version,
            "splits": {},
        }

        total_records = sum(len(records) for records in splits.values())

        for split_name, records in splits.items():
            split_metrics = {
                "count": len(records),
                "ratio": len(records) / total_records if total_records > 0 else 0,
            }

            # Compute cohort distribution
            cohort_stats = self.stratifier.get_cohort_statistics(records)
            split_metrics["cohort_count"] = len(cohort_stats)
            split_metrics["largest_cohort"] = max(
                (s["count"] for s in cohort_stats.values()),
                default=0
            )
            split_metrics["smallest_cohort"] = min(
                (s["count"] for s in cohort_stats.values()),
                default=0
            )

            # Compute label distribution if labels present
            for label in self.schema.labels:
                label_values = [r.get(label.name) for r in records if label.name in r]
                if label_values:
                    from collections import Counter
                    dist = Counter(label_values)
                    split_metrics[f"label_{label.name}_distribution"] = dict(dist)

            metrics["splits"][split_name.value] = split_metrics

        return metrics


# ============================================================================
# Schema YAML Generation
# ============================================================================

def generate_schema_yaml(
    name: str = "quan_collections",
    output_path: Optional[Union[str, Path]] = None,
) -> str:
    """
    Generate default data schema YAML for QUAN collections.

    Args:
        name: Schema name
        output_path: Optional path to save YAML

    Returns:
        YAML string
    """
    schema = DataSchema(
        name=name,
        version="1.0.0",
        description="QUAN Collections ML Training Data Schema",
        owner="mlops-team",
        entity_key="account_id",
        timestamp_key="snapshot_date",
        min_rows=1000,
        max_null_ratio=0.1,
        features=[
            # Identifiers (PII)
            FeatureSchema(
                name="account_id",
                dtype=FeatureType.CATEGORICAL,
                description="Unique account identifier",
                nullable=False,
            ),
            FeatureSchema(
                name="debtor_name",
                dtype=FeatureType.TEXT,
                description="Consumer name",
                contains_pii=True,
                pii_type=PIIType.NAME,
            ),
            FeatureSchema(
                name="ssn_last4",
                dtype=FeatureType.CATEGORICAL,
                description="Last 4 digits of SSN",
                contains_pii=True,
                pii_type=PIIType.SSN_LAST4,
            ),
            FeatureSchema(
                name="phone",
                dtype=FeatureType.CATEGORICAL,
                description="Primary phone number",
                nullable=True,
                contains_pii=True,
                pii_type=PIIType.PHONE,
            ),
            FeatureSchema(
                name="email",
                dtype=FeatureType.CATEGORICAL,
                description="Email address",
                nullable=True,
                contains_pii=True,
                pii_type=PIIType.EMAIL,
            ),

            # Account features
            FeatureSchema(
                name="balance",
                dtype=FeatureType.NUMERIC,
                description="Current outstanding balance",
                min_value=0.01,
                max_value=100000.0,
                feature_group="account",
            ),
            FeatureSchema(
                name="original_balance",
                dtype=FeatureType.NUMERIC,
                description="Original debt amount",
                min_value=0.01,
                max_value=100000.0,
                feature_group="account",
            ),
            FeatureSchema(
                name="days_overdue",
                dtype=FeatureType.NUMERIC,
                description="Days since payment due",
                min_value=0,
                max_value=3650,
                feature_group="account",
            ),
            FeatureSchema(
                name="account_type",
                dtype=FeatureType.CATEGORICAL,
                description="Type of account",
                allowed_values=["bnpl", "credit_card", "personal_loan", "subscription", "other"],
                feature_group="account",
            ),
            FeatureSchema(
                name="original_creditor",
                dtype=FeatureType.CATEGORICAL,
                description="Original creditor name",
                feature_group="account",
            ),

            # Temporal features
            FeatureSchema(
                name="snapshot_date",
                dtype=FeatureType.DATETIME,
                description="Date of data snapshot",
                nullable=False,
            ),
            FeatureSchema(
                name="charge_off_date",
                dtype=FeatureType.DATETIME,
                description="Date account was charged off",
                nullable=True,
                feature_group="temporal",
            ),
            FeatureSchema(
                name="last_payment_date",
                dtype=FeatureType.DATETIME,
                description="Date of last payment",
                nullable=True,
                feature_group="temporal",
            ),

            # Behavioral features
            FeatureSchema(
                name="contact_attempts_30d",
                dtype=FeatureType.NUMERIC,
                description="Contact attempts in last 30 days",
                min_value=0,
                max_value=100,
                feature_group="behavioral",
            ),
            FeatureSchema(
                name="rpc_count_30d",
                dtype=FeatureType.NUMERIC,
                description="Right party contacts in last 30 days",
                min_value=0,
                max_value=30,
                feature_group="behavioral",
            ),
            FeatureSchema(
                name="payment_count_90d",
                dtype=FeatureType.NUMERIC,
                description="Payments made in last 90 days",
                min_value=0,
                max_value=30,
                feature_group="behavioral",
            ),
            FeatureSchema(
                name="promise_to_pay_count",
                dtype=FeatureType.NUMERIC,
                description="Number of promises to pay",
                min_value=0,
                max_value=50,
                feature_group="behavioral",
            ),

            # Geographic features
            FeatureSchema(
                name="debtor_state",
                dtype=FeatureType.CATEGORICAL,
                description="Consumer state of residence",
                feature_group="geographic",
            ),
            FeatureSchema(
                name="debtor_zip",
                dtype=FeatureType.CATEGORICAL,
                description="Consumer ZIP code (first 3 digits)",
                contains_pii=False,  # First 3 digits only
                feature_group="geographic",
            ),

            # Model scores (if pre-computed)
            FeatureSchema(
                name="risk_score",
                dtype=FeatureType.NUMERIC,
                description="Pre-computed risk score",
                min_value=0.0,
                max_value=1.0,
                nullable=True,
                feature_group="scores",
            ),
        ],
        labels=[
            LabelSchema(
                name="paid_in_full_90d",
                label_type=LabelType.BINARY,
                description="Whether account was paid in full within 90 days",
                classes=["no_payment", "paid_in_full"],
                positive_class="paid_in_full",
                observation_window_days=90,
                definition="Balance reduced to $0 within 90 days of snapshot",
            ),
            LabelSchema(
                name="any_payment_30d",
                label_type=LabelType.BINARY,
                description="Whether any payment was made within 30 days",
                classes=["no_payment", "payment"],
                positive_class="payment",
                observation_window_days=30,
                definition="At least one payment > $0 within 30 days",
            ),
            LabelSchema(
                name="payment_amount_90d",
                label_type=LabelType.REGRESSION,
                description="Total payment amount in 90 days",
                min_value=0.0,
                max_value=100000.0,
                observation_window_days=90,
                definition="Sum of all payments within 90 day window",
            ),
            LabelSchema(
                name="outcome_category",
                label_type=LabelType.MULTICLASS,
                description="Categorical outcome at 90 days",
                classes=[
                    "paid_in_full",
                    "partial_payment",
                    "payment_plan",
                    "promise_to_pay",
                    "no_response",
                    "bankruptcy",
                    "dispute",
                    "cease_desist",
                ],
                observation_window_days=90,
                definition="Primary outcome category at observation window end",
            ),
        ],
    )

    yaml_content = schema.to_yaml()

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(yaml_content)
        logger.info(f"Schema saved to {path}")

    return yaml_content


# ============================================================================
# Reproducible Build Functions
# ============================================================================

def build_canonical_datasets(
    raw_data_path: Union[str, Path],
    output_path: Union[str, Path],
    schema_path: Optional[Union[str, Path]] = None,
    train_end_date: Optional[str] = None,
    val_end_date: Optional[str] = None,
    test_end_date: Optional[str] = None,
    version_name: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Main entry point for building canonical datasets.

    This function produces exact, reproducible train/val/test splits
    with full versioning and lineage tracking.

    Args:
        raw_data_path: Path to raw data (JSONL or directory)
        output_path: Output directory for datasets
        schema_path: Path to schema YAML (None = use default)
        train_end_date: Training period end (YYYY-MM-DD)
        val_end_date: Validation period end (YYYY-MM-DD)
        test_end_date: Test period end (YYYY-MM-DD)
        version_name: Name for versioned output
        config: Additional configuration

    Returns:
        Build result with metrics and paths
    """
    logger.info("Starting canonical dataset build...")

    config = config or {}

    # Load or create schema
    if schema_path and Path(schema_path).exists():
        schema = DataSchema.from_yaml_file(schema_path)
        logger.info(f"Loaded schema from {schema_path}")
    else:
        # Generate default schema
        schema_yaml = generate_schema_yaml()
        schema = DataSchema.from_yaml(schema_yaml)
        logger.info("Using default schema")

    # Load raw data
    raw_path = Path(raw_data_path)
    records = []

    if raw_path.is_file():
        # Single JSONL file
        with open(raw_path, "r") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
    elif raw_path.is_dir():
        # Directory of JSONL files
        for jsonl_file in sorted(raw_path.glob("*.jsonl")):
            with open(jsonl_file, "r") as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))
    else:
        raise ValueError(f"Invalid raw_data_path: {raw_data_path}")

    logger.info(f"Loaded {len(records)} records from {raw_data_path}")

    if not records:
        raise ValueError("No records found in raw data")

    # Parse dates
    default_end = datetime.utcnow()

    if train_end_date:
        train_end = datetime.strptime(train_end_date, "%Y-%m-%d")
    else:
        train_end = default_end - timedelta(days=90)

    if val_end_date:
        val_end = datetime.strptime(val_end_date, "%Y-%m-%d")
    else:
        val_end = default_end - timedelta(days=30)

    if test_end_date:
        test_end = datetime.strptime(test_end_date, "%Y-%m-%d")
    else:
        test_end = None

    # Generate version name if not provided
    if not version_name:
        version_name = f"v{datetime.utcnow().strftime('%Y%m%d')}"

    # Build datasets
    builder = CanonicalDatasetBuilder(
        schema=schema,
        output_path=output_path,
        split_salt=config.get("split_salt", DEFAULT_SPLIT_SALT),
    )

    splits = builder.build(
        records=records,
        train_end=train_end,
        val_end=val_end,
        test_end=test_end,
        use_time_split=config.get("use_time_split", True),
        stratify=config.get("stratify", True),
        redact_pii=config.get("redact_pii", True),
        validate=config.get("validate", True),
        version_name=version_name,
    )

    # Compute metrics
    metrics = builder.get_build_metrics(splits)

    # Save metrics
    metrics_path = Path(output_path) / version_name / "metrics.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    # Save schema used
    schema_output_path = Path(output_path) / version_name / "schema.yaml"
    with open(schema_output_path, "w") as f:
        f.write(schema.to_yaml())

    result = {
        "success": True,
        "version_name": version_name,
        "schema_version": schema.version,
        "metrics": metrics,
        "paths": {
            "output": str(output_path),
            "metrics": str(metrics_path),
            "schema": str(schema_output_path),
            "lineage": str(Path(output_path) / "lineage"),
        },
        "splits": {k.value: len(v) for k, v in splits.items()},
    }

    logger.info(f"Build complete: {result}")

    return result


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """Command-line interface for data contracts module."""
    import argparse

    parser = argparse.ArgumentParser(
        description="QUAN MLOps Data Contracts and Canonical Datasets"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build canonical datasets")
    build_parser.add_argument("--input", "-i", required=True, help="Input data path")
    build_parser.add_argument("--output", "-o", required=True, help="Output path")
    build_parser.add_argument("--schema", "-s", help="Schema YAML path")
    build_parser.add_argument("--train-end", help="Training end date (YYYY-MM-DD)")
    build_parser.add_argument("--val-end", help="Validation end date (YYYY-MM-DD)")
    build_parser.add_argument("--test-end", help="Test end date (YYYY-MM-DD)")
    build_parser.add_argument("--name", "-n", help="Version name")
    build_parser.add_argument("--no-pii-redact", action="store_true", help="Skip PII redaction")
    build_parser.add_argument("--no-stratify", action="store_true", help="Skip stratification")

    # Schema command
    schema_parser = subparsers.add_parser("schema", help="Generate schema YAML")
    schema_parser.add_argument("--output", "-o", required=True, help="Output path")
    schema_parser.add_argument("--name", "-n", default="quan_collections", help="Schema name")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate data against schema")
    validate_parser.add_argument("--input", "-i", required=True, help="Input data path")
    validate_parser.add_argument("--schema", "-s", required=True, help="Schema YAML path")

    # Labels command
    labels_parser = subparsers.add_parser("labels", help="Generate labeling documentation")
    labels_parser.add_argument("--output", "-o", help="Output path (default: stdout)")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if args.command == "build":
        result = build_canonical_datasets(
            raw_data_path=args.input,
            output_path=args.output,
            schema_path=args.schema,
            train_end_date=args.train_end,
            val_end_date=args.val_end,
            test_end_date=args.test_end,
            version_name=args.name,
            config={
                "redact_pii": not args.no_pii_redact,
                "stratify": not args.no_stratify,
            },
        )
        print(json.dumps(result, indent=2))

    elif args.command == "schema":
        yaml_content = generate_schema_yaml(
            name=args.name,
            output_path=args.output,
        )
        print(f"Schema generated at {args.output}")

    elif args.command == "validate":
        schema = DataSchema.from_yaml_file(args.schema)
        enforcer = DataContractEnforcer(schema)

        records = []
        with open(args.input, "r") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))

        result = enforcer.validate_dataset(records)
        print(f"Valid: {result.is_valid}")
        print(f"Errors: {len(result.errors)}")
        for err in result.errors[:20]:
            print(f"  - {err}")
        print(f"Warnings: {len(result.warnings)}")
        for warn in result.warnings[:10]:
            print(f"  - {warn}")

    elif args.command == "labels":
        doc = LabelingRules.generate_documentation()
        if args.output:
            with open(args.output, "w") as f:
                f.write(doc)
            print(f"Documentation saved to {args.output}")
        else:
            print(doc)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
