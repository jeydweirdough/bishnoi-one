import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { accountSend, getAccount } from "@/src/platform/lib/account";
import { apiFor } from "@/src/platform/lib/api";
import type { ModuleKey } from "@/src/platform/lib/modules";
import { moduleCookie } from "@/src/platform/lib/session-cookie";
import { myModules } from "@/src/one/mine";
import type { ReportData } from "@/src/platform/reports/types";
import { FigureCard, FigureCardLoading, Tile, type Figure } from "@/src/platform/ui/figures";
import { Later } from "@/src/platform/ui/later";
import { PageHeader } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";

export const metadata = { title: "Home" };

// The executive Home (decided 2026-10-28, feature plan Track R): the company in a few figures, read
// from each app's own Management reports with this person's access, each linking to its report.
// The page is drawn at once; the figures arrive as each app answers.

type Search = Promise<Record<string, string | string[] | undefined>>;
const BASE = "/platform/home";
const PERIODS = [
  { value: "month", label: "This month" },
  { value: "last-month", label: "Last month" },
  { value: "quarter", label: "This quarter" },
  { value: "year", label: "This year" },
] as const;
type Period = (typeof PERIODS)[number]["value"];

/** Today in Manila, and the period's first and last day (YYYY-MM-DD). */
function span(period: Period): { from: string; to: string } {
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Manila" }).format(new Date());
  const [y, m] = today.split("-").map(Number);
  const iso = (yy: number, mm: number, dd: number) => `${yy}-${String(mm).padStart(2, "0")}-${String(dd).padStart(2, "0")}`;
  const lastDay = (yy: number, mm: number) => new Date(Date.UTC(yy, mm, 0)).getUTCDate();
  if (period === "last-month") {
    const [py, pm] = m === 1 ? [y - 1, 12] : [y, m - 1];
    return { from: iso(py, pm, 1), to: iso(py, pm, lastDay(py, pm)) };
  }
  if (period === "quarter") return { from: iso(y, Math.floor((m - 1) / 3) * 3 + 1, 1), to: today };
  if (period === "year") return { from: iso(y, 1, 1), to: today };
  return { from: iso(y, m, 1), to: today };
}

const PATHS: Partial<Record<ModuleKey, string>> = { finance: "/finance/reports", crm: "/reports" };

/** One Management report, or null when it can't be read (no access, not connected). */
async function report(module: ModuleKey, key: string, from: string, to: string): Promise<ReportData | null> {
  try {
    return await apiFor(module).get<ReportData>(`${PATHS[module]}/${key}?from=${from}&to=${to}`);
  } catch {
    return null;
  }
}

