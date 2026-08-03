import { motion } from "motion/react";
import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";
import { fadeRise } from "@/lib/motion";
import { Transcript } from "./Transcript";
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
  onClose,
}: {
  lane: Lane;
  agent?: Agent;
  onClose: () => void;
}) {
  return (
    <Sheet open modal={false} onOpenChange={(next) => !next && onClose()}>
      <SheetContent
        side="right"
        showOverlay={false}
        className="w-full data-[side=right]:sm:max-w-md"
      >
        <motion.div {...fadeRise} className="flex min-h-0 flex-1 flex-col">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className="grid size-6 shrink-0 place-items-center rounded text-[10px] font-bold text-white"
                style={{ background: agent?.color ?? "#64748b" }}
              >
                {(agent?.name ?? lane.slug).slice(0, 2)}
              </span>
              {agent?.name ?? lane.slug}
            </SheetTitle>
            <SheetDescription className="truncate">
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
