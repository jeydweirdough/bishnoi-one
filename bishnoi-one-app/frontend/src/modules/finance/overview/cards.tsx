"use client";

import { Info } from "lucide-react";
import Link from "next/link";
import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { LinkButton } from "@/src/modules/finance/platform/ui/button";
import { Pill } from "@/src/platform/ui/figures";
import { Tip } from "@/src/platform/ui/tip";
import { ageRows, Columns, Gauge, HBars, Line, lines, Ring, Rows, Split, type BarRow, type Peso } from "./charts";
import { agoText, pl, short } from "./lib";
import s from "./overview.module.css";
import type { Action, Bucket, CardKey, Cards, Lead, OverviewData, PeriodKey, Row, Stage } from "./types";

// Each card and lead of the Overview, as the approved mock-up draws them, from what the API sent.
// A card is called only when its data came, so nothing here decides who may see what.

const ZOHO_LABEL = "From Zoho (copy, not yet in the books)";
const SAGE_DEEP = "#4f7f44";
const SAGE = "#a8d69b";

export const CARD_LABELS: Record<CardKey, string> = {
  wait: "Your hand-offs", cash: "Cash position", petty: "Petty cash funds", mkt: "Marketing by team", went: "Where money went",
  ap: "Owed to suppliers", inout: "Money in vs out", ar: "Owed by customers", od: "Most overdue customers", coll: "Collections",
  due: "Invoices falling due this week", zoho: "Zoho invoices, unpaid", vat: "VAT", ready: "BIR readiness", ewt: "Tax withheld (EWT)",
  books: "Books by source", dl: "BIR deadlines", soon: "Coming up", link: "Zoho link",
};
export const AREA_NAMES: Record<string, string> = { payables: "Payables", receivables: "Receivables", cash: "Cash", tax: "Tax", settings: "Settings" };

const WIDE = new Set<CardKey>(["wait", "inout", "due", "zoho", "vat"]);
export const isWide = (key: CardKey) => WIDE.has(key);

export type Ctx = { data: OverviewData; peso: Peso; loadedAt: number; prices: ReactNode; othersOnly: boolean };

const words = (p: PeriodKey) => ({ month: "this month", quarter: "this quarter", year: "this year" })[p];

function Source({ kind, loadedAt }: { kind: "books" | "zoho" | "live"; loadedAt?: number }) {
  const [now, setNow] = useState(0);
  useEffect(() => {
    if (kind !== "live") return;
    const tick = () => setNow(Date.now());
    const first = window.setTimeout(tick, 0);
    const every = window.setInterval(tick, 5000);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(every);
    };
  }, [kind]);
  if (kind === "zoho") return <span className={`${s.src} ${s.zoho}`} title={ZOHO_LABEL}>{ZOHO_LABEL}</span>;
  if (kind === "books") return <span className={s.src}>From the books</span>;
  const seconds = now && loadedAt ? Math.max(0, Math.round((now - loadedAt) / 1000)) : 0;
  return (
    <p className={s.live}>
      <span className={s.pulse} aria-hidden />
      Today · {agoText(seconds)}
    </p>
  );
}

export function Card({ id, title, sub, source, span, ctx, style, extra, children }: { id: string; title: string; sub?: string; source?: "books" | "zoho" | "live"; span: string; ctx: Ctx; style?: CSSProperties; extra?: ReactNode; children: ReactNode }) {
  return (
    <article className={`${s.cell} ${s.sheet} ${span}`} style={style} aria-labelledby={`${id}-t`}>
      <div className={s.in}>
        <header className={s.cardH}>
          <h2 className={s.ct} id={`${id}-t`}>
            <span className={s.ctT} title={title}>{title}</span>
            {sub && (
              <Tip tip={sub} className={s.about}>
                <Info className="size-3.5" aria-hidden />
              </Tip>
            )}
          </h2>
          {extra}
          {source && <Source kind={source} loadedAt={ctx.loadedAt} />}
        </header>
        {sub && <p className={s.sub}>{sub}</p>}
        <div className={s.cb}>{children}</div>
      </div>
    </article>
  );
}

