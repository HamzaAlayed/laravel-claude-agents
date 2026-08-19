import { motion } from "motion/react";
import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";
import { fadeRise } from "@/lib/motion";
import { Transcript } from "./Transcript";
import { Actor } from "./Actor";
import { actorPose } from "@/lib/actorPose";
import type { Agent, Lane } from "@/lib/types";

/**
 * A lane's transcript as a slide-over instead of a below-the-fold section.
 * Non-modal on purpose: reading one agent must not lock the board — clicking
 * another card swaps this panel's content, and an arriving decision sheet
 * (which IS modal) takes the screen. App closes this one when that happens.
 */
export function LanePanel({
  lane,
  agent,
  parked,
  open,
  onClose,
}: {
  lane: Lane;
  agent?: Agent;
  parked: boolean;
  /**
   * Controlled so Base UI can run `data-ending-style` on close. Hardcoding
   * `true` mounted the frame already-open and popped it off on unmount.
   */
  open: boolean;
  onClose: () => void;
}) {
  return (
    <Sheet open={open} modal={false} onOpenChange={(next) => !next && onClose()}>
      <SheetContent
        side="right"
        showOverlay={false}
        className="w-full border-[color-mix(in_oklab,var(--paper)_18%,transparent)] bg-[var(--floor)] text-[var(--paper)] data-[side=right]:sm:max-w-md"
      >
        <motion.div {...fadeRise} className="flex min-h-0 flex-1 flex-col">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2 font-heading text-[var(--paper)]">
              {/* Twice the card's size, which is what earns the instrument: this
                  is the surface you open to find out what an agent is doing. */}
              <Actor
                pose={actorPose(lane, parked)}
                color={agent?.color ?? "#64748b"}
                slug={lane.slug}
                size="lg"
              />
              {agent?.name ?? lane.slug}
            </SheetTitle>
            <SheetDescription className="truncate text-[color-mix(in_oklab,var(--paper)_70%,transparent)]">
              {lane.task || "working…"}
            </SheetDescription>
          </SheetHeader>
          <div className="min-h-0 flex-1 px-4 pb-4">
            <Transcript events={lane.events} />
          </div>
        </motion.div>
      </SheetContent>
    </Sheet>
  );
}
