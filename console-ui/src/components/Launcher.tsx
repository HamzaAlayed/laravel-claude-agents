import { useState } from "react";
import { Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { Catalog } from "@/lib/types";

export type LaunchSpec = { kind: string; target: string; text: string; mode: string };

export function Launcher({
  catalog,
  busy,
  onLaunch,
}: {
  catalog: Catalog;
  busy: boolean;
  onLaunch: (spec: LaunchSpec) => void;
}) {
  const [kind, setKind] = useState("prompt");
  const [target, setTarget] = useState("");
  const [text, setText] = useState("");
  const [mode, setMode] = useState("default");

  const targets =
    kind === "command"
      ? catalog.commands.map((command) => ({ value: command.slug, label: `/${command.slug}` }))
      : kind === "specialist"
        ? catalog.agents
            .filter((agent) => agent.stage !== null)
            .map((agent) => ({ value: agent.slug, label: `${agent.name} — ${agent.slug}` }))
        : [];

  return (
    <form
      className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border p-3"
      onSubmit={(event) => {
        event.preventDefault();
        onLaunch({ kind, target, text, mode });
      }}
    >
      <select
        aria-label="Run kind"
        className="h-9 rounded-md border bg-background px-2 text-sm"
        value={kind}
        onChange={(event) => {
          setKind(event.target.value);
          setTarget("");
        }}
      >
        <option value="prompt">Freeform</option>
        <option value="command">Command</option>
        <option value="specialist">Specialist</option>
      </select>

      {targets.length > 0 && (
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
      )}

      <Input
        className="min-w-56 flex-1"
        placeholder={kind === "command" ? "arguments (optional)" : "describe the task"}
        value={text}
        onChange={(event) => setText(event.target.value)}
      />

      <select
        aria-label="Permission mode"
        className="h-9 rounded-md border bg-background px-2 text-sm"
        value={mode}
        onChange={(event) => setMode(event.target.value)}
      >
        <option value="default">Ask me</option>
        <option value="acceptEdits">Accept edits</option>
        <option value="plan">Plan only</option>
      </select>

      <Button type="submit" disabled={busy}>
        <Play className="mr-1 size-4" aria-hidden /> Run
      </Button>
    </form>
  );
}
