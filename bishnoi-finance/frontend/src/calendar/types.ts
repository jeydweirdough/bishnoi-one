// The calendar, as GET /finance/calendar sends it (app/routers/calendar.py).
// Switched on per person; each person's events are their own unless shared.

export type Person = { id: string; name: string };

export type Repeat = "none" | "monthly" | "quarterly" | "yearly" | "twice_monthly";
export type RemindDays = 0 | 1 | 3 | 7;

export type CalEvent = {
  id: string;
  title: string;
  notes: string | null;
  startsOn: string;
  /** "14:30"; null: all day. */
  atTime: string | null;
  repeat: Repeat;
  until: string | null;
  /** Working days before each date to remind; null: no reminder. */
  remindDays: RemindDays | null;
  /** A page inside Finance it's about. */
  link: string | null;
  owner: Person;
  /** This person added it (and so may change it). */
  mine: boolean;
  sharedWith: Person[];
};

/** One date an event falls on. */
export type CalItem = { on: string; event: CalEvent; done: { by: string; at: string } | null };

export type CalendarData = {
  from: string;
  to: string;
  today: string;
  items: CalItem[];
  holidays: { on: string; name: string }[];
  liquidations: { on: string; id: string; number: string; requester: string }[];
  people: Person[];
};

export type EventInput = {
  title: string;
  notes: string | null;
  startsOn: string;
  atTime: string | null;
  repeat: Repeat;
  until: string | null;
  remindDays: RemindDays | null;
  link: string | null;
  sharedWith: string[];
};

export const REPEATS: Record<Repeat, string> = {
  none: "Doesn't repeat",
  monthly: "Every month, same day",
  quarterly: "Every 3 months",
  yearly: "Every year",
  twice_monthly: "Twice a month (15th and last day)",
};

export const REMINDERS: [RemindDays | null, string][] = [
  [null, "No reminder"],
  [0, "On the day"],
  [1, "1 working day before"],
  [3, "3 working days before"],
  [7, "7 working days before"],
];

/** Finance pages an event can point to. */
export const PAGES: [string, string][] = [
  ["/bir/sales-dat", "BIR sales DAT"],
  ["/ledger", "Journal entries"],
  ["/ledger/trial-balance", "Trial balance"],
  ["/funds", "Marketing requests"],
  ["/funds/settlement", "Refunds and reimbursements"],
  ["/invoices", "Invoices"],
  ["/invoices/receivables", "Receivables"],
  ["/bills", "Bills"],
  ["/tax", "Tax"],
];
