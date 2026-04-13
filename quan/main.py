"""QUAN Recovery - Main Application Entry Point"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pathlib import Path

from pydantic import BaseModel, Field

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


# ---------------------------------------------------------------------------
# Hierarchical Agent System — /api/v1/agent/*
# ---------------------------------------------------------------------------


class AgentStepRequest(BaseModel):
    """Request body for a single supervisor step."""

    account: dict = Field(
        ..., description="Account data dict (must include account_id)."
    )
    goal: str = Field(
        default="maximize recovery while maintaining compliance",
        description="Natural-language goal for this step.",
    )
    session_id: str | None = Field(
        default=None,
        description="Optional session ID to resume an existing agent session.",
    )


class AgentStepResponse(BaseModel):
    """Response from one supervisor step."""

    session_id: str
    step: int
    action: str
    reasoning: str
    payload: dict
    next_steps: list[str]
    token_estimate: int
    budget_pct: float


@app.post("/api/v1/agent/step", response_model=AgentStepResponse)
async def agent_step(req: AgentStepRequest):
    """
    Execute one reasoning step of the hierarchical agent system.

    The supervisor will:
    1. Run ML scoring (CollectionIntelligence) as a fast reflex.
    2. Build context from memory.
    3. Call the LLM for a routing decision.
    4. Delegate to the appropriate specialist.
    5. Return structured JSON with the result.

    Call this endpoint repeatedly to advance through the collection
    workflow for a single account.
    """
    from quan.agents.memory import QuannexMemoryManager
    from quan.agents.llm_wrapper import LLMWrapper
    from quan.agents.supervisor import QuannexSupervisor
    from quan.agents.outreach_specialist import OutreachSpecialist

    # Resolve persistence path (one file per session)
    session_id = req.session_id or ""
    persist_name = f"quan_agent_memory_{session_id}.json" if session_id else "quan_agent_memory.json"

    memory = QuannexMemoryManager(persist_path=persist_name)

    # Try to restore a previous session
    if session_id:
        memory.load()
        if memory.state.session_id and memory.state.session_id != session_id:
            # Mismatch — start fresh
            memory = QuannexMemoryManager(persist_path=persist_name)

    llm = LLMWrapper()
    supervisor = QuannexSupervisor(llm=llm, memory=memory)

    # Register the outreach specialist
    supervisor.register_specialist("outreach", OutreachSpecialist())

    # Execute one step
    result = await supervisor.step(account=req.account, goal=req.goal)

    return AgentStepResponse(
        session_id=memory.state.session_id,
        step=memory.state.step_count,
        action=result.action,
        reasoning=result.reasoning,
        payload=result.payload,
        next_steps=result.next_steps,
        token_estimate=result.token_estimate,
        budget_pct=round(memory.budget_pct(), 4),
    )


@app.get("/api/v1/agent/state/{session_id}")
async def agent_state(session_id: str):
    """Retrieve the current agent state for a session (debug / audit)."""
    from quan.agents.memory import QuannexMemoryManager

    memory = QuannexMemoryManager(
        persist_path=f"quan_agent_memory_{session_id}.json"
    )
    if not memory.load():
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": memory.state.session_id,
        "account_id": memory.state.account_id,
        "step_count": memory.state.step_count,
        "summary": memory.state.summary,
        "ml_cache": memory.state.ml_cache.model_dump(),
        "observations": [o.model_dump() for o in memory.state.observations],
        "compliance_notes": [c.model_dump() for c in memory.state.compliance_notes],
        "current_plan": memory.state.current_plan,
        "budget_pct": round(memory.budget_pct(), 4),
        "total_tokens_used": memory.state.total_tokens_used,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "quan.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
