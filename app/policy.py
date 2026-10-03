"""Spend rules. Pure functions, no I/O: this is AgentBudget's core.

Checks run in this order, cheapest and most absolute first:
  1. kill switch         -> deny
  2. circuit breaker     -> deny, and the caller freezes the agent (too many attempts, or spending too fast)
  3. approved list       -> deny  (unknown seller, or item this agent may not buy)
  4. repeat rule         -> deny  (the same purchase was already paid too often)
  5. budgets             -> deny  (per task and per day, money already reserved included)
  6. seller under review -> hold  (the seller sent a trap; a person decides)
  7. approval limit      -> hold  (a person decides)
Whatever passes is allowed.

The breaker comes before the other checks so that a loop of blocked attempts also trips it.
Its threshold (30 attempts a minute) is far above the repeat limit, so a loop shows "repeat" first.

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
    REPEAT_PURCHASE = "repeat_purchase"
    CIRCUIT_BREAKER = "circuit_breaker"
    SELLER_UNDER_REVIEW = "seller_under_review"


@dataclass(frozen=True)
class CatalogItem:
    tool: str
    url: str
    price: Decimal          # agreed price in USD; payments above it are never signed
    vendor: str
    name: str = ""          # human name, e.g. "Company record"
    description: str = ""
    content_policy: str = "annotate"   # response firewall: annotate | redact


@dataclass(frozen=True)
class AgentPolicy:
    agent_id: str
    allowed_tools: frozenset[str]
    per_task_cap: Decimal
    daily_cap: Decimal
    approval_above: Decimal
    description: str = ""
    max_repeats: int = 2                 # the same purchase is paid at most this often...
    repeat_window_minutes: int = 60      # ...within this window
    max_attempts_per_min: int = 30       # breaker: more attempts than this in one minute
    velocity_share_10m: float = 0.2      # breaker: more than this share of the daily cap spent in 10 minutes


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


def origin(url: str) -> str:
    """The seller key: scheme://host[:port]. Two items from one origin are one seller."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


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
    repeat_count: int = 0,
    attempts_last_min: int = 0,
    spent_last_10m: Decimal = Decimal("0"),
    seller_under_review: bool = False,
) -> Verdict:
    if frozen:
        return Verdict(Decision.DENY, Reason.FROZEN, "This agent is stopped. Someone flipped the kill switch.")

    if attempts_last_min >= policy.max_attempts_per_min:
        return Verdict(Decision.DENY, Reason.CIRCUIT_BREAKER,
                       f"Stopped automatically: {attempts_last_min + 1} purchase attempts in 60 seconds.")
    velocity_limit = policy.daily_cap * Decimal(str(policy.velocity_share_10m))
    if spent_last_10m > velocity_limit:
        return Verdict(Decision.DENY, Reason.CIRCUIT_BREAKER,
                       f"Stopped automatically: {usd(spent_last_10m)} USD spent in 10 minutes, more than "
                       f"{policy.velocity_share_10m:.0%} of the daily budget.")

    item = resolve(req, catalog)
    if item is None:
        return Verdict(Decision.DENY, Reason.NOT_IN_CATALOG,
                       "This seller isn't on the approved list, so nothing was paid.")

    label = item.name or item.tool
    if item.tool not in policy.allowed_tools:
        return Verdict(Decision.DENY, Reason.NOT_ALLOWED,
                       f"{policy.agent_id} isn't allowed to buy {label}.", item)

    if repeat_count >= policy.max_repeats:
        return Verdict(Decision.DENY, Reason.REPEAT_PURCHASE,
                       f"This exact purchase was already paid {repeat_count} times in the last "
                       f"{policy.repeat_window_minutes} minutes.", item)

    if spent_task + item.price > policy.per_task_cap:
        return Verdict(Decision.DENY, Reason.TASK_BUDGET,
                       f"This would go over the task budget: {usd(spent_task)} of {usd(policy.per_task_cap)} USD "
                       f"already used.", item)

    if spent_today + item.price > policy.daily_cap:
        return Verdict(Decision.DENY, Reason.DAILY_BUDGET,
                       f"This would go over today's budget: {usd(spent_today)} of {usd(policy.daily_cap)} USD "
                       f"already used.", item)

    # Budgets come first on purpose: never ask a person to approve what the budget forbids anyway.
    if seller_under_review and not approved:
        return Verdict(Decision.HOLD, Reason.SELLER_UNDER_REVIEW,
                       f"{item.vendor} is under review because it sent a link an agent was told to buy. "
                       f"A person has to approve purchases from it.", item)

    if item.price > policy.approval_above and not approved:
        return Verdict(Decision.HOLD, Reason.NEEDS_APPROVAL,
                       f"{usd(item.price)} USD is above the {usd(policy.approval_above)} USD limit for automatic "
                       f"purchases, so a person has to approve it.", item)

    return Verdict(Decision.ALLOW, Reason.OK, "Within the rules.", item)