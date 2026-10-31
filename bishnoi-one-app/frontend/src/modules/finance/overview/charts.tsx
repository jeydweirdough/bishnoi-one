"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { Pill } from "@/src/platform/ui/figures";
import { pl, short } from "./lib";
import s from "./overview.module.css";
import type { Bucket, Point, Row, Tone } from "./types";

// The Overview's pictures, drawn by hand as the CRM draws its own (donut, month bars, trend line): one
// colour per picture, red only for what's late. Each takes its size from the card. Every mark is a real
// link to the list behind it; its exact figure and count show on hover or focus through `data-tip`.

export type Peso = (centavos: number) => string;

const AGE_COLORS: Record<string, string> = { current: "#4f7f44", d1_30: "#f2b8b1", d31_60: "#e2786d", d61_90: "#c9473b", over_90: "#b42318", no_due: "#d6d6d4" };
const AGE_TONES: Record<string, string> = { current: "", d1_30: s.late1, d31_60: s.late2, d61_90: s.late3, over_90: s.late4, no_due: s.soft };
const AGE_SHORT: Record<string, string> = { current: "Not due", d1_30: "1–30 late", d31_60: "31–60 late", d61_90: "61–90 late", over_90: "90+ late", no_due: "No due date" };

export const lines = (...parts: (string | null | undefined | false)[]) => parts.filter(Boolean).join("\n");

/** The one bubble for every picture: the amount and the count stay on lines of their own, in the app's dark tooltip. */
export function HoverTip({ root }: { root: RefObject<HTMLElement | null> }) {
  const [tip, setTip] = useState<{ text: string; x: number; y: number } | null>(null);
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const anchor = (t: EventTarget | null) => (t instanceof Element ? t.closest<HTMLElement | SVGElement>("[data-tip]") : null);
    const place = (x: number, y: number) => ({ x: Math.min(Math.max(x, 170), window.innerWidth - 170), y: Math.max(y - 6, 70) });
    const over = (e: PointerEvent) => {
      const a = anchor(e.target);
      if (a?.dataset.tip) setTip({ text: a.dataset.tip, ...place(e.clientX, e.clientY) });
    };
    const move = (e: PointerEvent) => setTip((t) => (t ? { ...t, ...place(e.clientX, e.clientY) } : t));
    const out = (e: PointerEvent) => {
      const a = anchor(e.target);
      if (a && !(e.relatedTarget instanceof Node && a.contains(e.relatedTarget))) setTip(null);
    };
    const focus = (e: FocusEvent) => {
      const a = anchor(e.target);
      if (a === e.target && a?.dataset.tip) {
        const r = a.getBoundingClientRect();
        setTip({ text: a.dataset.tip, ...place(r.left + r.width / 2, r.top) });
      } else setTip(null);
    };
    const hide = () => setTip(null);
    el.addEventListener("pointerover", over);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerout", out);
    el.addEventListener("focusin", focus);
    el.addEventListener("focusout", hide);
    window.addEventListener("scroll", hide, { passive: true });
    return () => {
      el.removeEventListener("pointerover", over);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerout", out);
      el.removeEventListener("focusin", focus);
      el.removeEventListener("focusout", hide);
      window.removeEventListener("scroll", hide);
    };
  }, [root]);
  if (!tip) return null;
  const [first, ...rest] = tip.text.split("\n");
  return createPortal(
    <div role="tooltip" className={s.tip} style={{ left: tip.x, top: tip.y }}>
      <span className={s.tipB}>
        <strong>{first}</strong>
        {rest.map((line, i) => (
          <span key={i}>{line}</span>
        ))}
      </span>
    </div>,
    document.body,
  );
}

/** A slice of a ring: an SVG link, so it opens with a click, a key or a middle click like any other. */
function SvgLink({ href, tip, label, children }: { href: string; tip: string; label: string; children: ReactNode }) {
  const router = useRouter();
  return (
    <a
      href={href}
      data-tip={tip}
      aria-label={label}
      onClick={(e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
        e.preventDefault();
        router.push(href);
      }}
    >
      {children}
    </a>
  );
}

type Slice = Omit<Bucket, "key"> & { key: string; short?: string; color?: string; noun?: string };

