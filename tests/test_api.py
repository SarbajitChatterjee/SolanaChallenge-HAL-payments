"""End-to-end through HTTP with the mock rail, on SQLite and (if TEST_POSTGRES_URL is set) Postgres."""

import time
from concurrent.futures import ThreadPoolExecutor

from tests.conftest import AGENT_H, INTERN_H, OP_H


def call(api, headers=AGENT_H, agent="research-agent", task="t1", **body):
    return api.post(f"/v1/agents/{agent}/call", json={"task_id": task, **body}, headers=headers)


def set_reuse(api, tool, seconds, scope="agent"):
    """Change an item's reuse window directly (the Rules page does not edit it)."""
    from sqlalchemy import update
    from app.db import catalog_items
    with api.app.state.repo.engine.begin() as conn:
        conn.execute(update(catalog_items).where(catalog_items.c.tool == tool)
                     .values(reuse_ttl_seconds=seconds, reuse_scope=scope))
    api.app.state.rules.invalidate()


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
    assert api.get("/v1/status").json() == body          # same answer under an address ad blockers ignore


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
    assert r.json()["reason"] == "FX Feed (demo) asked 0.10 USD. The agreed price is 0.01 USD, so nothing was paid."
    assert research(api)["spent_today"] == "0.00"


def test_runaway_loop_stops_at_task_cap(api):

    # different params each time, so this tests the task budget and not the repeat rule
    codes = [call(api, tool="news_search", params={"q": f"query {i}"}).status_code for i in range(18)]
    assert codes.count(200) == 15 and codes[15:] == [403, 403, 403]


def test_parallel_calls_never_overspend(api):
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda i: call(api, task="race", tool="news_search",
                                             params={"q": f"query {i}"}).status_code, range(24)))
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
    assert lines[0] == "Date (UTC),Agent,Task,Item,Seller,Amount,Currency,Reference,Solana receipt,Status,Reused from"
    assert len(lines) == 2 and ",research-agent,t1,company_lookup,Registry Data (demo),0.05,USDC,AB-" in lines[1]
    assert lines[1].endswith(",paid,")


def test_ledger_lists_reused_purchases_with_their_source(api):
    first = call(api, tool="fx_rate", params={"pair": "EURUSD"}).json()
    again = call(api, task="t2", tool="fx_rate", params={"pair": "EURUSD"}).json()
    paid, reused = api.get("/v1/ledger.csv", headers=OP_H).text.strip().splitlines()[1:]
    assert paid.endswith(f",{first['tx']},paid,") and f",AB-{again['reused_from']}," in paid
    assert ",0.00,USDC,AB-" in reused and reused.endswith(",,reused,AB-" + again["reused_from"])




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


def test_waiting_row_turns_into_the_decision(api):
    def row(approval_id):
        return next(e for e in api.get("/v1/state", headers=OP_H).json()["events"] if e["id"] == approval_id)
    yes = call(api, tool="credit_report").json()["approval_id"]
    assert row(yes)["status"] == "held"
    api.post(f"/v1/approvals/{yes}/approve", headers=OP_H)
    assert row(yes)["status"] == "approved" and row(yes)["reason_code"] == "approved"
    no = call(api, task="t2", tool="credit_report").json()["approval_id"]
    api.post(f"/v1/approvals/{no}/deny", headers=OP_H)
    assert row(no)["status"] == "denied" and "said no" in row(no)["reason"]
    assert api.post(f"/v1/approvals/{no}/approve", headers=OP_H).status_code == 409   # can't change a decision
    assert row(no)["status"] == "denied"

# ---- loop protection: repeat rule and circuit breaker (feat/1.2) ------------------------------------------
def test_new_task_ids_do_not_get_around_the_limits(api):
    """The review's probe: a loop with a new task id for every call. Before this fix, 500 of 600 calls were paid.
    Reuse is off here, so the repeat rule is what stops it."""
    set_reuse(api, "news_search", 0)
    results = [call(api, task=f"loop-{i}", tool="news_search", params={"q": "Duping Bahn"}) for i in range(600)]
    codes = [r.json().get("reason_code") for r in results]
    assert codes.count("paid") == 2
    assert codes[2] == "repeat_purchase"                      # the third purchase is refused as a repeat
    assert "circuit_breaker" in codes and research(api)["frozen"] is True


