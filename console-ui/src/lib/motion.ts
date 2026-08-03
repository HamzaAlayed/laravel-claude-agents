/**
 * The console's whole motion vocabulary. Spread onto motion elements:
 * <motion.p {...fadeRise}>. Components do not improvise their own timings.
 */

/** Layout motion — the board's existing card spring, now shared. */
export const spring = { type: "spring", stiffness: 380, damping: 30 } as const;

/** Content appearing in place: banners, the final answer, sheet bodies. */
export const fadeRise = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: 8 },
  transition: { duration: 0.2 },
} as const;

/** The sticky approval bar dropping in from above. */
export const fadeDrop = {
  initial: { opacity: 0, y: -12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -12 },
  transition: { type: "spring", stiffness: 420, damping: 32 },
} as const;
