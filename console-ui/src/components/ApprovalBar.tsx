import { AnimatePresence, motion } from "motion/react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { PendingPrompt } from "@/lib/types";

/** Always on top of the board: a parked run must never be silent. */
export function ApprovalBar({
  pending,
  onOpen,
}: {
  pending: PendingPrompt | null;
  onOpen: () => void;
}) {
  return (
    <AnimatePresence>
      {pending && (
        <motion.div
          role="alert"
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }}
          transition={{ type: "spring", stiffness: 420, damping: 32 }}
          className="sticky top-0 z-30 mb-3 flex items-center gap-3 rounded-lg border-2 border-amber-500 bg-amber-500/10 px-3 py-2"
        >
          <AlertTriangle className="size-4 shrink-0 text-amber-600" aria-hidden />
          <p className="truncate text-sm font-semibold">
            {pending.is_question
              ? "The Guild needs a decision from you"
              : `Approval needed — ${pending.tool}`}
          </p>
          <Button size="sm" className="ml-auto" onClick={onOpen}>
            Review
          </Button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
