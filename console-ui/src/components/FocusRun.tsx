import { motion } from "motion/react";
import { useElapsed } from "@/lib/useElapsed";
import { Transcript } from "./Transcript";
import type { Catalog, RunView } from "@/lib/types";

export function FocusRun({ view, catalog }: { view: RunView; catalog: Catalog }) {
  const lane = view.lanes[0];
  const agent = catalog.agents.find((candidate) => candidate.slug === lane?.slug);
  const elapsed = useElapsed(lane?.startedAt ?? 0, lane?.endedAt ?? 0);
  const events = lane ? lane.events : view.main.filter((e) => e.type !== "error");

  return (
    <div className="flex flex-col gap-3 md:flex-row">
      <motion.aside
        layout
        className="rounded-xl border p-3 md:w-56"
        style={{ borderColor: agent?.color }}
      >
        <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
          {agent?.name ?? "Main thread"}
        </p>
        <p className="mt-1 text-sm">{lane?.task || view.result?.subtype || "working…"}</p>
        <p className="mt-1 text-xs tabular-nums text-muted-foreground">{elapsed}</p>
        {agent && <p className="mt-2 text-[11px] text-muted-foreground">{agent.model}</p>}
      </motion.aside>
      <section className="min-w-0 flex-1 rounded-xl border p-3">
        <Transcript events={events} />
      </section>
    </div>
  );
}
