import { AnimatePresence } from "motion/react";
import { AgentCard } from "./AgentCard";
import type { Agent, Lane } from "@/lib/types";

type Props = {
  stage: string;
  lanes: Lane[];
  agents: Record<string, Agent>;
  /** toolUseIds of every lane blocked on an approval — there can be several. */
  parkedLanes: Set<string>;
  onSelect: (lane: Lane) => void;
};

const captionClass = "text-[color-mix(in_oklab,var(--paper)_70%,transparent)]";

export function StageColumn({ stage, lanes, agents, parkedLanes, onSelect }: Props) {
  return (
    <section className="flex min-w-[150px] flex-1 flex-col p-2">
      <h2 className={`mb-2 text-[11px] font-semibold uppercase tracking-widest ${captionClass}`}>
        {stage}
        <span className="ml-1.5 tabular-nums opacity-60">{lanes.length || ""}</span>
      </h2>
      <div className="flex flex-col gap-2">
        <AnimatePresence mode="popLayout">
          {lanes.map((lane) => (
            <AgentCard
              key={lane.toolUseId}
              lane={lane}
              agent={agents[lane.slug]}
              parked={parkedLanes.has(lane.toolUseId)}
              onSelect={() => onSelect(lane)}
            />
          ))}
        </AnimatePresence>
        {lanes.length === 0 && (
          <p className={`px-2 py-3 text-center text-[11px] ${captionClass}`}>idle</p>
        )}
      </div>
    </section>
  );
}
