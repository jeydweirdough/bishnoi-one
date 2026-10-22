/* Preparing a month's Sales DAT: the converter's own steps (converter.html: loadReports,
   take, selectMonth, recMonth, recYear, defaultRole, irSource, runCore), followed line by line
   but with the settings passed in instead of read off its page. tests/bir-sales-dat.test.mjs
   runs these and the original on the same files and requires the same results. */

import {
  C, LISTING_LABEL, MON, addressBook, buildCorrectedDAT, checkDAT, classify, correctListing, entryMonth, fmt, irChecks, isFigures,
  listingFromSR, mergeGLAccounts, parseCSV, parseDATListing, parseGL, parseIS, parseSJ, parseSRGrid, readXlsx, reconcile, sjSales, tinChecks,
} from "./engine";

/** What a GL account is used for (the converter's step "What each General Ledger account is used for"). */
export type Role = "sales" | "fee" | "discount" | "deferred" | "ignore";
export const ROLE_LABEL: [Role, string][] = [
  ["sales", "Sales — compare with the Sales Journal"],
  ["fee", "Packaging fees"],
  ["discount", "Sales discounts"],
  ["deferred", "Deferred sales"],
  ["ignore", "Not used"],
];

/* The engine's records are untyped (it is kept exactly as written): the screen reads them through these names. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Any = any;

/** Everything loaded so far: Sales Journals and Sales Reliefs per month (year*100+month), the GL exports, the Income Statement, an Oojeema DAT. */
export type Loaded = {
  sjAll: Record<number, Any>;
  srAll: Record<number, { raw: Any; list: Any }>;
  glParts: Record<string, Any>;
  gl: Any | null;
  is: Any | null;
  dat: Any | null;
  datText: string | null;
  notes: string[];
};

export function emptyLoaded(): Loaded {
  return { sjAll: {}, srAll: {}, glParts: {}, gl: null, is: null, dat: null, datText: null, notes: [] };
}

/** A file as the browser (or a test) hands it over. */
export type InputFile = { name: string; arrayBuffer: () => Promise<ArrayBuffer> };

function take(L: Loaded, k: Any, grid: Any, from: string) {
  if (k.kind === "sj") {
    const p = parseSJ(grid, k.h, from);
    L.sjAll[sjMonthKey(p)] = p;
  } else if (k.kind === "gl") {
    /* several GL exports (Sale of Goods, Packaging Charges, discounts, Deferred Sales) are combined;
       loading the same file again replaces its earlier copy */
    L.glParts[from] = parseGL(grid, k.h, from);
    const ps = Object.keys(L.glParts).map((f) => L.glParts[f]);
    L.gl = {
      from: ps.map((p) => p.from).join(" + "),
      entries: ([] as Any[]).concat(...ps.map((p) => p.entries)),
      issues: ([] as Any[]).concat(...ps.map((p) => p.issues)),
      accounts: mergeGLAccounts(ps),
    };
  } else if (k.kind === "sr") {
    const raw = parseSRGrid(grid, from), list = listingFromSR(raw);
    L.srAll[(list.year || 0) * 100 + (list.month || 0)] = { raw, list };
  } else if (k.kind === "is") L.is = parseIS(grid, k.h, from);
}

