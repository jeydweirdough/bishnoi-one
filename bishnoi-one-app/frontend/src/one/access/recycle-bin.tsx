"use client";

import { RotateCcw } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { AsyncButton } from "@/src/platform/ui/async-button";
import { Empty, Sheet } from "@/src/platform/ui/sheet";
import { restorePerson } from "./actions";
import type { BinPerson } from "./types";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-PH", { year: "numeric", month: "short", day: "numeric", timeZone: "Asia/Manila" });

/** The company's recycle bin (2026-10-30): who was deleted, when and by whom, each with Restore beside them. */
export function RecycleBin({ people }: { people: BinPerson[] }) {
  const router = useRouter();
  if (people.length === 0) {
    return (
      <Sheet>
        <Empty icon="people" title="The recycle bin is empty">
          People you delete on People (⋯ → Delete) come here, and can be restored.
        </Empty>
      </Sheet>
    );
  }
  return (
    <Sheet className="px-5 py-2">
      <ul className="divide-y divide-rule">
        {people.map((p) => (
          <li key={p.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-3">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-ink">{p.fullName}</p>
              <p className="truncate text-meta text-ink-3">
                {p.email}
                {p.title ? ` · ${p.title}` : ""}
              </p>
            </div>
            <p className="text-meta text-ink-3">
              Deleted {day(p.deletedAt)}
              {p.deletedBy ? ` by ${p.deletedBy}` : ""}
            </p>
            <AsyncButton
              size="sm"
              icon={<RotateCcw className="size-4" aria-hidden />}
              onRun={async () => {
                const r = await restorePerson(p.id);
                if (!r.ok) return void toast.error(r.error);
                toast.success(`${p.fullName} is back on People`, { description: "Switched off: switch them on when they should sign in again." });
                router.refresh();
              }}
            >
              Restore
            </AsyncButton>
          </li>
        ))}
      </ul>
    </Sheet>
  );
}
