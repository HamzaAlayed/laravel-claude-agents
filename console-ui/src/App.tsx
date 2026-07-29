import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApprovalBar } from "@/components/ApprovalBar";
import { Board } from "@/components/Board";
import { DecisionSheet } from "@/components/DecisionSheet";
import { FocusRun } from "@/components/FocusRun";
import { Launcher, type LaunchSpec } from "@/components/Launcher";
import { Transcript } from "@/components/Transcript";
import * as api from "@/lib/api";
import { emptyRun, reduce } from "@/lib/reducer";
import type { Catalog, GuildEvent, Lane, RunView } from "@/lib/types";

export default function App() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [view, setView] = useState<RunView>(() => emptyRun("prompt"));
  const [selected, setSelected] = useState<Lane | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastSeq = useRef(0);

  useEffect(() => {
    api.fetchCatalog().then(setCatalog).catch((e) => setError(String(e.message ?? e)));
  }, []);

  const onEvent = useCallback((event: GuildEvent) => {
    lastSeq.current = Math.max(lastSeq.current, event.seq);
    setView((current) => reduce(current, event));
    if (event.type === "prompt") setSheetOpen(true);
  }, []);

  useEffect(() => {
    if (!runId) return;
    return api.streamRun(runId, lastSeq.current, onEvent);
  }, [runId, onEvent]);

  const launch = async (spec: LaunchSpec) => {
    setError(null);
    lastSeq.current = 0;
    setView(emptyRun(spec.kind));
    try {
      const { run_id } = await api.createRun(spec);
      setRunId(run_id);
    } catch (e) {
      setError(String((e as Error).message));
    }
  };

  const answer = async (payload: Record<string, unknown>) => {
    if (!runId) return;
    setSheetOpen(false);
    try {
      await api.answerPrompt(runId, payload);
    } catch (e) {
      setError(String((e as Error).message));
    }
  };

  if (!catalog) {
    return (
      <main className="mx-auto max-w-md p-8 text-sm">
        {error ? `Could not reach the console API: ${error}` : "Loading the Guild…"}
      </main>
    );
  }

  // The init event reports plugins, not agent counts — so "did the pack load"
  // is exactly: no plugin errors, and laravel-team present among the plugins.
  const packBroken =
    view.init !== null &&
    (view.init.plugin_errors.length > 0 || !view.init.plugins.includes("laravel-team"));

  return (
    <main className="mx-auto max-w-6xl p-4 md:p-6">
      <header className="mb-4 flex items-baseline gap-3">
        <h1 className="text-lg font-semibold">Laravel Guild Console</h1>
        {runId && (
          <Button
            size="sm"
            variant="outline"
            className="ml-auto"
            aria-label="Interrupt the running agent"
            onClick={() => api.interruptRun(runId)}
          >
            <Square className="mr-1 size-3.5" aria-hidden /> Interrupt
          </Button>
        )}
      </header>

      <Launcher catalog={catalog} busy={false} onLaunch={launch} />

      {packBroken && (
        <p role="alert" className="mb-3 flex items-center gap-2 rounded-lg border-2 border-destructive px-3 py-2 text-sm">
          <AlertTriangle className="size-4" aria-hidden />
          The Guild pack did not load cleanly — agents may be missing.
        </p>
      )}
      {error && <p role="alert" className="mb-3 text-sm text-destructive">{error}</p>}
      {view.retry && (
        <p className="mb-3 text-xs text-muted-foreground">
          Retrying after {view.retry.error} — attempt {view.retry.attempt} of {view.retry.max_retries}
        </p>
      )}

      <ApprovalBar pending={view.pending} onOpen={() => setSheetOpen(true)} />

      {view.mode === "board" ? (
        <Board view={view} catalog={catalog} onSelect={setSelected} />
      ) : (
        <FocusRun view={view} catalog={catalog} />
      )}

      {selected && (
        <section className="mt-4 rounded-xl border p-3">
          <h2 className="mb-2 text-sm font-medium">
            {catalog.agents.find((a) => a.slug === selected.slug)?.name ?? selected.slug}
          </h2>
          <Transcript events={view.lanes.find((l) => l.toolUseId === selected.toolUseId)?.events ?? []} />
        </section>
      )}

      {view.result && (
        <section className="mt-4 rounded-xl border bg-muted/30 p-3">
          <h2 className="mb-1 text-sm font-medium">Final answer</h2>
          <p className="whitespace-pre-wrap text-sm">{view.result.result}</p>
        </section>
      )}

      {view.pending && (
        <DecisionSheet
          pending={view.pending}
          open={sheetOpen}
          onClose={() => setSheetOpen(false)}
          onAnswer={answer}
        />
      )}
    </main>
  );
}
