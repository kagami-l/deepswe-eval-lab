#!/usr/bin/env python3
"""Build reproducible, layered DeepSWE v1.1 task-selection outputs.

Only the Python standard library is required. The public trials all use
mini-swe-agent, so these results identify promising tasks for comparing complete
agent systems; they do not establish framework or collaboration effects.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import sys
import tomllib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_THRESHOLDS = {
    "minimum_model_coverage": 17,
    "minimum_effective_repeats_per_config": 3,
    "maximum_error_rate": 0.05,
    "maximum_verifier_timeouts": 1,
    "broad_difficulty_min": 0.20,
    "broad_difficulty_max": 0.80,
    "broad_low_model_max_pass_rate": 0.25,
    "broad_high_model_min_pass_rate": 0.75,
    "broad_minimum_low_models": 3,
    "broad_minimum_high_models": 3,
    "core_difficulty_min": 0.30,
    "core_difficulty_max": 0.70,
    "core_minimum_low_models": 4,
    "core_minimum_high_models": 4,
    "core_minimum_item_rest_correlation": 0.30,
    "scoring_sensitive_absolute_delta": 0.10,
}


def parse_args() -> argparse.Namespace:
    script = Path(__file__).resolve()
    repo = script.parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=repo / "wip/data/official-v1.1",
        help="directory containing the five official v1.1 JSON files",
    )
    parser.add_argument(
        "--tasks-dir",
        type=Path,
        default=repo / "tasks",
        help="local DeepSWE task directory used for static metadata",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="output directory (default names a baseline or leave-model-out directory)",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=12,
        help="tasks in each disjoint dev/confirm sample (default: 12)",
    )
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument(
        "--exclude-model",
        action="append",
        default=[],
        metavar="MODEL",
        help="exclude a public base model from selection evidence; repeatable",
    )
    parser.add_argument(
        "--allow-input-hash-mismatch",
        action="store_true",
        help="run on inputs that differ from official-v1.1/SHA256SUMS",
    )
    args = parser.parse_args()
    args.exclude_model = sorted(set(args.exclude_model))
    if args.output_dir is None:
        suffix = "selection"
        if args.exclude_model:
            safe_names = [name.replace("/", "_") for name in args.exclude_model]
            suffix = "selection-leaveout-" + "-".join(safe_names)
        args.output_dir = repo / "wip/data" / suffix
    return args


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_hashes(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    hashes: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, filename = line.split(maxsplit=1)
        hashes[filename.lstrip("* ")] = digest
    return hashes


def validate_documents(
    tasks_document: dict[str, Any], trials_document: dict[str, Any]
) -> None:
    tasks = tasks_document.get("rows", [])
    trials = trials_document.get("rows", [])
    if tasks_document.get("n_tasks") != len(tasks):
        raise ValueError("tasks.json n_tasks does not match len(rows)")
    if trials_document.get("n_trials") != len(trials):
        raise ValueError("trials.json n_trials does not match len(rows)")
    task_ids = [row.get("id") for row in tasks]
    trial_names = [row.get("trial_name") for row in trials]
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("tasks.json contains duplicate task ids")
    if len(set(trial_names)) != len(trial_names):
        raise ValueError("trials.json contains duplicate trial names")
    known_tasks = set(task_ids)
    unknown_tasks = sorted({
        row.get("task_name") for row in trials
        if row.get("source") == "deep-swe" and row.get("eval_scope") == "full"
        and row.get("task_name") not in known_tasks
    })
    if unknown_tasks:
        raise ValueError(f"trials reference unknown task ids: {unknown_tasks}")
    config_mappings: dict[str, set[tuple[Any, Any, Any]]] = defaultdict(set)
    for row in trials:
        if row.get("source") == "deep-swe" and row.get("eval_scope") == "full":
            config_mappings[row["config"]].add(
                (row.get("harness"), row.get("model"), row.get("reasoning_effort"))
            )
    ambiguous = sorted(config for config, mappings in config_mappings.items() if len(mappings) > 1)
    if ambiguous:
        raise ValueError(f"configs have ambiguous harness/model/effort mappings: {ambiguous}")


def mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return statistics.fmean(values) if values else None


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    x_ss = sum((x - x_mean) ** 2 for x in xs)
    y_ss = sum((y - y_mean) ** 2 for y in ys)
    if x_ss == 0 or y_ss == 0:
        return None
    return numerator / math.sqrt(x_ss * y_ss)


def round_floats(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {key: round_floats(item) for key, item in value.items()}
    if isinstance(value, list):
        return [round_floats(item) for item in value]
    return value


def patch_stats(path: Path) -> dict[str, int]:
    if not path.exists():
        return {"gold_patch_files": 0, "gold_patch_insertions": 0,
                "gold_patch_deletions": 0, "gold_patch_changed_lines": 0}
    files = insertions = deletions = 0
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("diff --git "):
                files += 1
            elif line.startswith("+") and not line.startswith("+++"):
                insertions += 1
            elif line.startswith("-") and not line.startswith("---"):
                deletions += 1
    return {
        "gold_patch_files": files,
        "gold_patch_insertions": insertions,
        "gold_patch_deletions": deletions,
        "gold_patch_changed_lines": insertions + deletions,
    }


def local_task_metadata(tasks_dir: Path, task_id: str) -> dict[str, Any]:
    task_dir = tasks_dir / task_id
    result: dict[str, Any] = {}
    toml_path = task_dir / "task.toml"
    if toml_path.exists():
        with toml_path.open("rb") as handle:
            document = tomllib.load(handle)
        metadata = document.get("metadata", {})
        result["category"] = metadata.get("category")
    config_path = task_dir / "tests/config.json"
    if config_path.exists():
        config = load_json(config_path)
        result["f2p_test_count"] = len(config.get("f2p_node_ids", []))
        result["p2p_test_count"] = len(config.get("p2p_node_ids", []))
    result.update(patch_stats(task_dir / "solution/solution.patch"))
    return result


def percentile_cutpoints(values: list[int]) -> tuple[float, float]:
    ordered = sorted(values)
    if not ordered:
        return (0, 0)
    return (
        ordered[min(len(ordered) - 1, len(ordered) // 3)],
        ordered[min(len(ordered) - 1, (2 * len(ordered)) // 3)],
    )


def patch_size_band(changed_lines: int, cuts: tuple[float, float]) -> str:
    if changed_lines <= cuts[0]:
        return "small"
    if changed_lines <= cuts[1]:
        return "medium"
    return "large"


def difficulty_band(pass_rate: float) -> str:
    if pass_rate < 0.40:
        return "hard"
    if pass_rate <= 0.60:
        return "medium"
    return "easy"


def calculate_metrics(
    tasks: list[dict[str, Any]],
    trials: list[dict[str, Any]],
    v1_delta: dict[str, Any],
    tasks_dir: Path,
    excluded_models: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    relevant = [
        row for row in trials
        if row.get("source") == "deep-swe" and row.get("eval_scope") == "full"
        and row.get("model") not in excluded_models
    ]
    if not relevant:
        raise ValueError("no source=deep-swe, eval_scope=full trials found")
    harnesses = sorted({row["harness"] for row in relevant})
    configs = sorted({row["config"] for row in relevant})
    models = sorted({row["model"] for row in relevant})
    config_model = {row["config"]: row["model"] for row in relevant}

    all_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    valid_by_task_config: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in relevant:
        all_by_task[row["task_name"]].append(row)
        if row.get("included_in_score") is True and row.get("errored") is False:
            valid_by_task_config[(row["task_name"], row["config"])].append(row)

    task_config_rates: dict[str, dict[str, float]] = defaultdict(dict)
    task_config_counts: dict[str, dict[str, int]] = defaultdict(dict)
    for task in tasks:
        task_id = task["id"]
        for config in configs:
            rows = valid_by_task_config.get((task_id, config), [])
            task_config_counts[task_id][config] = len(rows)
            if rows:
                task_config_rates[task_id][config] = statistics.fmean(
                    float(row["score_value"]) for row in rows
                )

    task_model_rates: dict[str, dict[str, float]] = defaultdict(dict)
    for task_id, rates in task_config_rates.items():
        by_model: dict[str, list[float]] = defaultdict(list)
        for config, rate in rates.items():
            by_model[config_model[config]].append(rate)
        task_model_rates[task_id] = {
            model: statistics.fmean(model_rates)
            for model, model_rates in by_model.items()
        }

    # Item-rest correlation: compare a task's per-system pass-rate vector with
    # each system's mean performance on every other task.
    config_abilities: dict[str, dict[str, float]] = defaultdict(dict)
    model_abilities: dict[str, dict[str, float]] = defaultdict(dict)
    task_ids = [task["id"] for task in tasks]
    for excluded_task in task_ids:
        for config in configs:
            values = [
                task_config_rates[task_id][config]
                for task_id in task_ids
                if task_id != excluded_task and config in task_config_rates[task_id]
            ]
            if values:
                config_abilities[excluded_task][config] = statistics.fmean(values)
        for model in models:
            values = [
                task_model_rates[task_id][model]
                for task_id in task_ids
                if task_id != excluded_task and model in task_model_rates[task_id]
            ]
            if values:
                model_abilities[excluded_task][model] = statistics.fmean(values)

    delta_by_task = {row["task"]: row for row in v1_delta.get("tasks", [])}
    changed_line_values = [
        patch_stats(tasks_dir / task["id"] / "solution/solution.patch")[
            "gold_patch_changed_lines"
        ]
        for task in tasks
    ]
    patch_cuts = percentile_cutpoints(changed_line_values)

    results: list[dict[str, Any]] = []
    for task in tasks:
        task_id = task["id"]
        all_rows = all_by_task.get(task_id, [])
        valid_rows = [
            row for row in all_rows
            if row.get("included_in_score") is True and row.get("errored") is False
        ]
        error_rows = [
            row for row in all_rows
            if not (row.get("included_in_score") is True and row.get("errored") is False)
        ]
        config_rates = task_config_rates[task_id]
        model_rates = task_model_rates[task_id]
        counts = task_config_counts[task_id]
        config_values = list(config_rates.values())
        model_values = list(model_rates.values())

        common_configs = sorted(set(config_rates) & set(config_abilities[task_id]))
        config_corr = pearson(
            [config_abilities[task_id][config] for config in common_configs],
            [config_rates[config] for config in common_configs],
        )
        common_models = sorted(set(model_rates) & set(model_abilities[task_id]))
        model_corr = pearson(
            [model_abilities[task_id][model] for model in common_models],
            [model_rates[model] for model in common_models],
        )

        between_variance = statistics.pvariance(config_values) if config_values else 0.0
        within_variance = mean(
            rate * (1 - rate) / counts[config]
            for config, rate in config_rates.items()
            if counts[config] > 0
        ) or 0.0
        denominator = between_variance + within_variance
        signal_ratio = between_variance / denominator if denominator else 0.0
        model_mean = mean(model_values) or 0.0
        config_mean = mean(config_values) or 0.0
        centrality = 1 - abs(model_mean - 0.5) / 0.5
        rank_score = (
            0.45 * (config_corr if config_corr is not None else -1)
            + 0.25 * (model_corr if model_corr is not None else -1)
            + 0.20 * signal_ratio
            + 0.10 * centrality
        )

        local = local_task_metadata(tasks_dir, task_id)
        delta = delta_by_task.get(task_id, {})
        result = {
            "task_id": task_id,
            "title": task.get("problem_title"),
            "language": task.get("language"),
            "repository": task.get("repository"),
            "base_commit_hash": task.get("base_commit_hash"),
            "prompt_characters": task.get("prompt_characters"),
            **local,
            "total_trials": len(all_rows),
            "effective_trials": len(valid_rows),
            "excluded_trials": len(error_rows),
            "error_rate": len(error_rows) / len(all_rows) if all_rows else 1.0,
            "verifier_timeouts": sum(
                row.get("error_category") == "verifier_timeout" for row in error_rows
            ),
            "model_coverage": len(model_rates),
            "config_coverage": len(config_rates),
            "minimum_effective_repeats": min(counts.values()) if counts else 0,
            "base_model_equal_pass_rate": model_mean,
            "config_equal_pass_rate": config_mean,
            "low_model_count": sum(
                rate <= DEFAULT_THRESHOLDS["broad_low_model_max_pass_rate"]
                for rate in model_values
            ),
            "high_model_count": sum(
                rate >= DEFAULT_THRESHOLDS["broad_high_model_min_pass_rate"]
                for rate in model_values
            ),
            "item_rest_correlation_config": config_corr,
            "item_rest_correlation_base_model": model_corr,
            "between_config_variance": between_variance,
            "within_config_mean_variance": within_variance,
            "discrimination_signal_ratio": signal_ratio,
            "v1_pass_rate": delta.get("v1"),
            "v1_1_pass_rate_on_shared_rollouts": delta.get("current"),
            "v1_to_v1_1_delta": delta.get("delta"),
            "scoring_sensitive": abs(float(delta.get("delta", 0)))
            >= DEFAULT_THRESHOLDS["scoring_sensitive_absolute_delta"],
            "rank_score": rank_score,
        }
        result["difficulty_band"] = difficulty_band(model_mean)
        result["patch_size_band"] = patch_size_band(
            int(result.get("gold_patch_changed_lines", 0)), patch_cuts
        )
        results.append(round_floats(result))

    metadata = {
        "trial_scope": {"source": "deep-swe", "eval_scope": "full"},
        "excluded_models": sorted(excluded_models),
        "harnesses": harnesses,
        "n_tasks": len(tasks),
        "n_trials": len(relevant),
        "n_effective_trials": sum(
            row.get("included_in_score") is True and row.get("errored") is False
            for row in relevant
        ),
        "n_excluded_trials": sum(
            not (row.get("included_in_score") is True and row.get("errored") is False)
            for row in relevant
        ),
        "excluded_error_categories": dict(sorted(Counter(
            row.get("error_category") or "unspecified"
            for row in relevant
            if not (row.get("included_in_score") is True and row.get("errored") is False)
        ).items())),
        "n_configs": len(configs),
        "n_base_models": len(models),
        "patch_changed_line_tertile_cutpoints": list(patch_cuts),
    }
    return results, metadata


def apply_layers(
    rows: list[dict[str, Any]], thresholds: dict[str, float | int]
) -> dict[str, list[dict[str, Any]]]:
    t = thresholds
    all_rows = sorted(rows, key=lambda row: row["task_id"])

    for row in all_rows:
        stable_reasons = []
        if row["model_coverage"] < t["minimum_model_coverage"]:
            stable_reasons.append("model_coverage")
        if row["minimum_effective_repeats"] < t["minimum_effective_repeats_per_config"]:
            stable_reasons.append("minimum_effective_repeats")
        if row["error_rate"] > t["maximum_error_rate"]:
            stable_reasons.append("error_rate")
        if row["verifier_timeouts"] > t["maximum_verifier_timeouts"]:
            stable_reasons.append("verifier_timeouts")
        row["layer_01_stable"] = not stable_reasons
        row["layer_01_exclusion_reasons"] = stable_reasons

        broad_reasons = []
        for field in ("base_model_equal_pass_rate", "config_equal_pass_rate"):
            if not t["broad_difficulty_min"] <= row[field] <= t["broad_difficulty_max"]:
                broad_reasons.append(field)
        if row["low_model_count"] < t["broad_minimum_low_models"]:
            broad_reasons.append("low_model_count")
        if row["high_model_count"] < t["broad_minimum_high_models"]:
            broad_reasons.append("high_model_count")
        row["layer_02_broad"] = row["layer_01_stable"] and not broad_reasons
        row["layer_02_exclusion_reasons"] = broad_reasons

        core_reasons = []
        for field in ("base_model_equal_pass_rate", "config_equal_pass_rate"):
            if not t["core_difficulty_min"] <= row[field] <= t["core_difficulty_max"]:
                core_reasons.append(field)
        if row["low_model_count"] < t["core_minimum_low_models"]:
            core_reasons.append("low_model_count")
        if row["high_model_count"] < t["core_minimum_high_models"]:
            core_reasons.append("high_model_count")
        corr = row["item_rest_correlation_config"]
        if corr is None or corr < t["core_minimum_item_rest_correlation"]:
            core_reasons.append("item_rest_correlation_config")
        row["layer_03_core"] = row["layer_02_broad"] and not core_reasons
        row["layer_03_exclusion_reasons"] = core_reasons

    return {
        "00_all": all_rows,
        "01_stable": [row for row in all_rows if row["layer_01_stable"]],
        "02_broad_discriminative": [row for row in all_rows if row["layer_02_broad"]],
        "03_core_discriminative": [row for row in all_rows if row["layer_03_core"]],
    }


def allocate_quotas(counts: Counter[str], size: int) -> dict[str, int]:
    total = sum(counts.values())
    if not total or not size:
        return {}
    exact = {key: size * count / total for key, count in counts.items()}
    quotas = {key: math.floor(value) for key, value in exact.items()}
    for key, _ in sorted(
        exact.items(), key=lambda item: (-(item[1] - math.floor(item[1])), item[0])
    )[: size - sum(quotas.values())]:
        quotas[key] += 1
    return quotas


def balanced_sample(
    candidates: list[dict[str, Any]], size: int, seed: int
) -> list[dict[str, Any]]:
    if size <= 0:
        return []
    if len(candidates) < size:
        raise ValueError(f"need {size} candidates but only {len(candidates)} remain")
    rng = random.Random(seed)
    language_quota = allocate_quotas(Counter(row["language"] for row in candidates), size)
    difficulty_quota = allocate_quotas(
        Counter(row["difficulty_band"] for row in candidates), size
    )
    patch_quota = allocate_quotas(Counter(row["patch_size_band"] for row in candidates), size)
    selected: list[dict[str, Any]] = []
    remaining = list(candidates)
    jitter = {row["task_id"]: rng.random() for row in remaining}

    def deficit_bonus(row: dict[str, Any]) -> float:
        selected_languages = Counter(item["language"] for item in selected)
        selected_difficulty = Counter(item["difficulty_band"] for item in selected)
        selected_patch = Counter(item["patch_size_band"] for item in selected)
        return (
            1.5 * (selected_languages[row["language"]] < language_quota[row["language"]])
            + 1.0
            * (selected_difficulty[row["difficulty_band"]]
               < difficulty_quota[row["difficulty_band"]])
            + 0.75
            * (selected_patch[row["patch_size_band"]]
               < patch_quota[row["patch_size_band"]])
        )

    while len(selected) < size:
        used_repos = Counter(row["repository"] for row in selected)
        repo_limit = 1 if any(used_repos[row["repository"]] == 0 for row in remaining) else 2
        eligible = [row for row in remaining if used_repos[row["repository"]] < repo_limit]
        if not eligible:
            eligible = remaining
        chosen = max(
            eligible,
            key=lambda row: (
                deficit_bonus(row),
                row["rank_score"],
                jitter[row["task_id"]],
                row["task_id"],
            ),
        )
        selected.append(chosen)
        remaining.remove(chosen)
    return selected


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
                for key, value in row.items()
            })


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def write_sample(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(f"{row['task_id']}\n" for row in rows), encoding="utf-8")


def main() -> int:
    args = parse_args()
    if args.sample_size < 1:
        raise ValueError("--sample-size must be positive")
    required = [
        "tasks.json", "trials.json", "leaderboard-live.json", "release.json",
        "v1-delta.json",
    ]
    missing = [name for name in required if not (args.input_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"missing official inputs: {', '.join(missing)}")
    input_hashes = {name: sha256(args.input_dir / name) for name in required}
    frozen_hashes = expected_hashes(args.input_dir / "SHA256SUMS")
    mismatches = {
        name: {"expected": frozen_hashes.get(name), "actual": input_hashes[name]}
        for name in required
        if frozen_hashes.get(name) != input_hashes[name]
    }
    if mismatches and not args.allow_input_hash_mismatch:
        raise ValueError(
            "official input hash mismatch; inspect the new snapshot or use "
            f"--allow-input-hash-mismatch: {mismatches}"
        )

    tasks_document = load_json(args.input_dir / "tasks.json")
    trials_document = load_json(args.input_dir / "trials.json")
    v1_delta = load_json(args.input_dir / "v1-delta.json")
    validate_documents(tasks_document, trials_document)
    metrics, input_metadata = calculate_metrics(
        tasks_document["rows"], trials_document["rows"], v1_delta, args.tasks_dir,
        set(args.exclude_model),
    )
    run_thresholds = dict(DEFAULT_THRESHOLDS)
    run_thresholds["minimum_model_coverage"] = math.ceil(
        input_metadata["n_base_models"]
        * DEFAULT_THRESHOLDS["minimum_model_coverage"]
        / 18
    )
    layers = apply_layers(metrics, run_thresholds)

    core_ranked = sorted(
        layers["03_core_discriminative"],
        key=lambda row: (-row["rank_score"], row["task_id"]),
    )
    dev = balanced_sample(core_ranked, args.sample_size, args.seed)
    dev_ids = {row["task_id"] for row in dev}
    confirm_candidates = [row for row in core_ranked if row["task_id"] not in dev_ids]
    confirm = balanced_sample(confirm_candidates, args.sample_size, args.seed + 1)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in layers.items():
        write_csv(args.output_dir / f"{name}.csv", rows)
        write_json(args.output_dir / f"{name}.json", rows)
    write_csv(args.output_dir / "04_core_ranked.csv", core_ranked)
    write_json(args.output_dir / "04_core_ranked.json", core_ranked)
    write_sample(args.output_dir / "05_sample_dev.txt", dev)
    write_sample(args.output_dir / "05_sample_confirm.txt", confirm)
    write_csv(args.output_dir / "05_sample_dev.csv", dev)
    write_csv(args.output_dir / "05_sample_confirm.csv", confirm)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "script": str(Path(__file__).resolve()),
        "seed": args.seed,
        "sample_size_per_block": args.sample_size,
        "thresholds": run_thresholds,
        "excluded_models": args.exclude_model,
        "input_hashes_sha256": input_hashes,
        "input_metadata": input_metadata,
        "layer_counts": {name: len(rows) for name, rows in layers.items()},
        "dev_task_ids": [row["task_id"] for row in dev],
        "confirm_task_ids": [row["task_id"] for row in confirm],
        "interpretation": (
            "Public trials use a single harness (mini-swe-agent). Treat the selected "
            "tasks as candidates for agent-system comparisons, then validate framework "
            "and coder-reviewer collaboration differences with local repeated runs."
        ),
    }
    write_json(args.output_dir / "manifest.json", manifest)

    print(json.dumps({
        "layer_counts": manifest["layer_counts"],
        "dev": manifest["dev_task_ids"],
        "confirm": manifest["confirm_task_ids"],
        "output_dir": str(args.output_dir),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
