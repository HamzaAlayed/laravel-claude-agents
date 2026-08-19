import { useState, type ReactNode } from "react";
import { Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { Catalog } from "@/lib/types";

export type LaunchSpec = { kind: string; target: string; text: string; mode: string };

const KINDS = [
  { value: "prompt", label: "Freeform", caption: "Give the Guild a task in your own words." },
  { value: "command", label: "Command", caption: "Run one of the pack's slash commands." },
  { value: "specialist", label: "Specialist", caption: "Send a task straight to one specialist." },
] as const;

const MODES = [
  { value: "default", label: "Ask me", caption: "Asks before edits and commands." },
  { value: "acceptEdits", label: "Accept edits", caption: "Edits land without asking." },
  { value: "plan", label: "Plan only", caption: "Plans only, changes nothing." },
] as const;

const fieldClass =
  "w-full rounded-md border border-[color-mix(in_oklab,var(--ink)_18%,transparent)] bg-[var(--paper)] px-2 text-sm text-[var(--ink)]";

const captionClass = "text-xs text-[color-mix(in_oklab,var(--ink)_70%,transparent)]";

/** "backend-developer" → "backend developer" — the catalog's slug IS the role. */
export const roleOf = (slug: string) => slug.replace(/-/g, " ");

export function Launcher({
  catalog,
  busy,
  busyReason,
  onLaunch,
  pastShows,
}: {
  catalog: Catalog;
  busy: boolean;
  /** Shown when Start is disabled — never refuse a press silently. */
  busyReason: string | null;
  onLaunch: (spec: LaunchSpec) => void;
  /** Recorded-run picker — lives on the call sheet, not the floor. */
  pastShows?: ReactNode;
}) {
  const [kind, setKind] = useState<string>("prompt");
  const [target, setTarget] = useState("");
  const [text, setText] = useState("");
  const [mode, setMode] = useState<string>("default");

  const targets =
    kind === "command"
      ? catalog.commands.map((command) => ({ value: command.slug, label: `/${command.slug}` }))
      : kind === "specialist"
        ? catalog.agents
            .filter((agent) => agent.stage !== null)
            .map((agent) => ({ value: agent.slug, label: `${agent.name} — ${roleOf(agent.slug)}` }))
        : [];

  const kindCaption = KINDS.find((entry) => entry.value === kind)?.caption ?? "";
  const modeCaption = MODES.find((entry) => entry.value === mode)?.caption ?? "";
  const targetLabel = kind === "command" ? "Command" : "Specialist";

  return (
    <form
      id="guild-call-sheet"
      tabIndex={-1}
      // Focus target when an overlay closes: no dedicated trigger exists.
      className="flex min-h-dvh flex-col items-center justify-center bg-background px-4 py-10"
      onSubmit={(event) => {
        event.preventDefault();
        if (busy) return; // implicit submission must not sneak past the disabled button
        onLaunch({ kind, target, text, mode });
      }}
      onKeyDown={(event) => {
        // Cmd/Ctrl+Enter runs from anywhere in the form; the submit handler
        // still holds the busy gate.
        if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
          event.preventDefault();
          event.currentTarget.requestSubmit();
        }
      }}
    >
      <div className="w-full max-w-lg space-y-6 bg-[var(--paper)] px-8 py-10 text-[var(--ink)] shadow-[0_18px_40px_color-mix(in_oklab,var(--floor)_18%,transparent)]">
        <header className="space-y-1">
          <h1 className="font-heading text-4xl font-extrabold tracking-tight">The Guild</h1>
          <p className={captionClass}>Call sheet — start a production</p>
        </header>

        <div className="space-y-2">
          <div
            role="group"
            aria-label="Run kind"
            className="flex flex-wrap gap-1 border border-[color-mix(in_oklab,var(--ink)_14%,transparent)] p-1"
          >
            {KINDS.map((entry) => (
              <Button
                key={entry.value}
                type="button"
                size="sm"
                variant="ghost"
                aria-pressed={kind === entry.value}
                className={
                  kind === entry.value
                    ? "bg-[var(--ink)] text-[var(--paper)] hover:bg-[var(--ink)] hover:text-[var(--paper)]"
                    : "text-[var(--ink)]"
                }
                onClick={() => {
                  setKind(entry.value);
                  setTarget("");
                }}
              >
                {entry.label}
              </Button>
            ))}
          </div>
          <p className={captionClass}>{kindCaption}</p>
        </div>

        {targets.length > 0 && (
          <label className="flex flex-col gap-1.5">
            <span className="text-xs">{targetLabel}</span>
            <select
              aria-label={targetLabel}
              className={`${fieldClass} h-9`}
              value={target}
              onChange={(event) => setTarget(event.target.value)}
              required
            >
              <option value="">Choose…</option>
              {targets.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        )}

        <label className="flex flex-col gap-1.5">
          <span className="text-xs">Permission mode</span>
          <select
            aria-label="Permission mode"
            className={`${fieldClass} h-9`}
            value={mode}
            onChange={(event) => setMode(event.target.value)}
          >
            {MODES.map((entry) => (
              <option key={entry.value} value={entry.value}>
                {entry.label}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-xs">{kind === "command" ? "Arguments" : "Task"}</span>
          <Input
            aria-label={kind === "command" ? "Arguments" : "Task"}
            className={`${fieldClass} h-10`}
            placeholder={kind === "command" ? "arguments (optional)" : "describe the task"}
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        </label>

        <p className={captionClass}>
          {modeCaption}{" "}
          <kbd className="rounded border border-[color-mix(in_oklab,var(--ink)_18%,transparent)] px-1 font-mono">
            ⌘/Ctrl ↵
          </kbd>{" "}
          to start.
        </p>

        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="submit"
            size="lg"
            disabled={busy}
            title={busy ? (busyReason ?? undefined) : undefined}
          >
            <Play className="mr-1 size-4" aria-hidden /> Start
          </Button>
          {busy && busyReason && <p className={captionClass}>{busyReason}</p>}
        </div>

        {pastShows}
      </div>
    </form>
  );
}
