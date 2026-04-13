"""
QUAN Recovery - Terminal CLI

Unified command-line interface for starting, managing, and operating
the QUAN Recovery platform.

Usage:
    quan start          Start the full platform (API + Dashboard)
    quan api            Start the FastAPI backend only
    quan dashboard      Start the Next.js dashboard only
    quan db migrate     Run database migrations
    quan db seed        Seed the database with test data
    quan db reset       Reset and re-seed the database
    quan status         Show platform health and status
    quan test           Run the test suite
    quan lint           Run linters and type checks
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

# Resolve project root (parent of the quan/ package directory)
ROOT_DIR = Path(__file__).resolve().parent.parent

BANNER = r"""
  ____  _   _    _    _   _
 / __ \| | | |  / \  | \ | |
| |  | | | | | / _ \ |  \| |
| |  | | |_| |/ ___ \| |\  |
| |__| |\___//_/   \_\_| \_|
 \___\_\        Recovery v0.1
"""

# ANSI colors for terminal output
class _Colors:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"
    RESET = "\033[0m"

    @classmethod
    def disable(cls) -> None:
        for attr in ("BOLD", "DIM", "GREEN", "YELLOW", "RED", "CYAN", "MAGENTA", "RESET"):
            setattr(cls, attr, "")


C = _Colors

if not sys.stdout.isatty():
    C.disable()


def _print_header(msg: str) -> None:
    print(f"\n{C.CYAN}{C.BOLD}{'=' * 56}{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}  {msg}{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}{'=' * 56}{C.RESET}\n")


def _info(msg: str) -> None:
    print(f"  {C.GREEN}>{C.RESET} {msg}")


def _warn(msg: str) -> None:
    print(f"  {C.YELLOW}!{C.RESET} {msg}")


def _error(msg: str) -> None:
    print(f"  {C.RED}x{C.RESET} {msg}")


def _step(msg: str) -> None:
    print(f"  {C.MAGENTA}~{C.RESET} {C.DIM}{msg}{C.RESET}")


# -------------------------------------------------------------------------
# Environment helpers
# -------------------------------------------------------------------------

def _ensure_env() -> None:
    """Copy .env.example to .env if no .env exists."""
    env_file = ROOT_DIR / ".env"
    example = ROOT_DIR / ".env.example"
    if not env_file.exists() and example.exists():
        _warn(".env not found — copying from .env.example")
        env_file.write_text(example.read_text())


def _check_python_deps() -> bool:
    """Return True if core Python deps are importable."""
    try:
        import fastapi  # noqa: F401
        import sqlalchemy  # noqa: F401
        import uvicorn  # noqa: F401
        return True
    except ImportError:
        return False


def _check_node(dashboard_dir: Path) -> bool:
    """Return True if node_modules exist in the dashboard dir."""
    return (dashboard_dir / "node_modules").is_dir()


def _run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess, inheriting stdio."""
    return subprocess.run(cmd, cwd=cwd or ROOT_DIR, check=check)


# -------------------------------------------------------------------------
# Subcommands
# -------------------------------------------------------------------------

