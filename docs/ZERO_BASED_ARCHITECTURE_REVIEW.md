# Zero-Based Architecture Review — Quannex

**Date:** 2026-05-30
**Scope:** Business processes and system architecture, reviewed from first
principles, with multi-agent autonomy and debt tokenization as first-class
design goals.
**Status:** Strategic review for decision. Not yet an implementation plan.

---

## 0. Why this review exists, and how to read it

The recent pilot refocus (`docs/CORE_PRODUCT_REFOCUS_PLAN.md`) deliberately
narrowed Quannex to a thin, shippable "collections operating system":
ingest → score → work accounts → record payments → report. It moved the
multi-agent stack, the orchestration engines, and the entire tokenization /
securitization platform out of the runtime path into "experimental" territory
(`experimental/README.md`).

That was the right call **for getting a pilot live**. It is the wrong frame for
answering the question this review asks: *if we started from a blank page and
took the thesis seriously, what is the system?*

"Zero-based" here means we do **not** treat the current pilot scope as the
baseline. We reconstruct the business from its economic objective, then map the
architecture onto the assets that already exist in the tree. The surprising
result of the audit: **most of the target architecture is already written.**
It is approximately 24,000 lines of subsystem code that is currently dark.

| Subsystem (in `quan/`) | Lines | Runtime today | Role in target architecture |
| ---------------------- | -----:| ------------- | --------------------------- |
| `orchestration/`       | 9,070 | dark          | Pipeline + event backbone   |
| `finance/`             | 6,047 | dark          | Tokenization + reconciliation |
| `agents/`              | 4,673 | dark          | Autonomous recovery         |
| `shadow_bureau/`       | 3,719 | dark          | Behavioral data + marketplace |
| `risk/`                | 3,047 | dark          | Portfolio risk + stress     |
| `analytics/`           | 1,483 | **live**      | Dashboards                  |
| `backtest/`            | 1,416 | dark          | Lifecycle simulation        |
| `integration/`         | 1,186 | dark          | EventBus / module connectors |
| `api/`                 |   880 | **live**      | Pilot REST surface          |
| `intelligence/`        |   466 | **live**      | Scoring engine              |

The review's job is to decide which of those lines become product, in what
order, and how they connect.

---

## 1. The business thesis, compressed to one loop

The systemic thesis (`docs/SYSTEMIC_THESIS.md`) argues two things:

1. **Recovery is broken on unit economics.** Human-centric collection costs
   ~$47/account. For sub-$250 micro-debt (BNPL, subscriptions, gig advances,
   overdraft, small medical) that cost exceeds expected recovery, so ~$37B/yr is
   abandoned. Agentic AI collapses marginal cost ~95% and makes the sub-$250
   "dead zone" recoverable.

2. **Lenders holding this paper are illiquid.** Charged-off micro-debt trades
   opaquely for pennies. RWA tokenization (Centrifuge/Tinlake model) turns a
   portfolio into transparent, tranched, tradeable securities and gives the
   originator instant liquidity.

These are usually pitched as two products. They are actually **one machine**:

```
        capital in (investors buy DROP/TIN tranches)
                         │
                         ▼
   ┌──────────────────────────────────────────────┐
   │  acquire micro-debt portfolios with that      │
   │  capital  →  autonomously recover with agents │
   │  →  recovered cash flows through the waterfall │
   │  →  pays tranche yields  →  recycles capital   │
   └──────────────────────────────────────────────┘
                         │
                         ▼
        capital velocity (buy more, recover more)
```

The agents produce the cashflow. The tokenization layer prices, funds, and
distributes that cashflow. **Neither half is complete without the other**, and —
critically — the codebase already contains the seam that joins them:
`RWATokenizationPlatform.run_epoch(pool_id, collections, recoveries)` in
`quan/finance/tokenization.py:2587`. Agent-generated collections are exactly the
`collections` argument. That function is the heart of the machine.

---

## 2. Zero-based business process map

Reconstructed from the objective, independent of current code. Seven processes;
each maps to existing assets.

### P1 — Capital formation
Onboard investors (KYC/AML), accept subscriptions into pools, issue tranche
tokens, manage redemptions and NAV.
**Assets:** `InvestorPortal` (`tokenization.py:1840`), `ComplianceRecord`
(Reg D/A/S), `NAVCalculation`, `RedemptionRequest`.

### P2 — Asset acquisition & ingestion
Acquire/import portfolios; validate; register each debt; snapshot immutable
metadata.
**Assets:** pilot `portfolio_router.upload`, `IngestionPipeline`
(`orchestration/pipeline.py`), `DebtMetadata` (`tokenization.py:184`).

