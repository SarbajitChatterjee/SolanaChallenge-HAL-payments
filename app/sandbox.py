"""Top up agent wallets on the Surfpool sandbox (localnet) with Surfnet cheatcodes.

Each agent wallet is set to exactly its daily cap in USDC: the on-chain hard cap.
Only ever runs against a sandbox RPC; devnet wallets are funded from the public faucets.
"""

from __future__ import annotations

import logging

import httpx

from .catalog import Catalog
from .rails import PayKitRail

log = logging.getLogger("agentbudget.sandbox")
SYSTEM_PROGRAM = "11111111111111111111111111111111"


def is_sandbox(rpc_url: str) -> bool:
    return any(h in rpc_url for h in ("surfnet", "localhost", "127.0.0.1"))


async def autofund(rail: PayKitRail, catalog: Catalog) -> None:
    if rail.network != "localnet" or not is_sandbox(rail.rpc_url):
        return
    from solana_pay_kit._paycore import mints

    usdc = mints.resolve("USDC", "localnet")
    token_program = mints.token_program_for("USDC", "localnet")
    async with httpx.AsyncClient(timeout=20) as http:
        for agent_id, policy in catalog.agents.items():
            pubkey = rail.pubkey(agent_id)
            calls = [
                ("surfnet_setAccount", [pubkey, {"lamports": 50_000_000, "data": "", "executable": False,
                                                 "owner": SYSTEM_PROGRAM, "rentEpoch": 0}]),
                ("surfnet_setTokenAccount", [pubkey, usdc, {"amount": int(policy.daily_cap * 10**6),
                                                            "state": "initialized"}, token_program]),
            ]
            for method, params in calls:
                reply = (await http.post(rail.rpc_url, json={"jsonrpc": "2.0", "id": 1, "method": method,
                                                             "params": params})).json()
                if "error" in reply:
                    raise RuntimeError(f"{method} for {agent_id} failed: {reply['error']}")
            log.info("funded %s (%s) with %s USDC on the sandbox", agent_id, pubkey, policy.daily_cap)