/** Reads Oojeema's exports into `into` (a copy is returned): the converter's loadReports, without its page. */
export async function readFiles(files: InputFile[], into: Loaded = emptyLoaded()): Promise<Loaded> {
  const L: Loaded = { ...into, sjAll: { ...into.sjAll }, srAll: { ...into.srAll }, glParts: { ...into.glParts }, notes: [...into.notes] };
  const notes: string[] = [];
  const decode = (b: ArrayBuffer) => new TextDecoder("utf-8").decode(b);
  await Promise.all(
    files.map(async (file) => {
      const name = file.name, low = name.toLowerCase();
      if (/\.xlsx$/.test(low)) {
        const sheets = await readXlsx(await file.arrayBuffer());
        let found = 0;
        sheets.forEach((s: Any) => {
          const k = classify(s.grid);
          if (k) {
            found++;
            take(L, k, s.grid, name + " › " + s.name);
          }
        });
        if (!found) notes.push(name + ": no Sales Journal, GL, Sales Relief or Income Statement sheet recognised");
        return;
      }
      if (/\.xls$/.test(low)) {
        notes.push(name + ": old .xls format — save it as .xlsx or CSV in Excel first");
        return;
      }
      const t = decode(await file.arrayBuffer()).replace(/^﻿/, "");
      if (/^H,S,/.test(t)) {
        L.dat = parseDATListing(t, name);
        L.datText = t;
        return;
      }
      const grid = parseCSV(t), k = classify(grid);
      if (k) take(L, k, grid, name);
      else notes.push(name + ": not recognised as a Sales Journal, GL, Sales Relief, Income Statement or sales DAT");
    }),
  );
  L.notes = L.notes.concat(notes);
  return L;
}

/* Sales Journals and Sales Reliefs are kept per month (year*100+month); the month being prepared is chosen,
   and the other months are used to find invoices whose sale is recognised or adjusted in that month */