### P3 — Enrichment & scoring
Recovery probability, optimal channels, settlement threshold, behavioral tier.
**Assets:** `CollectionIntelligence` (`intelligence/engine.py`, **live**),
Shadow Bureau `live_ledger.py` (behavioral score, risk tiers A–F).

### P4 — Autonomous recovery (multi-agent)
Plan → draft compliant outreach → verify against FDCPA/TCPA/Reg F → simulate
settlement scenarios → negotiate → collect; with persistent memory and audit.
**Assets:** `QuannexSupervisor` + specialists (`agents/supervisor.py`),
`OutreachSpecialist` (`agents/outreach_specialist.py`), `LLMWrapper`,
`QuannexMemoryManager`, legacy `AgenticController` (voice/negotiation/learning).

### P5 — Servicing, reconciliation & accounting
Match payments, allocate (fees→interest→principal), trust accounting (FDCPA
segregation), settlements, contingency fees, 1099-C flagging, aging reserves,
mark-to-market, impairment.
**Assets:** `reconciliation.py` (6 engines, ~2,962 lines, graded functional).

### P6 — Tokenization & securitization
Mint debt NFTs → pool by asset class → create DROP/TIN tranches → run waterfall
per epoch → secondary-market order book.
**Assets:** `AssetTokenizer`, `PoolManager`, `TrancheManager`,
`LiquidityEngine`, `RWATokenizationPlatform` (`finance/tokenization.py`).

### P7 — Risk, compliance & oversight
Portfolio VaR, stress scenarios, concentration (HHI), circuit breakers,
compliance event ledger, human escalation.
**Assets:** `risk/risk_engine.py`, `compliance/`, `ComplianceMonitor` (kill
switch), pilot `ComplianceEvent` model.

**Finding:** every one of the seven processes has substantial existing code.
The gap is not "build the subsystems." The gap is **integration, a single
source of truth, honest external adapters, and sequencing.**

---

## 3. Target architecture

### 3.1 Layered view

```
┌─────────────────────────────────────────────────────────────────────┐
│ EXPERIENCE   Operator dashboard (live) · Investor portal UI (new)    │
├─────────────────────────────────────────────────────────────────────┤
│ API          FastAPI: portfolios, accounts, dashboard (live)         │
│              + recovery (agent runs), capital, pools, tranches (new)  │
├─────────────────────────────────────────────────────────────────────┤
│ AGENTS       QuannexSupervisor → Planner · Outreach · Verifier ·     │
│              Simulator · Memory   (LLMWrapper, persistent memory)     │
├─────────────────────────────────────────────────────────────────────┤
│ ORCHESTRATION  EventBus · StateMachine · ContactGovernor (Reg F) ·   │
│                RetryEngine · ReEngagement · PipelineMonitor          │
├─────────────────────────────────────────────────────────────────────┤
│ FINANCE      Reconciliation/accounting · Tokenization (NFT→Pool→     │
│              Tranche→Waterfall) · LiquidityEngine · InvestorPortal    │
├─────────────────────────────────────────────────────────────────────┤
│ INTELLIGENCE  CollectionIntelligence · Shadow Bureau · Risk/Stress   │
├─────────────────────────────────────────────────────────────────────┤
│ DATA         Postgres (accounts, payments, compliance, pools,        │
│              tranches, investors, events) · object store · ledger     │
├─────────────────────────────────────────────────────────────────────┤
│ ADAPTERS     LLM (Anthropic/OpenAI) · comms (SMS/email/voice) ·      │
│              payments (Stripe/ACH) · chain (sim today → L2 later)     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 The event backbone is the integration contract

`quan/integration/unified_layer.py` already defines an `EventBus`, 13
`SystemModule`s (including `TOKENIZATION`), and 17 `EventType`s spanning the
full lifecycle (`DEBT_INGESTED` … `PAYMENT_SUCCESS` … `DEBT_TOKENIZED`,
`POOL_CREATED`, `TRANCHE_SOLD`). This is the spine. Every subsystem should
publish/subscribe through it rather than calling peers directly. That is what
lets the agent layer and the finance layer stay decoupled while still forming
the closed loop:

```
PAYMENT_SUCCESS (from recovery)  ──►  finance subscriber accrues to pool
        … at epoch boundary …
run_epoch(pool_id, Σ collections, Σ recoveries)
        ──►  WaterfallDistribution  ──►  YieldDistribution to investors
        ──►  publishes TRANCHE yield + updated NAV  ──►  dashboard/investor UI
