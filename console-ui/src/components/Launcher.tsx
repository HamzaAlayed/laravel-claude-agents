import { useState, type ReactNode } from "react";
import { ArrowLeft, Bot, Braces, Check, Command, MessageSquareText, Play, ShieldCheck, UserRound } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { Catalog } from "@/lib/types";

export type LaunchSpec = { kind: string; target: string; text: string; mode: string };

const KINDS = [
  {
    value: "prompt",
    label: "Freeform",
    caption: "Describe an outcome in your own words.",
    icon: MessageSquareText,
  },
  {
    value: "command",
    label: "Command",
    caption: "Run one of the Guild’s focused workflows.",
    icon: Command,
  },
  {
    value: "specialist",
    label: "Specialist",
    caption: "Send work directly to one expert.",
    icon: UserRound,
  },
] as const;

const MODES = [
  { value: "managed", label: "Work independently", caption: "Edits and standard project checks continue automatically. Other commands still ask. Use with trusted projects." },
  { value: "default", label: "Ask me", caption: "Asks before edits and commands." },
  { value: "acceptEdits", label: "Accept edits", caption: "Edits land without asking." },
  { value: "plan", label: "Plan only", caption: "Plans only and changes nothing." },
] as const;

const fieldClass = "h-10 border-input bg-background text-foreground";

/** "backend-developer" → "backend developer" — the catalog's slug IS the role. */
export const roleOf = (slug: string) => slug.replace(/-/g, " ");

