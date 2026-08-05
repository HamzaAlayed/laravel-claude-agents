import { motion } from "motion/react";
import { AlertTriangle, Check, Pause } from "lucide-react";
import { useElapsed } from "@/lib/useElapsed";
import { actorPose } from "@/lib/actorPose";
import { Actor } from "./Actor";
import type { Agent, Lane } from "@/lib/types";

type Props = { lane: Lane; agent?: Agent; parked: boolean; onSelect: () => void };

/**
 * The lane's outcome, or null while it still has none. A running lane used to
 * carry a spinning loader, which said "busy" next to an actor already saying it
 * — and said nothing the actor did not. The icon now marks only the states where
 * the answer is settled.
 */
const outcomeOf = (lane: Lane, parked: boolean) => {
  if (parked) return { key: "parked", Icon: Pause } as const;
  if (lane.status === "error") return { key: "error", Icon: AlertTriangle } as const;
  if (lane.status === "done") return { key: "done", Icon: Check } as const;
  return null;
};

export function AgentCard({ lane, agent, parked, onSelect }: Props) {
  const elapsed = useElapsed(lane.startedAt, lane.endedAt);
  const color = agent?.color ?? "#64748b";
  const outcome = outcomeOf(lane, parked);

  return (
    <motion.button
      layout
      layoutId={lane.toolUseId}
      onClick={onSelect}
      initial={{ opacity: 0, y: 8, scale: 0.97 }}
      animate={{ opacity: lane.status === "done" ? 0.7 : 1, y: 0, scale: 1 }}
      transition={{ type: "spring", stiffness: 380, damping: 30 }}
      className={`w-full rounded-lg border bg-card p-2.5 text-left focus-visible:ring-2 ${parked ? "animate-attention" : ""}`}
      style={{
        ["--lane-color" as string]: color,
        borderColor: parked ? color : undefined,
        borderWidth: parked ? 2 : 1,
      }}
      aria-label={`${agent?.name ?? lane.slug}: ${lane.task || "working"}`}
    >
      <div className="flex items-center gap-2">
        <Actor pose={actorPose(lane, parked)} color={color} />
        <span className="truncate text-sm font-medium">{agent?.name ?? lane.slug}</span>
        {outcome && (
          <outcome.Icon data-outcome={outcome.key} className="ml-auto size-3.5 shrink-0" aria-hidden />
        )}
      </div>
      <p className="mt-1 truncate text-xs text-muted-foreground">{lane.task || "working…"}</p>
      <p className="mt-0.5 text-[11px] tabular-nums text-muted-foreground">
        {parked ? "needs you" : elapsed}
      </p>
      {/* Claude Code decides some calls before can_use_tool is consulted. Saying
          so is the difference between a transcript and an approval record. One
          template literal, not two nodes, so the line reads as one string. */}
      {lane.unasked > 0 && (
        <p className="mt-0.5 text-[11px] tabular-nums text-muted-foreground">
          {`${lane.unasked} ran unasked`}
        </p>
      )}
    </motion.button>
  );
}
