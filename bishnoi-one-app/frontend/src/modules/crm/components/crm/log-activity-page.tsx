"use client";

import { useRouter } from "next/navigation";
import type { Assignable, CrmKind, Org, Ref } from "@/src/platform/lib/types";
import { LogActivity } from "@/src/modules/crm/components/crm/log-activity";

/** The Log activity form on its own page: once it's saved, back to where it was opened from. */
export function LogActivityPageForm({ back, ...form }: { back: string; org: Org; now: string; people: Assignable[]; companyId?: string; contactId?: string; contacts?: Ref[]; companies?: Ref[]; initialKind?: CrmKind }) {
  const router = useRouter();
  return (
    <LogActivity
      {...form}
      onDone={() => {
        router.push(back);
        router.refresh();
      }}
    />
  );
}
