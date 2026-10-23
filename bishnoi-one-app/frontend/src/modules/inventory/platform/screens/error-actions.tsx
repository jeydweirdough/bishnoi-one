"use client";

import { useRouter } from "next/navigation";
import { plainButton } from "@/src/modules/inventory/platform/screens/error-screen";

// The error pages' buttons. Plain elements, not the kit's Ant buttons, so they
// work on the crash page too, where the app's frame (and its theme) is gone.

/** Try again: the page's own retry when it has one, else reload what was being asked for. */
export function TryAgain({ reset, primary = true }: { reset?: () => void; primary?: boolean }) {
  const router = useRouter();
  return (
    <button
      type="button"
      className={plainButton(primary)}
      onClick={() => {
        if (reset) {
          router.refresh();
          reset();
        } else window.location.reload();
      }}
    >
      Try again
    </button>
  );
}

/** Back where they came from; with nowhere to go back to, home. */
export function GoBack({ primary = true }: { primary?: boolean }) {
  return (
    <button
      type="button"
      className={plainButton(primary)}
      onClick={() => {
        if (window.history.length > 1) window.history.back();
        else window.location.assign("/");
      }}
    >
      Go back
    </button>
  );
}

export function GoHome({ primary = false }: { primary?: boolean }) {
  return (
    <a href="/inventory" className={plainButton(primary)}>
      Go home
    </a>
  );
}
