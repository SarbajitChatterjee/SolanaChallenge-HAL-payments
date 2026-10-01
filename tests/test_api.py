"""End-to-end through HTTP with the mock rail, on SQLite and (if TEST_POSTGRES_URL is set) Postgres."""

import time
from concurrent.futures import ThreadPoolExecutor

from tests.conftest import AGENT_H, INTERN_H, OP_H


def call(api, headers=AGENT_H, agent="research-agent", task="t1", **body):
    return api.post(f"/v1/agents/{agent}/call", json={"task_id": task, **body}, headers=headers)


def research(api):
    return next(a for a in api.get("/v1/state", headers=OP_H).json()["agents"] if a["agent_id"] == "research-agent")


# ---- auth ----------------------------------------------------------------------
def test_agent_key_required_and_scoped(api):
    assert call(api, headers={}, tool="fx_rate").status_code == 401
    assert call(api, headers=INTERN_H, tool="fx_rate").status_code == 401  # intern key can't spend as research
    assert call(api, tool="fx_rate").status_code == 200


def test_operator_token_required(api):
    assert api.get("/v1/state").status_code == 401
    assert api.post("/v1/agents/research-agent/freeze", headers=AGENT_H).status_code == 401
    assert api.get("/v1/state", headers=OP_H).status_code == 200


def test_public_demo_opens_dashboard_but_not_agent_spending(make_client):
    with make_client(public_demo=True) as api:
        assert api.get("/v1/state").status_code == 200
        assert call(api, headers={}, tool="fx_rate").status_code == 401


def test_health_is_public(api):
    body = api.get("/health").json()
    assert body["ok"] and body["auth_required"] is True and body["rail"] == "mock"


def test_cors_allows_only_configured_origin(make_client):
    with make_client(allowed_origins="https://agentbudget.lovable.app") as api:
        ok = api.options("/v1/state", headers={"Origin": "https://agentbudget.lovable.app",
                                               "Access-Control-Request-Method": "GET"})
        bad = api.options("/v1/state", headers={"Origin": "https://evil.example",
                                                "Access-Control-Request-Method": "GET"})
        assert ok.headers.get("access-control-allow-origin") == "https://agentbudget.lovable.app"
        assert "access-control-allow-origin" not in bad.headers


# ---- spend flow ------------------------------------------------------------------
def test_paid_call_settles_and_counts(api):
    r = call(api, tool="company_lookup")
    assert r.status_code == 200 and r.json()["status"] == "settled" and r.json()["amount"] == "0.05"
    assert r.json()["reason"] == "Paid 0.05 USD to Registry Data (demo)." and r.json()["item_name"] == "Company record"
    assert research(api)["spent_today"] == "0.05"
    assert research(api)["current_task"] == {"task_id": "t1", "spent": "0.05"}


def test_injected_url_blocked(api):
    r = call(api, url="http://127.0.0.1:8001/shady/full-dossier")
    assert r.status_code == 403 and r.json()["reason_code"] == "not_in_catalog"


def test_hold_approve_single_use(api):
    held = call(api, tool="credit_report")
    assert held.status_code == 202
    aid = held.json()["approval_id"]
    assert [a["id"] for a in api.get("/v1/state", headers=OP_H).json()["approvals"]] == [aid]
    assert call(api, tool="credit_report", approval_id=aid).status_code == 202
    assert api.post(f"/v1/approvals/{aid}/approve", headers=OP_H).status_code == 200
    assert call(api, tool="credit_report", approval_id=aid).status_code == 200
    assert call(api, tool="credit_report", approval_id=aid).status_code == 403
    assert api.post(f"/v1/approvals/{aid}/approve", headers=OP_H).status_code == 409


def test_approval_bound_to_tool(api):
    aid = call(api, tool="credit_report").json()["approval_id"]
    api.post(f"/v1/approvals/{aid}/approve", headers=OP_H)
    assert call(api, tool="company_lookup", approval_id=aid).status_code == 409


def test_denied_approval(api):
    aid = call(api, tool="credit_report").json()["approval_id"]
    api.post(f"/v1/approvals/{aid}/deny", headers=OP_H)
    assert call(api, tool="credit_report", approval_id=aid).status_code == 403


def test_price_pinning_releases_budget(api):
    r = call(api, tool="fx_realtime")
    assert r.status_code == 403 and r.json()["reason_code"] == "price_too_high"
    assert r.json()["reason"] == "The seller asked for more than the agreed 0.01 USD, so nothing was paid."
    assert research(api)["spent_today"] == "0.00"


def test_runaway_loop_stops_at_task_cap(api):
    codes = [call(api, tool="news_search").status_code for _ in range(18)]
    assert codes.count(200) == 15 and codes[15:] == [403, 403, 403]


def test_parallel_calls_never_overspend(api):
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda _: call(api, task="race", tool="news_search").status_code, range(24)))
    assert codes.count(200) == 15  # 0.75 cap / 0.05
    assert research(api)["current_task"]["spent"] == "0.75"


def test_kill_switch_and_least_privilege(api):
    api.post("/v1/agents/research-agent/freeze", headers=OP_H)
    assert call(api, tool="fx_rate").status_code == 403
    api.post("/v1/agents/research-agent/unfreeze", headers=OP_H)
    assert call(api, tool="fx_rate").status_code == 200
    r = call(api, headers=INTERN_H, agent="intern-agent", tool="credit_report")
    assert r.status_code == 403 and r.json()["reason_code"] == "not_allowed"


def test_ledger_export(api):
    call(api, tool="company_lookup")
    call(api, url="http://127.0.0.1:8001/shady/full-dossier")
    lines = api.get("/v1/ledger.csv", headers=OP_H).text.strip().splitlines()
    assert lines[0] == "Date (UTC),Agent,Task,Item,Seller,Amount,Currency,Reference,Solana receipt"
    assert len(lines) == 2 and ",research-agent,t1,company_lookup,Registry Data (demo),0.05,USDC,AB-" in lines[1]




def test_cors_regex_covers_lovable_previews(make_client):
    with make_client(allowed_origins="https://agentbudget.lovable.app",
                     allowed_origin_regex=r"https://([a-z0-9-]+\.)*(lovable\.app|lovableproject\.com)") as api:
        def allowed(origin):
            r = api.options("/v1/catalog", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
            return r.headers.get("access-control-allow-origin") == origin
        assert allowed("https://id-preview--1234abcd.lovable.app")
        assert allowed("https://abcd1234.lovableproject.com")
        assert not allowed("https://lovable.app.evil.example")
        assert not allowed("http://agentbudget.lovable.app")  # plain http refused