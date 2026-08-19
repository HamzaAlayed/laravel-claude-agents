import type { RunRow } from "./api";

const ago = (ms: number): string => {
  // A started_at slightly in the future (clock skew between the engine host and
  // the browser) used to fall through `ms < 60_000` because negatives are less
  // than a minute, and read as "just now" by accident. Clamp so that fallback
  // is an explicit choice.
  const elapsed = Math.max(0, ms);
  if (elapsed < 60_000) return "just now";
  if (elapsed < 3_600_000) return `${Math.floor(elapsed / 60_000)}m ago`;
  if (elapsed < 86_400_000) return `${Math.floor(elapsed / 3_600_000)}h ago`;
  return `${Math.floor(elapsed / 86_400_000)}d ago`;
};

/** `make-feature · done · 12m ago` — what a run row is, at a glance. */
export function formatRunLabel(row: RunRow, now = Date.now()): string {
  const kind = row.spec?.kind ?? "run";
  const when = row.started_at ? ` · ${ago(now - row.started_at)}` : "";
  return `${kind} · ${row.status}${when}`;
}