def test_same_purchase_is_paid_at_most_twice(api):
    set_reuse(api, "fx_rate", 0)
    first, second, third = (call(api, task=f"t{i}", tool="fx_rate", params={"pair": "EURUSD"}) for i in range(3))
    assert first.status_code == second.status_code == 200
    assert third.status_code == 403 and third.json()["reason_code"] == "repeat_purchase"
    other = call(api, task="t4", tool="fx_rate", params={"pair": " eurusd "})       # same after normalising
    assert other.json()["reason_code"] == "repeat_purchase"
    assert call(api, task="t5", tool="fx_rate", params={"pair": "GBPUSD"}).status_code == 200  # different purchase


def test_breaker_freezes_after_31_attempts_and_only_an_operator_unfreezes(api):
    codes = [call(api, tool="fx_rate", params={"pair": f"P{i}"}).json()["reason_code"] for i in range(31)]
    assert codes[:30] == ["paid"] * 30 and codes[30] == "circuit_breaker"
    assert research(api)["frozen"] is True
    stop = next(e for e in api.get("/v1/state", headers=OP_H).json()["events"] if e["status"] == "control")
    assert stop["reason_code"] == "circuit_breaker" and stop["reason"].startswith("Stopped automatically")
    assert call(api, tool="fx_rate", params={"pair": "X"}).json()["reason_code"] == "frozen"
    assert api.post("/v1/agents/research-agent/unfreeze", headers=AGENT_H).status_code == 401  # the agent can't
    assert api.post("/v1/agents/research-agent/unfreeze", headers=OP_H).status_code == 200    # a person can
    assert call(api, tool="fx_rate", params={"pair": "Y"}).status_code == 200                 # counting restarts


def test_waiting_for_an_approval_does_not_trip_the_breaker(api):
    approval_id = call(api, tool="credit_report").json()["approval_id"]
    for _ in range(40):                                        # an agent polling while it waits
        assert call(api, tool="credit_report", approval_id=approval_id).status_code == 202
    assert research(api)["frozen"] is False


# ---- response firewall (feat/2.1) ---------------------------------------------------------------------------
def test_news_purchase_comes_back_with_the_injection_removed(api):
    r = call(api, tool="news_search", params={"q": "Duping Bahn"})
    body = r.json()
    assert r.status_code == 200 and body["data"]["items"][1]["body"] == "[removed by HAL: instructions aimed at agents]"
    assert body["data"]["items"][0]["title"].startswith("Duping Bahn wins")              # normal news untouched
    assert {f["kind"] for f in body["content_flags"]} >= {"agent_instruction", "unlisted_link"}
    from app.db import event_details
    from sqlalchemy import select
    with api.app.state.repo.engine.connect() as conn:                                      # flags are recorded
        stored = conn.execute(select(event_details.c.content_flags_json)).scalars().all()
    assert any(s and "agent_instruction" in s for s in stored)


def test_clean_purchases_have_no_flags(api):
    r = call(api, tool="fx_rate", params={"pair": "EURUSD"})
    assert r.status_code == 200 and r.json()["content_flags"] == []



# ---- provenance: find the source of the trap (feat/2.2) ---------------------------------------------------
DOSSIER = "http://127.0.0.1:8001/shady/full-dossier"
DEMO_SELLER = "http://127.0.0.1:8001"


def test_blocked_link_is_traced_to_the_seller_that_sent_it(api):
    call(api, tool="news_search", params={"q": "Duping Bahn"})              # the response contains the dossier link
    news_event = next(e for e in api.get("/v1/state", headers=OP_H).json()["events"] if e["status"] == "settled")

    r = call(api, url=DOSSIER)
    body = r.json()
    assert r.status_code == 403 and body["reason_code"] == "not_in_catalog"
    assert body["caused_by"] == news_event["id"]
    assert "The link came from News Wire (demo)" in body["reason"] and "is now under review" in body["reason"]

    seller = next(x for x in api.get("/v1/sellers", headers=OP_H).json() if x["seller_origin"] == DEMO_SELLER)
    assert seller["status"] == "under_review" and seller["incidents"] == 1 and seller["updated_by"] == "HAL"

    held = call(api, tool="news_search", params={"q": "something else"})     # the next purchase waits for a person
    assert held.status_code == 202 and held.json()["reason_code"] == "seller_under_review"
    api.post(f"/v1/approvals/{held.json()['approval_id']}/approve", headers=OP_H)
    paid = call(api, tool="news_search", params={"q": "something else"}, approval_id=held.json()["approval_id"])
    assert paid.status_code == 200


