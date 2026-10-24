import { Sheet } from "@/src/modules/admin/platform/ui/sheet";

/** In place of a screen this person's role doesn't open. The API refuses it too. */
export function Restricted({ what }: { what: string }) {
  return (
    <Sheet className="p-8 text-center">
      <h2 className="text-base font-semibold text-ink">Access restricted</h2>
      <p className="mt-1 text-sm text-ink-3">Your role doesn&apos;t allow you to see {what}. Ask your administrator if you need it.</p>
    </Sheet>
  );
}
