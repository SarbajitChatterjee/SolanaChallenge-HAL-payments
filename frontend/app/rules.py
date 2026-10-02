"""
Rules: which agents exist, what each may buy and spend, and which items are on sale at which agreed price.
"""

from __future__ import annotations

import re
import threading
import time
from decimal import Decimal, InvalidOperation

from .catalog import Catalog, read_seed, to_catalog
from .db import Repository

AGENT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
TOOL_ID = re.compile(r"^[a-z0-9][a-z0-9_]{1,40}$")
MAX_USD = Decimal("100000")
CACHE_SECONDS = 2.0  # other API instances pick up changes within this time; this one immediately


class RuleError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


def _amount(field: str, value, *, allow_zero: bool = False) -> Decimal:
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        raise RuleError(field, "Enter an amount like 0.25.") from None
    if not amount.is_finite():
        raise RuleError(field, "Enter an amount like 0.25.")
    if amount < 0 or (amount == 0 and not allow_zero):
        raise RuleError(field, "The amount must be above zero." if not allow_zero else "The amount can't be negative.")
    if amount > MAX_USD:
        raise RuleError(field, f"The amount can't be above {MAX_USD:,.0f} USD.")
    if amount.as_tuple().exponent < -6:
        raise RuleError(field, "Use at most 6 decimal places.")
    return amount


def _text(field: str, value, *, required: bool, max_len: int) -> str:
    text = (value or "").strip() if isinstance(value, str) or value is None else str(value).strip()
    if required and not text:
        raise RuleError(field, "This can't be empty.")
    if len(text) > max_len:
        raise RuleError(field, f"Keep it under {max_len} characters.")
    return text


def _url(value) -> str:
    url = _text("url", value, required=True, max_len=2000)
    if url.startswith("{vendor_base}/"):
        return url
    if url.startswith("https://"):
        return url
    if re.match(r"^http://(localhost|127\.0\.0\.1)(:\d+)?/", url):
        return url
    raise RuleError("url", "Use the seller's full https:// address.")


