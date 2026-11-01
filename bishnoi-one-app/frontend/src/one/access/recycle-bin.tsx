"use client";

import { BulkList } from "@/src/platform/bulk/list";
import { SelectAllBox, SelectBox, SelectableRow } from "@/src/platform/bulk/selection";
import { RotateCcw, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { AsyncButton } from "@/src/platform/ui/async-button";
import { Button } from "@/src/platform/ui/ant-button";
import { Empty, Sheet } from "@/src/platform/ui/sheet";
import { TypeToDelete } from "@/src/platform/ui/type-to-delete";
import { bulkRestorePeople, erasePerson, restorePerson } from "./actions";
import type { BinPerson } from "./types";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-PH", { year: "numeric", month: "short", day: "numeric", timeZone: "Asia/Manila" });

/** The company's recycle bin (2026-10-30): who was deleted, when and by whom, each with Restore and Delete permanently beside them. */
export function RecycleBin({ people }: { people: BinPerson[] }) {
  const router = useRouter();
  const [erasing, setErasing] = useState<BinPerson | null>(null);
  if (people.length === 0) {
    return (
      <Sheet>
        <Empty icon="people" title="The recycle bin is empty">
          Employees you delete (⋯ → Delete) come here, and can be restored.
        </Empty>
      </Sheet>
    );
  }
  return (
    <BulkList
      items={people.map((p) => ({ id: p.id, name: p.fullName }))}
      noun={["employee", "employees"]}
      // Permanent delete stays one at a time: each is confirmed by typing their email.
      actions={[{ label: "Restore", icon: <RotateCcw className="size-4" aria-hidden />, doing: "Restoring", done: "restored, switched off", run: bulkRestorePeople }]}
    >
    <Sheet className="px-5 py-2">
      <div className="border-b border-rule py-2">
        <SelectAllBox>
          <span className="text-meta text-ink-3">Select all</span>
        </SelectAllBox>
      </div>
      <ul className="divide-y divide-rule">
        {people.map((p) => (
          <SelectableRow as="li" key={p.id} id={p.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-3">
            <SelectBox id={p.id} label={p.fullName} />
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
                toast.success(`${p.fullName} is back on Employees`, { description: "Switched off: switch them on when they should sign in again." });
                router.refresh();
              }}
            >
              Restore
            </AsyncButton>
            <Button size="sm" variant="danger" icon={<Trash2 className="size-4" aria-hidden />} onClick={() => setErasing(p)}>
              Delete permanently
            </Button>
          </SelectableRow>
        ))}
      </ul>
      {erasing && (
        <TypeToDelete
          open
          onClose={() => setErasing(null)}
          title="Delete employee permanently"
          name={erasing.email}
          nameLabel="Enter their email"
          phrase="delete employee"
          action="Delete permanently"
          onConfirm={async () => {
            const r = await erasePerson(erasing.id, erasing.email);
            if (r.ok) {
              toast.success(`${erasing.fullName} is permanently deleted`);
              router.refresh();
            }
            return r.ok ? { ok: true } : { ok: false, error: r.error };
          }}
        >
          {erasing.operator ? (
            <>
              <strong className="font-semibold text-ink">{erasing.fullName}</strong> leaves this company for good, but they are also a Bishnoi One operator: they keep their sign-in and can still enter every company until an operator
              switches that off in Operations.
            </>
          ) : (
            <>
              <strong className="font-semibold text-ink">{erasing.fullName}</strong> can&apos;t be restored after this: their sign-in, password, two-step sign-in and place on the organisation chart are removed. Their name stays on records
              they made in the apps, and the Activity log keeps what was done.
            </>
          )}
        </TypeToDelete>
      )}
    </Sheet>
    </BulkList>
  );
}
