"""Startup rules: one random APP_SECRET is enough, and missing or unsafe settings stop the API with a clear list."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from app.db import PG_SCHEMA, Repository
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

# ---- database upgrade at startup (feat/7.1) -------------------------------------------------------------
NEW_TABLES = {"event_details", "purchase_payloads", "content_links", "seller_status", "seller_incidents", "claims"}
NEW_AGENT_COLUMNS = {"max_repeats": 2, "repeat_window_minutes": 60, "max_attempts_per_min": 30,
                     "velocity_share_10m": 0.2}
NEW_ITEM_COLUMNS = {"reuse_ttl_seconds": 0, "reuse_scope": "agent", "content_policy": "annotate", "expect_json": None}

# The agents and catalog_items tables exactly as the main branch creates them.
MAIN_TABLES = """
create table {p}agents (agent_id varchar(64) primary key, description text, allowed_tools text not null,
  per_task_cap_micros bigint not null, daily_cap_micros bigint not null, approval_above_micros bigint not null,
  active boolean not null, created_at timestamp not null, updated_at timestamp not null);
create table {p}catalog_items (tool varchar(64) primary key, name varchar(80) not null, description text,
  vendor varchar(128) not null, url text not null, price_micros bigint not null, active boolean not null,
  created_at timestamp not null, updated_at timestamp not null);
insert into {p}agents values ('research-agent', 'Checks suppliers', '["fx_rate"]', 750000, 25000000, 250000, true,
  '2026-10-01 00:00:00', '2026-10-01 00:00:00');
insert into {p}catalog_items values ('fx_rate', 'Exchange rate', '', 'FX Feed (demo)', '{{vendor_base}}/v1/fx', 10000,
  true, '2026-10-01 00:00:00', '2026-10-01 00:00:00')
"""


@pytest.fixture(params=["sqlite"] + (["postgres"] if os.getenv("TEST_POSTGRES_URL") else []))
def blank_db(request, tmp_path):
    """(database url, table prefix) for an empty database."""
    if request.param == "postgres":
        url = os.environ["TEST_POSTGRES_URL"]
        with create_engine(url).begin() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {PG_SCHEMA} CASCADE"))
        return url, f"{PG_SCHEMA}."
    return f"sqlite:///{tmp_path / 'upgrade.db'}", ""


def _columns(url, table):
    schema = PG_SCHEMA if url.startswith("postgresql") else None
    return {c["name"] for c in inspect(create_engine(url)).get_columns(table, schema=schema)}


def test_app_starts_on_an_empty_database(blank_db):
    url, _ = blank_db
    settings = Settings(_env_file=None, database_url=url, public_demo=True, app_secret="s")
    with TestClient(create_app(settings, rail=MockRail())) as api:
        assert api.get("/v1/status").status_code == 200
    schema = PG_SCHEMA if url.startswith("postgresql") else None
    assert NEW_TABLES <= set(inspect(create_engine(url)).get_table_names(schema=schema))
    assert set(NEW_AGENT_COLUMNS) <= _columns(url, "agents")
    assert set(NEW_ITEM_COLUMNS) <= _columns(url, "catalog_items")


def test_app_upgrades_a_database_from_main(blank_db):
    url, prefix = blank_db
    with create_engine(url).begin() as conn:
        if prefix:
            conn.execute(text(f"create schema {PG_SCHEMA}"))
        for statement in MAIN_TABLES.format(p=prefix).split(";"):
            conn.execute(text(statement))
    settings = Settings(_env_file=None, database_url=url, public_demo=True, app_secret="s")
    with TestClient(create_app(settings, rail=MockRail())) as api:       # startup adds the columns
        assert api.get("/v1/rules").json()["agents"][0]["agent_id"] == "research-agent"  # old rows still work
    with create_engine(url).connect() as conn:                           # old rows got the defaults
        agent = conn.execute(text(f"select * from {prefix}agents")).mappings().one()
        item = conn.execute(text(f"select * from {prefix}catalog_items")).mappings().one()
    assert {k: agent[k] for k in NEW_AGENT_COLUMNS} == NEW_AGENT_COLUMNS
    assert {k: item[k] for k in NEW_ITEM_COLUMNS} == NEW_ITEM_COLUMNS
    assert Repository(url).add_missing_columns() == []                   # a second start changes nothing