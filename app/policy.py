"""Spend rules. Pure functions, no I/O: this is AgentBudget's core.

Checks run in this order, cheapest and most absolute first:
  1. kill switch         -> deny
  2. approved list       -> deny  (unknown seller, or item this agent may not buy)
  3. budgets             -> deny  (per task and per day, money already reserved included)
  4. approval limit      -> hold  (a person decides)
Whatever passes is allowed.

Every verdict carries a stable `code` for software and a plain `message` for people.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from urllib.parse import urlsplit


class Decision(str, Enum):
    ALLOW = "allow"
    HOLD = "hold"
    DENY = "deny"


class Reason(str, Enum):
    OK = "ok"
    FROZEN = "frozen"
    NOT_IN_CATALOG = "not_in_catalog"
    NOT_ALLOWED = "not_allowed"
    TASK_BUDGET = "task_budget"
    DAILY_BUDGET = "daily_budget"
    NEEDS_APPROVAL = "needs_approval"


@dataclass(frozen=True)
class CatalogItem:
    tool: str
    url: str
    price: Decimal          # agreed price in USD; payments above it are never signed
    vendor: str
    name: str = ""          # human name, e.g. "Company record"
    description: str = ""


@dataclass(frozen=True)
class AgentPolicy:
    agent_id: str
    allowed_tools: frozenset[str]
    per_task_cap: Decimal
    daily_cap: Decimal
    approval_above: Decimal
    description: str = ""


@dataclass(frozen=True)
class SpendRequest:
    agent_id: str
    task_id: str
    tool: str | None = None  # catalog id, e.g. "company_lookup"
    url: str | None = None   # raw URL, e.g. one an injected prompt told the agent to buy


@dataclass(frozen=True)
class Verdict:
    decision: Decision
    code: Reason
    message: str
    item: CatalogItem | None = None


def usd(value: Decimal) -> str:
    return f"{value:.2f}"


def _normalize(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}".rstrip("/").lower()


def resolve(req: SpendRequest, catalog: dict[str, CatalogItem]) -> CatalogItem | None:
    """Map a request to an approved item. Raw URLs must match an approved URL exactly."""
    if req.tool:
        return catalog.get(req.tool)
    if req.url:
        target = _normalize(req.url)
        return next((i for i in catalog.values() if _normalize(i.url) == target), None)
    return None


def evaluate(
    req: SpendRequest,
    *,
    policy: AgentPolicy,
    catalog: dict[str, CatalogItem],
    spent_task: Decimal,
    spent_today: Decimal,
    frozen: bool,
    approved: bool = False,
) -> Verdict:
    if frozen:
        return Verdict(Decision.DENY, Reason.FROZEN, "This agent is stopped. Someone flipped the kill switch.")

    item = resolve(req, catalog)
    if item is None:
        return Verdict(Decision.DENY, Reason.NOT_IN_CATALOG,
                       "This seller isn't on the approved list, so nothing was paid.")

    label = item.name or item.tool
    if item.tool not in policy.allowed_tools:
        return Verdict(Decision.DENY, Reason.NOT_ALLOWED,
                       f"{policy.agent_id} isn't allowed to buy {label}.", item)

    if spent_task + item.price > policy.per_task_cap:
        return Verdict(Decision.DENY, Reason.TASK_BUDGET,
                       f"This would go over the task budget: {usd(spent_task)} of {usd(policy.per_task_cap)} USD "
                       f"already used.", item)

    if spent_today + item.price > policy.daily_cap:
        return Verdict(Decision.DENY, Reason.DAILY_BUDGET,
                       f"This would go over today's budget: {usd(spent_today)} of {usd(policy.daily_cap)} USD "
                       f"already used.", item)

    # Budgets come first on purpose: never ask a person to approve what the budget forbids anyway.
    if item.price > policy.approval_above and not approved:
        return Verdict(Decision.HOLD, Reason.NEEDS_APPROVAL,
                       f"{usd(item.price)} USD is above the {usd(policy.approval_above)} USD limit for automatic "
                       f"purchases, so a person has to approve it.", item)

    return Verdict(Decision.ALLOW, Reason.OK, "Within the rules.", item)