const value = (r: ReportData | null, label: string) => r?.summary?.find((f) => f.label === label || f.label.startsWith(`${label},`))?.value ?? null;
const row = (r: ReportData | null, figure: string) => r?.rows.find((x) => x.figure === figure) ?? null;
const peso = (centavos: number | null) =>
  centavos === null ? "—" : `${centavos < 0 ? "−" : ""}₱${(Math.abs(centavos) / 100).toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const pct = (v: number | null) => (v === null ? "—" : `${Math.round(v * 1000) / 10}%`);
const reading = (text: unknown): Figure["pill"] => {
  const t = String(text ?? "");
  if (!t || t === "—" || t === "Not enough data") return undefined;
  const good = ["Healthy", "Profit", "Growing", "Positive", "Covered", "Target met", "Above it"].includes(t);
  const bad = ["Loss", "Short", "Low", "Slow", "Negative", "Down", "None", "Below it"].includes(t);
  return { text: t, tone: good ? "good" : bad ? "bad" : "warn" };
};

export default async function ExecutiveHome({ searchParams }: { searchParams: Search }) {
  const account = await getAccount();
  if (!account.isCompanyAdmin) redirect("/platform/reports");
  const s = await searchParams;
  const period: Period = PERIODS.some((p) => p.value === s.period) ? (s.period as Period) : "month";
  const { from, to } = span(period);
  const here = `${BASE}?period=${period}`;

  // Each app's figures are read with its own session, opened on the way if it isn't yet.
  const has = new Set(myModules(account).map((m) => m.key));
  const jar = await cookies();
  for (const m of ["finance", "crm"] as const) {
    if (has.has(m) && !jar.get(moduleCookie(m))?.value) redirect(`/auth/enter/${m}?next=${encodeURIComponent(here)}`);
  }

  const link = (module: string, key: string, dated = true) => `/platform/reports/${module}/${key}${dated ? `?from=${from}&to=${to}` : ""}`;
  const none = Promise.resolve(null);
  const finance = has.has("finance")
    ? Promise.all([report("finance", "key-figures", from, to), report("finance", "revenue-growth", from, to), report("finance", "cash-forecast", from, to), report("finance", "receivables-ageing", from, to)])
    : Promise.all([none, none, none, none]);
  const crm = has.has("crm")
    ? Promise.all([report("crm", "pipeline-coverage", from, to), report("crm", "sales-attainment", from, to), report("crm", "customer-lifetime-value", from, to)])
    : Promise.all([none, none, none]);
  const people = accountSend<{ people: { status: string }[] }>("GET", "/identity/access")
    .then((a) => a.people.filter((p) => p.status === "active").length)
    .catch(() => null);

  const lead = finance.then(([key, growth, cash]): Figure[] => {
    const g = value(growth, "Growth");
    const lowest = value(cash, "Lowest cash ahead");
    return [
      { value: peso(value(key, "Revenue")), label: "Revenue", note: g === null ? "No revenue the period before" : `${g >= 0 ? "+" : ""}${pct(g)} on the period before`, href: link("finance", "revenue-growth"), pill: reading(row(key, "Revenue")?.reading) },
      { value: peso(value(key, "Net profit")), label: "Net profit", note: `Net margin ${row(key, "Net margin")?.now ?? "—"}`, href: link("finance", "key-figures"), pill: reading(row(key, "Net profit")?.reading) },
      { value: peso(value(cash, "Cash now")), label: "Cash", note: lowest === null ? "Forecast not available" : `Lowest in the next 12 weeks: ${peso(lowest)}`, alert: lowest !== null && lowest < 0, href: link("finance", "cash-forecast", false) },
      { value: peso(value(key, "Working capital")), label: "Working capital", note: `Current ratio ${row(key, "Current ratio")?.now ?? "—"}`, href: link("finance", "key-figures"), pill: reading(row(key, "Current ratio")?.reading) },
    ];
  });
  const tiles = Promise.all([finance, crm, people]).then(([[key, , , ageing], [coverage, attainment, clv], heads]): Figure[] => {
    const late = value(ageing, "Late");
    const revenue = value(key, "Revenue");
    const out: Figure[] = [
      { value: String(row(key, "Days to collect (DSO)")?.now ?? "—"), label: "Days to collect", note: "Receivables ÷ revenue × days", href: link("finance", "key-figures"), pill: reading(row(key, "Days to collect (DSO)")?.reading) },
      { value: peso(late), label: "Overdue receivables", note: "Owed by customers, past due", alert: (late ?? 0) > 0, href: link("finance", "receivables-ageing") },
      { value: String(row(key, "Return on assets")?.now ?? "—"), label: "Return on assets", note: "Net profit ÷ total assets", href: link("finance", "key-figures"), pill: reading(row(key, "Return on assets")?.reading) },
      { value: String(row(key, "Quick ratio")?.now ?? "—"), label: "Quick ratio", note: "Current assets without inventory ÷ current liabilities", href: link("finance", "key-figures"), pill: reading(row(key, "Quick ratio")?.reading) },
      // Step 17: from expenses tagged on the chart of accounts, owner's equity and new customers.
      { value: String(row(key, "EBITDA")?.now ?? "—"), label: "EBITDA", note: "Net profit + depreciation, interest and income tax", href: link("finance", "key-figures"), pill: reading(row(key, "EBITDA")?.reading) },
      { value: String(row(key, "Return on equity")?.now ?? "—"), label: "Return on equity", note: `Debt to equity ${row(key, "Debt to equity")?.now ?? "—"}`, href: link("finance", "key-figures"), pill: reading(row(key, "Return on equity")?.reading) },
      { value: String(row(key, "Break-even revenue")?.now ?? "—"), label: "Break-even revenue", note: "Fixed costs ÷ contribution margin", href: link("finance", "key-figures"), pill: reading(row(key, "Break-even revenue")?.reading) },
      { value: String(row(key, "Customer acquisition cost")?.now ?? "—"), label: "Customer acquisition cost", note: "Sales and marketing spend ÷ new customers", href: link("finance", "key-figures") },
    ];
    if (has.has("crm")) {
      const cover = value(coverage, "Coverage");
      out.push(
        { value: pct(cover), label: "Pipeline coverage", note: "Open deals closing this month ÷ what's left of the target", href: link("crm", "pipeline-coverage"), pill: cover === null ? undefined : { text: cover >= 1 ? "Covered" : "Short", tone: cover >= 1 ? "good" : "warn" } },
        { value: pct(value(attainment, "Attainment")), label: "Sales against target", note: "Won ÷ target, this month", href: link("crm", "sales-attainment") },
        { value: peso(value(clv, "Average lifetime value")), label: "Customer lifetime value", note: "Average per customer", href: link("crm", "customer-lifetime-value") },
      );
    }
    out.push({ value: revenue !== null && heads ? peso(Math.round(revenue / heads)) : "—", label: "Revenue per person", note: heads ? `Revenue ÷ ${heads} active people` : "People not available" });
    return out;
  });

  const lead4 = ["Revenue", "Net profit", "Cash", "Working capital"];
  return (
    <>
      <PageHeader title="Home" tools={<ToggleLinks current={period} options={PERIODS.map((p) => ({ ...p, href: `${BASE}?period=${p.value}` }))} />}>
        The company in a few figures, {from} to {to}. Each opens its report.
      </PageHeader>
      {!has.has("finance") ? (
        <p className="text-sm text-ink-3">These figures come from Finance. Add Finance to your company&apos;s apps to see them.</p>
      ) : (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Later data={lead} fallback={lead4.map((l, i) => <FigureCardLoading key={l} label={l} first={i === 0} />)}>
              {(figures) => figures.map((f, i) => <FigureCard key={f.label} figure={f} first={i === 0} />)}
            </Later>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Later data={tiles} fallback={null}>
              {(figures) => figures.map((f) => <Tile key={f.label} figure={f} />)}
            </Later>
          </div>
        </div>
      )}
    </>
  );
}
