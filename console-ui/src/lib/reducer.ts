import type { GuildEvent, Lane, RunView } from "./types";

export const emptyRun = (kind: string): RunView => ({
  // specialist and freeform runs open focused; commands open on the board.
  mode: kind === "command" ? "board" : "focus",
  lanes: [],
  main: [],
  pending: [],
  init: null,
  retry: null,
  result: null,
  failure: null,
});

/**
 * Has the engine reported a terminal outcome? `result` is the happy path;
 * `failure` is the `error` event `_pump` publishes INSTEAD of a result when the
 * client dies. "Live" derived from `result === null` alone marked a dead run
 * live forever.
 */
export const isRunOver = (view: RunView): boolean =>
  view.result !== null || view.failure !== null;

const withLane = (lanes: Lane[], toolUseId: string, patch: Partial<Lane>): Lane[] =>
  lanes.map((lane) => (lane.toolUseId === toolUseId ? { ...lane, ...patch } : lane));

export function reduce(view: RunView, event: GuildEvent): RunView {
  const next: RunView = { ...view, retry: event.type === "api_retry" ? view.retry : null };

  switch (event.type) {
    case "init":
      return {
        ...next,
        init: {
          plugins: (event.plugins as string[]) ?? [],
          plugin_errors: (event.plugin_errors as unknown[]) ?? [],
        },
      };

    case "api_retry":
      return {
        ...next,
        retry: {
          attempt: event.attempt as number,
          max_retries: event.max_retries as number,
          error: event.error as string,
        },
      };

    case "agent_start": {
      const toolUseId = event.tool_use_id as string;
      if (next.lanes.some((lane) => lane.toolUseId === toolUseId)) return next;
      const lane: Lane = {
        slug: (event.agent as string) ?? "unknown",
        task: (event.task as string) ?? "",
        toolUseId,
        parent: (event.parent_agent as string) ?? null,
        status: "running",
        startedAt: event.ts,
        endedAt: 0,
        events: [],
      };
      const lanes = [...next.lanes, lane];
      // Promotion is one-way: a board run never demotes to focus.
      return { ...next, lanes, mode: lanes.length > 1 ? "board" : next.mode };
    }

    case "agent_end":
      return {
        ...next,
        lanes: withLane(next.lanes, event.tool_use_id as string, {
          status: event.is_error ? "error" : "done",
          endedAt: event.ts,
        }),
      };

    // Approvals queue: parallel subagents can each park on their own prompt,
    // and the engine keeps a future per prompt_id. Appending (not replacing)
    // is what stops the earlier subagent from being parked with nothing in the
    // UI able to name it. Idempotent because the SSE backlog is replayed on
    // every reconnect.
    case "prompt": {
      const promptId = event.prompt_id as string;
      if (next.pending.some((prompt) => prompt.prompt_id === promptId)) return next;
      return {
        ...next,
        pending: [
          ...next.pending,
          {
            prompt_id: promptId,
            agent: (event.agent as string) ?? null,
            tool: event.tool as string,
            input: (event.input as Record<string, unknown>) ?? {},
            is_question: Boolean(event.is_question),
            suggestions: (event.suggestions as unknown[]) ?? [],
          },
        ],
      };
    }

    // Removes exactly the resolved prompt and leaves every other one waiting.
    case "prompt_resolved":
      return next.pending.some((prompt) => prompt.prompt_id === event.prompt_id)
        ? { ...next, pending: next.pending.filter((p) => p.prompt_id !== event.prompt_id) }
        : next;

    case "result":
      return {
        ...next,
        result: {
          subtype: event.subtype as string,
          result: (event.result as string) ?? "",
          duration_ms: (event.duration_ms as number) ?? 0,
          total_cost_usd: (event.total_cost_usd as number) ?? 0,
        },
      };

    // A dead client / transport ends the run WITHOUT a result: `_pump` catches
    // the exception and publishes this instead. Terminal, like `result` — and
    // the message is the only account of why the run stopped, so it lands both
    // on the banner and in the timeline rather than being swallowed.
    case "error":
      return {
        ...next,
        main: [...next.main, event],
        failure: { message: String(event.message ?? "the run ended with an error") },
      };

    default: {
      if (!event.agent) return { ...next, main: [...next.main, event] };
      const lanes = next.lanes.map((lane) =>
        lane.slug === event.agent && lane.status === "running"
          ? { ...lane, events: [...lane.events, event] }
          : lane,
      );
      return { ...next, lanes };
    }
  }
}
