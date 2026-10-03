# Vendor catalog and agent policies 

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from .policy import AgentPolicy, CatalogItem

DEFAULT_PATH = Path(__file__).with_name("catalog.json")


@dataclass(frozen=True)
class Catalog:
    items: dict[str, CatalogItem]     # active items only
    agents: dict[str, AgentPolicy]    # active agents only


def read_seed(path: str | None = None) -> dict:
    """The starting rules, as plain rows: {"agents": [...], "items": [...]} with decimal strings."""
    raw = json.loads(Path(path or DEFAULT_PATH).read_text("utf-8"))
    return {"agents": raw["agents"], "items": raw["catalog"]}


def to_catalog(agent_rows: list[dict], item_rows: list[dict], vendor_base: str) -> Catalog:
    base = vendor_base.rstrip("/")
    items = {
        r["tool"]: CatalogItem(tool=r["tool"], url=r["url"].replace("{vendor_base}", base),
                               price=Decimal(str(r["price"])), vendor=r["vendor"], name=r.get("name") or "",
                               description=r.get("description") or "")
        for r in item_rows if r.get("active", True)
    }
    agents = {
        r["agent_id"]: AgentPolicy(agent_id=r["agent_id"], allowed_tools=frozenset(r["allowed_tools"]),
                                   per_task_cap=Decimal(str(r["per_task_cap"])), daily_cap=Decimal(str(r["daily_cap"])),
                                   approval_above=Decimal(str(r["approval_above"])),
                                   description=r.get("description") or "",
                                   max_repeats=int(r.get("max_repeats", 2)),
                                   repeat_window_minutes=int(r.get("repeat_window_minutes", 60)),
                                   max_attempts_per_min=int(r.get("max_attempts_per_min", 30)),
                                   velocity_share_10m=float(r.get("velocity_share_10m", 0.2)))
        for r in agent_rows if r.get("active", True)
    }
    return Catalog(items, agents)


def load_catalog(path: str | None, vendor_base: str) -> Catalog:
    """The starting rules as a Catalog (used by scripts and tests)."""
    seed = read_seed(path)
    return to_catalog(seed["agents"], seed["items"], vendor_base)