import { useEffect, useRef } from "react";
import { BrainCircuit, Check, MessageSquareText, Terminal, TriangleAlert } from "lucide-react";
import type { GuildEvent } from "@/lib/types";

/**
 * How close to the bottom still counts as "at the bottom", in px. Sub-pixel
 * rounding and a partially visible last row mean the arithmetic rarely lands on
 * exactly zero.
 */
const AT_BOTTOM_SLACK = 24;

const timeFormat = new Intl.DateTimeFormat(undefined, {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

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
  const ref = useRef<HTMLOListElement>(null);
  // Whether to keep following the tail. Only the reader's own scrolling flips
  // it: a log that drags you back to the bottom while you are reading what an
  // agent already did is worse than one that does not follow at all.
  const following = useRef(true);

  useEffect(() => {
    const list = ref.current;
    if (!list || !following.current) return;
    list.scrollTop = list.scrollHeight;
  }, [events.length]);

  if (events.length === 0) {
    return (
      <div className="flex min-h-40 items-center justify-center rounded-lg border border-dashed border-border text-sm text-muted-foreground">
        <span>Nothing yet.</span>
        <span className="ml-1 hidden sm:inline">Activity will appear here when the run begins.</span>
      </div>
    );
  }
  return (
    <ol
      ref={ref}
      onScroll={() => {
        const list = ref.current;
        if (!list) return;
        following.current =
          list.scrollHeight - list.scrollTop - list.clientHeight < AT_BOTTOM_SLACK;
      }}
      className="max-h-[60vh] space-y-1 overflow-y-auto overscroll-contain pr-1 text-xs"
    >
      {events.map((event) => {
        const isError = event.type === "tool_result" && event.is_error;
        const isTool = event.type === "tool_use" || event.type === "tool_result";
        const Icon = event.type === "tool_use"
          ? Terminal
          : event.type === "tool_result"
            ? isError ? TriangleAlert : Check
            : event.type === "thinking"
              ? BrainCircuit
              : MessageSquareText;
        const kind = event.type === "tool_use"
          ? "Tool call"
          : event.type === "tool_result"
            ? isError ? "Tool error" : "Tool result"
            : event.type === "thinking"
              ? "Reasoning"
              : "Message";
        return (
          <li
            key={event.seq}
            className="grid grid-cols-[2rem_minmax(0,1fr)] gap-2 rounded-lg px-2 py-2.5 animate-in fade-in duration-300 hover:bg-muted/50 sm:grid-cols-[4.75rem_2rem_minmax(0,1fr)]"
          >
            <time
              dateTime={new Date(event.ts).toISOString()}
              className="col-span-2 hidden pt-1 tabular-nums text-muted-foreground sm:block sm:col-span-1"
            >
              {timeFormat.format(new Date(event.ts))}
            </time>
            <span className={`flex size-7 items-center justify-center rounded-md ${isError ? "bg-destructive/10 text-destructive" : isTool ? "bg-primary/10 text-primary" : "bg-secondary text-secondary-foreground"}`}>
              <Icon className="size-3.5" aria-hidden />
            </span>
            <span className="min-w-0">
              <span className="mb-0.5 block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{kind}</span>
              <span
                className={`min-w-0 break-words leading-relaxed ${
                  event.type === "thinking" ? "line-clamp-4 max-h-24 overflow-hidden italic text-muted-foreground" : event.type === "text" ? "line-clamp-6 max-h-36 overflow-hidden text-foreground" : "line-clamp-3 font-mono text-[11px] text-foreground"
                }`}
                title={isTool ? label(event) : undefined}
              >
                {label(event)}
              </span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
