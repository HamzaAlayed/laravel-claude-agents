import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import * as api from "@/lib/api";

const fieldClass =
  "w-full rounded-md border border-[color-mix(in_oklab,var(--ink)_18%,transparent)] bg-[var(--paper)] px-2 text-sm text-[var(--ink)]";

/**
 * Delivery-kernel board + reopen strip. Visible on the call sheet so it works
 * without a live run. Never sends a client-chosen root — the server uses cwd.
 */
export function KernelStrip() {
  const [name, setName] = useState("");
  const [stage, setStage] = useState("");
  const [check, setCheck] = useState("");
  const [comment, setComment] = useState("");
  const [boardText, setBoardText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const showBoard = async () => {
    setError(null);
    setBusy(true);
    try {
      const { text } = await api.fetchKernelBoard(name.trim());
      setBoardText(text);
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };

  const reopenCheck = async () => {
    setError(null);
    setBusy(true);
    try {
      const result = await api.ingestKernel({
        name: name.trim(),
        kind: "check",
        stage: stage.trim(),
        check: check.trim(),
      });
      setBoardText(result.text);
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };

  const reopenReview = async () => {
    setError(null);
    setBusy(true);
    try {
      const result = await api.ingestKernel({
        name: name.trim(),
        kind: "review",
        stage: stage.trim(),
        comment: comment.trim(),
      });
      setBoardText(result.text);
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      aria-label="Delivery kernel"
      className="mx-auto mt-6 w-full max-w-lg space-y-3 border-t border-[color-mix(in_oklab,var(--ink)_12%,transparent)] pt-6"
    >
      <h2 className="text-sm font-medium text-[var(--ink)]">Kernel board</h2>
      <label className="flex flex-col gap-1.5">
        <span className="text-xs">Delivery name</span>
        <Input
          className={fieldClass}
          aria-label="Delivery name"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <Button type="button" size="sm" disabled={busy || !name.trim()} onClick={showBoard}>
        Show
      </Button>
      {boardText !== null && (
        <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-md border bg-muted/30 p-2 text-xs">
          {boardText}
        </pre>
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="flex flex-col gap-1.5">
          <span className="text-xs">Stage</span>
          <Input
            className={fieldClass}
            aria-label="Stage"
            value={stage}
            onChange={(event) => setStage(event.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-xs">Check name</span>
          <Input
            className={fieldClass}
            aria-label="Check name"
            value={check}
            onChange={(event) => setCheck(event.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-xs">Comment id</span>
          <Input
            className={fieldClass}
            aria-label="Comment id"
            value={comment}
            onChange={(event) => setComment(event.target.value)}
          />
        </label>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={busy || !name.trim() || !stage.trim() || !check.trim()}
          onClick={reopenCheck}
        >
          Reopen on check
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={busy || !name.trim() || !stage.trim() || !comment.trim()}
          onClick={reopenReview}
        >
          Reopen on review
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </section>
  );
}