export function Ring({ title, slices, center, sub, noun, peso }: { title: string; slices: Slice[]; center: string; sub: string; noun: string; peso: Peso }) {
  const R = 62;
  const C = 2 * Math.PI * R;
  const total = slices.reduce((n, x) => n + x.amountCentavos, 0);
  const shown = slices.filter((x) => x.amountCentavos > 0);
  const gap = shown.length > 1 ? 3 : 0;
  const color = (x: Slice) => x.color ?? AGE_COLORS[x.key];
  const tipOf = (x: Slice) => lines(x.label, peso(x.amountCentavos), pl(x.count, x.noun ?? noun));
  let off = 0;
  return (
    <div className={s.ringWrap}>
      <svg className={s.ring} viewBox="0 0 160 160" role="group" aria-label={`${title}: ${slices.map((x) => `${x.label} ${peso(x.amountCentavos)}`).join(", ")}`}>
        <circle className={s.track} cx="80" cy="80" r={R} />
        {shown.map((x) => {
          const L = (C * x.amountCentavos) / total;
          const arc = (
            <SvgLink key={x.key} href={x.href} tip={tipOf(x)} label={tipOf(x).replaceAll("\n", ", ")}>
              <circle className={s.arc} cx="80" cy="80" r={R} stroke={color(x)} style={{ strokeDasharray: `${Math.max(0.6, L - gap).toFixed(2)} ${C.toFixed(2)}`, strokeDashoffset: (-off).toFixed(2) }} transform="rotate(-90 80 80)" />
            </SvgLink>
          );
          off += L;
          return arc;
        })}
        <text x="80" y="82" className={s.ringC}>{center}</text>
        <text x="80" y="101" className={s.ringS}>{sub}</text>
      </svg>
      <ul className={s.legend}>
        {slices.map((x) => (
          <li key={x.key}>
            <Link href={x.href} className={s.leg} data-tip={tipOf(x)}>
              <span className={s.dot} style={{ background: color(x) }} aria-hidden />
              <span className={s.legL}>
                <span className={s.long}>{x.label}</span>
                <span className={s.shrt}>{x.short ?? AGE_SHORT[x.key] ?? x.label}</span>
              </span>
              <span className={s.legA}>{peso(x.amountCentavos)}</span>
              <span className={s.legC}>{total ? Math.round((100 * x.amountCentavos) / total) : 0}%</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** `short`: the name on the row where a narrow card would cut the full one; the hover keeps the full label. */
export type BarRow = { key?: string; label: string; short?: string; amountCentavos: number; count: number; href: string; noun?: string; tone?: string; note?: string };

export const ageRows = (buckets: Bucket[]): BarRow[] => buckets.map((b) => ({ ...b, tone: AGE_TONES[b.key] }));

export function HBars({ rows, noun, peso }: { rows: BarRow[]; noun: string; peso: Peso }) {
  const most = Math.max(1, ...rows.map((r) => r.amountCentavos));
  return (
    <ul className={s.hbars}>
      {rows.map((r) => {
        const width = r.amountCentavos <= 0 ? 0 : Math.max(2, (100 * r.amountCentavos) / most);
        const count = pl(r.count, r.noun ?? noun);
        return (
          <li key={r.key ?? r.label}>
            <Link href={r.href} className={`${s.hbar} ${r.tone ?? ""}`} data-tip={lines(r.label, peso(r.amountCentavos), count, r.note)}>
              <span className={s.hbTop}>
                <span className={s.hbL}>{r.short ?? r.label}</span>
                <span className={s.hbA}>
                  {peso(r.amountCentavos)}
                  <small>{count}</small>
                </span>
              </span>
              <span className={s.hbTrack} aria-hidden>
                <span className={s.hbFill} style={{ width: `${width.toFixed(1)}%` }} />
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export function Columns({ title, series, emptyText, peso }: { title: string; series: { name: string; color: string; noun: string; points: Point[] }[]; emptyText: string; peso: Peso }) {
  const cats = series[0].points.map((p) => p.label);
  const most = Math.max(1, ...series.flatMap((x) => x.points.map((p) => p.amountCentavos)));
  const empty = series.every((x) => x.points.every((p) => p.amountCentavos === 0));
  const density = cats.length > 6 ? s.many : cats.length > 3 ? s.mid : "";
  const label = `${title}: ${cats.map((c, i) => `${c} ${series.map((x) => `${x.name} ${peso(x.points[i].amountCentavos)}`).join(" and ")}`).join("; ")}`;
  return (
    <div className={`${s.cols} ${empty ? s.isEmpty : ""} ${density}`} role="group" aria-label={label}>
      {series.length > 1 && (
        <div className={s.key}>
          {series.map((x) => (
            <span key={x.name}>
              <i style={{ background: x.color }} />
              {x.name}
            </span>
          ))}
        </div>
      )}
      <div className={s.colsPlot}>
        {cats.map((c, i) => (
          <div key={`${c}-${i}`} className={s.col}>
            <div className={s.colBars}>
              {series.map((x) => {
                const p = x.points[i];
                const height = p.amountCentavos <= 0 ? 0 : Math.max(2, (100 * p.amountCentavos) / most);
                const tip = lines(`${x.name}, ${c}`, peso(p.amountCentavos), pl(p.count, x.noun));
                return <Link key={x.name} href={p.href} className={s.bar} style={{ height: `${height.toFixed(1)}%`, background: x.color }} data-tip={tip} aria-label={tip.replaceAll("\n", ", ")} />;
              })}
            </div>
            <span className={s.colL} aria-hidden>{c}</span>
          </div>
        ))}
        {empty && (
          <p className={s.emptyNote}>
            <span>{emptyText}</span>
          </p>
        )}
      </div>
    </div>
  );
}

export function Line({ title, points, noun, peso }: { title: string; points: Point[]; noun: string; peso: Peso }) {
  const vals = points.map((p) => p.amountCentavos);
  const flat = vals.every((v) => v === 0);
  let lo = Math.min(...vals);
  let hi = Math.max(...vals);
  if (flat) {
    lo = 0;
    hi = 1;
  } else {
    const pad = (hi - lo || Math.abs(hi) || 1) * 0.18;
    lo -= pad;
    hi += pad;
  }
  const n = points.length;
  const X = (i: number) => (n > 1 ? (i / (n - 1)) * 100 : 50);
  const Y = (v: number) => (flat ? 94 : (1 - (v - lo) / (hi - lo)) * 100);
  const d = points.map((p, i) => `${i ? "L" : "M"}${X(i).toFixed(2)},${Y(p.amountCentavos).toFixed(2)}`).join(" ");
  const xs = n <= 4 ? points.map((_, i) => i) : [0, Math.floor((n - 1) / 2), n - 1];
  return (
    <div className={`${s.line} ${flat ? s.isFlat : ""}`} role="group" aria-label={`${title}: ${points.map((p) => `${p.label} ${peso(p.amountCentavos)}`).join(", ")}`}>
      <div className={s.lineClip}>
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
          {[25, 50, 75].map((y) => (
            <line key={y} x1="0" x2="100" y1={y} y2={y} stroke="var(--color-rule)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
          ))}
          <line x1="0" x2="100" y1="100" y2="100" stroke="var(--color-rule-strong)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
          {!flat && n > 1 && <path d={`${d} L${X(n - 1).toFixed(2)},100 L0,100 Z`} fill="var(--color-sage)" fillOpacity="0.28" />}
          <path d={d} fill="none" stroke={flat ? "var(--color-rule-strong)" : "var(--color-sage-deep)"} strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round" strokeDasharray={flat ? "4 4" : undefined} vectorEffect="non-scaling-stroke" />
        </svg>
      </div>
      {!flat && <span className={s.yL} style={{ top: "0%" }} aria-hidden>{short(hi)}</span>}
      <span className={s.yL} style={{ top: "100%" }} aria-hidden>{short(flat ? 0 : lo)}</span>
      {xs.map((i) => (
        <span key={i} className={`${s.xL} ${i === 0 ? s.xFirst : i === n - 1 ? s.xLast : s.xMid}`} style={{ left: `${X(i).toFixed(2)}%` }} aria-hidden>
          {points[i].label}
        </span>
      ))}
      {points.map((p, i) => {
        const tip = lines(p.label, peso(p.amountCentavos), pl(p.count, noun));
        return <Link key={`${p.label}-${i}`} href={p.href} className={`${s.pt} ${i === n - 1 ? s.ptLast : ""}`} style={{ left: `${X(i).toFixed(2)}%`, top: `${Y(p.amountCentavos).toFixed(2)}%` }} data-tip={tip} aria-label={tip.replaceAll("\n", ", ")} />;
      })}
    </div>
  );
}

/** One petty cash fund. The books hold no fund amount yet, so the dial stays open: it never pretends to a share. */
export function Gauge({ name, balanceCentavos, waiting, href, peso }: { name: string; balanceCentavos: number; waiting: number; href: string; peso: Peso }) {
  return (
    <Link href={href} className={s.gauge} data-tip={lines(name, peso(balanceCentavos), `${pl(waiting, "voucher")} waiting`)}>
      <svg viewBox="0 0 100 58" aria-hidden>
        <path className={s.gTrack} d="M10 50 A40 40 0 0 1 90 50" pathLength="100" />
      </svg>
      <span className={s.gName}>{name.replace(/^petty cash\s*(fund)?\s*[-–:]?\s*/i, "") || name}</span>
      <span className={s.gAmt}>{peso(balanceCentavos)}</span>
      <span className={s.gSub}>{waiting ? `${pl(waiting, "voucher")} waiting` : "No fund amount yet"}</span>
    </Link>
  );
}

export function Split({ parts, noun, peso }: { parts: (Bucket & { color: string })[]; noun: string; peso: Peso }) {
  const total = parts.reduce((n, p) => n + p.amountCentavos, 0);
  return (
    <>
      <div className={s.splitWrap}>
        <div className={s.split} role="group" aria-label={parts.map((p) => `${p.label} ${peso(p.amountCentavos)}`).join(", ")}>
          {total > 0 &&
            parts.map((p) => {
              const tip = lines(p.label, peso(p.amountCentavos), pl(p.count, noun));
              return <Link key={p.key} href={p.href} className={s.segB} style={{ width: `${((100 * p.amountCentavos) / total).toFixed(1)}%`, background: p.color }} data-tip={tip} aria-label={tip.replaceAll("\n", ", ")} />;
            })}
        </div>
      </div>
      <div className={s.splitKey}>
        {parts.map((p) => (
          <span key={p.key}>
            <i style={{ background: p.color }} />
            {p.label} {total ? Math.round((100 * p.amountCentavos) / total) : 0}% <b>{peso(p.amountCentavos)}</b>
          </span>
        ))}
      </div>
    </>
  );
}

const PILL: Record<Tone, "good" | "warn" | "bad" | "plain"> = { good: "good", warn: "warn", bad: "bad", plain: "plain" };

function DayMark({ on, holiday }: { on: string; holiday?: boolean }) {
  const when = new Date(`${on}T00:00:00Z`);
  return (
    <span className={`${s.day} ${holiday ? s.dayHol : ""}`} aria-hidden>
      <b>{when.getUTCDate()}</b>
      <span>{when.toLocaleString("en-PH", { month: "short", timeZone: "UTC" })}</span>
    </span>
  );
}

/** A list that shows only what fits (the top few), then "See all N". Each row opens its record; nothing is done from here. */
export function Rows({ items, empty, peso, limit = 3, total, seeAll, tight = false, ranked = false, noSee = false }: {
  items: Row[];
  empty: string;
  peso: Peso;
  limit?: number;
  total?: number;
  seeAll?: string | null;
  tight?: boolean;
  ranked?: boolean;
  noSee?: boolean;
}) {
  if (!items.length) return <div className={s.empty}>{empty}</div>;
  const all = total ?? items.length;
  const shown = items.slice(0, limit);
  const more = all > shown.length;
  const extra = !more && shown.length >= 3;
  return (
    <>
      <ul className={`${s.rows} ${tight ? s.tight : ""}`}>
        {shown.map((it, i) => {
          const inside = (
            <>
              {ranked && <span className={s.rank} aria-hidden>{it.rank ?? i + 1}</span>}
              {it.on && <DayMark on={it.on} holiday={it.holiday} />}
              <span className={s.rowMain}>
                <span className={s.rowT}>{it.title}</span>
                <span className={s.rowM}>{it.meta}</span>
                {it.chip && <span className={`${s.rowS} ${it.chip.tone === "warn" ? s.rowSwarn : it.chip.tone === "bad" ? s.rowSbad : it.chip.tone === "good" ? s.rowSgood : ""}`}>{it.chip.text}</span>}
              </span>
              {it.chip && (
                <span className={s.rowPill}>
                  <Pill tone={PILL[it.chip.tone]}>{it.chip.text}</Pill>
                </span>
              )}
              {it.amountCentavos !== null && <span className={s.rowA}>{peso(it.amountCentavos)}</span>}
              {it.href && (
                <span className={s.open} aria-hidden>
                  <span className={s.openT}>Open </span>→
                </span>
              )}
            </>
          );
          const tip = lines(it.title, it.amountCentavos !== null && peso(it.amountCentavos), it.meta);
          const cls = `${s.row} ${it.chip ? s.hasS : ""}`;
          return (
            <li key={`${it.title}-${i}`}>
              {it.href ? (
                <Link href={it.href} className={cls} data-tip={tip}>
                  {inside}
                </Link>
              ) : (
                <div className={cls} data-tip={tip}>
                  {inside}
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {!noSee && seeAll && (more || extra) && (
        <Link href={seeAll} className={`${s.seeAll} ${extra ? s.seeExtra : ""}`}>
          See all {all.toLocaleString("en-PH")} →
        </Link>
      )}
    </>
  );
}
