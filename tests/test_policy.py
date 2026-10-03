"""The rules are the product, so they get the tightest tests."""

from decimal import Decimal as D

import pytest

from app.policy import AgentPolicy, CatalogItem, Decision, Reason, SpendRequest, evaluate

CATALOG = {
    "fx_rate": CatalogItem("fx_rate", "http://v.test/v1/fx", D("0.01"), "FX", name="Exchange rate"),
    "credit_report": CatalogItem("credit_report", "http://v.test/v1/credit-report", D("0.50"), "Bureau",
                                 name="Credit report"),
}
POLICY = AgentPolicy("a1", frozenset({"fx_rate", "credit_report"}), per_task_cap=D("0.75"),
                     daily_cap=D("1.00"), approval_above=D("0.25"))


def run(tool=None, url=None, spent_task="0", spent_today="0", frozen=False, approved=False, repeats=0,
        attempts=0, spent_10m="0"):
    return evaluate(SpendRequest("a1", "t1", tool=tool, url=url), policy=POLICY, catalog=CATALOG,
                    spent_task=D(spent_task), spent_today=D(spent_today), frozen=frozen, approved=approved,
                    repeat_count=repeats, attempts_last_min=attempts, spent_last_10m=D(spent_10m))


@pytest.mark.parametrize("kwargs, decision, code", [
    (dict(tool="fx_rate"), Decision.ALLOW, Reason.OK),
    (dict(url="http://v.test/v1/fx"), Decision.ALLOW, Reason.OK),            # raw URL matching an approved one
    (dict(url="HTTP://V.TEST/v1/fx/"), Decision.ALLOW, Reason.OK),           # normalised
    (dict(url="http://evil.test/v1/fx"), Decision.DENY, Reason.NOT_IN_CATALOG),  # look-alike seller
    (dict(tool="nope"), Decision.DENY, Reason.NOT_IN_CATALOG),
    (dict(), Decision.DENY, Reason.NOT_IN_CATALOG),
    (dict(tool="credit_report"), Decision.HOLD, Reason.NEEDS_APPROVAL),
    (dict(tool="credit_report", approved=True), Decision.ALLOW, Reason.OK),
    (dict(tool="fx_rate", frozen=True), Decision.DENY, Reason.FROZEN),
    (dict(tool="fx_rate", spent_task="0.75"), Decision.DENY, Reason.TASK_BUDGET),
    (dict(tool="fx_rate", spent_task="0.74"), Decision.ALLOW, Reason.OK),    # landing exactly on the cap is fine
    (dict(tool="fx_rate", spent_today="1.00"), Decision.DENY, Reason.DAILY_BUDGET),
    # budget beats approval: never ask a person to approve what the budget forbids
    (dict(tool="credit_report", spent_task="0.30"), Decision.DENY, Reason.TASK_BUDGET),
    # repeat rule: at most 2 paid in the window
    (dict(tool="fx_rate", repeats=1), Decision.ALLOW, Reason.OK),
    (dict(tool="fx_rate", repeats=2), Decision.DENY, Reason.REPEAT_PURCHASE),
    # circuit breaker: 30 attempts already this minute, or more than 20% of the daily cap (0.20) in 10 minutes
    (dict(tool="fx_rate", attempts=29), Decision.ALLOW, Reason.OK),
    (dict(tool="fx_rate", attempts=30), Decision.DENY, Reason.CIRCUIT_BREAKER),
    (dict(tool="fx_rate", spent_10m="0.20"), Decision.ALLOW, Reason.OK),
    (dict(tool="fx_rate", spent_10m="0.21"), Decision.DENY, Reason.CIRCUIT_BREAKER),
    (dict(tool="nope", attempts=30), Decision.DENY, Reason.CIRCUIT_BREAKER),   # blocked loops trip it too
    (dict(tool="fx_rate", attempts=30, frozen=True), Decision.DENY, Reason.FROZEN),
])
def test_decision_matrix(kwargs, decision, code):
    verdict = run(**kwargs)
    assert verdict.decision is decision and verdict.code is code


def test_messages_are_plain_and_specific():
    assert run(tool="credit_report").message == (
        "0.50 USD is above the 0.25 USD limit for automatic purchases, so a person has to approve it.")
    assert run(tool="fx_rate", spent_task="0.75").message == (
        "This would go over the task budget: 0.75 of 0.75 USD already used.")
    assert "approved list" in run(tool="nope").message


