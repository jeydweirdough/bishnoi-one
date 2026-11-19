// The Approvals inbox's shape while it loads: title, the boxes, then the list.
export default function Loading() {
  return (
    <div className="mx-auto max-w-[70rem] px-4 pt-20 sm:px-6 lg:px-8" aria-busy>
      <div className="h-9 w-48 animate-pulse rounded-lg bg-sheet" />
      <div className="mt-5 h-9 w-80 animate-pulse rounded-lg bg-sheet" />
      <div className="mt-4 space-y-2">
        {Array.from({ length: 4 }, (_, i) => <div key={i} className="h-14 animate-pulse rounded-xl bg-sheet" />)}
      </div>
    </div>
  );
}
