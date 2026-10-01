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
    keys = settings.agent_key_map
    if not keys and settings.app_env == "dev":
        return  # local dev without keys configured
    if not _matches(creds.credentials if creds else None, keys.get(agent_id)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing agent key.",
                            headers={"WWW-Authenticate": "Bearer"})


def require_operator(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
    settings = request.app.state.settings
    if settings.public_demo:
        return
    token = settings.operator_token.get_secret_value() if settings.operator_token else None
    if token is None and settings.app_env == "dev":
        return
    if not _matches(creds.credentials if creds else None, token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing operator token.",
                            headers={"WWW-Authenticate": "Bearer"})
