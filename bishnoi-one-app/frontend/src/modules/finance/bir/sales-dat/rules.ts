// The corrections the Sales DAT applies, as Sir Rommel confirmed them (he reviewed
// September 2026's files case by case, 15 to 19 October 2026). The engine (engine.ts)
// is what applies them; this is the record the screen shows under "Rules in use".
// A new or changed ruling: confirm it with Sir Rommel, change the engine, run the
// tests (tests/bir-sales-dat.test.mjs), and add it here with its date.

export type Rule = { title: string; detail: string; confirmed: string };

export const CONFIRMED_BY = "Sir Rommel";

export const RULES: Rule[] = [
  {
    title: "Issued and cancelled in the same month",
    detail: "Both rows are left out: they add to nothing. An invoice from an earlier month cancelled this month stays as a minus amount.",
    confirmed: "October 2026",
  },
  {
    title: "Discounts",
    detail: "Sales are reported after discount. Senior citizen and PWD discounts the same way.",
    confirmed: "17 October 2026 (SC/PWD)",
  },
  {
    title: "Packaging fees",
    detail:
      "Left out of the listing. A fee on its own VATable line stays as VATable sales with its VAT, and the same amount is taken off Exempt, so the listing agrees with the Income Statement.",
    confirmed: "15 October 2026",
  },
  {
    title: "Deferred sales (GL 4400)",
    detail: "Reported in the month the sale is recognised, with its VAT: left out of the month invoiced, added in the month the deferral is reversed.",
    confirmed: "17 October 2026",
  },
  {
    title: "Sales adjustment JVs",
    detail:
      "A JV on Sale of Goods that names an invoice in its description is added under that invoice's customer, in the JV's month, as VATable sales with 12% output VAT, unless you choose Exempt or Zero-rated for it.",
    confirmed: "19 October 2026",
  },
  {
    title: "One line per customer",
    detail: "All of a customer's invoices for the month are added into one line, by TIN (by name when there is no TIN). A customer whose rows add to zero is left out and listed.",
    confirmed: "17 October 2026",
  },
  {
    title: "Customer names",
    detail:
      "Capital letters; & becomes AND; periods and hyphens become spaces; apostrophes and commas are removed; Ñ becomes N. No exceptions list: the TIN is what must be right.",
    confirmed: "15 October 2026",
  },
  {
    title: "Rounding",
    detail: "A difference of 5 centavos or less between output VAT and 12% of VATable sales is rounding.",
    confirmed: "October 2026",
  },
];

/** Anything no rule covers is left exactly as Oojeema reports it, and listed for review. */
export const OTHERWISE = "Anything else is left exactly as Oojeema reports it, and listed so it can be decided before filing.";
