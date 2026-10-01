"""
- The API only ever talks to Solana's test networks (localnet sandbox or devnet). Mainnet is not
  an option in this code, so no setting can make it move real money.
- The API refuses to start if something is missing or unsafe, and lists every problem in the log.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from functools import cached_property
from typing import Literal

from pydantic import PrivateAttr, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("agentbudget.settings")


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

    # Storage: Supabase Postgres. SQLite only for the automated tests (data is lost on every Render deploy).
    database_url: str = "sqlite:///./agentbudget.db"

    # CORS: exact web app addresses, plus an optional pattern for Lovable preview links.
    allowed_origins: str = "http://localhost:5173,http://localhost:8080"
    allowed_origin_regex: str | None = None

    # Access
    app_secret: SecretStr | None = None       # one random string; agent keys and test wallets derive from it
    operator_token: SecretStr | None = None   # dashboard actions: approve, freeze, export, demo
    public_demo: bool = False                 # open the dashboard actions to anyone (for judging)
    agent_keys: SecretStr | None = None       # optional override: "research-agent:<key>,intern-agent:<key>"

    # Payments (test networks only)
    rail: Literal["mock", "paykit"] = "mock"
    network: Literal["localnet", "devnet"] = "localnet"
    rpc_url: str = "https://402.surfnet.dev:8899"
    agent_wallet_keys: SecretStr | None = None  # optional override: "research-agent:<base58 secret>,..."
    wallets_dir: str = ".wallets"               # optional: key files, used if nothing else is set
    sandbox_autofund: bool = True               # top up agent wallets on the localnet sandbox

    # Catalog and sellers
    catalog_path: str | None = None
    vendor_base: str = "http://127.0.0.1:8001"
    explorer_tx_url: str | None = None          # e.g. "https://explorer.solana.com/tx/{tx}?cluster=devnet"

    demo_enabled: bool = True

    _agent_keys: dict[str, str] | None = PrivateAttr(default=None)
    _wallet_keys: dict[str, str] | None = PrivateAttr(default=None)

    @cached_property
    def origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    # ---- keys: explicit values win, APP_SECRET fills the gaps ---------------------------------------
    def _derive(self, purpose: str, agent_id: str) -> bytes:
        secret = self.app_secret.get_secret_value().encode()
        return hmac.new(secret, f"agentbudget:{purpose}:{agent_id}".encode(), hashlib.sha256).digest()

    def derived_agent_key(self, agent_id: str) -> str:
        return "ab_" + base64.urlsafe_b64encode(self._derive("agent-key", agent_id)).decode().rstrip("=")[:32]

    def derived_wallet_key(self, agent_id: str) -> str:
        from solders.keypair import Keypair  # comes with solana-pay-kit

        return str(Keypair.from_seed(self._derive("wallet", agent_id)))  # base58 secret key

    def resolve_keys(self, agent_ids) -> None:
        agent_keys = parse_pairs(self.agent_keys.get_secret_value() if self.agent_keys else None)
        wallet_keys = parse_pairs(self.agent_wallet_keys.get_secret_value() if self.agent_wallet_keys else None)
        if self.app_secret:
            for agent_id in agent_ids:
                agent_keys.setdefault(agent_id, self.derived_agent_key(agent_id))
                wallet_keys.setdefault(agent_id, self.derived_wallet_key(agent_id))
        self._agent_keys, self._wallet_keys = agent_keys, wallet_keys

    @property
    def agent_key_map(self) -> dict[str, str]:
        if self._agent_keys is None:
            return parse_pairs(self.agent_keys.get_secret_value() if self.agent_keys else None)
        return self._agent_keys

    @property
    def wallet_key_map(self) -> dict[str, str]:
        if self._wallet_keys is None:
            return parse_pairs(self.agent_wallet_keys.get_secret_value() if self.agent_wallet_keys else None)
        return self._wallet_keys

    # ---- startup check -----------------------------------------------------------------------------
    def check(self, agent_ids: list[str] | tuple[str, ...] = ()) -> None:
        """Refuse to start with missing or unsafe settings, listing every problem at once."""
        how = "Set APP_SECRET to any long random string (Render can generate one)."
        problems = []
        if not self.public_demo and not self.operator_token:
            problems.append("Set OPERATOR_TOKEN, or PUBLIC_DEMO=true to open the dashboard for a demo.")
        if missing := [a for a in agent_ids if a not in self.agent_key_map]:
            problems.append(f"No agent key for: {', '.join(missing)}. {how}")
        if self.rail == "paykit":
            if missing := [a for a in agent_ids if a not in self.wallet_key_map]:
                problems.append(f"No wallet for: {', '.join(missing)} (needed when RAIL=paykit). {how}")
            if any(host in self.vendor_base for host in ("127.0.0.1", "localhost")):
                problems.append("VENDOR_BASE still points to this machine. Set it to the sellers' public URL, "
                                "e.g. https://agentbudget-vendors.onrender.com")
        if "*" in self.origins:
            problems.append("ALLOWED_ORIGINS must list exact web addresses, not '*'.")
        if problems:
            raise RuntimeError("Can't start:\n- " + "\n- ".join(problems))
        if not self.is_postgres:
            log.warning("DATABASE_URL is not Postgres: data will be lost on the next deploy. "
                        "Set it to the Supabase session pooler URL.")