import { AnimatePresence, motion } from "motion/react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { PendingPrompt } from "@/lib/types";

/**
 * Always on top of the board: a parked run must never be silent.
 *
 * `pending` is the whole queue, so the bar can say how many decisions are
 * outstanding; `agentLabel` names the owner of the one it is offering (the
 * oldest), because "Approval needed — Bash" with five agents running tells the
 * user nothing about who is blocked.
 */
export function ApprovalBar({
  pending,
  agentLabel,
  onOpen,
}: {
  pending: PendingPrompt[];
  agentLabel: string | null;
  onOpen: () => void;
}) {
  const head = pending[0] ?? null;
  const who = agentLabel ?? "The Guild";
  // The engine's fallback attribution can name the wrong lane. Saying "possibly"
  // costs one word and stops the bar from asserting something it cannot know.
  const named = head?.agentConfidence === "guess" ? `Possibly ${who}` : who;

  return (
    <AnimatePresence>
      {head && (
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
            {head.is_question
              ? `${named} needs a decision from you`
              : `${named} needs approval — ${head.tool}`}
          </p>
          {pending.length > 1 && (
            <span className="shrink-0 rounded-full bg-amber-500/20 px-2 py-0.5 text-xs font-semibold tabular-nums">
              {pending.length} waiting on you
            </span>
          )}
          <Button size="sm" className="ml-auto" onClick={onOpen}>
            Review
          </Button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
