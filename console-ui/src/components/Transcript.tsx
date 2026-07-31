import { useEffect, useRef } from "react";
import type { GuildEvent } from "@/lib/types";

/**
 * How close to the bottom still counts as "at the bottom", in px. Sub-pixel
 * rounding and a partially visible last row mean the arithmetic rarely lands on
 * exactly zero.
 */
const AT_BOTTOM_SLACK = 24;

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
    return <p className="text-xs text-muted-foreground">Nothing yet.</p>;
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
      className="max-h-[60vh] space-y-1.5 overflow-y-auto text-xs"
    >
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
