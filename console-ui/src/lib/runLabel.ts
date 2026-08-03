import type { RunRow } from "./api";

const ago = (ms: number): string => {
  if (ms < 60_000) return "just now";
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`;
  if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`;
  return `${Math.floor(ms / 86_400_000)}d ago`;
};

/** `make-feature · done · 12m ago` — what a run row is, at a glance. */
export function formatRunLabel(row: RunRow, now = Date.now()): string {
  const kind = row.spec?.kind ?? "run";
  const when = row.started_at ? ` · ${ago(now - row.started_at)}` : "";
  return `${kind} · ${row.status}${when}`;
}
