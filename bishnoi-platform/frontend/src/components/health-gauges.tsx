"use client";

import { HealthGauge, type Bands } from "@/src/platform/ui/health-gauge";

// The platform's health in three gauges, each read against its own scale
// (src/platform/ui/health-gauge.tsx). The same three on the dashboard and on
// Monitoring; an application's page uses the first two for itself.

/** Up 99% of the time or more is good; under 95% needs attention. On a 90 to 100% scale. */
export const UPTIME: Bands = { good: 99, bad: 95, higherIsBetter: true };
/** Under half of "slow" is good; over "slow" needs attention. On a scale of twice "slow". */
export const answerBands = (slowMs: number): Bands => ({ good: slowMs / 2, bad: slowMs, higherIsBetter: false });
/** Under 1% failing is good; over 5% needs attention. On a 0 to 10% scale. */
export const FAILED: Bands = { good: 1, bad: 5, higherIsBetter: false };

const percent = (v: number) => `${v.toFixed(v >= 99.95 || v === 0 ? 0 : 1)}%`;
const ms = (v: number) => (v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${Math.round(v)} ms`);

export function UptimeGauge({ value, note }: { value: number | null; note?: string }) {
  return <HealthGauge label="Uptime, last 24 hours" value={value} min={90} max={100} bands={UPTIME} format={percent} note={note ?? "Good from 99%"} empty="Not checked yet" />;
}

/** What counts as slow when the API doesn't say (its Settings > Monitoring default). */
const SLOW_MS = 1500;

export function AnswerGauge({ value, slowMs: given, label = "Average response time", note }: { value: number | null; slowMs?: number | null; label?: string; note?: string }) {
  const slowMs = given && given > 0 ? given : SLOW_MS;
  return (
    <HealthGauge label={label} value={value} max={slowMs * 2} bands={answerBands(slowMs)} format={ms} note={note ?? `Slow from ${ms(slowMs)}`} empty="No requests yet" />
  );
}

export function FailedGauge({ value, note }: { value: number | null; note?: string }) {
  return <HealthGauge label="Failed requests" value={value} max={10} bands={FAILED} format={percent} note={note ?? "Good under 1%"} empty="No requests yet" />;
}

/** The monitored applications' uptime, on average: one number for "are they up". */
export function averageUptime(apps: { uptime: number | null; monitored: boolean }[]): number | null {
  const known = apps.filter((a) => a.monitored && a.uptime != null).map((a) => a.uptime as number);
  return known.length ? Math.round((known.reduce((s, v) => s + v, 0) / known.length) * 10) / 10 : null;
}

/** Uptime of the applications, how fast the Platform API answers, and how many of its requests fail. */
export function HealthGauges({ health }: { health: { slowMs: number; platformApi: { averageMs: number | null; failedPercent: number }; applications: { uptime: number | null; monitored: boolean }[] } }) {
  return (
    <div className="grid grid-cols-1 gap-x-4 gap-y-6 sm:grid-cols-3">
      <UptimeGauge value={averageUptime(health.applications)} note="The applications, on average; good from 99%" />
      <AnswerGauge value={health.platformApi.averageMs} slowMs={health.slowMs} note={`The Platform API, last 15 minutes; slow from ${ms(health.slowMs > 0 ? health.slowMs : SLOW_MS)}`} />
      <FailedGauge value={health.platformApi.averageMs == null ? null : health.platformApi.failedPercent} note="The Platform API, last 15 minutes; good under 1%" />
    </div>
  );
}
