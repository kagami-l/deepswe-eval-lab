#!/usr/bin/env python3
"""Report current cligent accounting from DeepSWE job summaries.

Only usageSchema=2 with one usageReports slot per turn is accepted. Native
input/output totals include cache/reasoning subsets. Partial reports are observed
subtotals, not complete totals. Prefer cligent terminal cost; otherwise call its
estimateCost API. Preserve raw reports and separate reported/estimated subtotals.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import subprocess
from pathlib import Path
from typing import Any

TOKEN_FIELDS = {
    "input": ("total", "uncached", "cacheRead", "cacheWrite"),
    "output": ("total", "visible", "reasoning"),
}
COST_SOURCES = {"provider-reported", "agent-estimate", "account-estimate"}



RUNTIME_DIR = Path(__file__).resolve().parents[1] / "agents/deep_swe_agent/runtime"


def _estimate_costs(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Delegate pricing, cache handling and arithmetic to the pinned cligent API."""
    if not requests:
        return []
    try:
        process = subprocess.run(
            ["node", "--input-type=module", "--eval",
             Path(__file__).with_name("token_usage_cost.mjs").read_text()],
            cwd=RUNTIME_DIR, input=json.dumps(requests), capture_output=True,
            text=True, timeout=60, check=True,
        )
        results = json.loads(process.stdout)
        if not isinstance(results, list) or len(results) != len(requests):
            raise ValueError("cligent returned an invalid estimate batch")
        for result in results:
            if not isinstance(result, dict) or result.get("status") not in {"estimated", "unavailable"}:
                raise ValueError("cligent returned an invalid estimate result")
            if result["status"] == "estimated" and (
                not _number(result.get("amount")) or result.get("currency") != "USD"
                or result.get("coverage") not in {"complete", "partial"}
            ):
                raise ValueError("cligent returned an invalid estimate amount/coverage")
        return results
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        # Cost lookup must not discard otherwise valid token/native-cost reports.
        message = str(exc)
        if isinstance(exc, subprocess.CalledProcessError):
            message = exc.stderr.strip() or message
        return [{"status": "unavailable", "reason": "estimator-unavailable",
                 "message": message} for _ in requests]


def _native_cost_resolution(report: dict[str, Any] | None) -> dict[str, Any]:
    if report is not None and "cost" in report:
        return {"kind": "reported", "cost": report["cost"]}
    return {"kind": "unavailable", "estimate": {
        "status": "unavailable", "reason": "not-estimated",
        "message": "No cligent cost estimate was requested for this accounting view.",
    }}


def _cost_amount(resolution: dict[str, Any]) -> float | None:
    if resolution["kind"] == "reported":
        return resolution["cost"]["amount"]
    if resolution["kind"] == "estimated":
        return resolution["estimate"]["amount"]
    return None


def _cost_source(resolution: dict[str, Any]) -> str | None:
    if resolution["kind"] == "reported":
        return resolution["cost"]["source"]
    if resolution["kind"] == "estimated":
        return "cligent-estimate"
    return None


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
    reports: list[dict[str, Any] | None], *, tool_uses: int = 0, wall_ms: int = 0,
    cost_resolutions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    tokens = [r["tokens"] for r in reports if r is not None and "tokens" in r]
    resolutions = cost_resolutions if cost_resolutions is not None else [
        _native_cost_resolution(r) for r in reports
    ]
    assert len(resolutions) == len(reports)
    available_costs = [r for r in resolutions if _cost_amount(r) is not None]
    reported_costs = [r for r in resolutions if r["kind"] == "reported"]
    estimated_costs = [r for r in resolutions if r["kind"] == "estimated"]
    token_coverage = _coverage(
        len(tokens), len(reports), all(t["coverage"] == "complete" for t in tokens)
    )
    cost_coverage = _coverage(
        len(available_costs), len(reports),
        all(r["estimate"]["coverage"] == "complete" for r in estimated_costs),
    )
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
    observed_cost = _sum_known([_cost_amount(r) for r in available_costs])
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
        "costResolutions": resolutions,
        "costReportTurns": len(reported_costs),
        "costEstimateTurns": len(estimated_costs),
        "costAvailableTurns": len(available_costs),
        "partialCostEstimateTurns": sum(
            r["estimate"]["coverage"] == "partial" for r in estimated_costs
        ),
        "missingCostTurns": len(reports) - len(available_costs),
        "reportedCostUsd": _sum_known([_cost_amount(r) for r in reported_costs]),
        "estimatedCostUsd": _sum_known([_cost_amount(r) for r in estimated_costs]),
        "observedCostUsd": observed_cost,
        "costUsd": observed_cost if cost_coverage == "complete" else None,
        "costSources": sorted({_cost_source(r) for r in available_costs}),
        "modelRecordTurns": sum("records" in t for t in tokens),
        "modelUsage": _model_usage(reports),
    }


def _usage_cost(usage: dict[str, Any]) -> dict[str, Any] | None:
    accounting = _accounting(_reports(usage, "usage"), cost_resolutions=usage.get("costResolutions"))
    if accounting["observedCostUsd"] is None:
        return None
    models = sorted({m["model"] for m in accounting["modelUsage"] if m["model"] is not None})
    return {
        "models": models,
        "totalUsd": accounting["observedCostUsd"],
        "completeTotalUsd": accounting["costUsd"],
        "reportedUsd": accounting["reportedCostUsd"],
        "estimatedUsd": accounting["estimatedCostUsd"],
        "sources": accounting["costSources"],
        "coverage": accounting["costCoverage"],
        "estimated": any(s != "provider-reported" for s in accounting["costSources"]),
    }


