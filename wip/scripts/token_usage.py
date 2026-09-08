#!/usr/bin/env python3
"""Report current cligent accounting from DeepSWE job summaries.

Only usageSchema=2 with one usageReports slot per turn is accepted. Native
input/output totals include cache/reasoning subsets. Partial reports are observed
subtotals, not complete totals. Costs come exclusively from terminal cost reports;
model records explain those totals and are never added to them again.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

TOKEN_FIELDS = {
    "input": ("total", "uncached", "cacheRead", "cacheWrite"),
    "output": ("total", "visible", "reasoning"),
}
COST_SOURCES = {"provider-reported", "agent-estimate", "account-estimate"}


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _number(value: Any, *, integer: bool = False) -> bool:
    return (
        isinstance(value, int if integer else (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _validate_cost(cost: Any, where: str) -> None:
    if (
        not isinstance(cost, dict)
        or not _number(cost.get("amount"))
        or cost.get("currency") != "USD"
        or cost.get("source") not in COST_SOURCES
    ):
        raise ValueError(f"{where}: invalid cligent USD cost report")


def _validate_tokens(tokens: Any, where: str) -> None:
    if not isinstance(tokens, dict):
        raise ValueError(f"{where}: invalid token totals")
    for side, keys in TOKEN_FIELDS.items():
        values = tokens.get(side)
        if not isinstance(values, dict) or not _number(values.get("total"), integer=True):
            raise ValueError(f"{where}: missing or invalid {side}.total")
        for key in keys:
            if key in values and not _number(values[key], integer=True):
                raise ValueError(f"{where}: invalid {side}.{key}")


def _reports(usage: dict[str, Any], where: str) -> list[dict[str, Any] | None]:
    reports = usage.get("usageReports")
    turns = usage.get("turns")
    if usage.get("usageSchema") != 2:
        raise ValueError(f"{where}: only usageSchema=2 is supported; legacy usage is not accepted")
    if not isinstance(reports, list) or not _number(turns, integer=True) or len(reports) != turns:
        raise ValueError(f"{where}: usageReports must contain exactly one slot per turn")
    for index, report in enumerate(reports, 1):
        location = f"{where}, turn {index}"
        if report is None:
            continue
        if not isinstance(report, dict):
            raise ValueError(f"{location}: invalid usage report")
        if "tokens" in report:
            tokens = report["tokens"]
            if not isinstance(tokens, dict) or tokens.get("coverage") not in {"complete", "partial"}:
                raise ValueError(f"{location}: invalid token coverage")
            _validate_tokens(tokens.get("totals"), location)
            records = tokens.get("records", [])
            if not isinstance(records, list):
                raise ValueError(f"{location}: invalid model records")
            for record in records:
                if not isinstance(record, dict):
                    raise ValueError(f"{location}: invalid model record")
                for key in ("model", "provider"):
                    if key in record and not isinstance(record[key], str):
                        raise ValueError(f"{location}: invalid record {key}")
                _validate_tokens(record.get("tokens"), location)
                if "cost" in record:
                    _validate_cost(record["cost"], location)
        if "cost" in report:
            _validate_cost(report["cost"], location)
    return reports


def _sum_known(values: list[int | float]) -> int | float | None:
    return sum(values) if values else None


def _coverage(reported: int, total: int, complete: bool = True) -> str:
    if not reported:
        return "unavailable"
    return "complete" if reported == total and complete else "partial"


def _model_usage(reports: list[dict[str, Any] | None]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str | None, str | None], list[dict[str, Any]]] = {}
    for report in reports:
        for record in ((report or {}).get("tokens") or {}).get("records", []):
            grouped.setdefault((record.get("model"), record.get("provider")), []).append(record)
    return [
        {
            "model": model,
            "provider": provider,
            "records": len(records),
            "observedInputTokens": sum(r["tokens"]["input"]["total"] for r in records),
            "observedOutputTokens": sum(r["tokens"]["output"]["total"] for r in records),
            "observedCostUsd": _sum_known([r["cost"]["amount"] for r in records if "cost" in r]),
            "costRecords": sum("cost" in r for r in records),
            "costSources": sorted({r["cost"]["source"] for r in records if "cost" in r}),
        }
        for (model, provider), records in grouped.items()
    ]


def _accounting(
    reports: list[dict[str, Any] | None], *, tool_uses: int = 0, wall_ms: int = 0
) -> dict[str, Any]:
    tokens = [r["tokens"] for r in reports if r is not None and "tokens" in r]
    costs = [r["cost"] for r in reports if r is not None and "cost" in r]
    token_coverage = _coverage(
        len(tokens), len(reports), all(t["coverage"] == "complete" for t in tokens)
    )
    cost_coverage = _coverage(len(costs), len(reports))
    details = {}
    for side, keys in TOKEN_FIELDS.items():
        for key in keys:
            values = [t["totals"][side][key] for t in tokens if key in t["totals"][side]]
            observed = _sum_known(values)
            details[f"{side}.{key}"] = {
                "observed": observed,
                "reportedTurns": len(values),
                "total": (
                    observed
                    if token_coverage == "complete" and len(values) == len(reports)
                    else None
                ),
            }
    observed_input = details["input.total"]["observed"]
    observed_output = details["output.total"]["observed"]
    observed_cost = _sum_known([c["amount"] for c in costs])
    return {
        "usageSchema": 2,
        "usageReports": reports,
        "turns": len(reports),
        "toolUses": tool_uses,
        "wallMs": wall_ms,
        "tokenCoverage": token_coverage,
        "tokenReportTurns": len(tokens),
        "completeTokenTurns": sum(t["coverage"] == "complete" for t in tokens),
        "partialTokenTurns": sum(t["coverage"] == "partial" for t in tokens),
        "missingTokenTurns": len(reports) - len(tokens),
        "observedInputTokens": observed_input,
        "observedOutputTokens": observed_output,
        "inputTokens": observed_input if token_coverage == "complete" else None,
        "outputTokens": observed_output if token_coverage == "complete" else None,
        "tokenDetails": details,
        "costCoverage": cost_coverage,
        "costReportTurns": len(costs),
        "missingCostTurns": len(reports) - len(costs),
        "observedCostUsd": observed_cost,
        "costUsd": observed_cost if cost_coverage == "complete" else None,
        "costSources": sorted({c["source"] for c in costs}),
        "modelRecordTurns": sum("records" in t for t in tokens),
        "modelUsage": _model_usage(reports),
    }


def _usage_cost(usage: dict[str, Any]) -> dict[str, Any] | None:
    accounting = _accounting(_reports(usage, "usage"))
    if accounting["observedCostUsd"] is None:
        return None
    models = sorted({m["model"] for m in accounting["modelUsage"] if m["model"] is not None})
    return {
        "models": models,
        "totalUsd": accounting["observedCostUsd"],
        "completeTotalUsd": accounting["costUsd"],
        "sources": accounting["costSources"],
        "coverage": accounting["costCoverage"],
        "estimated": any(s != "provider-reported" for s in accounting["costSources"]),
    }


def _trial_rows(job_dir: Path) -> tuple[list[dict[str, Any]], list[str], dict[str, str]]:
    rows, skipped, labels = [], [], {}
    for trial in sorted(job_dir.iterdir()):
        if not trial.is_dir() or trial.name.startswith(".") or trial.name == "patch-scores":
            continue
        result = _load_json(trial / "result.json")
        summary = _load_json(trial / "agent/system/summary.json")
        usage = ((summary or {}).get("result") or {}).get("usage")
        if not isinstance(result, dict) or not isinstance(usage, dict):
            skipped.append(trial.name)
            continue
        role_usage = {}
        for role, spec in usage.items():
            if not isinstance(spec, dict):
                raise ValueError(f"{trial.name}/{role}: invalid usage")
            if spec.get("turns") == 0:
                continue
            reports = _reports(spec, f"{trial.name}/{role}")
            for key in ("toolUses", "wallMs"):
                if not _number(spec.get(key)):
                    raise ValueError(f"{trial.name}/{role}: missing or invalid {key}")
            role_usage[role] = _accounting(
                reports, tool_uses=spec["toolUses"], wall_ms=spec["wallMs"]
            )
            identity = (summary.get("roles") or {}).get(role, {})
            label = f"{identity.get('adapter', role)}/{identity.get('model', '?')}"
            if role in labels and labels[role] != label:
                labels[role] = "multiple configured models (see reported model records)"
            else:
                labels[role] = label
        if not role_usage:
            skipped.append(trial.name)
            continue
        rows.append({
            "trial": trial.name,
            "reward": ((result.get("verifier_result") or {}).get("rewards") or {}).get("reward"),
            "outcome": summary["result"].get("outcome"),
            "usage": role_usage,
        })
    return rows, skipped, labels


def _aggregate(usages: list[dict[str, Any]]) -> dict[str, Any]:
    return _accounting(
        [r for u in usages for r in u["usageReports"]],
        tool_uses=sum(u["toolUses"] for u in usages),
        wall_ms=sum(u["wallMs"] for u in usages),
    )


def _stats(values: list[int | float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    return {
        "mean": statistics.mean(ordered),
        "median": statistics.median(ordered),
        "min": ordered[0],
        "max": ordered[-1],
        "p90": ordered[max(0, round(0.9 * (len(ordered) - 1)))],
        "samples": len(values),
    }


def build_report(job_dir: Path) -> dict[str, Any]:
    rows, skipped, labels = _trial_rows(job_dir)
    roles = list(dict.fromkeys(role for row in rows for role in row["usage"]))
    totals = {
        role: _aggregate([row["usage"][role] for row in rows if role in row["usage"]])
        for role in roles
    }
    for row in rows:
        row["costs"] = {
            role: cost for role, usage in row["usage"].items()
            if (cost := _usage_cost(usage)) is not None
        }
    costs = {
        role: cost for role, usage in totals.items() if (cost := _usage_cost(usage)) is not None
    }
    job_totals = _aggregate(list(totals.values()))
    if skipped:
        # Excluded trials may have usage even if all readable turns are complete.
        for kind, fields in (("token", ("inputTokens", "outputTokens")), ("cost", ("costUsd",))):
            if job_totals[f"{kind}Coverage"] == "complete":
                job_totals[f"{kind}Coverage"] = "partial"
            for key in fields:
                job_totals[key] = None
        for detail in job_totals["tokenDetails"].values():
            detail["total"] = None
    metrics = ("observedInputTokens", "observedOutputTokens", "observedCostUsd", "wallMs")
    stats = {
        role: {
            key: _stats([
                row["usage"][role][key] for row in rows
                if role in row["usage"] and row["usage"][role][key] is not None
            ])
            for key in metrics
        }
        for role in roles
    }
    split = {}
    for group, rewards in (("passed", {1}), ("failed", {0}), ("unscored", {None})):
        per_role = {}
        for role in roles:
            usages = [
                row["usage"][role] for row in rows
                if row["reward"] in rewards and role in row["usage"]
            ]
            if not usages:
                continue
            bucket = {"trials": len(usages)}
            for source, target in (
                ("observedInputTokens", "meanObservedInput"),
                ("observedOutputTokens", "meanObservedOutput"),
                ("inputTokens", "meanInput"),
                ("outputTokens", "meanOutput"),
                ("observedCostUsd", "meanCostUsd"),
            ):
                values = [u[source] for u in usages if u[source] is not None]
                bucket[target] = statistics.mean(values) if values else None
                bucket[target + "Samples"] = len(values)
            per_role[role] = bucket
        split[group] = per_role
    return {
        "reportSchemaVersion": 2,
        "jobDir": str(job_dir),
        "roleModels": labels,
        "trials": rows,
        "skippedTrials": skipped,
        "jobTotals": job_totals,
        "totals": totals,
        "costs": costs,
        "stats": stats,
        "passedVsFailed": split,
    }


def _fmt(value: int | float | None) -> str:
    return "unavailable" if value is None else f"{value:,.0f}"


def _fmt_usd(value: int | float | None) -> str:
    return "unavailable" if value is None else "$" + f"{value:,.6f}"


def _print_accounting(usage: dict[str, Any], *, details: bool = False) -> None:
    print(
        f"  observed subtotal: in {_fmt(usage['observedInputTokens'])}"
        f"  out {_fmt(usage['observedOutputTokens'])}"
        f"  cost {_fmt_usd(usage['observedCostUsd'])}"
    )
    print(
        f"  complete totals: in {_fmt(usage['inputTokens'])}"
        f"  out {_fmt(usage['outputTokens'])}  cost {_fmt_usd(usage['costUsd'])}"
    )
    print(
        f"  token coverage {usage['tokenCoverage']}; reports {usage['tokenReportTurns']}/{usage['turns']}"
        f" turns (complete {usage['completeTokenTurns']}, partial {usage['partialTokenTurns']},"
        f" missing {usage['missingTokenTurns']})"
    )
    print(
        f"  cost coverage {usage['costCoverage']}; reports {usage['costReportTurns']}/{usage['turns']}"
        f" turns; sources {', '.join(usage['costSources']) or 'unavailable'}"
    )
    if not details:
        return
    for side, fields in TOKEN_FIELDS.items():
        for field in fields:
            if field == "total":
                continue
            detail = usage["tokenDetails"][f"{side}.{field}"]
            print(
                f"    {side}.{field}: {_fmt(detail['observed'])}"
                f" (reported {detail['reportedTurns']}/{usage['turns']} turns)"
            )
    if usage["modelUsage"]:
        print(
            f"  reported model records ({usage['modelRecordTurns']}/{usage['turns']} turns;"
            " already included above, not additional usage):"
        )
        for model in usage["modelUsage"]:
            print(
                f"    {model['model'] or 'unreported model'}"
                f" [{model['provider'] or 'unreported provider'}]:"
                f" in {_fmt(model['observedInputTokens'])}"
                f" out {_fmt(model['observedOutputTokens'])}"
                f" cost {_fmt_usd(model['observedCostUsd'])}"
                f" ({model['costRecords']}/{model['records']} records report cost;"
                f" {', '.join(model['costSources']) or 'unavailable'})"
            )


def print_report(report: dict[str, Any]) -> None:
    print(f"# Token usage — {report['jobDir']}")
    print(f"trials with usage: {len(report['trials'])}; excluded: {len(report['skippedTrials'])}")
    if report["skippedTrials"]:
        print("Excluded trials: " + ", ".join(report["skippedTrials"]))
    print("Input includes cacheRead/cacheWrite; output includes reasoning. Do not add subsets again.")
    print("Partial = observed scope only. Missing = unknown, never zero. Costs are USD.")
    print("agent-estimate / account-estimate are estimates, not bills; no API-rate estimate is added.")
    print("\n## Job usage (all roles)")
    _print_accounting(report["jobTotals"])
    for role, usage in report["totals"].items():
        print(f"\n## {role} (configured: {report['roleModels'].get(role, '?')})")
        _print_accounting(usage, details=True)
        print(
            f"  turns {usage['turns']}; toolUses {usage['toolUses']};"
            f" Agent turn time {usage['wallMs'] / 60000:.2f} min"
        )
    print("\n## Per-trial / per-turn usage")
    print("Turn numbers are per role; complete and partial both describe the reported token scope.")
    for row in report["trials"]:
        print(f"\n{row['trial']} reward={row['reward']}")
        for role, usage in row["usage"].items():
            for index, native in enumerate(usage["usageReports"], 1):
                turn = _accounting([native])
                print(
                    f"  {role} turn {index}: tokens={turn['tokenCoverage']}"
                    f" in {_fmt(turn['observedInputTokens'])} out {_fmt(turn['observedOutputTokens'])}"
                    f" cost {_fmt_usd(turn['observedCostUsd'])}"
                    f" source={', '.join(turn['costSources']) or 'unavailable'}"
                )
    print("\n## Per-trial observed subtotal statistics")
    print("Only trials reporting each metric enter its statistics; these are not complete-job totals.")
    for role, metrics in report["stats"].items():
        print(f"  {role}")
        for metric, values in metrics.items():
            if not values:
                print(f"    {metric}: unavailable (n=0)")
                continue
            formatter = _fmt_usd if metric == "observedCostUsd" else _fmt
            print(
                f"    {metric}: n={values['samples']} mean {formatter(values['mean'])}"
                f" median {formatter(values['median'])} p90 {formatter(values['p90'])}"
                f" min {formatter(values['min'])} max {formatter(values['max'])}"
            )
    print("\n## Passed / failed / unscored trials (observed means)")
    for group, roles in report["passedVsFailed"].items():
        for role, values in roles.items():
            print(
                f"  {group} {role}: trials={values['trials']}"
                f" in {_fmt(values['meanObservedInput'])} (n={values['meanObservedInputSamples']})"
                f" out {_fmt(values['meanObservedOutput'])} (n={values['meanObservedOutputSamples']})"
                f" cost {_fmt_usd(values['meanCostUsd'])} (n={values['meanCostUsdSamples']})"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("job_dir", type=Path, help="Pier job directory")
    parser.add_argument("--json", action="store_true", help="emit structured report JSON")
    args = parser.parse_args(argv)
    job_dir = args.job_dir.expanduser().resolve()
    if not job_dir.is_dir():
        print(f"not a directory: {job_dir}", file=sys.stderr)
        return 2
    try:
        report = build_report(job_dir)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not report["trials"]:
        print(f"no trials with usage found in {job_dir}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