def test_restoring_a_seller_ends_the_review(api):
    call(api, tool="news_search", params={"q": "Duping Bahn"})
    call(api, url=DOSSIER)
    assert api.post(f"/v1/sellers/{DEMO_SELLER}/restore", headers=AGENT_H).status_code == 401
    r = api.post(f"/v1/sellers/{DEMO_SELLER}/restore", headers=OP_H)
    assert r.status_code == 200 and r.json()["status"] == "active"
    assert call(api, tool="fx_rate", params={"pair": "EURUSD"}).status_code == 200
    history = api.get("/v1/rules/history", headers=OP_H).json()
    assert history[0]["action"] == "seller.restored" and history[0]["target"] == DEMO_SELLER
    assert api.post("/v1/sellers/https://nobody.example/restore", headers=OP_H).status_code == 404


def test_an_unknown_link_without_a_source_is_only_blocked(api):
    r = call(api, url="https://dossier-deals.example/full-dossier")         # never seen in a paid response
    assert r.status_code == 403 and "caused_by" not in r.json()
    assert all(x["status"] == "active" for x in api.get("/v1/sellers", headers=OP_H).json())


def test_reset_demo_ends_reviews(api):
    call(api, tool="news_search", params={"q": "Duping Bahn"})
    call(api, url=DOSSIER)
    api.post("/v1/demo/reset", headers=OP_H)
    assert all(x["status"] == "active" and x["incidents"] == 0
               for x in api.get("/v1/sellers", headers=OP_H).json())



# ---- News Wire as its own seller, and waking the seller services ------------------------------------------------
NEWS_SELLER = "http://127.0.0.1:8002"


def test_news_wire_on_its_own_service_is_a_separate_seller(make_client):
    with make_client(news_vendor_base=NEWS_SELLER) as api:
        call(api, tool="news_search", params={"q": "Duping Bahn"})
        assert "News Wire (demo) is now under review" in call(api, url=DOSSIER).json()["reason"]
        status = {x["seller_origin"]: x["status"] for x in api.get("/v1/sellers", headers=OP_H).json()}
        assert status == {DEMO_SELLER: "active", NEWS_SELLER: "under_review"}
        assert call(api, tool="fx_rate", params={"pair": "EURUSD"}).status_code == 200   # FX Feed still paid
        assert call(api, tool="news_search", params={"q": "other"}).status_code == 202   # News Wire waits


def test_a_status_check_wakes_the_seller_services(api):
    calls = []

    async def fake_wake():
        calls.append(1)

    api.app.state.waker.wake = fake_wake
    assert api.get("/v1/status").status_code == 200 and api.get("/health").status_code == 200
    assert len(calls) == 2


# ---- purchase reuse (feat/2.3) -------------------------------------------------------------------------------
def test_second_identical_purchase_is_reused_and_costs_nothing(api):
    first = call(api, task="a", tool="fx_rate", params={"pair": "EURUSD"}).json()
    spent = research(api)["spent_today"]
    second = call(api, task="b", tool="fx_rate", params={"pair": " eurusd "})          # same after normalising
    body = second.json()
    assert second.status_code == 200 and body["status"] == "reused" and body["reason_code"] == "reused"
    assert body["amount"] == "0.00" and body["saved"] == "0.01" and body["tx"] == first["tx"]
    assert body["data"] == first["data"] and body["reused_from"]
    assert research(api)["spent_today"] == spent                                        # the budget did not move
    assert call(api, task="c", tool="fx_rate", params={"pair": "GBPUSD"}).json()["reason_code"] == "paid"


def test_reuse_comes_before_the_repeat_rule(api):
    codes = [call(api, task=f"loop-{i}", tool="fx_rate", params={"pair": "EURUSD"}).json()["reason_code"]
             for i in range(40)]
    assert codes[0] == "paid" and "repeat_purchase" not in codes
    assert codes[1:30] == ["reused"] * 29 and codes[30] == "circuit_breaker"             # reused calls still count
    assert research(api)["frozen"] is True


def test_reused_news_keeps_the_firewall_result(api):
    first = call(api, tool="news_search", params={"q": "Duping Bahn"}).json()
    again = call(api, task="t2", tool="news_search", params={"q": "Duping Bahn"}).json()
    assert again["status"] == "reused" and again["data"] == first["data"]
    assert again["data"]["items"][1]["body"] == "[removed by HAL: instructions aimed at agents]"
    assert again["content_flags"] == first["content_flags"]


def test_credit_report_is_never_reused(api):
    held = call(api, tool="credit_report", params={"name": "Duping Bahn GmbH"}).json()
    api.post(f"/v1/approvals/{held['approval_id']}/approve", headers=OP_H)
    assert call(api, tool="credit_report", params={"name": "Duping Bahn GmbH"},
                approval_id=held["approval_id"]).json()["reason_code"] == "paid"
    again = call(api, task="t2", tool="credit_report", params={"name": "Duping Bahn GmbH"})
    assert again.status_code == 202 and again.json()["reason_code"] == "needs_approval"


