"use client";

// The same net the shell has always had. A screen that throws shows what went
// wrong and offers another go, instead of the app falling over around it.
import { Button } from "@/src/platform/ui/button";
import { Sheet } from "@/src/platform/ui/sheet";

export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <Sheet className="px-6 py-10 text-center">
      <h1 className="text-heading">This page couldn&apos;t load</h1>
      <p className="mx-auto mt-1 max-w-md text-ink-2">
        {error.message && !error.digest ? error.message : "Something went wrong on our side. Try again in a moment."}
      </p>
      <Button className="mt-5" onClick={reset}>
        Try again
      </Button>
    </Sheet>
  );
}
