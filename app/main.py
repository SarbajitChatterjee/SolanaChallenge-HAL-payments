"""AgentBudget API.

    uvicorn app.main:create_app --factory --port 8000
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import httpx
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .api import agent, operator, public, rules as rules_api
from .catalog import load_catalog
from .rules import Rules
from .db import Repository
from .demo import DemoRunner
from .ratelimit import RateLimiter
from .rails import MockRail, PaymentRail, PayKitRail
from .sandbox import autofund
from .schemas import HealthView
from .service import SpendService
from .settings import Settings

VERSION = "1.8.0"
log = logging.getLogger("agentbudget")


class SellerWaker:
    """Free Render services sleep after 15 minutes without traffic. A status check of the API also pings
    the seller services, so opening the web app wakes all of them. At most once every 5 minutes."""

    def __init__(self, bases, every_seconds: float = 300) -> None:
        local = ("localhost", "127.0.0.1")
        self.urls = sorted({b.rstrip("/") + "/health" for b in bases if urlsplit(b).hostname not in local})
        self.every_seconds = every_seconds
        self.last = float("-inf")

    async def ping(self, client: httpx.AsyncClient, url: str) -> None:
        try:
            await client.get(url)
        except httpx.HTTPError as exc:
            log.info("wake-up ping to %s: %s", url, type(exc).__name__)

    async def wake(self) -> None:
        if not self.urls or time.monotonic() - self.last < self.every_seconds:
            return
        self.last = time.monotonic()
        async with httpx.AsyncClient(timeout=60) as client:   # a cold start can take about 30-60 seconds
            await asyncio.gather(*(self.ping(client, url) for url in self.urls))


def build_rail(s: Settings) -> PaymentRail:
    if s.rail == "paykit":
        return PayKitRail(network=s.network, rpc_url=s.rpc_url, wallet_key_for=s.wallet_key_for,
                          wallets_dir=s.wallets_dir)
    return MockRail()


def create_app(settings: Settings | None = None, repo: Repository | None = None,
               rail: PaymentRail | None = None) -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    for noisy in ("httpx", "httpx2", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    s = settings or Settings()
    s.check(tuple(load_catalog(s.catalog_path, s.seller_bases).agents))  # settings problems, before any DB work
    repo = repo or Repository(s.database_url)
    repo.init_schema()
    rules = Rules(repo, s.seller_bases, s.catalog_path)
    rules.seed_if_empty()                       # first start: the starting rules from catalog.json
    repo.seed_agents(rules.catalog().agents)    # a kill-switch row for every agent
    s.check(tuple(rules.catalog().agents))      # agents added on the dashboard need keys too
    rail = rail or build_rail(s)

    async def topup(only: str | None = None) -> None:
        """Test network: give agent wallets their daily budget in test USDC. Best effort, never blocks."""
        if isinstance(rail, PayKitRail) and s.sandbox_autofund:
            agents = rules.catalog().agents
            if only is not None:
                agents = {only: agents[only]} if only in agents else {}
            try:
                await autofund(rail, agents)
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
    app.state.rules = rules
    app.state.repo = repo
    app.state.rail = rail
    app.state.service = SpendService(repo, rail, rules, s.explorer_tx_url, s.seller_review_after)
    app.state.demo = DemoRunner()
    app.state.topup = topup
    app.state.limiter = RateLimiter()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.origins,
        allow_origin_regex=s.allowed_origin_regex,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
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

    app.state.waker = SellerWaker(s.seller_bases.values())

    @app.get("/health", response_model=HealthView, tags=["public"])          # for Render's health check
    @app.get("/v1/status", response_model=HealthView, tags=["public"])       # for the web app (ad blockers block /health)
    async def health(background: BackgroundTasks):
        background.add_task(app.state.waker.wake)                            # runs after the answer is sent
        return HealthView(ok=True, version=VERSION, rail=rail.name, network=getattr(rail, "network", None),
                          database="postgres" if repo.is_postgres else "sqlite",
                          auth_required=not s.public_demo,
                          demo_enabled=s.demo_enabled)

    app.include_router(public.router)
    app.include_router(agent.router)
    app.include_router(operator.router)
    app.include_router(operator.key_router)
    app.include_router(rules_api.router)
    return app