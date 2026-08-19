import type { Lane } from "./types";

/**
 * The tool a lane is in the middle of, or null if it has not called one yet.
 *
 * Walks newest-first through `lane.events` for a `tool_use` and returns its
 * `tool` field. The tooltip on the card sprite uses this so a just-started lane
 * can say "starting…" instead of omitting the line (which would jump the
 * tooltip's height the instant the first call lands).
 */
export function currentTool(lane: Lane): string | null {
  for (let index = lane.events.length - 1; index >= 0; index -= 1) {
    const event = lane.events[index];
    if (event.type === "tool_use" && typeof event.tool === "string") {
      return event.tool;
    }
  }
  return null;
}
