import type { GuildEvent } from "@/lib/types";

const label = (event: GuildEvent) => {
  if (event.type === "tool_use") {
    const input = (event.input as Record<string, unknown>) ?? {};
    const detail = input.command ?? input.file_path ?? input.pattern ?? "";
    return `${event.tool} ${String(detail)}`.trim();
  }
  if (event.type === "text" || event.type === "thinking") return String(event.text ?? "");
  if (event.type === "tool_result") return event.is_error ? "→ error" : "→ ok";
  return event.type;
};

export function Transcript({ events }: { events: GuildEvent[] }) {
  if (events.length === 0) {
    return <p className="text-xs text-muted-foreground">Nothing yet.</p>;
  }
  return (
    <ol className="space-y-1.5 text-xs">
      {events.map((event) => (
        <li key={event.seq} className="flex gap-2">
          <span className="w-16 shrink-0 tabular-nums text-muted-foreground">
            {new Date(event.ts).toLocaleTimeString()}
          </span>
          <span
            className={`min-w-0 flex-1 break-words ${
              event.type === "thinking" ? "italic text-muted-foreground" : ""
            }`}
          >
            {label(event)}
          </span>
        </li>
      ))}
    </ol>
  );
}
