import type { ActorPose } from "@/lib/actorPose";

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
export function Actor({ pose, color }: { pose: ActorPose; color: string }) {
  return (
    <span
      className="-m-1 block size-8 shrink-0"
      data-pose={pose}
      style={{ ["--lane" as string]: color }}
    >
      <svg className="block size-8 overflow-hidden" viewBox="0 0 32 32" aria-hidden="true">
        <ellipse className="sp-shadow" cx="16" cy="27.4" rx="6.6" ry="1.1" />
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
    </span>
  );
}
