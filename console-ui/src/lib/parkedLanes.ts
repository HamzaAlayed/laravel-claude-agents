import type { RunView } from "./types";

/**
 * The lanes a waiting prompt blocks, by tool_use_id.
 *
 * Marked from the prompt's own `agent`, never guessed. A guessed attribution
 * marks nothing: the promise is that a marked lane is really the blocked one, and
 * the approval bar hedges in words instead. A prompt with no agent came from the
 * main thread — the board's header, not a card — so nothing is blamed.
 */
export function parkedLaneIds(view: RunView): Set<string> {
  return new Set(
    view.pending.flatMap((prompt) => {
      if (!prompt.agent || prompt.agentConfidence === "guess") return [];
      const lane = view.lanes.find(
        (candidate) => candidate.slug === prompt.agent && candidate.status === "running",
      );
      return lane ? [lane.toolUseId] : [];
    }),
  );
}
