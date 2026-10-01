import type { Org } from "./types";

// Money, dates and times belong to the company, not to Bishnoi One: its timezone
// decides what "today" means, its locale how a date reads, its currency and
// its minor units how money prints. Build a set of these with makeFormat(org)
// wherever the company is in reach — a server component has it from getMe(),
// a client component is handed it as a prop.

/** Where Bishnoi One started, for the few call sites that can't reach the company. */
const FALLBACK = { currency: "PHP", locale: "en-PH", timezone: "Asia/Manila", minorUnits: 2 };

type Company = Pick<Org, "currency" | "locale" | "timezone"> & { minorUnits?: number | null };

// Intl refuses a locale, a zone or a currency it doesn't know, and one crooked
// company record must not take every page down with it. Anything it won't take
// is shown the way Bishnoi One's first company saw it.
function dates(locale: string, timeZone: string, options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  try {
    return new Intl.DateTimeFormat(locale, { timeZone, ...options });
  } catch {
    // Most likely a zone nobody has heard of. Keep the wording and only move the
    // clock, or the YYYY-MM-DD keys the app compares would come back as dates.
    try {
      return new Intl.DateTimeFormat(locale, { timeZone: FALLBACK.timezone, ...options });
    } catch {
      return new Intl.DateTimeFormat(FALLBACK.locale, { timeZone: FALLBACK.timezone, ...options });
    }
  }
}

function amounts(locale: string, currency: string, options: Intl.NumberFormatOptions): Intl.NumberFormat {
  try {
    return new Intl.NumberFormat(locale, { style: "currency", currency, ...options });
  } catch {
    return new Intl.NumberFormat(FALLBACK.locale, { style: "currency", currency: FALLBACK.currency, ...options });
  }
}

function counts(locale: string): Intl.NumberFormat {
  try {
    return new Intl.NumberFormat(locale);
  } catch {
    return new Intl.NumberFormat(FALLBACK.locale);
  }
}

