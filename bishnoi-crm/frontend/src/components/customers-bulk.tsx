"use client";

import { CalendarPlus, Trash2 } from "lucide-react";
import { useState, useTransition, type ReactNode } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, Input, Select } from "@/src/platform/ui/field";
import { bulkCustomers, customersMatching, divisionPeople } from "../actions/bulk";
import { makeFormat, plural } from "@/src/platform/lib/format";
import { CUSTOMER_STATUSES } from "@/src/platform/lib/labels";
import type { CustomerStatus, Org } from "@/src/platform/lib/types";
import { BulkBar, BulkStep, useBulkRun, useSelection } from "@/src/platform/bulk/selection";

const NOUN: [string, string] = ["customer", "customers"];

type Step = "follow_up" | "status" | "owner" | null;

export function CustomersBulk({
  teams,
  can,
  filters,
  total,
  org,
}: {
  /** The teams the caller works in, each naming its division: who customers
   *  can be given to depends on both. */
  teams: { code: string; division: string }[];
  can: { create: boolean; edit: boolean; delete: boolean };
  /** The list's filters, for "select all that match". */
  filters: Record<string, string>;
  total: number;
  org: Org;
}) {
  const fmt = makeFormat(org);
  const s = useSelection();
  const { run, running } = useBulkRun();
  const [step, setStep] = useState<Step>(null);
  const [people, setPeople] = useState<{ id: string; name: string }[] | null>(null);
  const [finding, startFinding] = useTransition();
  const count = s.ids.length;
  const many = plural(count, ...NOUN);

  function openOwner() {
    setStep("owner");
    if (people) return;
    void divisionPeople(teams).then((r) => (r.ok ? setPeople(r.data) : toast.error(r.error)));
  }

  function selectAll() {
    startFinding(async () => {
      const found = await customersMatching(filters);
      if (found.ok) s.selectMatching(found.data);
      else toast.error(found.error);
    });
  }

  // Gmail's offer: the whole page is ticked and there's more beyond it.
  const extra =
    s.matching ? (
      <span className="text-meta text-ink-3">Every customer that matches</span>
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
          await run({ doing: "Adding follow-ups", did: (n) => `Follow-up added for ${plural(n, ...NOUN)}` }, (ids) =>
            bulkCustomers(ids, {
              action: "follow_up",
              followUp: { title, dueOn, assigneeId: null },
              toOwner: form.get("who") === "owner",
            }),
          );
        }}
      >
        <Field label="Follow-up" className="w-56">
          {(p) => <Input {...p} name="title" defaultValue="Follow-up call" required minLength={2} maxLength={160} autoFocus />}
        </Field>
        <Field label="Due" className="w-36">
          {(p) => <Input {...p} name="dueOn" type="date" defaultValue={fmt.todayKey()} required />}
        </Field>
        <Field label="For" className="w-44">
          {(p) => (
            <Select {...p} name="who" defaultValue="owner">
              <option value="owner">Each customer&apos;s owner</option>
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
          const status = String(form.get("status")) as CustomerStatus;
          await run(
            { doing: "Changing status", did: (n) => `${plural(n, ...NOUN)} now ${CUSTOMER_STATUSES[status].toLowerCase()}` },
            (ids) => bulkCustomers(ids, { action: "status", status }),
          );
        }}
      >
        <Field label="Status" className="w-36">
          {(p) => (
            <Select {...p} name="status" defaultValue="active" autoFocus>
              {Object.entries(CUSTOMER_STATUSES).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
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
          const name = people?.find((p) => p.id === ownerId)?.name ?? "them";
          await run({ doing: "Changing owner", did: (n) => `${plural(n, ...NOUN)} now with ${name}` }, (ids) =>
            bulkCustomers(ids, { action: "owner", ownerId }),
          );
        }}
      >
        <Field label="New owner" className="w-52">
          {(p) => (
            <Select {...p} name="ownerId" required disabled={!people} defaultValue="" autoFocus>
              <option value="" disabled>
                {people ? "Pick someone" : "Loading people…"}
              </option>
              {people?.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </BulkStep>
    ),
  };

  return (
    <BulkBar noun={NOUN} extra={extra} step={step ? steps[step] : undefined}>
      {can.create && (
        <Button size="sm" variant="primary" disabled={running} onClick={() => setStep("follow_up")} icon={<CalendarPlus className="size-4" aria-hidden />}>
          Add follow-up
        </Button>
      )}
      {can.edit && (
        <>
          <Button size="sm" disabled={running} onClick={() => setStep("status")}>
            Set status
          </Button>
          <Button size="sm" disabled={running} onClick={openOwner}>
            Change owner
          </Button>
        </>
      )}
      {can.delete && (
        <ConfirmButton
          label="Delete"
          triggerSize="sm"
          icon={<Trash2 className="size-4" aria-hidden />}
          disabled={running}
          title={`Delete ${many}?`}
          body="Their calls, visits, follow-ups and quotes are deleted with them. This can't be undone."
          confirmLabel={`Delete ${many}`}
          onConfirm={() => run({ doing: "Deleting", did: (n) => `${plural(n, ...NOUN)} deleted` }, (ids) => bulkCustomers(ids, { action: "delete" }))}
        />
      )}
    </BulkBar>
  );
}
