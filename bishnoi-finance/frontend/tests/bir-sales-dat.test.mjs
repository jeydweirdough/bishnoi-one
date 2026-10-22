// The Sales DAT screen must give exactly what Sir Rommel's converter gives.
//
// For each set of real Oojeema exports in the converter's "Test Files" folder, this
// runs the original converter.html (its own code, in a sandbox) and Finance's
// src/bir/sales-dat, and requires the same DAT byte for byte, the same corrections,
// open items, checks and totals, and the same Excel report, month by month.
//
// The files hold real customers and amounts, so they stay on this computer, outside
// the repo: set BIR_CONVERTER_DIR to the converter's folder (default: the sibling
// folder "BIR DAT Converter"). Without it, these tests are skipped.
//
// Run:  node --test tests/        (from bishnoi-finance/frontend; Node 24+, nothing to install)

import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

import * as engine from "../src/bir/sales-dat/engine.ts";
import { readFiles, emptyLoaded, months, withDefaultRoles, prepareMonth, explainGap } from "../src/bir/sales-dat/prepare.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
const DIR = process.env.BIR_CONVERTER_DIR || path.resolve(here, "../../../../BIR DAT Converter");
const HAVE = fs.existsSync(path.join(DIR, "converter.html")) && fs.existsSync(path.join(DIR, "Test Files"));
const FILES = path.join(DIR, "Test Files");

/** The original converter's code, run in a sandbox with just enough of a page for it to load. */
function original() {
  const html = fs.readFileSync(path.join(DIR, "converter.html"), "utf8");
  const script = html.slice(html.indexOf("<script>") + "<script>".length, html.lastIndexOf("</script>"));
  const stub = () =>
    new Proxy(function () {}, {
      get(t, k) {
        if (k === Symbol.toPrimitive) return () => "";
        if (k === "length") return 0;
        return stub();
      },
      apply: () => stub(),
      set: () => true,
    });
  // The settings runCore reads off the page, at the page's own defaults; anything else
  // asked of these fields (listeners, styles) is a no-op.
  const fields = { rRdo: { value: "53A" }, rFy: { value: "12" }, rPerCust: { checked: true }, fIr: { value: "" } };
  const element = (f) => new Proxy(f, { get: (t, k) => (k in t ? t[k] : stub()), set: (t, k, v) => ((t[k] = v), true) });
  const ctx = vm.createContext({
    document: { getElementById: (id) => (fields[id] ? element(fields[id]) : stub()) },
    window: stub(),
    navigator: stub(),
    localStorage: { getItem: () => null, setItem() {} },
    alert() {},
    confirm: () => true,
    console,
    setTimeout,
    TextDecoder,
    TextEncoder,
    Blob,
    Response,
    DecompressionStream,
    URL,
  });
  vm.runInContext(script, ctx, { filename: "converter.html" });
  return { ctx, fields };
}

const bytesOf = (file) => {
  const b = fs.readFileSync(file);
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
};

/** Loads the files into the original, in the given order, as its loadReports would, then prepares every month. */
async function runOriginal(files) {
  const { ctx, fields } = original();
  for (const file of files) {
    const name = path.basename(file);
    if (/\.xlsx$/i.test(name)) {
      const sheets = await ctx.readXlsx(bytesOf(file));
      sheets.forEach((s) => {
        const k = ctx.classify(s.grid);
        if (k) ctx.take(k, s.grid, name + " › " + s.name);
      });
      continue;
    }
    const t = new TextDecoder("utf-8").decode(bytesOf(file)).replace(/^﻿/, "");
    if (/^H,S,/.test(t)) {
      ctx.R.dat = ctx.parseDATListing(t, name);
      ctx.R.datText = t;
      continue;
    }
    const grid = ctx.parseCSV(t), k = ctx.classify(grid);
    if (k) ctx.take(k, grid, name);
  }
  // afterLoad, without its page: the month, the GL roles, and the RDO and year-end from an Oojeema DAT
  ctx.selectMonth();
  const names = ctx.R.gl ? Object.keys(ctx.R.gl.accounts) : [];
  names.forEach((n) => {
    if (!ctx.R.roles[n]) ctx.R.roles[n] = ctx.defaultRole(n, names.length);
  });
  if (ctx.R.dat && ctx.R.dat.header) {
    if (ctx.R.dat.header.rdo) fields.rRdo.value = ctx.R.dat.header.rdo;
    if (ctx.R.dat.header.fy) fields.rFy.value = ctx.R.dat.header.fy;
  }
  const out = {};
  for (const k of ctx.recMonths()) {
    ctx.R.month = k;
    ctx.selectMonth();
    const o = ctx.runCore(false);
    ctx.apply(o);
    o.gap = o.cor ? ctx.irExplain(o.irC != null ? o.irC - o.cor.totals.net : null) : {};
    out[k] = o;
  }
  return { months: ctx.recMonths(), out, rdo: fields.rRdo.value, fy: fields.rFy.value };
}

