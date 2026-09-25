import type { Catalog, GuildEvent } from "./types";

const token = new URLSearchParams(window.location.search).get("token") ?? "";

const headers = { "Content-Type": "application/json", "X-Guild-Token": token };

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, { method: "POST", headers, body: JSON.stringify(body) });
  if (!response.ok) throw new Error((await response.json()).error ?? response.statusText);
  return response.json();
}

export const fetchCatalog = async (): Promise<Catalog> => {
  const response = await fetch("/api/catalog", { headers });
  if (!response.ok) throw new Error("could not load the catalog");
  return response.json();
};

/** A run this process may or may not still own. `spec` is null for disk-derived rows. */
export type RunRow = {
  run_id: string;
  status: string;
  spec: { kind?: string; target?: string; text?: string } | null;
  started_at: number;
};

export const listRuns = async (): Promise<RunRow[]> => {
  const response = await fetch("/api/runs", { headers });
  if (!response.ok) throw new Error("could not list the runs");
  return (await response.json()).runs ?? [];
};

/**
 * The whole event history of one run, from memory if this process owns it and
 * from the run's jsonl otherwise. This is the replay the SSE stream deliberately
 * does not do — see the spec's failure-mode section.
 */
export const fetchRun = async (runId: string): Promise<GuildEvent[]> => {
  const response = await fetch(`/api/runs/${runId}`, { headers });
  if (!response.ok) throw new Error("could not load that run");
  return (await response.json()).events ?? [];
};

export const createRun = (spec: {
  kind: string;
  target: string;
  text: string;
  mode?: string;
  model?: string;
}) => post<{ run_id: string }>("/api/runs", spec);

export const sendMessage = (runId: string, text: string) =>
  post(`/api/runs/${runId}/message`, { text });

export const answerPrompt = (runId: string, payload: Record<string, unknown>) =>
  post(`/api/runs/${runId}/answer`, payload);

export const interruptRun = (runId: string) => post(`/api/runs/${runId}/interrupt`, {});

export const setMode = (runId: string, mode?: string, model?: string) =>
  post(`/api/runs/${runId}/mode`, { mode, model });

export const fetchKernelBoard = async (name: string): Promise<{ text: string }> => {
  const response = await fetch(
    `/api/kernel/board?name=${encodeURIComponent(name)}`,
    { headers },
  );
  if (!response.ok) throw new Error((await response.json()).error ?? response.statusText);
  return response.json();
};

export type KernelIngestBody = {
  name: string;
  kind: "check" | "review";
  stage?: string;
  check?: string;
  comment?: string;
};

export const ingestKernel = (body: KernelIngestBody) =>
  post<{ ok: boolean; text: string }>("/api/kernel/ingest", body);

export type DeliveryRow = {
  name: string;
  status: string;
  done_when: string;
  issue_url: string;
  issue_number: number | null;
  pr_url: string;
  pr_state: string;
  board: string;
  steps?: { who: string; state: string }[];
  watching: boolean;
};

export const listDeliveries = async (): Promise<{ deliveries: DeliveryRow[] }> => {
  const response = await fetch("/api/kernel/deliveries", { headers });
  if (!response.ok) throw new Error((await response.json()).error ?? response.statusText);
  return response.json();
};

/** Enable or disable PR watch for one delivery. Never sends a client root. */
export const setWatch = (name: string, enabled: boolean) =>
  post<{ ok: boolean; watching: boolean }>("/api/kernel/watch", { name, enabled });

/**
 * SSE with resume: EventSource cannot send headers, so the token rides the query.
 *
 * Resume replays from the run's in-memory buffer, so it survives a dropped
 * connection but NOT a console restart — the server answers 404 for a run this
 * process no longer owns. `onFailure` is how that stops being silent.
 */
export function streamRun(
  runId: string,
  sinceSeq: number,
  onEvent: (e: GuildEvent) => void,
  onFailure?: () => void,
) {
  const source = new EventSource(
    `/api/runs/${runId}/events?since=${sinceSeq}&token=${encodeURIComponent(token)}`,
  );
  source.onmessage = (message) => onEvent(JSON.parse(message.data) as GuildEvent);
  // EventSource retries on its own while CONNECTING, so only CLOSED is final —
  // shouting on every transient blip would train the user to ignore the message.
  source.onerror = () => {
    if (source.readyState === EventSource.CLOSED) onFailure?.();
  };
  return () => source.close();
}