```

**Architectural decision #1:** adopt the existing `EventBus` as the single
inter-module contract and forbid new cross-subsystem direct imports. Today the
pilot calls routers→ORM directly; that is fine within a subsystem, but the
agent and finance layers must integrate through events or we recreate the
tangle the refocus just cleaned up.

### 3.3 Agent topology (what runs per account)

`QuannexSupervisor.step()` (`agents/supervisor.py:287`) is the per-account loop:
ML fast-path scoring (no LLM cost) → render memory context → LLM decision →
dispatch to a specialist → log observation + compliance note → persist.

The compliance posture is already correct by construction and must be preserved:
- `OutreachSpecialist` **drafts only, never sends**; enforces Mini-Miranda,
  channel limits, time-of-day, prohibited-phrase post-validation.
- `VerifierSpecialist` is a Constitutional-AI gate that must `approve` before
  anything leaves the system.
- `MemoryManagerSpecialist` compresses context under a token budget so
  long-running accounts stay affordable.

**Architectural decision #2:** the v2 `QuannexSupervisor` is the supported
agent runtime. The ~2,800-line legacy `AgenticController` (voice personas,
negotiation state machine, learning loop, cost tracker) is a **capability
quarry**, not a parallel runtime — port pieces into specialists/services as
needed (e.g., `NegotiationEngine` → a `NegotiatorSpecialist`), don't run both.

### 3.4 Unified data model (the missing keystone)

Today there are two disjoint data worlds: the pilot ORM (`Account`, `Payment`,
`ComplianceEvent`, integer PKs, Postgres) and the finance layer's dataclasses
(`DebtNFT`, `DebtPool`, `TrancheToken`, in-memory). The machine only works if a
single `Account` can become a `DebtMetadata` snapshot, be minted into a
`DebtNFT`, join a `DebtPool`, and have its `Payment`s roll into `run_epoch`.

**Architectural decision #3:** make the canonical Postgres `Account` the system
of record and persist the finance entities as tables keyed back to it:

```
Account (1) ──► DebtNFT (1) ──► DebtPool (N:1) ──► Tranche {DROP,TIN}
   │                                                    │
   └── Payment (N) ──► epoch aggregation ──► Waterfall ─┘──► InvestorPosition
