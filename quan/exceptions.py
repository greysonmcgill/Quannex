"""
QUAN Recovery - Custom Exception Hierarchy

This module defines all custom exceptions used throughout the QUAN platform.
Use specific exceptions instead of generic Exception to enable proper error handling.

Usage:
    from quan.exceptions import PaymentProcessingError, ComplianceViolationError

    try:
        process_payment(...)
    except PaymentProcessingError as e:
        logger.error(f"Payment failed: {e}")
        # Handle payment-specific recovery
"""

from typing import Any, Dict, Optional


# =============================================================================
# BASE EXCEPTION
# =============================================================================

class QuanException(Exception):
    """
    Base exception for all QUAN-specific errors.

    All custom exceptions should inherit from this class to enable
    catching all QUAN errors with a single except clause.

    Attributes:
        message: Human-readable error message
        code: Machine-readable error code for API responses
        details: Additional context about the error
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


# =============================================================================
# VALIDATION EXCEPTIONS
# =============================================================================

class ValidationError(QuanException):
    """Base class for validation errors"""
    pass


class DataValidationError(ValidationError):
    """Invalid data format or content"""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if field:
            details["field"] = field
        if value is not None:
            details["invalid_value"] = str(value)[:100]  # Truncate for safety
        super().__init__(message, details=details, **kwargs)


class SchemaValidationError(ValidationError):
    """Data does not conform to expected schema"""
    pass


class AccountNotFoundError(ValidationError):
    """Requested account does not exist"""

    def __init__(self, account_id: str, **kwargs):
        super().__init__(
            f"Account not found: {account_id}",
            details={"account_id": account_id},
            **kwargs
        )


# =============================================================================
# PAYMENT EXCEPTIONS
# =============================================================================

class PaymentException(QuanException):
    """Base class for payment-related errors"""
    pass


class PaymentProcessingError(PaymentException):
    """Error during payment processing"""

    def __init__(
        self,
        message: str,
        transaction_id: Optional[str] = None,
        processor: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if transaction_id:
            details["transaction_id"] = transaction_id
        if processor:
            details["processor"] = processor
        super().__init__(message, details=details, **kwargs)


class PaymentDeclinedError(PaymentException):
    """Payment was declined by processor or bank"""

    def __init__(
        self,
        message: str,
        decline_code: Optional[str] = None,
        decline_reason: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if decline_code:
            details["decline_code"] = decline_code
        if decline_reason:
            details["decline_reason"] = decline_reason
        super().__init__(message, code="PAYMENT_DECLINED", details=details, **kwargs)


class InsufficientFundsError(PaymentException):
    """Payment failed due to insufficient funds"""
    pass


class RefundError(PaymentException):
    """Error processing a refund"""
    pass


class PaymentTimeoutError(PaymentException):
    """Payment processing timed out"""
    pass


class InvalidPaymentMethodError(PaymentException):
    """Payment method is invalid or expired"""
    pass


# =============================================================================
# COMPLIANCE EXCEPTIONS
# =============================================================================

class ComplianceException(QuanException):
    """Base class for compliance-related errors"""
    pass


class ComplianceViolationError(ComplianceException):
    """Action would violate compliance rules"""

    def __init__(
        self,
        message: str,
        violation_type: Optional[str] = None,
        regulation: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if violation_type:
            details["violation_type"] = violation_type
        if regulation:
            details["regulation"] = regulation
        super().__init__(message, code="COMPLIANCE_VIOLATION", details=details, **kwargs)


class FDCPAViolationError(ComplianceViolationError):
    """Fair Debt Collection Practices Act violation"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, regulation="FDCPA", **kwargs)


class TCPAViolationError(ComplianceViolationError):
    """Telephone Consumer Protection Act violation"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, regulation="TCPA", **kwargs)


class RegFViolationError(ComplianceViolationError):
    """Regulation F violation"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, regulation="REG_F", **kwargs)


class StateComplianceError(ComplianceViolationError):
    """State-specific compliance violation"""

    def __init__(self, message: str, state: str, **kwargs):
        details = kwargs.pop("details", {})
        details["state"] = state
        super().__init__(message, regulation=f"STATE_LAW_{state}", details=details, **kwargs)


class ContactFrequencyError(ComplianceViolationError):
    """Contact frequency limit exceeded"""

    def __init__(
        self,
        message: str,
        current_count: int,
        limit: int,
        period: str = "7 days",
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "current_count": current_count,
            "limit": limit,
            "period": period,
        })
        super().__init__(message, violation_type="contact_frequency", details=details, **kwargs)


class ConsentRequiredError(ComplianceViolationError):
    """Required consent not obtained"""

    def __init__(self, message: str, consent_type: str, **kwargs):
        details = kwargs.pop("details", {})
        details["consent_type"] = consent_type
        super().__init__(message, violation_type="consent", details=details, **kwargs)


class CeaseAndDesistError(ComplianceException):
    """Consumer has requested cease and desist"""

    def __init__(self, account_id: str, **kwargs):
        super().__init__(
            f"Cease and desist active for account: {account_id}",
            code="CEASE_DESIST",
            details={"account_id": account_id},
            **kwargs
        )


class BankruptcyStayError(ComplianceException):
    """Account is under bankruptcy protection"""

    def __init__(self, account_id: str, case_number: Optional[str] = None, **kwargs):
        details = {"account_id": account_id}
        if case_number:
            details["case_number"] = case_number
        super().__init__(
            f"Bankruptcy stay active for account: {account_id}",
            code="BANKRUPTCY_STAY",
            details=details,
            **kwargs
        )