/** Books by source, in a narrow card: the full name stays on hover. */
const SOURCE_SHORT: Record<string, string> = { bill: "Bills", voucher: "Vouchers", petty_cash: "Petty cash", expense: "Zoho expenses", invoice: "Sales", manual: "Typed by hand", fund: "Marketing" };

function Actions({ actions }: { actions: Action[] }) {
  return (
    <div className={s.heroActions}>
      {actions.map((a) => (
        <LinkButton key={a.href + a.label} href={a.href} size="sm" variant={a.primary ? "primary" : "default"} title={a.title ?? undefined}>
          {a.label}
        </LinkButton>
      ))}
    </div>
  );
}

function Hero({ eyebrow, fig, note, stats = [], chips = [], lead, vtitle, source, span, ctx, children }: {
  eyebrow: string;
  fig: string;
  note: string;
  stats?: [string, string][];
  chips?: string[];
  lead: Lead;
  vtitle: string;
  source?: "books" | "zoho" | "live";
  span: string;
  ctx: Ctx;
  children: ReactNode;
}) {
  return (
    <section className={`${s.cell} ${s.lead} ${s.sheet} ${span}`} aria-labelledby="overview-hero">
      <div className={s.heroIn}>
        <div className={s.leadFig}>
          <p className={s.eyebrow}>{eyebrow}</p>
          <h2 id="overview-hero" className={s.heroFig}>{fig}</h2>
          <p className={s.heroNote} title={note}>{note}</p>
          {stats.length > 0 && (
            <div className={s.heroStats}>
              {stats.map(([k, v]) => (
                <div key={k} className={s.hstat}>
                  <span>{k}</span>
                  <b>{v}</b>
                </div>
              ))}
            </div>
          )}
          {chips.length > 0 && (
            <p className={s.heroChips}>
              {chips.map((c) => (
                <Pill key={c}>{c}</Pill>
              ))}
            </p>
          )}
          <Actions actions={lead.actions} />
        </div>
        <div className={s.heroViz}>
          <div className={s.hvH}>
            <h3>{vtitle}</h3>
            {source && <Source kind={source} loadedAt={ctx.loadedAt} />}
          </div>
          <div className={s.hvB}>{children}</div>
        </div>
      </div>
    </section>
  );
}

// ---- Pictures shared by a card and a lead -----------------------------------------------------

function AgeRing({ title, buckets, centavos, noun, peso }: { title: string; buckets: Bucket[]; centavos: number; noun: string; peso: Peso }) {
  return <Ring title={title} slices={buckets} center={short(centavos)} sub="unpaid" noun={noun} peso={peso} />;
}

function VatColumns({ c, ctx }: { c: NonNullable<Cards["vat"]>; ctx: Ctx }) {
  return (
    <Columns
      title="VAT"
      peso={ctx.peso}
      emptyText={`No sales or purchases recorded ${words(ctx.data.period.key)}: ₱0.00`}
      series={[
        { name: "Output VAT", color: SAGE_DEEP, noun: "invoice", points: c.output },
        { name: "Input VAT", color: SAGE, noun: "purchase", points: c.input },
      ]}
    />
  );
}

function CashLine({ c, ctx }: { c: NonNullable<Cards["cash"]>; ctx: Ctx }) {
  return <Line title="Cash position" points={c.points} noun="entry" peso={ctx.peso} />;
}

const FundGauges = ({ c, ctx }: { c: NonNullable<Cards["petty"]>; ctx: Ctx }) =>
  c.funds.length ? (
    <div className={s.gauges}>
      {c.funds.map((f) => (
        <Gauge key={f.name} {...f} peso={ctx.peso} />
      ))}
    </div>
  ) : (
    <div className={s.empty}>No petty cash funds set up yet.</div>
  );

// ---- The cards ---------------------------------------------------------------------------------

type Slot = { span: string; style?: CSSProperties };

