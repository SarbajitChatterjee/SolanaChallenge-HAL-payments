"""The purchase flow, independent of HTTP:

    decide + reserve  (one locked DB transaction, run in a worker thread)
    pay               (async, outside the lock; the reservation already holds the budget)
    settle / release  (mark the event paid, or blocked/failed so it stops counting)

Every answer has the same shape: decision, status, reason_code (for software) and reason (for people).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import timedelta
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from urllib.parse import quote

from .catalog import Catalog
from .rules import Rules
from .db import Repository, iso, money, new_id, start_of_day, utcnow
from .fingerprint import canonical_json, fingerprint
from .firewall import scan
from .policy import CatalogItem, Decision, Reason, SpendRequest, _normalize, evaluate, origin, resolve, usd
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
                 explorer_tx_url: str | None = None, seller_review_after: int = 1) -> None:
        self.repo = repo
        self.rail = rail
        self.rules = rules
        self.explorer_tx_url = explorer_tx_url
        self.seller_review_after = seller_review_after  # incidents before a seller goes under review
        
        # Per-process lock per agent. The DB row lock covers several instances; this covers SQLite.
        self._locks: dict[str, threading.Lock] = defaultdict(threading.Lock)

    # ---- the purchase flow ---------------------------------------------------
    async def call(self, agent_id: str, req: CallRequest) -> Outcome:
        decided = await asyncio.to_thread(self._decide_and_reserve, agent_id, req)
        if isinstance(decided, Outcome):
            return decided  # blocked, held, or reused (nothing to pay)
        item = decided.item
        try:
            result = await self.rail.pay_and_fetch(agent_id=agent_id, url=item.url, max_price=item.price,
                                                   params=req.params)
        except PriceRejected as exc:
            log.info("price rejected for %s/%s: %s", agent_id, item.tool, exc)
            if exc.quoted is not None:
                message = (f"{item.vendor} asked {usd(exc.quoted)} USD. The agreed price is {usd(item.price)} USD, "
                           f"so nothing was paid.")
            else:
                message = f"The seller asked for more than the agreed {usd(item.price)} USD, so nothing was paid."
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
        
        # Response firewall: check what the seller sent before the agent sees it.
        approved = {i.url for i in self.catalog.items.values()}
        data, flags, links = scan(result.data, approved, item.content_policy)
        if flags:
            await asyncio.to_thread(self.repo.record_content_flags, decided.event_id, flags)

        # Provenance: remember every link, so a later purchase of it can be traced back to this seller.
        if links:
            await asyncio.to_thread(self.repo.record_links, event_id=decided.event_id, agent_id=agent_id,
                                    origin=origin(item.url), links=links)

        # Purchase reuse: keep the cleaned result, so the same purchase in the window costs nothing.
        if item.reuse_ttl_seconds > 0:
            await asyncio.to_thread(self.repo.store_payload, decided.event_id, data, item.reuse_ttl_seconds)
        return answer(200, "allow", "settled", "paid", message, amount=usd(item.price), vendor=item.vendor,
                      tool=item.tool, item_name=item.name or item.tool, tx=result.tx,
                      explorer_url=self.explorer_url(result.tx), data=data, content_flags=flags)

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

            # Loop protection: the same purchase across all tasks, and the attempt rate of this agent.
            fp = fingerprint(req.tool or req.url or "", req.params)
            now, floor = utcnow(), tx.unfrozen_at()

            def since(delta: timedelta):
                start = now - delta
                return max(start, floor) if floor else start

            spend = SpendRequest(agent_id=agent_id, task_id=req.task_id, tool=req.tool, url=req.url)
            target = resolve(spend, catalog.items)  # only to look up the seller's review status and reuse

            # Reuse needs no payment. A purchase a person approved is always paid, as approved.
            stored = None
            if target and target.reuse_ttl_seconds > 0 and not approved:
                stored = tx.find_reusable(fp, org_wide=target.reuse_scope == "org")
            verdict = evaluate(
                spend, policy=policy, catalog=catalog.items,
                spent_task=tx.spent(task_id=req.task_id), spent_today=tx.spent(since=start_of_day()),
                frozen=tx.is_frozen(), approved=approved,
                repeat_count=tx.count_fingerprint_since(fp, now - timedelta(minutes=policy.repeat_window_minutes)),
                attempts_last_min=tx.count_attempts_since(since(timedelta(minutes=1))),
                spent_last_10m=tx.spent(since=since(timedelta(minutes=10))),
                seller_under_review=bool(target) and tx.seller_under_review(origin(target.url)),
                reusable=stored is not None)
            item = verdict.item

            if approved and (item is None or item.tool != tx.get_approval(req.approval_id)["tool"]):
                return Outcome(409, {"detail": "This approval was given for a different purchase."})

            common = dict(task_id=req.task_id, tool=item.tool if item else req.tool,
                          url=item.url if item else req.url, vendor=item.vendor if item else None,
                          amount=item.price if item else None, reason=verdict.message,
                          reason_code=verdict.code.value, fingerprint=fp, params_json=canonical_json(req.params))

            if verdict.decision is Decision.DENY:

                # Provenance: a blocked link that came from a paid response names the seller that sent it.
                source = None
                if verdict.code is Reason.NOT_IN_CATALOG and req.url:
                    source = tx.lookup_link(_normalize(req.url), now - timedelta(hours=24))
                if source is None:
                    tx.record(decision="deny", status="blocked", **common)
                    if verdict.code is Reason.CIRCUIT_BREAKER:
                        tx.freeze(verdict.message)  # only a person can switch the agent back on
                    return answer(403, "deny", "blocked", verdict.code.value, verdict.message)
                return self._trace_to_seller(tx, source, verdict.message, common)

            if verdict.code is Reason.REUSED:
                return self._reuse(tx, item, stored, common)

            if verdict.decision is Decision.HOLD:
                message = verdict.message + self._task_so_far(tx, req.task_id)
                common = {**common, "reason": message}
                approval_id = tx.create_approval(task_id=req.task_id, tool=item.tool, vendor=item.vendor,
                                                 amount=item.price, reason=message)
                tx.record(decision="hold", status="held", event_id=approval_id, **common)  # same id: decision updates it
                return answer(202, "hold", "pending", verdict.code.value, message, approval_id=approval_id,
                              amount=usd(item.price), item_name=item.name or item.tool)

            if approved and not tx.use_approval(req.approval_id):
                return answer(403, "deny", "used", "approval_used",
                              "This approval was already used for an earlier purchase.")
            event_id = tx.record(decision="allow", status="reserved", **common)
            return _Reserved(event_id, item)

    def _trace_to_seller(self, tx, source: dict, message: str, common: dict) -> Outcome:
        """Record the blocked attempt with its cause, add a seller incident, and start a review if needed."""
        seller, vendor = source["seller_origin"], source["vendor"] or source["seller_origin"]
        message += f" The link came from {vendor}, purchase {source['source_event_id'][:4]}."
        already = tx.seller_under_review(seller)
        event_id = new_id()
        tx.add_incident(seller, "injection", event_id)
        if already:
            message += f" {vendor} is under review."
        elif tx.count_incidents(seller) >= self.seller_review_after:
            tx.set_seller_status(seller, "under_review", "HAL")
            message += f" {vendor} is now under review: its next purchases wait for a person."
        common = {**common, "reason": message}
        tx.record(decision="deny", status="blocked", event_id=event_id,
                  caused_by_event_id=source["source_event_id"], **common)
        return answer(403, "deny", "blocked", Reason.NOT_IN_CATALOG.value, message,
                      caused_by=source["source_event_id"], caused_by_seller=vendor)

    def _task_so_far(self, tx, task_id: str) -> str:
        """Context for the person who approves: what this task already bought."""
        bought = tx.task_purchases(task_id)
        if not bought:
            return " This task has bought nothing yet."
        names = ", ".join(self._name(tool) or tool for tool, _ in bought)
        total = sum((amount for _, amount in bought), Decimal("0"))
        return f" Task {task_id} already bought: {names} ({usd(total)} USD)."

    def _reuse(self, tx, item: CatalogItem, stored: dict, common: dict) -> Outcome:
        """Answer with the stored result of an earlier purchase. Nothing is paid, and no budget is used."""
        message = f"Reused the result of purchase {stored['id'][:4]}. Nothing was paid (saved {usd(item.price)} USD)."
        common = {**common, "amount": Decimal("0"), "reason": message}
        tx.record(decision="allow", status="reused", reused_from_event_id=stored["id"], **common)
        return answer(200, "allow", "reused", Reason.REUSED.value, message, amount=usd(Decimal("0")),
                      saved=usd(item.price), vendor=item.vendor, tool=item.tool, item_name=item.name or item.tool,
                      reused_from=stored["id"], tx=stored["tx"], explorer_url=self.explorer_url(stored["tx"]),
                      data=json.loads(stored["body_json"]),
                      content_flags=json.loads(stored["content_flags_json"] or "[]"))

    def sellers(self) -> list[dict[str, Any]]:
        """Every seller in the rules or with a record, with its status and incident count."""
        overview = self.repo.seller_overview()
        names: dict[str, list[str]] = defaultdict(list)
        for i in self.catalog.items.values():
            if i.vendor not in names[origin(i.url)]:
                names[origin(i.url)].append(i.vendor)
        out = []
        for seller in sorted(set(names) | set(overview)):
            row = overview.get(seller, {})
            out.append({"seller_origin": seller, "vendors": names.get(seller, []),
                        "status": row.get("status", "active"), "incidents": row.get("incidents", 0),
                        "updated_at": iso(row.get("updated_at")), "updated_by": row.get("updated_by")})
        return out

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
                **self._saved(a.agent_id, since),
                "frozen_reason": self.repo.frozen_reason(a.agent_id) if frozen.get(a.agent_id) else None,
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
            "caused_by": r["caused_by_event_id"], "reused_from": r["reused_from_event_id"],
            "content_flags": json.loads(r["content_flags_json"] or "[]"),
        } for r in self.repo.recent_events()]
        return {"rail": self.rail.name, "network": getattr(self.rail, "network", None),
                "agents": agents, "approvals": approvals, "events": events}

    def _saved(self, agent_id: str, since) -> dict[str, Any]:
        amount, count = self.repo.saved(agent_id, since=since)
        return {"saved_today": usd(amount), "reused_today": count}

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