def _trial_rows(
    job_dir: Path, cost_options: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], dict[str, str]]:
    rows, skipped, labels = [], [], {}
    requests, pending = [], []
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
            options = {key: identity[key] for key in ("model", "provider") if identity.get(key)}
            options.update(cost_options.get("*", {}))
            options.update(cost_options.get(role, {}))
            for index, report in enumerate(reports):
                if report is not None and "cost" in report:
                    continue  # A genuine zero cost is authoritative too.
                requests.append({"usage": report if report is not None else {"toolUses": 0},
                                 "options": options})
                pending.append((role_usage, role, index))
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
    for (usages, role, index), estimate in zip(pending, _estimate_costs(requests), strict=True):
        usages[role]["costResolutions"][index] = {
            "kind": "estimated" if estimate["status"] == "estimated" else "unavailable",
            "estimate": estimate,
        }
    for row in rows:
        for role, usage in row["usage"].items():
            row["usage"][role] = _accounting(
                usage["usageReports"], tool_uses=usage["toolUses"], wall_ms=usage["wallMs"],
                cost_resolutions=usage["costResolutions"],
            )
    return rows, skipped, labels


def _aggregate(usages: list[dict[str, Any]]) -> dict[str, Any]:
    return _accounting(
        [r for u in usages for r in u["usageReports"]],
        tool_uses=sum(u["toolUses"] for u in usages),
        wall_ms=sum(u["wallMs"] for u in usages),
        cost_resolutions=[r for u in usages for r in u["costResolutions"]],
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


def build_report(
    job_dir: Path, *, cost_options: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows, skipped, labels = _trial_rows(job_dir, cost_options or {})
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
        "reportSchemaVersion": 3,
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
        f"  available subtotal: in {_fmt(usage['observedInputTokens'])}"
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
        f"  cost coverage {usage['costCoverage']}; reported {usage['costReportTurns']},"
        f" estimated {usage['costEstimateTurns']}, missing {usage['missingCostTurns']}"
        f" / {usage['turns']} turns; sources {', '.join(usage['costSources']) or 'unavailable'}"
    )
    print(
        f"  cost split: reported {_fmt_usd(usage['reportedCostUsd'])};"
        f" cligent-estimated {_fmt_usd(usage['estimatedCostUsd'])}"
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
            " detail only; not added to totals):"
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
    print("Cost priority: cligent reported cost, then cligent estimateCost(); no agent-specific pricing.")
    print("agent-estimate / account-estimate / cligent-estimate are estimates, not bills.")
    print("Cost totals may combine reported and estimated amounts; complete describes scope, not billing certainty.")
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
                resolution = usage["costResolutions"][index - 1]
                turn = _accounting([native], cost_resolutions=[resolution])
                print(
                    f"  {role} turn {index}: tokens={turn['tokenCoverage']}"
                    f" in {_fmt(turn['observedInputTokens'])} out {_fmt(turn['observedOutputTokens'])}"
                    f" cost {_fmt_usd(turn['observedCostUsd'])} ({turn['costCoverage']})"
                    f" source={', '.join(turn['costSources']) or 'unavailable'}"
                )
                if resolution["kind"] == "unavailable":
                    estimate = resolution["estimate"]
                    print(f"    cost unavailable: {estimate['reason']}: {estimate['message']}")
                elif resolution["kind"] == "estimated":
                    estimate = resolution["estimate"]
                    print(f"    estimate source: {json.dumps(estimate['source'], sort_keys=True)}")
                    for record in estimate["records"]:
                        print(
                            f"    estimated {record.get('provider', '?')}/{record.get('model', '?')}:"
                            f" {_fmt_usd(record['amount'])}; USD/M token rates"
                            f" {json.dumps(record['prices'], sort_keys=True)}"
                        )
                    for assumption in estimate["assumptions"]:
                        print(f"    assumption: {assumption}")
    print("\n## Per-trial available subtotal statistics")
    print("Tokens are observed; costs follow the reported-then-estimated priority above.")
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
    parser.add_argument("--cost-provider", action="append", default=[], metavar="[ROLE=]PROVIDER",
                        help="cligent catalog pricing provider; optionally scoped to a role")
    parser.add_argument("--cost-prices", type=Path, metavar="JSON",
                        help="explicit cligent TokenPrices JSON (USD per million tokens)")
    parser.add_argument("--cost-cache", type=Path, metavar="PATH",
                        help="cligent pricing cache path (default: cligent OS cache)")
    args = parser.parse_args(argv)
    job_dir = args.job_dir.expanduser().resolve()
    if not job_dir.is_dir():
        print(f"not a directory: {job_dir}", file=sys.stderr)
        return 2
    try:
        options: dict[str, dict[str, Any]] = {"*": {}}
        for entry in args.cost_provider:
            role, provider = entry.split("=", 1) if "=" in entry else ("*", entry)
            if not role or not provider:
                raise ValueError("--cost-provider requires [ROLE=]PROVIDER")
            options.setdefault(role, {})["provider"] = provider
        if args.cost_prices:
            prices = _load_json(args.cost_prices.expanduser())
            if not isinstance(prices, dict):
                raise ValueError("--cost-prices must be a readable TokenPrices JSON object")
            options["*"]["prices"] = prices
        if args.cost_cache:
            options["*"]["cachePath"] = str(args.cost_cache.expanduser().resolve())
        report = build_report(job_dir, cost_options=options)
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