def cmd_start(args: argparse.Namespace) -> int:
    """Start the full platform (API + Dashboard)."""
    _print_header("QUAN Recovery — Full Platform Start")
    _ensure_env()

    if not _check_python_deps():
        _error("Python dependencies missing. Run: pip install -e '.[dev]'")
        return 1

    dashboard_dir = ROOT_DIR / "dashboard"
    if not _check_node(dashboard_dir):
        _warn("Dashboard node_modules not found. Installing...")
        _run(["npm", "install"], cwd=dashboard_dir)

    # Run migrations
    _step("Running database migrations...")
    _run([sys.executable, "-m", "alembic", "upgrade", "head"])

    api_port = args.api_port
    dashboard_port = args.dashboard_port

    _info(f"Starting API server on http://localhost:{api_port}")
    _info(f"Starting Dashboard on http://localhost:{dashboard_port}")
    print()

    procs: list[subprocess.Popen] = []

    def _shutdown(signum=None, frame=None):
        _step("Shutting down...")
        for p in procs:
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                p.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    env = os.environ.copy()
    env.setdefault("ENVIRONMENT", "development")
    env.setdefault("DEBUG", "true")

    # Start API
    api_cmd = [
        sys.executable, "-m", "uvicorn", "quan.main:app",
        "--reload", "--host", "0.0.0.0", "--port", str(api_port),
    ]
    procs.append(subprocess.Popen(api_cmd, cwd=ROOT_DIR, env=env))

    # Start Dashboard
    dash_env = env.copy()
    dash_env["PORT"] = str(dashboard_port)
    procs.append(subprocess.Popen(["npm", "run", "dev"], cwd=dashboard_dir, env=dash_env))

    _info("Platform running. Press Ctrl+C to stop.")
    print()

    # Wait for either process to exit
    while True:
        for p in procs:
            ret = p.poll()
            if ret is not None:
                _warn(f"Process (pid={p.pid}) exited with code {ret}")
                _shutdown()
        time.sleep(1)


def cmd_api(args: argparse.Namespace) -> int:
    """Start the FastAPI backend only."""
    _print_header("QUAN Recovery — API Server")
    _ensure_env()

    if not _check_python_deps():
        _error("Python dependencies missing. Run: pip install -e '.[dev]'")
        return 1

    _step("Running database migrations...")
    _run([sys.executable, "-m", "alembic", "upgrade", "head"])

    port = args.port
    host = args.host
    _info(f"Starting API on http://{host}:{port}")
    _info(f"API docs at http://{host}:{port}/docs")
    print()

    cmd = [
        sys.executable, "-m", "uvicorn", "quan.main:app",
        "--host", host, "--port", str(port),
    ]
    if args.reload:
        cmd.append("--reload")
    if args.workers and args.workers > 1:
        cmd.extend(["--workers", str(args.workers)])

    return _run(cmd, check=False).returncode


def _check_node_runtime() -> tuple[bool, str]:
    """Return (available, version) for Node.js."""
    try:
        result = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
    except Exception:
        pass
    return False, ""


