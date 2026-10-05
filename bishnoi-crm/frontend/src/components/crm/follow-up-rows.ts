import type { FollowUpRow } from "../follow-up-item";
import type { ActivityItem, Bucket } from "@/src/platform/lib/types";

// Follow-ups are tasks. These turn a task into the row the follow-up screens
// have always drawn, so those screens keep working as they were.

/** The calendar day (YYYY-MM-DD) a moment falls on, where the company is. */
export function dayOf(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(iso));
}

export function bucketOf(dueOn: string, today: string): Bucket {
  return dueOn < today ? "overdue" : dueOn === today ? "today" : "upcoming";
}

/** Where a task's customer is: the contact if it names one, else the company. */
export function customerOf(a: ActivityItem): { name: string | null; href: string | null } {
  if (a.contact) return { name: a.company ? `${a.contact.name}, ${a.company.name}` : a.contact.name, href: `/contacts/${a.contact.id}` };
  if (a.company) return { name: a.company.name, href: `/companies/${a.company.id}` };
  return { name: null, href: null };
}

export function followUpRow(a: ActivityItem, today: string, timeZone: string, extra: Partial<FollowUpRow> = {}): FollowUpRow {
  const dueOn = dayOf(a.at, timeZone);
  const customer = customerOf(a);
  return {
    id: a.id,
    title: a.subject,
    dueOn,
    bucket: a.isDone ? null : bucketOf(dueOn, today),
    status: a.isDone ? "done" : "open",
    customerId: a.company?.id ?? a.contact?.id ?? "",
    customerName: customer.name,
    href: customer.href ?? undefined,
    doneAt: a.doneAt,
    canEdit: a.can.edit,
    ...extra,
  };
}
