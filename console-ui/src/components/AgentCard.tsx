import { motion } from "motion/react";
import { AlertTriangle, Check, Loader2, Pause } from "lucide-react";
import { useElapsed } from "@/lib/useElapsed";
import type { Agent, Lane } from "@/lib/types";

type Props = { lane: Lane; agent?: Agent; parked: boolean; onSelect: () => void };

export function AgentCard({ lane, agent, parked, onSelect }: Props) {
  const elapsed = useElapsed(lane.startedAt, lane.endedAt);
  const color = agent?.color ?? "#64748b";
  const Icon = parked ? Pause : lane.status === "running" ? Loader2 : lane.status === "error" ? AlertTriangle : Check;

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
        <span
          className="grid size-6 shrink-0 place-items-center rounded text-[10px] font-bold text-white"
          style={{ background: color }}
        >
          {(agent?.name ?? lane.slug).slice(0, 2)}
        </span>
        <span className="truncate text-sm font-medium">{agent?.name ?? lane.slug}</span>
        <Icon
          className={`ml-auto size-3.5 shrink-0 ${lane.status === "running" && !parked ? "animate-spin" : ""}`}
          aria-hidden
        />
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
