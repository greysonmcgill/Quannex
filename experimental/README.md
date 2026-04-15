# experimental/

Research artifacts and tooling that are **not part of the pilot collections OS**.
Everything in this directory is explicitly out of the default runtime path.
The FastAPI app, dashboard, migrations, seed script, and tests do not import
from here.

Nothing in this directory needs to run for the product to work. It is kept so
that prior work is preserved and can be revived if it becomes relevant to a
real pilot need.

## What's here

- `api_gateway_legacy.py` — the ~2,700-line alternate FastAPI definition that
  lived at `quan/api/gateway.py`. It bundled auth, Shadow Bureau, tokenization,
  debt lifecycle, and report endpoints that the pilot product does not need.
  It was never wired into the runtime. Kept for reference only.

- `scripts/` — large-scale simulation scripts, business plan / thesis PDF
  generators, and one-off agentic test harnesses:
  - `run_advanced_calibration.py`, `run_bnpl_1m_simulation.py`,
    `run_calibration.py`, `run_collections_test.py`, `run_full_scale.py`,
    `run_lifecycle_backtest.py`, `run_perpetual_simulation.py`, `run_sub1k.py`
  - `test_agentic.py`, `test_quannex_agent.py`
  - `build_business_plan.py`, `generate_business_plan.py`,
    `generate_thesis_pdf.py`

- `business_plan_generator/`, `mlflow-artifacts/`, `model-registry/`,
  `output/` — outputs and artifacts from prior research runs.

- `QUAN_Systemic_Thesis.pdf`, `PERFORMANCE_REVIEW.md` — longform writing
  and internal performance review notes.

## What still lives inside `quan/` but is **not** on the product path

Several Python modules under `quan/` are not imported by `quan.main`, the
routers, the analytics layer, or the seed script. They are not required for a
pilot deployment. They are kept in-tree for now to avoid disruptive import
path changes, but are out of the runtime surface and should be treated as
experimental until explicitly revived:

- `quan/shadow_bureau/`
- `quan/quantum/`
- `quan/finance/`
- `quan/simulation/`
- `quan/backtest/`
- `quan/semantic/`
- `quan/mlops/`
- `quan/agents/`
- `quan/orchestration/`
- `quan/optimization/`
- `quan/integration/`
- `quan/reporting/`
- `quan/risk/`

If any of these are wired back into the default application, update
`docs/CORE_PRODUCT_REFOCUS_PLAN.md` and `docs/REFOCUS_CHANGELOG.md` to
reflect the new scope.