function HandOffs({ c, ctx, slot }: { c: NonNullable<Cards["wait"]>; ctx: Ctx; slot: Slot }) {
  const peso = ctx.peso;
  const youTitle = ctx.data.views.overview?.lead === "cash" ? "For your approval" : "Waiting for you";
  const you = (limit: number) => (
    <>
      <div className={s.waitH}>
        <h3>{youTitle}</h3>
        <span className={s.count}>{c.forYouTotal}</span>
        {c.forYouTotal > 2 && c.seeAll && <Link href={c.seeAll} className={s.seeAll}>See all {c.forYouTotal} →</Link>}
      </div>
      <Rows items={c.forYou} empty="Nothing waiting for you." peso={peso} limit={limit} total={c.forYouTotal} tight noSee />
    </>
  );
  const others = (limit: number) => (
    <>
      <div className={s.waitH}>
        <h3>Waiting on others</h3>
        <span className={`${s.count} ${s.countSoft}`}>{c.othersTotal}</span>
      </div>
      <Rows items={c.others} empty="Nothing of yours is waiting on anyone." peso={peso} limit={limit} tight={!ctx.othersOnly} noSee />
    </>
  );
  const solo = ctx.othersOnly;
  return (
    <Card id="wait" title="Your hand-offs" sub="Both sides of every hand-off. Each row opens the record; nothing is approved from here." source="live" span={slot.span} style={slot.style} ctx={ctx} extra={c.prices ? <span className={s.prices}>{ctx.prices}</span> : undefined}>
      <div className={s.waitWide} style={solo ? ({ "--wc": 1 } as CSSProperties) : undefined}>
        {!solo && <div>{you(3)}</div>}
        <div>{others(3)}</div>
      </div>
      <div className={s.waitNarrow}>
        {solo ? others(2) : you(2)}
        {!solo && c.others[0]?.href && <Link href={c.others[0].href} className={s.also}>Also waiting on others: {c.othersTotal} →</Link>}
      </div>
    </Card>
  );
}

function ReadinessCard({ c, ctx, slot }: { c: NonNullable<Cards["ready"]>; ctx: Ctx; slot: Slot }) {
  const peso = ctx.peso;
  const label = { agrees: ["Agrees", "good"], differs: ["Differs", "bad"], not_set: ["Not set", "plain"] } as const;
  const rows: Row[] = c.checks
    .filter((x) => x.status !== "agrees")
    .map((x) => ({
      title: x.title, href: x.href, on: null, amountCentavos: null,
      meta: x.status === "differs" ? `Differs by ${peso(Math.abs(x.differenceCentavos ?? 0))}` : "The account isn't set under Default accounts",
      chip: { text: label[x.status][0], tone: label[x.status][1] },
    }));
  return (
    <Card id="ready" title="BIR readiness" sub="Do the BIR lists agree with the records behind them? Problems first." source="books" span={slot.span} style={slot.style} ctx={ctx}>
      <div className={s.checksSum}>
        <span className={c.counts.differs > 0 ? undefined : s.keepPill}><Pill tone="good">{c.counts.agrees} agree</Pill></span>
        {/* Only a real difference is red: "0 differ" read as a problem when every check agreed (2026-10-31). */}
        {c.counts.differs > 0 && <span className={s.keepPill}><Pill tone="bad">{c.counts.differs} differ</Pill></span>}
        <Pill>{c.counts.not_set} not set</Pill>
        <Link href={c.href} className={s.seeAll}>See all {c.checks.length} →</Link>
      </div>
      <Rows items={rows} empty="Every check agrees." peso={peso} limit={3} noSee />
    </Card>
  );
}

