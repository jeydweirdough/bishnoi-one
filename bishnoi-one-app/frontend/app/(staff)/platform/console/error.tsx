"use client";

// A screen that throws shows what happened and offers another go, instead of
// the app falling over around it. Never the error's text: the reference
// (Next's digest) finds it in the server's log.
import { ErrorScreen } from "@/src/modules/console/platform/screens/error-screen";
import { GoHome, TryAgain } from "@/src/modules/console/platform/screens/error-actions";

export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <ErrorScreen kind="failed" reference={error.digest} actions={<><TryAgain reset={reset} /><GoHome /></>} />;
}
