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
