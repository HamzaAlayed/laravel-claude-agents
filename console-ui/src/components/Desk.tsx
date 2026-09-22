import { Button } from "@/components/ui/button";

/** Idle shell — Task 7 fills the delivery list. */
export function Desk({ onNewRun }: { onNewRun: () => void }) {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4 py-10">
      <h1 className="font-heading text-4xl font-extrabold tracking-tight">The Guild</h1>
      <p className="text-sm text-muted-foreground">Delivery desk</p>
      <Button type="button" size="lg" onClick={onNewRun}>
        New run
      </Button>
    </div>
  );
}
