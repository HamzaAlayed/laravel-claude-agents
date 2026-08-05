import type { Lane } from "./types";

/**
 * What the actor on a lane's card is doing. Named for the behaviour, not for the
 * event that caused it, because several events land on one pose.
 */
export type ActorPose =
  | "thinking"
  | "working"
  | "speaking"
  | "stumble"
  | "needs"
  | "done"
  | "failed";

/**
 * The pose for one lane, in strict precedence order.
 *
 * Being blocked on the human comes first — a parked lane's card exists to get
 * answered, and it is already the one wearing the pulsing border. Terminal
 * status comes next: a lane whose newest event is a tool call but which has
 * since ended is finished, not still working. Only a live, unparked lane reads
 * its transcript, and only the newest event counts.
 *
 * `api_retry` deliberately has no pose here. The engine reports it on the RUN,
 * not on a lane, so posing every lane as retrying would claim something about
 * agents that are working fine.
 */
export function actorPose(lane: Lane, parked: boolean): ActorPose {
  if (parked) return "needs";
  if (lane.status === "error") return "failed";
  if (lane.status === "done") return "done";

  const newest = lane.events[lane.events.length - 1];
  switch (newest?.type) {
    case "tool_use":
      return "working";
    // A result that came back fine puts the agent back to reading it. The next
    // tool_use is what says work resumed.
    case "tool_result":
      return newest.is_error ? "stumble" : "thinking";
    case "text":
      return "speaking";
    default:
      return "thinking";
  }
}
