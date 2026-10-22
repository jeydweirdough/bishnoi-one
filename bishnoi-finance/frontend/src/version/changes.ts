// What's new in Finance, newest first, in the finance team's words. The first
// entry's number is the version the sidebar shows: add an entry (and raise the
// number) with each change that ships. Finance's own file: no other app reads it.

export type Release = {
  version: string;
  /** YYYY-MM-DD; null for the starting point, whose date isn't one day. */
  date: string | null;
  changes: string[];
};

export const RELEASES: Release[] = [
  {
    version: "0.4.0",
    date: "2026-10-22",
    changes: [
      "BIR sales DAT: the monthly Summary List of Sales from Oojeema's exports, with the corrections Sir Rommel confirmed and a check against the Income Statement. It replaces the converter page and gives the same files. Only a role allowed to prepare BIR files sees it.",
      "Ready for Getmeds Philippines too: the page asks for its RDO and year-end month until they are set.",
    ],
  },
  {
    version: "0.3.0",
    date: "2026-10-22",
    changes: [
      "The Overview shows what your role's work calls for: what's waiting for you, receivables, sales invoiced in the Hub, marketing spending by team, the journal, tax and setup, and balances. Ms. Malou's and Sir Rommel's roles first; the Administrator, Finance Staff and Auditor keep the Overview as it was.",
      "Prices waiting for approval fill in a moment after the page opens, so a slow CRM never holds up the Overview.",
      "Figures that count only invoices issued in the Hub say so.",
    ],
  },
  {
    version: "0.2.1",
    date: "2026-10-20",
    changes: [
      "Finance tells the CRM which company it works for (2MG), so the customer list and price approvals keep working once Finance is live. If that isn't set up, Finance says so plainly.",
    ],
  },
  {
    version: "0.2.0",
    date: "2026-10-20",
    changes: [
      "Whoever releases a cash advance can't review its liquidation: someone else does.",
      "An employee's next cash advance waits until their last one is liquidated. The request says which one they still owe.",
      "When the CRM refuses a request, Finance says so and that trying again won't help, instead of \"try again in a minute\".",
      "The version and what's new, at the bottom of the sidebar.",
    ],
  },
  {
    version: "0.1.1",
    date: "2026-10-05",
    changes: [
      "Search on the journal and the marketing request lists, and CSV downloads of them, the trial balance and each account's ledger.",
      "A download needs the same permission as its screen.",
      "A guide for the finance team.",
    ],
  },
  {
    version: "0.1.0",
    date: null,
    changes: [
      "The starting point: marketing requests (release, liquidation review, refunds and reimbursements), the journal and chart of accounts, sales invoices and payments, receivables aging, tax setup, price approvals for the CRM, and roles.",
    ],
  },
];

export const VERSION = RELEASES[0].version;
