import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { AnimatePresence, motion } from "motion/react";
import { AlertTriangle, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Board } from "@/components/Board";
import { FocusRun } from "@/components/FocusRun";
import { LanePanel } from "@/components/LanePanel";
import { Launcher, type LaunchSpec } from "@/components/Launcher";
import { Markdown } from "@/components/Markdown";
import { ShowHeader } from "@/components/ShowHeader";
import { Spotlight } from "@/components/Spotlight";
import * as api from "@/lib/api";
import { fadeRise } from "@/lib/motion";
import { formatRunLabel } from "@/lib/runLabel";
import { emptyRun, isRunOver, reduce } from "@/lib/reducer";
import { parkedLaneIds } from "@/lib/parkedLanes";
import { sceneOf } from "@/lib/scene";
import { armGate, canSubmit, settleSubmit, startSubmit } from "@/lib/submitGate";
import type { Catalog, GuildEvent, Lane, RunView } from "@/lib/types";

/**
 * Neither overlay has a dedicated trigger to return to: any card opens the
 * panel, and a `prompt` event can open the spotlight by itself. Prefer the cue
 * line when the floor is up; otherwise the call sheet. Both are tabindex -1 so
 * they are not in the tab order. Do not invent a fake trigger.
 */
function restoreConsoleFocus() {
  const cue = document.getElementById("cue-line");
  if (cue) {
    cue.focus({ preventScroll: true });
    return;
  }
  document.getElementById("guild-call-sheet")?.focus({ preventScroll: true });
}

const KIND_LABEL: Record<string, string> = {
  prompt: "Freeform",
  command: "Command",
  specialist: "Specialist",
};

/** What the show is called on the floor: the ask, else the target, else the kind. */
function productionTitle(spec: LaunchSpec): string {
  const text = spec.text.trim();
  if (text) return text;
  const target = spec.target.trim();
  if (target) return target;
  return KIND_LABEL[spec.kind] ?? spec.kind;
}

