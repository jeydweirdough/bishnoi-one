"use client";

import "./globals.css";
import { ErrorScreen } from "@/src/platform/screens/error-screen";
import { GoHome, TryAgain } from "@/src/platform/screens/error-actions";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en">
      <body className="bg-bench font-sans text-ink antialiased">
        <ErrorScreen kind="crashed" standalone reference={error.digest} actions={<><TryAgain reset={reset} /><GoHome /></>} />
      </body>
    </html>
  );
}
