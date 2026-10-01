"""All configuration comes from environment variables (or a local .env). Nothing secret lives in code."""

from __future__ import annotations

from functools import cached_property
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_pairs(raw: str | None) -> dict[str, str]:
    """'agent-a:value,agent-b:value' -> {'agent-a': 'value', ...}"""
    pairs: dict[str, str] = {}
    for chunk in (raw or "").split(","):
        if ":" in chunk:
            key, value = chunk.split(":", 1)
            pairs[key.strip()] = value.strip()
    return pairs


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["dev", "prod"] = "dev"

    # Storage: SQLite for local dev and tests, Supabase Postgres in production.
    database_url: str = "sqlite:///./agentbudget.db"

    # CORS: exact frontend origins, plus an optional regex for Lovable preview URLs.
    allowed_origins: str = "http://localhost:5173,http://localhost:8080"
    allowed_origin_regex: str | None = None

    # Auth
    operator_token: SecretStr | None = None   # dashboard actions: approve, freeze, export, demo
    public_demo: bool = False                 # open the dashboard actions for judges (sandbox only)
    agent_keys: SecretStr | None = None       # "research-agent:<key>,intern-agent:<key>"

    # Payments
    rail: Literal["mock", "paykit"] = "mock"
    network: Literal["localnet", "devnet"] = "localnet"  # mainnet deliberately not allowed in the MVP
    rpc_url: str = "https://402.surfnet.dev:8899"
    agent_wallet_keys: SecretStr | None = None  # "research-agent:<base58 secret>,..."
    wallets_dir: str = ".wallets"               # local-dev fallback for keys
    sandbox_autofund: bool = True               # top up agent wallets via Surfnet cheatcodes on localnet

    # Catalog and vendors
    catalog_path: str | None = None
    vendor_base: str = "http://127.0.0.1:8001"
    explorer_tx_url: str | None = None          # e.g. "https://explorer.solana.com/tx/{tx}?cluster=devnet"

    demo_enabled: bool = True

    @cached_property
    def origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip()]

    @cached_property
    def agent_key_map(self) -> dict[str, str]:
        return parse_pairs(self.agent_keys.get_secret_value() if self.agent_keys else None)

    @cached_property
    def wallet_key_map(self) -> dict[str, str]:
        return parse_pairs(self.agent_wallet_keys.get_secret_value() if self.agent_wallet_keys else None)

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    def check(self) -> None:
        """Fail fast on unsafe production configs instead of discovering them in a demo."""
        if self.app_env != "prod":
            return
        problems = []
        if not self.public_demo and not self.operator_token:
            problems.append("OPERATOR_TOKEN is required (or set PUBLIC_DEMO=true for a sandbox demo).")
        if not self.agent_key_map:
            problems.append("AGENT_KEYS is required in prod.")
        if "*" in self.origins:
            problems.append("ALLOWED_ORIGINS must list exact origins, not '*'.")
        if not self.is_postgres:
            problems.append("DATABASE_URL must point to Postgres (Supabase) in prod.")
        if problems:
            raise RuntimeError("Unsafe configuration:\n- " + "\n- ".join(problems))
