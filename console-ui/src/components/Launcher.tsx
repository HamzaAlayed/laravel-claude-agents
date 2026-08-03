import { useState } from "react";
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

/** "backend-developer" → "backend developer" — the catalog's slug IS the role. */
export const roleOf = (slug: string) => slug.replace(/-/g, " ");

export function Launcher({
  catalog,
  busy,
  busyReason,
  onLaunch,
}: {
  catalog: Catalog;
  busy: boolean;
  /** Shown next to the disabled Run button — never refuse a press silently. */
  busyReason: string | null;
  onLaunch: (spec: LaunchSpec) => void;
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

  return (
    <form
      className="mb-4 space-y-2 rounded-xl border p-3"
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
      <div className="flex flex-wrap items-center gap-2">
        <div role="group" aria-label="Run kind" className="flex gap-0.5 rounded-lg border p-0.5">
          {KINDS.map((entry) => (
            <Button
              key={entry.value}
              type="button"
              size="sm"
              variant={kind === entry.value ? "default" : "ghost"}
              aria-pressed={kind === entry.value}
              onClick={() => {
                setKind(entry.value);
                setTarget("");
              }}
            >
              {entry.label}
            </Button>
          ))}
        </div>

        {targets.length > 0 && (
          <label className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground">
              {kind === "command" ? "Command" : "Specialist"}
            </span>
            <select
              aria-label="Target"
              className="h-9 max-w-56 rounded-md border bg-background px-2 text-sm"
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

        <select
          aria-label="Permission mode"
          className="ml-auto h-9 rounded-md border bg-background px-2 text-sm"
          value={mode}
          onChange={(event) => setMode(event.target.value)}
        >
          {MODES.map((entry) => (
            <option key={entry.value} value={entry.value}>
              {entry.label}
            </option>
          ))}
        </select>

        <Button type="submit" disabled={busy} title={busy ? (busyReason ?? undefined) : undefined}>
          <Play className="mr-1 size-4" aria-hidden /> Run
        </Button>
      </div>

      <Input
        className="w-full"
        placeholder={kind === "command" ? "arguments (optional)" : "describe the task"}
        value={text}
        onChange={(event) => setText(event.target.value)}
      />

      <p className="text-xs text-muted-foreground">
        {kindCaption} {modeCaption} <kbd className="rounded border px-1">⌘/Ctrl ↵</kbd> to run.
      </p>

      {busy && busyReason && (
        <p className="text-xs text-muted-foreground">{busyReason}</p>
      )}
    </form>
  );
}
