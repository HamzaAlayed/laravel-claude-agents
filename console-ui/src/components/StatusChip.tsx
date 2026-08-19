import { useElapsed } from "@/lib/useElapsed";

export type RunOutcome = "done" | "error" | "stopped" | null;

/**
 * The at-a-glance answer to "is it still going?". Deliberately NOT a live
 * region: the elapsed time ticks every second, and announcing that to a screen
 * reader would be noise — the approval bar and alerts carry the urgent states.
 */
export function StatusChip({
  live,
  startedAt,
  outcome,
}: {
  live: boolean;
  startedAt: number;
  outcome: RunOutcome;
}) {
  // (0, 1) when idle: startedAt 0 renders "", endedAt 1 skips the interval.
  const elapsed = useElapsed(live ? startedAt : 0, live ? 0 : 1);
  if (live) {
    return (
      <span className="flex items-center gap-1.5 rounded-full border border-[color-mix(in_oklab,var(--tungsten)_40%,transparent)] px-2 py-0.5 text-xs tabular-nums text-[var(--tungsten)]">
        <span className="size-1.5 animate-pulse rounded-full bg-[var(--tungsten)]" aria-hidden />
        running · {elapsed}
      </span>
    );
  }
  if (!outcome) return null;
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-xs ${
        outcome === "error"
          ? "border-[color-mix(in_oklab,var(--cue)_50%,var(--paper))] text-[color-mix(in_oklab,var(--cue)_50%,var(--paper))]"
          : "border-[color-mix(in_oklab,var(--paper)_24%,transparent)] text-[color-mix(in_oklab,var(--paper)_70%,transparent)]"
      }`}
    >
      {outcome}
    </span>
  );
}
