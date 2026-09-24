"use client";

import { useState, useTransition, type ReactNode } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Choice, Field, FormError, Input } from "@/src/platform/ui/field";
import type { IconName } from "@/src/platform/ui/icons";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { saveSettings } from "../../actions/platform";
import { SEVERITIES } from "../../lib/words";
import type { IncidentSeverity, PlatformSettings, Severity } from "../../lib/types";

// The four sections of Settings, each its own form that saves on its own.
// For Support they are the same fields, read-only, with no save button.

type Section = keyof PlatformSettings;

const ZONES = ["Asia/Manila", "Asia/Singapore", "Asia/Hong_Kong", "Asia/Jakarta", "Asia/Bangkok", "Asia/Tokyo", "Australia/Sydney", "Europe/London", "America/New_York", "UTC"];

/** Saving one section: the pending state, and what was wrong, whether found here
 *  (a number that isn't one) or by the API. */
function useSave<K extends Section>(section: K) {
  const [pending, start] = useTransition();
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  function save(value: PlatformSettings[K], success: string, found: Record<string, string> = {}) {
    if (Object.keys(found).length) {
      setError(null);
      return setFields(found);
    }
    start(async () => {
      const r = await saveSettings(section, value);
      if (!r.ok) {
        setError(r.fields && Object.keys(r.fields).length ? null : r.error);
        setFields(r.fields ?? {});
        return;
      }
      setError(null);
      setFields({});
      toast.success("Saved", { description: success });
    });
  }
  return { pending, fields, error, save };
}

/** A whole number within its bounds, or the words for what's wrong. */
function whole(text: string, min: number, max: number, found: Record<string, string>, key: string): number {
  const n = Number(text);
  if (!text.trim() || !Number.isInteger(n) || n < min || n > max) found[key] = `A whole number from ${min} to ${max}.`;
  return n;
}

function SectionSheet({
  title,
  icon,
  intro,
  readOnly,
  pending,
  error,
  onSave,
  children,
}: {
  title: string;
  icon: IconName;
  intro: ReactNode;
  readOnly: boolean;
  pending: boolean;
  error: string | null;
  onSave: () => void;
  children: ReactNode;
}) {
  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        if (!readOnly) onSave();
      }}
    >
      <Sheet className="px-5 pt-4 pb-5">
        <SectionTitle icon={icon}>{title}</SectionTitle>
        <p className="text-meta text-ink-3">{intro}</p>
        <fieldset disabled={readOnly} className="mt-4 grid min-w-0 gap-5 sm:grid-cols-2">
          {children}
        </fieldset>
        {!readOnly && (
          <div className="mt-5">
            <FormError message={error} />
            <Button type="submit" variant="primary" loading={pending} className="mt-2">
              Save {title.toLowerCase()} settings
            </Button>
          </div>
        )}
      </Sheet>
    </form>
  );
}

export function PlatformForm({ initial, readOnly }: { initial: PlatformSettings["platform"]; readOnly: boolean }) {
  const { pending, fields, error, save } = useSave("platform");
  const [v, setV] = useState({ name: initial.name, supportEmail: initial.supportEmail ?? "", timezone: initial.timezone });
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value });

  return (
    <SectionSheet
      title="Platform"
      icon="company"
      intro="What the platform calls itself, where people write for help, and the time zone its times are shown in."
      readOnly={readOnly}
      pending={pending}
      error={error}
      onSave={() =>
        save(
          { name: v.name.trim(), supportEmail: v.supportEmail.trim() || null, timezone: v.timezone.trim() },
          "Every screen uses them from now on.",
        )
      }
    >
      <Field label="Name" error={fields.name} hint="Shown on the console and in what the platform sends.">
        {(p) => <Input {...p} value={v.name} onChange={set("name")} maxLength={60} />}
      </Field>
      <Field label="Support email" optional error={fields.supportEmail} hint="Where people write when something is wrong.">
        {(p) => <Input {...p} type="email" value={v.supportEmail} onChange={set("supportEmail")} maxLength={254} />}
      </Field>
      <Field label="Time zone" error={fields.timezone} className="sm:col-span-2" hint="What counts as today, and how times are written.">
        {(p) => (
          <>
            <Input {...p} value={v.timezone} onChange={set("timezone")} list="settings-zones" />
            <datalist id="settings-zones">
              {ZONES.map((z) => (
                <option key={z} value={z} />
              ))}
            </datalist>
          </>
        )}
      </Field>
    </SectionSheet>
  );
}

export function MonitoringForm({ initial, readOnly }: { initial: PlatformSettings["monitoring"]; readOnly: boolean }) {
  const { pending, fields, error, save } = useSave("monitoring");
  const [v, setV] = useState({
    staleSeconds: String(initial.staleSeconds),
    timeoutSeconds: String(initial.timeoutSeconds),
    slowMs: String(initial.slowMs),
    keepDays: String(initial.keepDays),
  });
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value });

  function submit() {
    const found: Record<string, string> = {};
    const value = {
      staleSeconds: whole(v.staleSeconds, 15, 3600, found, "staleSeconds"),
      timeoutSeconds: whole(v.timeoutSeconds, 1, 15, found, "timeoutSeconds"),
      slowMs: whole(v.slowMs, 100, 15000, found, "slowMs"),
      keepDays: whole(v.keepDays, 1, 365, found, "keepDays"),
    };
    save(value, "The next health check uses them.", found);
  }

  return (
    <SectionSheet
      title="Monitoring"
      icon="monitoring"
      intro="How the platform checks that each application answers, and what counts as slow or down."
      readOnly={readOnly}
      pending={pending}
      error={error}
      onSave={submit}
    >
      <Field label="Check again after (seconds)" error={fields.staleSeconds} hint="A check older than this is out of date, and the next look runs a new one. 15 to 3,600.">
        {(p) => <Input {...p} inputMode="numeric" value={v.staleSeconds} onChange={set("staleSeconds")} />}
      </Field>
      <Field label="Wait for an answer (seconds)" error={fields.timeoutSeconds} hint="An application that takes longer counts as down. 1 to 15.">
        {(p) => <Input {...p} inputMode="numeric" value={v.timeoutSeconds} onChange={set("timeoutSeconds")} />}
      </Field>
      <Field label="Slow after (ms)" error={fields.slowMs} hint="An application that answers slower than this is marked degraded. 100 to 15,000.">
        {(p) => <Input {...p} inputMode="numeric" value={v.slowMs} onChange={set("slowMs")} />}
      </Field>
      <Field label="Keep history for (days)" error={fields.keepDays} hint="Health checks and traffic older than this are cleared away. 1 to 365.">
        {(p) => <Input {...p} inputMode="numeric" value={v.keepDays} onChange={set("keepDays")} />}
      </Field>
    </SectionSheet>
  );
}

