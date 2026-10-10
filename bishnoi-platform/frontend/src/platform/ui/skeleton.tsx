import { Sheet } from "./sheet";

/** A grey bar where text is about to be. */
export function Bone({ className = "" }: { className?: string }) {
  return <span aria-hidden className={`block animate-pulse rounded-full bg-rule/70 ${className}`} />;
}

function Lines({ rows }: { rows: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }, (_, i) => (
        <Bone key={i} className={`h-3.5 ${i % 3 === 2 ? "w-2/3" : i % 3 === 1 ? "w-5/6" : "w-full"}`} />
      ))}
    </div>
  );
}

/**
 * The shape of a page while its data is on the way, shown the moment a link
 * is clicked, so the app answers at once instead of seeming to hang.
 */
export function PageSkeleton({ aside = true }: { aside?: boolean }) {
  return (
    <div role="status" aria-label="Loading">
      <span className="sr-only">Loading…</span>
      <Bone className="mb-2 h-8 w-72 max-w-full" />
      <Bone className="mb-6 h-4 w-96 max-w-full" />
      <div className={aside ? "grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start" : ""}>
        <div className="space-y-5">
          <Sheet className="px-5 py-5">
            <Bone className="mb-4 h-3 w-32" />
            <Lines rows={6} />
          </Sheet>
          <Sheet className="px-5 py-5">
            <Bone className="mb-4 h-3 w-24" />
            <Lines rows={4} />
          </Sheet>
        </div>
        {aside && (
          <Sheet className="px-5 py-5 max-lg:hidden">
            <Bone className="mb-4 h-3 w-28" />
            <Lines rows={5} />
          </Sheet>
        )}
      </div>
    </div>
  );
}