export function Launcher({
  catalog,
  busy,
  busyReason,
  onLaunch,
  onBack,
  pastShows,
}: {
  catalog: Catalog;
  busy: boolean;
  /** Shown when Start is disabled — never refuse a press silently. */
  busyReason: string | null;
  onLaunch: (spec: LaunchSpec) => void;
  /** Return to the delivery desk without launching. */
  onBack?: () => void;
  /** Recorded-run picker — lives on the call sheet, not the floor. */
  pastShows?: ReactNode;
}) {
  const [kind, setKind] = useState<string>("prompt");
  const [target, setTarget] = useState("");
  const [text, setText] = useState("");
  const [mode, setMode] = useState<string>("managed");

  const targets =
    kind === "command"
      ? catalog.commands.map((command) => ({ value: command.slug, label: `/${command.slug}` }))
      : kind === "specialist"
        ? catalog.agents
            .filter((agent) => agent.stage !== null)
            .map((agent) => ({ value: agent.slug, label: `${agent.name} — ${roleOf(agent.slug)}` }))
        : [];

  const modeCaption = MODES.find((entry) => entry.value === mode)?.caption ?? "";
  const targetLabel = kind === "command" ? "Command" : "Specialist";

  return (
    <form
      id="guild-call-sheet"
      tabIndex={-1}
      className="guild-desk min-h-dvh bg-background text-foreground"
      onSubmit={(event) => {
        event.preventDefault();
        if (busy) return;
        onLaunch({ kind, target, text, mode });
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
          event.preventDefault();
          event.currentTarget.requestSubmit();
        }
      }}
    >
      <header className="desk-topbar">
        <div className="flex items-center gap-3">
          <span className="guild-mark" aria-hidden="true">
            <Bot />
          </span>
          <div>
            <strong className="block font-heading text-sm">Guild</strong>
            <span className="text-[0.65rem] tracking-[0.14em] text-muted-foreground uppercase">
              New run
            </span>
          </div>
        </div>
        {onBack ? (
          <Button type="button" variant="ghost" onClick={onBack}>
            <ArrowLeft data-icon="inline-start" aria-hidden />
            Back to desk
          </Button>
        ) : null}
      </header>

      <div className="mx-auto grid w-full max-w-6xl gap-8 px-4 py-8 sm:px-6 lg:grid-cols-[minmax(0,0.78fr)_minmax(28rem,1.22fr)] lg:items-start lg:px-8 lg:py-12">
        <section className="lg:sticky lg:top-28">
          <Badge variant="outline" className="mb-4 border-primary/30 bg-primary/10 text-primary">
            <Braces data-icon="inline-start" aria-hidden />
            Run launcher
          </Badge>
          <h1 className="text-balance font-heading text-4xl font-bold tracking-tight sm:text-5xl">
            Start with the outcome.
            <span className="block text-primary">The Guild handles the route.</span>
          </h1>
          <p className="mt-5 max-w-lg text-pretty text-base leading-7 text-muted-foreground">
            Choose how you want to begin, tell the team what success looks like, and review each important decision on the live floor.
          </p>

          <ol className="mt-8 flex max-w-md flex-col gap-5">
            {[
              ["01", "Choose a starting point"],
              ["02", "Describe the work"],
              ["03", "Review the live run"],
            ].map(([number, label]) => (
              <li key={number} className="flex items-center gap-4 text-sm">
                <span className="font-mono text-xs text-primary tabular-nums">{number}</span>
                <span className="h-px w-8 bg-border" aria-hidden="true" />
                <span className="font-medium">{label}</span>
              </li>
            ))}
          </ol>

          <div className="mt-8 flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="size-4 text-primary" aria-hidden />
            Runs stay in your local workspace.
          </div>
        </section>

        <Card className="bg-card/80 shadow-2xl shadow-black/20">
          <CardHeader>
            <CardTitle className="text-xl">Configure your run</CardTitle>
            <CardDescription>Pick one path. You can always return to the desk without starting.</CardDescription>
          </CardHeader>

          <CardContent className="flex flex-col gap-6">
            <fieldset aria-label="Run kind">
              <legend className="mb-3 text-xs font-semibold tracking-[0.1em] text-muted-foreground uppercase">
                Run kind
              </legend>
              <div className="grid gap-2 sm:grid-cols-3">
                {KINDS.map((entry) => {
                  const Icon = entry.icon;
                  return (
                    <label key={entry.value} className="group relative cursor-pointer">
                      <input
                        type="radio"
                        name="run-kind"
                        value={entry.value}
                        checked={kind === entry.value}
                        className="peer sr-only"
                        onChange={() => {
                          setKind(entry.value);
                          setTarget("");
                        }}
                      />
                      <span className="flex min-h-28 flex-col rounded-xl border border-border bg-background/35 p-3 transition-[background-color,border-color,box-shadow] group-hover:border-primary/40 peer-checked:border-primary peer-checked:bg-primary/8 peer-focus-visible:ring-3 peer-focus-visible:ring-ring/50">
                        <span className="mb-4 flex items-center justify-between gap-2">
                          <Icon className="size-4 text-primary" aria-hidden />
                          {kind === entry.value ? <Check className="size-3.5 text-primary" aria-hidden /> : null}
                        </span>
                        <strong className="text-sm font-semibold">{entry.label}</strong>
                        <span className="mt-1 text-xs leading-4 text-muted-foreground">{entry.caption}</span>
                      </span>
                    </label>
                  );
                })}
              </div>
            </fieldset>

            {targets.length > 0 ? (
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-semibold">{targetLabel}</span>
                <select
                  aria-label={targetLabel}
                  className={`${fieldClass} rounded-lg border px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50`}
                  value={target}
                  onChange={(event) => setTarget(event.target.value)}
                  required
                >
                  <option value="">Choose {targetLabel.toLowerCase()}…</option>
                  {targets.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}

            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-semibold">Permission mode</span>
              <select
                aria-label="Permission mode"
                className={`${fieldClass} rounded-lg border px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50`}
                value={mode}
                onChange={(event) => setMode(event.target.value)}
              >
                {MODES.map((entry) => (
                  <option key={entry.value} value={entry.value}>
                    {entry.label}
                  </option>
                ))}
              </select>
              <span className="text-xs text-muted-foreground">{modeCaption}</span>
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-semibold">{kind === "command" ? "Arguments" : "Task"}</span>
              {kind === "command" ? (
                <Input
                  aria-label="Arguments"
                  className={fieldClass}
                  name="arguments"
                  autoComplete="off"
                  placeholder="Optional command arguments…"
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                />
              ) : (
                <Textarea
                  aria-label="Task"
                  className="min-h-32 resize-y border-input bg-background text-foreground"
                  name="task"
                  autoComplete="off"
                  placeholder="Describe the task…"
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                />
              )}
            </label>
            <details className="rounded-lg border border-border p-3 text-sm">
              <summary className="cursor-pointer rounded-sm font-medium focus-visible:outline-2 focus-visible:outline-ring">
                Project context and remembered preferences
              </summary>
              <p className="mt-3 text-muted-foreground">
                Each run loads project instructions and refreshes package metadata. Keep explicit preferences in
                {" "}<code>.claude/guild-preferences.md</code>, or ask the Guild to remember a preference there.
                You can edit or remove that file at any time. Don’t store secrets in it.
              </p>
            </details>
          </CardContent>

          <CardFooter className="flex flex-col items-stretch gap-4 bg-muted/30 sm:flex-row sm:items-center">
            <Button
              type="submit"
              size="lg"
              disabled={busy}
              title={busy ? (busyReason ?? undefined) : undefined}
            >
              <Play data-icon="inline-start" aria-hidden />
              Start run
            </Button>
            <p className="text-xs text-muted-foreground">
              Press <kbd className="rounded border border-border bg-background px-1.5 py-0.5 font-mono">⌘/Ctrl&nbsp;↵</kbd>
            </p>
            {busy && busyReason ? <p className="text-xs text-destructive">{busyReason}</p> : null}
          </CardFooter>

          {pastShows ? <div className="border-t border-border px-4 py-4">{pastShows}</div> : null}
        </Card>
      </div>
    </form>
  );
}
