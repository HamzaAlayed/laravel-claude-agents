/**
 * The object a specialist's sprite holds, if its craft has one that reads at
 * nine pixels.
 *
 * This is deliberately a short list rather than a complete one. A prop earns its
 * place by being unmistakable at the size the card actually draws it, and by not
 * colliding with another specialist's object — a padlock is a padlock at 9px,
 * whereas an architect's blueprint and an analyst's document are the same grey
 * rectangle. Everyone else keeps the plain rig, which is what stops a newly added
 * agent from looking unfinished.
 */
export type PropKey = "padlock" | "clipboard" | "stopwatch";

export const PROPS: Record<string, PropKey> = {
  "security-engineer": "padlock",
  "qa-engineer": "clipboard",
  "performance-engineer": "stopwatch",
};

export const propFor = (slug: string): PropKey | null => PROPS[slug] ?? null;
