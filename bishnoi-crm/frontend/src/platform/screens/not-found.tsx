import { LinkButton } from "../ui/button";

export default function NotFound() {
  return (
    <main className="flex min-h-[60dvh] items-center justify-center px-4">
      <div className="max-w-md rounded-[6px] bg-sheet px-6 py-10 text-center shadow-sheet">
        <h1 className="text-heading">Nothing here</h1>
        <p className="mt-1 text-ink-2">
          That page doesn&apos;t exist, or it belongs to a team you can&apos;t see.
        </p>
        <LinkButton href="/" className="mt-5">
          Go home
        </LinkButton>
      </div>
    </main>
  );
}
