"""QUAN Recovery - Main Application Entry Point"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pathlib import Path

from quan.config import settings
from quan.logging_config import configure_logging, get_logger
from quan.ingestion import ingestion_router
from quan.api import dashboard_router, accounts_router, portfolios_router
from quan.monitoring import get_metrics
from quan.database import init_db, close_db, check_db_connection

# Configure logging at module load
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""

    # Startup
    logger.info(f"Starting QUAN Recovery API - {settings.environment}")

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database initialization: {e}")

    # Initialize metrics
    metrics = get_metrics()
    metrics.update_active_campaigns(0)

    # Initialize Kafka producer
    try:
        from quan.ingestion.kafka_producer import KafkaProducerClient
        producer = KafkaProducerClient()
        await producer.connect()
        app.state.kafka_producer = producer
    except Exception as e:
        logger.warning(f"Kafka not available: {e}")

    yield

    # Shutdown
    logger.info("Shutting down QUAN Recovery API")

    # Close database connections
    await close_db()

    if hasattr(app.state, "kafka_producer"):
        await app.state.kafka_producer.disconnect()


app = FastAPI(
    title="QUAN Recovery API",
    description="AI-Powered Micro-Debt Collection Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["https://quanrecovery.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    metrics = get_metrics()

    with metrics.track_api_request(request.url.path, request.method):
        response = await call_next(request)

    return response


# Include routers
app.include_router(ingestion_router, prefix="/api/v1")
app.include_router(dashboard_router)
app.include_router(accounts_router)
app.include_router(portfolios_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "QUAN Recovery",
        "version": "0.1.0",
        "status": "operational",
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/ready")
async def ready():
    """Readiness check endpoint"""
    # Check dependencies
    db_ok = await check_db_connection()

    checks = {
        "database": db_ok,
        "kafka": True,  # Would check Kafka connection
        "redis": True,  # Would check Redis connection
    }

    all_ready = all(checks.values())

    return {
        "ready": all_ready,
        "checks": checks,
    }


@app.get("/api/v1/business-plan/download")
async def download_business_plan():
    """Download the QUAN business plan PDF."""
    pdf_path = Path(__file__).resolve().parents[1] / "QUAN_Business_Plan.pdf"

    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Business plan not found")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name,
    )


# API routes for core functionality
@app.post("/api/v1/analyze")
async def analyze_portfolio(request: Request):
    """Analyze portfolio with collection intelligence"""
    from quan.intelligence import CollectionIntelligence

    body = await request.json()
    accounts = body.get("accounts", [])

    engine = CollectionIntelligence()
    analysis = engine.analyze_portfolio(accounts)
    strategies = [engine.generate_strategy(acc) for acc in accounts]

    return {
        "analyzed": len(accounts),
        "strategies": [
            {
                "account_id": s.account_id,
                "recovery_probability": s.recovery_probability,
                "optimal_channels": s.optimal_channels,
                "settlement_threshold": s.settlement_threshold,
            }
            for s in strategies
        ],
        "expected_rate": analysis.get("expected_rate", 0),
    }


@app.post("/api/v1/campaigns")
async def create_campaign(request: Request):
    """Create collection campaign"""
    from quan.orchestration import CollectionOrchestrator

    body = await request.json()

    orchestrator = CollectionOrchestrator()
    campaign = await orchestrator.process_portfolio(
        portfolio_id=body.get("portfolio_id"),
        accounts=body.get("accounts", []),
        client_id=body.get("client_id"),
    )

    return {
        "campaign_id": campaign.id,
        "status": campaign.stage.value,
        "accounts": len(campaign.accounts),
    }


@app.get("/api/v1/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str):
    """Get campaign status"""
    from quan.orchestration import CollectionOrchestrator

    orchestrator = CollectionOrchestrator()
    status = await orchestrator.get_campaign_status(campaign_id)

    if not status:
        return {"error": "Campaign not found"}

    return status


@app.post("/api/v1/settlements")
async def calculate_settlement(request: Request):
    """Calculate settlement offer"""
    from quan.payments import SettlementEngine
    from decimal import Decimal

    body = await request.json()
    account = body.get("account", {})
    offer = body.get("offer")

    engine = SettlementEngine()
    settlement = await engine.calculate_settlement(
        account,
        Decimal(str(offer)) if offer else None,
    )

    return {
        "account_id": settlement.account_id,
        "original_balance": float(settlement.original_balance),
        "settlement_amount": float(settlement.settlement_amount),
        "savings": float(settlement.savings),
        "discount_percentage": settlement.discount_percentage,
        "valid_until": settlement.valid_until.isoformat(),
        "payment_options": settlement.payment_options,
    }


@app.post("/api/v1/payments")
async def process_payment(request: Request):
    """Process payment"""
    from quan.payments import PaymentProcessor
    from decimal import Decimal

    body = await request.json()

    processor = PaymentProcessor()
    result = await processor.process_payment(
        account=body.get("account", {}),
        payment_method=body.get("payment_method", {}),
        amount=Decimal(str(body.get("amount", 0))),
    )

    return {
        "success": result.success,
        "transaction_id": result.transaction_id,
        "error": result.error,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "quan.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
