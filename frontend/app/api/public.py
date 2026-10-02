"""Public endpoints: no token needed. Nothing here exposes secrets, keys or other people's data."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request

from ..ratelimit import limit
from ..schemas import CatalogView, EarlyAccessIn, StepView
from ..tour import steps_payload

router = APIRouter(prefix="/v1", tags=["public"])


@router.get("/catalog", response_model=CatalogView)
async def catalog(request: Request):
    """What agents can buy, at which agreed price, and each agent's rules."""
    return request.app.state.service.public_catalog()


@router.get("/demo/steps", response_model=list[StepView])
async def demo_steps():
    """The guided tour's steps, in plain words."""
    return steps_payload()


@router.post("/early-access", dependencies=[Depends(limit("early-access", 5, 600))])
async def early_access(body: EarlyAccessIn, request: Request):
    """Sign up for early access. Always answers the same way, so nobody can test who is on the list."""
    if not body.website:  # honeypot empty -> a person, not a bot
        await asyncio.to_thread(request.app.state.repo.add_early_access, email=body.email, role=body.role,
                                use_case=(body.use_case or "").strip() or None)
    return {"ok": True, "message": "Thanks! We'll get in touch within a few days."}


@router.get("/early-access/count")
async def early_access_count(request: Request):
    return {"count": await asyncio.to_thread(request.app.state.repo.early_access_count)}
