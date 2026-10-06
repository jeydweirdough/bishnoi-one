import type { ReactNode } from "react";

// The drawings an empty list shows, one for each kind of thing (the components
// page's look: ink lines, sage fills, a mint shadow, a dashed arc). Picked by
// the icon the screen already names, so each empty state reads as its own.

const INK = "#141414";
const SAGE = "#a8d69b";
const line = { stroke: INK, strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

const chart = (
  <>
    <rect x="24" y="16" width="72" height="60" rx="9" fill="#fff" {...line} />
    <rect x="36" y="50" width="10" height="16" rx="2" fill={SAGE} {...line} />
    <rect x="53" y="40" width="10" height="26" rx="2" fill={SAGE} {...line} />
    <rect x="70" y="30" width="10" height="36" rx="2" fill={SAGE} {...line} />
    <path d="M34 40l14-8 14 4 18-12" fill="none" {...line} />
  </>
);
const people = (
  <>
    <circle cx="48" cy="36" r="12" fill="#fff" {...line} />
    <path d="M26 74c2-14 11-21 22-21s20 7 22 21z" fill={SAGE} {...line} />
    <circle cx="78" cy="40" r="9" fill="#fff" {...line} />
    <path d="M66 74c1-10 6-16 13-16s13 6 14 16z" fill="#fff" {...line} />
  </>
);
const calendar = (
  <>
    <rect x="26" y="18" width="68" height="60" rx="8" fill="#fff" {...line} />
    <path d="M26 32h68M40 12v12M80 12v12" fill="none" {...line} />
    <rect x="38" y="42" width="10" height="9" rx="2" fill={SAGE} {...line} />
    <path d="M56 46h22M40 62h12M58 62h20" fill="none" {...line} />
  </>
);
const doc = (
  <>
    <path d="M32 14h40l16 16v48H32z" fill="#fff" {...line} />
    <path d="M72 14v16h16" fill="none" {...line} />
    <path d="M42 40h34M42 50h34M42 60h20" fill="none" {...line} />
    <circle cx="84" cy="68" r="11" fill={SAGE} {...line} />
    <path d="M84 63v10M79 68h10" fill="none" {...line} />
  </>
);
const receipt = (
  <>
    <path d="M34 14h52v62l-6-5-7 5-7-5-6 5-7-5-6 5-7-5-6 5z" fill="#fff" {...line} />
    <path d="M44 28h32M44 38h24M44 48h28" fill="none" {...line} />
    <rect x="44" y="56" width="32" height="8" rx="3" fill={SAGE} {...line} />
  </>
);
const box = (
  <>
    <path d="M60 18 92 32v32L60 78 28 64V32z" fill="#fff" {...line} />
    <path d="M28 32l32 14 32-14M60 46v32" fill="none" {...line} />
    <path d="M44 25l32 14v10" fill="none" {...line} />
    <path d="M60 46 92 32v32L60 78z" fill={SAGE} {...line} />
  </>
);
const tag = (
  <>
    <path d="M30 22h30l30 30-26 26-34-34z" fill="#fff" {...line} />
    <circle cx="44" cy="36" r="6" fill={SAGE} {...line} />
    <path d="M58 52l12 12M64 46l12 12" fill="none" {...line} />
  </>
);
const envelope = (
  <>
    <rect x="22" y="24" width="76" height="52" rx="8" fill="#fff" {...line} />
    <path d="M24 28l36 26 36-26" fill="none" {...line} />
    <path d="M60 54 96 28v4L60 58 24 32v-4z" fill={SAGE} {...line} />
  </>
);
const pulse = (
  <>
    <rect x="22" y="20" width="76" height="54" rx="10" fill="#fff" {...line} />
    <path d="M30 50h14l6-14 10 26 8-18 6 6h16" fill="none" {...line} />
    <circle cx="90" cy="50" r="5" fill={SAGE} {...line} />
  </>
);
const picture = (
  <>
    <rect x="24" y="18" width="72" height="58" rx="8" fill="#fff" {...line} />
    <circle cx="44" cy="36" r="6" fill={SAGE} {...line} />
    <path d="M26 70l22-20 14 12 12-10 20 18" fill="none" {...line} />
  </>
);
const coins = (
  <>
    <ellipse cx="52" cy="62" rx="22" ry="8" fill={SAGE} {...line} />
    <path d="M30 62v-10c0 4 10 8 22 8s22-4 22-8v10" fill="#fff" {...line} />
    <ellipse cx="52" cy="50" rx="22" ry="8" fill="#fff" {...line} />
    <circle cx="80" cy="34" r="14" fill="#fff" {...line} />
    <path d="M80 27v14M75 31h8a3 3 0 0 1 0 6h-6" fill="none" {...line} />
  </>
);
const search = (
  <>
    <circle cx="54" cy="44" r="22" fill="#fff" {...line} />
    <circle cx="54" cy="44" r="13" fill={SAGE} {...line} />
    <path d="M70 60l18 18" fill="none" stroke={INK} strokeWidth="5" strokeLinecap="round" />
  </>
);
const tray = (
  <>
    <path d="M24 50l12-28h48l12 28v22a6 6 0 0 1-6 6H30a6 6 0 0 1-6-6z" fill="#fff" {...line} />
    <path d="M24 50h22l4 8h20l4-8h22" fill={SAGE} {...line} />
  </>
);

const gauge = (
  <>
    <path d="M22 66a38 38 0 0 1 76 0z" fill="#fff" {...line} />
    <path d="M30 66a30 30 0 0 1 22-29" fill="none" stroke={SAGE} strokeWidth="8" strokeLinecap="round" />
    <path d="M60 66 78 42" fill="none" stroke={INK} strokeWidth="3" strokeLinecap="round" />
    <circle cx="60" cy="66" r="5" fill={INK} />
  </>
);
const steps = (
  <>
    <rect x="22" y="56" width="22" height="20" rx="3" fill={SAGE} {...line} />
    <rect x="49" y="42" width="22" height="34" rx="3" fill="#fff" {...line} />
    <rect x="76" y="26" width="22" height="50" rx="3" fill="#fff" {...line} />
    <path d="M33 48v-6M60 34v-6M87 18v-4" fill="none" {...line} />
  </>
);
const flag = (
  <>
    <path d="M40 16v62" fill="none" stroke={INK} strokeWidth="3" strokeLinecap="round" />
    <path d="M42 18h40l-8 12 8 12H42z" fill={SAGE} {...line} />
    <path d="M30 78h22" fill="none" {...line} />
  </>
);

const BY_ICON: Record<string, ReactNode> = {
  // results and progress
  deals: chart, trend: chart, goals: chart, reports: chart, overview: chart, salesDivision: chart, reps: chart, worthACall: chart,
  // people
  customers: people, people, teams: people, roles: people, person: people, profile: people, account: people, addRole: people, companies: people, company: people, headquarters: people, divisions: people, hr: people,
  // dates and to-dos
  calendar, followUps: calendar, visit: calendar, task: calendar, goingQuiet: calendar,
  // papers
  quotes: receipt, orders: receipt, letters: doc, approvals: doc, note: doc, particulars: doc, history: doc, auditLog: doc, regulatory: doc, inlicensing: doc, logActivity: doc,
  // goods
  products: box, bundles: box, inventory: box, dispatch: box,
  // prices and money
  pricing: tag, promos: tag, lists: tag, money: coins, payments: coins, finance: coins, bid: coins, retention: coins,
  // talking
  email: envelope, message: envelope, call: pulse, activity: pulse,
  // the rest
  apps: picture, external: picture, settings: tray, inbox: tray, home: tray, exec: chart, password: tray,
  search, gauge, steps, flag,
};

/** The drawing for an empty state that names this icon; an empty tray for anything else. */
export function EmptyDrawing({ icon, className }: { icon: string; className?: string }) {
  return (
    <svg viewBox="0 0 120 92" className={className} aria-hidden>
      <ellipse cx="60" cy="85" rx="44" ry="5" fill="#e3eedf" />
      {BY_ICON[icon] ?? tray}
      <path d="M102 24c8 4 10 14 4 20" fill="none" stroke="#7fb070" strokeWidth="2" strokeLinecap="round" strokeDasharray="3 5" />
    </svg>
  );
}
