"""The scripted demo, in two modes.

- tour: the visitor drives it. Each step starts when they press Next (POST /v1/demo/next).
        They approve the credit report themselves and flip the kill switch themselves.
- auto: runs straight through (for videos and the CLI). Approval waits up to 2 minutes, or auto-approves.

The script calls the API through its own HTTP stack (auth included), exactly like a real agent would.
CLI:  python -m app.demo --base-url https://<api> [--auto-approve]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Literal

import httpx

from .tour import STEPS

AGENT = "research-agent"
INTERN = "intern-agent"
NEXT_TIMEOUT_S = 20 * 60        # tour gives up after 20 minutes without a click
HUMAN_TIMEOUT_TOUR_S = 10 * 60
HUMAN_TIMEOUT_AUTO_S = 120
LOOP_MAX_CALLS = 40             # the breaker stops the loop at 31 attempts in a minute


class DemoStopped(Exception):
    pass


@dataclass
class DemoStatus:
    running: bool = False
    finished: bool = False
    mode: Literal["tour", "auto"] = "auto"
    step_key: str | None = None
    step_index: int = 0
    step_total: int = len(STEPS)
    waiting_for: Literal["next", "approval", "kill_switch_on", "kill_switch_off"] | None = None
    approval_id: str | None = None
    task_id: str | None = None
    started_at: float | None = None
    error: str | None = None
    log: list[str] = field(default_factory=list)


class Controls:
    """What the script needs besides HTTP: waiting for the visitor and reading the kill switch."""

    def __init__(self, status: DemoStatus, is_frozen: Callable[[str], Awaitable[bool]] | None = None) -> None:
        self.status = status
        self.is_frozen = is_frozen
        self.advance = asyncio.Event()
        self.stopped = False

    async def wait_for_next(self) -> None:
        if self.status.mode != "tour":
            return
        self.status.waiting_for = "next"
        try:
            await asyncio.wait_for(self.advance.wait(), NEXT_TIMEOUT_S)
        except asyncio.TimeoutError as exc:
            raise DemoStopped("The tour ended after 20 minutes without a click.") from exc
        finally:
            self.advance.clear()
            self.status.waiting_for = None
        if self.stopped:
            raise DemoStopped("Tour stopped.")

    async def wait_for_switch(self, want_frozen: bool, timeout_s: int) -> bool:
        self.status.waiting_for = "kill_switch_on" if want_frozen else "kill_switch_off"
        deadline = time.monotonic() + timeout_s
        try:
            while time.monotonic() < deadline:
                if self.stopped:
                    raise DemoStopped("Tour stopped.")
                if self.is_frozen and await self.is_frozen(AGENT) == want_frozen:
                    return True
                await asyncio.sleep(0.5)
            return False
        finally:
            self.status.waiting_for = None


async def run_scenario(http: httpx.AsyncClient, agent_keys: dict[str, str], controls: Controls, *,
                       operator_headers: dict[str, str] | None = None, auto_approve: bool = False) -> None:
    status = controls.status
    tour = status.mode == "tour"
    op = operator_headers or {}
    task = f"supplier-check-{uuid.uuid4().hex[:4]}"
    status.task_id = task

    def key(agent: str) -> dict[str, str]:
        k = agent_keys.get(agent)
        return {"Authorization": f"Bearer {k}"} if k else {}

    async def buy(agent: str = AGENT, task_id: str = task, log: bool = True, **body) -> dict:
        r = await http.post(f"/v1/agents/{agent}/call", json={"task_id": task_id, **body}, headers=key(agent))
        out = r.json()
        if r.status_code == 202 and "approval_id" not in body:
            approval_id = out["approval_id"]
            status.approval_id = approval_id
            status.waiting_for = "approval"
            status.log.append(f"Waiting for you: {out['reason']}")
            if auto_approve:
                await http.post(f"/v1/approvals/{approval_id}/approve", headers=op)
            deadline = time.monotonic() + (HUMAN_TIMEOUT_TOUR_S if tour else HUMAN_TIMEOUT_AUTO_S)
            try:
                while time.monotonic() < deadline:
                    if controls.stopped:
                        raise DemoStopped("Tour stopped.")
                    r = await http.post(f"/v1/agents/{agent}/call",
                                        json={"task_id": task_id, **body, "approval_id": approval_id},
                                        headers=key(agent))
                    if r.status_code != 202:
                        out = r.json()
                        break
                    await asyncio.sleep(1)
                else:
                    status.log.append("Nobody decided in time, so the agent moved on without it.")
                    return out
            finally:
                status.waiting_for = None
                status.approval_id = None
        if log:
            status.log.append(out.get("reason") or out.get("detail") or "")
        return out

    async def switch_back_on() -> None:
        """The visitor (tour) or the script (auto) switches the agent back on."""
        if tour:
            if not await controls.wait_for_switch(False, HUMAN_TIMEOUT_TOUR_S):
                await http.post(f"/v1/agents/{AGENT}/unfreeze", headers=op)
                status.log.append("No switch was flipped, so the tour switched the agent back on for you.")
        else:
            await http.post(f"/v1/agents/{AGENT}/unfreeze", headers=op)

    news: dict = {}
    for index, step in enumerate(STEPS, start=1):
        status.step_key, status.step_index = step.key, index
        await controls.wait_for_next()

        if step.key == "everyday":
            await buy(tool="company_lookup", params={"name": "Duping Bahn GmbH"})
            await buy(tool="fx_rate", params={"pair": "EURUSD"})
            news = await buy(tool="news_search", params={"q": "Duping Bahn"})

        elif step.key == "trap":

            # The firewall removed the instruction, but flagged the link. The agent tries it anyway.
            flagged = [f["extract"] for f in news.get("content_flags", []) if f.get("kind") == "unlisted_link"]
            items = news.get("data", {}).get("items", []) if isinstance(news.get("data"), dict) else []
            injected = " ".join(flagged + [i.get("body") or "" for i in items])
            found = re.search(r"https?://\S+/shady/full-dossier", injected)
            await buy(url=found.group(0) if found else "https://dossier-deals.example/full-dossier")

        elif step.key == "approval":
            await buy(tool="credit_report", params={"name": "Duping Bahn GmbH"})

        elif step.key == "overcharge":
            await buy(tool="fx_realtime", params={"pair": "EURUSD"})

        elif step.key == "loop":

            # The loop needs a running agent. If the visitor stopped it early, switch it back on first.
            if controls.is_frozen and await controls.is_frozen(AGENT):
                await http.post(f"/v1/agents/{AGENT}/unfreeze", headers=op)
                status.log.append("research-agent was stopped, so the tour switched it back on before the loop.")

            # A new task on every restart, the same exchange rate each time (News Wire is under review now).
            paid = reused = 0
            stopped = False
            for attempt in range(1, LOOP_MAX_CALLS + 1):
                out = await buy(task_id=f"{task}-restart-{attempt}", tool="fx_rate", params={"pair": "EURCHF"},
                                log=False)
                code = out.get("reason_code")
                paid += code == "paid"
                reused += code == "reused"
                if code in ("circuit_breaker", "frozen"):
                    stopped = True
                    status.log.append(f"Paid {paid} time{'s' if paid != 1 else ''}. Reused {reused} times, "
                                      f"for free. {out.get('reason')}")
                    break
            if stopped:
                await switch_back_on()

        elif step.key == "permissions":
            await buy(agent=INTERN, tool="credit_report")

        elif step.key == "kill_switch":
            if tour:
                if not await controls.wait_for_switch(True, HUMAN_TIMEOUT_TOUR_S):
                    await http.post(f"/v1/agents/{AGENT}/freeze", headers=op)
                    status.log.append("No switch was flipped, so the tour flipped it for you.")
            else:
                await http.post(f"/v1/agents/{AGENT}/freeze", headers=op)
            await buy(task_id=f"{task}-after-stop", tool="fx_rate")
            await switch_back_on()

        elif step.key == "ledger":
            status.log.append("Every purchase is in the ledger: paid ones with their Solana receipt, "
                              "reused ones at 0.00 with the purchase they reused.")


class DemoRunner:
    """One demo at a time, in the background of the API process (the demo assumes a single instance)."""

    def __init__(self) -> None:
        self.status = DemoStatus()
        self.controls: Controls | None = None
        self._task: asyncio.Task | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self, app, agent_keys: dict[str, str], operator_token: str | None, *, mode: str,
              auto_approve: bool, is_frozen, unfreeze, before=None) -> bool:
        if self.running:
            return False
        self.status = DemoStatus(running=True, mode=mode, started_at=time.time())
        self.controls = controls = Controls(self.status, is_frozen)

        async def _run() -> None:
            try:
                if before is not None:
                    await before()
                await unfreeze(AGENT)  # every run starts from a clean switch
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://agentbudget.internal",
                                             timeout=90) as http:
                    op = {"Authorization": f"Bearer {operator_token}"} if operator_token else {}
                    await run_scenario(http, agent_keys, controls, operator_headers=op, auto_approve=auto_approve)
                self.status.finished = True
            except DemoStopped as exc:
                self.status.error = str(exc) if str(exc) != "Tour stopped." else None
                await unfreeze(AGENT)
            except Exception as exc:  # noqa: BLE001 - surfaced to the app via /v1/demo
                self.status.error = f"The demo hit a problem: {type(exc).__name__}: {exc}"
                await unfreeze(AGENT)
            finally:
                self.status.running = False
                self.status.waiting_for = None

        self._task = asyncio.create_task(_run())
        return True

    def next(self) -> bool:
        if not self.running or self.controls is None or self.status.waiting_for != "next":
            return False
        self.controls.advance.set()
        return True

    def stop(self) -> bool:
        if not self.running or self.controls is None:
            return False
        self.controls.stopped = True
        self.controls.advance.set()
        return True


def _cli() -> None:
    from .settings import Settings

    parser = argparse.ArgumentParser(description="Run the AgentBudget demo against a running API.")
    parser.add_argument("--base-url", default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--auto-approve", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    keys = {a: settings.agent_key_for(a) for a in (AGENT, INTERN)}
    op_token = settings.operator_token.get_secret_value() if settings.operator_token else None

    async def main() -> None:
        status = DemoStatus(running=True, mode="auto")
        async with httpx.AsyncClient(base_url=args.base_url, timeout=90) as http:
            await run_scenario(http, keys, Controls(status),
                               operator_headers={"Authorization": f"Bearer {op_token}"} if op_token else {},
                               auto_approve=args.auto_approve)
        print(f"Task {status.task_id}")
        print("\n".join(f"  {line}" for line in status.log))

    asyncio.run(main())


if __name__ == "__main__":
    _cli()