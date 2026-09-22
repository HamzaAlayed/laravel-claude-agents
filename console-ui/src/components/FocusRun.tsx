import { motion } from "motion/react";
import { Activity, Clock3, Cpu } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useElapsed } from "@/lib/useElapsed";
import { Transcript } from "./Transcript";
import type { Catalog, RunView } from "@/lib/types";

export function FocusRun({ view, catalog }: { view: RunView; catalog: Catalog }) {
  const lane = view.lanes[0];
  const agent = catalog.agents.find((candidate) => candidate.slug === lane?.slug);
  const elapsed = useElapsed(lane?.startedAt ?? 0, lane?.endedAt ?? 0);
  const events = lane ? lane.events : view.main;

  return (
    <div className="grid gap-4 xl:grid-cols-[17rem_minmax(0,1fr)]">
      <motion.aside
        layout
        className="min-w-0"
      >
        <Card className="h-full border-t-2 bg-card/80" style={{ borderTopColor: agent?.color ?? "var(--primary)" }}>
          <CardHeader>
            <div className="mb-2 flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Activity className="size-4" aria-hidden />
            </div>
            <CardTitle>{agent?.name ?? "Main thread"}</CardTitle>
            <CardDescription className="line-clamp-3">
              {lane?.task || view.result?.subtype || "Preparing the run…"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 border-t border-border/70 pt-4 text-xs text-muted-foreground">
            <p className="flex items-center gap-2">
              <Clock3 className="size-3.5 text-primary" aria-hidden />
              <span className="tabular-nums">{elapsed || (view.result ? "Completed" : "Just started")}</span>
            </p>
            {agent && (
              <p className="flex items-center gap-2">
                <Cpu className="size-3.5 text-primary" aria-hidden />
                <span className="truncate" title={agent.model}>{agent.model}</span>
              </p>
            )}
          </CardContent>
        </Card>
      </motion.aside>
      <Card className="min-w-0 bg-card/80">
        <CardHeader className="border-b border-border/70">
          <CardTitle>Run activity</CardTitle>
          <CardDescription>Tools, reasoning, and responses in chronological order.</CardDescription>
        </CardHeader>
        <CardContent className="px-2 sm:px-4">
          <Transcript events={events} />
        </CardContent>
      </Card>
    </div>
  );
}