```

`DebtMetadata` already carries the right snapshot fields
(`quan_risk_score`, `shadow_bureau_score`, `recovery_probability`,
`total_payments_made`, `consumer_hash`). The work is persistence + a migration,
not redesign.

---

## 4. Maturity grading of existing assets

Honest read from the audit — what is real vs. what looks real.

| Capability | Grade | Notes |
| ---------- | ----- | ----- |
| Pilot ingest/accounts/payments/dashboard | **Production** | Live, tested (30/30). |
| `CollectionIntelligence` scoring | **Production** | Live, unit-tested. |
| `QuannexSupervisor` + specialists | **Functional** | Complete logic; needs real LLM keys, tests, persistence wiring. |
| `OutreachSpecialist` / `VerifierSpecialist` compliance guards | **Functional** | Strong design; needs adversarial test suite. |
| Tokenization (NFT→pool→tranche→waterfall→NAV) | **Functional** | Math complete; in-memory; needs persistence. |
| Reconciliation/accounting engines | **Functional** | GAAP/FDCPA logic present; needs DB + audit storage. |
| Secondary-market order book | **Functional** | Matching logic present; not wired to settlement. |
| `EventBus` / integration layer | **Functional** | Spine exists; nothing publishes to it yet. |
| Orchestration pipelines (settlement/payment/resolution) | **Skeletal** | Stages defined; execution stubbed/mocked. |
| Comms adapters (Twilio/SendGrid/voice) | **Skeletal** | Lazy clients, no tests, no real send path. |
| `BlockchainSimulator` / on-chain | **Simulated** | Mock gas/tx; no real network. Acceptable for v1. |
| Risk VaR / stress | **Partial** | Scenarios + method names; light implementations. |

**Implication:** the dominant risk is *over-trusting "functional"*. The
financial math being written down is not the same as it being correct under
audit, or correct against persisted state. Everything graded Functional needs a
test harness and a persistence layer before it can carry real money or real
consumer contact.

---

## 5. Gap analysis — what actually has to be built

1. **One source of truth.** Persist finance entities (NFT/pool/tranche/
   investor/waterfall) in Postgres, keyed to `Account`. (P6/keystone)
2. **Wire the EventBus.** Make recovery publish `PAYMENT_SUCCESS`/contact events
   and finance subscribe; replace direct calls at subsystem boundaries.
3. **Real adapters behind interfaces.** LLM (have wrapper), comms send-path,
   payments (Stripe/ACH), KYC. Each as a swappable provider with a sandbox mode.
4. **Compliance as a hard runtime gate, not a draft note.** The `Verifier` →
   `ComplianceMonitor` kill-switch must sit on the actual send path, with an
   immutable compliance ledger and human-escalation queue.
5. **Investor surface.** API + UI for subscribe/redeem/NAV/yield; the operator
   dashboard already proves the pattern.
6. **Epoch scheduler.** A job that aggregates collections per pool and calls
   `run_epoch`, emits distributions, updates NAV.
7. **Test + audit harness** for everything financial and everything that
   contacts a consumer. This is the gating dependency for the whole thing.

Note what is **not** on this list: building the tokenization math, the waterfall,
the agent loop, the scoring engine, or the event taxonomy. Those exist.

---

## 6. Reconciliation with the pilot — phasing, not contradiction

The pilot is not discarded; it becomes **Phase 0 / the recovery substrate** of
the machine. The same `Account`/`Payment` tables feed the tokenization layer.
Sequencing that respects regulatory and capital reality:

- **Phase 0 — Pilot (today).** Manual/assisted recovery, honest dashboards.
  *Proves recovery rates on real paper.* ✅ shipped.

- **Phase 1 — Autonomous recovery (agents on).** Wire `QuannexSupervisor`
  behind the accounts API as "suggested next action," then supervised auto-send
  through the Verifier gate. Publish events to the bus.
  *Proves the cost-collapse thesis.* Gating: compliance test harness, comms
  adapter, LLM keys.

- **Phase 2 — Internal accounting & risk.** Turn on reconciliation, trust
  accounting, aging/reserves, portfolio risk. No external capital yet.
  *Proves we can account for the cash the agents produce.*

- **Phase 3 — Tokenization (private).** Persist NFT/pool/tranche; run epochs
  against internal capital; investor portal in private beta with the
  `BlockchainSimulator` as the ledger. *Proves the waterfall on real cashflows.*

- **Phase 4 — Liquidity & secondary market.** Real KYC, real funds, order book,
  and only then evaluate moving the simulated ledger to an actual L2.
  *Closes the capital-velocity loop.*

Each phase is independently valuable and independently shippable. Regulatory and
trust risk rises monotonically across phases, which is exactly why this order is
non-negotiable: **never expose investor capital before the recovery economics
and the accounting are proven on live data.**

---

## 7. Top risks

- **Regulatory (severe).** Autonomous consumer contact (FDCPA/TCPA/Reg F,
  50-state licensing) and issuing tranche securities (Reg D/A/S, KYC/AML) are
  both heavily regulated. The architecture's compliance-by-design posture
  (`Verifier` gate, kill-switch, immutable ledger) is correct but must be
  treated as load-bearing, with counsel sign-off per phase.
- **Model risk (high).** LLM hallucination on the send path; scoring/valuation
  models driving real pricing. Mitigation: deterministic guardrails in front of
  probabilistic models (already the design), plus backtesting (`backtest/`)
  before any model output prices a tranche or contacts a person.
- **"Functional ≠ correct" (high).** ~16k lines graded Functional carry money
  and compliance logic with thin/no tests. The test+audit harness is the
  critical path, not a follow-up.
- **Scope gravity (medium).** This is the failure mode the refocus fixed.
  Mitigation: the phase gates above; nothing leaves "experimental" without
  persistence + tests + an adapter.

---

## 8. Decisions requested

1. **Adopt the closed-loop machine as the product vision** (recovery + tokenization
   as one system), with the pilot as Phase 0 — yes/no.
2. **Approve the three architectural decisions:** EventBus as the integration
   contract; `QuannexSupervisor` (v2) as the sole agent runtime; canonical
   Postgres `Account` as the single source of truth with persisted finance
   entities.
3. **Authorize Phase 1** (autonomous recovery behind the Verifier gate) as the
   next build, gated on the compliance test harness — yes/no.
4. **Confirm Phase 3 tokenization runs on the `BlockchainSimulator` ledger**
   until Phase 4, deferring any real-chain decision.

If approved, the immediate next deliverable is a Phase 1 implementation plan:
persist + event-wire the supervisor, stand up the comms adapter behind the
Verifier gate, and build the compliance/adversarial test harness — converting
the largest block of already-written, currently-dark code into product.

---

## Appendix — primary source files

- Agents: `quan/agents/supervisor.py`, `outreach_specialist.py`, `memory.py`,
  `llm_wrapper.py`, `agentic_controller.py`
- Orchestration: `quan/orchestration/{pipeline,master_engine,master_orchestrator,workflow,re_engagement}.py`
- Finance: `quan/finance/tokenization.py` (`RWATokenizationPlatform.run_epoch`,
  `tokenize_portfolio`), `quan/finance/reconciliation.py`
- Integration: `quan/integration/unified_layer.py` (`EventBus`, `EventType`)
- Intelligence/data: `quan/intelligence/engine.py`, `quan/shadow_bureau/`,
  `quan/risk/risk_engine.py`
- Thesis: `docs/SYSTEMIC_THESIS.md`; pilot scope: `docs/CORE_PRODUCT_REFOCUS_PLAN.md`
