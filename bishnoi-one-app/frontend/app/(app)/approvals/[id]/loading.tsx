// An approval slip's shape while it loads: number and title, the request, the steps beside it.
export default function Loading() {
  return (
    <div className="mx-auto max-w-[70rem] px-4 pt-20 sm:px-6 lg:px-8" aria-busy>
      <div className="h-9 w-40 animate-pulse rounded-lg bg-sheet" />
      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <div className="h-64 animate-pulse rounded-2xl bg-sheet lg:col-span-2" />
        <div className="h-64 animate-pulse rounded-2xl bg-sheet" />
      </div>
    </div>
  );
}
