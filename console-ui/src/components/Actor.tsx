import { propFor, type PropKey } from "@/lib/agentProp";
import type { ActorPose } from "@/lib/actorPose";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/**
 * The instruments, drawn on the bench beside the sprite: x 23.5–30.5, y 18.5–27.5.
 *
 * They are neutral rather than lane-coloured on purpose — the colour is the
 * agent's identity and the object is what it works on, so a lane-coloured tool
 * read as another limb. Each one has to survive being nine pixels wide, which is
 * why they are silhouettes with one detail each and no interior line work.
 */
const INSTRUMENTS: Record<PropKey, React.ReactNode> = {
  padlock: (
    <>
      <path d="M25.4 22.6v-1.7a1.6 1.6 0 0 1 3.2 0v1.7" />
      <rect className="sp-prop-fill" x="23.6" y="22.6" width="6.8" height="5.2" rx="1.4" />
      <rect x="23.6" y="22.6" width="6.8" height="5.2" rx="1.4" />
    </>
  ),
  clipboard: (
    <>
      <rect className="sp-prop-fill" x="23.6" y="19.6" width="6.8" height="8.2" rx="1.2" />
      <rect x="23.6" y="19.6" width="6.8" height="8.2" rx="1.2" />
      <path d="M25.6 19.6v-1.1h2.8v1.1" />
      <path d="M25.4 22.6h3.2M25.4 25h3.2" />
    </>
  ),
  stopwatch: (
    <>
      <circle className="sp-prop-fill" cx="27" cy="24" r="3.6" />
      <circle cx="27" cy="24" r="3.6" />
      <path d="M26.2 19.9h1.6" />
      <path d="M27 24v-2" />
    </>
  ),
};

/**
 * The specialist, animated. One rig serves all seventeen agents — colour is the
 * only per-agent art — and every pose is CSS keyed off `data-pose`, so nothing
 * ships an animation runtime for it.
 *
 * Parts are grouped by what moves: `sp-body` bobs, `sp-skull` tilts, `sp-eyes`
 * glance, and the two limbs swing independently. The rig is drawn AT REST here
 * because the reduced-motion guard kills loops rather than replacing them, so a
 * frozen actor falls back to exactly this markup.
 *
 * It takes the card's 24px avatar slot without moving anything else in the row:
 * a 32px box with -4px margin gives the extra eight pixels back to the layout.
 */
export function Actor({
  pose,
  color,
  slug,
  size = "sm",
  elapsed,
  tool,
}: {
  pose: ActorPose;
  color: string;
  /** Which specialist this is, so it can be given its instrument at `lg`. */
  slug?: string;
  /**
   * `sm` is the card's 24px slot; `lg` is the lane panel, at twice that.
   *
   * The instrument only appears at `lg`, and that gate is a finding rather than a
   * preference: at card size a padlock, a clipboard and a stopwatch are the same
   * grey lump. Drawing one there costs legibility and buys nothing.
   */
  size?: "sm" | "lg";
  /**
   * Card-size hover tooltip: elapsed time and the current tool. Omitted at `lg`
   * (the lane panel already is the "more detail" surface) and when the parent
   * has nothing to pass.
   */
  elapsed?: string;
  tool?: string | null;
}) {
  const prop = size === "lg" && slug ? propFor(slug) : null;
  const hoverable = size === "sm" && elapsed !== undefined;
  const sprite = (
    <>
      <svg className="block size-full overflow-hidden" viewBox="0 0 32 32" aria-hidden="true">
        <ellipse className="sp-shadow" cx="16" cy="27.4" rx="6.6" ry="1.1" />
        {prop && (
          <g className="sp-prop" data-prop={prop}>
            {INSTRUMENTS[prop]}
          </g>
        )}
        <g className="sp-body">
          <rect className="sp-torso" x="10.9" y="17.6" width="10.2" height="8.8" rx="3.4" />
          <g className="sp-skull">
            <rect className="sp-head" x="9.6" y="5.9" width="12.8" height="10.9" rx="4.6" />
            <g className="sp-eyes">
              <circle className="sp-eye" cx="13.1" cy="11.6" r="1.5" />
              <circle className="sp-eye" cx="18.9" cy="11.6" r="1.5" />
              <path className="sp-xeye" d="M12 10.5l2.2 2.2m0-2.2l-2.2 2.2M17.8 10.5l2.2 2.2m0-2.2l-2.2 2.2" />
              <path className="sp-lid" d="M11.6 11.6h3M17.4 11.6h3" />
            </g>
            <path className="sp-mouth" d="M14.6 14.6h2.8" />
          </g>
          {/* Both limbs are drawn after the head, and after it, so a raised hand
              passes IN FRONT of the skull instead of behind it. */}
          <g className="sp-arm">
            <path d="M20.8 19.8 24.6 22.2" />
            <circle className="sp-hand" cx="25.2" cy="22.5" r="1.6" />
          </g>
          {/* A limb of its own for the one gesture that has to survive 32 pixels.
              Rotating the working arm to vertical left the hand beside the head in
              the head's own colour — a wave that read as a lump. */}
          <g className="sp-raise">
            <path d="M20.8 19.8 22.4 12.4" />
            <circle className="sp-hand" cx="22.8" cy="10.4" r="1.9" />
          </g>
        </g>
        <circle className="sp-think" cx="24.6" cy="7.2" r="1.6" />
      </svg>
    </>
  );
  const box = {
    className: size === "lg" ? "block size-16 shrink-0" : "-m-1 block size-8 shrink-0",
    "data-pose": pose,
    style: { ["--lane" as string]: color },
  } as const;

  if (!hoverable) {
    return (
      <span className={box.className} data-pose={box["data-pose"]} style={box.style}>
        {sprite}
      </span>
    );
  }

  // Trigger MUST be a span: this sprite lives inside AgentCard's <motion.button>,
  // and a nested button (TooltipTrigger's default) is invalid HTML that browsers
  // "fix" by breaking the card's click handler.
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger
          render={
            <span
              className={box.className}
              data-pose={box["data-pose"]}
              data-hover=""
              style={box.style}
            />
          }
        >
          {sprite}
        </TooltipTrigger>
        <TooltipContent>
          <span className="flex flex-col gap-0.5">
            <span>{elapsed}</span>
            <span>{tool ?? "starting…"}</span>
          </span>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
