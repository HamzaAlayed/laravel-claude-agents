import { useElapsed } from "@/lib/useElapsed";
import { Badge } from "@/components/ui/badge";

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
      <Badge
        variant="outline"
        className="h-6 border-primary/30 bg-primary/10 px-2.5 text-primary"
      >
        <span className="size-1.5 animate-pulse rounded-full bg-primary" aria-hidden />
        <span className="tabular-nums">running · {elapsed}</span>
      </Badge>
    );
  }
  if (!outcome) return null;
  return (
    <Badge
      variant={outcome === "error" ? "destructive" : "secondary"}
      className="h-6 px-2.5 capitalize"
    >
      {outcome}
    </Badge>
  );
}