def test_reuse_is_per_agent_unless_the_item_says_org(api):
    call(api, tool="fx_rate", params={"pair": "EURUSD"})
    assert call(api, headers=INTERN_H, agent="intern-agent", tool="fx_rate",
                params={"pair": "EURUSD"}).json()["reason_code"] == "paid"
    set_reuse(api, "fx_rate", 3600, scope="org")
    call(api, tool="fx_rate", params={"pair": "GBPUSD"})
    assert call(api, headers=INTERN_H, agent="intern-agent", tool="fx_rate",
                params={"pair": "GBPUSD"}).json()["reason_code"] == "reused"


def test_expired_results_are_paid_again_and_deleted(api):
    from sqlalchemy import func, select, update
    from app.db import purchase_payloads, utcnow
    call(api, tool="fx_rate", params={"pair": "EURUSD"})
    with api.app.state.repo.engine.begin() as conn:
        conn.execute(update(purchase_payloads).values(expires_at=utcnow()))
    assert call(api, task="t2", tool="fx_rate", params={"pair": "EURUSD"}).json()["reason_code"] == "paid"
    with api.app.state.repo.engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(purchase_payloads)).scalar_one() == 1  # old one gone


def test_no_payload_is_stored_for_items_without_reuse(api):
    from sqlalchemy import func, select
    from app.db import purchase_payloads
    set_reuse(api, "fx_rate", 0)
    call(api, tool="fx_rate", params={"pair": "EURUSD"})
    with api.app.state.repo.engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(purchase_payloads)).scalar_one() == 0


def test_parallel_identical_calls_with_reuse_never_overspend(api):
    with ThreadPoolExecutor(max_workers=24) as pool:
        codes = list(pool.map(lambda i: call(api, task=f"p{i}", tool="company_lookup",
                                             params={"name": "Duping Bahn GmbH"}).json()["reason_code"], range(24)))
    assert codes.count("paid") <= 2 and set(codes) <= {"paid", "reused", "repeat_purchase"}
    assert research(api)["spent_today"] == f"{0.05 * codes.count('paid'):.2f}"



# ---- tour v2: context for the person who approves -------------------------------------------------------------
def test_approval_request_shows_what_the_task_already_bought(api):
    assert call(api, task="new-task", tool="credit_report").json()["reason"].endswith(
        "This task has bought nothing yet.")
    call(api, task="check-1", tool="company_lookup", params={"name": "Duping Bahn GmbH"})
    call(api, task="check-1", tool="fx_rate", params={"pair": "EURUSD"})
    held = call(api, task="check-1", tool="credit_report").json()
    assert held["reason"].endswith("Task check-1 already bought: Company record, Exchange rate (0.06 USD).")
    pending = api.get("/v1/state", headers=OP_H).json()["approvals"]
    assert any(a["reason"] == held["reason"] for a in pending)                 # the approval card shows it too


# ---- what the dashboard needs to show the new controls --------------------------------------------------------
def test_fingerprint_ignores_extra_spaces_inside_strings():
    from app.fingerprint import fingerprint
    assert fingerprint("news_search", {"q": "Duping  Bahn"}) == fingerprint("news_search", {"q": " duping bahn"})
    assert fingerprint("news_search", {"q": "Duping Bahn", "page": 1}) != fingerprint("news_search", {"q": "Duping Bahn"})


def test_state_shows_savings_and_why_an_agent_is_stopped(api):
    call(api, tool="fx_rate", params={"pair": "EURUSD"})
    for i in range(3):
        call(api, task=f"r{i}", tool="fx_rate", params={"pair": "EURUSD"})
    agent = research(api)
    assert agent["saved_today"] == "0.03" and agent["reused_today"] == 3 and agent["frozen_reason"] is None
    api.post("/v1/agents/research-agent/freeze", headers=OP_H)
    assert research(api)["frozen_reason"].startswith("Kill switch on")


def test_state_events_show_reuse_provenance_and_flags(api):
    news = call(api, tool="news_search", params={"q": "Duping Bahn"}).json()
    again = call(api, task="t2", tool="news_search", params={"q": "Duping Bahn"}).json()
    call(api, url=DEMO_SELLER + "/shady/full-dossier")
    events = api.get("/v1/state", headers=OP_H).json()["events"]
    paid = next(e for e in events if e["status"] == "settled")
    assert paid["id"] == again["reused_from"] and paid["content_flags"] == news["content_flags"] != []
    assert next(e for e in events if e["status"] == "reused")["reused_from"] == paid["id"]
    assert next(e for e in events if e["reason_code"] == "not_in_catalog")["caused_by"] == paid["id"]