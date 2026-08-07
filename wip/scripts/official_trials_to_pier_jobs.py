"""Convert official DeepSWE release data into a pier-compatible jobs folder.

Reads the exported ``trials.json`` from https://deepswe.datacurve.ai/data/v1.1
and materializes one pier job directory per model config (harness + model +
reasoning effort), each containing per-trial ``result.json`` files built with
pier's own pydantic models. The output folder can then be served with::

    pier view <out-dir> --jobs

and configs can be multi-selected in the viewer for heatmap comparison.

Trial artifacts (trajectories, logs, patches) are not downloaded; only the
metrics needed for the jobs list and heatmaps are materialized.
"""

import argparse
import json
import shutil
from collections import defaultdict
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from pier.models.agent.context import AgentContext
from pier.models.job.config import JobConfig
from pier.models.job.result import JobResult, JobStats
from pier.models.task.id import LocalTaskId
from pier.models.trial.config import AgentConfig, TaskConfig, TrialConfig
from pier.models.trial.result import (
    AgentInfo,
    ExceptionInfo,
    ModelInfo,
    TrialResult,
)
from pier.models.verifier.result import VerifierResult

REWARD_KEYS = ("reward", "f2p", "p2p", "partial")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def build_trial_result(row: dict, artifact_uri_prefix: str) -> TrialResult:
    task_name = row["task_name"]
    effort = row.get("reasoning_effort")
    agent_kwargs = {"reasoning_effort": effort} if effort else {}

    rewards = {k: row[k] for k in REWARD_KEYS if row.get(k) is not None}
    for k in ("f2p_passed", "f2p_total", "p2p_passed", "p2p_total"):
        if row.get(k) is not None:
            rewards[k] = row[k]

    exception_info = None
    if row.get("exception"):
        exception_info = ExceptionInfo.model_validate(row["exception"])

    return TrialResult(
        id=uuid5(NAMESPACE_URL, f"deepswe-trial/{row['trial_name']}"),
        task_name=task_name,
        trial_name=row["trial_name"],
        trial_uri=f"{artifact_uri_prefix}/{row['trial_name']}",
        task_id=LocalTaskId(path=Path("tasks") / task_name),
        source=row.get("source"),
        task_checksum="",
        config=TrialConfig(
            task=TaskConfig(path=Path("tasks") / task_name, source=row.get("source")),
            trial_name=row["trial_name"],
            agent=AgentConfig(
                name=row["harness"],
                model_name=f"{row['provider']}/{row['model']}",
                kwargs=agent_kwargs,
            ),
        ),
        agent_info=AgentInfo(
            name=row["harness"],
            version="official-v1.1",
            model_info=ModelInfo(name=row["model"], provider=row["provider"]),
        ),
        agent_result=AgentContext(
            n_input_tokens=row.get("n_input_tokens"),
            n_cache_tokens=row.get("n_cache_tokens"),
            n_output_tokens=row.get("n_output_tokens"),
            cost_usd=row.get("cost_usd"),
            peak_context_tokens=row.get("peak_context_tokens"),
            n_agent_steps=row.get("n_agent_steps"),
            metadata={
                "official_outcome": row.get("outcome"),
                "official_error_category": row.get("error_category"),
                "official_included_in_score": row.get("included_in_score"),
                "official_config": row.get("config"),
            },
        ),
        verifier_result=VerifierResult(rewards=rewards) if rewards else None,
        exception_info=exception_info,
        started_at=row.get("started_at"),
        finished_at=row.get("finished_at"),
        n_agent_steps=row.get("n_agent_steps"),
    )


def write_job(job_dir: Path, config_name: str, rows: list[dict], uri_prefix: str) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    trial_results = []
    for row in rows:
        trial_result = build_trial_result(row, uri_prefix)
        trial_dir = job_dir / row["trial_name"]
        trial_dir.mkdir(exist_ok=True)
        (trial_dir / "result.json").write_text(
            trial_result.model_dump_json(indent=None)
        )
        trial_results.append(trial_result)

    first = rows[0]
    job_config = JobConfig(
        job_name=config_name,
        agents=[
            AgentConfig(
                name=first["harness"],
                model_name=f"{first['provider']}/{first['model']}",
                kwargs=(
                    {"reasoning_effort": first["reasoning_effort"]}
                    if first.get("reasoning_effort")
                    else {}
                ),
            )
        ],
        tasks=[
            TaskConfig(path=Path("tasks") / name)
            for name in sorted({r["task_name"] for r in rows})
        ],
    )
    (job_dir / "config.json").write_text(job_config.model_dump_json(indent=4))

    started = min(t.started_at for t in trial_results if t.started_at)
    finished = max(t.finished_at for t in trial_results if t.finished_at)
    job_result = JobResult(
        id=uuid5(NAMESPACE_URL, f"deepswe-job/{config_name}"),
        started_at=started,
        updated_at=finished,
        finished_at=finished,
        n_total_trials=len(trial_results),
        stats=JobStats.from_trial_results(trial_results),
    )
    (job_dir / "result.json").write_text(job_result.model_dump_json(indent=None))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trials",
        type=Path,
        default=DATA_DIR / "official-v1.1/trials.json",
        help="Path to the official trials.json export",
    )
    parser.add_argument(
        "--release",
        type=Path,
        default=DATA_DIR / "official-v1.1/release.json",
        help="Path to release.json (for artifact URI prefixes)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DATA_DIR / "official-v1.1-jobs",
        help="Output jobs folder for `pier view --jobs`",
    )
    parser.add_argument(
        "--config",
        action="append",
        default=None,
        metavar="GLOB",
        help="Only convert configs matching this glob (repeatable), "
        "e.g. --config 'mini_swe_agent_claude_*'",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete existing job dirs in --out before writing",
    )
    args = parser.parse_args()

    data = json.loads(args.trials.read_text())
    rows = data["rows"]

    uri_prefix = ""
    if args.release.exists():
        release = json.loads(args.release.read_text())
        uri_prefix = (
            f"{release['artifact_base_url']}/{release['artifact_key_prefix']}"
        )

    by_config: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_config[row["config"]].append(row)

    if args.config:
        selected = {
            name: rows_
            for name, rows_ in by_config.items()
            if any(fnmatch(name, pattern) for pattern in args.config)
        }
        if not selected:
            available = "\n  ".join(sorted(by_config))
            raise SystemExit(
                f"No configs matched {args.config}. Available:\n  {available}"
            )
        by_config = selected

    if args.clean and args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True, exist_ok=True)

    for config_name in sorted(by_config):
        config_rows = by_config[config_name]
        print(f"{config_name}: {len(config_rows)} trials")
        write_job(args.out / config_name, config_name, config_rows, uri_prefix)

    print(f"\nWrote {len(by_config)} jobs to {args.out}")
    print(f"View with: pier view {args.out} --jobs")


if __name__ == "__main__":
    main()
