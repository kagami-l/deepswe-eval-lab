"""Resolved, non-secret contracts shared by the launcher and Pier agent."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Literal


Topology = Literal["single", "collab"]
Workflow = Literal["single", "review-loop"]
Engine = Literal["direct"]


@dataclass(frozen=True)
class KimiModelConfig:
    provider: str
    provider_type: str
    base_url: str
    upstream_model: str
    max_context_size: int
    capabilities: tuple[str, ...]
    support_efforts: tuple[str, ...]
    default_effort: str


@dataclass(frozen=True)
class AgentProfile:
    name: str
    status: Literal["verified", "unverified"]
    adapter: Literal["claude", "codex", "gemini", "kimi", "opencode"]
    model: str
    effort: str | None
    auth: str
    permissions: Literal["auto", "bypass"]
    model_config: KimiModelConfig | None = None
    benchmark_mode: bool = True

    def with_overrides(
        self, *, model: str | None = None, effort: str | None = None
    ) -> "AgentProfile":
        return replace(
            self,
            model=model if model is not None else self.model,
            effort=effort if effort is not None else self.effort,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Budget:
    task_timeout_seconds: float
    agent_timeout_multiplier: float
    hard_timeout_seconds: float
    cleanup_reserve_seconds: float
    soft_deadline_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionPlan:
    schema_version: int
    topology: Topology
    workflow: Workflow
    engine: Engine
    modifier: AgentProfile
    reviewer: AgentProfile | None
    budget: Budget
    runtime_manifest_digest: str
    runtime_image: str
    max_reviews: int
    max_agent_attempts: int
    reviewer_timeout_seconds: float | None
    revision_timeout_seconds: float | None
    event_silence_timeout_seconds: float
    min_turn_seconds: float
    strict: bool
    keep_workspaces: bool

    @property
    def profiles(self) -> tuple[AgentProfile, ...]:
        return (
            (self.modifier,)
            if self.reviewer is None
            else (self.modifier, self.reviewer)
        )

    @property
    def adapters(self) -> set[str]:
        return {profile.adapter for profile in self.profiles}

    def to_dict(self) -> dict[str, Any]:
        workflow_config: dict[str, Any] = {
            "maxReviews": self.max_reviews,
            "maxAgentAttempts": self.max_agent_attempts,
            "eventSilenceTimeoutSeconds": self.event_silence_timeout_seconds,
            "minTurnSeconds": self.min_turn_seconds,
            "strict": self.strict,
            "keepWorkspaces": self.keep_workspaces,
        }
        if self.reviewer_timeout_seconds is not None:
            workflow_config["reviewerTimeoutSeconds"] = self.reviewer_timeout_seconds
        if self.revision_timeout_seconds is not None:
            workflow_config["revisionTimeoutSeconds"] = self.revision_timeout_seconds
        return {
            "schemaVersion": self.schema_version,
            "topology": self.topology,
            "workflow": self.workflow,
            "engine": self.engine,
            "roles": {
                "modifier": self.modifier.to_dict(),
                "reviewer": self.reviewer.to_dict() if self.reviewer else None,
            },
            "budget": self.budget.to_dict(),
            "runtime": {
                "manifestDigest": self.runtime_manifest_digest,
                "image": self.runtime_image,
            },
            "workflowConfig": workflow_config,
        }
