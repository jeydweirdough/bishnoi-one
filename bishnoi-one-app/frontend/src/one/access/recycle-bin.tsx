"use client";

import { BulkBar, SelectAllBox, SelectBox, SelectableRow, SelectionProvider, useBulkRun, useSelection } from "@/src/platform/bulk/selection";
import { plural } from "@/src/platform/lib/format";
import { RotateCcw, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { AsyncButton } from "@/src/platform/ui/async-button";
import { Button } from "@/src/platform/ui/ant-button";
import { Empty, Sheet } from "@/src/platform/ui/sheet";
import { TypeToDelete } from "@/src/platform/ui/type-to-delete";
import { bulkErasePeople, bulkRestorePeople, erasePerson, restorePerson } from "./actions";
import type { BinPerson } from "./types";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-PH", { year: "numeric", month: "short", day: "numeric", timeZone: "Asia/Manila" });

const NOUN: [string, string] = ["employee", "employees"];

/** What can be done to several at once. Delete permanently asks as one does: here you type how many (2026-11-01). */
function BinBar({ people }: { people: BinPerson[] }) {
  const s = useSelection();
  const { run, running } = useBulkRun();
  const [erasing, setErasing] = useState(false);
  const chosen = people.filter((p) => s.isSelected(p.id));
  const many = plural(chosen.length, ...NOUN);
  const operators = chosen.filter((p) => p.operator).length;
  return (
    <>
      <BulkBar noun={NOUN}>
        <Button size="sm" icon={<RotateCcw className="size-4" aria-hidden />} disabled={running} onClick={() => void run({ doing: "Restoring", did: (n) => `${plural(n, ...NOUN)} restored, switched off` }, bulkRestorePeople)}>
          Restore
        </Button>
        <Button size="sm" variant="danger" icon={<Trash2 className="size-4" aria-hidden />} disabled={running} onClick={() => setErasing(true)}>
          Delete permanently
        </Button>
      </BulkBar>
      {erasing && (
        <TypeToDelete
          open
          onClose={() => setErasing(false)}
          title={`Delete ${many} permanently`}
          name={many}
          nameLabel="Enter how many"
          phrase="delete employees"
          action="Delete permanently"
          onConfirm={async () => {
            await run({ doing: "Deleting permanently", did: (n) => `${plural(n, ...NOUN)} permanently deleted` }, () => bulkErasePeople(chosen.map((p) => ({ id: p.id, email: p.email }))));
            return { ok: true };
          }}
        >
          <strong className="font-semibold text-ink">{many}</strong> can&apos;t be restored after this: their sign-ins, passwords, two-step sign-in and places on the organisation chart are removed. Their names stay on records they made in the
          apps, and the Activity log keeps what was done.
          {operators > 0 && <> {plural(operators, "of them is", "of them are")} also a Bishnoi One operator: they keep their sign-in and can still enter every company until an operator switches that off in Operations.</>}
        </TypeToDelete>
      )}
    </>
  );
}

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
    <SelectionProvider items={people.map((p) => ({ id: p.id, name: p.fullName }))}>
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
    <BinBar people={people} />
    </SelectionProvider>
  );
}
