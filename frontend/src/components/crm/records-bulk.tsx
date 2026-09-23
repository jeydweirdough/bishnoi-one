"use client";

import { CalendarPlus, Trash2 } from "lucide-react";
import { useState, useTransition, type ReactNode } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, Input, Select } from "@/src/platform/ui/field";
import { BulkBar, BulkStep, useBulkRun, useSelection } from "@/src/platform/bulk/selection";
import { makeFormat, plural } from "@/src/platform/lib/format";
import type { Assignable, CompanyStatus, CustomerType, Org } from "@/src/platform/lib/types";
import { bulkRecords, recordsMatching } from "../../actions/crm";
import { typeOptions } from "./words";

type Step = "follow_up" | "status" | "owner" | null;

/**
 * What can be done to many companies or contacts at once: a follow-up for each,
 * a new status (companies), a new owner, or deleting them. Each shows only if
 * the person's role allows it; the API checks every record again.
 */
export function RecordsBulk({
  kind,
  can,
  people,
  filters,
  total,
  org,
  types = [],
}: {
  kind: "companies" | "contacts";
  /** The customer types a company can be set to (companies only). */
  types?: CustomerType[];
  can: { followUp: boolean; edit: boolean; delete: boolean };
  people: Assignable[];
  /** The list's filters, for "select all that match". */
  filters: Record<string, string>;
  total: number;
  org: Org;
}) {
  const noun: [string, string] = kind === "companies" ? ["company", "companies"] : ["contact", "contacts"];
  const fmt = makeFormat(org);
  const s = useSelection();
  const { run, running } = useBulkRun();
  const [step, setStep] = useState<Step>(null);
  const [finding, startFinding] = useTransition();
  const count = s.ids.length;
  const many = plural(count, ...noun);

  function selectAll() {
    startFinding(async () => {
      const found = await recordsMatching(kind, filters);
      if (found.ok) s.selectMatching(found.data);
      else toast.error(found.error);
    });
  }

  // Gmail's offer: the whole page is ticked and there's more beyond it.
  const extra = s.matching ? (
    <span className="text-meta text-ink-3">Every {noun[0]} that matches</span>
  ) : s.pageState === "all" && total > count && total <= 500 ? (
    <Button size="sm" variant="quiet" loading={finding} onClick={selectAll}>
      Select all {total} that match
    </Button>
  ) : null;

  const steps: Record<Exclude<Step, null>, ReactNode> = {
    follow_up: (
      <BulkStep
        submitLabel={`Add ${plural(count, "follow-up")}`}
        onCancel={() => setStep(null)}
        onSubmit={async (form) => {
          const title = String(form.get("title") ?? "").trim();
          const dueOn = String(form.get("dueOn") ?? "");
          if (title.length < 2 || !dueOn) {
            toast.error("Give the follow-up a title and a date.");
            return false;
          }
          await run({ doing: "Adding follow-ups", did: (n) => `Follow-up added for ${plural(n, ...noun)}` }, (ids) =>
            bulkRecords(kind, ids, { action: "follow_up", followUp: { title, dueOn }, toOwner: form.get("who") === "owner" }),
          );
        }}
      >
        <Field label="Follow-up" className="w-56">
          {(p) => <Input {...p} name="title" defaultValue="Follow-up call" required minLength={2} maxLength={160} autoFocus />}
        </Field>
        <Field label="Due" className="w-36">
          {(p) => <Input {...p} name="dueOn" type="date" defaultValue={fmt.todayKey()} min={fmt.todayKey()} required />}
        </Field>
        <Field label="For" className="w-44">
          {(p) => (
            <Select {...p} name="who" defaultValue="owner">
              <option value="owner">Each one&apos;s owner</option>
              <option value="me">Me</option>
            </Select>
          )}
        </Field>
      </BulkStep>
    ),
    status: (
      <BulkStep
        submitLabel={`Set for ${many}`}
        onCancel={() => setStep(null)}
        onSubmit={async (form) => {
          const status = String(form.get("status")) as CompanyStatus;
          const label = types.find((x) => x.code === status)?.name.toLowerCase() ?? status;
          await run({ doing: "Changing type", did: (n) => `${plural(n, ...noun)} now ${label}` }, (ids) =>
            bulkRecords(kind, ids, { action: "status", status }),
          );
        }}
      >
        <Field label="Type" className="w-44">
          {(p) => (
            <Select {...p} name="status" autoFocus>
              {typeOptions(types).map((x) => (
                <option key={x.value} value={x.value}>
                  {x.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </BulkStep>
    ),
    owner: (
      <BulkStep
        submitLabel={`Give ${many}`}
        onCancel={() => setStep(null)}
        onSubmit={async (form) => {
          const ownerId = String(form.get("ownerId") ?? "");
          if (!ownerId) return false;
          const name = people.find((p) => p.id === ownerId)?.name ?? "them";
          await run({ doing: "Changing owner", did: (n) => `${plural(n, ...noun)} now with ${name}` }, (ids) =>
            bulkRecords(kind, ids, { action: "owner", ownerId }),
          );
        }}
      >
        <Field label="New owner" className="w-52">
          {(p) => (
            <Select {...p} name="ownerId" required defaultValue="" autoFocus>
              <option value="" disabled>
                Pick someone
              </option>
              {people.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.name}
                  {person.isMe ? " (you)" : ""}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </BulkStep>
    ),
  };

  return (
    <BulkBar noun={noun} extra={extra} step={step ? steps[step] : undefined}>
      {can.followUp && (
        <Button size="sm" variant="primary" disabled={running} onClick={() => setStep("follow_up")} icon={<CalendarPlus className="size-4" aria-hidden />}>
          Add follow-up
        </Button>
      )}
      {can.edit && kind === "companies" && (
        <Button size="sm" disabled={running} onClick={() => setStep("status")}>
          Set type
        </Button>
      )}
      {can.edit && people.length > 1 && (
        <Button size="sm" disabled={running} onClick={() => setStep("owner")}>
          Change owner
        </Button>
      )}
      {can.delete && (
        <ConfirmButton
          label="Delete"
          triggerSize="sm"
          icon={<Trash2 className="size-4" aria-hidden />}
          disabled={running}
          title={`Delete ${many}?`}
          body={
            kind === "companies"
              ? "Their activities are deleted with them. A company that still has contacts is skipped. This can't be undone."
              : "Activities only about them are deleted with them. This can't be undone."
          }
          confirmLabel={`Delete ${many}`}
          onConfirm={() => run({ doing: "Deleting", did: (n) => `${plural(n, ...noun)} deleted` }, (ids) => bulkRecords(kind, ids, { action: "delete" }))}
        />
      )}
    </BulkBar>
  );
}
