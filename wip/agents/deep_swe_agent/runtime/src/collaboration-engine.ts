/**
 * Shared contracts for the unified DeepSWE single/collab runtime.
 *
 * The first-phase DirectCollaborationEngine and the later playbook backend
 * both implement `CollaborationEngine` so the Pier agent and cligent glue
 * stay unchanged when the control plane is swapped
 * (docs/collab-agent-design.md section 5).
 */

export type AdapterName = 'claude' | 'codex' | 'gemini' | 'kimi' | 'opencode';

export interface RoleConfig {
  adapter: AdapterName;
  model?: string;
  effort?: string;
  permissions?: 'auto' | 'bypass';
  profileName?: string;
}

export interface CollabConfig {
  repoDir: string;
  instructionPath: string;
  outputDir: string;
  workDir: string;
  modifier: RoleConfig;
  reviewer: RoleConfig;
  maxReviews: number;
  maxAgentAttempts: number;
  modifierTimeoutSec: number;
  reviewerTimeoutSec: number;
  revisionTimeoutSec: number;
  eventSilenceTimeoutSec: number;
  totalTimeoutSec: number;
  /** Do not start a turn with less than this much wall clock remaining. */
  minTurnSec: number;
  strict: boolean;
  keepWorkspaces: boolean;
}

export interface SingleConfig {
  repoDir: string;
  instructionPath: string;
  outputDir: string;
  workDir: string;
  modifier: RoleConfig;
  maxAgentAttempts: number;
  modifierTimeoutSec: number;
  eventSilenceTimeoutSec: number;
  totalTimeoutSec: number;
  minTurnSec: number;
}

export const DELIVERABLE_OUTCOMES = [
  'completed',
  'approved',
  'max_reviews_reached',
  'degraded',
] as const;

export const FAILURE_OUTCOMES = [
  'modifier_failed',
  'timeout',
  'empty_patch',
  'checkpoint_failed',
  'infrastructure_failed',
] as const;

export type Outcome =
  | (typeof DELIVERABLE_OUTCOMES)[number]
  | (typeof FAILURE_OUTCOMES)[number];

export type DegradedReason =
  | 'reviewer_failed'
  | 'invalid_review_output'
  | 'revision_failed'
  | 'timeout'
  | 'infrastructure';

export interface RoleUsage {
  inputTokens: number;
  outputTokens: number;
  toolUses: number;
  costUsd: number | null;
  turns: number;
  wallMs: number;
}

export interface CollaborationResult {
  outcome: Outcome;
  degradedReason: DegradedReason | null;
  deliverable: boolean;
  error: string | null;
  baseCommit: string;
  finalCommit: string | null;
  checkpoints: { label: string; commit: string }[];
  reviewCount: number;
  revisionCount: number;
  noChangeRevision: boolean;
  findingsTotal: number;
  blockingFindingsTotal: number;
  protocolViolations: string[];
  usage: { modifier: RoleUsage; reviewer?: RoleUsage };
  /** Provider-resolved model per role, from the first cligent init event. */
  actualModels: { modifier: string | null; reviewer?: string | null };
}

export interface CollaborationEngine {
  run(): Promise<CollaborationResult>;
}

export function isDeliverable(outcome: Outcome, strict: boolean): boolean {
  if (outcome === 'degraded' && strict) return false;
  return (DELIVERABLE_OUTCOMES as readonly string[]).includes(outcome);
}

export function emptyRoleUsage(): RoleUsage {
  return {
    inputTokens: 0,
    outputTokens: 0,
    toolUses: 0,
    costUsd: null,
    turns: 0,
    wallMs: 0,
  };
}
