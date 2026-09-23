"use client";

import { Plus } from "lucide-react";
import { useOptimistic, useState, useTransition } from "react";
import { toast } from "sonner";
import { FollowUpItem } from "../components/follow-up-item";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { addFollowUp } from "../actions/sales";
import type { FollowUp, Org, Person } from "@/src/platform/lib/types";

export function FollowUpsPanel({
  customerId,
  followUps,
  today,
  people,
  me,
  canAdd,
  org,
}: {
  customerId: string;
  followUps: FollowUp[];
  today: string;
  people: { id: string; name: string }[];
  me: Person;
  canAdd: boolean;
  org: Org;
}) {
  const [adding, setAdding] = useState(false);
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  // What was typed, kept so a failed save can put it back.
  const [draft, setDraft] = useState<{ title: string; dueOn: string; assigneeId: string | null } | null>(null);
  // A new follow-up joins the list the moment it's added; the server's copy replaces it.
  const [shown, show] = useOptimistic(followUps, (list: FollowUp[], added: FollowUp) => [...list, added]);
  const open = shown.filter((f) => f.status === "open");
  const done = shown.filter((f) => f.status === "done");

  const row = (f: FollowUp) => ({
    ...f,
    place: f.assignee.name ? `for ${f.assignee.id === me.id ? "you" : f.assignee.name}` : undefined,
    doneByName: f.doneBy?.name,
    canEdit: f.can.edit,
  });

  function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const input = {
      title: String(data.get("title") ?? "").trim(),
      dueOn: String(data.get("dueOn") ?? ""),
      assigneeId: String(data.get("assigneeId") ?? "") || null,
    };
    if (input.title.length < 2) {
      setFields({ title: "Say what to do (at least 2 characters)." });
      return;
    }
    const assignee = people.find((p) => p.id === input.assigneeId) ?? { id: me.id ?? "", name: me.name ?? "" };
    start(async () => {
      show({
        id: `pending-${Date.now()}`,
        rev: null,
        customerId,
        customerName: null,
        // Blank until the server answers; this row only exists for the moment
        // between pressing the button and the real one arriving.
        division: "",
        divisionName: "",
        team: "",
        teamName: "",
        title: input.title,
        dueOn: input.dueOn,
        bucket: input.dueOn < today ? "overdue" : input.dueOn === today ? "today" : "upcoming",
        status: "open",
        assignee: { id: assignee.id, name: assignee.name },
        doneAt: null,
        doneBy: null,
        can: { edit: false },
      });
      setAdding(false);
      setError(null);
      setFields({});

      const result = await addFollowUp(customerId, input);
      if (!result.ok) {
        setDraft(input);
        setAdding(true);
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      setDraft(null);
      toast.success("Follow-up added", { description: input.title });
    });
  }

  return (
    <div>
      {open.length === 0 && !adding && <p className="py-3 text-meta text-ink-3">No open follow-ups.</p>}
      {open.length > 0 && (
        <ul className="divide-y divide-rule">
          {open.map((f) => (
            <FollowUpItem key={f.id} row={row(f)} today={today} org={org} showCustomer={false} />
          ))}
        </ul>
      )}

      {adding ? (
        <form onSubmit={submit} noValidate className="animate-reshape mt-2 space-y-4 border-t border-rule pt-4">
          <Field label="Follow-up" error={fields.title}>
            {(p) => <Input {...p} name="title" defaultValue={draft?.title} maxLength={160} placeholder="e.g. Send price list" autoFocus />}
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Due" error={fields.dueOn}>
              {(p) => <Input {...p} name="dueOn" type="date" defaultValue={draft?.dueOn ?? today} min={today} />}
            </Field>
            <Field label="For" error={fields.assigneeId}>
              {(p) => (
                <Select {...p} name="assigneeId" defaultValue={draft?.assigneeId ?? me.id ?? ""}>
                  {people.map((person) => (
                    <option key={person.id} value={person.id}>
                      {person.id === me.id ? `${person.name} (you)` : person.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <FormError message={error} />
          <div className="flex gap-2">
            <Button type="submit" variant="primary" size="sm" loading={pending}>
              Add follow-up
            </Button>
            <Button size="sm" variant="quiet" onClick={() => setAdding(false)} disabled={pending}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        canAdd && (
          <Button size="sm" variant="quiet" className="mt-1 -ml-3" icon={<Plus className="size-4" aria-hidden />} onClick={() => setAdding(true)}>
            Add follow-up
          </Button>
        )
      )}

      {done.length > 0 && (
        <details className="mt-3 border-t border-rule pt-2">
          <summary className="cursor-pointer py-1 text-meta font-medium text-ink-2">Done · {done.length}</summary>
          <ul className="divide-y divide-rule">
            {done.map((f) => (
              <FollowUpItem key={f.id} row={row(f)} today={today} org={org} showCustomer={false} />
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
