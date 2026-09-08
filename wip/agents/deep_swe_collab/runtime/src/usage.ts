/** Preserve cligent accounting while retaining the historical summary projection. */
import type { DoneUsage, TokenUsageReport, UsageCost } from '@sublang/cligent';

export interface Accounting {
  usageSchema?: 2;
  tokens?: TokenUsageReport;
  cost?: UsageCost;
  tokenCoverage?: 'complete' | 'partial' | 'unavailable';
  costCoverage?: 'complete' | 'partial' | 'unavailable';
  /** Per-invocation reports retain model/rate-card dimensions and missing turns. */
  usageReports?: (DoneUsage | null)[];
}

interface FlatUsage extends Accounting {
  tokenAvailability: 'reported' | 'unavailable';
  inputTokens: number | null;
  outputTokens: number | null;
  toolUses: number;
  costUsd: number | null;
}

export function normalizeUsage(usage: DoneUsage) {
  return {
    usageSchema: 2 as const,
    tokenAvailability: usage.tokens ? 'reported' as const : 'unavailable' as const,
    inputTokens: usage.tokens?.totals.input.total ?? null,
    outputTokens: usage.tokens?.totals.output.total ?? null,
    toolUses: usage.toolUses,
    costUsd: usage.cost?.amount ?? null,
    tokenCoverage: usage.tokens?.coverage ?? 'unavailable' as const,
    costCoverage: usage.cost ? 'complete' as const : 'unavailable' as const,
    ...(usage.tokens ? { tokens: structuredClone(usage.tokens) } : {}),
    ...(usage.cost ? { cost: structuredClone(usage.cost) } : {}),
  };
}

function sumReports(reports: (DoneUsage | null)[]): TokenUsageReport | undefined {
  const tokens = reports.flatMap((report) => report?.tokens ? [report.tokens] : []);
  if (!tokens.length) return undefined;
  const totals: TokenUsageReport['totals'] = { input: { total: 0 }, output: { total: 0 } };
  for (const side of ['input', 'output'] as const) {
    const keys = side === 'input'
      ? ['total', 'uncached', 'cacheRead', 'cacheWrite']
      : ['total', 'visible', 'reasoning'];
    for (const key of keys) {
      const values = tokens.map((report) => (report.totals[side] as unknown as Record<string, number>)[key]);
      // Missing detail is unknown, never an implicit zero.
      if (values.every((value) => value !== undefined)) {
        (totals[side] as unknown as Record<string, number>)[key] = values.reduce((a, b) => a + b, 0);
      }
    }
  }
  return {
    coverage: tokens.length === reports.length && tokens.every((report) => report.coverage === 'complete')
      ? 'complete' : 'partial',
    totals,
    ...(tokens.every((report) => report.records !== undefined)
      ? { records: tokens.flatMap((report) => report.records!) } : {}),
  };
}

export function accumulateUsage(
  bucket: FlatUsage & { turns: number; wallMs: number },
  usage: FlatUsage | null,
  durationMs: number,
): void {
  const previousTurns = bucket.turns++;
  bucket.wallMs += durationMs;
  const previouslyReported = previousTurns === 0 || bucket.tokenAvailability === 'reported';
  if (usage?.tokenAvailability === 'reported' && previouslyReported) {
    bucket.tokenAvailability = 'reported';
    bucket.inputTokens = (bucket.inputTokens ?? 0) + (usage.inputTokens ?? 0);
    bucket.outputTokens = (bucket.outputTokens ?? 0) + (usage.outputTokens ?? 0);
  } else {
    bucket.tokenAvailability = 'unavailable';
    bucket.inputTokens = bucket.outputTokens = null;
  }
  bucket.toolUses += usage?.toolUses ?? 0;
  if (usage?.costUsd != null) bucket.costUsd = (bucket.costUsd ?? 0) + usage.costUsd;

  if (usage?.usageSchema === 2 || bucket.usageSchema === 2) {
    bucket.usageSchema = 2;
    bucket.usageReports ??= Array<null>(previousTurns).fill(null);
    bucket.usageReports.push(usage?.usageSchema === 2 ? structuredClone({
      toolUses: usage.toolUses,
      ...(usage.tokens ? { tokens: usage.tokens } : {}),
      ...(usage.cost ? { cost: usage.cost } : {}),
    }) : null);
    bucket.tokens = sumReports(bucket.usageReports);
    bucket.tokenCoverage = bucket.tokens?.coverage ?? 'unavailable';
    const costs = bucket.usageReports.flatMap((report) => report?.cost ? [report.cost] : []);
    bucket.costUsd = costs.length ? costs.reduce((sum, cost) => sum + cost.amount, 0) : null;
    bucket.costCoverage = costs.length === bucket.turns ? 'complete' : costs.length ? 'partial' : 'unavailable';
  }
}
