"use client";

import { Pill } from "./figures";
import { Gauge, GaugeArc, GaugeText, GaugeTrack, GaugeValue, GaugeZones } from "./gauge";

/**
 * One measure read against a known scale with a good, a watch and a bad
 * band (uptime, how fast the API answers, how many requests fail): a half
 * dial drawn with Gauge UI (./gauge). The bands are a thin ring outside the
 * dial; the value is the ink arc and the number in the middle; the word under
 * it (Good, Watch, Bad) says the same thing without the colour, so it reads
 * in print and for colour-blind eyes too. Counts with no good or bad level
 * (companies, users) are figures, not gauges.
 */

const GOOD = "#a8d69b"; // --color-sage
const WATCH = "#e5b45a"; // a softer --color-due-today
const BAD = "#e4877f"; // a softer --color-danger
const INK = "#141414";

export type Bands = {
  /** Where good ends and watch begins, and where watch ends and bad begins, in the gauge's units. */
  good: number;
  bad: number;
  /** Uptime: higher is better. Answer time, failures: lower is better. */
  higherIsBetter: boolean;
};

export type Reading = "good" | "watch" | "bad";

export function readingOf(value: number, bands: Bands): Reading {
  if (bands.higherIsBetter) return value >= bands.good ? "good" : value >= bands.bad ? "watch" : "bad";
  return value <= bands.good ? "good" : value <= bands.bad ? "watch" : "bad";
}

const WORDS: Record<Reading, { text: string; tone: "good" | "warn" | "bad" }> = {
  good: { text: "Good", tone: "good" },
  watch: { text: "Watch", tone: "warn" },
  bad: { text: "Needs attention", tone: "bad" },
};

export function HealthGauge({
  label,
  value,
  min = 0,
  max,
  bands,
  format,
  note,
  empty = "No data yet",
}: {
  label: string;
  /** Null when there's nothing to read yet (no checks, no requests). */
  value: number | null;
  min?: number;
  max: number;
  bands: Bands;
  format: (value: number) => string;
  /** One line under the label: the scale, or where the number comes from. */
  note?: string;
  empty?: string;
}) {
  const zones = bands.higherIsBetter
    ? [
        { to: bands.bad, color: BAD },
        { to: bands.good, color: WATCH },
        { to: max, color: GOOD },
      ]
    : [
        { to: bands.good, color: GOOD },
        { to: bands.bad, color: WATCH },
        { to: max, color: BAD },
      ];
  const shown = value == null ? min : Math.min(max, Math.max(min, value));
  const reading = value == null ? null : readingOf(value, bands);
  return (
    <figure className="flex min-w-0 flex-col items-center text-center">
      <div className="w-full max-w-[13rem]">
        <Gauge
          value={shown}
          min={min}
          max={max}
          startAngle={90}
          endAngle={270}
          radius={100}
          padding={22}
          fit="content"
          transition
          initialValue={min}
          role="img"
          aria-label={value == null ? `${label}: ${empty}` : `${label}: ${format(value)}, ${WORDS[reading!].text.toLowerCase()}`}
        >
          <GaugeZones zones={zones} width={6} offset={16} gap={2} cap="round" />
          <GaugeTrack width={16} color={INK} opacity={0.08} />
          {value != null && <GaugeArc width={16} color={INK} />}
          {value == null ? (
            <GaugeText y={-14} fontSize={20} color="#6a6a6a" weight="medium">
              {empty}
            </GaugeText>
          ) : (
            <GaugeValue y={-12} fontSize={44} color={INK} format={format} />
          )}
        </Gauge>
      </div>
      <figcaption className="mt-1 min-w-0">
        <span className="block text-sm font-medium text-ink">{label}</span>
        {note && <span className="block text-meta text-ink-3">{note}</span>}
        {reading && (
          <Pill tone={WORDS[reading].tone} className="mt-1.5">
            {WORDS[reading].text}
          </Pill>
        )}
      </figcaption>
    </figure>
  );
}
