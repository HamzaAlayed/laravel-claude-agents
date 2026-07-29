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
