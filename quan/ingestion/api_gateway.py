"""Multi-source data ingestion with validation"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import asyncio
from datetime import datetime
import uuid

from quan.config import settings
from .validators import BNPLValidator, BankValidator, SubscriptionValidator
from .kafka_producer import KafkaProducerClient


router = APIRouter(prefix="/ingest", tags=["ingestion"])


class AccountInput(BaseModel):
    """Input schema for account data"""

    account_id: str
    balance: float = Field(gt=0)
    original_creditor: str
    debtor_name: str
    debtor_email: Optional[str] = None
    debtor_phone: Optional[str] = None
    debtor_address: Optional[Dict[str, str]] = None
    days_overdue: int = Field(ge=0)
    original_amount: float = Field(gt=0)
    charge_off_date: Optional[datetime] = None
    last_payment_date: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class PortfolioInput(BaseModel):
    """Input schema for portfolio ingestion"""

    accounts: List[AccountInput]
    source_type: str = Field(pattern="^(bnpl|bank|subscription)$")
    client_id: str


class IngestionResponse(BaseModel):
    """Response from ingestion endpoint"""

    received: int
    validated: int
    processing_id: str
    errors: List[Dict[str, Any]] = []


class QuanIngestion:
    """Multi-source data ingestion with validation"""

    def __init__(self):
        self.kafka_producer = KafkaProducerClient()
        self.validators = {
            "bnpl": BNPLValidator(),
            "bank": BankValidator(),
            "subscription": SubscriptionValidator(),
        }
        self._enrichment_services = self._init_enrichment_services()

    def _init_enrichment_services(self) -> Dict[str, Any]:
        """Initialize connections to enrichment data sources"""
        return {
            "credit": CreditDataService(),
            "contact": ContactInfoService(),
            "employment": EmploymentDataService(),
            "social": SocialSignalsService(),
            "banking": BankingSignalsService(),
        }

    async def ingest_portfolio(
        self,
        portfolio: List[Dict],
        source_type: str,
        client_id: str,
    ) -> IngestionResponse:
        """Ingest and validate portfolio data"""

        batch_id = self._generate_batch_id()
        validated_accounts = []
        errors = []

        for account in portfolio:
            # Schema validation
            if not self.validators[source_type].validate(account):
                errors.append({
                    "account_id": account.get("account_id"),
                    "error": "Schema validation failed",
                })
                continue

            # Enrichment
            account = await self.enrich_account(account)

            # Compliance screening
            if await self.compliance_screen(account):
                validated_accounts.append(account)

                # Stream to Kafka for real-time processing
                await self.kafka_producer.send(
                    topic="quan.accounts.new",
                    value=account,
                    key=account["account_id"],
                )
            else:
                errors.append({
                    "account_id": account["account_id"],
                    "error": "Failed compliance screening",
                })

        # Batch store to data lake
        await self.store_to_lake(validated_accounts, client_id, batch_id)

        return IngestionResponse(
            received=len(portfolio),
            validated=len(validated_accounts),
            processing_id=batch_id,
            errors=errors,
        )

    async def enrich_account(self, account: Dict) -> Dict:
        """Real-time enrichment from multiple sources"""

        enrichment_tasks = [
            self._get_credit_data(account),
            self._get_contact_info(account),
            self._get_employment_data(account),
            self._get_social_signals(account),
            self._get_banking_signals(account),
        ]

        results = await asyncio.gather(*enrichment_tasks, return_exceptions=True)

        for result in results:
            if not isinstance(result, Exception):
                account.update(result)

        account["enriched_at"] = datetime.utcnow().isoformat()
        return account

    async def compliance_screen(self, account: Dict) -> bool:
        """Screen account for compliance issues"""

        # Check for bankruptcy
        if account.get("bankruptcy_status"):
            return False

        # Check for deceased status
        if account.get("deceased_indicator"):
            return False

        # Check for active military (SCRA protection)
        if account.get("active_military"):
            return False

        # Check for cease and desist
        if account.get("cease_desist_received"):
            return False

        # Check statute of limitations
        if self._is_past_sol(account):
            return False

        return True

    def _is_past_sol(self, account: Dict) -> bool:
        """Check if debt is past statute of limitations"""
        state = account.get("debtor_state", "")
        charge_off_date = account.get("charge_off_date")

        if not charge_off_date:
            return False

        # State-specific SOL (simplified)
        sol_years = {
            "CA": 4, "NY": 6, "TX": 4, "FL": 5,
            "IL": 5, "PA": 4, "OH": 6, "GA": 6,
        }

        years = sol_years.get(state, 6)
        sol_date = charge_off_date + timedelta(days=years * 365)

        return datetime.utcnow() > sol_date

    async def _get_credit_data(self, account: Dict) -> Dict:
        """Fetch credit bureau data"""
        try:
            return await self._enrichment_services["credit"].fetch(
                ssn_last4=account.get("ssn_last4"),
                name=account.get("debtor_name"),
                address=account.get("debtor_address"),
            )
        except Exception:
            return {}

    async def _get_contact_info(self, account: Dict) -> Dict:
        """Fetch updated contact information"""
        try:
            return await self._enrichment_services["contact"].fetch(
                name=account.get("debtor_name"),
                address=account.get("debtor_address"),
            )
        except Exception:
            return {}

    async def _get_employment_data(self, account: Dict) -> Dict:
        """Fetch employment data"""
        try:
            return await self._enrichment_services["employment"].fetch(
                name=account.get("debtor_name"),
                ssn_last4=account.get("ssn_last4"),
            )
        except Exception:
            return {}

    async def _get_social_signals(self, account: Dict) -> Dict:
        """Fetch social media signals"""
        try:
            return await self._enrichment_services["social"].fetch(
                email=account.get("debtor_email"),
                phone=account.get("debtor_phone"),
            )
        except Exception:
            return {}

    async def _get_banking_signals(self, account: Dict) -> Dict:
        """Fetch banking/financial signals"""
        try:
            return await self._enrichment_services["banking"].fetch(
                account_id=account.get("account_id"),
            )
        except Exception:
            return {}

    async def store_to_lake(
        self,
        accounts: List[Dict],
        client_id: str,
        batch_id: str,
    ) -> None:
        """Store validated accounts to data lake"""
        # Implementation would write to GCS/S3
        pass

    def _generate_batch_id(self) -> str:
        """Generate unique batch identifier"""
        return f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


# Placeholder enrichment services
class CreditDataService:
    async def fetch(self, **kwargs) -> Dict:
        return {}


class ContactInfoService:
    async def fetch(self, **kwargs) -> Dict:
        return {}


class EmploymentDataService:
    async def fetch(self, **kwargs) -> Dict:
        return {}


class SocialSignalsService:
    async def fetch(self, **kwargs) -> Dict:
        return {}


class BankingSignalsService:
    async def fetch(self, **kwargs) -> Dict:
        return {}


# Initialize singleton
_ingestion_instance: Optional[QuanIngestion] = None


def get_ingestion() -> QuanIngestion:
    global _ingestion_instance
    if _ingestion_instance is None:
        _ingestion_instance = QuanIngestion()
    return _ingestion_instance


@router.post("/portfolio", response_model=IngestionResponse)
async def ingest_portfolio(
    portfolio: PortfolioInput,
    background_tasks: BackgroundTasks,
    ingestion: QuanIngestion = Depends(get_ingestion),
):
    """Ingest a portfolio of accounts for processing"""

    result = await ingestion.ingest_portfolio(
        portfolio=[acc.model_dump() for acc in portfolio.accounts],
        source_type=portfolio.source_type,
        client_id=portfolio.client_id,
    )

    return result


@router.get("/status/{batch_id}")
async def get_ingestion_status(batch_id: str):
    """Get status of a batch ingestion"""
    # Would query processing status from database
    return {"batch_id": batch_id, "status": "processing"}
