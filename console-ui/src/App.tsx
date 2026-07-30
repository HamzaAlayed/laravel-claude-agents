import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { AlertTriangle, Send, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApprovalBar } from "@/components/ApprovalBar";
import { Board } from "@/components/Board";
import { DecisionSheet } from "@/components/DecisionSheet";
import { FocusRun } from "@/components/FocusRun";
import { Launcher, type LaunchSpec } from "@/components/Launcher";
import { Transcript } from "@/components/Transcript";
import * as api from "@/lib/api";
import { emptyRun, isRunOver, reduce } from "@/lib/reducer";
import { armGate, canSubmit, settleSubmit, startSubmit } from "@/lib/submitGate";
import type { Catalog, GuildEvent, Lane, RunView } from "@/lib/types";

export default function App() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [view, setView] = useState<RunView>(() => emptyRun("prompt"));
  const [selected, setSelected] = useState<Lane | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  // prompt_ids whose answer is in flight: dropped from the queue optimistically
  // so the sheet advances to the next decision without waiting for the round
  // trip, and restored if the POST fails (the agent is still parked).
  const [answering, setAnswering] = useState<string[]>([]);
  // Which decision may be submitted, and which one is already submitted. Kept
  // here rather than in DecisionSheet because the sheet is remounted the instant
  // the queue advances and would lose the flag exactly when it matters.
  const [gate, setGate] = useState(() => armGate(null));
  const [stopped, setStopped] = useState(false);
  const [followUp, setFollowUp] = useState("");
  const [error, setError] = useState<string | null>(null);
  const lastSeq = useRef(0);

  useEffect(() => {
    api.fetchCatalog().then(setCatalog).catch((e) => setError(String(e.message ?? e)));
  }, []);

  const onEvent = useCallback((event: GuildEvent) => {
    lastSeq.current = Math.max(lastSeq.current, event.seq);
    setView((current) => reduce(current, event));
    if (event.type === "prompt") setSheetOpen(true);
    if (event.type === "prompt_resolved")
      setAnswering((ids) => ids.filter((id) => id !== event.prompt_id));
  }, []);

  useEffect(() => {
    if (!runId) return;
    return api.streamRun(runId, lastSeq.current, onEvent);
  }, [runId, onEvent]);

  const queue = view.pending.filter((prompt) => !answering.includes(prompt.prompt_id));
  const head = queue[0] ?? null;
  const headId = head?.prompt_id ?? null;

  // Arming is deliberately an effect: it costs a render cycle AFTER the queue
  // advanced and the sheet remounted for the next prompt, so the second click of
  // a double-click has nothing enabled to hit. No timer, no confirmation step.
  // `armedFor` is a dependency too so that no batching of the submit and its
  // settle can leave the gate shut on a prompt that is still waiting.
  useEffect(() => {
    if (headId === null) return;
    setGate((current) =>
      current.inFlight === null && current.armedFor !== headId ? armGate(headId) : current,
    );
  }, [headId, gate.inFlight, gate.armedFor]);

  const launch = async (spec: LaunchSpec) => {
    setError(null);
    lastSeq.current = 0;
    setView(emptyRun(spec.kind));
    setSelected(null);
    setAnswering([]);
    setGate(armGate(null));
    setSheetOpen(false);
    setStopped(false);
    try {
      const { run_id } = await api.createRun(spec);
      setRunId(run_id);
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

  // Live = launched, no terminal outcome (result OR error) and no interrupt yet.
  // Launching a second run while one is live abandoned the first: its SDK client
  // stayed connected and billing, still reported `running`, and could park on an
  // approval no browser was watching.
  const live = runId !== null && !isRunOver(view) && !stopped;
  const agentLabel = head?.agent
    ? catalog.agents.find((agent) => agent.slug === head.agent)?.name ?? head.agent
    : null;

  const answer = async (payload: Record<string, unknown>) => {
    if (!runId) return;
    const promptId = String(payload.prompt_id ?? "");
    // One click, one decision. The buttons are already disabled while the gate
    // is closed; this refuses anything that gets past them anyway.
    if (!canSubmit(gate, promptId)) return;
    setGate((current) => startSubmit(current, promptId));
    setAnswering((ids) => [...ids, promptId]);
    // One prompt is answered at a time; if others are still waiting the sheet
    // stays open on the next one rather than leaving a parked run hidden.
    setSheetOpen(queue.some((prompt) => prompt.prompt_id !== promptId));
    try {
      await api.answerPrompt(runId, payload);
    } catch (e) {
      setAnswering((ids) => ids.filter((id) => id !== promptId));
      setError(String((e as Error).message));
    } finally {
      // Releases the gate; the effect above re-arms it for whatever prompt is on
      // screen one render later.
      setGate((current) => settleSubmit(current, promptId));
    }
  };

  const interrupt = async () => {
    if (!runId) return;
    try {
      await api.interruptRun(runId);
    } catch (e) {
      // An interrupt that fails is still an ended run — the usual cause is a
      // client that already died (CLINotConnectedError → 500). Leaving `stopped`
      // false there wedged the Launcher until the page was reloaded.
      setError(
        `Interrupt failed — treating this run as ended: ${String((e as Error).message)}`,
      );
    } finally {
      setStopped(true);
    }
  };

  const sendFollowUp = async (event: FormEvent) => {
    event.preventDefault();
    const text = followUp.trim();
    if (!runId || !text) return;
    setFollowUp("");
    try {
      await api.sendMessage(runId, text);
    } catch (e) {
      setFollowUp(text);
      setError(String((e as Error).message));
    }
  };

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
            onClick={interrupt}
          >
            <Square className="mr-1 size-3.5" aria-hidden /> Interrupt
          </Button>
        )}
      </header>

      <Launcher
        catalog={catalog}
        busy={live}
        busyReason={
          live ? "A run is in flight — interrupt it before starting another." : null
        }
        onLaunch={launch}
      />

      {packBroken && (
        <p role="alert" className="mb-3 flex items-center gap-2 rounded-lg border-2 border-destructive px-3 py-2 text-sm">
          <AlertTriangle className="size-4" aria-hidden />
          The Guild pack did not load cleanly — agents may be missing.
        </p>
      )}
      {error && <p role="alert" className="mb-3 text-sm text-destructive">{error}</p>}
      {/* The main thread has no card to carry this, and in a freeform run it is
          where most tool calls happen. */}
      {view.unasked > 0 && (
        <p className="mb-3 text-xs text-muted-foreground">
          {`${view.unasked} ran unasked on the main thread`}
        </p>
      )}
      {view.retry && (
        <p className="mb-3 text-xs text-muted-foreground">
          Retrying after {view.retry.error} — attempt {view.retry.attempt} of {view.retry.max_retries}
        </p>
      )}

      <ApprovalBar pending={queue} agentLabel={agentLabel} onOpen={() => setSheetOpen(true)} />

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

      {/* The run died without a result — say why instead of looking idle. */}
      {view.failure && (
        <section role="alert" className="mt-4 rounded-xl border-2 border-destructive p-3">
          <h2 className="mb-1 flex items-center gap-2 text-sm font-medium">
            <AlertTriangle className="size-4" aria-hidden /> The run ended with an error
          </h2>
          <p className="whitespace-pre-wrap text-sm">{view.failure.message}</p>
        </section>
      )}

      {/* Clarifications arrive as plain text; this is how the user replies. */}
      {live && (
        <form className="mt-4 flex items-center gap-2" onSubmit={sendFollowUp}>
          <Input
            className="flex-1"
            aria-label="Follow-up message"
            placeholder="Reply to the Guild, or add context…"
            value={followUp}
            onChange={(event) => setFollowUp(event.target.value)}
          />
          <Button type="submit" variant="secondary" disabled={!followUp.trim()}>
            <Send className="mr-1 size-4" aria-hidden /> Send
          </Button>
        </form>
      )}

      {head && (
        // key: per-prompt local state (selections, the Other fields, the deny
        // reason) must not leak from one prompt into the next.
        <DecisionSheet
          key={head.prompt_id}
          pending={head}
          open={sheetOpen}
          // Closed while an answer is in flight AND until this prompt has been
          // armed, so a click meant for the previous decision cannot commit this
          // one. Survives the remount above because the gate is App state.
          disabled={!canSubmit(gate, head.prompt_id)}
          onClose={() => setSheetOpen(false)}
          onAnswer={answer}
        />
      )}
    </main>
  );
}
