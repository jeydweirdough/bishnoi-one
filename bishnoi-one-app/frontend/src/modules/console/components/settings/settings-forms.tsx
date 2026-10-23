"use client";

import { useState, useTransition, type ReactNode } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/console/platform/ui/button";
import { Choice, Field, FormError, Input } from "@/src/modules/console/platform/ui/field";
import type { IconName } from "@/src/modules/console/platform/ui/icons";
import { SectionTitle, Sheet } from "@/src/modules/console/platform/ui/sheet";
import { saveSettings } from "@/src/modules/console/actions/platform";
import { SEVERITIES } from "@/src/modules/console/lib/words";
import type { IncidentSeverity, PlatformSettings, Severity } from "@/src/modules/console/lib/types";

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
      intro="The platform name, support contact and time zone."
      readOnly={readOnly}
      pending={pending}
      error={error}
      onSave={() =>
        save(
          { name: v.name.trim(), supportEmail: v.supportEmail.trim() || null, timezone: v.timezone.trim() },
          "Applied to every screen.",
        )
      }
    >
      <Field label="Name" error={fields.name} hint="Shown on the console and in platform emails.">
        {(p) => <Input {...p} value={v.name} onChange={set("name")} maxLength={60} />}
      </Field>
      <Field label="Support email" optional error={fields.supportEmail} hint="Where users send support requests.">
        {(p) => <Input {...p} type="email" value={v.supportEmail} onChange={set("supportEmail")} maxLength={254} />}
      </Field>
      <Field label="Time zone" error={fields.timezone} className="sm:col-span-2" hint="Used for dates and times across the platform.">
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
      intro="Health check settings and the thresholds for degraded and down."
      readOnly={readOnly}
      pending={pending}
      error={error}
      onSave={submit}
    >
      <Field label="Check interval (seconds)" error={fields.staleSeconds} hint="A check older than this is stale and a new one runs. 15 to 3,600.">
        {(p) => <Input {...p} inputMode="numeric" value={v.staleSeconds} onChange={set("staleSeconds")} />}
      </Field>
      <Field label="Timeout (seconds)" error={fields.timeoutSeconds} hint="An application that takes longer is marked down. 1 to 15.">
        {(p) => <Input {...p} inputMode="numeric" value={v.timeoutSeconds} onChange={set("timeoutSeconds")} />}
      </Field>
      <Field label="Slow response threshold (ms)" error={fields.slowMs} hint="An application that responds slower than this is marked degraded. 100 to 15,000.">
        {(p) => <Input {...p} inputMode="numeric" value={v.slowMs} onChange={set("slowMs")} />}
      </Field>
      <Field label="History retention (days)" error={fields.keepDays} hint="Health checks and traffic older than this are deleted. 1 to 365.">
        {(p) => <Input {...p} inputMode="numeric" value={v.keepDays} onChange={set("keepDays")} />}
      </Field>
    </SectionSheet>
  );
}

const BANNER: { value: IncidentSeverity; label: string }[] = [
  { value: "critical", label: "Critical only" },
  { value: "major", label: "Major and critical" },
  { value: "minor", label: "All active incidents" },
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
    save({ responseHours, bannerSeverity: banner }, "Overdue tickets and the banner now use these settings.", found);
  }

  return (
    <SectionSheet
      title="Notifications"
      icon="support"
      intro="Ticket response targets, and which incidents appear in the banner on every screen."
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
        <Choice name="bannerSeverity" legend="Incident banner" value={banner} onChange={setBanner} options={BANNER} />
        <p className={`mt-1 text-meta ${fields.bannerSeverity ? "text-danger" : "text-ink-3"}`}>
          {fields.bannerSeverity ?? "While one is active, it is shown at the top of every staff screen."}
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
      intro="Session length and sign-in lockout."
      readOnly={readOnly}
      pending={pending}
      error={error}
      onSave={submit}
    >
      <Field
        label="Session length (hours)"
        error={fields.sessionHours}
        className="sm:col-span-2"
        hint="1 to 168. Applies to new sign-ins; current sessions are not affected."
      >
        {(p) => <Input {...p} inputMode="numeric" value={v.sessionHours} onChange={set("sessionHours")} />}
      </Field>
      <Field label="Failed sign-ins before lockout" error={fields.loginAttempts} hint="3 to 20, per email.">
        {(p) => <Input {...p} inputMode="numeric" value={v.loginAttempts} onChange={set("loginAttempts")} />}
      </Field>
      <Field label="Lockout duration (minutes)" error={fields.lockoutMinutes} hint="How long before the user can try again. 1 to 240.">
        {(p) => <Input {...p} inputMode="numeric" value={v.lockoutMinutes} onChange={set("lockoutMinutes")} />}
      </Field>
    </SectionSheet>
  );
}
