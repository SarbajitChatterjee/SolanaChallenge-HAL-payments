"""Persistence: SQLAlchemy Core over SQLite (dev, tests) or Supabase Postgres (prod).

Design choices:
- Money is stored as integer micro-USD (6 decimals, like USDC on-chain): exact on every database.
- On Postgres the tables live in their own schema, "agentbudget", which Supabase's auto-generated
  Data API does not expose. Only the backend, via the connection string, can read them.
- Every spend decision runs inside AgentTx: one transaction holding a row lock on the agent
  (SELECT ... FOR UPDATE), so several API instances can never double-spend the same budget.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterator

from sqlalchemy import (BigInteger, Boolean, Column, DateTime, Index, MetaData, String, Table, Text,
                        create_engine, delete, func, insert, select, text, update)
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

PG_SCHEMA = "agentbudget"
MICRO = Decimal(10**6)
COUNTED = ("reserved", "settled")  # statuses that consume budget

metadata = MetaData()

events = Table(
    "events", metadata,
    Column("id", String(24), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("agent_id", String(64), nullable=False),
    Column("task_id", String(64), nullable=False),
    Column("tool", String(64)),
    Column("url", Text),
    Column("vendor", String(128)),
    Column("amount_micros", BigInteger),
    Column("decision", String(8), nullable=False),   # allow | hold | deny
    Column("status", String(16), nullable=False),    # reserved | settled | held | blocked | failed | control
    Column("reason", Text),            # plain-language message for people
    Column("reason_code", String(32)),  # stable code for software, see policy.Reason
    Column("tx", String(128)),
)
Index("ix_events_agent_time", events.c.agent_id, events.c.created_at)
Index("ix_events_agent_task", events.c.agent_id, events.c.task_id)

approvals = Table(
    "approvals", metadata,
    Column("id", String(24), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("agent_id", String(64), nullable=False),
    Column("task_id", String(64), nullable=False),
    Column("tool", String(64), nullable=False),
    Column("vendor", String(128)),
    Column("amount_micros", BigInteger, nullable=False),
    Column("reason", Text),
    Column("status", String(16), nullable=False),  # pending | approved | denied | used
    Column("decided_at", DateTime(timezone=True)),
)

agent_state = Table(
    "agent_state", metadata,
    Column("agent_id", String(64), primary_key=True),
    Column("frozen", Boolean, nullable=False, default=False),
)

early_access = Table(
    "early_access", metadata,
    Column("email", String(254), primary_key=True),   # lower-cased; one row per person
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("role", String(16), nullable=False),        # builder | approver | vendor | curious
    Column("use_case", Text),
    Column("consent_at", DateTime(timezone=True), nullable=False),
)


agents = Table(
    "agents", metadata,
    Column("agent_id", String(64), primary_key=True),
    Column("description", Text),
    Column("allowed_tools", Text, nullable=False),          # JSON list of item ids
    Column("per_task_cap_micros", BigInteger, nullable=False),
    Column("daily_cap_micros", BigInteger, nullable=False),
    Column("approval_above_micros", BigInteger, nullable=False),
    Column("active", Boolean, nullable=False, default=True),  # archived agents keep their history
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

catalog_items = Table(
    "catalog_items", metadata,
    Column("tool", String(64), primary_key=True),
    Column("name", String(80), nullable=False),
    Column("description", Text),
    Column("vendor", String(128), nullable=False),
    Column("url", Text, nullable=False),                      # may contain {vendor_base}
    Column("price_micros", BigInteger, nullable=False),
    Column("active", Boolean, nullable=False, default=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

audit_log = Table(
    "audit_log", metadata,
    Column("id", String(24), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("actor", String(32), nullable=False),              # operator | demo visitor
    Column("action", String(64), nullable=False),             # agent.created, item.updated, demo.reset, ...
    Column("target", String(128)),
    Column("details", Text),                                  # JSON: {"field": [old, new], ...}
)

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def start_of_day() -> datetime:
    return utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


def to_micros(amount: Decimal | None) -> int | None:
    return None if amount is None else int((amount * MICRO).to_integral_value())


def from_micros(micros: int | None) -> Decimal | None:
    return None if micros is None else Decimal(micros) / MICRO


def money(micros: int | None) -> str | None:
    value = from_micros(micros)
    return None if value is None else f"{value:.2f}" if value == value.quantize(Decimal("0.01")) else f"{value:f}"


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class AgentTx:
    """Reads and writes for one agent inside one locked transaction."""

    def __init__(self, conn: Connection, agent_id: str) -> None:
        self.conn = conn
        self.agent_id = agent_id

    def is_frozen(self) -> bool:
        return bool(self.conn.execute(
            select(agent_state.c.frozen).where(agent_state.c.agent_id == self.agent_id)).scalar())

    def spent(self, *, task_id: str | None = None, since: datetime | None = None) -> Decimal:
        q = select(func.coalesce(func.sum(events.c.amount_micros), 0)).where(
            events.c.agent_id == self.agent_id, events.c.status.in_(COUNTED))
        if task_id is not None:
            q = q.where(events.c.task_id == task_id)
        if since is not None:
            q = q.where(events.c.created_at >= since)
        return from_micros(int(self.conn.execute(q).scalar_one()))

    def record(self, *, task_id: str, decision: str, status: str, reason: str, reason_code: str,
               tool: str | None = None, url: str | None = None, vendor: str | None = None,
               amount: Decimal | None = None, event_id: str | None = None) -> str:
        event_id = event_id or new_id()
        self.conn.execute(insert(events).values(
            id=event_id, created_at=utcnow(), agent_id=self.agent_id, task_id=task_id, tool=tool, url=url,
            vendor=vendor, amount_micros=to_micros(amount), decision=decision, status=status, reason=reason,
            reason_code=reason_code))
        return event_id

    def get_approval(self, approval_id: str) -> dict | None:
        row = self.conn.execute(select(approvals).where(approvals.c.id == approval_id)).mappings().first()
        return dict(row) if row else None

    def create_approval(self, *, task_id: str, tool: str, vendor: str, amount: Decimal, reason: str) -> str:
        approval_id = new_id()
        self.conn.execute(insert(approvals).values(
            id=approval_id, created_at=utcnow(), agent_id=self.agent_id, task_id=task_id, tool=tool,
            vendor=vendor, amount_micros=to_micros(amount), reason=reason, status="pending"))
        return approval_id

    def use_approval(self, approval_id: str) -> bool:
        return _transition(self.conn, approval_id, "approved", "used")


def _transition(conn: Connection, approval_id: str, from_status: str, to_status: str) -> bool:
    res = conn.execute(update(approvals)
                       .where(approvals.c.id == approval_id, approvals.c.status == from_status)
                       .values(status=to_status, decided_at=utcnow()))
    return res.rowcount == 1


class Repository:
    def __init__(self, database_url: str) -> None:
        self.is_postgres = database_url.startswith("postgresql")
        kwargs: dict = {"pool_pre_ping": True}
        if self.is_postgres:
            kwargs.update(pool_size=5, max_overflow=5, pool_recycle=300)
        else:
            kwargs["connect_args"] = {"check_same_thread": False}
        engine: Engine = create_engine(database_url, **kwargs)
        if self.is_postgres:
            engine = engine.execution_options(schema_translate_map={None: PG_SCHEMA})
        self.engine = engine

    # ---- lifecycle -----------------------------------------------------------
    def init_schema(self) -> None:
        if self.is_postgres:
            with self.engine.begin() as conn:
                conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{PG_SCHEMA}"'))
        metadata.create_all(self.engine)

    def seed_agents(self, agent_ids) -> None:
        for agent_id in agent_ids:
            try:
                with self.engine.begin() as conn:
                    exists = conn.execute(select(agent_state.c.agent_id)
                                          .where(agent_state.c.agent_id == agent_id)).first()
                    if not exists:
                        conn.execute(insert(agent_state).values(agent_id=agent_id, frozen=False))
            except IntegrityError:
                pass  # another instance seeded it first

    def ping(self) -> bool:
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT 1")).scalar() == 1

    # ---- spend transaction ---------------------------------------------------
    @contextmanager
    def agent_tx(self, agent_id: str) -> Iterator[AgentTx]:
        with self.engine.begin() as conn:
            # Row lock: serialises decisions for this agent across all API instances (no-op on SQLite).
            conn.execute(select(agent_state.c.agent_id)
                         .where(agent_state.c.agent_id == agent_id).with_for_update())
            yield AgentTx(conn, agent_id)

    def finish_event(self, event_id: str, *, status: str, decision: str | None = None,
                     reason: str | None = None, reason_code: str | None = None, tx: str | None = None) -> None:
        values: dict = {"status": status}
        if reason_code is not None:
            values["reason_code"] = reason_code
        if decision is not None:
            values["decision"] = decision
        if reason is not None:
            values["reason"] = reason
        if tx is not None:
            values["tx"] = tx
        with self.engine.begin() as conn:
            conn.execute(update(events).where(events.c.id == event_id).values(**values))

    # ---- operator actions ----------------------------------------------------
    def decide_approval(self, approval_id: str, approve: bool) -> bool:
        """Record the decision, and turn the waiting row in the statement into Approved or Denied.
        (The waiting row has the same id as its approval.)"""
        with self.engine.begin() as conn:
            if not _transition(conn, approval_id, "pending", "approved" if approve else "denied"):
                return False
            conn.execute(update(events).where(events.c.id == approval_id, events.c.status == "held").values(
                status="approved" if approve else "denied", decision="allow" if approve else "deny",
                reason_code="approved" if approve else "denied",
                reason="A person approved this. The agent can now buy it." if approve
                else "A person said no. Nothing was paid."))
            return True

    def set_frozen(self, agent_id: str, frozen: bool) -> None:
        with self.engine.begin() as conn:
            conn.execute(update(agent_state).where(agent_state.c.agent_id == agent_id).values(frozen=frozen))
            conn.execute(insert(events).values(
                id=new_id(), created_at=utcnow(), agent_id=agent_id, task_id="-",
                decision="deny" if frozen else "allow", status="control",
                reason_code="kill_switch_on" if frozen else "kill_switch_off",
                reason="Kill switch on: this agent can't buy anything." if frozen
                else "Kill switch off: this agent can buy again."))

    # ---- rules: agents and items (edited from the dashboard) -------------------------------------------
    @staticmethod
    def _agent_row(r) -> dict:
        return {"agent_id": r["agent_id"], "description": r["description"] or "",
                "allowed_tools": json.loads(r["allowed_tools"]),
                "per_task_cap": from_micros(r["per_task_cap_micros"]), "daily_cap": from_micros(r["daily_cap_micros"]),
                "approval_above": from_micros(r["approval_above_micros"]), "active": bool(r["active"]),
                "created_at": r["created_at"], "updated_at": r["updated_at"]}

    @staticmethod
    def _item_row(r) -> dict:
        return {"tool": r["tool"], "name": r["name"], "description": r["description"] or "", "vendor": r["vendor"],
                "url": r["url"], "price": from_micros(r["price_micros"]), "active": bool(r["active"]),
                "created_at": r["created_at"], "updated_at": r["updated_at"]}

    @staticmethod
    def _agent_values(a: dict) -> dict:
        return {"agent_id": a["agent_id"], "description": a.get("description") or "",
                "allowed_tools": json.dumps(sorted(a["allowed_tools"])),
                "per_task_cap_micros": to_micros(Decimal(str(a["per_task_cap"]))),
                "daily_cap_micros": to_micros(Decimal(str(a["daily_cap"]))),
                "approval_above_micros": to_micros(Decimal(str(a["approval_above"]))),
                "active": a.get("active", True)}

    @staticmethod
    def _item_values(i: dict) -> dict:
        return {"tool": i["tool"], "name": i.get("name") or i["tool"], "description": i.get("description") or "",
                "vendor": i["vendor"], "url": i["url"], "price_micros": to_micros(Decimal(str(i["price"]))),
                "active": i.get("active", True)}

    def list_agents(self) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(agents).order_by(agents.c.agent_id)).mappings().all()
        return [self._agent_row(r) for r in rows]

    def list_items(self) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(catalog_items).order_by(catalog_items.c.tool)).mappings().all()
        return [self._item_row(r) for r in rows]

    def seed_rules_if_empty(self, seed: dict) -> bool:
        """Fill an empty rules table from catalog.json. Never overwrites rules edited on the dashboard."""
        with self.engine.begin() as conn:
            if conn.execute(select(func.count()).select_from(agents)).scalar_one() or \
               conn.execute(select(func.count()).select_from(catalog_items)).scalar_one():
                return False
            self._insert_seed(conn, seed)
        return True

    def _insert_seed(self, conn: Connection, seed: dict) -> None:
        now = utcnow()
        for i in seed["items"]:
            conn.execute(insert(catalog_items).values(**self._item_values(i), created_at=now, updated_at=now))
        for a in seed["agents"]:
            conn.execute(insert(agents).values(**self._agent_values(a), created_at=now, updated_at=now))
            if not conn.execute(select(agent_state.c.agent_id).where(agent_state.c.agent_id == a["agent_id"])).first():
                conn.execute(insert(agent_state).values(agent_id=a["agent_id"], frozen=False))

    def create_agent(self, a: dict) -> None:
        now = utcnow()
        with self.engine.begin() as conn:
            conn.execute(insert(agents).values(**self._agent_values(a), created_at=now, updated_at=now))
            if not conn.execute(select(agent_state.c.agent_id).where(agent_state.c.agent_id == a["agent_id"])).first():
                conn.execute(insert(agent_state).values(agent_id=a["agent_id"], frozen=False))

    def update_agent(self, a: dict) -> None:
        values = self._agent_values(a)
        values.pop("agent_id")
        with self.engine.begin() as conn:
            conn.execute(update(agents).where(agents.c.agent_id == a["agent_id"]).values(**values, updated_at=utcnow()))

    def create_item(self, i: dict) -> None:
        now = utcnow()
        with self.engine.begin() as conn:
            conn.execute(insert(catalog_items).values(**self._item_values(i), created_at=now, updated_at=now))

    def update_item(self, i: dict) -> None:
        values = self._item_values(i)
        values.pop("tool")
        with self.engine.begin() as conn:
            conn.execute(update(catalog_items).where(catalog_items.c.tool == i["tool"])
                         .values(**values, updated_at=utcnow()))

    # ---- change history ------------------------------------------------------------------------------------
    def add_audit(self, *, actor: str, action: str, target: str | None, details: dict | None = None) -> None:
        with self.engine.begin() as conn:
            conn.execute(insert(audit_log).values(id=new_id(), created_at=utcnow(), actor=actor, action=action,
                                                  target=target, details=json.dumps(details or {}, default=str)))

    def list_audit(self, limit: int = 100) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(audit_log).order_by(audit_log.c.created_at.desc()).limit(limit)).mappings().all()
        return [{**dict(r), "details": json.loads(r["details"] or "{}")} for r in rows]

    # ---- demo reset ------------------------------------------------------------------------------------------
    def reset_demo(self, seed: dict) -> None:
        """Clear purchases and approvals, put the starting rules back, release every kill switch.
        Sign-ups and the change history are kept."""
        with self.engine.begin() as conn:
            for table in (events, approvals, agents, catalog_items, agent_state):
                conn.execute(delete(table))
            self._insert_seed(conn, seed)

    # ---- reads ---------------------------------------------------------------
    def frozen_map(self) -> dict[str, bool]:
        with self.engine.connect() as conn:
            return {r.agent_id: bool(r.frozen) for r in conn.execute(select(agent_state))}

    def spent(self, agent_id: str, *, task_id: str | None = None, since: datetime | None = None) -> Decimal:
        with self.engine.connect() as conn:
            return AgentTx(conn, agent_id).spent(task_id=task_id, since=since)

    def current_task(self, agent_id: str) -> tuple[str, Decimal] | None:
        """The task that most recently spent money, with its total."""
        with self.engine.connect() as conn:
            task_id = conn.execute(
                select(events.c.task_id)
                .where(events.c.agent_id == agent_id, events.c.status.in_(COUNTED))
                .order_by(events.c.created_at.desc()).limit(1)).scalar()
            if task_id is None:
                return None
            return task_id, AgentTx(conn, agent_id).spent(task_id=task_id)

    def pending_approvals(self) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(approvals).where(approvals.c.status == "pending")
                                .order_by(approvals.c.created_at)).mappings().all()
        return [dict(r) for r in rows]

    def get_approval(self, approval_id: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(approvals).where(approvals.c.id == approval_id)).mappings().first()
        return dict(row) if row else None

    def recent_events(self, limit: int = 60) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(events).order_by(events.c.created_at.desc()).limit(limit)).mappings().all()
        return [dict(r) for r in rows]

    def is_frozen(self, agent_id: str) -> bool:
        return self.frozen_map().get(agent_id, False)

    # ---- early access ---------------------------------------------------------
    def add_early_access(self, *, email: str, role: str, use_case: str | None) -> bool:
        """Returns True if this is a new sign-up. Repeats are ignored (no way to probe who signed up)."""
        now = utcnow()
        try:
            with self.engine.begin() as conn:
                conn.execute(insert(early_access).values(email=email, created_at=now, role=role,
                                                         use_case=use_case, consent_at=now))
            return True
        except IntegrityError:
            return False

    def early_access_count(self) -> int:
        with self.engine.connect() as conn:
            return int(conn.execute(select(func.count()).select_from(early_access)).scalar_one())

    def list_early_access(self) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(early_access).order_by(early_access.c.created_at.desc())).mappings().all()
        return [dict(r) for r in rows]

    def delete_early_access(self, email: str) -> bool:
        with self.engine.begin() as conn:
            return conn.execute(delete(early_access).where(early_access.c.email == email)).rowcount == 1

    def export_csv(self) -> str:
        """Paid purchases as a plain CSV: comma-separated, decimal point, one row per payment."""
        with self.engine.connect() as conn:
            rows = conn.execute(select(events).where(events.c.status == "settled")
                                .order_by(events.c.created_at)).mappings().all()
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["Date (UTC)", "Agent", "Task", "Item", "Seller", "Amount", "Currency", "Reference",
                    "Solana receipt"])
        for r in rows:
            created = r["created_at"] if r["created_at"].tzinfo else r["created_at"].replace(tzinfo=timezone.utc)
            w.writerow([created.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), r["agent_id"], r["task_id"],
                        r["tool"] or "", r["vendor"] or "", money(r["amount_micros"]), "USDC", f"AB-{r['id']}",
                        r["tx"] or ""])
        return buf.getvalue()