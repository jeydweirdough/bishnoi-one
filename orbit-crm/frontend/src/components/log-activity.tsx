"use client";

import { useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { useActivityFeed } from "../components/activity-feed";
import { Button } from "@/src/platform/ui/button";
import { Choice, Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { Icon, listIcon } from "@/src/platform/ui/icons";
import { logActivity } from "../actions/customers";
import { makeFormat } from "@/src/platform/lib/format";
import { listName, pickable } from "@/src/platform/lib/labels";
import type { Activity, ListItem, Org, Person } from "@/src/platform/lib/types";

// A follow-up worth suggesting after a call that didn't land. Only the outcomes
// Orbit starts a company off with are known by code here; a company that writes
// its own simply gets no suggestion, which is no worse than typing one.
const SUGGESTED_FOLLOW_UP: Record<string, string> = {
  no_answer: "Try calling again",
  call_back: "Call back",
  reached: "Follow up",
};
const CHASE = new Set(["no_answer", "call_back"]);

function addDays(key: string, days: number) {
  const d = new Date(`${key}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function LogActivity({
  customerId,
  people,
  me,
  org,
  kinds,
  outcomes,
}: {
  customerId: string;
  people: { id: string; name: string }[];
  me: Person;
  // The company: how it writes dates, and its own words for what just happened.
  org: Org;
  kinds: ListItem[];
  outcomes: ListItem[];
}) {
  const form = useRef<HTMLFormElement>(null);
  const [pending, start] = useTransition();
  const offered = pickable(kinds);
  const pickableOutcomes = pickable(outcomes);
  const [kind, setKind] = useState(offered[0]?.code ?? "");
  const [outcome, setOutcome] = useState("");
  const [withFollowUp, setWithFollowUp] = useState(false);
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const feed = useActivityFeed();
  const fmt = makeFormat(org);
  const today = fmt.todayKey();
  const kindName = listName(kinds, kind);
  // Which activities deserve an outcome is the company's call, not ours, so it's
  // offered on every one of them and stays optional.
  const hasOutcome = pickableOutcomes.length > 0;

  function pickOutcome(value: string) {
    setOutcome(value);
    const suggestion = SUGGESTED_FOLLOW_UP[value];
    if (suggestion && !title) setTitle(suggestion);
    if (CHASE.has(value)) setWithFollowUp(true);
  }

  function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const input = {
      kind,
      outcome: hasOutcome && outcome ? outcome : null,
      summary: String(data.get("summary") ?? "").trim(),
      followUp: withFollowUp
        ? {
            title: title.trim(),
            dueOn: String(data.get("dueOn") ?? ""),
            assigneeId: String(data.get("assigneeId") ?? "") || null,
          }
        : null,
    };
    // Catch the obvious here, so nothing appears in the history only to vanish.
    if (input.summary.length < 2) {
      setFields({ summary: "Say what happened (at least 2 characters)." });
      setError("Some fields need a look.");
      return;
    }
    const typed = { kind, outcome, withFollowUp, title };
    start(async () => {
      // Show it in the history now and clear the form for the next one; the
      // server catches up behind. Nothing is lost if it refuses: the entry goes
      // and what was typed comes back.
      feed?.add({
        id: `pending-${Date.now()}`,
        customerId,
        customerName: null,
        division: "",
        divisionName: "",
        team: "",
        teamName: "",
        kind,
        outcome: input.outcome as Activity["outcome"],
        summary: input.summary,
        occurredAt: new Date().toISOString(),
        by: me,
        can: { delete: false },
      });
      form.current?.reset();
      setOutcome("");
      setWithFollowUp(false);
      setTitle("");
      setError(null);
      setFields({});

      const result = await logActivity(customerId, input);
      if (!result.ok) {
        setKind(typed.kind);
        setOutcome(typed.outcome);
        setWithFollowUp(typed.withFollowUp);
        setTitle(typed.title);
        const summary = form.current?.elements.namedItem("summary");
        if (summary instanceof HTMLTextAreaElement) summary.value = input.summary;
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(`${listName(kinds, typed.kind)} logged`, {
        description: input.followUp ? `Follow-up set: ${input.followUp.title}` : undefined,
      });
    });
  }

  return (
    <form ref={form} onSubmit={submit} noValidate className="space-y-4">
      <Choice
        legend="What happened"
        name="kind"
        value={kind}
        onChange={setKind}
        options={offered.map((k) => ({ value: k.code, label: k.name, icon: <Icon name={listIcon(k)} /> }))}
      />
      {hasOutcome && (
        <Field label="Outcome" optional>
          {(p) => (
            <Select {...p} value={outcome} onChange={(e) => pickOutcome(e.target.value)}>
              <option value="">—</option>
              {pickableOutcomes.map((o) => (
                <option key={o.code} value={o.code}>
                  {o.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
      )}
      <Field label="Summary" error={fields.summary}>
        {(p) => (
          <Textarea
            {...p}
            name="summary"
            required
            rows={3}
            maxLength={2000}
            placeholder="What was discussed, what they asked for"
          />
        )}
      </Field>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={withFollowUp}
          onChange={(e) => setWithFollowUp(e.target.checked)}
          className="size-4 accent-hema"
        />
        Add a follow-up
      </label>

      {withFollowUp && (
        <div className="animate-reshape space-y-4 border-l-2 border-rule pl-4">
          <Field label="Follow-up" error={fields.title}>
            {(p) => <Input {...p} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={160} placeholder="e.g. Send samples" />}
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Due" error={fields.dueOn}>
              {(p) => <Input {...p} name="dueOn" type="date" defaultValue={addDays(today, 1)} min={today} />}
            </Field>
            <Field label="For" error={fields.assigneeId}>
              {(p) => (
                <Select {...p} name="assigneeId" defaultValue={me.id ?? ""}>
                  {people.map((person) => (
                    <option key={person.id} value={person.id}>
                      {person.id === me.id ? `${person.name} (you)` : person.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
        </div>
      )}

      <FormError message={error} />
      <Button type="submit" variant="primary" loading={pending}>
        Save {kindName.toLowerCase()}
      </Button>
    </form>
  );
}
