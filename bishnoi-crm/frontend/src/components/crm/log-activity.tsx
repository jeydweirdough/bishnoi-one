"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Choice, Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { Icon } from "@/src/platform/ui/icons";
import { createActivity, type ActivityInput } from "../../actions/crm";
import type { Assignable, CrmKind, Org, Ref } from "@/src/platform/lib/types";
import { OwnerField } from "./owner-field";
import { useCan } from "../quick-add/can";
import { AddCustomer } from "../quick-add/forms";
import { QuickAdd } from "../quick-add/quick-add";
import { KINDS, kindOf, localDateTime, tomorrowMorning } from "./words";

const PLACEHOLDERS: Record<CrmKind, string> = {
  call: "What was the call about?",
  meeting: "What's the meeting for?",
  email: "What was the email about?",
  note: "What should the team remember?",
  task: "What needs doing?",
};

/**
 * Logging what happened (a call, an email, a note) or planning what's next (a
 * meeting, a task). On a company or contact page it's about that record; on the
 * Activities page a company can be picked.
 */
export function LogActivity({
  org,
  now,
  people,
  companyId,
  contactId,
  contacts = [],
  companies,
  onDone,
}: {
  org: Org;
  /** The moment the page was made, so the server and the browser start the
   *  "when" field on the same minute (they'd disagree if each read its own clock). */
  now: string;
  people: Assignable[];
  companyId?: string;
  contactId?: string;
  /** On a company page: its contacts, so the activity can name one. */
  contacts?: Ref[];
  /** On the Activities page: companies to pick from. */
  companies?: Ref[];
  /** Called once it's saved (the panel it sits in closes). */
  onDone?: () => void;
}) {
  const [kind, setKind] = useState<CrmKind>("call");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [at, setAt] = useState(() => localDateTime(new Date(now), org.timezone));
  const [planned, setPlanned] = useState(false);
  const [duration, setDuration] = useState("");
  const [direction, setDirection] = useState<"out" | "in">("out");
  const [contact, setContact] = useState(contactId ?? "");
  const [company, setCompany] = useState(companyId ?? "");
  const can = useCan();
  const [made, setMade] = useState<Ref[]>([]);
  const [ownerId, setOwnerId] = useState(people.find((p) => p.isMe)?.id ?? people[0]?.id ?? "");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [pending, start] = useTransition();
  const info = kindOf(kind);

  function pick(next: CrmKind) {
    setKind(next);
    // A meeting or task is for later; a call, email or note already happened.
    const isPlanned = kindOf(next).planned;
    if (isPlanned !== planned) {
      setPlanned(isPlanned);
      setAt(isPlanned ? tomorrowMorning(org.timezone) : localDateTime(new Date(), org.timezone));
    }
  }

  function submit() {
    const input: ActivityInput = {
      kind,
      subject: subject.trim(),
      body: body.trim() || null,
      at: at || null,
      companyId: company || null,
      contactId: contact || null,
      durationMinutes: (kind === "call" || kind === "meeting") && duration ? Number(duration) : null,
      direction: kind === "call" || kind === "email" ? direction : null,
      ownerId: ownerId || null,
    };
    start(async () => {
      const result = await createActivity(input);
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(info.planned ? `${info.label} planned` : `${info.label} logged`, { description: result.data.subject });
      setSubject("");
      setBody("");
      setDuration("");
      setError(null);
      setFields({});
      setAt(info.planned ? tomorrowMorning(org.timezone) : localDateTime(new Date(), org.timezone));
      onDone?.();
    });
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="space-y-4"
    >
      <Choice<CrmKind>
        name="kind"
        legend="What"
        value={kind}
        onChange={pick}
        options={KINDS.map((k) => ({ value: k.kind, label: k.label, icon: <Icon name={k.icon} className="size-3.5" /> }))}
      />
      <Field label={info.planned ? "What it's for" : "Subject"} error={fields.subject}>
        {(p) => <Input {...p} value={subject} onChange={(e) => setSubject(e.target.value)} placeholder={PLACEHOLDERS[kind]} required />}
      </Field>
      <Field label="Details" optional error={fields.body}>
        {(p) => <Textarea {...p} rows={2} value={body} onChange={(e) => setBody(e.target.value)} />}
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={info.planned ? "When it's due" : "When"} error={fields.at}>
          {(p) => <Input {...p} type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} />}
        </Field>
        {(kind === "call" || kind === "meeting") && (
          <Field label="How long (minutes)" optional error={fields.durationMinutes}>
            {(p) => <Input {...p} type="number" min={0} max={1440} inputMode="numeric" value={duration} onChange={(e) => setDuration(e.target.value)} />}
          </Field>
        )}
        {(kind === "call" || kind === "email") && (
          <Choice<"out" | "in">
            name="direction"
            legend="Which way"
            value={direction}
            onChange={setDirection}
            options={[
              { value: "out", label: kind === "call" ? "We called" : "We sent it" },
              { value: "in", label: kind === "call" ? "They called" : "They sent it" },
            ]}
          />
        )}
        {companies && (
          <div>
          <Field label="Customer" optional error={fields.companyId}>
            {(p) => (
              <Select {...p} value={company} onChange={(e) => setCompany(e.target.value)}>
                <option value="">None</option>
                {[...made, ...companies.filter((c) => !made.some((m) => m.id === c.id))].map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          {can("customers.create") && (
            <QuickAdd label="New customer" title="New customer">
              {(done) => <AddCustomer onAdded={(c) => (setMade([c, ...made]), setCompany(c.id))} done={done} />}
            </QuickAdd>
          )}
          </div>
        )}
        {contacts.length > 0 && !contactId && (
          <Field label="With" optional error={fields.contactId}>
            {(p) => (
              <Select {...p} value={contact} onChange={(e) => setContact(e.target.value)}>
                <option value="">Nobody in particular</option>
                {contacts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}
        {info.planned && people.length > 1 && (
          <OwnerField people={people} value={ownerId} onChange={setOwnerId} error={fields.ownerId} label="Who's doing it" />
        )}
      </div>
      <FormError message={error} />
      <Button type="submit" variant="primary" loading={pending} disabled={!subject.trim()}>
        {info.planned ? `Plan ${info.label.toLowerCase()}` : `Log ${info.label.toLowerCase()}`}
      </Button>
    </form>
  );
}