def _check_npm_runtime() -> tuple[bool, str]:
    """Return (available, version) for npm."""
    try:
        result = subprocess.run(
            ["npm", "--version"], capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
    except Exception:
        pass
    return False, ""


def _check_api_reachable(port: int) -> bool:
    """Return True if the API health endpoint responds."""
    try:
        import urllib.request
        urllib.request.urlopen(f"http://localhost:{port}/health", timeout=2)
        return True
    except Exception:
        return False


DASHBOARD_PAGES = [
    ("/",              "Overview",      "KPIs, funnel, alerts, channel performance"),
    ("/executive",     "Executive",     "Revenue trends, gross margin, ROI"),
    ("/operations",    "Operations",    "Pipeline stages, throughput, bottlenecks"),
    ("/compliance",    "Compliance",    "FDCPA/TCPA scores, violations, audit readiness"),
    ("/tokenization",  "Tokenization",  "Pools, tranches, investor metrics"),
    ("/upload",        "Upload",        "CSV portfolio uploader with validation"),
    ("/accounts",      "Accounts",      "Filterable account list with detail views"),
    ("/health",        "System Health", "Module status, uptime, incidents"),
    ("/alerts",        "Alerts",        "Active alerts and recommendations"),
]


def cmd_dashboard(args: argparse.Namespace) -> int:
    """Start the Next.js dashboard frontend."""
    _print_header("QUAN Recovery — Dashboard Frontend")

    dashboard_dir = ROOT_DIR / "dashboard"
    if not dashboard_dir.is_dir():
        _error(f"Dashboard directory not found: {dashboard_dir}")
        return 1

    # ---- Pre-flight checks ----
    _step("Running pre-flight checks...")

    node_ok, node_ver = _check_node_runtime()
    npm_ok, npm_ver = _check_npm_runtime()

    if not node_ok:
        _error("Node.js is not installed. Install Node.js 18+ to continue.")
        return 1
    _info(f"Node.js:       {node_ver}")

    if not npm_ok:
        _error("npm is not installed.")
        return 1
    _info(f"npm:           v{npm_ver}")

    # ---- Install dependencies if needed ----
    if not _check_node(dashboard_dir):
        _warn("node_modules not found. Installing dependencies...")
        ret = _run(["npm", "install"], cwd=dashboard_dir, check=False)
        if ret.returncode != 0:
            _error("npm install failed")
            return 1
        _info("Dependencies installed")
    else:
        _info("Dependencies:  installed")

    port = args.port
    api_port = args.api_port

    # ---- Optionally start the backend API ----
    api_proc = None
    procs: list[subprocess.Popen] = []

    if args.with_api:
        _ensure_env()
        api_running = _check_api_reachable(api_port)
        if api_running:
            _info(f"API server:    already running on port {api_port}")
        else:
            _step(f"Starting API backend on port {api_port}...")

            # Run migrations first
            _run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                check=False,
            )

            api_env = os.environ.copy()
            api_env.setdefault("ENVIRONMENT", "development")
            api_env.setdefault("DEBUG", "true")
            api_cmd = [
                sys.executable, "-m", "uvicorn", "quan.main:app",
                "--reload", "--host", "0.0.0.0", "--port", str(api_port),
            ]
            api_proc = subprocess.Popen(
                api_cmd, cwd=ROOT_DIR, env=api_env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            procs.append(api_proc)

            # Give the API a moment to boot
            for _ in range(10):
                time.sleep(0.5)
                if _check_api_reachable(api_port):
                    break
            if _check_api_reachable(api_port):
                _info(f"API server:    {C.GREEN}started{C.RESET} on port {api_port}")
            else:
                _warn(f"API server:    started on port {api_port} (may still be booting)")
    else:
        api_running = _check_api_reachable(api_port)
        if api_running:
            _info(f"API server:    {C.GREEN}connected{C.RESET} on port {api_port}")
        else:
            _warn(f"API server:    not detected on port {api_port}")
            _warn("Dashboard will show empty-state data. Use --with-api to auto-start it.")

    # ---- Handle lint-only mode early ----
    if args.lint_only:
        print()
        _step("Running Next.js lint...")
        ret = _run(["npm", "run", "lint"], cwd=dashboard_dir, check=False)
        for p in procs:
            p.terminate()
        if ret.returncode == 0:
            _info("Lint: clean")
        else:
            _warn("Lint found issues")
        return ret.returncode

    # ---- Build environment ----
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["NEXT_PUBLIC_API_URL"] = f"http://localhost:{api_port}"
    env.setdefault("API_URL", f"http://localhost:{api_port}")

    # ---- Print startup summary ----
    mode = "production" if args.build else "development"
    print()
    print(f"  {C.BOLD}Mode:{C.RESET}   {mode}")
    print(f"  {C.BOLD}URL:{C.RESET}    {C.CYAN}http://localhost:{port}{C.RESET}")
    print(f"  {C.BOLD}API:{C.RESET}    http://localhost:{api_port}")
    print()

    print(f"  {C.BOLD}Pages:{C.RESET}")
    for path, name, desc in DASHBOARD_PAGES:
        url = f"http://localhost:{port}{path}"
        print(f"    {C.DIM}{name:<16}{C.RESET} {url}")
    print()

    # ---- Start the dashboard ----
    def _shutdown(signum=None, frame=None):
        _step("Shutting down...")
        for p in procs:
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                p.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    if args.build:
        _step("Building production bundle...")
        ret = _run(["npm", "run", "build"], cwd=dashboard_dir, check=False)
        if ret.returncode != 0:
            _error("Build failed")
            _shutdown()
            return 1
        _info("Build complete. Starting production server...")
        print()
        dash_proc = subprocess.Popen(
            ["npm", "run", "start"], cwd=dashboard_dir, env=env,
        )
    else:
        dash_proc = subprocess.Popen(
            ["npm", "run", "dev"], cwd=dashboard_dir, env=env,
        )

    procs.append(dash_proc)

    _info("Dashboard running. Press Ctrl+C to stop.")
    print()

    # Wait for processes
    while True:
        for p in procs:
            ret = p.poll()
            if ret is not None and p is dash_proc:
                _warn(f"Dashboard exited with code {ret}")
                _shutdown()
        time.sleep(1)


def cmd_db(args: argparse.Namespace) -> int:
    """Database management subcommands."""
    action = args.db_action

    if action == "migrate":
        _print_header("QUAN Recovery — Database Migration")
        _ensure_env()
        revision = args.revision if hasattr(args, "revision") else "head"
        _step(f"Running alembic upgrade {revision}...")
        return _run([sys.executable, "-m", "alembic", "upgrade", revision], check=False).returncode

    elif action == "rollback":
        _print_header("QUAN Recovery — Database Rollback")
        _ensure_env()
        steps = args.steps if hasattr(args, "steps") else "1"
        _step(f"Rolling back {steps} revision(s)...")
        return _run(
            [sys.executable, "-m", "alembic", "downgrade", f"-{steps}"],
            check=False,
        ).returncode

    elif action == "seed":
        _print_header("QUAN Recovery — Seed Database")
        _ensure_env()
        count = str(args.count) if hasattr(args, "count") else "1000"
        _step(f"Seeding {count} accounts...")
        cmd = [sys.executable, "scripts/seed_data.py", "--count", count]
        if hasattr(args, "reset") and args.reset:
            cmd.append("--reset")
        return _run(cmd, check=False).returncode

    elif action == "reset":
        _print_header("QUAN Recovery — Reset Database")
        _ensure_env()
        _warn("Resetting database — all data will be replaced with seed data.")
        count = str(args.count) if hasattr(args, "count") else "1000"
        _step("Running migrations...")
        _run([sys.executable, "-m", "alembic", "upgrade", "head"])
        _step(f"Re-seeding with {count} accounts...")
        return _run(
            [sys.executable, "scripts/seed_data.py", "--reset", "--count", count],
            check=False,
        ).returncode

    elif action == "history":
        _print_header("QUAN Recovery — Migration History")
        return _run([sys.executable, "-m", "alembic", "history", "--verbose"], check=False).returncode

    else:
        _error(f"Unknown db action: {action}")
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Show platform health and status."""
    _print_header("QUAN Recovery — Platform Status")

    import json

    # Check .env
    env_exists = (ROOT_DIR / ".env").exists()
    _info(f".env file:        {'found' if env_exists else 'MISSING'}")

    # Check database
    db_path = ROOT_DIR / "quan.db"
    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        _info(f"Database (SQLite): {size_mb:.2f} MB")
    else:
        _warn("Database:          not initialized (run: quan db migrate)")

    # Try to count records
    try:
        from quan.database import SessionLocal, init_database
        from quan.models.database import Account, Portfolio

        init_database()
        with SessionLocal() as db:
            portfolio_count = db.query(Portfolio).count()
            account_count = db.query(Account).count()
            _info(f"Portfolios:        {portfolio_count}")
            _info(f"Accounts:          {account_count}")
    except Exception as e:
        _warn(f"Database query:    unavailable ({e})")

    # Check API server
    try:
        import urllib.request
        port = args.api_port
        resp = urllib.request.urlopen(f"http://localhost:{port}/health", timeout=2)
        data = json.loads(resp.read())
        _info(f"API server:        {C.GREEN}healthy{C.RESET} (port {port})")
    except Exception:
        _warn(f"API server:        not running (port {args.api_port})")

    # Check Dashboard
    try:
        import urllib.request
        port = args.dashboard_port
        urllib.request.urlopen(f"http://localhost:{port}", timeout=2)
        _info(f"Dashboard:         {C.GREEN}running{C.RESET} (port {port})")
    except Exception:
        _warn(f"Dashboard:         not running (port {args.dashboard_port})")

    # Check node_modules
    dashboard_dir = ROOT_DIR / "dashboard"
    node_ok = _check_node(dashboard_dir)
    _info(f"Node modules:      {'installed' if node_ok else 'NOT installed'}")

    # Check Python deps
    py_ok = _check_python_deps()
    _info(f"Python deps:       {'installed' if py_ok else 'NOT installed'}")

    print()
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    """Run the test suite."""
    _print_header("QUAN Recovery — Test Suite")

    cmd = [sys.executable, "-m", "pytest"]

    if args.unit:
        cmd.extend(["tests/unit"])
    elif args.integration:
        cmd.extend(["tests/integration"])

    if args.coverage:
        cmd.extend(["--cov=quan", "--cov-report=term-missing"])

    if args.verbose:
        cmd.append("-v")

    if args.marker:
        cmd.extend(["-m", args.marker])

    if args.parallel:
        cmd.extend(["-n", "auto"])

    if args.keyword:
        cmd.extend(["-k", args.keyword])

    _step(f"Running: {' '.join(cmd)}")
    print()
    return _run(cmd, check=False).returncode


def cmd_lint(args: argparse.Namespace) -> int:
    """Run linters and type checks."""
    _print_header("QUAN Recovery — Code Quality")

    failed = False

    # Ruff
    _step("Running ruff...")
    ret = _run([sys.executable, "-m", "ruff", "check", "quan/"], check=False)
    if ret.returncode != 0:
        _warn("Ruff found issues")
        failed = True
    else:
        _info("Ruff: clean")

    # MyPy
    if not args.skip_mypy:
        _step("Running mypy...")
        ret = _run([sys.executable, "-m", "mypy", "quan/"], check=False)
        if ret.returncode != 0:
            _warn("MyPy found issues")
            failed = True
        else:
            _info("MyPy: clean")

    if args.fix:
        _step("Running ruff --fix...")
        _run([sys.executable, "-m", "ruff", "check", "--fix", "quan/"], check=False)
        _step("Running black...")
        _run([sys.executable, "-m", "black", "quan/"], check=False)
        _info("Auto-fixes applied")

    print()
    return 1 if failed else 0


def cmd_install(args: argparse.Namespace) -> int:
    """Install all dependencies."""
    _print_header("QUAN Recovery — Install Dependencies")

    _step("Installing Python dependencies...")
    ret = _run([sys.executable, "-m", "pip", "install", "-e", ".[dev]"], check=False)
    if ret.returncode != 0:
        _error("Python install failed")
        return 1
    _info("Python dependencies installed")

    dashboard_dir = ROOT_DIR / "dashboard"
    if dashboard_dir.is_dir():
        _step("Installing Node.js dependencies...")
        ret = _run(["npm", "install"], cwd=dashboard_dir, check=False)
        if ret.returncode != 0:
            _error("npm install failed")
            return 1
        _info("Node dependencies installed")

    _step("Running database migrations...")
    _run([sys.executable, "-m", "alembic", "upgrade", "head"], check=False)

    print()
    _info("Installation complete. Run 'quan start' to launch the platform.")
    print()
    return 0


# -------------------------------------------------------------------------
# Argument parser
# -------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quan",
        description="QUAN Recovery — AI-Powered Micro-Debt Collection Platform CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Quick start:
              quan install            Install all dependencies
              quan start              Launch API + Dashboard
              quan db reset           Reset DB with seed data
              quan status             Check platform health
        """),
    )

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # --- start ---
    p_start = sub.add_parser("start", help="Start API + Dashboard together")
    p_start.add_argument("--api-port", type=int, default=8000, help="API port (default: 8000)")
    p_start.add_argument("--dashboard-port", type=int, default=3000, help="Dashboard port (default: 3000)")

    # --- api ---
    p_api = sub.add_parser("api", help="Start the FastAPI backend")
    p_api.add_argument("--port", "-p", type=int, default=8000, help="Port (default: 8000)")
    p_api.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    p_api.add_argument("--reload", action="store_true", default=True, help="Enable auto-reload (default: on)")
    p_api.add_argument("--no-reload", dest="reload", action="store_false", help="Disable auto-reload")
    p_api.add_argument("--workers", "-w", type=int, default=1, help="Number of workers (default: 1)")

    # --- dashboard ---
    p_dash = sub.add_parser(
        "dashboard",
        help="Start the Next.js dashboard frontend",
        description="Start the QUAN Recovery dashboard. Runs pre-flight checks, "
        "optionally boots the API backend, and launches Next.js.",
    )
    p_dash.add_argument("--port", "-p", type=int, default=3000, help="Dashboard port (default: 3000)")
    p_dash.add_argument("--api-port", type=int, default=8000, help="Backend API port (default: 8000)")
    p_dash.add_argument("--with-api", action="store_true", help="Auto-start the backend API server alongside the dashboard")
    p_dash.add_argument("--build", action="store_true", help="Build and serve a production bundle instead of dev mode")
    p_dash.add_argument("--lint-only", action="store_true", help="Run Next.js lint only (no server)")

    # --- db ---
    p_db = sub.add_parser("db", help="Database management")
    db_sub = p_db.add_subparsers(dest="db_action", help="Database commands")

    db_sub.add_parser("migrate", help="Run pending migrations").add_argument(
        "--revision", default="head", help="Target revision (default: head)"
    )

    p_rollback = db_sub.add_parser("rollback", help="Rollback migrations")
    p_rollback.add_argument("--steps", default="1", help="Number of revisions to rollback (default: 1)")

    p_seed = db_sub.add_parser("seed", help="Seed database with test data")
    p_seed.add_argument("--count", "-n", type=int, default=1000, help="Number of accounts (default: 1000)")
    p_seed.add_argument("--reset", action="store_true", help="Delete existing data before seeding")

    p_reset = db_sub.add_parser("reset", help="Reset and re-seed the database")
    p_reset.add_argument("--count", "-n", type=int, default=1000, help="Number of accounts (default: 1000)")

    db_sub.add_parser("history", help="Show migration history")

    # --- status ---
    p_status = sub.add_parser("status", help="Show platform health and status")
    p_status.add_argument("--api-port", type=int, default=8000, help="API port to check (default: 8000)")
    p_status.add_argument("--dashboard-port", type=int, default=3000, help="Dashboard port to check (default: 3000)")

    # --- test ---
    p_test = sub.add_parser("test", help="Run the test suite")
    p_test.add_argument("--unit", action="store_true", help="Run unit tests only")
    p_test.add_argument("--integration", action="store_true", help="Run integration tests only")
    p_test.add_argument("--coverage", "--cov", action="store_true", help="Enable coverage reporting")
    p_test.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    p_test.add_argument("--marker", "-m", help="Run tests matching a pytest marker")
    p_test.add_argument("--parallel", action="store_true", help="Run tests in parallel")
    p_test.add_argument("--keyword", "-k", help="Run tests matching keyword expression")

    # --- lint ---
    p_lint = sub.add_parser("lint", help="Run linters and type checks")
    p_lint.add_argument("--fix", action="store_true", help="Auto-fix issues (ruff --fix + black)")
    p_lint.add_argument("--skip-mypy", action="store_true", help="Skip mypy type checking")

    # --- install ---
    sub.add_parser("install", help="Install all dependencies (Python + Node)")

    return parser


# -------------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        print(BANNER)
        parser.print_help()
        return 0

    dispatch = {
        "start": cmd_start,
        "api": cmd_api,
        "dashboard": cmd_dashboard,
        "db": cmd_db,
        "status": cmd_status,
        "test": cmd_test,
        "lint": cmd_lint,
        "install": cmd_install,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return handler(args)
    except KeyboardInterrupt:
        print()
        _step("Interrupted.")
        return 130
    except subprocess.CalledProcessError as e:
        _error(f"Command failed with exit code {e.returncode}")
        return e.returncode


def _entrypoint() -> None:
    """Wrapper for pyproject.toml [project.scripts] entry point."""
    sys.exit(main())


if __name__ == "__main__":
    _entrypoint()
