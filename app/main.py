"""AgentBudget API.

    uvicorn app.main:create_app --factory --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .api import agent, operator, public
from .catalog import load_catalog
from .db import Repository
from .demo import DemoRunner
from .ratelimit import RateLimiter
from .rails import MockRail, PaymentRail, PayKitRail
from .sandbox import autofund
from .schemas import HealthView
from .service import SpendService
from .settings import Settings

VERSION = "0.3.0"
log = logging.getLogger("agentbudget")


def build_rail(s: Settings) -> PaymentRail:
    if s.rail == "paykit":
        return PayKitRail(network=s.network, rpc_url=s.rpc_url, wallet_keys=s.wallet_key_map,
                          wallets_dir=s.wallets_dir)
    return MockRail()


def create_app(settings: Settings | None = None, repo: Repository | None = None,
               rail: PaymentRail | None = None) -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    for noisy in ("httpx", "httpx2", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    s = settings or Settings()
    s.check()
    catalog = load_catalog(s.catalog_path, s.vendor_base)
    repo = repo or Repository(s.database_url)
    repo.init_schema()
    repo.seed_agents(catalog.agents)
    rail = rail or build_rail(s)

    async def topup() -> None:
        """Best-effort sandbox top-up; never blocks startup or the demo."""
        if isinstance(rail, PayKitRail) and s.sandbox_autofund:
            try:
                await autofund(rail, catalog)
            except Exception as exc:  # noqa: BLE001
                log.warning("sandbox top-up skipped: %s", exc)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await topup()
        log.info("AgentBudget %s up: rail=%s network=%s db=%s", VERSION, rail.name,
                 getattr(rail, "network", None), "postgres" if repo.is_postgres else "sqlite")
        yield
        repo.engine.dispose()

    app = FastAPI(title="AgentBudget API", version=VERSION, lifespan=lifespan,
                  description="AgentBudget lets AI agents buy data per call in USDC on Solana, within rules a "
                              "person sets: approved sellers, agreed prices, budgets, approval limits and a "
                              "kill switch.")
    app.state.settings = s
    app.state.catalog = catalog
    app.state.repo = repo
    app.state.rail = rail
    app.state.service = SpendService(repo, rail, catalog, s.explorer_tx_url)
    app.state.demo = DemoRunner()
    app.state.topup = topup
    app.state.limiter = RateLimiter()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.origins,
        allow_origin_regex=s.allowed_origin_regex,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Content-Disposition"],
        max_age=600,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.get("/health", response_model=HealthView, tags=["public"])
    async def health():
        return HealthView(ok=True, version=VERSION, rail=rail.name, network=getattr(rail, "network", None),
                          database="postgres" if repo.is_postgres else "sqlite",
                          auth_required=not s.public_demo and (s.operator_token is not None or s.app_env == "prod"),
                          demo_enabled=s.demo_enabled)

    app.include_router(public.router)
    app.include_router(agent.router)
    app.include_router(operator.router)
    return app
