"use client";

import { ErrorScreen } from "@/src/platform/screens/error-screen";
import { GoHome, TryAgain } from "@/src/platform/screens/error-actions";

export default function PageError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <ErrorScreen kind="failed" reference={error.digest} actions={<><TryAgain reset={reset} /><GoHome /></>} />;
}
