"use client";

import { RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { AsyncButton } from "@/src/platform/ui/async-button";
import { checkNow } from "@/src/actions/applications";

/** Asks every application, integration and the database now, rather than when it's due. Anyone on staff may. */
export function CheckNow() {
  return (
    <AsyncButton
      icon={<RefreshCw className="size-4" aria-hidden />}
      onRun={async () => {
        const result = await checkNow();
        if (!result.ok) toast.error(result.error);
        else toast.success("Checked just now");
      }}
    >
      Check now
    </AsyncButton>
  );
}
