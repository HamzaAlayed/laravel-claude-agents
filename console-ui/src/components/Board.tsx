import { LayoutGroup } from "motion/react";
import { StageColumn } from "./StageColumn";
import type { Agent, Catalog, Lane, RunView } from "@/lib/types";

type Props = {
  view: RunView;
  catalog: Catalog;
  onSelect: (lane: Lane) => void;
};

export function Board({ view, catalog, onSelect }: Props) {
  const agents: Record<string, Agent> = Object.fromEntries(
    catalog.agents.map((agent) => [agent.slug, agent]),
  );
  const stageOf = (slug: string) => agents[slug]?.stage ?? "Working";
  // Working only earns a column when something actually lands in it.
  const stages = catalog.stages.filter(
    (stage) => stage !== "Working" || view.lanes.some((lane) => stageOf(lane.slug) === "Working"),
  );
  // Marked from the prompt's own `agent`, never guessed. A prompt with no agent
  // came from the main thread — the coordinator is the board's header, not a
  // card — so nothing is marked, rather than blaming whichever lane is first.
  const parkedLanes = new Set(
    view.pending.flatMap((prompt) => {
      if (!prompt.agent) return [];
      const lane = view.lanes.find(
        (candidate) => candidate.slug === prompt.agent && candidate.status === "running",
      );
      return lane ? [lane.toolUseId] : [];
    }),
  );

  return (
    <LayoutGroup>
      <div className="flex gap-2 overflow-x-auto pb-2">
        {stages.map((stage) => (
          <StageColumn
            key={stage}
            stage={stage}
            lanes={view.lanes.filter((lane) => stageOf(lane.slug) === stage)}
            agents={agents}
            parkedLanes={parkedLanes}
            onSelect={onSelect}
          />
        ))}
      </div>
    </LayoutGroup>
  );
}
