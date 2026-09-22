import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import * as api from "@/lib/api";
import type { LaunchSpec } from "@/components/Launcher";

const fieldClass =
  "w-full rounded-md border border-[color-mix(in_oklab,var(--ink)_18%,transparent)] bg-[var(--paper)] px-2 text-sm text-[var(--ink)]";

function runText(row: api.DeliveryRow): string {
  return typeof row.issue_number === "number"
    ? `${row.name} --issue ${row.issue_number}`
    : row.name;
}

export function Desk({
  onNewRun,
  onLaunch,
}: {
  onNewRun: () => void;
  onLaunch: (spec: LaunchSpec) => void;
}) {
  const [deliveries, setDeliveries] = useState<api.DeliveryRow[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [stage, setStage] = useState("");
  const [check, setCheck] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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

  const reopenCheck = async () => {
    if (!selected) return;
    setError(null);
    setBusy(true);
    try {
      await api.ingestKernel({
        name: selected,
        kind: "check",
        stage: stage.trim(),
        check: check.trim(),
      });
      refresh();
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };

  const rows = deliveries ?? [];
  const selectedRow = rows.find((row) => row.name === selected) ?? null;

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-2xl flex-col gap-6 bg-[var(--floor)] px-4 py-10 text-[var(--paper)]">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="font-heading text-4xl font-extrabold tracking-tight text-[var(--paper)]">
            The Guild
          </h1>
          <p className="text-sm text-[color-mix(in_oklab,var(--paper)_70%,transparent)]">
            Delivery desk
          </p>
        </div>
        <Button
          type="button"
          size="lg"
          className="bg-[var(--paper)] text-[var(--ink)] hover:bg-[var(--paper)]"
          onClick={onNewRun}
        >
          New run
        </Button>
      </header>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      {deliveries !== null && rows.length === 0 && (
        <p className="text-sm text-[color-mix(in_oklab,var(--paper)_70%,transparent)]">
          There are no deliveries.
        </p>
      )}

      {rows.length > 0 && (
        <ul className="space-y-3" aria-label="Deliveries">
          {rows.map((row) => {
            const isSelected = selected === row.name;
            return (
              <li
                key={row.name}
                className={`rounded-lg border px-3 py-3 ${
                  isSelected
                    ? "border-[var(--paper)] bg-[color-mix(in_oklab,var(--paper)_12%,transparent)]"
                    : "border-[color-mix(in_oklab,var(--paper)_18%,transparent)] bg-transparent"
                }`}
              >
                <button
                  type="button"
                  aria-pressed={isSelected}
                  className="w-full text-left"
                  onClick={() => setSelected(row.name)}
                >
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="font-medium text-[var(--paper)]">{row.name}</span>
                    <span className="text-xs text-[color-mix(in_oklab,var(--paper)_70%,transparent)]">
                      {row.status}
                    </span>
                  </div>
                  {row.issue_url ? (
                    <p className="mt-1 truncate text-xs text-[color-mix(in_oklab,var(--paper)_70%,transparent)]">
                      {row.issue_url}
                    </p>
                  ) : null}
                  {row.pr_url ? (
                    <p className="truncate text-xs text-[color-mix(in_oklab,var(--paper)_70%,transparent)]">
                      {row.pr_url}
                    </p>
                  ) : null}
                  <p className="mt-2 text-xs text-[var(--paper)]">{row.board}</p>
                </button>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    className="bg-[var(--paper)] text-[var(--ink)] hover:bg-[var(--paper)]"
                    onClick={() => launchRow(row)}
                  >
                    Run
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="border-[color-mix(in_oklab,var(--paper)_30%,transparent)] text-[var(--paper)]"
                    disabled={busy || !row.pr_url}
                    onClick={() => void toggleWatch(row)}
                  >
                    {row.watching ? "Unwatch" : "Watch"}
                  </Button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {selectedRow && (
        <section
          aria-label="Reopen check"
          className="space-y-3 border-t border-[color-mix(in_oklab,var(--paper)_18%,transparent)] pt-6"
        >
          <h2 className="text-sm font-medium text-[var(--paper)]">
            Reopen {selectedRow.name}
          </h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-[color-mix(in_oklab,var(--paper)_70%,transparent)]">
                Stage id
              </span>
              <Input
                className={fieldClass}
                aria-label="Stage id"
                value={stage}
                onChange={(event) => setStage(event.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs text-[color-mix(in_oklab,var(--paper)_70%,transparent)]">
                Check name
              </span>
              <Input
                className={fieldClass}
                aria-label="Check name"
                value={check}
                onChange={(event) => setCheck(event.target.value)}
              />
            </label>
          </div>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="border-[color-mix(in_oklab,var(--paper)_30%,transparent)] text-[var(--paper)]"
            disabled={busy || !stage.trim() || !check.trim()}
            onClick={() => void reopenCheck()}
          >
            Reopen on check
          </Button>
        </section>
      )}
    </div>
  );
}