export default function App() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [view, setView] = useState<RunView>(() => emptyRun("prompt"));
  const [selected, setSelected] = useState<Lane | null>(null);
  const [spotlightOpen, setSpotlightOpen] = useState(false);
  // Set on Spotlight dismiss; consumed after the floor leaves inert so
  // #cue-line.focus() is not a no-op on a still-inert wrapper.
  const [restoreFocus, setRestoreFocus] = useState(false);
  // prompt_ids whose answer is in flight: dropped from the queue optimistically
  // so the spotlight advances to the next decision without waiting for the round
  // trip, and restored if the POST fails (the agent is still parked).
  const [answering, setAnswering] = useState<string[]>([]);
  // Which decision may be submitted, and which one is already submitted. Kept
  // here rather than in Spotlight because the canvas is remounted the instant
  // the queue advances and would lose the flag exactly when it matters.
  const [gate, setGate] = useState(() => armGate(null));
  const [stopped, setStopped] = useState(false);
  // The mode this run is CURRENTLY on, which the Launcher's select cannot
  // represent: that one configures the next run.
  const [liveMode, setLiveMode] = useState("default");
  const [followUp, setFollowUp] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [runs, setRuns] = useState<api.RunRow[]>([]);
  // The run_id being read back from disk, or null when this is a live run.
  // Recorded runs are strictly read-only: their approval futures died with the
  // process that held them, so there is nothing left to answer or interrupt.
  const [recorded, setRecorded] = useState<string | null>(null);
  const [showTitle, setShowTitle] = useState("The Guild");
  const [runStartedAt, setRunStartedAt] = useState(0);
  const lastSeq = useRef(0);
  // Survives close so LanePanel can animate out; written only while a lane is
  // selected. Declared with the other hooks — selectedLane is derived later.
  const lastSelectedLane = useRef<Lane | null>(null);

  useEffect(() => {
    api.fetchCatalog().then(setCatalog).catch((e) => setError(String(e.message ?? e)));
  }, []);

  const refreshRuns = useCallback(() => {
    api.listRuns().then(setRuns).catch((e) => setError(String((e as Error).message)));
  }, []);

  useEffect(refreshRuns, [refreshRuns]);

  const onEvent = useCallback((event: GuildEvent) => {
    lastSeq.current = Math.max(lastSeq.current, event.seq);
    setView((current) => reduce(current, event));
    if (event.type === "prompt") {
      setSpotlightOpen(true);
      setSelected(null);
    }
    if (event.type === "prompt_resolved")
      setAnswering((ids) => ids.filter((id) => id !== event.prompt_id));
  }, []);

  // A stream that fails for good (a 404 for a run this console process no longer
  // owns — i.e. it was restarted) used to be completely silent: the page simply
  // stopped updating, with the Launcher still disabled behind a run nobody was
  // watching. Say it, and hand the console back.
  const onStreamLost = useCallback(() => {
    setError(
      "Lost the event stream for this run — the console is no longer receiving it. " +
        "Treating the run as ended.",
    );
    setStopped(true);
  }, []);

  useEffect(() => {
    if (!runId) return;
    return api.streamRun(runId, lastSeq.current, onEvent, onStreamLost);
  }, [runId, onEvent, onStreamLost]);

  // A recorded run offers no approvals: a `prompt` with no `prompt_resolved`
  // means the process died holding that decision, and inviting an answer that
  // can never land would be a lie.
  const queue = recorded
    ? []
    : view.pending.filter((prompt) => !answering.includes(prompt.prompt_id));
  const head = queue[0] ?? null;
  const headId = head?.prompt_id ?? null;

  // Live = launched, no terminal outcome (result OR error) and no interrupt yet.
  // Launching a second run while one is live abandoned the first: its SDK client
  // stayed connected and billing, still reported `running`, and could park on an
  // approval no browser was watching.
  const live = runId !== null && !isRunOver(view) && !stopped;
  const scene = sceneOf({
    runActive: live,
    recorded: recorded !== null,
    pending: queue.length,
    spotlightOpen,
  });

  useEffect(() => {
    document.documentElement.dataset.scene = scene;
    return () => {
      delete document.documentElement.dataset.scene;
    };
  }, [scene]);

  useEffect(() => {
    if (!restoreFocus || scene !== "floor") return;
    restoreConsoleFocus();
    setRestoreFocus(false);
  }, [restoreFocus, scene]);

  // Arming is deliberately an effect: it costs a render cycle AFTER the queue
  // advanced and the spotlight remounted for the next prompt, so the second click
  // of a double-click has nothing enabled to hit. No timer, no confirmation step.
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
    // Drop the previous run id first so `live` cannot flip true on the stale
    // id while createRun is in flight — that left the user on an empty floor
    // if the POST failed.
    setRunId(null);
    setView(emptyRun(spec.kind));
    setSelected(null);
    setAnswering([]);
    setGate(armGate(null));
    setSpotlightOpen(false);
    setStopped(false);
    setLiveMode(spec.mode);
    setRecorded(null);
    setShowTitle(productionTitle(spec));
    setRunStartedAt(Date.now());
    lastSelectedLane.current = null;
    try {
      const { run_id } = await api.createRun(spec);
      setRunId(run_id);
      refreshRuns();
    } catch (e) {
      setError(String((e as Error).message));
    }
  };

  /** Read one run back from its jsonl and replay it through the same reducer. */
  const openRecorded = async (id: string) => {
    setError(null);
    try {
      const events = await api.fetchRun(id);
      const row = runs.find((entry) => entry.run_id === id);
      const kind = row?.spec?.kind ?? "prompt";
      // Detach from any live stream first: the effect below closes the
      // EventSource when runId goes null.
      setRunId(null);
      setSelected(null);
      setSpotlightOpen(false);
      lastSelectedLane.current = null;
      setView(events.reduce(reduce, emptyRun(kind)));
      setRecorded(id);
      setShowTitle(row ? formatRunLabel(row) : id);
    } catch (e) {
      setError(String((e as Error).message));
    }
  };

  const closeRecorded = () => {
    setRecorded(null);
    setView(emptyRun("prompt"));
    setShowTitle("The Guild");
    setSelected(null);
    lastSelectedLane.current = null;
    setError(null);
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

  // The lane behind `selected` re-derived from the live view every render, so
  // the panel's transcript keeps growing with the same lane instead of
  // freezing on the snapshot that was on screen the moment the card was
  // clicked.
  const selectedLane = selected
    ? view.lanes.find((lane) => lane.toolUseId === selected.toolUseId) ?? null
    : null;
  // Keep the last open lane mounted after close so the Sheet can run its
  // `data-ending-style` slide-out. Swapping cards keeps `open` true and only
  // replaces `lane` — the panel does not remount, which is the non-modal
  // "click another card" behaviour.
  if (selectedLane) lastSelectedLane.current = selectedLane;
  const panelLane = selectedLane ?? lastSelectedLane.current;

  const answer = async (payload: Record<string, unknown>) => {
    if (!runId) return;
    const promptId = String(payload.prompt_id ?? "");
    // One click, one decision. The buttons are already disabled while the gate
    // is closed; this refuses anything that gets past them anyway.
    if (!canSubmit(gate, promptId)) return;
    setGate((current) => startSubmit(current, promptId));
    setAnswering((ids) => [...ids, promptId]);
    try {
      await api.answerPrompt(runId, payload);
      // Close only after the POST lands, and only when this was the last
      // waiting decision. A failed Allow must leave the spotlight up.
      setSpotlightOpen(queue.some((prompt) => prompt.prompt_id !== promptId));
    } catch (e) {
      setAnswering((ids) => ids.filter((id) => id !== promptId));
      setError(String((e as Error).message));
      setSpotlightOpen(true);
    } finally {
      // Releases the gate; the effect above re-arms it for whatever prompt is on
      // screen one render later.
      setGate((current) => settleSubmit(current, promptId));
    }
  };

  // The spec promised the mode could be changed mid-run; the API could, and
  // nothing in the UI called it. Optimistic, and reverted if the API refuses, so
  // the select never shows a mode the run is not actually on.
  const changeMode = async (next: string) => {
    if (!runId) return;
    const previous = liveMode;
    setLiveMode(next);
    try {
      await api.setMode(runId, next);
    } catch (e) {
      setLiveMode(previous);
      setError(String((e as Error).message));
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

  const answerableParked = recorded ? new Set<string>() : parkedLaneIds(view);

  const onSelect = (lane: Lane) => {
    if (!recorded && answerableParked.has(lane.toolUseId)) {
      setSpotlightOpen(true);
      setSelected(null);
      return;
    }
    setSelected(lane);
  };

  if (scene === "call") {
    return (
      <main>
        {(error || view.failure) && (
          <div className="mx-auto max-w-lg space-y-2 px-4 pt-6">
            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
            {view.failure && (
              <section role="alert" className="rounded-xl border-2 border-destructive p-3">
                <h2 className="mb-1 flex items-center gap-2 text-sm font-medium">
                  <AlertTriangle className="size-4" aria-hidden /> The run ended with an error
                </h2>
                <p className="whitespace-pre-wrap text-sm">{view.failure.message}</p>
              </section>
            )}
          </div>
        )}
        <Launcher
          catalog={catalog}
          busy={false}
          busyReason={null}
          onLaunch={launch}
          pastShows={
            runs.length > 0 ? (
              <label className="flex flex-col gap-1.5">
                <span className="text-xs">Past shows</span>
                <select
                  aria-label="Open a recorded run"
                  className="h-9 w-full rounded-md border border-[color-mix(in_oklab,var(--ink)_18%,transparent)] bg-[var(--paper)] px-2 text-sm text-[var(--ink)]"
                  value=""
                  onChange={(event) => {
                    if (event.target.value) void openRecorded(event.target.value);
                  }}
                >
                  <option value="">Recorded runs…</option>
                  {runs.map((row) => (
                    <option key={row.run_id} value={row.run_id}>
                      {formatRunLabel(row)}
                    </option>
                  ))}
                </select>
              </label>
            ) : null
          }
        />
      </main>
    );
  }

  return (
    <main className="min-h-dvh bg-[var(--floor)]">
      <div
        data-floor=""
        inert={scene === "spotlight" ? true : undefined}
        aria-hidden={scene === "spotlight" || undefined}
      >
      <header className="mb-4 flex items-baseline gap-3 bg-[var(--floor)] px-4 pt-4 md:px-6">
        <ShowHeader
          title={showTitle}
          live={live}
          startedAt={runStartedAt}
          outcome={
            runId && !recorded
              ? view.result
                ? "done"
                : view.failure
                  ? "error"
                  : stopped
                    ? "stopped"
                    : null
              : null
          }
          onStop={live ? interrupt : undefined}
          onBack={recorded ? closeRecorded : undefined}
          onCue={
            scene === "floor" && head ? () => setSpotlightOpen(true) : undefined
          }
          cueTool={head?.tool}
        />
        {live && (
          <div className="ml-auto flex items-center gap-2">
            <select
              aria-label="Change this run's permission mode"
              className="h-8 rounded-md border bg-background px-2 text-sm"
              value={liveMode}
              onChange={(event) => changeMode(event.target.value)}
            >
              <option value="default">Ask me</option>
              <option value="acceptEdits">Accept edits</option>
              <option value="plan">Plan only</option>
            </select>
          </div>
        )}
      </header>

      {/* Deliberately not "it has finished": GET /api/runs lists live runs too, so
          the one being replayed may still be running elsewhere. What is reliably
          true is that this view is a replay and cannot act on it. */}
      <AnimatePresence>
        {recorded && (
          <motion.p
            {...fadeRise}
            className="mb-3 rounded-lg border px-3 py-2 text-sm text-muted-foreground"
          >
            Viewing a recorded run — {recorded}. Read-only replay: approvals and
            interrupts are not available here.
          </motion.p>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {packBroken && (
          <motion.p
            role="alert"
            {...fadeRise}
            className="mb-3 flex items-center gap-2 rounded-lg border-2 border-destructive px-3 py-2 text-sm"
          >
            <AlertTriangle className="size-4" aria-hidden />
            The Guild pack did not load cleanly — agents may be missing.
          </motion.p>
        )}
      </AnimatePresence>
      <AnimatePresence>
        {error && (
          <motion.p role="alert" {...fadeRise} className="mb-3 text-sm text-destructive">
            {error}
          </motion.p>
        )}
      </AnimatePresence>
      {/* The main thread has no card to carry this, and in a freeform run it is
          where most tool calls happen. */}
      <AnimatePresence>
        {view.unasked > 0 && (
          <motion.p {...fadeRise} className="mb-3 text-xs text-muted-foreground">
            {`${view.unasked} ran unasked on the main thread`}
          </motion.p>
        )}
      </AnimatePresence>
      <AnimatePresence>
        {view.retry && (
          <motion.p {...fadeRise} className="mb-3 text-xs text-muted-foreground">
            Retrying after {view.retry.error} — attempt {view.retry.attempt} of {view.retry.max_retries}
          </motion.p>
        )}
      </AnimatePresence>

      {view.mode === "board" ? (
        <Board
          view={view}
          catalog={catalog}
          onSelect={onSelect}
          parkedLanes={answerableParked}
        />
      ) : (
        <FocusRun view={view} catalog={catalog} />
      )}

      <AnimatePresence>
        {panelLane && (
          <LanePanel
            open={selectedLane !== null}
            lane={panelLane}
            agent={catalog.agents.find((a) => a.slug === panelLane.slug)}
            parked={answerableParked.has(panelLane.toolUseId)}
            onClose={() => {
              setSelected(null);
              restoreConsoleFocus();
            }}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {view.result && (
          <motion.section {...fadeRise} className="mt-4 rounded-xl border bg-muted/30 p-3">
            <h2 className="mb-1 text-sm font-medium">Final answer</h2>
            {/* Agents answer in markdown — headings, bullets, fenced diffs. As
                pre-wrapped text it read as a wall of asterisks and backticks. */}
            <Markdown>{view.result.result}</Markdown>
          </motion.section>
        )}
      </AnimatePresence>

      {/* The run died without a result — say why instead of looking idle. */}
      <AnimatePresence>
        {view.failure && (
          <motion.section
            role="alert"
            {...fadeRise}
            className="mt-4 rounded-xl border-2 border-destructive p-3"
          >
            <h2 className="mb-1 flex items-center gap-2 text-sm font-medium">
              <AlertTriangle className="size-4" aria-hidden /> The run ended with an error
            </h2>
            <p className="whitespace-pre-wrap text-sm">{view.failure.message}</p>
          </motion.section>
        )}
      </AnimatePresence>

      {/* Clarifications arrive as plain text; this is how the user replies. */}
      {live && (
        <form
          id="cue-line"
          tabIndex={-1}
          className="mt-4 flex items-center gap-2 bg-[var(--floor)] px-4 pb-4 text-[var(--paper)] md:px-6"
          onSubmit={sendFollowUp}
        >
          <Input
            className="flex-1 border-[color-mix(in_oklab,var(--paper)_18%,transparent)] bg-transparent text-[var(--paper)] placeholder:text-[color-mix(in_oklab,var(--paper)_70%,transparent)]"
            aria-label="Follow-up message"
            placeholder="Reply to the Guild, or add context…"
            value={followUp}
            onChange={(event) => setFollowUp(event.target.value)}
          />
          <Button
            type="submit"
            variant="secondary"
            className="bg-[var(--paper)] text-[var(--ink)] hover:bg-[var(--paper)]"
            disabled={!followUp.trim()}
          >
            <Send className="mr-1 size-4" aria-hidden /> Send
          </Button>
        </form>
      )}

      </div>

      {scene === "spotlight" && head && (
        // key: per-prompt local state (selections, the Other fields, the deny
        // reason) must not leak from one prompt into the next. Outside the
        // floor wrapper so inert/aria-hidden do not hide the canvas.
        <div className="fixed inset-0 z-50 overflow-auto">
          <Spotlight
            key={head.prompt_id}
            pending={head}
            disabled={!canSubmit(gate, head.prompt_id)}
            queueLength={queue.length}
            agent={catalog.agents.find((agent) => agent.slug === head.agent)}
            onClose={() => {
              setSpotlightOpen(false);
              setRestoreFocus(true);
            }}
            onAnswer={answer}
          />
        </div>
      )}
    </main>
  );
}
