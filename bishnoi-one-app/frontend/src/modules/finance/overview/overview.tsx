"use client";

import { Pencil } from "lucide-react";
import { createContext, use, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, useTransition, type ReactNode } from "react";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { Modal } from "@/src/modules/finance/platform/ui/modal";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import type { Org } from "@/src/modules/finance/platform/lib/types";
import { overviewFor } from "./actions";
import { AREA_NAMES, CARD_LABELS, CardFor, isWide, LeadFor, type Ctx } from "./cards";
import { HoverTip } from "./charts";
import { MAX_CARDS, pl, place, readPicks, writePicks } from "./lib";
import s from "./overview.module.css";
import type { AreaKey, CardKey, OverviewData, PeriodKey } from "./types";

// The page around the cards: the tabs, the period switch, and "Edit my overview". The first answer comes
// from the server with the page; a new period asks again, and nothing else on the page reloads.

const TABS: [AreaKey, string][] = [["overview", "Overview"], ["payables", "Payables"], ["receivables", "Receivables"], ["cash", "Cash"], ["tax", "Tax"]];
const PERIODS: [PeriodKey, string][] = [["month", "This month"], ["quarter", "This quarter"], ["year", "This year"]];
// The rows fill what's left of the window, down to MIN_ROW: below that the page scrolls a little rather than cramming.
const MIN_ROW = 168;
const MAX_ROW = 270;
const MAX_SOLO = 380;
const GAP = 20;
const BOTTOM = 48;

type Shared = { data: OverviewData; setData: (d: OverviewData) => void; userId: string; picks: CardKey[] | null; setPicks: (p: CardKey[] | null) => void; editing: boolean; setEditing: (on: boolean) => void };
const Overview = createContext<Shared | null>(null);

/** Holds the answer for the header's Edit button and the cards below it, which the server draws apart. */
export function OverviewProvider({ initial, userId, children }: { initial: OverviewData; userId: string; children: ReactNode }) {
  const [data, setData] = useState(initial);
  const [picks, setPicksState] = useState<CardKey[] | null>(null);
  const [editing, setEditing] = useState(false);
  // After the first draw, so the server's page and the browser's first draw agree.
  useEffect(() => {
    const allowed = initial.pickable.map((p) => p.key);
    const first = window.setTimeout(() => setPicksState(readPicks(userId, allowed)), 0);
    return () => window.clearTimeout(first);
  }, [initial, userId]);
  const setPicks = useCallback((p: CardKey[] | null) => {
    writePicks(userId, p);
    setPicksState(p);
  }, [userId]);
  const shared = useMemo(() => ({ data, setData, userId, picks, setPicks, editing, setEditing }), [data, userId, picks, setPicks, editing]);
  return <Overview value={shared}>{children}</Overview>;
}

function useOverview(): Shared {
  const shared = use(Overview);
  if (!shared) throw new Error("Inside OverviewProvider only.");
  return shared;
}

export function EditOverviewButton() {
  const { editing, setEditing } = useOverview();
  return (
    <Button size="sm" icon={<Pencil className="size-3.5" aria-hidden />} aria-haspopup="dialog" aria-expanded={editing} onClick={() => setEditing(true)}>
      Edit my overview
    </Button>
  );
}

function EditPanel({ suggested }: { suggested: CardKey[] }) {
  const { data, picks, setPicks, setEditing } = useOverview();
  const [chosen, setChosen] = useState<CardKey[]>(picks ?? suggested);
  const full = chosen.length >= MAX_CARDS;
  const flip = (key: CardKey) => setChosen((now) => (now.includes(key) ? now.filter((k) => k !== key) : [...now, key].slice(0, MAX_CARDS)));
  return (
    <Modal open title="Edit my overview" width={480} footer={null} onCancel={() => setEditing(false)}>
      <p className={s.why}>Pick up to {MAX_CARDS} cards, so it all fits on one screen. Everything else stays in the area tabs. Only what you may see is offered.</p>
      <fieldset className={s.picks} aria-label="Cards you may show">
        {data.pickable.map(({ key, area }) => {
          const on = chosen.includes(key);
          const off = !on && full;
          return (
            <label key={key} className={`${s.pick} ${off ? s.pickOff : ""}`}>
              <input suppressHydrationWarning type="checkbox" checked={on} disabled={off} onChange={() => flip(key)} />
              <span>
                {CARD_LABELS[key]}
                <small>{AREA_NAMES[area]}</small>
              </span>
            </label>
          );
        })}
      </fieldset>
      <p className={`${s.pickMsg} ${full ? s.pickFull : ""}`} aria-live="polite">
        {chosen.length} of {MAX_CARDS} picked.{full ? " That's the limit, so it all fits on one screen; untick one to swap." : ""}
      </p>
      <div className={s.panelF}>
        <button suppressHydrationWarning type="button" className={s.reset} onClick={() => { setPicks(null); setEditing(false); }}>
          Reset to suggested
        </button>
        <Button onClick={() => setEditing(false)}>Cancel</Button>
        <Button variant="primary" onClick={() => { setPicks(chosen); setEditing(false); }}>
          Save
        </Button>
      </div>
    </Modal>
  );
}

