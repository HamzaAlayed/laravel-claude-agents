import { useEffect, useState } from "react";

const format = (ms: number) => {
  if (ms < 60_000) return `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)}s`;
  return `${Math.floor(ms / 60_000)}m ${Math.round((ms % 60_000) / 1000)}s`;
};

/** Ticks once a second while running; freezes at the final duration when done. */
export function useElapsed(startedAt: number, endedAt: number): string {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (endedAt) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [endedAt]);
  if (!startedAt) return "";
  return format((endedAt || now) - startedAt);
}
