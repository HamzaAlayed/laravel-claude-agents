import { ArrowLeft, CircleAlert, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusChip, type RunOutcome } from "@/components/StatusChip";

export function ShowHeader({
  title,
  live,
  startedAt,
  outcome,
  onStop,
  onBack,
  onCue,
  cueTool,
}: {
  title: string;
  live: boolean;
  startedAt: number;
  outcome: RunOutcome;
  /** Omit unless a run is live — ended and recorded shows have nothing to interrupt. */
  onStop?: () => void;
  /** Omit unless a recording is open — returns to the call sheet. */
  onBack?: () => void;
  /** Floor-only return to Spotlight when a prompt is waiting. */
  onCue?: () => void;
  /** Tool name on the waiting prompt — part of the accessible name. */
  cueTool?: string;
}) {
  return (
    <div className="flex min-w-0 flex-1 flex-wrap items-center gap-3">
      {onBack && (
        <Button
          size="icon-sm"
          variant="ghost"
          aria-label="Back — close recording"
          onClick={onBack}
        >
          <ArrowLeft aria-hidden />
        </Button>
      )}
      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
          {onBack ? "Recorded run" : live ? "Live run" : "Run summary"}
        </p>
        <h1 className="truncate font-heading text-base font-semibold text-foreground sm:text-lg" title={title}>
          {title}
        </h1>
      </div>
      <StatusChip live={live} startedAt={startedAt} outcome={outcome} />
      <div className="flex items-center gap-2">
        {onCue && (
          <Button
            size="sm"
            variant="destructive"
            aria-label={cueTool ? `Needs you — ${cueTool}` : "Needs you"}
            onClick={onCue}
          >
            <CircleAlert aria-hidden />
            Needs you
          </Button>
        )}
        {onStop && (
          <Button
            size="sm"
            variant="outline"
            aria-label="Stop — interrupt the running agent"
            onClick={onStop}
          >
            <Square aria-hidden />
            Stop
          </Button>
        )}
      </div>
    </div>
  );
}
