// The 4-dot loader (decided 2026-10-30): four dots turning, for a wait whose shape isn't known yet
// (opening another app, a dialog's contents, the sign-in steps). A page whose shape is known shows its
// skeleton instead (ui/skeleton.tsx), so nothing jumps when the data lands. Styles in styles/globals.css.

type Size = "sm" | "md" | "lg";
const SIZE: Record<Size, string> = { sm: "size-4", md: "size-7", lg: "size-10" };

/** Four dots turning; `label` is read out to screen readers (and shown under it when `show`). */
export function Dots({ size = "md", label = "Loading", show = false, className = "" }: { size?: Size; label?: string; show?: boolean; className?: string }) {
  return (
    <span role="status" className={`inline-flex flex-col items-center gap-3 ${className}`}>
      <span aria-hidden className={`dots ${SIZE[size]}`}>
        <i />
        <i />
        <i />
        <i />
      </span>
      {show ? <span className="text-sm text-ink-2">{label}</span> : <span className="sr-only">{label}</span>}
    </span>
  );
}

/** A whole area waiting: the dots in its middle, with what's coming said under them. */
export function DotsPanel({ label = "Loading", className = "" }: { label?: string; className?: string }) {
  return (
    <div className={`grid min-h-[50vh] place-items-center ${className}`}>
      <Dots size="lg" label={label} show />
    </div>
  );
}
