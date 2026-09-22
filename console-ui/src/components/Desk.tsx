import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import * as api from "@/lib/api";
import type { LaunchSpec } from "@/components/Launcher";

const fieldClass =
  "w-full rounded-md border border-[color-mix(in_oklab,var(--ink)_18%,transparent)] bg-[var(--paper)] px-2 text-sm text-[var(--ink)]";

const quiet = "text-sm text-[color-mix(in_oklab,var(--ink)_70%,transparent)]";

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
      return "Stopped";
    default:
      return status ? status : "Not started";
  }
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
      mode: "default",
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

  return (
    <div className="flex min-h-dvh flex-col items-center bg-background px-4 py-10 text-[var(--ink)]">
      <div className="flex w-full max-w-lg flex-col gap-8">
        <header className="space-y-3">
          <h1 className="font-heading text-3xl font-extrabold tracking-tight">
            What should the Guild do?
          </h1>
          <p className={quiet}>
            Choose work that's already underway, or start something new. You'll watch the team on the floor once it starts.
          </p>
          <Button type="button" size="lg" aria-label="New run" onClick={onNewRun}>
            Start something new
          </Button>
        </header>

        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}

        {deliveries === null && !error && <p className={quiet}>Loading deliveries…</p>}

        {deliveries !== null && rows.length === 0 && (
          <p className={quiet}>Nothing is underway yet. Start something new and it will show up here.</p>
        )}

        {rows.length > 0 && (
          <ul className="space-y-4" aria-label="Deliveries">
            {rows.map((row) => {
              const steps = row.steps ?? [];
              const repairing = showRepair === row.name;
              return (
                <li
                  key={row.name}
                  className="space-y-4 rounded-xl border border-[color-mix(in_oklab,var(--ink)_14%,transparent)] bg-[var(--paper)] p-4"
                >
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <h2 className="font-heading text-xl font-bold tracking-tight">{row.name}</h2>
                      <span className="text-xs font-medium uppercase tracking-wide text-[color-mix(in_oklab,var(--ink)_60%,transparent)]">
                        {statusLabel(row.status)}
                      </span>
                    </div>
                    {row.done_when ? (
                      <p className={quiet}>Finished when {row.done_when}</p>
                    ) : null}
                  </div>

                  {steps.length > 0 && (
                    <ol className="space-y-1" aria-label={`Steps for ${row.name}`}>
                      {steps.map((step, index) => (
                        <li key={`${step.who}-${index}`} className="flex justify-between gap-3 text-sm">
                          <span>{step.who}</span>
                          <span className={quiet}>{step.state}</span>
                        </li>
                      ))}
                    </ol>
                  )}

                  <div className="flex flex-wrap gap-3 text-sm">
                    {row.issue_url ? (
                      <a className="underline" href={row.issue_url}>
                        GitHub issue{typeof row.issue_number === "number" ? ` ${row.issue_number}` : ""}
                      </a>
                    ) : null}
                    {row.pr_url ? (
                      <a className="underline" href={row.pr_url}>
                        Pull request{row.pr_state ? ` (${row.pr_state})` : ""}
                      </a>
                    ) : (
                      <span className={quiet}>No pull request yet</span>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Button type="button" onClick={() => launchRow(row)}>
                      Continue
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={busy || !row.pr_url}
                      onClick={() => void toggleWatch(row)}
                    >
                      {row.watching ? "Stop watching" : "Watch GitHub"}
                    </Button>
                  </div>
                  <p className={quiet}>
                    {row.pr_url
                      ? "Continue sends the Guild back to this delivery. Watch GitHub reopens the work once if a check fails or someone leaves a review comment."
                      : "Continue sends the Guild back to this delivery. Watch GitHub turns on after a pull request exists."}
                  </p>

                  <div>
                    <button
                      type="button"
                      className="text-sm underline"
                      aria-expanded={repairing}
                      onClick={() => setShowRepair(repairing ? null : row.name)}
                    >
                      A check already failed
                    </button>
                    {repairing && (
                      <div className="mt-3 space-y-3">
                        <p className={quiet}>
                          Name the step id, such as a, and the GitHub check, such as pint. That step is sent back to work.
                        </p>
                        <div className="grid gap-3 sm:grid-cols-2">
                          <label className="flex flex-col gap-1.5">
                            <span className="text-xs">Step id</span>
                            <Input
                              className={fieldClass}
                              aria-label={`Step id for ${row.name}`}
                              value={stage}
                              onChange={(event) => setStage(event.target.value)}
                            />
                          </label>
                          <label className="flex flex-col gap-1.5">
                            <span className="text-xs">GitHub check</span>
                            <Input
                              className={fieldClass}
                              aria-label={`GitHub check for ${row.name}`}
                              value={check}
                              onChange={(event) => setCheck(event.target.value)}
                            />
                          </label>
                        </div>
                        <Button
                          type="button"
                          variant="outline"
                          disabled={busy || !stage.trim() || !check.trim()}
                          onClick={() => void reopenCheck(row.name)}
                        >
                          Send this step back
                        </Button>
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
