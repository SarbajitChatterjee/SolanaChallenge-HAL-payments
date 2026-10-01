"""OPTIONAL. Normally not needed: Render generates APP_SECRET and the API derives every agent's key
and test wallet from it.

Use this only to set keys by hand (AGENT_KEYS / AGENT_WALLET_KEYS override the derived ones):

    pip install solders
    python scripts/generate_secrets.py

Every run creates NEW keys. Keep the output private and never commit it.
The wallet keys are throwaway keys for Solana's test networks.
"""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from solders.keypair import Keypair
except ImportError:
    sys.exit("Missing package. Run:  pip install solders")

from app.catalog import load_catalog  # noqa: E402  (plain Python, no heavy dependencies)

agents = list(load_catalog(None, "http://unused").agents)
wallets, keys = [], []
print("# Public wallet addresses (safe to share):")
for agent_id in agents:
    keypair = Keypair()
    wallets.append(f"{agent_id}:{keypair}")          # base58 of the 64-byte secret key
    keys.append(f"{agent_id}:ab_{secrets.token_urlsafe(24)}")
    print(f"#   {agent_id:16} {keypair.pubkey()}")
print("\n# Optional overrides for Render -> agentbudget-api -> Environment:")
print(f"OPERATOR_TOKEN=op_{secrets.token_urlsafe(24)}")
print(f"AGENT_KEYS={','.join(keys)}")
print(f"AGENT_WALLET_KEYS={','.join(wallets)}")