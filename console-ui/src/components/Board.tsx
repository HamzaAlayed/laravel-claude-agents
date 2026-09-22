import { LayoutGroup } from "motion/react";
import { StageColumn } from "./StageColumn";
import { Actor } from "./Actor";
import { actorPose } from "@/lib/actorPose";
import { parkedLaneIds } from "@/lib/parkedLanes";
import type { Agent, Catalog, Lane, RunView } from "@/lib/types";

type Props = {
  view: RunView;
  catalog: Catalog;
  onSelect: (lane: Lane) => void;
  /** Recorded replays pass an empty set — pending on disk is not answerable. */
  parkedLanes?: Set<string>;
};

export function Board({ view, catalog, onSelect, parkedLanes }: Props) {
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
  // Shared with App, which needs the same answer for the lane panel's actor —
  // see parkedLaneIds for why a guessed attribution marks nothing.
  const parked = parkedLanes ?? parkedLaneIds(view);

  return (
    <div data-floor="" className="rounded-2xl border border-border bg-card/50 p-3 text-foreground shadow-2xl shadow-black/10 sm:p-4">
      <LayoutGroup>
        {/* The header, not a column — and still clickable, so its transcript is
            reachable exactly like a card's. */}
        {headerLanes.length > 0 && (
          <div className="mb-4 flex flex-wrap gap-2 border-b border-border pb-4">
            {headerLanes.map((lane) => {
              const waiting = parked.has(lane.toolUseId);
              return (
                <button
                  key={lane.toolUseId}
                  data-station=""
                  onClick={() => onSelect(lane)}
                  aria-label={`${agents[lane.slug]?.name ?? lane.slug}: ${lane.task || "coordinating"}`}
                  className={`flex min-h-12 flex-1 items-center gap-2 rounded-xl border bg-background/50 px-3 py-2 text-left text-foreground shadow-sm transition-[background-color,border-color,box-shadow] hover:border-primary/30 hover:bg-accent/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                    waiting
                      ? "animate-attention border-destructive/60 shadow-[inset_0_-3px_0_0_var(--destructive)]"
                      : "border-border"
                  }`}
                  style={{
                    ["--lane-color" as string]: agents[lane.slug]?.color ?? "#64748b",
                  }}
                >
                  <Actor
                    pose={actorPose(lane, waiting)}
                    color={agents[lane.slug]?.color ?? "#64748b"}
                  />
                  <span className="text-sm font-medium">
                    {agents[lane.slug]?.name ?? lane.slug}
                  </span>
                  <span className="min-w-0 truncate text-xs text-muted-foreground">
                    {lane.task || "coordinating…"}
                  </span>
                  {waiting && (
                    <span className="ml-auto shrink-0 rounded-full bg-destructive/10 px-2 py-0.5 text-[11px] font-semibold text-destructive">
                      needs you
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
        <div className="flex gap-3 overflow-x-auto pb-1">
          {stages.map((stage) => (
            <StageColumn
              key={stage}
              stage={stage}
              lanes={columnLanes.filter((lane) => stageOf(lane.slug) === stage)}
              agents={agents}
              parkedLanes={parked}
              onSelect={onSelect}
            />
          ))}
        </div>
      </LayoutGroup>
    </div>
  );
}
