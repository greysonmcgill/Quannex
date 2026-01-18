"""Schema validators for different account source types"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import re


class BaseAccountSchema(BaseModel):
    """Base schema for all account types"""

    account_id: str
    balance: float = Field(gt=0, le=100000)
    original_creditor: str
    debtor_name: str
    days_overdue: int = Field(ge=0)

    @field_validator("account_id")
    @classmethod
    def validate_account_id(cls, v: str) -> str:
        if not v or len(v) < 3:
            raise ValueError("Account ID must be at least 3 characters")
        return v.strip()

    @field_validator("debtor_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v.strip()


class BNPLAccountSchema(BaseAccountSchema):
    """Schema for Buy Now Pay Later accounts"""

    provider: str = Field(pattern="^(klarna|affirm|afterpay|sezzle|zip|other)$")
    installment_count: int = Field(ge=1, le=24)
    installments_paid: int = Field(ge=0)
    merchant_name: str
    purchase_date: datetime
    purchase_category: Optional[str] = None

    @field_validator("installments_paid")
    @classmethod
    def validate_installments(cls, v: int, info) -> int:
        if "installment_count" in info.data and v > info.data["installment_count"]:
            raise ValueError("Installments paid cannot exceed total installments")
        return v


class BankAccountSchema(BaseAccountSchema):
    """Schema for bank/credit card accounts"""

    account_type: str = Field(pattern="^(credit_card|overdraft|personal_loan|line_of_credit)$")
    credit_limit: Optional[float] = None
    apr: Optional[float] = Field(default=None, ge=0, le=50)
    last_payment_amount: Optional[float] = None
    last_payment_date: Optional[datetime] = None
    charge_off_date: datetime
    charge_off_reason: Optional[str] = None


class SubscriptionAccountSchema(BaseAccountSchema):
    """Schema for subscription/recurring service accounts"""

    service_type: str = Field(
        pattern="^(streaming|telecom|utilities|gym|software|other)$"
    )
    monthly_amount: float = Field(gt=0)
    subscription_start: datetime
    subscription_end: Optional[datetime] = None
    cancellation_date: Optional[datetime] = None
    service_provider: str


class BaseValidator(ABC):
    """Abstract base validator"""

    @abstractmethod
    def validate(self, account: Dict) -> bool:
        """Validate account data"""
        pass

    @abstractmethod
    def get_errors(self) -> List[str]:
        """Get validation errors"""
        pass


class BNPLValidator(BaseValidator):
    """Validator for BNPL account data"""

    def __init__(self):
        self._errors: List[str] = []

    def validate(self, account: Dict) -> bool:
        """Validate BNPL account against schema"""
        self._errors = []

        try:
            BNPLAccountSchema(**account)
            return True
        except Exception as e:
            self._errors.append(str(e))
            return False

    def get_errors(self) -> List[str]:
        return self._errors


class BankValidator(BaseValidator):
    """Validator for bank account data"""

    def __init__(self):
        self._errors: List[str] = []

    def validate(self, account: Dict) -> bool:
        """Validate bank account against schema"""
        self._errors = []

        try:
            BankAccountSchema(**account)

            # Additional bank-specific validations
            if account.get("account_type") == "credit_card":
                if not account.get("credit_limit"):
                    self._errors.append("Credit cards require credit_limit")
                    return False

            return True
        except Exception as e:
            self._errors.append(str(e))
            return False

    def get_errors(self) -> List[str]:
        return self._errors


class SubscriptionValidator(BaseValidator):
    """Validator for subscription account data"""

    def __init__(self):
        self._errors: List[str] = []

    def validate(self, account: Dict) -> bool:
        """Validate subscription account against schema"""
        self._errors = []

        try:
            SubscriptionAccountSchema(**account)

            # Calculate expected balance
            if account.get("monthly_amount") and account.get("days_overdue"):
                months_overdue = account["days_overdue"] // 30
                expected_min = account["monthly_amount"] * max(1, months_overdue - 1)
                expected_max = account["monthly_amount"] * (months_overdue + 2)

                if not (expected_min <= account["balance"] <= expected_max):
                    self._errors.append(
                        f"Balance {account['balance']} seems inconsistent with "
                        f"{months_overdue} months overdue at {account['monthly_amount']}/month"
                    )
                    # Warning only, don't fail validation

            return True
        except Exception as e:
            self._errors.append(str(e))
            return False

    def get_errors(self) -> List[str]:
        return self._errors


class PhoneValidator:
    """Validate and normalize phone numbers"""

    PHONE_REGEX = re.compile(r"^\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}$")

    @classmethod
    def validate(cls, phone: str) -> bool:
        """Check if phone number is valid"""
        if not phone:
            return False
        return bool(cls.PHONE_REGEX.match(phone.strip()))

    @classmethod
    def normalize(cls, phone: str) -> Optional[str]:
        """Normalize phone to E.164 format"""
        if not phone:
            return None

        # Remove all non-digits
        digits = re.sub(r"\D", "", phone)

        # Add country code if missing
        if len(digits) == 10:
            digits = "1" + digits

        if len(digits) != 11 or not digits.startswith("1"):
            return None

        return f"+{digits}"


class EmailValidator:
    """Validate email addresses"""

    EMAIL_REGEX = re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    )

    @classmethod
    def validate(cls, email: str) -> bool:
        """Check if email is valid"""
        if not email:
            return False
        return bool(cls.EMAIL_REGEX.match(email.strip().lower()))

    @classmethod
    def normalize(cls, email: str) -> Optional[str]:
        """Normalize email to lowercase"""
        if not email or not cls.validate(email):
            return None
        return email.strip().lower()


class AddressValidator:
    """Validate and standardize addresses"""

    US_STATES = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
        "DC", "PR", "VI", "GU",
    }

    ZIP_REGEX = re.compile(r"^\d{5}(-\d{4})?$")

    @classmethod
    def validate(cls, address: Dict) -> bool:
        """Validate address components"""
        if not address:
            return False

        # Check required fields
        required = ["street", "city", "state", "zip"]
        if not all(address.get(f) for f in required):
            return False

        # Validate state
        state = address.get("state", "").upper()
        if state not in cls.US_STATES:
            return False

        # Validate ZIP
        zip_code = address.get("zip", "")
        if not cls.ZIP_REGEX.match(zip_code):
            return False

        return True
