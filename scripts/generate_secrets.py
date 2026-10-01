"""Print every secret the API needs, ready to paste into Render's environment settings.

    python scripts/generate_secrets.py

Agent wallet keys are throwaway sandbox/devnet keys. Never reuse them on mainnet, never commit them.
"""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solana_pay_kit import Signer  # noqa: E402
from solders.keypair import Keypair  # noqa: E402

from app.catalog import load_catalog  # noqa: E402

agents = list(load_catalog(None, "http://unused").agents)
wallets, keys = [], []
print("# Public wallet addresses (safe to share):")
for agent_id in agents:
    signer = Signer.generate()
    wallets.append(f"{agent_id}:{Keypair.from_bytes(signer.secret_key())}")
    keys.append(f"{agent_id}:ab_{secrets.token_urlsafe(24)}")
    print(f"#   {agent_id:16} {signer.pubkey()}")
print("\n# Paste into Render -> agentbudget-api -> Environment (secret values):")
print(f"OPERATOR_TOKEN=op_{secrets.token_urlsafe(24)}")
print(f"AGENT_KEYS={','.join(keys)}")
print(f"AGENT_WALLET_KEYS={','.join(wallets)}")
