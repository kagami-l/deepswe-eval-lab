"""Read current and historical accounting without treating partial totals as complete."""

from __future__ import annotations

from typing import Any


def event_accounting(usage: dict[str, Any]) -> dict[str, Any]:
    tokens = usage.get("tokens")
    if isinstance(tokens, dict):
        totals = tokens["totals"]
        return {
            "input": totals["input"]["total"],
            "output": totals["output"]["total"],
            "availability": "reported",
            "coverage": tokens["coverage"],
            "cost": (usage.get("cost") or {}).get("amount"),
        }
    # Historical flat events are readable only with their explicit discriminator.
    reported = usage.get("tokenAvailability") == "reported"
    return {
        "input": usage.get("inputTokens") if reported else None,
        "output": usage.get("outputTokens") if reported else None,
        "availability": "reported" if reported else "unavailable",
        "coverage": "unknown" if reported else "unavailable",
        "cost": (usage.get("cost") or {}).get("amount", usage.get("totalCostUsd")),
    }


def complete_summary_tokens(usage: dict[str, Any]) -> bool:
    return usage.get("tokenAvailability") == "reported" and (
        usage.get("usageSchema") != 2 or usage.get("tokenCoverage") == "complete"
    )


def complete_summary_cost(usage: dict[str, Any]) -> bool:
    return usage.get("costUsd") is not None and (
        usage.get("usageSchema") != 2 or usage.get("costCoverage") == "complete"
    )
