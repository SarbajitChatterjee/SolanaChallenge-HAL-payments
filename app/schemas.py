"""Request/response models. This is the contract the Lovable frontend codes against (see /docs)."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,253}\.[^@\s]{2,}$")


# ---- agents -------------------------------------------------------------------
class CallIn(BaseModel):
    task_id: str = Field(min_length=1, max_length=64)
    tool: str | None = Field(default=None, max_length=64)
    url: str | None = Field(default=None, max_length=2048)
    params: dict[str, Any] = Field(default_factory=dict)
    approval_id: str | None = Field(default=None, max_length=24)


class PlaygroundIn(BaseModel):
    agent_id: str = Field(max_length=64)
    tool: str | None = Field(default=None, max_length=64)
    url: str | None = Field(default=None, max_length=2048)
    task_id: str = Field(default="playground", min_length=1, max_length=64)
    approval_id: str | None = Field(default=None, max_length=24)


# ---- dashboard ----------------------------------------------------------------
class CurrentTask(BaseModel):
    task_id: str
    spent: str


class AgentView(BaseModel):
    agent_id: str
    description: str
    frozen: bool
    allowed_tools: list[str]
    per_task_cap: str
    daily_cap: str
    approval_above: str
    spent_today: str
    saved_today: str                 # what reused purchases would have cost today
    reused_today: int
    frozen_reason: str | None        # why the agent is stopped: kill switch by hand, or the circuit breaker
    current_task: CurrentTask | None
    wallet_address: str | None
    wallet_usdc: str | None


class ApprovalView(BaseModel):
    id: str
    created_at: str
    agent_id: str
    task_id: str
    tool: str
    item_name: str | None
    vendor: str | None
    amount: str
    reason: str | None
    status: Literal["pending", "approved", "denied", "used"]


class EventView(BaseModel):
    id: str
    created_at: str
    agent_id: str
    task_id: str
    tool: str | None
    item_name: str | None
    url: str | None
    vendor: str | None
    amount: str | None
    decision: Literal["allow", "hold", "deny"]
    status: Literal["reserved", "settled", "reused", "held", "approved", "denied", "blocked", "failed", "control"]
    reason_code: str | None
    reason: str | None
    tx: str | None
    explorer_url: str | None
    caused_by: str | None = None     # blocked link: the paid purchase whose response contained it
    reused_from: str | None = None   # reused purchase: the paid purchase whose result was sent
    content_flags: list[dict] = []   # what the response firewall found in this purchase's data


class SellerView(BaseModel):
    seller_origin: str               # scheme://host, the seller key
    vendors: list[str]               # display names of the items from this origin
    status: Literal["active", "under_review"]
    incidents: int
    updated_at: str | None
    updated_by: str | None           # "HAL" for an automatic review, else the operator


class StateView(BaseModel):
    rail: Literal["mock", "paykit"]
    network: str | None
    agents: list[AgentView]
    approvals: list[ApprovalView]
    events: list[EventView]


# ---- public -------------------------------------------------------------------
class HealthView(BaseModel):
    ok: bool
    version: str
    rail: str
    network: str | None
    database: Literal["postgres", "sqlite"]
    auth_required: bool
    demo_enabled: bool


class CatalogItemView(BaseModel):
    tool: str
    name: str
    description: str
    vendor: str
    price: str


class CatalogAgentView(BaseModel):
    agent_id: str
    description: str
    allowed_tools: list[str]
    per_task_cap: str
    daily_cap: str
    approval_above: str


class CatalogView(BaseModel):
    items: list[CatalogItemView]
    agents: list[CatalogAgentView]


class StepView(BaseModel):
    index: int
    key: str
    title: str
    what_happens: str
    why_it_matters: str
    focus: Literal["agents", "statement", "approvals", "breaker", "ledger"]
    your_turn: str | None


class DemoView(BaseModel):
    running: bool
    finished: bool
    mode: Literal["tour", "auto"]
    started: bool | None = None
    step_key: str | None
    step_index: int
    step_total: int
    waiting_for: Literal["next", "approval", "kill_switch_on", "kill_switch_off"] | None
    approval_id: str | None
    task_id: str | None
    error: str | None
    log: list[str]


class EarlyAccessIn(BaseModel):
    email: str = Field(max_length=254)
    role: Literal["builder", "approver", "vendor", "curious"]
    use_case: str | None = Field(default=None, max_length=500)
    consent: bool
    website: str | None = Field(default=None, max_length=200)  # honeypot: humans leave it empty

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL.match(v):
            raise ValueError("Please enter a valid email address.")
        return v

    @field_validator("consent")
    @classmethod
    def must_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Please agree that we may email you about early access.")
        return v


class EarlyAccessView(BaseModel):
    email: str
    created_at: str
    role: str
    use_case: str | None