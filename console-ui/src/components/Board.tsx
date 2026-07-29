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
  const parkedLane =
    view.pending && view.lanes.find((lane) => lane.status === "running")?.toolUseId;

  return (
    <LayoutGroup>
      <div className="flex gap-2 overflow-x-auto pb-2">
        {stages.map((stage) => (
          <StageColumn
            key={stage}
            stage={stage}
            lanes={view.lanes.filter((lane) => stageOf(lane.slug) === stage)}
            agents={agents}
            parkedLane={parkedLane ?? null}
            onSelect={onSelect}
          />
        ))}
      </div>
    </LayoutGroup>
  );
}