const BANNER: { value: IncidentSeverity; label: string }[] = [
  { value: "critical", label: "Critical only" },
  { value: "major", label: "Major and critical" },
  { value: "minor", label: "Every active incident" },
];

export function NotificationsForm({ initial, readOnly }: { initial: PlatformSettings["notifications"]; readOnly: boolean }) {
  const { pending, fields, error, save } = useSave("notifications");
  const levels = Object.keys(SEVERITIES) as Severity[];
  const [hours, setHours] = useState<Record<Severity, string>>(
    Object.fromEntries(levels.map((s) => [s, String(initial.responseHours[s])])) as Record<Severity, string>,
  );
  const [banner, setBanner] = useState<IncidentSeverity>(initial.bannerSeverity);

  function submit() {
    const found: Record<string, string> = {};
    const responseHours = Object.fromEntries(levels.map((s) => [s, whole(hours[s], 1, 720, found, s)])) as Record<Severity, number>;
    save({ responseHours, bannerSeverity: banner }, "Overdue tickets and the banner follow them now.", found);
  }

  return (
    <SectionSheet
      title="Notifications"
      icon="support"
      intro="How fast each ticket should be answered, and which incidents are announced at the top of every screen."
      readOnly={readOnly}
      pending={pending}
      error={error}
      onSave={submit}
    >
      <fieldset className="grid min-w-0 gap-5 sm:col-span-2 sm:grid-cols-4">
        <legend className="mb-2 text-sm font-semibold text-ink sm:col-span-4">Response targets</legend>
        <p className="-mt-3 text-meta text-ink-3 sm:col-span-4">A ticket still open this many hours after it was reported is overdue. 1 to 720 hours.</p>
        {levels.map((s) => (
          <Field key={s} label={`${SEVERITIES[s]} (hours)`} error={fields[s]}>
            {(p) => <Input {...p} inputMode="numeric" value={hours[s]} onChange={(e) => setHours({ ...hours, [s]: e.target.value })} />}
          </Field>
        ))}
      </fieldset>
      <div className="sm:col-span-2">
        <Choice name="bannerSeverity" legend="Incidents shown on every screen" value={banner} onChange={setBanner} options={BANNER} />
        <p className={`mt-1 text-meta ${fields.bannerSeverity ? "text-danger" : "text-ink-3"}`}>
          {fields.bannerSeverity ?? "While one is active, every staff member sees it above whatever they're doing."}
        </p>
      </div>
    </SectionSheet>
  );
}

export function SecurityForm({ initial, readOnly }: { initial: PlatformSettings["security"]; readOnly: boolean }) {
  const { pending, fields, error, save } = useSave("security");
  const [v, setV] = useState({
    sessionHours: String(initial.sessionHours),
    loginAttempts: String(initial.loginAttempts),
    lockoutMinutes: String(initial.lockoutMinutes),
  });
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value });

  function submit() {
    const found: Record<string, string> = {};
    const value = {
      sessionHours: whole(v.sessionHours, 1, 168, found, "sessionHours"),
      loginAttempts: whole(v.loginAttempts, 3, 20, found, "loginAttempts"),
      lockoutMinutes: whole(v.lockoutMinutes, 1, 240, found, "lockoutMinutes"),
    };
    save(value, "A new session length applies to sign-ins from now on.", found);
  }

  return (
    <SectionSheet
      title="Security"
      icon="roles"
      intro="How long a sign-in lasts, and how many wrong passwords it takes before someone has to wait."
      readOnly={readOnly}
      pending={pending}
      error={error}
      onSave={submit}
    >
      <Field
        label="A sign-in lasts (hours)"
        error={fields.sessionHours}
        className="sm:col-span-2"
        hint="1 to 168. A new length applies to sign-ins from now on; anyone already signed in keeps theirs."
      >
        {(p) => <Input {...p} inputMode="numeric" value={v.sessionHours} onChange={set("sessionHours")} />}
      </Field>
      <Field label="Wrong passwords before a wait" error={fields.loginAttempts} hint="3 to 20, for one email.">
        {(p) => <Input {...p} inputMode="numeric" value={v.loginAttempts} onChange={set("loginAttempts")} />}
      </Field>
      <Field label="Wait (minutes)" error={fields.lockoutMinutes} hint="How long before they can try again. 1 to 240.">
        {(p) => <Input {...p} inputMode="numeric" value={v.lockoutMinutes} onChange={set("lockoutMinutes")} />}
      </Field>
    </SectionSheet>
  );
}
