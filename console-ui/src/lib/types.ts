export type GuildEvent = {
  seq: number;
  run_id: string;
  ts: number;
  type: string;
  agent: string | null;
  [key: string]: unknown;
};

export type LaneStatus = "running" | "done" | "error";

export type Lane = {
  slug: string;
  task: string;
  toolUseId: string;
  parent: string | null;
  status: LaneStatus;
  startedAt: number;
  endedAt: number;
  events: GuildEvent[];
  /**
   * How many of this lane's tool calls ran WITHOUT the browser being asked.
   * Claude Code decides some calls before `can_use_tool` is consulted, so a
   * transcript that showed only tool calls implied every one had been approved.
   * Counted from `tool_gate` events published by the PreToolUse hook.
   */
  unasked: number;
};

export type PendingPrompt = {
  prompt_id: string;
  /** The agent whose lane is blocked; null when the main thread asked. */
  agent: string | null;
  tool: string;
  input: Record<string, unknown>;
  is_question: boolean;
  suggestions: unknown[];
};

export type RunView = {
  mode: "board" | "focus";
  lanes: Lane[];
  main: GuildEvent[];
  /**
   * A QUEUE, ordered by arrival — the engine holds many simultaneous pending
   * prompts (one future per parallel subagent), so a single slot silently
   * discarded the earlier one and parked that subagent forever.
   */
  pending: PendingPrompt[];
  init: { plugins: string[]; plugin_errors: unknown[] } | null;
  retry: { attempt: number; max_retries: number; error: string } | null;
  result: { subtype: string; result: string; duration_ms: number; total_cost_usd: number } | null;
  /**
   * The OTHER terminal outcome. When the CLI or the transport dies mid-run the
   * engine publishes an `error` event and never a `result`, so a run read as
   * "still live" forever and the Launcher stayed disabled with no way back
   * short of reloading the page.
   */
  failure: { message: string } | null;
  /** Main-thread calls that ran without an ask — the lane-less counterpart. */
  unasked: number;
};

export type Agent = {
  slug: string;
  name: string;
  description: string;
  model: string;
  tools: string[];
  color: string;
  stage: string | null;
};

export type Catalog = {
  agents: Agent[];
  commands: { slug: string; description: string; argument_hint: string }[];
  skills: { slug: string; description: string }[];
  stages: string[];
};
