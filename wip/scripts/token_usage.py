#!/usr/bin/env python3
"""Per-model token usage report for a Pier job directory.

Reads each trial's ``agent/system/summary.json`` (``result.usage``, the only
per-role source of truth) plus the trial/job ``result.json``, and prints:

1. job-level totals per model (role);
2. a per-trial table;
3. distribution statistics (mean/median/min/max/p90) per model;
4. passed-vs-failed trial comparison and the Pier job-level mixed-semantics
   figure for reference.

Current summaries preserve inclusive input/output totals, cache/reasoning subsets,
coverage and per-invocation cligent reports. Partial accounting is an observed
subtotal, not a complete job total. Upstream cost and its provenance are retained;
new-schema usage without an upstream cost is not priced from an assumed model or
missing cache dimensions. Historical flat summaries retain their explicit,
labelled API-rate estimate for backwards compatibility.

Usage (from the ``wip`` directory)::

    uv run python scripts/token_usage.py ../jobs/<job-name> [--json]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any


TOKEN_USAGE_KEYS = ("inputTokens", "outputTokens")
OPERATIONAL_USAGE_KEYS = ("toolUses", "turns", "wallMs")
USAGE_KEYS = TOKEN_USAGE_KEYS + OPERATIONAL_USAGE_KEYS
OPTIONAL_USAGE_KEYS = ("cacheTokens",)
DEFAULT_PRICING_PATH = Path(__file__).resolve().parents[1] / "data" / "model-pricing.json"


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _role_specs(job_dir: Path) -> dict[str, dict[str, str]]:
    """Map role to its adapter, model, and display label from the execution plan."""
    config = _load_json(job_dir / "config.json") or {}
    plan: dict[str, Any] = {}
    agents = config.get("agents") or []
    if isinstance(agents, list) and agents:
        plan = (
            agents[0].get("kwargs", {}).get("execution_plan_json", {})
            if isinstance(agents[0], dict)
            else {}
        )
    role_specs = {}
    for role, spec in (plan.get("roles") or {}).items():
        if isinstance(spec, dict):
            adapter = str(spec.get("adapter", role))
            model = str(spec.get("model", "?"))
            role_specs[role] = {
                "adapter": adapter,
                "model": model,
                "label": f"{adapter}/{model}",
            }
    return role_specs


def _load_pricing(path: Path) -> dict[str, Any]:
    pricing = _load_json(path)
    if not isinstance(pricing, dict) or not isinstance(pricing.get("models"), dict):
        raise ValueError(f"invalid model pricing file: {path}")
    unit_tokens = pricing.get("unitTokens")
    if not isinstance(unit_tokens, int) or unit_tokens <= 0:
        raise ValueError(f"invalid unitTokens in model pricing file: {path}")
    return pricing


def _pricing_index(pricing: dict[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    index: dict[str, tuple[str, dict[str, Any]]] = {}
    for canonical, spec in pricing["models"].items():
        if not isinstance(canonical, str) or not isinstance(spec, dict):
            continue
        index[canonical] = (canonical, spec)
        for alias in spec.get("aliases") or []:
            if isinstance(alias, str):
                index[alias] = (canonical, spec)
    return index


def _model_price(
    model: str, pricing: dict[str, Any]
) -> tuple[str, dict[str, Any], dict[str, Any]] | None:
    index = _pricing_index(pricing)
    match = index.get(model)
    if match is None and "/" in model:
        match = index.get(model.rsplit("/", 1)[-1])
    if match is None:
        return None
    canonical, spec = match
    tier = pricing.get("defaultTier", "standard")
    context = pricing.get("defaultContext", "shortContext")
    rates = (spec.get(tier) or {}).get(context)
    if not isinstance(rates, dict):
        return None
    if not isinstance(rates.get("input"), (int, float)) or not isinstance(
        rates.get("output"), (int, float)
    ):
        return None
    return canonical, spec, rates


def _usage_cost(
    usage: dict[str, Any], model: str, pricing: dict[str, Any]
) -> dict[str, Any] | None:
    if usage.get("usageSchema") == 2:
        reports = usage.get("usageReports") or []
        costs = [
            report["cost"] for report in reports if isinstance(report, dict) and report.get("cost")
        ]
        if not costs:
            return None
        models = sorted(
            {
                record["model"]
                for report in reports
                if isinstance(report, dict)
                for record in (report.get("tokens") or {}).get("records", [])
                if isinstance(record.get("model"), str)
            }
        )
        return {
            "model": ", ".join(models) if models else None,
            "models": models,
            "inputUsd": None,
            "cacheUsd": None,
            "outputUsd": None,
            "totalUsd": sum(cost["amount"] for cost in costs),
            "estimated": any(cost["source"] != "provider-reported" for cost in costs),
            "sources": sorted({cost["source"] for cost in costs}),
            "coverage": "complete" if len(costs) == len(reports) else "partial",
            "breakdownUsd": {"in": None, "cache": None, "out": None},
        }
    if usage.get("tokenAvailability") != "reported":
        return None
    if not all(isinstance(usage.get(key), int) for key in TOKEN_USAGE_KEYS):
        return None
    match = _model_price(model, pricing)
    if match is None:
        return None
    canonical, spec, rates = match
    unit = pricing["unitTokens"]
    cache_tokens = max(0, usage.get("cacheTokens", 0))
    input_tokens = max(0, usage["inputTokens"] - cache_tokens)
    input_usd = input_tokens * rates["input"] / unit
    cache_rate = rates.get("cachedInput")
    cache_usd = (
        cache_tokens * cache_rate / unit
        if cache_tokens and isinstance(cache_rate, (int, float))
        else None
    )
    output_usd = usage["outputTokens"] * rates["output"] / unit
    total_usd = input_usd + (cache_usd or 0) + output_usd
    return {
        "model": canonical,
        "provider": spec.get("provider"),
        "inputUsd": round(input_usd, 12),
        "cacheUsd": round(cache_usd, 12) if cache_usd is not None else None,
        "outputUsd": round(output_usd, 12),
        "totalUsd": round(total_usd, 12),
        "breakdownUsd": {
            "in": round(input_usd, 12),
            "cache": round(cache_usd, 12) if cache_usd is not None else None,
            "out": round(output_usd, 12),
        },
        "tokensPriced": {
            "in": input_tokens,
            "cache": cache_tokens if cache_tokens else None,
            "out": usage["outputTokens"],
        },
        "estimated": True,
        "rates": {
            "inputPerMillion": rates["input"],
            "cachedInputPerMillion": cache_rate,
            "outputPerMillion": rates["output"],
        },
    }


def _trial_rows(job_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    skipped: list[str] = []
    for trial_dir in sorted(job_dir.iterdir()):
        if not trial_dir.is_dir() or trial_dir.name.startswith("."):
            continue
        if trial_dir.name == "patch-scores":
            continue
        result = _load_json(trial_dir / "result.json")
        if result is None:
            skipped.append(f"{trial_dir.name} (no result.json)")
            continue
        summary = _load_json(trial_dir / "agent" / "system" / "summary.json")
        usage = ((summary or {}).get("result") or {}).get("usage")
        if not isinstance(usage, dict):
            skipped.append(f"{trial_dir.name} (no usage in summary.json)")
            continue
        rewards = (result.get("verifier_result") or {}).get("rewards") or {}
        row: dict[str, Any] = {
            "trial": trial_dir.name,
            "reward": rewards.get("reward"),
            "outcome": ((summary or {}).get("result") or {}).get("outcome"),
            "usage": {},
        }
        for role, spec in usage.items():
            if not isinstance(spec, dict):
                continue
            turns = int(spec.get("turns") or 0)
            if turns <= 0:
                continue
            token_availability = (
                "reported"
                if spec.get("tokenAvailability") == "reported"
                and all(isinstance(spec.get(key), int) for key in TOKEN_USAGE_KEYS)
                else "unavailable"
            )
            role_usage = {
                "tokenAvailability": token_availability,
                "inputTokens": (
                    int(spec.get("inputTokens") or 0) if token_availability == "reported" else None
                ),
                "outputTokens": (
                    int(spec.get("outputTokens") or 0) if token_availability == "reported" else None
                ),
                "toolUses": int(spec.get("toolUses") or 0),
                "turns": turns,
                "wallMs": int(spec.get("wallMs") or 0),
            }
            for key in OPTIONAL_USAGE_KEYS:
                if key in spec and spec[key] is not None:
                    role_usage[key] = spec[key] or 0
            for key in (
                "usageSchema",
                "tokens",
                "tokenCoverage",
                "costCoverage",
                "usageReports",
                "costUsd",
            ):
                if key in spec:
                    role_usage[key] = spec[key]
            row["usage"][role] = role_usage
        rows.append(row)
    return rows, skipped


def _totals(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    totals: dict[str, dict[str, Any]] = {}
    for row in rows:
        for role, spec in row["usage"].items():
            bucket = totals.setdefault(
                role,
                {
                    "tokenAvailability": "reported",
                    "inputTokens": 0,
                    "outputTokens": 0,
                    "reportedInputTokens": 0,
                    "reportedOutputTokens": 0,
                    "reportedTokenTrials": 0,
                    "unavailableTokenTrials": 0,
                    **{key: 0 for key in OPERATIONAL_USAGE_KEYS},
                },
            )
            for key in OPERATIONAL_USAGE_KEYS:
                bucket[key] += spec[key]
            if spec["tokenAvailability"] == "reported":
                bucket["reportedInputTokens"] += spec["inputTokens"]
                bucket["reportedOutputTokens"] += spec["outputTokens"]
                bucket["reportedTokenTrials"] += 1
                for key in OPTIONAL_USAGE_KEYS:
                    if key in spec:
                        bucket[key] = bucket.get(key, 0) + spec[key]
            else:
                bucket["unavailableTokenTrials"] += 1
    for bucket in totals.values():
        if bucket["unavailableTokenTrials"]:
            bucket["tokenAvailability"] = "unavailable"
            bucket["inputTokens"] = None
            bucket["outputTokens"] = None
        else:
            bucket["inputTokens"] = bucket["reportedInputTokens"]
            bucket["outputTokens"] = bucket["reportedOutputTokens"]
    for role, bucket in totals.items():
        specs = [row["usage"][role] for row in rows if role in row["usage"]]
        if any(spec.get("usageSchema") == 2 for spec in specs):
            bucket["usageSchema"] = 2
            bucket["usageReports"] = [
                report
                for spec in specs
                for report in (spec.get("usageReports") or [None] * spec["turns"])
            ]
            observed = [
                report["tokens"]
                for report in bucket["usageReports"]
                if isinstance(report, dict) and report.get("tokens")
            ]
            bucket["tokenCoverage"] = (
                "complete"
                if len(observed) == len(bucket["usageReports"])
                and all(report["coverage"] == "complete" for report in observed)
                else "partial"
                if observed
                else "unavailable"
            )
            # Observed subtotals survive even when another turn has no accounting.
            bucket["observedInputTokens"] = (
                sum(report["totals"]["input"]["total"] for report in observed) if observed else None
            )
            bucket["observedOutputTokens"] = (
                sum(report["totals"]["output"]["total"] for report in observed)
                if observed
                else None
            )
    return totals


def _stats(values: list[int | float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    p90_index = max(0, int(round(0.9 * (len(ordered) - 1))))
    return {
        "mean": statistics.mean(ordered),
        "median": statistics.median(ordered),
        "min": ordered[0],
        "max": ordered[-1],
        "p90": ordered[p90_index],
    }


def _fmt(value: float) -> str:
    return f"{value:,.0f}"


def _fmt_usd(value: float | None) -> str:
    return "n/a" if value is None else f"${value:,.6f}"


def build_report(job_dir: Path, pricing_path: Path = DEFAULT_PRICING_PATH) -> dict[str, Any]:
    role_specs = _role_specs(job_dir)
    labels = {role: spec["label"] for role, spec in role_specs.items()}
    models = {role: spec["model"] for role, spec in role_specs.items()}
    rows, skipped = _trial_rows(job_dir)
    job_result = _load_json(job_dir / "result.json") or {}
    job_stats = job_result.get("stats") or {}
    pricing = _load_pricing(pricing_path)
    totals = _totals(rows)

    for row in rows:
        row["costs"] = {
            role: cost
            for role, usage in row["usage"].items()
            if (cost := _usage_cost(usage, models.get(role, "?"), pricing)) is not None
        }

    costs = {
        role: cost
        for role, usage in totals.items()
        if (cost := _usage_cost(usage, models.get(role, "?"), pricing)) is not None
    }

    per_role_stats: dict[str, dict[str, dict[str, float]]] = {}
    for role in totals:
        per_role_stats[role] = {
            "inputTokens": _stats(
                [
                    r["usage"][role]["inputTokens"]
                    for r in rows
                    if role in r["usage"] and r["usage"][role]["tokenAvailability"] == "reported"
                ]
            ),
            "outputTokens": _stats(
                [
                    r["usage"][role]["outputTokens"]
                    for r in rows
                    if role in r["usage"] and r["usage"][role]["tokenAvailability"] == "reported"
                ]
            ),
            "wallMs": _stats([r["usage"][role]["wallMs"] for r in rows if role in r["usage"]]),
            "costInUsd": _stats(
                [
                    r["costs"][role]["inputUsd"]
                    for r in rows
                    if role in r["costs"] and r["costs"][role]["inputUsd"] is not None
                ]
            ),
            "costCacheUsd": _stats(
                [
                    r["costs"][role]["cacheUsd"]
                    for r in rows
                    if role in r["costs"] and r["costs"][role]["cacheUsd"] is not None
                ]
            ),
            "costOutUsd": _stats(
                [
                    r["costs"][role]["outputUsd"]
                    for r in rows
                    if role in r["costs"] and r["costs"][role]["outputUsd"] is not None
                ]
            ),
            "costTotalUsd": _stats(
                [r["costs"][role]["totalUsd"] for r in rows if role in r["costs"]]
            ),
        }

    def _split_totals(predicate) -> dict[str, dict[str, float]]:
        subset = [r for r in rows if predicate(r)]
        out: dict[str, dict[str, float]] = {}
        for role in totals:
            reported = [
                r["usage"][role]
                for r in subset
                if role in r["usage"] and r["usage"][role]["tokenAvailability"] == "reported"
            ]
            values = [usage["inputTokens"] for usage in reported]
            outs = [usage["outputTokens"] for usage in reported]
            if values:
                bucket = {
                    "trials": len(values),
                    "meanInput": statistics.mean(values),
                    "meanOutput": statistics.mean(outs),
                }
                trial_costs = [r["costs"][role]["totalUsd"] for r in subset if role in r["costs"]]
                if trial_costs:
                    bucket["meanCostUsd"] = statistics.mean(trial_costs)
                out[role] = bucket
        return out

    return {
        "jobDir": str(job_dir),
        "roleModels": labels,
        "roleModelIds": models,
        "trials": rows,
        "skippedTrials": skipped,
        "totals": totals,
        "costs": costs,
        "pricing": {
            "path": str(pricing_path),
            "currency": pricing.get("currency", "USD"),
            "unitTokens": pricing["unitTokens"],
            "tier": pricing.get("defaultTier", "standard"),
            "context": pricing.get("defaultContext", "shortContext"),
            "updatedAt": pricing.get("updatedAt"),
            "unpricedRoles": [
                role
                for role in totals
                if (
                    role not in costs
                    if totals[role].get("usageSchema") == 2
                    else _model_price(models.get(role, "?"), pricing) is None
                )
            ],
            "unavailableTokenRoles": [
                role for role, usage in totals.items() if usage["tokenAvailability"] != "reported"
            ],
            "partialTokenRoles": [
                role for role, usage in totals.items() if usage.get("tokenCoverage") == "partial"
            ],
            "partialCostRoles": [
                role for role, cost in costs.items() if cost.get("coverage") == "partial"
            ],
            "estimateBasis": (
                "New-schema costs come only from upstream reports with their source and coverage; "
                "no model/cache price is inferred. Historical flat summaries: "
                "cacheTokens, when present, are priced as cached input and subtracted from "
                "inputTokens; otherwise cache cost is null and all aggregate inputTokens use "
                "the base input rate. Per-request long-context tiers are not applied."
            ),
        },
        "stats": per_role_stats,
        "passedVsFailed": {
            "passed": _split_totals(lambda r: r["reward"] == 1),
            "failed": _split_totals(lambda r: r["reward"] in (0, None)),
        },
        "pierJobLevel": {
            "inputTokens": job_stats.get("n_input_tokens"),
            "outputTokens": job_stats.get("n_output_tokens"),
            "costUsd": job_stats.get("cost_usd"),
        },
    }


def print_report(report: dict[str, Any]) -> None:
    labels = report["roleModels"]
    rows = report["trials"]

    def name(role: str) -> str:
        return f"{role} (configured: {labels.get(role, '?')})"

    print(f"# Token usage — {report['jobDir']}")
    print(f"trials with usage: {len(rows)}", end="")
    if report["skippedTrials"]:
        print(f"; skipped: {', '.join(report['skippedTrials'])}", end="")
    print("\n")

    print("## Job totals per role")
    for role, t in report["totals"].items():
        wall_h = t["wallMs"] / 3_600_000
        cost = report["costs"].get(role)
        cost_text = (
            f"  cost in {_fmt_usd(cost['inputUsd']):>13s}"
            f"  cache {(_fmt_usd(cost['cacheUsd']) if cost['cacheUsd'] is not None else ''):>13s}"
            f"  out {_fmt_usd(cost['outputUsd']):>13s}"
            f"  total {_fmt_usd(cost['totalUsd']):>13s}"
            if cost
            else "  cost n/a"
        )
        input_text = (
            _fmt(t["inputTokens"]) if t["tokenAvailability"] == "reported" else "unavailable"
        )
        output_text = (
            _fmt(t["outputTokens"]) if t["tokenAvailability"] == "reported" else "unavailable"
        )
        availability_text = (
            f"  token trials reported {t['reportedTokenTrials']}"
            f" unavailable {t['unavailableTokenTrials']}"
        )
        print(
            f"  {name(role):48s} in {input_text:>15s}  out {output_text:>11s}"
            f"{cost_text}  toolUses {t['toolUses']:>5d}  turns {t['turns']:>3d}"
            f"  token coverage {t.get('tokenCoverage', 'legacy unknown')}"
            f"  cost coverage {(cost or {}).get('coverage', 'legacy estimate')}"
            f"  wall {wall_h:.1f}h{availability_text}"
        )
        if t.get("usageSchema") == 2:
            print(
                f"    observed subtotal: in {t.get('observedInputTokens')} out {t.get('observedOutputTokens')}; "
                f"cost sources {', '.join((cost or {}).get('sources', [])) or 'unavailable'}"
            )
    pier = report["pierJobLevel"]
    if pier.get("inputTokens") is not None:
        print(
            f"  {'pier job-level (mixed semantics, not per-model)':48s}"
            f" in {_fmt(pier['inputTokens']):>15s}  out {_fmt(pier['outputTokens']):>11s}"
            f"  cost {pier.get('costUsd')}"
        )

    print("\n## Per-trial usage")
    roles = list(report["totals"])
    header = f"  {'trial':44s} {'reward':>6s}"
    for role in roles:
        header += (
            f" {role + ' in':>14s} {role + ' out':>12s}"
            f" {role + ' in$':>14s} {role + ' cache$':>14s}"
            f" {role + ' out$':>14s} {role + ' total$':>14s}"
        )
    print(header)
    for row in rows:
        line = f"  {row['trial'][:44]:44s} {str(row['reward']):>6s}"
        for role in roles:
            spec = row["usage"].get(role)
            if spec and spec["tokenAvailability"] == "reported":
                line += f" {_fmt(spec['inputTokens']):>14s}" f" {_fmt(spec['outputTokens']):>12s}"
            elif spec:
                line += f" {'unavailable':>14s} {'unavailable':>12s}"
            else:
                line += f" {'-':>14s} {'-':>12s}"
            cost = row["costs"].get(role)
            if cost:
                cache_text = _fmt_usd(cost["cacheUsd"]) if cost["cacheUsd"] is not None else ""
                line += (
                    f" {_fmt_usd(cost['inputUsd']):>14s} {cache_text:>14s}"
                    f" {_fmt_usd(cost['outputUsd']):>14s} {_fmt_usd(cost['totalUsd']):>14s}"
                )
            else:
                line += f" {'n/a':>14s} {'':>14s} {'':>14s} {'':>14s}"
        print(line)

        if any(spec.get("usageSchema") == 2 for spec in row["usage"].values()):
            print(
                "    coverage: "
                + "; ".join(
                    f"{role} tokens={spec.get('tokenCoverage', 'legacy unknown')} "
                    f"cost={(row['costs'].get(role) or {}).get('coverage', 'unavailable')}"
                    for role, spec in row["usage"].items()
                )
            )

    print("\n## Per-trial distribution stats")
    for role, metrics in report["stats"].items():
        print(f"  {name(role)}")
        has_cost_stats = any(
            metrics[metric] for metric in ("costInUsd", "costOutUsd", "costTotalUsd")
        )
        for metric, st in metrics.items():
            if not st:
                if metric == "costCacheUsd" and has_cost_stats:
                    print(f"    {metric:13s}")
                continue
            is_cost = metric.startswith("cost") and metric.endswith("Usd")
            unit = " min" if metric == "wallMs" else (" USD" if is_cost else "")
            scale = 60000 if metric == "wallMs" else 1
            formatter = _fmt_usd if is_cost else _fmt
            print(
                f"    {metric:13s} mean {formatter(st['mean']/scale):>12s}{unit}"
                f"  median {formatter(st['median']/scale):>12s}{unit}"
                f"  p90 {formatter(st['p90']/scale):>12s}{unit}"
                f"  min {formatter(st['min']/scale):>10s}{unit}"
                f"  max {formatter(st['max']/scale):>12s}{unit}"
            )

    print("\n## Passed vs failed trials (mean per trial)")
    for bucket, per_role in report["passedVsFailed"].items():
        for role, st in per_role.items():
            cost_text = (
                f"  mean cost {_fmt_usd(st['meanCostUsd']):>13s}"
                if "meanCostUsd" in st
                else "  mean cost           n/a"
            )
            print(
                f"  {bucket:6s} {name(role):48s} n={st['trials']:<3d}"
                f" mean in {_fmt(st['meanInput']):>14s}  mean out {_fmt(st['meanOutput']):>11s}"
                f"{cost_text}"
            )

    print(
        "\nCaveats: new-schema input/output totals include reported cache/reasoning subsets."
        " Partial coverage is an observed subtotal, not complete spend. Missing details remain unknown."
        " Upstream costs retain their sources (including agent-estimate); these are not necessarily bills."
        " New usage without a cost report is not priced using an assumed role model or cache split."
        " Historical flat summaries use a labelled API-rate estimate with standard short-context rates;"
        " missing cache details are not reconstructed. Tool uses, turns and wall time remain independent."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_dir", type=Path, help="Pier job directory")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument(
        "--pricing",
        type=Path,
        default=DEFAULT_PRICING_PATH,
        help=f"model pricing JSON (default: {DEFAULT_PRICING_PATH})",
    )
    args = parser.parse_args(argv)

    job_dir = args.job_dir.expanduser().resolve()
    if not job_dir.is_dir():
        print(f"not a directory: {job_dir}", file=sys.stderr)
        return 2
    pricing_path = args.pricing.expanduser().resolve()
    try:
        report = build_report(job_dir, pricing_path)
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
