import { Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusChip, type RunOutcome } from "@/components/StatusChip";

const headerActionClass =
  "border-[color-mix(in_oklab,var(--paper)_24%,transparent)] bg-transparent text-[var(--paper)] hover:bg-[color-mix(in_oklab,var(--paper)_10%,transparent)] hover:text-[var(--paper)]";

const cueActionClass =
  "border-[color-mix(in_oklab,var(--cue)_50%,transparent)] bg-[color-mix(in_oklab,var(--cue)_22%,transparent)] text-[var(--paper)] hover:bg-[color-mix(in_oklab,var(--cue)_32%,transparent)] hover:text-[var(--paper)]";

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
    <div className="contents">
      <h1
        className="font-heading truncate text-lg font-extrabold text-[var(--paper)]"
        title={title}
      >
        {title}
      </h1>
      <StatusChip live={live} startedAt={startedAt} outcome={outcome} />
      {onCue && (
        <Button
          size="sm"
          variant="outline"
          className={cueActionClass}
          aria-label={cueTool ? `Needs you — ${cueTool}` : "Needs you"}
          onClick={onCue}
        >
          Needs you
        </Button>
      )}
      {onStop && (
        <Button
          size="sm"
          variant="outline"
          className={headerActionClass}
          aria-label="Stop — interrupt the running agent"
          onClick={onStop}
        >
          <Square className="mr-1 size-3.5" aria-hidden /> Stop
        </Button>
      )}
      {onBack && (
        <Button
          size="sm"
          variant="outline"
          className={headerActionClass}
          aria-label="Back — close recording"
          onClick={onBack}
        >
          Back
        </Button>
      )}
    </div>
  );
}
