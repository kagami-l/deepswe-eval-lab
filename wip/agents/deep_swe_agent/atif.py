"""Convert cligent's normalized event stream to one ATIF-v1.7 trajectory."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pier.models.trajectories import (
    Agent,
    FinalMetrics,
    Metrics,
    Observation,
    ObservationResult,
    Step,
    ToolCall,
    Trajectory,
)


@dataclass
class _Turn:
    label: str
    session_id: str | None = None
    timestamp: str | None = None
    adapter: str | None = None
    model: str | None = None
    text: list[str] = field(default_factory=list)
    thinking: list[str] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    observations: list[ObservationResult] = field(default_factory=list)
    metrics: Metrics | None = None
    done_status: str | None = None


def _timestamp(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    if not isinstance(value, (int, float)):
        return None
    # cligent timestamps are Unix milliseconds.
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()


def _content(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def load_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def _turns(events: list[dict[str, Any]]) -> list[_Turn]:
    ordered: list[_Turn] = []
    by_key: dict[tuple[str, str], _Turn] = {}
    for event in events:
        label = str(event.get("label") or "unknown-turn")
        session_id = str(event.get("sessionId") or "unknown-session")
        key = (label, session_id)
        turn = by_key.get(key)
        if turn is None:
            turn = _Turn(label=label, session_id=session_id)
            by_key[key] = turn
            ordered.append(turn)
        turn.timestamp = turn.timestamp or _timestamp(event.get("timestamp"))
        if isinstance(event.get("agent"), str):
            turn.adapter = event["agent"]
        payload = event.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        event_type = event.get("type")
        if event_type == "init" and isinstance(payload.get("model"), str):
            turn.model = payload["model"]
        elif event_type == "text" and isinstance(payload.get("content"), str):
            turn.text.append(payload["content"])
        elif event_type == "text_delta" and isinstance(payload.get("delta"), str):
            turn.text.append(payload["delta"])
        elif event_type == "thinking" and isinstance(payload.get("summary"), str):
            turn.thinking.append(payload["summary"])
        elif event_type == "tool_use":
            call_id = str(
                payload.get("toolUseId") or f"{label}-tool-{len(turn.tool_calls)}"
            )
            arguments = payload.get("input")
            turn.tool_calls.append(
                ToolCall(
                    tool_call_id=call_id,
                    function_name=str(payload.get("toolName") or "unknown"),
                    arguments=arguments if isinstance(arguments, dict) else {},
                    extra={"description": payload.get("description")}
                    if payload.get("description") is not None
                    else None,
                )
            )
        elif event_type == "tool_result":
            call_id = payload.get("toolUseId")
            turn.observations.append(
                ObservationResult(
                    source_call_id=str(call_id) if call_id is not None else None,
                    content=_content(payload.get("output")),
                    extra={
                        "status": payload.get("status"),
                        "tool_name": payload.get("toolName"),
                        "duration_ms": payload.get("durationMs"),
                    },
                )
            )
        elif event_type == "done":
            turn.done_status = str(payload.get("status") or "unknown")
            if not turn.text and isinstance(payload.get("result"), str):
                turn.text.append(payload["result"])
            usage = payload.get("usage")
            if isinstance(usage, dict):
                turn.metrics = Metrics(
                    prompt_tokens=int(usage.get("inputTokens") or 0),
                    completion_tokens=int(usage.get("outputTokens") or 0),
                    cost_usd=(
                        float(usage["totalCostUsd"])
                        if usage.get("totalCostUsd") is not None
                        else None
                    ),
                    extra={"tool_uses": int(usage.get("toolUses") or 0)},
                )
    return ordered


def events_to_trajectory(
    *,
    events: list[dict[str, Any]],
    instruction: str,
    summary: dict[str, Any] | None,
    agent_version: str,
) -> Trajectory | None:
    parsed = _turns(events)
    if not parsed:
        return None
    steps: list[Step] = [Step(step_id=1, source="user", message=instruction)]
    for turn in parsed:
        known_ids = {call.tool_call_id for call in turn.tool_calls}
        observations = [
            result
            for result in turn.observations
            if result.source_call_id is None or result.source_call_id in known_ids
        ]
        role = "reviewer" if turn.label.startswith("review-") else "modifier"
        steps.append(
            Step(
                step_id=len(steps) + 1,
                timestamp=turn.timestamp,
                source="agent",
                model_name=turn.model,
                message="".join(turn.text),
                reasoning_content="\n\n".join(turn.thinking) or None,
                tool_calls=turn.tool_calls or None,
                observation=Observation(results=observations) if observations else None,
                metrics=turn.metrics,
                llm_call_count=1,
                extra={
                    "role": role,
                    "turn_label": turn.label,
                    "adapter": turn.adapter,
                    "status": turn.done_status,
                },
            )
        )

    agent_steps = [step for step in steps if step.source == "agent"]
    prompt_tokens = sum(
        step.metrics.prompt_tokens or 0 for step in agent_steps if step.metrics
    )
    completion_tokens = sum(
        step.metrics.completion_tokens or 0 for step in agent_steps if step.metrics
    )
    costs = [
        step.metrics.cost_usd
        for step in agent_steps
        if step.metrics and step.metrics.cost_usd is not None
    ]
    roles = summary.get("roles") if isinstance(summary, dict) else None
    modifier = roles.get("modifier") if isinstance(roles, dict) else None
    default_model = modifier.get("actualModel") if isinstance(modifier, dict) else None
    session_id = next(
        (turn.session_id for turn in parsed if turn.session_id), "unknown"
    )
    return Trajectory(
        schema_version="ATIF-v1.7",
        session_id=session_id,
        agent=Agent(
            name="deep-swe-agent",
            version=agent_version,
            model_name=default_model if isinstance(default_model, str) else None,
            extra={"roles": roles} if isinstance(roles, dict) else None,
        ),
        steps=steps,
        final_metrics=FinalMetrics(
            total_prompt_tokens=prompt_tokens,
            total_completion_tokens=completion_tokens,
            total_cost_usd=sum(costs) if costs else None,
            total_steps=len(agent_steps),
        ),
        extra={
            "workflow": summary.get("workflow") if isinstance(summary, dict) else None,
            "outcome": (
                summary.get("result", {}).get("outcome")
                if isinstance(summary, dict) and isinstance(summary.get("result"), dict)
                else None
            ),
        },
    )
