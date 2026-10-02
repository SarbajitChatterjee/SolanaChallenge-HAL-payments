''' 
Dashboard endpoints: operator token required, or open when PUBLIC_DEMO=true (sandbox judging).
'''

from __future__ import annotations

import asyncio
import csv
import io
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from ..db import iso
from ..ratelimit import limit
from ..schemas import DemoView, EarlyAccessView, PlaygroundIn, StateView
from ..security import actor_of, require_operator, require_operator_token
from ..service import CallRequest

router = APIRouter(prefix="/v1", tags=["operator"], dependencies=[Depends(require_operator)])


def _known_agent(request: Request, agent_id: str) -> None:
    if agent_id not in request.app.state.service.catalog.agents:
        raise HTTPException(404, f"Unknown agent '{agent_id}'.")


def _demo_view(request: Request, started: bool | None = None) -> DemoView:
    st = request.app.state.demo.status
    return DemoView(running=st.running, finished=st.finished, mode=st.mode, started=started, step_key=st.step_key,
                    step_index=st.step_index, step_total=st.step_total, waiting_for=st.waiting_for,
                    approval_id=st.approval_id, task_id=st.task_id, error=st.error, log=st.log[-50:])


# ---- live state and decisions ---------------------------------------------------
@router.get("/state", response_model=StateView)
async def state(request: Request):
    return await request.app.state.service.state()


@router.post("/approvals/{approval_id}/approve")
async def approve(approval_id: str, request: Request):
    if not await asyncio.to_thread(request.app.state.repo.decide_approval, approval_id, True):
        raise HTTPException(409, "This purchase was already decided.")
    return {"id": approval_id, "status": "approved"}


@router.post("/approvals/{approval_id}/deny")
async def deny(approval_id: str, request: Request):
    if not await asyncio.to_thread(request.app.state.repo.decide_approval, approval_id, False):
        raise HTTPException(409, "This purchase was already decided.")
    return {"id": approval_id, "status": "denied"}


@router.post("/agents/{agent_id}/freeze")
async def freeze(agent_id: str, request: Request):
    _known_agent(request, agent_id)
    await asyncio.to_thread(request.app.state.repo.set_frozen, agent_id, True)
    return {"agent_id": agent_id, "frozen": True}


@router.post("/agents/{agent_id}/unfreeze")
async def unfreeze(agent_id: str, request: Request):
    _known_agent(request, agent_id)
    await asyncio.to_thread(request.app.state.repo.set_frozen, agent_id, False)
    return {"agent_id": agent_id, "frozen": False}