export function OverviewBody({ org, prices }: { org: Org; prices: ReactNode }) {
  const { data, setData, picks, editing } = useOverview();
  const [tab, setTab] = useState<AreaKey>("overview");
  const [period, setPeriod] = useState<PeriodKey>(data.period.key);
  const [problem, setProblem] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const [entered, setEntered] = useState(false);
  const [loadedAt, setLoadedAt] = useState(() => Date.now());
  const root = useRef<HTMLDivElement>(null);
  const bento = useRef<HTMLDivElement>(null);
  const peso = useMemo(() => makeFormat(org).peso, [org]);

  const view = data.views[tab] ?? data.views.overview!;
  const shownTab: AreaKey = data.views[tab] ? tab : "overview";
  const keys = (shownTab === "overview" && picks ? picks.filter((k) => data.cards[k]) : view.cards).slice(0, MAX_CARDS);
  const placed = place(keys.map((key) => ({ key, wide: isWide(key) })));
  const rows = keys.length > 1 ? 2 : 1;

  // Pictures animate in once, for each view.
  useEffect(() => {
    setEntered(false);
    let second = 0;
    const first = requestAnimationFrame(() => {
      second = requestAnimationFrame(() => setEntered(true));
    });
    return () => {
      cancelAnimationFrame(first);
      cancelAnimationFrame(second);
    };
  }, [shownTab, data]);

  // The rows end at the window's bottom when they can. Stacked layouts keep their own height.
  useLayoutEffect(() => {
    const fit = () => {
      const b = bento.current;
      if (!b) return;
      if (getComputedStyle(b).gridTemplateColumns.split(" ").length < 4) {
        b.style.removeProperty("--row");
        return;
      }
      const room = window.innerHeight - (b.getBoundingClientRect().top + window.scrollY) - BOTTOM - GAP * (rows - 1);
      b.style.setProperty("--row", `${Math.max(MIN_ROW, Math.min(rows === 1 ? MAX_SOLO : MAX_ROW, Math.floor(room / rows)))}px`);
    };
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, [rows, shownTab, data]);

  function pick(next: PeriodKey) {
    if (next === period) return;
    setPeriod(next);
    setProblem(null);
    start(async () => {
      const found = await overviewFor(next);
      if (found.ok) {
        setData(found.data);
        setLoadedAt(Date.now());
      } else {
        setProblem(found.error);
        setPeriod(period);
      }
    });
  }

  const ctx: Ctx = { data, peso, loadedAt, prices, othersOnly: view.othersOnly };
  const suggested = data.views.overview!.cards;
  const tabs = TABS.filter(([k]) => data.views[k]);
  return (
    <div ref={root} className={s.root}>
      <div className={s.ctl}>
        <nav className={s.tabs} aria-label="Areas you can see">
          {tabs.map(([k, label]) => {
            const n = data.counts[k] ?? 0;
            return (
              <button suppressHydrationWarning key={k} type="button" className={s.tab} aria-pressed={k === shownTab} aria-label={n ? `${label}, ${pl(n, "item")} waiting for you` : undefined} onClick={() => setTab(k)}>
                {label}
                {n > 0 && <span className={s.tabN} aria-hidden>{n}</span>}
              </button>
            );
          })}
        </nav>
        <div className={s.seg} role="group" aria-label="Period">
          {PERIODS.map(([k, label]) => (
            <button suppressHydrationWarning key={k} type="button" aria-pressed={k === period} onClick={() => pick(k)}>
              {label}
            </button>
          ))}
        </div>
      </div>
      {problem && <p className={s.problem} role="alert">{problem}</p>}
      <div ref={bento} className={`${s.bento} ${entered ? "" : s.pre} ${pending ? s.busy : ""}`} aria-live="polite">
        <LeadFor lead={data.leads[view.lead]} ctx={ctx} span={s[placed.lead]} />
        {placed.cards.map((c, i) => (
          <CardFor key={c.key} cardKey={c.key} ctx={ctx} span={s[placed.spans[i]]} index={i} />
        ))}
      </div>
      <HoverTip root={root} />
      {editing && <EditPanel suggested={suggested} />}
    </div>
  );
}
