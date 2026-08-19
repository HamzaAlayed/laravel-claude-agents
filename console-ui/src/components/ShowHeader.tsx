import { Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusChip, type RunOutcome } from "@/components/StatusChip";

const headerActionClass =
  "border-[color-mix(in_oklab,var(--paper)_24%,transparent)] bg-transparent text-[var(--paper)] hover:bg-[color-mix(in_oklab,var(--paper)_10%,transparent)] hover:text-[var(--paper)]";

export function ShowHeader({
  title,
  live,
  startedAt,
  outcome,
  onStop,
  onBack,
}: {
  title: string;
  live: boolean;
  startedAt: number;
  outcome: RunOutcome;
  /** Omit unless a run is live — ended and recorded shows have nothing to interrupt. */
  onStop?: () => void;
  /** Omit unless a recording is open — returns to the call sheet. */
  onBack?: () => void;
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
          aria-label="Close recording"
          onClick={onBack}
        >
          Back
        </Button>
      )}
    </div>
  );
}
