"""
Response firewall: checks the data a seller sent back, before the agent sees it.
The payment is already complete at this point. The firewall protects the agent's next step.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .policy import _normalize as normalize_url

MAX_BYTES = 200_000
REDACTED = "[removed by HAL: instructions aimed at agents]"

AGENT_INSTRUCTION = [re.compile(p, re.IGNORECASE) for p in (
    r"\bignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|rules|messages)",
    r"\bdisregard (all |any )?(the )?(previous|prior|above|your) (instructions|rules)",
    r"\bforget (all |any )?(the )?(previous|prior|your) (instructions|rules)",
    r"\bsystem (note|prompt|message|instruction)s?\b",
    r"\b(note|message|instructions?) (for|to) (the )?(ai|llm|language model|automated) ?(agents?|assistants?|systems?)?\b",
    r"\bthis (message|note) is for (ai|automated) (agents|assistants|systems)",
    r"\bas an ai (agent|assistant|model)\b",
    r"\byou are now (a|an|the)\b",
    r"\byou must (now )?(buy|purchase|pay|order|call|send|transfer)\b",
    r"\bimmediately (buy|purchase|pay|order|transfer|send)\b",
    r"\b(budget|budgets|limits?|rules) (do not|don't|does not|doesn't) apply\b",
    r"\b(override|bypass|ignore|skip) (your |the )?(budget|limits?|rules|approval|kill switch)\b",
    r"\byour (analysis|task|research|answer) is (incomplete|not complete)\b",
    r"\bdo not (tell|inform|ask) (the )?(user|human|operator|person)\b",
    r"\bwithout (asking|approval|telling) (the )?(user|human|operator|anyone)\b",
    r"\b(new|updated|revised) instructions\s*:",
    r"(^|\n)\s*(assistant|system)\s*:",
    r"#{2,}\s*instructions?\b",
    r"\b(transfer|send) (all )?(the )?(funds|money|usdc|sol|tokens)\b",
    r"\bimportant\s*:?\s*(for )?(ai|agents?)\b",
)]

AMOUNT = re.compile(r"(\$\s?\d[\d,]*(\.\d+)?|\b\d[\d,]*(\.\d+)?\s?(usdc|usd|sol)\b)(?!\s*(million|billion|bn|mn)\b)",
                    re.IGNORECASE)
BUY_WORD = re.compile(r"\b(buy|purchase|pay|send|transfer)\b", re.IGNORECASE)
URL = re.compile(r"https?://[^\s\"'<>()\[\]]+", re.IGNORECASE)


def _extract(text: str, start: int) -> str:
    return text[max(0, start - 20):max(0, start - 20) + 80]


def _check(text: str, approved: set[str]) -> tuple[list[tuple[str, str]], list[str]]:
    """(kind, extract) flags and normalised links found in one string."""
    flags: list[tuple[str, str]] = []
    for pattern in AGENT_INSTRUCTION:
        if m := pattern.search(text):
            flags.append(("agent_instruction", _extract(text, m.start())))
            break
    for m in AMOUNT.finditer(text):
        window = text[max(0, m.start() - 60):m.end() + 60]
        if BUY_WORD.search(window):
            flags.append(("payment_solicitation", _extract(text, m.start())))
            break
    links = []
    for m in URL.finditer(text):
        url = normalize_url(m.group(0).rstrip(".,;:!?"))
        links.append(url)
        if url not in approved:
            flags.append(("unlisted_link", url[:80]))
    return flags, links


def scan(data: Any, approved_urls: set[str], policy: str = "annotate") -> tuple[Any, list[dict], list[str]]:
    """Return (data for the agent, flags, links found). Flags: {"path", "kind", "extract"}."""
    try:
        size = len(json.dumps(data, default=str))
    except (TypeError, ValueError):
        size = 0
    if size > MAX_BYTES:
        return data, [{"path": "$", "kind": "not_scanned", "extract": f"Response is {size} bytes, over the limit."}], []

    approved = {normalize_url(u) for u in approved_urls}
    flags: list[dict] = []
    links: list[str] = []

    def walk(value: Any, path: str) -> Any:
        if isinstance(value, dict):
            return {k: walk(v, f"{path}.{k}" if path else str(k)) for k, v in value.items()}
        if isinstance(value, list):
            return [walk(v, f"{path}[{i}]") for i, v in enumerate(value)]
        if not isinstance(value, str):
            return value
        found, found_links = _check(value, approved)
        links.extend(u for u in found_links if u not in links)
        flags.extend({"path": path or "$", "kind": kind, "extract": extract} for kind, extract in found)
        if policy == "redact" and any(kind in ("agent_instruction", "payment_solicitation") for kind, _ in found):
            return REDACTED
        return value

    return walk(data, ""), flags, links