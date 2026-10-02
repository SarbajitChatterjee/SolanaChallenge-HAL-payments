"""
Rules endpoints for the dashboard: view and edit agents and items, read the change history.
Same access as the other dashboard endpoints (operator token, or open with PUBLIC_DEMO).

"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..db import iso
from ..rules import RuleError
from ..security import actor_of, require_operator

router = APIRouter(prefix="/v1/rules", tags=["rules"], dependencies=[Depends(require_operator)])


class AgentIn(BaseModel):
    agent_id: str = Field(max_length=64)
    description: str | None = Field(default=None, max_length=200)
    allowed_tools: list[str]
    per_task_cap: str
    daily_cap: str
    approval_above: str


class AgentPatch(BaseModel):
    description: str | None = Field(default=None, max_length=200)
    allowed_tools: list[str] | None = None
    per_task_cap: str | None = None
    daily_cap: str | None = None
    approval_above: str | None = None
    active: bool | None = None


class ItemIn(BaseModel):
    tool: str = Field(max_length=64)
    name: str = Field(max_length=80)
    vendor: str = Field(max_length=128)
    url: str = Field(max_length=2000)
    price: str
    description: str | None = Field(default=None, max_length=200)


class ItemPatch(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    vendor: str | None = Field(default=None, max_length=128)
    url: str | None = Field(default=None, max_length=2000)
    price: str | None = None
    description: str | None = Field(default=None, max_length=200)
    active: bool | None = None


def _money(v: Any) -> str:
    return f"{Decimal(str(v)):.2f}" if Decimal(str(v)) == Decimal(str(v)).quantize(Decimal("0.01")) else f"{Decimal(str(v)):f}"


def _agent_view(a: dict, request: Request) -> dict:
    return {"agent_id": a["agent_id"], "description": a["description"], "allowed_tools": a["allowed_tools"],
            "per_task_cap": _money(a["per_task_cap"]), "daily_cap": _money(a["daily_cap"]),
            "approval_above": _money(a["approval_above"]), "active": a["active"],
            "frozen": request.app.state.repo.is_frozen(a["agent_id"]),
            "created_at": iso(a["created_at"]), "updated_at": iso(a["updated_at"])}


def _item_view(i: dict) -> dict:
    return {"tool": i["tool"], "name": i["name"], "description": i["description"], "vendor": i["vendor"],
            "url": i["url"], "price": _money(i["price"]), "active": i["active"],
            "created_at": iso(i["created_at"]), "updated_at": iso(i["updated_at"])}


def _invalid(exc: RuleError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.message, "field": exc.field})


async def _topup(request: Request, agent_id: str) -> None:
    """Test network only: give a new or changed agent its daily budget in test USDC right away."""
    await request.app.state.topup(only=agent_id)


@router.get("")
async def rules(request: Request):
    view = await asyncio.to_thread(request.app.state.rules.admin_view)
    return {"agents": [_agent_view(a, request) for a in view["agents"]],
            "items": [_item_view(i) for i in view["items"]]}


@router.post("/agents", status_code=201)
async def create_agent(body: AgentIn, request: Request):
    s = request.app.state.settings
    try:
        agent = await asyncio.to_thread(request.app.state.rules.create_agent, body.model_dump(),
                                        actor=actor_of(request), has_key=s.agent_key_for)
    except RuleError as exc:
        return _invalid(exc)
    await _topup(request, agent["agent_id"])
    return _agent_view(agent, request)


@router.patch("/agents/{agent_id}")
async def update_agent(agent_id: str, body: AgentPatch, request: Request):
    try:
        agent = await asyncio.to_thread(request.app.state.rules.update_agent, agent_id,
                                        body.model_dump(exclude_none=True), actor=actor_of(request))
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    except RuleError as exc:
        return _invalid(exc)
    if agent["active"]:
        await _topup(request, agent_id)
    return _agent_view(agent, request)


@router.post("/items", status_code=201)
async def create_item(body: ItemIn, request: Request):
    try:
        item = await asyncio.to_thread(request.app.state.rules.create_item, body.model_dump(), actor=actor_of(request))
    except RuleError as exc:
        return _invalid(exc)
    return _item_view(item)


@router.patch("/items/{tool}")
async def update_item(tool: str, body: ItemPatch, request: Request):
    try:
        item = await asyncio.to_thread(request.app.state.rules.update_item, tool,
                                       body.model_dump(exclude_none=True), actor=actor_of(request))
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    except RuleError as exc:
        return _invalid(exc)
    return _item_view(item)


@router.get("/history")
async def history(request: Request, limit: int = 100):
    rows = await asyncio.to_thread(request.app.state.repo.list_audit, max(1, min(limit, 500)))
    return [{"id": r["id"], "created_at": iso(r["created_at"]), "actor": r["actor"], "action": r["action"],
             "target": r["target"], "details": r["details"]} for r in rows]