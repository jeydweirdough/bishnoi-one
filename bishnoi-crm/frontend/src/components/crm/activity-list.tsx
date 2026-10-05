"use client";

import { Trash2 } from "lucide-react";
import { CallOutcome } from "./new-call";
import Link from "next/link";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Icon } from "@/src/platform/ui/icons";
import { makeFormat } from "@/src/platform/lib/format";
import type { ActivityItem, Org } from "@/src/platform/lib/types";
import { deleteActivity, updateActivity } from "../../actions/crm";
import { kindOf } from "./words";

/**
 * Activities, newest or soonest first as given. Meetings and tasks carry a box
 * to tick when they're done. `hide` leaves out links that would only point back
 * at the page this list is on.
 */
export function ActivityList({
  activities,
  org,
  empty,
  hide = [],
}: {
  activities: ActivityItem[];
  org: Org;
  empty: string;
  hide?: ("company" | "contact" | "owner")[];
}) {
  if (activities.length === 0) return <p className="py-3 text-meta text-ink-3">{empty}</p>;
  return (
    <ol className="divide-y divide-rule">
      {activities.map((a) => (
        <Line key={a.id} a={a} org={org} hide={hide} />
      ))}
    </ol>
  );
}

function Line({ a, org, hide }: { a: ActivityItem; org: Org; hide: string[] }) {
  const fmt = makeFormat(org);
  const kind = kindOf(a.kind);
  const [done, setDone] = useState(a.isDone);
  const [saving, start] = useTransition();
  const [asking, setAsking] = useState(false);
  // A planned call with an objective asks how it went when it's ticked off.
  const isCall = Boolean(a.objective);

  function toggle() {
    const next = !done;
    if (next && isCall) return setAsking(true);
    setDone(next); // at once; put back if the API says no
    start(async () => {
      const result = await updateActivity(a.id, { done: next });
      if (!result.ok) {
        setDone(!next);
        toast.error(result.error);
      }
    });
  }

  function finish(outcome: string, discussed: string[]) {
    start(async () => {
      const result = await updateActivity(a.id, { done: true, outcome: outcome || null, discussed });
      if (!result.ok) return void toast.error(result.error);
      setDone(true);
      setAsking(false);
    });
  }

  const when = a.isPlanned && !done ? due(a.at, fmt) : fmt.whenLabel(a.at);
  const late = a.isPlanned && !done && a.isOverdue;

  return (
    <li className="flex gap-3 py-3.5">
      {a.isPlanned ? (
        <label className={`mt-1 inline-flex size-6 shrink-0 items-center justify-center ${a.can.edit ? "cursor-pointer" : ""}`}>
          <input
            type="checkbox"
            checked={done}
            disabled={!a.can.edit || saving}
            onChange={toggle}
            className="size-4 accent-[var(--color-hema)]"
            aria-label={`${done ? "Reopen" : "Mark done"}: ${a.subject}`}
          />
        </label>
      ) : (
        <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-bench text-ink-2">
          <Icon name={kind.icon} />
        </span>
      )}
      <div className="min-w-0 flex-1">
        <p className="text-meta text-ink-3">
          <span className="inline-flex items-center gap-1 font-semibold text-ink-2">
            {a.isPlanned && <Icon name={kind.icon} className="size-3.5" />}
            {kind.label}
            {a.direction && <span className="font-normal">{a.direction === "in" ? " · incoming" : " · outgoing"}</span>}
          </span>{" "}
          · <span className={late ? "font-semibold text-danger" : ""}>{when}</span>
          {a.durationMinutes ? <> · {a.durationMinutes} min</> : null}
          {!hide.includes("owner") && <> · {a.owner.name}</>}
        </p>
        <p className={`mt-0.5 text-ink ${done && a.isPlanned ? "text-ink-3 line-through decoration-ink-3/60" : ""}`}>{a.subject}</p>
        {a.body && <p className="mt-0.5 whitespace-pre-line text-meta text-ink-2">{a.body}</p>}
        {(a.products?.length ?? 0) > 0 && !done && <p className="mt-0.5 text-meta text-ink-2">To discuss: {a.products!.map((p) => p.name).join(", ")}</p>}
        {a.outcome && <p className="mt-0.5 whitespace-pre-line text-meta text-ink-2">Outcome: {a.outcome}</p>}
        {(a.discussed?.length ?? 0) > 0 && <p className="mt-0.5 text-meta text-ink-2">Discussed: {a.discussed!.map((p) => p.name).join(", ")}</p>}
        {(a.alsoOn?.length ?? 0) > 0 && (
          <p className="mt-0.5 text-meta text-ink-3">
            Also on:{" "}
            {a.alsoOn!.map((c, n) => (
              <span key={c.id}>
                {n > 0 && ", "}
                <Link href={`/companies/${c.id}`} className="text-ink hover:underline">
                  {c.name}
                </Link>
              </span>
            ))}
          </p>
        )}
        {isCall && <CallOutcome open={asking} planned={a.products ?? []} onCancel={() => setAsking(false)} onSave={finish} saving={saving} />}
        {(a.company && !hide.includes("company")) || (a.contact && !hide.includes("contact")) ? (
          <p className="mt-0.5 text-meta">
            {a.contact && !hide.includes("contact") && (
              <Link href={`/contacts/${a.contact.id}`} className="text-ink hover:underline">
                {a.contact.name}
              </Link>
            )}
            {a.contact && !hide.includes("contact") && a.company && !hide.includes("company") && <span className="text-ink-3"> at </span>}
            {a.company && !hide.includes("company") && (
              <Link href={`/companies/${a.company.id}`} className="text-ink hover:underline">
                {a.company.name}
              </Link>
            )}
          </p>
        ) : null}
      </div>
      {a.can.delete && (
        <ConfirmButton
          label={<span className="sr-only">Delete this {kind.label.toLowerCase()}</span>}
          icon={<Trash2 className="size-4" aria-hidden />}
          triggerVariant="quiet"
          triggerSize="sm"
          triggerClassName="!px-2 !text-ink-3 hover:!text-danger"
          title={`Delete this ${kind.label.toLowerCase()}?`}
          body="It's removed for everyone. This can't be undone."
          confirmLabel="Delete"
          onConfirm={async () => {
            const result = await deleteActivity(a.id);
            if (!result.ok) {
              toast.error(result.error);
              return false;
            }
            toast.success("Deleted");
          }}
        />
      )}
    </li>
  );
}

/** When something planned is due: "Today, 2:00 PM", "Tomorrow, 9:00 AM", "3 days late", "Thu, Sep 26". */
function due(iso: string, fmt: ReturnType<typeof makeFormat>): string {
  const at = new Date(iso);
  const day = fmt.on({ year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(at);
  const key = `${day.find((p) => p.type === "year")?.value}-${day.find((p) => p.type === "month")?.value}-${day.find((p) => p.type === "day")?.value}`;
  const label = fmt.dueLabel(key);
  const time = fmt.on({ hour: "numeric", minute: "2-digit" }).format(at);
  return label === "Today" || label === "Tomorrow" || label === "Yesterday" ? `${label}, ${time}` : label;
}