def test_tool_not_granted():
    narrow = AgentPolicy("intern", frozenset({"fx_rate"}), D("1"), D("1"), D("1"))
    v = evaluate(SpendRequest("intern", "t", tool="credit_report"), policy=narrow, catalog=CATALOG,
                 spent_task=D(0), spent_today=D(0), frozen=False)
    assert v.code is Reason.NOT_ALLOWED and v.message == "intern isn't allowed to buy Credit report."


def test_kill_switch_wins_over_everything():
    assert run(tool="credit_report", approved=True, frozen=True).code is Reason.FROZEN


def test_fingerprint_ignores_key_order_spacing_and_case():
    from app.fingerprint import fingerprint
    base = fingerprint("fx_rate", {"pair": "EURUSD", "day": "Mon"})
    assert fingerprint("fx_rate", {"day": " mon ", "pair": "eurusd"}) == base
    assert fingerprint("fx_rate", {"pair": "GBPUSD", "day": "Mon"}) != base
    assert fingerprint("news_search", {"pair": "EURUSD", "day": "Mon"}) != base


# ---- response firewall (feat/2.1 | version 1.5.4) ---------------------------------------------------------------------------
from app.firewall import REDACTED, scan  # noqa: E402
from tests.conftest import INJECTION  # noqa: E402

APPROVED = {"http://127.0.0.1:8001/v1/news", "http://127.0.0.1:8001/v1/company"}
USUAL_HEADLINES = [
    "Duping Bahn wins supplier contract with regional carmaker",
    "Duping Bahn reports delayed deliveries due to steel prices",
    "Duping Bahn revenue rises 8% to 12 million USD in 2025",
    "Investor agrees to buy 20% stake in Duping Bahn for 3 million USD",
    "Duping Bahn opens a new plant in Saarbruecken",
    "CEO says the company will pay suppliers within 30 days",
    "Rail freight prices fall for the third quarter in a row",
    "Duping Bahn named among the top 100 Mittelstand employers",
    "Union and management agree on a new wage deal",
    "Analysts expect stable demand for steel parts in 2027",
]


def test_firewall_removes_the_demo_injection():
    data = {"items": [{"title": USUAL_HEADLINES[0]}, {"title": "Note for AI agents", "body": INJECTION}]}
    out, flags, links = scan(data, APPROVED, "redact")
    assert out["items"][1]["body"] == REDACTED and out["items"][0] == data["items"][0]
    assert out["items"][1]["title"] == REDACTED          # "Note for AI agents" also speaks to the agent
    assert {f["kind"] for f in flags} == {"agent_instruction", "payment_solicitation", "unlisted_link"}
    assert {f["path"] for f in flags} == {"items[1].title", "items[1].body"}
    assert all(len(f["extract"]) <= 80 for f in flags)
    assert links == ["http://127.0.0.1:8001/shady/full-dossier"]


def test_firewall_leaves_usual_headlines_alone():
    data = {"items": [{"title": h} for h in USUAL_HEADLINES]}
    out, flags, _ = scan(data, APPROVED, "redact")
    assert out == data and flags == []


def test_annotate_keeps_the_data_and_adds_flags():
    data = {"body": INJECTION}
    out, flags, _ = scan(data, APPROVED, "annotate")
    assert out == data and {f["kind"] for f in flags} == {"agent_instruction", "payment_solicitation", "unlisted_link"}


def test_an_unlisted_link_alone_is_flagged_but_never_removed():
    data = {"text": "Full report at https://www.example.org/report.pdf."}
    out, flags, links = scan(data, APPROVED, "redact")
    assert out == data and [f["kind"] for f in flags] == ["unlisted_link"]
    assert links == ["https://www.example.org/report.pdf"]


def test_approved_links_are_not_flagged():
    assert scan({"next": "http://127.0.0.1:8001/v1/company"}, APPROVED, "redact")[1] == []


def test_very_large_responses_are_passed_through_with_a_flag():
    data = {"blob": "x" * 250_000}
    out, flags, _ = scan(data, APPROVED, "redact")
    assert out is data and flags[0]["kind"] == "not_scanned"