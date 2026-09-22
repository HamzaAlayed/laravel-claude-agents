import { useCallback, useEffect, useState, type ComponentType } from "react";
import {
  Activity,
  ArrowUpRight,
  Bot,
  CheckCircle2,
  CircleDot,
  Eye,
  EyeOff,
  GitBranch,
  GitPullRequest,
  LayoutDashboard,
  Play,
  Plus,
  Radar,
  RefreshCcw,
  ShieldCheck,
  Sparkles,
  Workflow,
  Wrench,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import * as api from "@/lib/api";
import type { LaunchSpec } from "@/components/Launcher";

const fieldClass = "h-10 border-input bg-background text-foreground";

function runText(row: api.DeliveryRow): string {
  return typeof row.issue_number === "number"
    ? `${row.name} --issue ${row.issue_number}`
    : row.name;
}

function statusLabel(status: string): string {
  switch (status) {
    case "running":
      return "In progress";
    case "done":
      return "Finished";
    case "stopped":
      return "Needs attention";
    default:
      return status ? status : "Not started";
  }
}

function MetricCard({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  label: string;
  value: number;
  detail: string;
}) {
  return (
    <Card size="sm" className="min-w-0 bg-card/75">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xs font-semibold tracking-[0.12em] text-muted-foreground uppercase">
          <Icon className="size-4 text-primary" aria-hidden />
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex items-end justify-between gap-3">
        <strong className="font-mono text-3xl font-medium tracking-tight text-foreground tabular-nums">
          {String(value).padStart(2, "0")}
        </strong>
        <span className="pb-1 text-right text-xs text-muted-foreground">{detail}</span>
      </CardContent>
    </Card>
  );
}

function EmptyWorkspace({ onNewRun }: { onNewRun: () => void }) {
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
      <Card className="desk-network relative min-h-[28rem] overflow-hidden bg-card/70">
        <div className="pointer-events-none absolute inset-0" aria-hidden="true">
          <svg className="size-full" viewBox="0 0 760 440" preserveAspectRatio="xMidYMid slice">
            <g className="desk-network-lines">
              <path d="M130 284 L306 158 L508 216 L642 112" />
              <path d="M130 284 L354 330 L508 216" />
              <path d="M306 158 L354 330 L642 352" />
              <path d="M508 216 L642 352" />
            </g>
            <g className="desk-network-dots">
              <circle cx="130" cy="284" r="7" />
              <circle cx="306" cy="158" r="10" />
              <circle cx="354" cy="330" r="6" />
              <circle cx="508" cy="216" r="13" />
              <circle cx="642" cy="112" r="6" />
              <circle cx="642" cy="352" r="8" />
            </g>
          </svg>
          <span className="desk-node left-[12%] top-[60%]">Task</span>
          <span className="desk-node left-[34%] top-[25%]">Plan</span>
          <span className="desk-node left-[58%] top-[41%]">Build</span>
          <span className="desk-node right-[9%] top-[16%]">Review</span>
          <span className="desk-node right-[8%] bottom-[13%]">Ship</span>
        </div>

        <CardContent className="relative flex min-h-[28rem] items-end p-6 sm:p-8">
          <div className="max-w-lg rounded-2xl border border-border/80 bg-background/90 p-5 shadow-2xl backdrop-blur-sm sm:p-6">
            <Badge variant="outline" className="mb-4 border-primary/30 bg-primary/10 text-primary">
              <Sparkles data-icon="inline-start" aria-hidden />
              Ready for work
            </Badge>
            <h2 className="text-pretty font-heading text-2xl font-bold tracking-tight sm:text-3xl">
              Your delivery map starts here
            </h2>
            <p className="mt-3 max-w-md text-pretty text-sm leading-6 text-muted-foreground">
              Start with a task. The Guild plans the work, routes it to specialists, and brings decisions back to you.
            </p>
            <Button type="button" size="lg" className="mt-5" onClick={onNewRun}>
              <Plus data-icon="inline-start" aria-hidden />
              Create your first run
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card/70">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Workflow className="size-4 text-primary" aria-hidden />
            How work moves
          </CardTitle>
          <CardDescription>One clear path from request to delivery.</CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="flex flex-col gap-6">
            {[
              ["01", "Describe the outcome", "Use plain language or pick a Guild command."],
              ["02", "Watch the specialists", "See who is working and answer decisions as they appear."],
              ["03", "Return to the delivery", "Continue later or monitor its pull request from this desk."],
            ].map(([number, title, description]) => (
              <li key={number} className="grid grid-cols-[2.25rem_1fr] gap-3">
                <span className="font-mono text-xs text-primary tabular-nums">{number}</span>
                <div>
                  <h3 className="text-sm font-semibold text-foreground">{title}</h3>
                  <p className="mt-1 text-sm leading-5 text-muted-foreground">{description}</p>
                </div>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}

function DeliveryCard({
  row,
  busy,
  repairing,
  stage,
  check,
  onStageChange,
  onCheckChange,
  onLaunch,
  onToggleWatch,
  onToggleRepair,
  onReopenCheck,
}: {
  row: api.DeliveryRow;
  busy: boolean;
  repairing: boolean;
  stage: string;
  check: string;
  onStageChange: (value: string) => void;
  onCheckChange: (value: string) => void;
  onLaunch: () => void;
  onToggleWatch: () => void;
  onToggleRepair: () => void;
  onReopenCheck: () => void;
}) {
  const steps = row.steps ?? [];
  const finishedSteps = steps.filter((step) => /done|finished|complete/i.test(step.state)).length;

  return (
    <Card className="delivery-card bg-card/75">
      <CardHeader>
        <div className="mb-2 flex items-center gap-2 text-xs font-medium tracking-[0.12em] text-muted-foreground uppercase">
          <GitBranch className="size-3.5" aria-hidden />
          Delivery
        </div>
        <CardTitle>
          <h2 className="break-words text-xl font-semibold tracking-tight">{row.name}</h2>
        </CardTitle>
        <CardDescription className="line-clamp-2 leading-5">
          {row.done_when ? `Done when ${row.done_when}` : "No completion condition has been recorded yet."}
        </CardDescription>
        <CardAction>
          <Badge className="delivery-status" data-status={row.status || "idle"} variant="outline">
            <CircleDot data-icon="inline-start" aria-hidden />
            {statusLabel(row.status)}
          </Badge>
        </CardAction>
      </CardHeader>

      <CardContent className="flex flex-col gap-5">
        <div>
          <div className="mb-2 flex items-center justify-between gap-3 text-xs text-muted-foreground">
            <span>Delivery progress</span>
            <span className="font-mono tabular-nums">
              {steps.length > 0 ? `${finishedSteps}/${steps.length} stages` : "No stages yet"}
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${steps.length > 0 ? Math.max(8, (finishedSteps / steps.length) * 100) : 0}%` }}
            />
          </div>
        </div>

        {steps.length > 0 ? (
          <ol className="flex flex-col gap-2" aria-label={`Steps for ${row.name}`}>
            {steps.map((step, index) => (
              <li
                key={`${step.who}-${index}`}
                className="flex min-w-0 items-center justify-between gap-3 rounded-lg border border-border/70 bg-background/45 px-3 py-2.5 text-sm"
              >
                <span className="min-w-0 truncate">{step.who}</span>
                <span className="shrink-0 text-xs text-muted-foreground">{step.state}</span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="rounded-lg border border-dashed border-border px-3 py-4 text-sm text-muted-foreground">
            Stages will appear after the Guild plans this delivery.
          </p>
        )}

        <div className="flex flex-wrap gap-2 text-xs">
          {row.issue_url ? (
            <a className="desk-link" href={row.issue_url}>
              Issue {typeof row.issue_number === "number" ? `#${row.issue_number}` : ""}
              <ArrowUpRight aria-hidden />
            </a>
          ) : null}
          {row.pr_url ? (
            <a className="desk-link" href={row.pr_url}>
              PR{row.pr_state ? ` · ${row.pr_state}` : ""}
              <ArrowUpRight aria-hidden />
            </a>
          ) : (
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <GitPullRequest className="size-3.5" aria-hidden />
              No pull request yet
            </span>
          )}
        </div>
      </CardContent>

      <CardFooter className="flex flex-wrap justify-between gap-3 bg-muted/30">
        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={onLaunch}>
            <Play data-icon="inline-start" aria-hidden />
            {row.status === "running" ? "Continue delivery" : "Run delivery"}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={busy || !row.pr_url}
            title={!row.pr_url ? "A pull request is required before monitoring can start." : undefined}
            onClick={onToggleWatch}
          >
            {row.watching ? (
              <EyeOff data-icon="inline-start" aria-hidden />
            ) : (
              <Eye data-icon="inline-start" aria-hidden />
            )}
            {row.watching ? "Stop monitoring" : "Monitor PR"}
          </Button>
        </div>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          aria-expanded={repairing}
          aria-controls={`repair-${row.name}`}
          onClick={onToggleRepair}
        >
          <Wrench data-icon="inline-start" aria-hidden />
          Reopen a failed check
        </Button>
      </CardFooter>

      {repairing ? (
        <div id={`repair-${row.name}`} className="border-t border-border px-4 py-5">
          <div className="mb-4 flex items-start gap-3">
            <RefreshCcw className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
            <div>
              <h3 className="text-sm font-semibold">Send one stage back to work</h3>
              <p className="mt-1 text-sm leading-5 text-muted-foreground">
                Enter the stage ID and the failed GitHub check. The Guild will reopen only that stage.
              </p>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium">Stage ID</span>
              <Input
                className={fieldClass}
                name={`stage-${row.name}`}
                autoComplete="off"
                placeholder="Example: a…"
                value={stage}
                onChange={(event) => onStageChange(event.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium">GitHub check</span>
              <Input
                className={fieldClass}
                name={`check-${row.name}`}
                autoComplete="off"
                placeholder="Example: pint…"
                value={check}
                onChange={(event) => onCheckChange(event.target.value)}
              />
            </label>
          </div>
          <Button
            type="button"
            className="mt-4"
            variant="secondary"
            disabled={busy || !stage.trim() || !check.trim()}
            onClick={onReopenCheck}
          >
            <RefreshCcw data-icon="inline-start" aria-hidden />
            Reopen stage
          </Button>
        </div>
      ) : null}
    </Card>
  );
}

export function Desk({
  onNewRun,
  onLaunch,
}: {
  onNewRun: () => void;
  onLaunch: (spec: LaunchSpec) => void;
}) {
  const [deliveries, setDeliveries] = useState<api.DeliveryRow[] | null>(null);
  const [stage, setStage] = useState("");
  const [check, setCheck] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showRepair, setShowRepair] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api
      .listDeliveries()
      .then((payload) => setDeliveries(payload.deliveries))
      .catch((e) => setError(String((e as Error).message ?? e)));
  }, []);

  useEffect(refresh, [refresh]);

  const launchRow = (row: api.DeliveryRow) => {
    onLaunch({
      kind: "command",
      target: "make-feature",
      text: runText(row),
      mode: "managed",
    });
  };

  const toggleWatch = async (row: api.DeliveryRow) => {
    setError(null);
    setBusy(true);
    try {
      await api.setWatch(row.name, !row.watching);
      refresh();
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };

  const reopenCheck = async (name: string) => {
    setError(null);
    setBusy(true);
    try {
      await api.ingestKernel({
        name,
        kind: "check",
        stage: stage.trim(),
        check: check.trim(),
      });
      setStage("");
      setCheck("");
      setShowRepair(null);
      refresh();
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };

  const rows = deliveries ?? [];
  const activeCount = rows.filter((row) => row.status === "running").length;
  const attentionCount = rows.filter((row) => row.status === "stopped").length;
  const watchingCount = rows.filter((row) => row.watching).length;

  return (
    <div className="guild-desk min-h-dvh bg-background text-foreground">
      <a href="#desk-content" className="skip-link">
        Skip to deliveries
      </a>

      <aside className="desk-sidebar hidden lg:flex">
        <a href="#desk-content" className="flex items-center gap-3" aria-label="Guild delivery desk home">
          <span className="guild-mark" aria-hidden="true">
            <Bot />
          </span>
          <span>
            <strong className="block font-heading text-base tracking-tight">Guild</strong>
            <span className="block text-[0.65rem] tracking-[0.18em] text-muted-foreground uppercase">
              Operations
            </span>
          </span>
        </a>

        <nav className="mt-10" aria-label="Primary navigation">
          <a className="desk-nav-item" href="#deliveries" aria-current="page">
            <LayoutDashboard aria-hidden />
            Delivery desk
          </a>
        </nav>

        <div className="mt-auto rounded-xl border border-border bg-card/60 p-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
            <span className="size-2 rounded-full bg-primary shadow-[0_0_12px_var(--primary)]" aria-hidden="true" />
            Console ready
          </div>
          <p className="mt-1.5 text-xs leading-5 text-muted-foreground">
            Local workspace connected. Runs stay on this machine.
          </p>
        </div>
      </aside>

      <main id="desk-content" tabIndex={-1} className="min-w-0 lg:pl-64">
        <header className="desk-topbar">
          <div className="flex min-w-0 items-center gap-3">
            <span className="guild-mark lg:hidden" aria-hidden="true">
              <Bot />
            </span>
            <div className="min-w-0">
              <p className="truncate text-xs font-medium tracking-[0.12em] text-muted-foreground uppercase">
                Local workspace / Delivery desk
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="size-4 text-primary" aria-hidden />
            <span className="hidden sm:inline">Protected local session</span>
          </div>
        </header>

        <div className="mx-auto flex w-full max-w-[96rem] flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <section id="deliveries" aria-labelledby="deliveries-title">
            <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
              <div className="max-w-2xl">
                <Badge variant="outline" className="mb-3 border-primary/30 bg-primary/10 text-primary">
                  <Radar data-icon="inline-start" aria-hidden />
                  Workspace overview
                </Badge>
                <h1
                  id="deliveries-title"
                  className="text-balance font-heading text-3xl font-bold tracking-tight sm:text-4xl"
                >
                  Deliveries
                </h1>
                <p className="mt-3 max-w-xl text-pretty text-sm leading-6 text-muted-foreground sm:text-base">
                  Start new work, return to a delivery, and monitor its pull request from one place.
                </p>
              </div>
              <Button type="button" size="lg" aria-label="New run" onClick={onNewRun}>
                <Plus data-icon="inline-start" aria-hidden />
                New run
              </Button>
            </div>
          </section>

          <section className="grid gap-3 sm:grid-cols-3" aria-label="Delivery overview">
            <MetricCard icon={Activity} label="Active" value={activeCount} detail="running now" />
            <MetricCard icon={CircleDot} label="Attention" value={attentionCount} detail="need a decision" />
            <MetricCard icon={Eye} label="Monitored" value={watchingCount} detail="pull requests" />
          </section>

          {error ? (
            <div role="alert" className="rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              <strong className="font-semibold">The delivery desk could not update.</strong>{" "}
              {error} Try again after checking the local console server.
            </div>
          ) : null}

          {deliveries === null && !error ? (
            <Card className="min-h-72 items-center justify-center bg-card/70" aria-live="polite">
              <CardContent className="flex flex-col items-center gap-3 text-center">
                <RefreshCcw className="size-5 text-primary" aria-hidden />
                <p className="text-sm font-medium">Loading deliveries…</p>
                <p className="text-xs text-muted-foreground">Reading the local delivery workspace.</p>
              </CardContent>
            </Card>
          ) : null}

          {deliveries !== null && rows.length === 0 ? <EmptyWorkspace onNewRun={onNewRun} /> : null}

          {rows.length > 0 ? (
            <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
              <ul className="grid min-w-0 gap-4 2xl:grid-cols-2" aria-label="Deliveries">
                {rows.map((row) => (
                  <li key={row.name} className="min-w-0">
                    <DeliveryCard
                      row={row}
                      busy={busy}
                      repairing={showRepair === row.name}
                      stage={stage}
                      check={check}
                      onStageChange={setStage}
                      onCheckChange={setCheck}
                      onLaunch={() => launchRow(row)}
                      onToggleWatch={() => void toggleWatch(row)}
                      onToggleRepair={() => setShowRepair(showRepair === row.name ? null : row.name)}
                      onReopenCheck={() => void reopenCheck(row.name)}
                    />
                  </li>
                ))}
              </ul>

              <Card className="sticky top-20 bg-card/70">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <CheckCircle2 className="size-4 text-primary" aria-hidden />
                    Desk guide
                  </CardTitle>
                  <CardDescription>What each action does.</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-5 text-sm">
                  <div>
                    <h3 className="font-semibold text-foreground">Continue delivery</h3>
                    <p className="mt-1 leading-5 text-muted-foreground">
                      Opens the live floor and sends the Guild back to that outcome.
                    </p>
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground">Monitor PR</h3>
                    <p className="mt-1 leading-5 text-muted-foreground">
                      Watches for a failed check or review comment and reopens one stage.
                    </p>
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground">Reopen a check</h3>
                    <p className="mt-1 leading-5 text-muted-foreground">
                      Manually returns one known failed check to its owning stage.
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          ) : null}
        </div>
      </main>
    </div>
  );
}
