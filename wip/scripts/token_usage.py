#!/usr/bin/env python3
"""Per-model token usage report for a Pier job directory.

Reads each trial's ``agent/system/summary.json`` (``result.usage``, the only
per-role source of truth) plus the trial/job ``result.json``, and prints:

1. job-level totals per model (role);
2. a per-trial table;
3. distribution statistics (mean/median/min/max/p90) per model;
4. passed-vs-failed trial comparison and the Pier job-level mixed-semantics
   figure for reference.

Caveats printed with the report: input tokens are NOT comparable across
adapters; cost is null for login-based adapters; interrupted attempts record
zero usage. No layer of the job records splits cached vs uncached tokens
(cligent flattens provider usage to three fields; pier's ``n_cache_tokens``
is never fed). Magnitude-based inference of what ``inputTokens`` contains,
per adapter (2026-08 records):

- codex: INCLUDES cache reads (cumulative full-context per call);
- claude: INCLUDES cache read/creation (same cumulative shape);
- opencode/deepseek: EXCLUDES cache hits (miss-only, ~100x smaller).

Output tokens carry no cache concept and are comparable across adapters.

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


USAGE_KEYS = ("inputTokens", "outputTokens", "toolUses", "turns", "wallMs")


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _role_labels(job_dir: Path) -> dict[str, str]:
    """Map role -> 'adapter/model' from the job config's execution plan."""
    config = _load_json(job_dir / "config.json") or {}
    plan: dict[str, Any] = {}
    agents = config.get("agents") or []
    if isinstance(agents, list) and agents:
        plan = (
            agents[0].get("kwargs", {}).get("execution_plan_json", {})
            if isinstance(agents[0], dict)
            else {}
        )
    labels = {}
    for role, spec in (plan.get("roles") or {}).items():
        if isinstance(spec, dict):
            labels[role] = f"{spec.get('adapter', role)}/{spec.get('model', '?')}"
    return labels


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
            "usage": {
                role: {key: (spec or {}).get(key, 0) or 0 for key in USAGE_KEYS}
                for role, spec in usage.items()
                if isinstance(spec, dict)
            },
        }
        rows.append(row)
    return rows, skipped


def _totals(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    for row in rows:
        for role, spec in row["usage"].items():
            bucket = totals.setdefault(role, {key: 0 for key in USAGE_KEYS})
            for key in USAGE_KEYS:
                bucket[key] += spec[key]
    return totals


def _stats(values: list[int]) -> dict[str, float]:
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


def build_report(job_dir: Path) -> dict[str, Any]:
    labels = _role_labels(job_dir)
    rows, skipped = _trial_rows(job_dir)
    job_result = _load_json(job_dir / "result.json") or {}
    job_stats = job_result.get("stats") or {}

    per_role_stats: dict[str, dict[str, dict[str, float]]] = {}
    for role in _totals(rows):
        per_role_stats[role] = {
            "inputTokens": _stats([r["usage"][role]["inputTokens"] for r in rows if role in r["usage"]]),
            "outputTokens": _stats([r["usage"][role]["outputTokens"] for r in rows if role in r["usage"]]),
            "wallMs": _stats([r["usage"][role]["wallMs"] for r in rows if role in r["usage"]]),
        }

    def _split_totals(predicate) -> dict[str, dict[str, float]]:
        subset = [r for r in rows if predicate(r)]
        out: dict[str, dict[str, float]] = {}
        for role in _totals(rows):
            values = [r["usage"][role]["inputTokens"] + 0 for r in subset if role in r["usage"]]
            outs = [r["usage"][role]["outputTokens"] for r in subset if role in r["usage"]]
            if values:
                out[role] = {
                    "trials": len(values),
                    "meanInput": statistics.mean(values),
                    "meanOutput": statistics.mean(outs),
                }
        return out

    return {
        "jobDir": str(job_dir),
        "roleModels": labels,
        "trials": rows,
        "skippedTrials": skipped,
        "totals": _totals(rows),
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
        return f"{role} ({labels.get(role, '?')})"

    print(f"# Token usage — {report['jobDir']}")
    print(f"trials with usage: {len(rows)}", end="")
    if report["skippedTrials"]:
        print(f"; skipped: {', '.join(report['skippedTrials'])}", end="")
    print("\n")

    print("## Job totals per model")
    for role, t in report["totals"].items():
        wall_h = t["wallMs"] / 3_600_000
        print(
            f"  {name(role):48s} in {_fmt(t['inputTokens']):>15s}  out {_fmt(t['outputTokens']):>11s}"
            f"  toolUses {t['toolUses']:>5d}  turns {t['turns']:>3d}  wall {wall_h:.1f}h"
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
        header += f" {role + ' in':>14s} {role + ' out':>12s}"
    print(header)
    for row in rows:
        line = f"  {row['trial'][:44]:44s} {str(row['reward']):>6s}"
        for role in roles:
            spec = row["usage"].get(role)
            line += (
                f" {_fmt(spec['inputTokens']):>14s} {_fmt(spec['outputTokens']):>12s}"
                if spec
                else f" {'-':>14s} {'-':>12s}"
            )
        print(line)

    print("\n## Per-trial distribution stats")
    for role, metrics in report["stats"].items():
        print(f"  {name(role)}")
        for metric, st in metrics.items():
            if not st:
                continue
            unit = " min" if metric == "wallMs" else ""
            scale = 60000 if metric == "wallMs" else 1
            print(
                f"    {metric:13s} mean {_fmt(st['mean']/scale):>12s}{unit}"
                f"  median {_fmt(st['median']/scale):>12s}{unit}"
                f"  p90 {_fmt(st['p90']/scale):>12s}{unit}"
                f"  min {_fmt(st['min']/scale):>10s}{unit}"
                f"  max {_fmt(st['max']/scale):>12s}{unit}"
            )

    print("\n## Passed vs failed trials (mean per trial)")
    for bucket, per_role in report["passedVsFailed"].items():
        for role, st in per_role.items():
            print(
                f"  {bucket:6s} {name(role):48s} n={st['trials']:<3d}"
                f" mean in {_fmt(st['meanInput']):>14s}  mean out {_fmt(st['meanOutput']):>11s}"
            )

    print(
        "\nCaveats: input tokens are not comparable across adapters; no record"
        " layer splits cached vs uncached. Magnitude-based inference: codex and"
        " claude inputTokens INCLUDE cache reads (cumulative full-context);"
        " opencode/deepseek EXCLUDES cache hits (miss-only, ~100x smaller"
        " numbers). Output tokens have no cache concept and are comparable."
        " Cost is null for login-based adapters; interrupted attempts record"
        " zero usage."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_dir", type=Path, help="Pier job directory")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)

    job_dir = args.job_dir.expanduser().resolve()
    if not job_dir.is_dir():
        print(f"not a directory: {job_dir}", file=sys.stderr)
        return 2
    report = build_report(job_dir)
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
