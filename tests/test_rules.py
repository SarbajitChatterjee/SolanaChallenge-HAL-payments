"""Rules on the dashboard: edits are validated, recorded in the history, and apply to the next purchase."""

from tests.conftest import AGENT_H, OP_H


def rules(api):
    return api.get("/v1/rules", headers=OP_H).json()


def buy(api, tool, headers=AGENT_H, agent="research-agent", task="t1"):
    return api.post(f"/v1/agents/{agent}/call", json={"task_id": task, "tool": tool}, headers=headers)


def test_starting_rules_come_from_catalog_json(api):
    body = rules(api)
    assert {a["agent_id"] for a in body["agents"]} == {"research-agent", "intern-agent"}
    research = next(a for a in body["agents"] if a["agent_id"] == "research-agent")
    assert research["per_task_cap"] == "0.75" and research["approval_above"] == "0.25" and research["active"]
    assert {i["tool"] for i in body["items"]} >= {"company_lookup", "credit_report"}


def test_rules_need_the_operator(api):
    assert api.get("/v1/rules").status_code == 401
    assert api.patch("/v1/rules/agents/research-agent", json={"daily_cap": "1"}).status_code == 401


def test_raising_the_approval_limit_applies_to_the_next_purchase(api):
    assert buy(api, "credit_report").status_code == 202                       # 0.50 > 0.25: needs approval
    r = api.patch("/v1/rules/agents/research-agent", headers=OP_H, json={"approval_above": "0.60"})
    assert r.status_code == 200 and r.json()["approval_above"] == "0.60"
    assert buy(api, "credit_report", task="t2").status_code == 200             # now within the limit: paid


def test_new_price_is_the_new_cap(api):
    api.patch("/v1/rules/items/fx_realtime", headers=OP_H, json={"price": "0.10"})  # agree to the seller's price
    assert buy(api, "fx_realtime").status_code == 200


def test_validation_messages_name_the_field(api):
    cases = [
        ({"per_task_cap": "30"}, "per_task_cap", "bigger than the daily budget"),
        ({"approval_above": "0.80"}, "approval_above", "bigger than the task budget"),
        ({"daily_cap": "-1"}, "daily_cap", "above zero"),
        ({"daily_cap": "abc"}, "daily_cap", "like 0.25"),
        ({"allowed_tools": ["teleporter"]}, "allowed_tools", "Not on sale"),
        ({"allowed_tools": []}, "allowed_tools", "at least one"),
    ]
    for body, field, text in cases:
        r = api.patch("/v1/rules/agents/research-agent", headers=OP_H, json=body)
        assert r.status_code == 422 and r.json()["field"] == field and text in r.json()["detail"], (body, r.json())
    r = api.post("/v1/rules/items", headers=OP_H, json={"tool": "weather", "name": "Weather", "vendor": "W",
                                                        "url": "http://weather.example/v1", "price": "0.02"})
    assert r.status_code == 422 and r.json()["field"] == "url"


def test_new_item_and_new_agent_work_end_to_end(api):
    r = api.post("/v1/rules/items", headers=OP_H, json={
        "tool": "weather_lookup", "name": "Weather", "vendor": "Weather Co", "price": "0.02",
        "url": "https://api.weather.example/v1/now", "description": "Today's weather"})
    assert r.status_code == 201 and r.json()["price"] == "0.02"
    r = api.post("/v1/rules/agents", headers=OP_H, json={
        "agent_id": "travel-agent", "description": "Plans trips", "allowed_tools": ["weather_lookup", "fx_rate"],
        "per_task_cap": "0.50", "daily_cap": "5.00", "approval_above": "0.10"})
    assert r.status_code == 201 and r.json()["active"]
    assert api.post("/v1/rules/agents", headers=OP_H, json={**r.json(), "allowed_tools": ["fx_rate"]}).status_code == 422
    key = api.get("/v1/agents/travel-agent/key", headers=OP_H).json()["agent_key"]   # derived from APP_SECRET
    paid = buy(api, "fx_rate", headers={"Authorization": f"Bearer {key}"}, agent="travel-agent")
    assert paid.status_code == 200
    state_agents = [a["agent_id"] for a in api.get("/v1/state", headers=OP_H).json()["agents"]]
    assert "travel-agent" in state_agents


def test_archiving(api):
    api.patch("/v1/rules/items/news_search", headers=OP_H, json={"active": False})
    r = buy(api, "news_search")
    assert r.status_code == 403 and r.json()["reason_code"] == "not_in_catalog"   # archived: off the list
    api.patch("/v1/rules/agents/intern-agent", headers=OP_H, json={"active": False})
    assert buy(api, "fx_rate", headers={"Authorization": "Bearer ik-test"}, agent="intern-agent").status_code == 404
    assert "intern-agent" not in [a["agent_id"] for a in api.get("/v1/state", headers=OP_H).json()["agents"]]
    assert next(a for a in rules(api)["agents"] if a["agent_id"] == "intern-agent")["active"] is False  # still listed


def test_history_records_every_change(api):
    api.patch("/v1/rules/agents/research-agent", headers=OP_H, json={"daily_cap": "30.00"})
    api.patch("/v1/rules/agents/research-agent", headers=OP_H, json={"daily_cap": "30.00"})  # no-op: not recorded
    api.patch("/v1/rules/items/fx_rate", headers=OP_H, json={"active": False})
    history = api.get("/v1/rules/history", headers=OP_H).json()
    assert [h["action"] for h in history] == ["item.archived", "agent.updated"]
    assert history[1]["details"] == {"daily_cap": ["25", "30"]} and history[1]["actor"] == "operator"


def test_demo_reset_clears_and_restores(api):
    buy(api, "company_lookup")
    api.patch("/v1/rules/agents/research-agent", headers=OP_H, json={"per_task_cap": "0.30"})
    api.post("/v1/agents/intern-agent/freeze", headers=OP_H)
    assert api.post("/v1/demo/run?mode=tour", headers=OP_H).status_code == 409   # tour needs the demo rules
    r = api.post("/v1/demo/reset", headers=OP_H)
    assert r.status_code == 200 and "reset" in r.json()["message"].lower()
    state = api.get("/v1/state", headers=OP_H).json()
    assert state["events"] == [] and state["approvals"] == []
    assert all(not a["frozen"] for a in state["agents"])
    assert next(a for a in rules(api)["agents"] if a["agent_id"] == "research-agent")["per_task_cap"] == "0.75"
    assert api.get("/v1/rules/history", headers=OP_H).json()[0]["action"] == "demo.reset"  # history kept
    assert api.post("/v1/demo/run?mode=tour", headers=OP_H).json()["started"] is True
    api.post("/v1/demo/stop", headers=OP_H)


def test_reset_keeps_sign_ups(api):
    api.post("/v1/early-access", json={"email": "a@example.de", "role": "builder", "consent": True})
    api.post("/v1/demo/reset", headers=OP_H)
    assert api.get("/v1/early-access/count").json() == {"count": 1}


def test_visitor_changes_are_labelled_in_public_demo(make_client):
    with make_client(public_demo=True) as api:
        api.patch("/v1/rules/agents/research-agent", json={"daily_cap": "20.00"})
        assert api.get("/v1/rules/history").json()[0]["actor"] == "demo visitor"