# =============================================================================
# ORCHESTRATION EXCEPTIONS
# =============================================================================

class OrchestrationException(QuanException):
    """Base class for orchestration/workflow errors"""
    pass


class StateTransitionError(OrchestrationException):
    """Invalid state transition attempted"""

    def __init__(
        self,
        message: str,
        current_state: str,
        target_state: str,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "current_state": current_state,
            "target_state": target_state,
        })
        super().__init__(message, details=details, **kwargs)


class PipelineError(OrchestrationException):
    """Error in pipeline processing"""

    def __init__(
        self,
        message: str,
        stage: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if stage:
            details["stage"] = stage
        super().__init__(message, details=details, **kwargs)


class WorkflowTimeoutError(OrchestrationException):
    """Workflow execution timed out"""
    pass


class ConcurrencyError(OrchestrationException):
    """Concurrent operation conflict"""
    pass


# =============================================================================
# RECONCILIATION EXCEPTIONS
# =============================================================================

class ReconciliationException(QuanException):
    """Base class for reconciliation errors"""
    pass


class MatchingError(ReconciliationException):
    """Unable to match transactions"""
    pass


class BalanceDiscrepancyError(ReconciliationException):
    """Balance mismatch detected"""

    def __init__(
        self,
        message: str,
        expected: float,
        actual: float,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details.update({
            "expected": expected,
            "actual": actual,
            "discrepancy": actual - expected,
        })
        super().__init__(message, details=details, **kwargs)


class AuditError(ReconciliationException):
    """Audit trail integrity error"""
    pass


# =============================================================================
# COMMUNICATION EXCEPTIONS
# =============================================================================

class CommunicationException(QuanException):
    """Base class for communication errors"""
    pass


class MessageDeliveryError(CommunicationException):
    """Failed to deliver message"""

    def __init__(
        self,
        message: str,
        channel: Optional[str] = None,
        provider_error: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if channel:
            details["channel"] = channel
        if provider_error:
            details["provider_error"] = provider_error
        super().__init__(message, details=details, **kwargs)


class ChannelUnavailableError(CommunicationException):
    """Communication channel is unavailable"""
    pass


# =============================================================================
# INTELLIGENCE/ML EXCEPTIONS
# =============================================================================

class IntelligenceException(QuanException):
    """Base class for ML/Intelligence errors"""
    pass


class ModelInferenceError(IntelligenceException):
    """Error during model inference"""

    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        model_version: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        if model_name:
            details["model_name"] = model_name
        if model_version:
            details["model_version"] = model_version
        super().__init__(message, details=details, **kwargs)


class FeatureExtractionError(IntelligenceException):
    """Error extracting features for model input"""
    pass


class ModelNotFoundError(IntelligenceException):
    """Requested model not found in registry"""
    pass


# =============================================================================
# CONFIGURATION EXCEPTIONS
# =============================================================================

class ConfigurationError(QuanException):
    """Configuration-related errors"""
    pass


class MissingConfigurationError(ConfigurationError):
    """Required configuration is missing"""

    def __init__(self, key: str, **kwargs):
        super().__init__(
            f"Missing required configuration: {key}",
            details={"key": key},
            **kwargs
        )


class InvalidConfigurationError(ConfigurationError):
    """Configuration value is invalid"""
    pass


# =============================================================================
# INTEGRATION EXCEPTIONS
# =============================================================================

class IntegrationException(QuanException):
    """Base class for external integration errors"""
    pass


class ExternalServiceError(IntegrationException):
    """Error communicating with external service"""

    def __init__(
        self,
        message: str,
        service: str,
        status_code: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details["service"] = service
        if status_code:
            details["status_code"] = status_code
        super().__init__(message, details=details, **kwargs)


class RateLimitError(IntegrationException):
    """Rate limit exceeded for external service"""

    def __init__(
        self,
        service: str,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.pop("details", {})
        details["service"] = service
        if retry_after:
            details["retry_after_seconds"] = retry_after
        super().__init__(
            f"Rate limit exceeded for {service}",
            code="RATE_LIMIT",
            details=details,
            **kwargs
        )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Base
    "QuanException",
    # Validation
    "ValidationError",
    "DataValidationError",
    "SchemaValidationError",
    "AccountNotFoundError",
    # Payment
    "PaymentException",
    "PaymentProcessingError",
    "PaymentDeclinedError",
    "InsufficientFundsError",
    "RefundError",
    "PaymentTimeoutError",
    "InvalidPaymentMethodError",
    # Compliance
    "ComplianceException",
    "ComplianceViolationError",
    "FDCPAViolationError",
    "TCPAViolationError",
    "RegFViolationError",
    "StateComplianceError",
    "ContactFrequencyError",
    "ConsentRequiredError",
    "CeaseAndDesistError",
    "BankruptcyStayError",
    # Orchestration
    "OrchestrationException",
    "StateTransitionError",
    "PipelineError",
    "WorkflowTimeoutError",
    "ConcurrencyError",
    # Reconciliation
    "ReconciliationException",
    "MatchingError",
    "BalanceDiscrepancyError",
    "AuditError",
    # Communication
    "CommunicationException",
    "MessageDeliveryError",
    "ChannelUnavailableError",
    # Intelligence
    "IntelligenceException",
    "ModelInferenceError",
    "FeatureExtractionError",
    "ModelNotFoundError",
    # Configuration
    "ConfigurationError",
    "MissingConfigurationError",
    "InvalidConfigurationError",
    # Integration
    "IntegrationException",
    "ExternalServiceError",
    "RateLimitError",
]
