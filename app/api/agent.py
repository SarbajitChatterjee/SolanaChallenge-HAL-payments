"""Agent-facing endpoint: an agent asks to buy; the answer is paid (200), held (202) or blocked (403)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from ..schemas import CallIn
from ..security import require_agent
from ..service import CallRequest

router = APIRouter(prefix="/v1/agents", tags=["agents"])


@router.post("/{agent_id}/call", dependencies=[Depends(require_agent)],
             responses={202: {"description": "Held for human approval"}, 403: {"description": "Blocked"}})
async def call(agent_id: str, body: CallIn, request: Request) -> JSONResponse:
    service = request.app.state.service
    if agent_id not in service.catalog.agents:
        raise HTTPException(404, f"Unknown agent '{agent_id}'.")
    outcome = await service.call(agent_id, CallRequest(**body.model_dump()))
    return JSONResponse(status_code=outcome.http_status, content=outcome.body)
