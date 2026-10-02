"""The purchase flow, independent of HTTP:

    decide + reserve  (one locked DB transaction, run in a worker thread)
    pay               (async, outside the lock; the reservation already holds the budget)
    settle / release  (mark the event paid, or blocked/failed so it stops counting)

Every answer has the same shape: decision, status, reason_code (for software) and reason (for people).
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

from .catalog import Catalog
from .rules import Rules
from .db import Repository, iso, money, start_of_day
from .policy import CatalogItem, Decision, SpendRequest, evaluate, usd
from .rails import PaymentRail, PriceRejected

log = logging.getLogger("agentbudget.service")


@dataclass
class CallRequest:
    task_id: str
    tool: str | None = None
    url: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    approval_id: str | None = None


@dataclass
class Outcome:
    http_status: int
    body: dict[str, Any]


@dataclass
class _Reserved:
    event_id: str
    item: CatalogItem


def answer(status_code: int, decision: str, status: str, code: str, reason: str, **extra: Any) -> Outcome:
    return Outcome(status_code, {"decision": decision, "status": status, "reason_code": code, "reason": reason,
                                 **extra})


class SpendService:
    def __init__(self, repo: Repository, rail: PaymentRail, rules: Rules,
                 explorer_tx_url: str | None = None) -> None:
        self.repo = repo
        self.rail = rail
        self.rules = rules
        self.explorer_tx_url = explorer_tx_url
        # Per-process lock per agent. The DB row lock covers several instances; this covers SQLite.
        self._locks: dict[str, threading.Lock] = defaultdict(threading.Lock)

    # ---- the purchase flow ---------------------------------------------------
    async def call(self, agent_id: str, req: CallRequest) -> Outcome:
        decided = await asyncio.to_thread(self._decide_and_reserve, agent_id, req)
        if isinstance(decided, Outcome):
            return decided
        item = decided.item
        try:
            result = await self.rail.pay_and_fetch(agent_id=agent_id, url=item.url, max_price=item.price,
                                                   params=req.params)
        except PriceRejected as exc:
            log.info("price rejected for %s/%s: %s", agent_id, item.tool, exc)
            message = (f"The seller asked for more than the agreed {usd(item.price)} USD, so nothing was paid.")
            await asyncio.to_thread(self.repo.finish_event, decided.event_id, status="blocked", decision="deny",
                                    reason=message, reason_code="price_too_high")
            return answer(403, "deny", "blocked", "price_too_high", message)
        except Exception as exc:  # noqa: BLE001 - any payment failure releases the reservation
            log.warning("payment failed for %s/%s: %s", agent_id, item.tool, exc)
            message = "The payment didn't go through, so nothing was charged. Try again in a moment."
            await asyncio.to_thread(self.repo.finish_event, decided.event_id, status="failed",
                                    reason=message, reason_code="payment_failed")
            return answer(502, "allow", "failed", "payment_failed", message, detail=f"{type(exc).__name__}: {exc}")

        message = f"Paid {usd(item.price)} USD to {item.vendor}."
        await asyncio.to_thread(self.repo.finish_event, decided.event_id, status="settled", tx=result.tx,
                                reason=message, reason_code="paid")
        return answer(200, "allow", "settled", "paid", message, amount=usd(item.price), vendor=item.vendor,
                      tool=item.tool, item_name=item.name or item.tool, tx=result.tx,
                      explorer_url=self.explorer_url(result.tx), data=result.data)

    @property
    def catalog(self) -> Catalog:
        """The live rules (edited on the dashboard)."""
        return self.rules.catalog()

    def _decide_and_reserve(self, agent_id: str, req: CallRequest) -> Outcome | _Reserved:
        catalog = self.catalog  # one consistent snapshot for this purchase
        policy = catalog.agents.get(agent_id)
        if policy is None:
            return Outcome(404, {"detail": f"Unknown agent '{agent_id}'."})
        with self._locks[agent_id], self.repo.agent_tx(agent_id) as tx:
            approved = False
            if req.approval_id:
                approval = tx.get_approval(req.approval_id)
                if not approval or approval["agent_id"] != agent_id:
                    return Outcome(404, {"detail": "Unknown approval."})
                if approval["status"] == "pending":
                    return answer(202, "hold", "pending", "approval_pending",
                                  "Still waiting for a person to approve this.", approval_id=req.approval_id)
                if approval["status"] == "denied":
                    return answer(403, "deny", "denied", "approval_denied", "A person said no to this purchase.")
                if approval["status"] == "used":
                    return answer(403, "deny", "used", "approval_used",
                                  "This approval was already used for an earlier purchase.")
                approved = True

            verdict = evaluate(
                SpendRequest(agent_id=agent_id, task_id=req.task_id, tool=req.tool, url=req.url),
                policy=policy, catalog=catalog.items,
                spent_task=tx.spent(task_id=req.task_id), spent_today=tx.spent(since=start_of_day()),
                frozen=tx.is_frozen(), approved=approved)
            item = verdict.item

            if approved and (item is None or item.tool != tx.get_approval(req.approval_id)["tool"]):
                return Outcome(409, {"detail": "This approval was given for a different purchase."})

            common = dict(task_id=req.task_id, tool=item.tool if item else req.tool,
                          url=item.url if item else req.url, vendor=item.vendor if item else None,
                          amount=item.price if item else None, reason=verdict.message,
                          reason_code=verdict.code.value)

            if verdict.decision is Decision.DENY:
                tx.record(decision="deny", status="blocked", **common)
                return answer(403, "deny", "blocked", verdict.code.value, verdict.message)

            if verdict.decision is Decision.HOLD:
                approval_id = tx.create_approval(task_id=req.task_id, tool=item.tool, vendor=item.vendor,
                                                 amount=item.price, reason=verdict.message)
                tx.record(decision="hold", status="held", event_id=approval_id, **common)  # same id: decision updates it
                return answer(202, "hold", "pending", verdict.code.value, verdict.message, approval_id=approval_id,
                              amount=usd(item.price), item_name=item.name or item.tool)

            if approved and not tx.use_approval(req.approval_id):
                return answer(403, "deny", "used", "approval_used",
                              "This approval was already used for an earlier purchase.")
            event_id = tx.record(decision="allow", status="reserved", **common)
            return _Reserved(event_id, item)

    # ---- read models -----------------------------------------------------------
    def explorer_url(self, tx: str | None) -> str | None:
        network = getattr(self.rail, "network", None)
        if not tx or tx.startswith("mock-") or network is None:
            return None
        if self.explorer_tx_url:
            return self.explorer_tx_url.format(tx=tx)
        if network == "localnet":  # Solana Explorer can read any RPC, including the sandbox
            return (f"https://explorer.solana.com/tx/{tx}?cluster=custom"
                    f"&customUrl={quote(getattr(self.rail, 'rpc_url', ''), safe='')}")
        return f"https://explorer.solana.com/tx/{tx}?cluster={network}"

    def public_catalog(self) -> dict[str, Any]:
        return {
            "items": [{"tool": i.tool, "name": i.name or i.tool, "description": i.description, "vendor": i.vendor,
                       "price": usd(i.price)} for i in self.catalog.items.values()],
            "agents": [{"agent_id": a.agent_id, "description": a.description, "allowed_tools": sorted(a.allowed_tools),
                        "per_task_cap": usd(a.per_task_cap), "daily_cap": usd(a.daily_cap),
                        "approval_above": usd(a.approval_above)} for a in self.catalog.agents.values()],
        }

    async def state(self) -> dict[str, Any]:
        snapshot = await asyncio.to_thread(self._read_state)
        balances = await asyncio.gather(*(self.rail.balance(a) for a in self.catalog.agents))
        for agent, balance in zip(snapshot["agents"], balances):
            agent["wallet_usdc"] = usd(balance) if balance is not None else None
        return snapshot

    def _read_state(self) -> dict[str, Any]:
        since = start_of_day()
        frozen = self.repo.frozen_map()
        agents = []
        for a in self.catalog.agents.values():
            current = self.repo.current_task(a.agent_id)
            agents.append({
                "agent_id": a.agent_id,
                "description": a.description,
                "frozen": frozen.get(a.agent_id, False),
                "allowed_tools": sorted(a.allowed_tools),
                "per_task_cap": usd(a.per_task_cap),
                "daily_cap": usd(a.daily_cap),
                "approval_above": usd(a.approval_above),
                "spent_today": usd(self.repo.spent(a.agent_id, since=since)),
                "current_task": {"task_id": current[0], "spent": usd(current[1])} if current else None,
                "wallet_address": self._wallet_address(a.agent_id),
                "wallet_usdc": None,
            })
        approvals = [{
            "id": r["id"], "created_at": iso(r["created_at"]), "agent_id": r["agent_id"], "task_id": r["task_id"],
            "tool": r["tool"], "item_name": self._name(r["tool"]), "vendor": r["vendor"],
            "amount": money(r["amount_micros"]), "reason": r["reason"], "status": r["status"],
        } for r in self.repo.pending_approvals()]
        events = [{
            "id": r["id"], "created_at": iso(r["created_at"]), "agent_id": r["agent_id"], "task_id": r["task_id"],
            "tool": r["tool"], "item_name": self._name(r["tool"]) if r["tool"] else None, "url": r["url"],
            "vendor": r["vendor"], "amount": money(r["amount_micros"]), "decision": r["decision"],
            "status": r["status"], "reason_code": r["reason_code"], "reason": r["reason"], "tx": r["tx"],
            "explorer_url": self.explorer_url(r["tx"]),
        } for r in self.repo.recent_events()]
        return {"rail": self.rail.name, "network": getattr(self.rail, "network", None),
                "agents": agents, "approvals": approvals, "events": events}

    def _wallet_address(self, agent_id: str) -> str | None:
        """Display only: a missing key must never take the dashboard down."""
        if self.rail.name != "paykit":
            return None
        try:
            return self.rail.pubkey(agent_id)
        except Exception:  # noqa: BLE001
            return None

    def _name(self, tool: str | None) -> str | None:
        return self.rules.item_name(tool)