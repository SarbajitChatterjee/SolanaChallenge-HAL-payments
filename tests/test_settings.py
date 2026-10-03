"""Startup rules: one random APP_SECRET is enough, and missing or unsafe settings stop the API with a clear list."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.rails import MockRail, PayKitRail
from app.settings import Settings

AGENTS = ("research-agent", "intern-agent")
RENDER = dict(database_url="postgresql+psycopg://u:p@db.example:5432/postgres?sslmode=require",
              app_secret="a-long-random-string-render-generated", public_demo=True, rail="paykit",
              vendor_base="https://agentbudget-vendors.onrender.com", allowed_origins="https://app.lovable.app")


def problems(**overrides):
    s = Settings(_env_file=None, **{**RENDER, **overrides})
    try:
        s.check(AGENTS)
    except RuntimeError as exc:
        return str(exc)
    return ""


def test_render_setup_needs_only_the_generated_secret():
    assert problems() == ""


def test_missing_secret_and_seller_address_are_listed_together():
    msg = problems(app_secret=None, vendor_base="http://127.0.0.1:8001")
    assert "No agent key for: research-agent, intern-agent" in msg
    assert "No wallet for" in msg and "APP_SECRET" in msg and "VENDOR_BASE" in msg


@pytest.mark.parametrize("overrides, expected", [
    (dict(public_demo=False), "Set OPERATOR_TOKEN, or PUBLIC_DEMO=true"),
    (dict(allowed_origins="*"), "not '*'"),
])
def test_each_problem_is_named(overrides, expected):
    assert expected in problems(**overrides)


def test_operator_token_satisfies_the_dashboard_rule():
    assert problems(public_demo=False, operator_token="op") == ""


def test_sqlite_only_warns(caplog):
    assert problems(database_url="sqlite:///x.db") == ""
    assert "data will be lost" in caplog.text


def test_mock_payments_need_no_wallets_or_seller_address():
    assert problems(rail="mock", app_secret=None, agent_keys="research-agent:a,intern-agent:b",
                    vendor_base="http://127.0.0.1:8001") == ""


def test_derived_keys_are_stable_distinct_and_load_as_wallets():
    pytest.importorskip("solana_pay_kit")  # wallet keys need the Solana SDK
    a, b = Settings(_env_file=None, **RENDER), Settings(_env_file=None, **RENDER)
    for agent in AGENTS:                                                 # same after a redeploy
        assert a.agent_key_for(agent) == b.agent_key_for(agent) and a.wallet_key_for(agent) == b.wallet_key_for(agent)
    assert a.agent_key_for("research-agent") != a.agent_key_for("intern-agent")
    assert a.agent_key_for("new-agent-added-later").startswith("ab_")  # agents added on the dashboard get keys
    other = Settings(_env_file=None, **{**RENDER, "app_secret": "different"})
    assert other.agent_key_for("research-agent") != a.agent_key_for("research-agent")
    rail = PayKitRail(network="localnet", rpc_url="https://x", wallet_key_for=a.wallet_key_for)
    assert len(rail.pubkey("research-agent")) >= 32


def test_explicit_keys_win_over_derived():
    s = Settings(_env_file=None, **{**RENDER, "agent_keys": "research-agent:mine"})
    assert s.agent_key_for("research-agent") == "mine" and s.agent_key_for("intern-agent").startswith("ab_")


def test_mainnet_is_not_a_valid_setting():
    with pytest.raises(Exception):
        Settings(_env_file=None, network="mainnet")


def test_key_endpoint_needs_the_real_token_even_in_public_demo(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path/'k.db'}", public_demo=True,
                        app_secret="s3cret", operator_token="op")
    with TestClient(create_app(settings, rail=MockRail())) as api:
        assert api.get("/v1/state").status_code == 200                       # public demo: dashboard open
        assert api.get("/v1/agents/research-agent/key").status_code == 401   # ...but keys are not
        body = api.get("/v1/agents/research-agent/key", headers={"Authorization": "Bearer op"}).json()
        assert body["agent_key"].startswith("ab_")
        r = api.post("/v1/agents/research-agent/call", json={"task_id": "t", "tool": "nope"},
                     headers={"Authorization": f"Bearer {body['agent_key']}"})
        assert r.status_code == 403 and r.json()["reason_code"] == "not_in_catalog"  # key works, rules apply