class Rules:
    def __init__(self, repo: Repository, vendor_base: str, seed_path: str | None = None) -> None:
        self.repo = repo
        self.vendor_base = vendor_base
        self.seed_path = seed_path
        self._lock = threading.Lock()
        self._cache: tuple[float, Catalog, dict[str, str]] | None = None

    # ---- reading ---------------------------------------------------------------------------------------
    def seed(self) -> dict:
        return read_seed(self.seed_path)

    def seed_if_empty(self) -> None:
        self.repo.seed_rules_if_empty(self.seed())

    def catalog(self) -> Catalog:
        """Active agents and items. Cached briefly; any edit on this instance clears the cache at once."""
        with self._lock:
            if self._cache and time.monotonic() - self._cache[0] < CACHE_SECONDS:
                return self._cache[1]
            items = self.repo.list_items()
            catalog = to_catalog(self.repo.list_agents(), items, self.vendor_base)
            names = {i["tool"]: i["name"] for i in items}  # archived items keep their name in the ledger
            self._cache = (time.monotonic(), catalog, names)
            return catalog

    def item_name(self, tool: str | None) -> str | None:
        self.catalog()
        return self._cache[2].get(tool or "", tool) if self._cache else tool

    def invalidate(self) -> None:
        with self._lock:
            self._cache = None

    def admin_view(self) -> dict:
        return {"agents": self.repo.list_agents(), "items": self.repo.list_items()}

    # ---- validation --------------------------------------------------------------------------------------
    def _check_agent(self, a: dict) -> dict:
        per_task = _amount("per_task_cap", a.get("per_task_cap"))
        daily = _amount("daily_cap", a.get("daily_cap"))
        approval = _amount("approval_above", a.get("approval_above"), allow_zero=True)
        if per_task > daily:
            raise RuleError("per_task_cap", "The task budget can't be bigger than the daily budget.")
        if approval > per_task:
            raise RuleError("approval_above", "The approval limit can't be bigger than the task budget.")
        tools = a.get("allowed_tools")
        if not isinstance(tools, list) or not tools:
            raise RuleError("allowed_tools", "Pick at least one item this agent may buy.")
        known = {i["tool"] for i in self.repo.list_items() if i["active"]}
        if unknown := sorted(set(tools) - known):
            raise RuleError("allowed_tools", f"Not on sale (or archived): {', '.join(unknown)}.")
        return {**a, "per_task_cap": per_task, "daily_cap": daily, "approval_above": approval,
                "allowed_tools": sorted(set(tools)),
                "description": _text("description", a.get("description"), required=False, max_len=200)}

    def _check_item(self, i: dict) -> dict:
        return {**i, "name": _text("name", i.get("name"), required=True, max_len=80),
                "vendor": _text("vendor", i.get("vendor"), required=True, max_len=128),
                "description": _text("description", i.get("description"), required=False, max_len=200),
                "url": _url(i.get("url")), "price": _amount("price", i.get("price"))}

    @staticmethod
    def _diff(old: dict, new: dict, fields: tuple[str, ...]) -> dict:
        changes = {}
        for f in fields:
            before, after = old.get(f), new.get(f)
            if isinstance(before, Decimal) or isinstance(after, Decimal):
                before, after = (f"{Decimal(str(x)).normalize():f}" if x is not None else None for x in (before, after))
            if before != after:
                changes[f] = [before, after]
        return changes

    # ---- agents ------------------------------------------------------------------------------------------
    AGENT_FIELDS = ("description", "allowed_tools", "per_task_cap", "daily_cap", "approval_above", "active")
    ITEM_FIELDS = ("name", "description", "vendor", "url", "price", "active")

    def create_agent(self, data: dict, *, actor: str, has_key) -> dict:
        agent_id = (data.get("agent_id") or "").strip()
        if not AGENT_ID.match(agent_id):
            raise RuleError("agent_id", "Use 2–41 lowercase letters, digits or dashes, e.g. pricing-agent.")
        if any(a["agent_id"] == agent_id for a in self.repo.list_agents()):
            raise RuleError("agent_id", "An agent with this name already exists.")
        if not has_key(agent_id):
            raise RuleError("agent_id", "This server can't create keys for new agents. Set APP_SECRET in Render.")
        agent = self._check_agent({**data, "agent_id": agent_id, "active": True})
        self.repo.create_agent(agent)
        self.repo.add_audit(actor=actor, action="agent.created", target=agent_id,
                            details={f: [None, str(agent[f]) if isinstance(agent[f], Decimal) else agent[f]]
                                     for f in self.AGENT_FIELDS if f != "active"})
        self.invalidate()
        return self._find_agent(agent_id)

    def update_agent(self, agent_id: str, changes: dict, *, actor: str) -> dict:
        current = self._find_agent(agent_id)
        merged = {**current, **{k: v for k, v in changes.items() if k in self.AGENT_FIELDS}}
        if merged.get("active") is not False:
            merged = self._check_agent(merged)
        else:
            merged = {**current, "active": False}  # archiving needs no other checks
        diff = self._diff(current, merged, self.AGENT_FIELDS)
        if diff:
            self.repo.update_agent(merged)
            action = ("agent.archived" if diff.get("active") == [True, False]
                      else "agent.restored" if diff.get("active") == [False, True] else "agent.updated")
            self.repo.add_audit(actor=actor, action=action, target=agent_id, details=diff)
            self.invalidate()
        return self._find_agent(agent_id)

    def _find_agent(self, agent_id: str) -> dict:
        found = next((a for a in self.repo.list_agents() if a["agent_id"] == agent_id), None)
        if not found:
            raise LookupError(f"Unknown agent '{agent_id}'.")
        return found

    # ---- items -------------------------------------------------------------------------------------------
    def create_item(self, data: dict, *, actor: str) -> dict:
        tool = (data.get("tool") or "").strip()
        if not TOOL_ID.match(tool):
            raise RuleError("tool", "Use 2–41 lowercase letters, digits or underscores, e.g. weather_lookup.")
        if any(i["tool"] == tool for i in self.repo.list_items()):
            raise RuleError("tool", "An item with this id already exists.")
        item = self._check_item({**data, "tool": tool, "active": True})
        self.repo.create_item(item)
        self.repo.add_audit(actor=actor, action="item.created", target=tool,
                            details={f: [None, str(item[f]) if isinstance(item[f], Decimal) else item[f]]
                                     for f in self.ITEM_FIELDS if f != "active"})
        self.invalidate()
        return self._find_item(tool)

    def update_item(self, tool: str, changes: dict, *, actor: str) -> dict:
        current = self._find_item(tool)
        merged = {**current, **{k: v for k, v in changes.items() if k in self.ITEM_FIELDS}}
        merged = self._check_item(merged) if merged.get("active") is not False else {**current, "active": False}
        diff = self._diff(current, merged, self.ITEM_FIELDS)
        if diff:
            self.repo.update_item(merged)
            action = ("item.archived" if diff.get("active") == [True, False]
                      else "item.restored" if diff.get("active") == [False, True] else "item.updated")
            self.repo.add_audit(actor=actor, action=action, target=tool, details=diff)
            self.invalidate()
        return self._find_item(tool)

    def _find_item(self, tool: str) -> dict:
        found = next((i for i in self.repo.list_items() if i["tool"] == tool), None)
        if not found:
            raise LookupError(f"Unknown item '{tool}'.")
        return found

    # ---- demo ------------------------------------------------------------------------------------------------
    def reset_demo(self, *, actor: str) -> None:
        self.repo.reset_demo(self.seed())
        self.repo.add_audit(actor=actor, action="demo.reset", target=None,
                            details={"note": "Purchases and approvals cleared, starting rules restored."})
        self.invalidate()

    def demo_rules_intact(self) -> bool:
        """The guided tour's story (0.75 task budget, 0.25 approval limit, ...) needs the starting rules."""
        seed = self.seed()
        current = self.catalog()
        start = to_catalog(seed["agents"], seed["items"], self.vendor_base)
        return all(current.agents.get(k) == v for k, v in start.agents.items()) and \
            all(current.items.get(k) == v for k, v in start.items.items())