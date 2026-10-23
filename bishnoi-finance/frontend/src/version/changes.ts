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
    version: "0.4.11",
    date: "2026-10-23",
    changes: [
      "Price approvals shows in the sidebar only for a role with Product prices: View; opened anyway, it says the role doesn't allow it instead of an error page.",
    ],
  },
  {
    version: "0.4.10",
    date: "2026-10-23",
    changes: [
      "Payables → Suppliers: Import from a file. Pick Zoho's vendor export (CSV); every vendor is shown first as new, already here (same name or TIN), or needing a look. Tick what to import; it's added all or none.",
      "On the way in: Zoho's Company ID becomes the TIN when it is one (otherwise it's kept in the remarks), \"Net 30\" becomes 30 days, inactive vendors come in switched off, and a vendor billed in another currency gets a remark (Finance keeps pesos for now).",
      "Not brought in: what's owed each vendor (an opening balance), their VAT status and the tax usually withheld: set those on each supplier after.",
    ],
  },
  {
    version: "0.4.9",
    date: "2026-10-23",
    changes: [
      "Suppliers like Zoho's vendors: primary contact (salutation, first and last name), company name and display name, work phone and mobile, contact persons, remarks, and the supplier's papers (BIR 2303, accreditation) attached.",
      "A supplier can have its own Accounts payable (e.g. AP – Trade or AP – Non-Trade from Oojeema's chart); its bills post there instead of the default.",
      "The supplier list shows Zoho's columns, with Payables: what's owed each on recorded bills.",
      "Separate ticks on the Roles screen. Suppliers: View, Add, Edit, Switch off. Supplier bills: View, Make drafts, Record (post to the books), Void. Every role keeps what it could do before.",
      "Payables stays open in the sidebar on the Suppliers pages (Suppliers used to disappear from it there).",
    ],
  },
  {
    version: "0.4.8",
    date: "2026-10-23",
    changes: [
      "Payables → Suppliers: who the company buys from, with their TIN, whether they charge VAT, payment terms, bank details and the tax usually withheld from them (BIR code and rate).",
      "Payables → Bills: enter a supplier's invoice the way Zoho's New Bill reads. Picking the supplier fills in their terms, VAT and usual withholding; the VAT and the tax withheld are worked out (withheld on the amount before VAT), down to what's paid the supplier.",
      "Tick \"checked against the PO\" and \"against the delivery receipt\", and keep the same bill's Zoho and Oojeema numbers on it while all three are used.",
      "Attach the supplier's invoice as a photo or PDF (photos are made smaller first). A bill without one shows \"Document missing\", and the list can show only those.",
      "Recording a bill posts it to the books at once: the expense and input VAT, against what's owed the supplier and the tax withheld. A recorded bill is voided with a reason, never changed. The same invoice from a supplier can't be entered twice.",
      "Making bills is one tick on the Roles screen (Supplier bills: Make and record), so any role can have it on or off.",
    ],
  },
  {
    version: "0.4.7",
    date: "2026-10-23",
    changes: [
      "Chart of accounts: Import from a file. Pick the CSV (Oojeema's or Zoho's export); every row is shown first as new, already here, or needing a look, with its type worked out from the class. Tick what to import; it's added all or none, and nothing already here changes.",
      "Accounts can sit under a parent account, as in Oojeema's chart, and are shown indented under it.",
    ],
  },
  {
    version: "0.4.6",
    date: "2026-10-22",
    changes: [
      "Tax, Registration: an \"On record\" summary of the registration as every invoice will print it, with who changed it last, and a History of changes (who, when and which parts; never the old values).",
      "Saving the registration without changing anything says \"Nothing changed\" and adds nothing to the history.",
      "BIR Sales DAT: its check against Sir Rommel's converter runs again (it had stopped loading; the screen itself was fine).",
    ],
  },
  {
    version: "0.4.5",
    date: "2026-10-22",
    changes: [
      "Tax registration: the page names exactly what an invoice still needs (e.g. \"The company's registered address isn't filled in yet\"), marks that box, and saving says \"Still missing: …\" instead of only \"saved\".",
      "A draft invoice held up by the registration says what's missing, with a link to Tax, Registration.",
    ],
  },
  {
    version: "0.4.4",
    date: "2026-10-22",
    changes: [
      "A draft invoice that can't be issued yet says exactly what's wrong and where (e.g. \"Customer's TIN: enter it as 9 digits…\", \"Line 2: pick the VAT category\"), on the invoice and beside the field when you edit it, instead of \"Some lines need fixing\".",
      "TINs: type the digits only; the dashes go in by themselves.",
      "The \"Find a customer in the CRM\" box says it only searches the CRM and isn't saved, and says so there when the CRM can't be reached.",
    ],
  },
  {
    version: "0.4.3",
    date: "2026-10-22",
    changes: [
      "Cancel and reissue an invoice in one step: it's voided as before, and a copy opens as a draft dated today to correct and issue with the next number. Both invoices show they're linked (on screen, in the list and in the journal); the printed invoice stays as standard.",
    ],
  },
  {
    version: "0.4.2",
    date: "2026-10-22",
    changes: [
      "The sidebar no longer warns that the screens and the API are on different builds on a developer's computer, where that happens with nothing wrong. Once deployed, it still warns when an update reached only one of them.",
    ],
  },
  {
    version: "0.4.1",
    date: "2026-10-22",
    changes: [
      "E-signatures: set yours on your account page, drawn or uploaded (a photo on white paper is cleaned on your computer: the paper made transparent, the ink black). Finance places it on what you prepare, approve, review or settle, with your name, the date and a reference.",
      "Journal vouchers and liquidation reports to print or save as PDF, with Prepared by / Approved by and Reviewed by / Settled by signed.",
    ],
  },
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
