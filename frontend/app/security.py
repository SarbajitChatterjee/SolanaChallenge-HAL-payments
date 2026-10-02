"""Two kinds of callers, two credentials:
- agents call /v1/agents/{agent_id}/call with their own key (an agent can only spend as itself)
- the operator dashboard calls everything else with the operator token
Both are bearer tokens compared in constant time.
"""

from __future__ import annotations

import hmac

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)


def _matches(given: str | None, expected: str | None) -> bool:
    return bool(given and expected) and hmac.compare_digest(given.encode(), expected.encode())


def require_agent(agent_id: str, request: Request,
                  creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
    settings = request.app.state.settings
    if not _matches(creds.credentials if creds else None, settings.agent_key_for(agent_id)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing agent key.",
                            headers={"WWW-Authenticate": "Bearer"})


def require_operator(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
    settings = request.app.state.settings
    if settings.public_demo:
        return
    token = settings.operator_token.get_secret_value() if settings.operator_token else None
    if not _matches(creds.credentials if creds else None, token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing operator token.",
                            headers={"WWW-Authenticate": "Bearer"})


def require_operator_token(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
    """The real operator token, always. PUBLIC_DEMO does not open this (used to reveal agent keys)."""
    settings = request.app.state.settings
    token = settings.operator_token.get_secret_value() if settings.operator_token else None
    if not _matches(creds.credentials if creds else None, token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "This needs the operator token (PUBLIC_DEMO doesn't open it).",
                            headers={"WWW-Authenticate": "Bearer"})


def actor_of(request: Request) -> str:
    """'operator' when the real operator token was sent, otherwise 'demo visitor' (PUBLIC_DEMO)."""
    settings = request.app.state.settings
    token = settings.operator_token.get_secret_value() if settings.operator_token else None
    header = request.headers.get("authorization", "")
    given = header[7:] if header.lower().startswith("bearer ") else None
    return "operator" if _matches(given, token) else "demo visitor"