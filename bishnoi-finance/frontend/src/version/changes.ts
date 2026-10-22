// What's new in Finance, newest first, in the finance team's words. The first
// entry's number is the version the sidebar shows. Numbering (decided 2026-10-22):
// everything done on 22 October 2026 is 0.4.0; from then on, each change raises
// the last number only (0.4.1, 0.4.2, ...). Finance's own file: no other app reads it.

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
      "The Overview shows what your role's work calls for: what's waiting for you, receivables, sales invoiced in the Hub, marketing spending by team, the journal, tax and setup, and balances. Ms. Malou's and Sir Rommel's roles first; the Administrator, Finance Staff and Auditor keep the Overview as it was.",
      "Prices waiting for approval fill in a moment after the page opens, so a slow CRM never holds up the Overview.",
      "Figures that count only invoices issued in the Hub say so.",
      "BIR sales DAT: the monthly Summary List of Sales from Oojeema's exports, with the corrections Sir Rommel confirmed and a check against the Income Statement. It replaces the converter page and gives the same files. Only a role allowed to prepare BIR files sees it.",
      "Ready for Getmeds Philippines too: the page asks for its RDO and year-end month until they are set.",
      "The Overview for a role that releases cash advances and settles refunds and reimbursements (Ms. Cristal's) shows how many are waiting for each, with a link to the list.",
      "Journal entries typed by hand, and reversals, wait for approval and count in the books only once someone else approves them. Nobody approves their own; a rejection says why. Entries from marketing requests and invoices count at once, as before.",
      "If two people decide the same entry at nearly the same moment, the first decision stands and the other person is told who decided and when.",
      "A bell at the top right: entries waiting for your approval, decisions on your entries, cash advances to release, liquidations to review, and refunds and reimbursements to settle.",
      "The Overview shows journal entries waiting for your approval, and your own still waiting on someone else.",
      "Quieter notifications: once someone acts on something, it leaves everyone's bell; several of a kind show as one line; the red number counts only what needs you.",
      "The Finance Head is told first of entries waiting; the Finance Deputy is told of the Head's own entries, and of any still waiting after a working day (Monday to Saturday, not counting Philippine holidays).",
      "Approve several journal entries at once: tick them and choose Approve selected. Any someone else had just decided are named.",
      "An entry whose reversal still waits for approval says so, instead of \"Reversed\". The journal form explains that a line is either a debit or a credit.",
      "A calendar, switched on per person by an Administrator: your deadlines, cut-offs and monthly tasks, repeating if you like, with reminders in the bell and a \"Coming up\" section on the Overview. Your events are yours unless you share them. Philippine holidays and liquidations falling due show on it too.",
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
