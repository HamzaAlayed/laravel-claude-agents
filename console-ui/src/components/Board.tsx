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
  /**
   * A `stage` of null is the catalog stating that this agent is not a column —
   * only the coordinator, and only because it belongs in the board's header
   * (`catalog.py`). An agent MISSING from the catalog is a different thing, and
   * `stageOf`'s `?? "Working"` still gives it a card; reading the two cases as one
   * is what turned that deliberate null back into a Working-column card.
   */
  const isHeaderAgent = (slug: string) => agents[slug]?.stage === null;
  const headerLanes = view.lanes.filter((lane) => isHeaderAgent(lane.slug));
  const columnLanes = view.lanes.filter((lane) => !isHeaderAgent(lane.slug));
  // Working only earns a column when something actually lands in it.
  const stages = catalog.stages.filter(
    (stage) => stage !== "Working" || columnLanes.some((lane) => stageOf(lane.slug) === "Working"),
  );
  // Marked from the prompt's own `agent`, never guessed. A prompt with no agent
  // came from the main thread — the coordinator is the board's header, not a
  // card — so nothing is marked, rather than blaming whichever lane is first.
  const parkedLanes = new Set(
    view.pending.flatMap((prompt) => {
      // A guessed attribution marks nothing: this promise is that a marked card
      // is really the blocked one, and the bar hedges in words instead.
      if (!prompt.agent || prompt.agentConfidence === "guess") return [];
      const lane = view.lanes.find(
        (candidate) => candidate.slug === prompt.agent && candidate.status === "running",
      );
      return lane ? [lane.toolUseId] : [];
    }),
  );

  return (
    <LayoutGroup>
      {/* The header, not a column — and still clickable, so its transcript is
          reachable exactly like a card's. */}
      {headerLanes.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2">
          {headerLanes.map((lane) => (
            <button
              key={lane.toolUseId}
              onClick={() => onSelect(lane)}
              aria-label={`${agents[lane.slug]?.name ?? lane.slug}: ${lane.task || "coordinating"}`}
              className={`flex flex-1 items-center gap-2 rounded-xl border bg-card px-3 py-2 text-left focus-visible:ring-2${parkedLanes.has(lane.toolUseId) ? " animate-attention" : ""}`}
              style={{
                ["--lane-color" as string]: agents[lane.slug]?.color ?? "#64748b",
                borderColor: parkedLanes.has(lane.toolUseId)
                  ? agents[lane.slug]?.color
                  : undefined,
                borderWidth: parkedLanes.has(lane.toolUseId) ? 2 : 1,
              }}
            >
              <span
                className="grid size-6 shrink-0 place-items-center rounded text-[10px] font-bold text-white"
                style={{ background: agents[lane.slug]?.color ?? "#64748b" }}
              >
                {(agents[lane.slug]?.name ?? lane.slug).slice(0, 2)}
              </span>
              <span className="text-sm font-medium">
                {agents[lane.slug]?.name ?? lane.slug}
              </span>
              <span className="min-w-0 truncate text-xs text-muted-foreground">
                {lane.task || "coordinating…"}
              </span>
              {parkedLanes.has(lane.toolUseId) && (
                <span className="ml-auto shrink-0 text-[11px] font-semibold">needs you</span>
              )}
            </button>
          ))}
        </div>
      )}
      <div className="flex gap-2 overflow-x-auto pb-2">
        {stages.map((stage) => (
          <StageColumn
            key={stage}
            stage={stage}
            lanes={columnLanes.filter((lane) => stageOf(lane.slug) === stage)}
            agents={agents}
            parkedLanes={parkedLanes}
            onSelect={onSelect}
          />
        ))}
      </div>
    </LayoutGroup>
  );
}
