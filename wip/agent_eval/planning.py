"""Normalize CLI intent into one non-secret execution plan."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Budget, ExecutionPlan
from .profiles import ProfileRegistry


DEFAULT_CLEANUP_RESERVE_SECONDS = 300.0
DEFAULT_EVENT_SILENCE_TIMEOUT_SECONDS = 600.0


@dataclass(frozen=True)
class PlanRequest:
    agent: str
    modifier: str | None
    reviewer: str | None
    model: str | None
    effort: str | None
    modifier_model: str | None
    modifier_effort: str | None
    reviewer_model: str | None
    reviewer_effort: str | None
    allow_unverified: bool
    task_timeout_seconds: float
    agent_timeout_multiplier: float
    cleanup_reserve_seconds: float
    runtime_manifest_digest: str
    runtime_image: str
    max_reviews: int
    max_agent_attempts: int
    reviewer_timeout_seconds: float
    revision_timeout_seconds: float
    event_silence_timeout_seconds: float
    min_turn_seconds: float
    strict: bool
    keep_workspaces: bool


def build_execution_plan(
    request: PlanRequest, registry: ProfileRegistry
) -> ExecutionPlan:
    if request.agent == "collab":
        if request.modifier is None or request.reviewer is None:
            raise ValueError("collab requires both --modifier and --reviewer")
        if request.model is not None or request.effort is not None:
            raise ValueError("collab uses role-specific model/effort overrides")
        modifier = registry.resolve(
            request.modifier,
            allow_unverified=request.allow_unverified,
            model=request.modifier_model,
            effort=request.modifier_effort,
        )
        reviewer = registry.resolve(
            request.reviewer,
            allow_unverified=request.allow_unverified,
            model=request.reviewer_model,
            effort=request.reviewer_effort,
        )
        topology = "collab"
        workflow = "review-loop"
        max_reviews = request.max_reviews
    else:
        if request.modifier is not None or request.reviewer is not None:
            raise ValueError("single mode does not accept --modifier or --reviewer")
        if any(
            value is not None
            for value in (
                request.modifier_model,
                request.modifier_effort,
                request.reviewer_model,
                request.reviewer_effort,
            )
        ):
            raise ValueError("single mode uses --model and --effort overrides")
        modifier = registry.resolve(
            request.agent,
            allow_unverified=request.allow_unverified,
            model=request.model,
            effort=request.effort,
        )
        reviewer = None
        topology = "single"
        workflow = "single"
        max_reviews = 0

    if request.agent_timeout_multiplier <= 0:
        raise ValueError("--agent-timeout-multiplier must be positive")
    if request.cleanup_reserve_seconds <= 0:
        raise ValueError("--cleanup-reserve-seconds must be positive")
    hard_timeout = request.task_timeout_seconds * request.agent_timeout_multiplier
    soft_deadline = hard_timeout - request.cleanup_reserve_seconds
    if soft_deadline <= 0:
        raise ValueError("cleanup reserve must be smaller than the hard Agent timeout")
    if request.max_reviews < 1 and topology == "collab":
        raise ValueError("collab --max-reviews must be at least 1")
    if request.max_agent_attempts < 1:
        raise ValueError("--max-agent-attempts must be at least 1")
    if request.event_silence_timeout_seconds <= 0:
        raise ValueError("--event-silence-timeout-seconds must be positive")

    return ExecutionPlan(
        schema_version=1,
        topology=topology,  # type: ignore[arg-type]
        workflow=workflow,  # type: ignore[arg-type]
        engine="direct",
        modifier=modifier,
        reviewer=reviewer,
        budget=Budget(
            task_timeout_seconds=request.task_timeout_seconds,
            agent_timeout_multiplier=request.agent_timeout_multiplier,
            hard_timeout_seconds=hard_timeout,
            cleanup_reserve_seconds=request.cleanup_reserve_seconds,
            soft_deadline_seconds=soft_deadline,
        ),
        runtime_manifest_digest=request.runtime_manifest_digest,
        runtime_image=request.runtime_image,
        max_reviews=max_reviews,
        max_agent_attempts=request.max_agent_attempts,
        reviewer_timeout_seconds=request.reviewer_timeout_seconds,
        revision_timeout_seconds=request.revision_timeout_seconds,
        event_silence_timeout_seconds=request.event_silence_timeout_seconds,
        min_turn_seconds=request.min_turn_seconds,
        strict=request.strict,
        keep_workspaces=request.keep_workspaces,
    )