function sjMonthKey(p: Any): number {
  const n: Record<number, number> = {};
  let best = 0;
  p.lines.forEach((l: Any) => {
    const m = entryMonth(l.date);
    if (m.mon) {
      const k = m.yr * 100 + m.mon;
      n[k] = (n[k] || 0) + 1;
      if (!best || n[k] > n[best]) best = k;
    }
  });
  return best;
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
export const monthLabel = (k: number | null) => (k ? cap(MON[(k % 100) - 1]) + " " + Math.floor(k / 100) : "?");
const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
export const monthName = (k: number | null) => (k ? MONTH_NAMES[(k % 100) - 1] + " " + Math.floor(k / 100) : "?");
/* the converter's own peso(): the typed IR in a Sales Relief workbook goes through it, so it is kept */
const peso = (n: number) => n.toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Every month loaded, oldest first. */
export function months(L: Loaded): number[] {
  const ks: Record<string, 1> = {};
  Object.keys(L.sjAll).concat(Object.keys(L.srAll)).forEach((k) => (ks[k] = 1));
  return Object.keys(ks).map(Number).sort((a, b) => a - b);
}

/** The month shown first: the latest with a Sales Relief, else the latest loaded (the converter's selectMonth). */
export function defaultMonth(L: Loaded, current: number | null = null): number | null {
  const ks = months(L);
  if (current != null && ks.indexOf(current) >= 0) return current;
  const withSr = ks.filter((k) => L.srAll[k]);
  return (withSr.length ? withSr : ks).slice(-1)[0] || null;
}

/** What each GL account is used for, guessed from its name; the user can change it. */
export function defaultRole(name: string, count: number): Role {
  if (/def+er+ed/i.test(name)) return "deferred";
  if (/packag/i.test(name)) return "fee";
  if (/^(sales|sc\s*\/?\s*pwd) discount/i.test(name)) return "discount"; /* SC/PWD: same treatment as sales discounts */
  if (/discount|return/i.test(name)) return "ignore";
  if (/sale/i.test(name) || count === 1) return "sales";
  return "ignore";
}

/** Each loaded GL account's role: the ones already set are kept, new ones are guessed (the converter's afterLoad). */
export function withDefaultRoles(L: Loaded, roles: Record<string, Role>): Record<string, Role> {
  const names = L.gl ? Object.keys(L.gl.accounts) : [];
  const out = { ...roles };
  names.forEach((n) => {
    if (!out[n]) out[n] = defaultRole(n, names.length);
  });
  return out;
}

/** Does this GL account's export cover month k? (an export without a "Date :" range is taken to cover every month) */
export function glCovers(L: Loaded, name: string, k: number): boolean {
  const a = L.gl && L.gl.accounts[name];
  return !a || !a.periods || a.periods.some((p: Any) => p.a <= k && k <= p.b);
}

/** The month's records, as the converter's selectMonth sets them. */
function picked(L: Loaded, month: number | null) {
  const s = month != null ? L.srAll[month] : null;
  return { sj: (month != null && L.sjAll[month]) || null, sr: s ? s.raw : null, srList: s ? s.list : null };
}

function recMonth(L: Loaded, p: ReturnType<typeof picked>): number | null {
  if (p.srList && p.srList.month) return p.srList.month;
  if (L.dat && L.dat.month) return L.dat.month;
  const d = p.sj && p.sj.lines.length && /^([A-Z][a-z]{2})/.exec(p.sj.lines[0].date);
  return d ? MON.indexOf(d[1].toLowerCase()) + 1 : null;
}

function recYear(L: Loaded, p: ReturnType<typeof picked>): number | null {
  if (p.srList && p.srList.year) return p.srList.year;
  if (L.dat && L.dat.year) return L.dat.year;
  const d = p.sj && p.sj.lines.length && /(\d{4})$/.exec(p.sj.lines[0].date);
  return d ? +d[1] : null;
}

/** The IR for the month: the Income Statement's Total Revenue, else a figure typed in the Sales Relief workbook. */
function irSource(L: Loaded, p: ReturnType<typeof picked>) {
  const mon = recMonth(L, p), figs = L.is && mon ? isFigures(L.is, mon) : null;
  if (figs && figs.total && figs.total.value != null) return { value: figs.total.value, figs, note: "Total Revenue from " + L.is.from + ", row " + figs.total.row };
  if (p.sr && p.sr.taxpayer.ir) return { value: C(peso(p.sr.taxpayer.ir.value)), figs, note: 'Typed "Income Statement" figure in ' + p.sr.from + ", row " + p.sr.taxpayer.ir.row };
  return { value: null, figs, note: "" };
}

/** The settings a month is prepared with (the converter's Settings fold, and its step-4 choices). */
export type Options = {
  roles: Record<string, Role>;
  rdo: string;
  fyMonth: number | string;
  perCustomer: boolean;
  /** An IR typed by hand, in centavos; null to use the Income Statement's. */
  typedIr?: number | null;
  /** How each sales adjustment JV is reported: {"<GL file>#<row>": "vatable" | "exempt" | "zero"}. */
  adjClass?: Record<string, string>;
};

/** Everything for one month (the converter's runCore): reconciliation, corrections, the DAT, and whether it's ready to file. */
export function prepareMonth(L: Loaded, month: number | null, opt: Options): Any {
  const p = picked(L, month);
  const o: Any = { issues: [] }, src = irSource(L, p);
  o.isFigs = src.figs || null;
  o.irNote = src.note;
  const typed = opt.typedIr != null ? opt.typedIr : null;
  o.irC = typed != null ? typed : src.value;
  o.irTyped = typed != null;
  o.sj = p.sj;
  o.srList = p.srList;
  if (!p.sj) return o;
  const issues = o.issues;
  p.sj.issues.forEach((i: Any) => issues.push(Object.assign({ report: "Sales Journal" }, i)));
  if (L.gl) L.gl.issues.forEach((i: Any) => issues.push(Object.assign({ report: "General Ledger" }, i)));
  if (p.sr && p.sr.total) {
    const srT: Any = { exempt: 0, zero: 0, taxable: 0, vat: 0 };
    p.sr.rows.forEach((r: Any) => {
      srT.exempt += r.exempt;
      srT.zero += r.zero;
      srT.taxable += r.taxable;
      srT.vat += r.vat;
    });
    ["exempt", "zero", "taxable", "vat"].forEach((k) => {
      if (C(srT[k]) !== C(p.sr.total[k]))
        issues.push({ report: "Sales Relief", where: p.sr.from, name: "TOTAL row", msg: k + ": rows add to " + fmt(C(srT[k])) + " but the TOTAL row says " + fmt(C(p.sr.total[k])) });
    });
  }
  if (L.dat) {
    const fname = L.dat.from;
    checkDAT(L.datText, fname.replace(/ \(\d+\)(?=\.DAT$)/i, ""), null).forEach((k: Any) => {
      if (!k.ok) issues.push({ report: "DAT", where: fname, name: "", msg: "Check failed: " + k.label });
    });
    if (/ \(\d+\)\.DAT$/i.test(fname)) issues.push({ report: "DAT", where: fname, name: "", msg: "File name has a browser copy number — rename to " + fname.replace(/ \(\d+\)(?=\.DAT$)/i, "") + " before submitting" });
    if (!L.dat.header) issues.push({ report: "DAT", where: fname, name: "", msg: "No header (H) line" });
  }
  const roleSet = (r: Role) => new Set(Object.keys(opt.roles).filter((n) => opt.roles[n] === r));
  o.res = reconcile({
    sj: p.sj, gl: L.gl, accounts: L.gl ? roleSet("sales") : null, feeAccounts: L.gl ? roleSet("fee") : null,
    discAccounts: L.gl ? roleSet("discount") : null, defAccounts: L.gl ? roleSet("deferred") : null,
    sr: p.srList || null, dat: L.dat, ir: o.irC, month: recMonth(L, p), year: recYear(L, p),
    others: Object.keys(L.sjAll).map(Number).filter((k) => k !== month).map((k) => ({ key: k, label: monthLabel(k), sj: L.sjAll[k], sr: L.srAll[k] ? L.srAll[k].list : null })),
  });
  (o.res.unlinkedDisc || []).forEach((e: Any) =>
    issues.push({ report: "General Ledger", where: e.from + " row " + e.row, name: e.name, msg: "Sales Discount entry without an invoice number (" + fmt(e.dr - e.cr) + ")" }));
  o.irChecks = o.isFigs ? irChecks(o.res, o.isFigs) : [];
  o.irChecks.filter((c: Any) => !c.ok).forEach((c: Any) => issues.push({ report: "Income Statement", where: L.is.from, name: c.label, msg: c.msg }));
  (o.res.unlinkedFee || []).forEach((e: Any) =>
    issues.push({ report: "General Ledger", where: e.from + " row " + e.row, name: e.name, msg: "Packaging-fee entry without an invoice number (" + fmt(e.cr - e.dr) + ")" }));
  tinChecks(o.res).forEach((i: Any) => issues.push(i));
  /* corrected DAT: built from the Sales Relief if loaded, otherwise from the loaded DAT */
  o.corKey = p.srList ? "sr" : L.dat && L.dat.month === recMonth(L, p) ? "dat" : null;
  o.cor = o.corKey ? correctListing(o.res, o.corKey, { adjClass: opt.adjClass || {} }) : null;
  if (o.cor) {
    o.L = o.corKey === "sr" ? p.srList : L.dat;
    try {
      o.fixOut = buildCorrectedDAT(o.cor, {
        taxpayer: o.L.taxpayer, month: o.L.month, year: o.L.year,
        book: L.datText ? addressBook(L.datText) : null, rdo: String(opt.rdo).trim() || "53A", fy: opt.fyMonth, perCustomer: opt.perCustomer,
      });
    } catch (err) {
      o.err = (err as Error).message;
    }
  }
  o.diff = o.cor && o.irC != null ? o.cor.totals.net - o.irC : null;
  o.items = o.cor ? o.cor.pending.length + o.cor.open.length : 0;
  o.ready = !!(o.fixOut && !o.items && o.diff === 0);
  return o;
}

/** What explains the gap between the IR and the corrected DAT, when the loaded files account for all of it
 *  (the converter's irExplain, for a month prepared by prepareMonth). Empty when they don't. */
export type GapPart = { s: string; t: string; v: number };
export function explainGap(o: Any): { short?: string; parts?: GapPart[]; text?: string } {
  const d = o.cor && o.irC != null ? o.irC - o.cor.totals.net : null;
  if (d == null || d === 0 || !o.isFigs || o.irTyped) return {};
  const F = o.isFigs, fl = F.deferred && F.deferred.label, res = o.res, parts: GapPart[] = [];
  (res.deferred || []).forEach((x: Any) => {
    if (!x.applied) parts.push({ s: "Deferred Sales not moved", t: "Deferred Sales not moved — " + (x.e.voucher || "entry") + " " + (x.sis.join(", ") || ""), v: -x.amt });
  });
  (F.revenue || []).forEach((f: Any) => {
    if (!f.value || /discount/i.test(f.label)) return;
    if (f.label === fl) {
      if (!res.deferred) parts.push({ s: "Deferred Sales on the IR", t: "Deferred Sales on the Income Statement — add the Deferred Sales GL to see which invoices", v: f.value });
      return;
    }
    parts.push({ s: f.label + " on the IR", t: f.label + " on the Income Statement — no rule for it yet", v: f.value });
  });
  /* items left as reported whose amount the IR has and the DAT does not (Non-VAT sales; invoices the GL never credited) */
  const oe: Record<string, number> = {};
  (o.cor ? o.cor.open : []).forEach((x: Any) => {
    if (!x.irEffect) return;
    const k = /Non-VAT/.test(x.msg) ? "Non-VAT sales not in the " + (LISTING_LABEL as Record<string, string>)[o.corKey] : "Invoices not in the Sale of Goods GL";
    oe[k] = (oe[k] || 0) + x.irEffect;
  });
  Object.keys(oe).forEach((k) => parts.push({ s: k, t: k, v: oe[k] }));
  /* with the Sale of Goods GL loaded the corrected DAT follows the GL, so a gap is the Income Statement not matching the GL */
  if (F.sales && F.sales.value != null && res.totals.gl) {
    const gg = F.sales.value - res.totals.gl.net;
    if (gg)
      parts.push({
        s: "Income Statement ≠ Sale of Goods GL",
        t: "the Income Statement's Sale of Goods not matching the Sale of Goods GL (IS " + fmt(F.sales.value) + " vs GL " + fmt(res.totals.gl.net) +
          "). If the GL was exported after the Income Statement, entries posted in between are missing from it — export the Income Statement again",
        v: gg,
      });
  } else if (F.sales && F.sales.value != null && res.totals.sj) {
    const g = F.sales.value - sjSales(res);
    if (g)
      parts.push({
        s: "Sale of Goods not in the Sales Journal",
        t: "Sale of Goods on the Income Statement that is not in the Sales Journal (IS " + fmt(F.sales.value) + " vs Sales Journal " + fmt(sjSales(res)) +
          ") — add this month's Sale of Goods GL to see the entries",
        v: g,
      });
  }
  if (!parts.length || d !== parts.reduce((a, p) => a + p.v, 0)) return {};
  return { short: parts.map((p) => p.s).join(" + "), parts, text: "Equals " + parts.map((p) => p.t + " (" + fmt(p.v) + ")").join(" + ") };
}

/** The TINs Oojeema's files give, to write full TINs (with branch code) in the Sales Relief CSV (the converter's fixTins). */
export function tinsFor(o: Any): string[] {
  return ([] as string[]).concat(
    o.srList ? o.srList.rows.map((r: Any) => r.tin) : [],
    o.sj ? o.sj.lines.map((l: Any) => l.tin) : [],
    o.srList && o.srList.taxpayer ? [o.srList.taxpayer.tin] : [],
  );
}

/** A month's status for its button: ready, off by an amount, items to check (the converter's summary). */
export type Status = { ready: boolean; diff: number | null; items: number; noSj: boolean; noList: boolean; noIr: boolean; err?: string };
export function statusOf(o: Any): Status {
  return { ready: o.ready, diff: o.diff ?? null, items: o.items ?? 0, noSj: !o.sj, noList: !o.cor, noIr: o.irC == null, err: o.err };
}
