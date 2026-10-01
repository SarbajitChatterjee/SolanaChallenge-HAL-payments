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
    items: dict[str, CatalogItem]
    agents: dict[str, AgentPolicy]


def load_catalog(path: str | None, vendor_base: str) -> Catalog:
    raw = json.loads(Path(path or DEFAULT_PATH).read_text("utf-8"))
    base = vendor_base.rstrip("/")
    items = {
        c["tool"]: CatalogItem(tool=c["tool"], url=c["url"].replace("{vendor_base}", base),
                               price=Decimal(c["price"]), vendor=c["vendor"], name=c.get("name", ""),
                               description=c.get("description", ""))
        for c in raw["catalog"]
    }
    agents = {
        a["agent_id"]: AgentPolicy(agent_id=a["agent_id"], allowed_tools=frozenset(a["allowed_tools"]),
                                   per_task_cap=Decimal(a["per_task_cap"]), daily_cap=Decimal(a["daily_cap"]),
                                   approval_above=Decimal(a["approval_above"]),
                                   description=a.get("description", ""))
        for a in raw["agents"]
    }
    unknown = {t for a in agents.values() for t in a.allowed_tools} - items.keys()
    if unknown:
        raise ValueError(f"Agents reference tools missing from the catalog: {sorted(unknown)}")
    return Catalog(items, agents)