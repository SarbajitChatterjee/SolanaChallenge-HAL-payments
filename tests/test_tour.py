"""Guided tour, playground and early access."""

import time

from tests.conftest import OP_H

NEWS_SELLER = "http://127.0.0.1:8002"   # News Wire on its own service, as on Render


def wait_until(api, predicate, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        demo = api.get("/v1/demo", headers=OP_H).json()
        if predicate(demo):
            return demo
        time.sleep(0.1)
    raise AssertionError(f"timed out, last demo state: {demo}")


def statuses(api):
    return [e["status"] for e in api.get("/v1/state", headers=OP_H).json()["events"]]


def test_steps_are_public_and_plain(api):
    steps = api.get("/v1/demo/steps").json()
    assert [s["key"] for s in steps] == ["everyday", "trap", "approval", "overcharge", "loop", "permissions",
                                         "kill_switch", "ledger"]
    assert all(s["title"] and s["what_happens"] and s["why_it_matters"] for s in steps)
    assert steps[2]["your_turn"] and steps[6]["focus"] == "breaker"


def test_catalog_is_public_and_has_no_urls(api):
    body = api.get("/v1/catalog").json()
    assert {i["tool"] for i in body["items"]} >= {"company_lookup", "credit_report"}
    assert all("url" not in i for i in body["items"])
    assert body["agents"][0]["description"]


def test_tour_is_driven_by_the_visitor(make_client):
    with make_client(news_vendor_base=NEWS_SELLER) as api:
        _visitor_tour(api)


def _visitor_tour(api):
    assert api.post("/v1/demo/run?mode=tour", headers=OP_H).json()["started"] is True
    wait_until(api, lambda d: d["waiting_for"] == "next" and d["step_key"] == "everyday")
    assert statuses(api) == []                                    # nothing happens before Next

    api.post("/v1/demo/next", headers=OP_H)
    wait_until(api, lambda d: d["waiting_for"] == "next" and d["step_key"] == "trap")
    assert statuses(api).count("settled") == 3

    api.post("/v1/demo/next", headers=OP_H)                       # trap
    wait_until(api, lambda d: d["waiting_for"] == "next" and d["step_key"] == "approval")
    api.post("/v1/demo/next", headers=OP_H)                       # approval: the visitor decides
    demo = wait_until(api, lambda d: d["waiting_for"] == "approval")
    assert api.post(f"/v1/approvals/{demo['approval_id']}/approve", headers=OP_H).status_code == 200
    wait_until(api, lambda d: d["waiting_for"] == "next" and d["step_key"] == "overcharge")

    api.post("/v1/demo/next", headers=OP_H)                       # overcharge
    wait_until(api, lambda d: d["waiting_for"] == "next" and d["step_key"] == "loop")
    api.post("/v1/demo/next", headers=OP_H)                       # loop: the breaker stops the agent
    wait_until(api, lambda d: d["waiting_for"] == "kill_switch_off" and d["step_key"] == "loop")
    api.post("/v1/agents/research-agent/unfreeze", headers=OP_H)  # the visitor switches it back on
    wait_until(api, lambda d: d["waiting_for"] == "next" and d["step_key"] == "permissions")
    api.post("/v1/demo/next", headers=OP_H)                       # permissions
    wait_until(api, lambda d: d["waiting_for"] == "next" and d["step_key"] == "kill_switch")

    api.post("/v1/demo/next", headers=OP_H)                       # kill switch: the visitor flips it
    wait_until(api, lambda d: d["waiting_for"] == "kill_switch_on")
    api.post("/v1/agents/research-agent/freeze", headers=OP_H)
    wait_until(api, lambda d: d["waiting_for"] == "kill_switch_off")
    api.post("/v1/agents/research-agent/unfreeze", headers=OP_H)
    wait_until(api, lambda d: d["waiting_for"] == "next" and d["step_key"] == "ledger")

    api.post("/v1/demo/next", headers=OP_H)
    demo = wait_until(api, lambda d: not d["running"])
    assert demo["finished"] and demo["error"] is None
    events = api.get("/v1/state", headers=OP_H).json()["events"]
    codes = [e["reason_code"] for e in events]
    for code in ("paid", "not_in_catalog", "price_too_high", "reused", "circuit_breaker", "not_allowed", "frozen"):
        assert code in codes, code
    assert "seller_under_review" not in codes                       # the loop buys from FX Feed, not News Wire


def test_next_only_when_waiting_and_stop_cleans_up(api):
    assert api.post("/v1/demo/next", headers=OP_H).status_code == 409
    api.post("/v1/demo/run?mode=tour", headers=OP_H)
    wait_until(api, lambda d: d["waiting_for"] == "next")
    assert api.post("/v1/demo/run?mode=tour", headers=OP_H).json()["started"] is False  # one at a time
    demo = api.post("/v1/demo/stop", headers=OP_H).json()
    assert demo["running"] is False and demo["error"] is None


def test_auto_mode_runs_through(make_client):
    with make_client(news_vendor_base=NEWS_SELLER) as api:
        api.post("/v1/demo/run?mode=auto&auto_approve=true", headers=OP_H)
        demo = wait_until(api, lambda d: not d["running"], timeout=30)
        assert demo["finished"], demo
        events = list(reversed(api.get("/v1/state", headers=OP_H).json()["events"]))
        codes = [e["reason_code"] for e in events]

        # Step 2: the blocked dossier link is traced to News Wire, which goes under review.
        trap = next(e for e in events if e["reason_code"] == "not_in_catalog")
        assert "came from News Wire (demo)" in trap["reason"] and "is now under review" in trap["reason"]
        sellers = {s["seller_origin"]: s["status"] for s in api.get("/v1/sellers", headers=OP_H).json()}
        assert sellers[NEWS_SELLER] == "under_review"

        # Step 4: the quoted price and the agreed price, side by side.
        assert any(e["reason"] == "FX Feed (demo) asked 0.10 USD. The agreed price is 0.01 USD, so nothing was paid."
                   for e in events)

        # Step 5: the loop pays once, reuses the rest, then the breaker stops it. Nothing waits for a person.
        loop = [e for e in events if "-restart-" in (e["task_id"] or "")]
        loop_codes = [e["reason_code"] for e in loop]
        assert loop_codes[0] == "paid" and loop_codes[-1] == "circuit_breaker"
        assert set(loop_codes[1:-1]) == {"reused"} and "needs_approval" not in codes
        assert any(line.startswith("Paid 1 time. Reused ") for line in demo["log"])

        # Step 7: the manual kill switch still works after the automatic stop.
        assert "frozen" in codes and "kill_switch_on" in codes
        assert not next(a for a in api.get("/v1/state", headers=OP_H).json()["agents"]
                        if a["agent_id"] == "research-agent")["frozen"]


def test_playground(api):
    ok = api.post("/v1/playground/buy", headers=OP_H, json={"agent_id": "research-agent", "tool": "fx_rate"})
    assert ok.status_code == 200 and ok.json()["reason_code"] == "paid"
    trap = api.post("/v1/playground/buy", headers=OP_H,
                    json={"agent_id": "research-agent", "url": "https://dossier-deals.example/full-dossier"})
    assert trap.status_code == 403 and trap.json()["reason_code"] == "not_in_catalog"
    held = api.post("/v1/playground/buy", headers=OP_H, json={"agent_id": "research-agent", "tool": "credit_report"})
    assert held.status_code == 202 and held.json()["reason_code"] == "needs_approval"
    assert api.post("/v1/playground/buy", json={"agent_id": "research-agent", "tool": "fx_rate"}).status_code == 401


def test_early_access(api):
    body = {"email": " Anna@Example.de ", "role": "builder", "use_case": "Our agent buys company data", "consent": True}
    assert api.post("/v1/early-access", json=body).status_code == 200
    assert api.post("/v1/early-access", json=body).status_code == 200         # repeat: same answer, one row
    assert api.post("/v1/early-access", json={**body, "email": "bot@spam.io", "website": "x"}).status_code == 200
    assert api.get("/v1/early-access/count").json() == {"count": 1}           # bot and repeat not stored
    assert api.post("/v1/early-access", json={**body, "email": "nope"}).status_code == 422
    assert api.post("/v1/early-access", json={**body, "consent": False}).status_code == 422
    assert api.get("/v1/early-access").status_code == 401                     # list needs the operator
    rows = api.get("/v1/early-access", headers=OP_H).json()
    assert rows[0]["email"] == "anna@example.de" and rows[0]["role"] == "builder"
    assert api.delete("/v1/early-access/anna@example.de", headers=OP_H).json() == {"deleted": True}
    assert api.get("/v1/early-access/count").json() == {"count": 0}


def test_early_access_rate_limit(api):
    codes = [api.post("/v1/early-access", json={"email": f"p{i}@example.de", "role": "curious", "consent": True})
             .status_code for i in range(7)]
    assert codes[:5] == [200] * 5 and codes[5:] == [429, 429]