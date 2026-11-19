// The Reports page's shape while it loads: title, then the cards.
export default function Loading() {
  return (
    <div className="mx-auto max-w-[70rem] px-4 pt-20 sm:px-6 lg:px-8" aria-busy>
      <div className="h-9 w-40 animate-pulse rounded-lg bg-sheet" />
      <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 3 }, (_, i) => <div key={i} className="h-24 animate-pulse rounded-2xl bg-sheet" />)}
      </div>
    </div>
  );
}
