"""Manually top up agent wallets on the Surfpool sandbox (the API also does this on startup).

    RAIL=paykit python scripts/fund_sandbox.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.catalog import load_catalog  # noqa: E402
from app.rails import PayKitRail  # noqa: E402
from app.sandbox import autofund  # noqa: E402
from app.settings import Settings  # noqa: E402

s = Settings()
rail = PayKitRail(network=s.network, rpc_url=s.rpc_url, wallet_keys=s.wallet_key_map, wallets_dir=s.wallets_dir)
asyncio.run(autofund(rail, load_catalog(s.catalog_path, s.vendor_base)))
print("Funded:", ", ".join(f"{a} {rail.pubkey(a)}" for a in load_catalog(s.catalog_path, s.vendor_base).agents))