function card(key: CardKey, ctx: Ctx, slot: Slot): ReactNode {
  const { data, peso } = ctx;
  const period = data.period.key;
  const pw = words(period);
  const c = data.cards;
  const common = { span: slot.span, style: slot.style, ctx };
  switch (key) {
    case "wait":
      return <HandOffs c={c.wait!} ctx={ctx} slot={slot} />;
    case "ready":
      return <ReadinessCard c={c.ready!} ctx={ctx} slot={slot} />;
    case "cash": {
      const x = c.cash!;
      return (
        <Card id="cash" title="Cash position" sub={`All accounts under CASH, ${period === "year" ? "month end" : "week end"}`} source="books" {...common}>
          <div className={s.figRow}>
            <span className={s.fig}>{peso(x.balanceCentavos)}</span>
            <span className={s.figNote}>
              {x.points.every((p) => p.amountCentavos === 0) ? "No money recorded yet" : (
                <>
                  <span className={x.changeCentavos >= 0 ? s.up : ""}>{x.changeCentavos >= 0 ? "Up" : "Down"} {peso(Math.abs(x.changeCentavos))}</span> since {x.points[0].label}
                </>
              )}
            </span>
          </div>
          <CashLine c={x} ctx={ctx} />
        </Card>
      );
    }
    case "petty": {
      const x = c.petty!;
      return (
        <Card id="petty" title="Petty cash funds" sub={`Balance in the books today · ${pl(x.postedInPeriod, "voucher")} posted ${pw}`} source="books" {...common}>
          <FundGauges c={x} ctx={ctx} />
          {x.fundCount > x.funds.length && <Link href={x.href} className={s.seeAll}>See all {x.fundCount} →</Link>}
        </Card>
      );
    }
    case "mkt": {
      const x = c.mkt!;
      return (
        <Card id="mkt" title="Marketing by team" sub={`Reviewed liquidations, ${pw} · ${peso(x.totalCentavos)}`} source="books" {...common}>
          {x.teams.length ? <HBars rows={x.teams.map((t) => ({ ...t, tone: s.soft }))} noun="liquidation" peso={peso} /> : <div className={s.empty}>No reviewed spending {pw}: ₱0.00</div>}
        </Card>
      );
    }
    case "went": {
      const x = c.went!;
      const COLORS: Record<string, string> = { bills: SAGE_DEEP, petty: "#7fb26f", marketing: SAGE };
      return (
        <Card id="went" title="Where money went" sub={x.hidden.length ? `Recorded ${pw} · ${x.hidden.join(" and ")} outside your access` : `Recorded ${pw}, by kind`} source="books" {...common}>
          <Ring title="Where money went" slices={x.slices.map((v) => ({ ...v, color: COLORS[v.key] }))} center={short(x.totalCentavos)} sub="recorded" noun="record" peso={peso} />
        </Card>
      );
    }
    case "ap": {
      const x = c.ap!;
      return (
        <Card id="ap" title="Owed to suppliers" sub={`${peso(x.wholeCentavos)} owed in all · bills dated ${pw}: ${peso(x.periodCentavos)}`} source="books" {...common}>
          <HBars rows={ageRows(x.buckets)} noun="bill" peso={peso} />
        </Card>
      );
    }
    case "inout": {
      const x = c.inout!;
      return (
        <Card id="inout" title="Money in vs out" sub={`In ${peso(x.inCentavos)} · out ${peso(x.outCentavos)}, ${data.period.byUnit}`} source="books" {...common}>
          <Columns title="Money in vs out" peso={peso} emptyText={`No money in or out ${pw}: ₱0.00`}
            series={[{ name: "Money in", color: SAGE_DEEP, noun: "entry", points: x.in }, { name: "Money out", color: SAGE, noun: "entry", points: x.out }]} />
        </Card>
      );
    }
    case "ar": {
      const x = c.ar!;
      return (
        <Card id="ar" title="Owed by customers" sub={`${peso(x.wholeCentavos)} owed in all · invoices dated ${pw}: ${peso(x.periodCentavos)}`} source="books" {...common}>
          <AgeRing title="Owed by customers by age" buckets={x.buckets} centavos={x.periodCentavos} noun="invoice" peso={peso} />
        </Card>
      );
    }
    case "od": {
      const x = c.od!;
      return (
        <Card id="od" title="Most overdue" sub="Ranked by days late; each opens the customer's invoices" source="books" {...common}>
          <Rows items={x.rows} empty="No customer is overdue." peso={peso} ranked limit={3} total={x.total} seeAll={x.href} />
        </Card>
      );
    }
    case "coll": {
      const x = c.coll!;
      return (
        <Card id="coll" title="Collections" sub={`Payments received ${pw}, ${data.period.byUnit}`} source="books" {...common}>
          <div className={s.figRow}>
            <span className={s.fig}>{peso(x.totalCentavos)}</span>
            <span className={s.figNote}>from {pl(x.count, "payment")}</span>
          </div>
          <Line title="Collections" points={x.points} noun="payment" peso={peso} />
        </Card>
      );
    }
    case "due": {
      const x = c.due!;
      return (
        <Card id="due" title="Invoices due this week" sub="2MG and GPI, soonest first" source="zoho" {...common}>
          {x.available ? <Rows items={x.rows} empty="No invoices fall due this week." peso={peso} limit={3} total={x.total} seeAll={x.href} /> : <div className={s.empty}>Not available yet: the Zoho organisation isn&apos;t confirmed here.</div>}
        </Card>
      );
    }
    case "zoho": {
      const x = c.zoho!;
      if (!x.available) {
        return (
          <Card id="zoho" title="Zoho invoices, unpaid" sub="Saved copies of Zoho's invoices" source="zoho" {...common}>
            <div className={s.empty}>Not available yet: the Zoho organisation isn&apos;t confirmed here.</div>
          </Card>
        );
      }
      const shades: Record<string, string> = { "2mg": SAGE_DEEP, gpi: SAGE, unknown: "#d6d6d4" };
      return (
        <Card id="zoho" title="Zoho invoices, unpaid" sub={`${peso(x.totalCentavos!)} · invoices dated ${pw}${x.notCounted ? ` · ${pl(x.notCounted, "invoice")} not counted (no saved balance, or not in pesos)` : ""}`} source="zoho" {...common}>
          <div className={s.two}>
            <div>
              <p className={s.miniH}>By company</p>
              <Split parts={x.companies!.map((p) => ({ ...p, color: shades[p.key] }))} noun="invoice" peso={peso} />
            </div>
            <div>
              <p className={s.miniH}>By age</p>
              <HBars rows={ageRows(x.buckets!)} noun="invoice" peso={peso} />
            </div>
          </div>
        </Card>
      );
    }
    case "vat": {
      const x = c.vat!;
      return (
        <Card id="vat" title="VAT" sub={x.vatRegistered ? `${x.payableCentavos < 0 ? "Carried over" : "Payable"}: ${peso(Math.abs(x.payableCentavos))} · output minus input` : "This company files percentage tax (2551Q), not VAT"} source="books" {...common}>
          <VatColumns c={x} ctx={ctx} />
        </Card>
      );
    }
    case "ewt": {
      const x = c.ewt!;
      return (
        <Card id="ewt" title="Tax withheld (EWT)" sub={`${peso(x.totalCentavos)} ${pw} · ${pl(x.payees, "payee")} need a 2307 (the certificate of tax withheld)`} source="books" {...common}>
          <Columns title="Tax withheld" peso={peso} emptyText={`No tax withheld ${pw}: ₱0.00`} series={[{ name: "Tax withheld", color: SAGE, noun: "purchase", points: x.points }]} />
        </Card>
      );
    }
    case "books": {
      const x = c.books!;
      const rows: BarRow[] = x.sources.map((r) => ({ ...r, short: SOURCE_SHORT[r.key], noun: "entry", tone: r.key === "manual" ? s.warn : r.key === "petty_cash" ? s.soft : "", note: r.key === "manual" && r.count ? "Typed entries skip the usual checks, so they are worth a look." : undefined }));
      return (
        <Card id="books" title="Books by source" sub={`Journal entries ${pw}; amber = typed by hand`} source="books" {...common}>
          <HBars rows={rows} noun="entry" peso={peso} />
        </Card>
      );
    }
    case "dl":
      return (
        <Card id="dl" title="BIR deadlines" sub="Coming after Sir Mel's list" {...common}>
          <div className={s.placeholder}>
            <p className={s.phNote}>Legal dates are never guessed. They appear here once Sir Mel gives his list of forms and dates.</p>
            <div className={s.ghostRow} />
            <div className={s.ghostRow} style={{ opacity: 0.6 }} />
          </div>
        </Card>
      );
    case "soon": {
      const x = c.soon!;
      return (
        <Card id="soon" title="Coming up" sub="Bills falling due, your calendar and holidays, next 30 days" {...common}>
          <Rows items={x.rows} empty="Nothing coming up in the next 30 days." peso={peso} limit={3} total={x.total} seeAll={x.href} />
        </Card>
      );
    }
    case "link": {
      const x = c.link!;
      const state = !x.connected ? "Not connected here" : x.stoppedForToday ? "Stopped for today" : x.error ? "Needs a look" : "Reading";
      return (
        <Card id="link" title="Zoho link" sub="The reader's last update and today's requests" {...common}>
          <div className={s.checksSum}>
            <Pill tone={x.connected && !x.error && !x.stoppedForToday ? "good" : "warn"}>{state}</Pill>
            <Link href={x.href} className={s.seeAll}>Open →</Link>
          </div>
          {x.connected && <p className={s.phNote}>{(x.usedToday ?? 0).toLocaleString("en-PH")} of {(x.dailyLimit ?? 0).toLocaleString("en-PH")} requests today</p>}
        </Card>
      );
    }
  }
}

