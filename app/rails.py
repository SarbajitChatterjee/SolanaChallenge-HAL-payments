"""Payment rails. The gateway decides *whether* to pay; a rail does the paying.

- PayKitRail: real Solana payments through solana-pay-kit (x402 / MPP). The agent's
  key lives here, never in the agent. Every client is built per call with:
    * an origin allowlist of exactly one vendor origin, and
    * a per-payment cap equal to the pinned catalog price,
  so a vendor that quotes more than the contract price never gets a signature.
- MockRail: no chain, no keys. For tests and for demoing without network access.
"""

from __future__ import annotations

import base64
import json
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol
from urllib.parse import urlsplit

import httpx


class RailError(Exception):
    """Payment or vendor call failed. Budget reserved for the call is released."""


class PriceRejected(RailError):
    """The vendor asked for more than the pinned price, so nothing was signed."""


@dataclass
class RailResult:
    status_code: int
    data: Any
    tx: str | None


class PaymentRail(Protocol):
    name: str
    network: str | None

    async def pay_and_fetch(self, *, agent_id: str, url: str, max_price: Decimal,
                            params: dict[str, Any]) -> RailResult: ...

    async def balance(self, agent_id: str) -> Decimal | None: ...


def _body(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return resp.text[:4000]


def settlement_signature(headers: httpx.Headers | dict[str, str]) -> str | None:
    """Pull the on-chain signature out of x402 / MPP receipt headers."""
    sig = headers.get("x-payment-settlement-signature")
    if sig:
        return sig
    for name in ("payment-response", "x-payment-response", "payment-receipt"):
        raw = headers.get(name)
        if not raw:
            continue
        candidates = [raw]
        try:
            candidates.append(base64.b64decode(raw + "=" * (-len(raw) % 4)).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            pass
        for text in candidates:
            try:
                obj = json.loads(text)
            except ValueError:
                continue
            if isinstance(obj, dict):
                for key in ("transaction", "signature", "settledSignature", "txHash", "reference"):
                    if obj.get(key):
                        return str(obj[key])
        return raw[:120]
    return None


class MockRail:
    """Calls vendors without paying (run vendors with PAYWALL=off). Fakes a receipt.

    Honours the vendor's x-demo-price header so price pinning is demoable offline.
    """

    name = "mock"
    network = None

    def __init__(self, fetch: Callable[[str, dict], Awaitable[tuple[Any, Decimal | None]]] | None = None):
        self._fetch = fetch  # tests inject this to avoid HTTP

    async def pay_and_fetch(self, *, agent_id: str, url: str, max_price: Decimal,
                            params: dict[str, Any]) -> RailResult:
        if self._fetch:
            data, quoted = await self._fetch(url, params)
        else:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(url, params=params)
            if resp.status_code == 402:
                raise RailError("Vendor demanded payment. Run vendors with PAYWALL=off in mock mode, "
                                "or set RAIL=paykit.")
            if resp.status_code >= 400:
                raise RailError(f"Vendor error {resp.status_code}: {resp.text[:200]}")
            data = _body(resp)
            quoted = Decimal(resp.headers["x-demo-price"]) if "x-demo-price" in resp.headers else None
        if quoted is not None and quoted > max_price:
            raise PriceRejected(f"Vendor quoted {quoted} USD, pinned price is {max_price} USD. Nothing signed.")
        return RailResult(200, data, f"mock-{uuid.uuid4().hex[:16]}")

    async def balance(self, agent_id: str) -> Decimal | None:
        return None

    def pubkey(self, agent_id: str) -> str | None:
        return None


class PayKitRail:
    name = "paykit"

    def __init__(self, *, network: str, rpc_url: str, wallet_keys: dict[str, str] | None = None,
                 wallets_dir: str | Path = ".wallets") -> None:
        from solana_pay_kit._paycore.rpc import SolanaRpc  # imported lazily: mock mode needs no SDK

        self.network = network          # "localnet" (Surfpool sandbox) or "devnet"
        self.rpc_url = rpc_url
        self.wallet_keys = wallet_keys or {}
        self.wallets_dir = Path(wallets_dir)
        self._rpc = SolanaRpc(rpc_url)
        self._balances: dict[str, tuple[float, Decimal | None]] = {}

    def signer(self, agent_id: str):
        """Keys come from AGENT_WALLET_KEYS (a Render secret); .wallets/<agent>.json is the local fallback."""
        from solana_pay_kit import Signer

        if agent_id in self.wallet_keys:
            return Signer.base58(self.wallet_keys[agent_id])
        path = self.wallets_dir / f"{agent_id}.json"
        if path.exists():
            return Signer.file(str(path))
        raise RailError(f"No wallet key for {agent_id}. Run: python scripts/new_wallets.py")

    def pubkey(self, agent_id: str) -> str:
        return str(self.signer(agent_id).pubkey())

    async def pay_and_fetch(self, *, agent_id: str, url: str, max_price: Decimal,
                            params: dict[str, Any]) -> RailResult:
        from solana_pay_kit.client import ClientPermissions, PayKitClient, PermissionDeniedError, usd

        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        permissions = (
            ClientPermissions.builder()
            .allow_origin(origin)                         # only this vendor
            .only_network(self.network)
            .max_amount_per_payment(usd(str(max_price)))  # price pinning, enforced at signing
            .build()
        )
        client = (
            PayKitClient.builder()
            .signer(self.signer(agent_id))
            .rpc(self._rpc)
            .network(self.network)
            .permissions(permissions)
            .httpx_options(timeout=60.0)  # free-tier vendors can take a while to wake up
            .build()
        )
        try:
            async with client:
                resp = await client.get(url, params=params)
        except PermissionDeniedError as exc:
            raise PriceRejected(f"Vendor quote rejected at signing (pinned {max_price} USD): {exc}") from exc
        if resp.status_code == 402:
            raise RailError("Payment was not completed (vendor still answers 402).")
        if resp.status_code >= 400:
            raise RailError(f"Vendor error {resp.status_code}: {resp.text[:200]}")
        self._balances.pop(agent_id, None)  # balance changed; refresh on next read
        return RailResult(resp.status_code, _body(resp), settlement_signature(resp.headers))

    async def balance(self, agent_id: str) -> Decimal | None:
        """USDC in the agent wallet: the on-chain hard cap. Cached for 5 s for dashboard polling."""
        cached = self._balances.get(agent_id)
        if cached and time.monotonic() - cached[0] < 5:
            return cached[1]
        value: Decimal | None = None
        try:
            from solana_pay_kit._paycore import mints

            label = self.network
            mint = mints.resolve("USDC", label)
            ata = mints.derive_ata(self.pubkey(agent_id), mint, mints.token_program_for("USDC", label))
            async with httpx.AsyncClient(timeout=5) as http:
                r = await http.post(self.rpc_url, json={"jsonrpc": "2.0", "id": 1,
                                                        "method": "getTokenAccountBalance", "params": [ata]})
            ui = r.json().get("result", {}).get("value", {}).get("uiAmountString")
            value = Decimal(ui) if ui is not None else Decimal("0")
        except Exception:  # balance is display-only; never break the dashboard over it
            value = None
        self._balances[agent_id] = (time.monotonic(), value)
        return value