/** The same files through Finance's src/bir/sales-dat. */
async function runFinance(files) {
  let L = emptyLoaded();
  for (const file of files) L = await readFiles([{ name: path.basename(file), arrayBuffer: async () => bytesOf(file) }], L);
  const roles = withDefaultRoles(L, {});
  let rdo = "53A", fy = "12";
  if (L.dat && L.dat.header) {
    if (L.dat.header.rdo) rdo = L.dat.header.rdo;
    if (L.dat.header.fy) fy = L.dat.header.fy;
  }
  const out = {};
  for (const k of months(L)) {
    const o = prepareMonth(L, k, { roles, rdo, fyMonth: fy, perCustomer: true });
    o.gap = explainGap(o);
    out[k] = o;
  }
  return { months: months(L), out, rdo, fy };
}

/** What a month comes to, in a form two runs can be compared by. */
function summary(o, xlsx) {
  const plain = (xs) => (xs || []).map(({ si, name, where, msg, rule, column, before, after, changed, basis }) => ({ si, name, where, msg, rule, column, before, after, changed, basis }));
  return {
    dat: o.fixOut ? o.fixOut.text : null,
    filename: o.fixOut ? o.fixOut.filename : null,
    checks: o.fixOut ? o.fixOut.checks : null,
    ir: o.irC ?? null,
    diff: o.diff ?? null,
    items: o.items ?? 0,
    ready: !!o.ready,
    err: o.err ?? null,
    totals: o.cor ? o.cor.totals : null,
    corrections: plain(o.cor && o.cor.log),
    open: plain(o.cor && o.cor.open),
    issues: (o.issues || []).map(({ report, where, name, msg }) => ({ report, where, name, msg })),
    gap: o.gap || {},
    report: o.res ? Buffer.from(xlsx(o)).toString("base64") : null,
  };
}

/** The test sets: each folder as Sir Rommel would load it, and everything at once (the cross-month rules). */
function sets() {
  const list = (d) => fs.readdirSync(d).filter((f) => fs.statSync(path.join(d, f)).isFile()).sort().map((f) => path.join(d, f));
  const folders = fs.readdirSync(FILES).filter((f) => fs.statSync(path.join(FILES, f)).isDirectory()).sort();
  const top = list(FILES);
  const out = [["Test Files (top level)", top]];
  folders.forEach((f) => out.push([f, list(path.join(FILES, f))]));
  out.push(["everything", [...top, ...folders.flatMap((f) => list(path.join(FILES, f)))]]);
  return out;
}

const run = HAVE ? test : test.skip;

/* The original runs in a sandbox, whose arrays and objects are another realm's; compare plain data. */
const plain = (x) => JSON.parse(JSON.stringify(x));

run("the engine is the converter's own code", () => {
  const html = fs.readFileSync(path.join(DIR, "converter.html"));
  const ours = fs.readFileSync(path.join(here, "../src/bir/sales-dat/engine.ts"));
  // Lines 369-1417 of the converter, unchanged, inside ours.
  const lines = html.toString("binary").split("\n");
  const block = lines.slice(368, 1417).join("\n");
  assert.ok(ours.toString("binary").includes(block), "src/bir/sales-dat/engine.ts no longer holds converter.html's lines 369-1417 unchanged");
});

for (const [label, files] of HAVE ? sets() : []) {
  run(`same results as the converter: ${label}`, async () => {
    const a = await runOriginal(files);
    const b = await runFinance(files);
    assert.deepEqual(plain(b.months), plain(a.months), "the months found");
    assert.equal(b.rdo, a.rdo, "RDO code");
    assert.equal(String(b.fy), String(a.fy), "year-end month");
    const { ctx } = original();
    const xlsxA = (o) => ctx.buildXlsx(ctx.reconSheets(o.res, { issues: o.issues, cor: o.cor, fixOut: o.fixOut }));
    const xlsxB = (o) => engine.buildXlsx(engine.reconSheets(o.res, { issues: o.issues, cor: o.cor, fixOut: o.fixOut }));
    for (const k of a.months) {
      const want = plain(summary(a.out[k], xlsxA)), got = plain(summary(b.out[k], xlsxB));
      assert.ok(want.dat || want.err || !a.out[k].sj, `month ${k}: the original made no DAT, so there's nothing to compare`);
      assert.deepEqual(got, want, `month ${k}`);
    }
  });
}