export function CardFor({ cardKey, ctx, span, index }: { cardKey: CardKey; ctx: Ctx; span: string; index: number }) {
  return <>{card(cardKey, ctx, { span, style: { "--i": index + 1 } as CSSProperties })}</>;
}

// ---- The leads -----------------------------------------------------------------------------------

const STAGE_LOOK: Record<string, { color: string; ink: string }> = {
  returned: { color: "#d48806", ink: "#fff" }, drafts: { color: "#d6d6d4", ink: "#141414" }, approve: { color: SAGE, ink: "#141414" },
  check: { color: "#7fb26f", ink: "#141414" }, posted: { color: SAGE_DEEP, ink: "#fff" },
};

function StageStrip({ stages, peso }: { stages: Stage[]; peso: Peso }) {
  const shown = stages.filter((x) => x.count > 0);
  return (
    <>
      <div className={s.stages} role="group" aria-label={shown.length ? "Your records by stage" : "No records yet"}>
        {shown.map((x) => {
          const tip = lines(x.label, peso(x.amountCentavos), pl(x.count, x.noun));
          return (
            <Link key={x.key} href={x.href} className={s.stage} style={{ flex: x.count, background: STAGE_LOOK[x.key].color, color: STAGE_LOOK[x.key].ink }} data-tip={tip} aria-label={tip.replaceAll("\n", ", ")}>
              {x.count}
            </Link>
          );
        })}
      </div>
      <div className={s.stageKey}>
        {stages.map((x) => (
          <span key={x.key}>
            <i style={{ background: STAGE_LOOK[x.key].color }} />
            {x.label} · {x.count}
          </span>
        ))}
      </div>
    </>
  );
}