@router.get("/ledger.csv", response_class=PlainTextResponse)
async def ledger_csv(request: Request):
    text = await asyncio.to_thread(request.app.state.repo.export_csv)
    return PlainTextResponse(text, media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": 'attachment; filename="agentbudget-ledger.csv"'})


# ---- guided tour / demo -----------------------------------------------------------
@router.post("/demo/run", response_model=DemoView)
async def run_demo(request: Request, mode: Literal["tour", "auto"] = "tour", auto_approve: bool = False):
    s = request.app.state.settings
    if not s.demo_enabled:
        raise HTTPException(403, "The demo is switched off on this server.")
    repo = request.app.state.repo

    async def is_frozen(agent_id: str) -> bool:
        return await asyncio.to_thread(repo.is_frozen, agent_id)

    async def unfreeze_agent(agent_id: str) -> None:
        if await is_frozen(agent_id):
            await asyncio.to_thread(repo.set_frozen, agent_id, False)

    if not request.app.state.demo.running and not request.app.state.rules.demo_rules_intact():
        raise HTTPException(409, "The demo rules were changed. Press Reset demo first, then start the tour.")
    keys = {a: s.agent_key_for(a) for a in ("research-agent", "intern-agent")}
    started = request.app.state.demo.start(
        request.app, keys, s.operator_token.get_secret_value() if s.operator_token else None,
        mode=mode, auto_approve=auto_approve, is_frozen=is_frozen, unfreeze=unfreeze_agent,
        before=request.app.state.topup)
    return _demo_view(request, started)


@router.post("/demo/reset")
async def demo_reset(request: Request):
    """Demo only: clear purchases and approvals, restore the starting rules, release every kill switch,
    top up the test wallets. Sign-ups and the change history are kept."""
    s = request.app.state.settings
    if not s.demo_enabled:
        raise HTTPException(403, "The demo is switched off on this server.")
    request.app.state.demo.stop()
    for _ in range(40):
        if not request.app.state.demo.running:
            break
        await asyncio.sleep(0.05)
    await asyncio.to_thread(request.app.state.rules.reset_demo, actor=actor_of(request))
    await request.app.state.topup()
    return {"ok": True, "message": "Demo reset: purchases cleared, starting rules restored, "
                                   "all agents running, test wallets topped up."}


@router.post("/demo/next", response_model=DemoView)
async def demo_next(request: Request):
    if not request.app.state.demo.next():
        raise HTTPException(409, "The tour isn't waiting for Next right now.")
    await asyncio.sleep(0)  # let the step start before answering
    return _demo_view(request)


@router.post("/demo/stop", response_model=DemoView)
async def demo_stop(request: Request):
    request.app.state.demo.stop()
    for _ in range(40):  # give the runner up to 2 s to clean up
        if not request.app.state.demo.running:
            break
        await asyncio.sleep(0.05)
    return _demo_view(request)


@router.get("/demo", response_model=DemoView)
async def demo_status(request: Request):
    return _demo_view(request)


# ---- playground: the visitor plays the agent -----------------------------------------
@router.post("/playground/buy", dependencies=[Depends(limit("playground", 30, 60))])
async def playground_buy(body: PlaygroundIn, request: Request) -> JSONResponse:
    """Try a purchase as one of the demo agents. Same rules, same payments as a real agent call."""
    _known_agent(request, body.agent_id)
    outcome = await request.app.state.service.call(
        body.agent_id, CallRequest(task_id=body.task_id, tool=body.tool, url=body.url, approval_id=body.approval_id))
    return JSONResponse(status_code=outcome.http_status, content=outcome.body)


# ---- early access (operator side) -------------------------------------------------------
@router.get("/early-access", response_model=list[EarlyAccessView])
async def early_access_list(request: Request):
    rows = await asyncio.to_thread(request.app.state.repo.list_early_access)
    return [EarlyAccessView(email=r["email"], created_at=iso(r["created_at"]), role=r["role"],
                            use_case=r["use_case"]) for r in rows]


@router.get("/early-access.csv", response_class=PlainTextResponse)
async def early_access_csv(request: Request):
    rows = await asyncio.to_thread(request.app.state.repo.list_early_access)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow(["email", "signed_up", "role", "use_case"])
    for r in rows:
        w.writerow([r["email"], iso(r["created_at"]), r["role"], r["use_case"] or ""])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": 'attachment; filename="early-access.csv"'})


@router.delete("/early-access/{email}")
async def early_access_delete(email: str, request: Request):
    """Delete a sign-up on request (GDPR)."""
    if not await asyncio.to_thread(request.app.state.repo.delete_early_access, email.strip().lower()):
        raise HTTPException(404, "No sign-up with that email.")
    return {"deleted": True}


# ---- connecting a real agent in the sandbox ---------------------------------------------------
key_router = APIRouter(prefix="/v1", tags=["operator"])


@key_router.get("/agents/{agent_id}/key", dependencies=[Depends(require_operator_token)])
async def agent_key(agent_id: str, request: Request):
    """Show an agent's key and wallet address, so you can connect a real agent (operator token only)."""
    s = request.app.state.settings
    _known_agent(request, agent_id)
    rail = request.app.state.rail
    return {"agent_id": agent_id, "agent_key": s.agent_key_for(agent_id),
            "wallet_address": request.app.state.service._wallet_address(agent_id) if rail.name == "paykit" else None}