function daysBetween(fromKey: string, toKey: string): number {
  return Math.round((Date.parse(toKey) - Date.parse(fromKey)) / 86_400_000);
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** 1250 basis points -> "12.5%". A rate is a rate in any country, so no company setting reaches this. */
export function percent(bp: number): string {
  return `${bp / 100}%`;
}

const HUNDREDTHS = /^(\d{1,12})(?:\.(\d{0,2}))?$/;

/** "12.5" (percent) -> 1250 basis points. Null when it isn't a number with at most two decimals. */
export function toBasisPoints(text: string): number | null {
  const m = text.replace(/[%\s]/g, "").match(HUNDREDTHS);
  return m ? Number(m[1]) * 100 + Number((m[2] ?? "").padEnd(2, "0")) : null;
}

/** For an input's starting value: 1250 -> "12.5". */
export function percentText(bp: number | null | undefined): string {
  return bp == null ? "" : String(bp / 100);
}

/** Everything that reads differently from one company to the next. */
export function makeFormat(company: Company) {
  const locale = company.locale || FALLBACK.locale;
  const timeZone = company.timezone || FALLBACK.timezone;
  const currency = company.currency || FALLBACK.currency;
  // How many decimal places the currency keeps: two for pesos, none for yen.
  const minorUnits = company.minorUnits ?? FALLBACK.minorUnits;
  const whole = 10 ** minorUnits;

  // YYYY-MM-DD is a key the app compares and sends to the API, never something
  // a person reads, so it stays en-CA whatever the company's locale is.
  const dayKey = dates("en-CA", timeZone, { year: "numeric", month: "2-digit", day: "2-digit" });
  // A calendar date carries no time of day, so it's read back in UTC: then no
  // timezone can nudge "the 20th" into the 19th on its way to the screen.
  const onDate = (options: Intl.DateTimeFormatOptions) => dates(locale, "UTC", options);
  const shortDate = onDate({ month: "short", day: "numeric" });
  const shortDateYear = onDate({ month: "short", day: "numeric", year: "numeric" });
  const weekdayDate = onDate({ weekday: "short", month: "short", day: "numeric" });
  const monthLong = onDate({ month: "long" });
  // An instant, on the other hand, is whatever the company's own clocks said.
  const atDate = dates(locale, timeZone, { month: "short", day: "numeric" });
  const atDateYear = dates(locale, timeZone, { month: "short", day: "numeric", year: "numeric" });
  const time = dates(locale, timeZone, { hour: "numeric", minute: "2-digit" });
  const hour = dates("en-GB", timeZone, { hour: "numeric", hourCycle: "h23" });

  const amount = amounts(locale, currency, { minimumFractionDigits: minorUnits, maximumFractionDigits: minorUnits });
  const amountShort = amounts(locale, currency, { notation: "compact", maximumFractionDigits: 1 });
  const grouped = counts(locale);
  const decimals = new RegExp(`^(\\d{1,12})(?:\\.(\\d{0,${minorUnits}}))?$`);

  /** YYYY-MM-DD for "today" where the company is. */
  const todayKey = (now = new Date()): string => dayKey.format(now);

  return {
    locale,
    timeZone,
    currency,
    minorUnits,
    todayKey,

    /** The currency's mark on its own ("₱"), for the adornment beside an amount field. */
    symbol: amount.formatToParts(0).find((p) => p.type === "currency")?.value ?? currency,

    /** A due date ("2026-09-20") in words relative to today. */
    dueLabel(dueOn: string, today = todayKey()): string {
      const diff = daysBetween(today, dueOn);
      if (diff === 0) return "Today";
      if (diff === 1) return "Tomorrow";
      if (diff === -1) return "Yesterday";
      if (diff < 0) return `${-diff} days late`;
      return (diff < 7 ? weekdayDate : shortDate).format(new Date(`${dueOn}T00:00:00Z`));
    },

    /** When something happened: "Today, 2:15 PM", "Yesterday", "Sep 12". */
    whenLabel(iso: string | null, today = todayKey()): string {
      if (!iso) return "—";
      const at = new Date(iso);
      const diff = daysBetween(dayKey.format(at), today);
      if (diff === 0) return `Today, ${time.format(at)}`;
      if (diff === 1) return `Yesterday, ${time.format(at)}`;
      if (diff < 7) return `${diff} days ago`;
      const sameYear = today.slice(0, 4) === dayKey.format(at).slice(0, 4);
      return (sameYear ? atDate : atDateYear).format(at);
    },

    greeting(now = new Date()): string {
      const h = Number(hour.format(now));
      return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
    },

    /** A calendar date ("2026-09-20") as "Sep 20, 2026". */
    dateLabel(key: string): string {
      return shortDateYear.format(new Date(`${key}T00:00:00Z`));
    },

    /** A month ("2026-09") by name: "September". */
    monthLabel(month: string): string {
      return monthLong.format(new Date(`${month}-01T00:00:00Z`));
    },

    /** A date built to whatever shape a page asks for, in the company's locale and zone. */
    on(options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
      return dates(locale, options.timeZone ?? timeZone, options);
    },

    // The four money ones are still named for the peso Bishnoi One was born with;
    // renaming them would touch a dozen screens for no one's benefit. What they
    // print is the company's own currency, to however many places it keeps.

    /** Money travels as whole minor units and is only turned into currency to show it. */
    peso(minor: number): string {
      return amount.format(minor / whole);
    },

    /** 1.2M, 48K: for figures where the exact minor unit doesn't matter. */
    pesoCompact(minor: number): string {
      return amountShort.format(minor / whole);
    },

    /** A plain number with the company's grouping: 12000 -> "12,000". */
    count(n: number): string {
      return grouped.format(n);
    },

    /** What someone typed into an amount field -> whole minor units. Null when the currency can't hold it. */
    toCentavos(text: string): number | null {
      // Everything but digits and the point goes: the currency mark, thousands
      // separators and the spaces people leave while typing.
      const m = text.replace(/[^\d.]/g, "").match(decimals);
      if (!m) return null;
      return Number(m[1]) * whole + Number((m[2] ?? "").padEnd(minorUnits, "0") || "0");
    },

    /** For an amount field's starting value: 125050 -> "1250.50". */
    pesosText(minor: number | null | undefined): string {
      return minor == null ? "" : (minor / whole).toFixed(minorUnits);
    },

    plural,
    percent,
    toBasisPoints,
    percentText,
  };
}

export type Format = ReturnType<typeof makeFormat>;

// The same functions for the call sites that can't reach the company. They show
// Bishnoi One's first company's pesos and Manila time, so nothing ever goes blank; as
// each of those screens finds its way to the company, it moves off these.
const fallback = makeFormat(FALLBACK);

export const { todayKey, dueLabel, whenLabel, greeting, dateLabel, monthLabel, peso, pesoCompact, toCentavos, pesosText } = fallback;