export function LeadFor({ lead, ctx, span }: { lead: Lead; ctx: Ctx; span: string }) {
  const { data, peso } = ctx;
  const period = data.period.key;
  const pw = words(period);
  const c = data.cards;
  const common = { lead, span, ctx };
  switch (lead.key) {
    case "release": {
      const rows = (lead.rows ?? []) as (Bucket & { noun: string })[];
      const n = lead.count ?? 0;
      return (
        <Hero eyebrow="To release" fig={peso(lead.totalCentavos ?? 0)} {...common} vtitle="What is waiting to be released" source="live"
          note={n ? `${pl(n, "payment")} approved and waiting for release; the oldest has waited ${pl(lead.oldestDays ?? 0, "day")}. Each opens on its own record.` : "Nothing approved and waiting for release. That's fine."}
          stats={[[`Released ${pw}`, peso(lead.releasedCentavos ?? 0)], ["Payments released", String(lead.releasedCount ?? 0)]]}>
          <HBars rows={rows} noun="payment" peso={peso} />
        </Hero>
      );
    }
    case "cash": {
      const x = c.cash!;
      const none = x.points.every((p) => p.amountCentavos === 0);
      return (
        <Hero eyebrow="Cash position today" fig={peso(x.balanceCentavos)} {...common} vtitle={period === "year" ? "Cash at each month end" : "Cash at each week end"} source="books"
          note={none ? "No money recorded in the books yet. That's fine." : `All money accounts under CASH. ${x.changeCentavos >= 0 ? "Up" : "Down"} ${peso(Math.abs(x.changeCentavos))} since ${x.points[0].label}.`}
          stats={c.inout ? [[`Money in ${pw}`, peso(c.inout.inCentavos)], [`Money out ${pw}`, peso(c.inout.outCentavos)]] : []}>
          <CashLine c={x} ctx={ctx} />
        </Hero>
      );
    }
    case "vat": {
      const x = c.vat!;
      const carried = x.payableCentavos < 0;
      const none = !x.outputCentavos && !x.inputCentavos;
      return (
        <Hero eyebrow={carried ? `VAT carried over ${pw}` : `VAT payable ${pw}`} fig={peso(Math.abs(x.payableCentavos))} {...common} vtitle={`Output vs input VAT, ${data.period.byUnit}`} source="books"
          note={!x.vatRegistered ? "This company files percentage tax (2551Q), not VAT." : none ? "No sales or purchases recorded yet, so there is no VAT to show. That's fine." : `Output VAT on sales minus input VAT on purchases. ${carried ? "Input is higher, so the difference carries over." : "Output is higher, so this is payable."}`}
          stats={[["Output VAT", peso(x.outputCentavos)], ["Input VAT", peso(x.inputCentavos)]]}>
          <VatColumns c={x} ctx={ctx} />
        </Hero>
      );
    }
    case "recv": {
      const x = c.ar!;
      return (
        <Hero eyebrow="Owed by customers" fig={peso(x.wholeCentavos)} {...common} vtitle={`Invoices dated ${pw}, by how late`} source="books"
          note={x.wholeCentavos ? `${peso(x.over60Centavos)} is more than 60 days late. Dated ${pw}: ${pl(x.periodInvoices, "invoice")} unpaid.` : "No unpaid invoices in the books yet. That's fine: this fills in as invoices are recorded."}
          chips={lead.viewOnly ? ["View only: you can open and read, not post"] : []}>
          <AgeRing title="Owed by customers by age" buckets={x.buckets} centavos={x.periodCentavos} noun="invoice" peso={peso} />
        </Hero>
      );
    }
    case "sup": {
      const x = c.ap!;
      return (
        <Hero eyebrow="Owed to suppliers" fig={peso(x.wholeCentavos)} {...common} vtitle={`Bills dated ${pw}, by how late`} source="books"
          note={x.wholeCentavos ? `${peso(x.over60Centavos)} is more than 60 days late. Dated ${pw}: ${pl(x.periodBills, "unpaid bill")}. Due this week: ${peso(x.dueThisWeekCentavos)}.` : "No unpaid bills yet. That's fine."}>
          <HBars rows={ageRows(x.buckets)} noun="bill" peso={peso} />
        </Hero>
      );
    }
    case "check": {
      const n = lead.count ?? 0;
      return (
        <Hero eyebrow="Waiting for your tax check" fig={peso(lead.totalCentavos ?? 0)} {...common} vtitle="Oldest first" source="live"
          note={n ? `${pl(n, "bill")} approved and waiting for you to check the tax withheld (ATC: the BIR's tax code for each kind of payment).` : "No bills are waiting for your tax check."}>
          <Rows items={(lead.rows ?? []) as Row[]} empty="No bills are waiting for your tax check." peso={peso} limit={3} total={n} seeAll={lead.actions[0]?.href} tight />
        </Hero>
      );
    }
    case "mine": {
      const n = lead.count ?? 0;
      return (
        <Hero eyebrow="Your bills and petty cash" fig={peso(lead.totalCentavos ?? 0)} {...common} vtitle="Where your records are" source="live"
          note={n ? `${pl(n, "record")} in progress; ${lead.returned ?? 0} came back to you.` : "Nothing in progress yet. New bills you record show up here."}>
          <StageStrip stages={lead.stages ?? []} peso={peso} />
          <p className={s.miniH}>Returned first</p>
          <Rows items={(lead.rows ?? []) as Row[]} empty="Nothing came back to you." peso={peso} limit={2} total={lead.rowsTotal} noSee tight />
        </Hero>
      );
    }
    case "petty": {
      const x = c.petty!;
      return (
        <Hero eyebrow="Petty cash funds" fig={peso(x.balanceCentavos)} {...common} vtitle="Balance in the books, per fund" source="books"
          note={x.fundCount ? `Left across ${pl(x.fundCount, "fund")} today. ${pl(x.postedInPeriod, "voucher")} posted ${pw}.` : "No petty cash funds set up yet. That's fine."}>
          <FundGauges c={x} ctx={ctx} />
        </Hero>
      );
    }
    default:
      return (
        <Hero eyebrow="Your overview" fig="Nothing to show yet" {...common} vtitle="What you can open" note="The pictures here follow what your role can open. Your pages are in the sidebar.">
          <div className={s.empty}>No picture for your role yet.</div>
        </Hero>
      );
  }
}
