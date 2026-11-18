"use client";

import { KeyRound, Pencil, Plus, ShieldOff, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { ago, when } from "@/src/modules/console/lib/words";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Pill } from "@/src/platform/ui/figures";
import { Icon, moduleIcon } from "@/src/platform/ui/icons";
import { Combobox, Select } from "@/src/platform/ui/pickers";
import { RowMenu } from "@/src/platform/ui/row-menu";
import { Empty, Particulars, Sheet } from "@/src/platform/ui/sheet";
import { addWatcher, removeWatcher, setPersonAppRole, setPersonModule } from "./actions";
import { moduleLabel } from "./labels";
import { usePersonActions } from "./person-dialogs";
import type { AccessData, AccessPerson, PersonPage, Watcher } from "./types";

// A person in a panel beside People (2026-10-31, after Zoho Directory's): who they are and every action on them
// at the top, then Info, Applications (each app with their role in it), Security and Activity (their own actions in
// Bishnoi One and every app, 2026-11-18).

export type PanelActivity = { id: string; at: string; app: string; text: string; fields: string[] };
/** Read on the server only when the Activity tab is open (null: not open). */
export type PanelLog = { entries: PanelActivity[]; older: string | null; unavailable: string[] } | null;

const TABS = [
  ["info", "Info"],
  ["apps", "Applications"],
  ["watchers", "Who can see them"],
  ["security", "Security"],
  ["activity", "Activity"],
] as const;
type Tab = (typeof TABS)[number][0];

const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("en-PH", { day: "numeric", month: "short", year: "numeric" }) : null);

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("");
}

export function PersonPanel({ person, row, data, activity }: { person: PersonPage; row: AccessPerson; data: AccessData; activity: PanelLog }) {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>(activity ? "activity" : "info");
  const isMe = row.id === data.meId;
  const colleagues = data.people.filter((c) => c.status === "active").map((c) => ({ id: c.id, name: c.fullName }));
  const nameOf = (id?: string | null) => data.people.find((c) => c.id === id)?.fullName ?? null;
  const a = usePersonActions(row, isMe, data.modules.map((m) => m.key), colleagues);
  const s = person.security;

  /** A menu action (with its own confirmation) from a button: said when done, the page read again. */
  async function run(item: NonNullable<typeof a.power>): Promise<boolean> {
    if (!("run" in item)) return false;
    const r = await item.run();
    if (!r.ok) {
      toast.error("error" in r ? String(r.error) : "That didn't work.");
      return false;
    }
    if ("done" in item && item.done) toast.success(item.done);
    router.refresh();
    return true;
  }

  const more = [a.invite, a.admin, a.remove].filter((x): x is NonNullable<typeof x> => x !== null);
  return (
    <Sheet className="overflow-hidden">
      {a.dialogs}
      <div className="flex items-start gap-4 px-6 pt-5">
        <span className="grid size-16 shrink-0 place-items-center rounded-full bg-hema-tint text-xl font-semibold text-ink" aria-hidden>
          {initials(person.fullName)}
        </span>
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2">
            <span className="truncate text-xl font-semibold text-ink">{person.fullName}</span>
            {person.isCompanyAdmin && <span className="rounded border border-sage-deep px-1.5 text-[0.6875rem] font-semibold tracking-wide text-sage-deep uppercase">Admin</span>}
            {a.off && <Pill tone="bad">Switched off</Pill>}
          </p>
          <p className="truncate text-sm text-ink-2">{person.email}</p>
          {person.title && <p className="truncate text-sm text-ink-3">{person.title}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {a.power &&
            ("confirm" in a.power && a.power.confirm ? (
              <ConfirmButton
                label={a.power.label}
                title={`${a.power.label}: ${person.fullName}`}
                body={a.power.confirm}
                confirmLabel={a.power.label}
                triggerVariant="danger"
                onConfirm={() => run(a.power!)}
              />
            ) : (
              <Button onClick={() => void run(a.power!)}>{a.power.label}</Button>
            ))}
          <Link href="/platform/roles/people" aria-label="Close" title="Close" className="grid size-9 place-items-center rounded-lg text-ink-3 hover:bg-bench hover:text-ink">
            <X className="size-5" aria-hidden />
          </Link>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 px-6">
        <Button size="sm" icon={<Pencil className="size-4" aria-hidden />} onClick={a.openEdit}>
          Edit
        </Button>
        <Button size="sm" icon={<KeyRound className="size-4" aria-hidden />} onClick={a.openPassword}>
          Reset password
        </Button>
        {a.twoStep && s.twoStep && (
          <ConfirmButton
            label="Reset two-step sign-in"
            title={`Reset ${person.fullName}'s two-step sign-in`}
            body={"confirm" in a.twoStep ? a.twoStep.confirm : undefined}
            confirmLabel="Reset"
            triggerSize="sm"
            icon={<ShieldOff className="size-4" aria-hidden />}
            onConfirm={() => run(a.twoStep!)}
          />
        )}
        {more.length > 0 && <RowMenu always label={`More for ${person.fullName}`} items={more} />}
      </div>

      <nav className="mt-5 flex gap-1 border-b border-rule px-6" aria-label={`About ${person.fullName}`}>
        {TABS.map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => {
              setTab(key);
              // Activity is read on the server, only for the person open and only when asked for.
              if (key === "activity" && !activity) router.push(`/platform/roles/people?person=${encodeURIComponent(row.id)}&tab=activity`, { scroll: false });
            }}
            aria-current={tab === key ? "page" : undefined}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${tab === key ? "border-ink font-semibold text-ink" : "border-transparent text-ink-3 hover:text-ink"}`}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="px-6 py-5">
        {tab === "info" && (
          <Particulars
            items={[
              ["Full name", person.fullName],
              ["Work email", person.email],
              ["Title", person.title],
              ["Reports to", nameOf(row.reportsToId)],
              ["Assistant to", nameOf(row.assistantOfId)],
              ["Status", a.off ? "Switched off" : "Active"],
              ["Company administrator", person.isCompanyAdmin ? "Yes" : "No"],
              ["Employee ID (CRM)", person.appDetails?.crm?.employeeId ?? null],
              ["Licence number (Pharmacy)", person.appDetails?.pharmacy?.licenseNo ?? null],
              ["Finance calendar", person.appDetails?.finance?.calendarOn ? "On" : "Off"],
              ["Added", person.addedAt ? `${day(person.addedAt)}${row.addedBy ? ` by ${row.addedBy}` : ""}` : null],
            ]}
          />
        )}
        {tab === "apps" && <Applications row={row} data={data} />}
        {tab === "watchers" && <Watchers person={person} colleagues={colleagues} />}
        {tab === "security" && (
          <Particulars
            items={[
              ["Two-step sign-in", s.twoStep ? <Pill tone="good">On</Pill> : <Pill tone={s.twoStepRequired ? "bad" : "warn"}>{s.twoStepRequired ? "Off: required for them" : "Off"}</Pill>],
              ["Last signed in", s.lastSignIn ? <span title={when(s.lastSignIn)}>{ago(s.lastSignIn)}</span> : "Never"],
              ["Password", !s.passwordSet ? "Not set yet" : s.mustChangePassword ? "Set by an administrator: changed at their next sign-in" : `Changed ${s.passwordChangedAt ? ago(s.passwordChangedAt) : "—"}`],
              ["Open sign-ins", String(s.openSignIns)],
              ["Wrong passwords (30 days)", String(s.wrongPasswords30Days)],
              ["Locked out now", s.lockedNow ? <Pill tone="bad">Yes, for a few minutes</Pill> : "No"],
              ["Invitation", s.invitationWaiting ? "Sent, not yet accepted" : "None waiting"],
            ]}
          />
        )}
        {tab === "activity" &&
          (!activity ? (
            <p className="text-sm text-ink-3">Reading their activity…</p>
          ) : (
            <>
              {activity.unavailable.length > 0 && (
                <p role="status" className="mb-3 rounded-lg border border-promo bg-promo-tint px-4 py-2 text-sm text-promo-ink">
                  {activity.unavailable.join(", ")} can&apos;t be read just now, so {activity.unavailable.length === 1 ? "its" : "their"} entries are left out.
                </p>
              )}
              {activity.entries.length === 0 ? (
                <Empty icon="auditLog" title="Nothing recorded yet">
                  What they do in Bishnoi One and in every app shows here, newest first.
                </Empty>
              ) : (
                <ul className="divide-y divide-rule">
                  {activity.entries.map((e) => (
                    <li key={e.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 py-2 text-sm">
                      <time dateTime={e.at} title={when(e.at)} className="w-24 shrink-0 text-meta text-ink-3">
                        {ago(e.at)}
                      </time>
                      <span className="w-20 shrink-0 truncate text-meta text-ink-3">{e.app}</span>
                      <span className="min-w-0 flex-1 text-ink-2">
                        {e.text}
                        {e.fields.length > 0 && <span className="text-meta text-ink-3"> ({e.fields.join(", ")})</span>}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-3 flex flex-wrap gap-4">
                {activity.older && (
                  <Link href={activity.older} scroll={false} className="text-sm font-medium text-sage-deep hover:underline">
                    Older
                  </Link>
                )}
                <Link href="/platform/company/activity" className="text-meta text-ink-2 hover:text-hema hover:underline">
                  Company activity log
                </Link>
              </div>
            </>
          ))}
      </div>
    </Sheet>
  );
}

/** Each app they may open as a tile, their role in it beneath; + gives another app (Zoho Directory's Applications). */
function Applications({ row, data }: { row: AccessPerson; data: AccessData }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const given = new Set(row.apps.map((x) => x.key));
  const opened = data.modules.filter((m) => given.has(m.key));
  const notYet = data.modules.filter((m) => !given.has(m.key));
  const rolesFor = (key: string) => data.roles.filter((r) => r.isAdmin || (r.permissions[key]?.length ?? 0) > 0);

  function act(work: () => Promise<{ ok: boolean; error?: string }>) {
    start(async () => {
      const r = await work();
      if (!r.ok) toast.error(r.error ?? "That didn't work.");
      else router.refresh();
    });
  }

  return (
    <div className="grid gap-x-6 gap-y-5 sm:grid-cols-2 xl:grid-cols-3">
      {opened.map((m) => {
        const current = row.apps.find((x) => x.key === m.key)?.roleId ?? null;
        const choices = rolesFor(m.key);
        return (
          <div key={m.key} className="group flex items-start gap-3">
            <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-bench text-ink-2" aria-hidden>
              <Icon name={moduleIcon(m.key)} className="size-5" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-1 text-sm font-semibold text-ink">
                {moduleLabel(m)}
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => act(() => setPersonModule(row.id, m.key, false))}
                  aria-label={`Take ${moduleLabel(m)} away from ${row.fullName}`}
                  title={`Take ${moduleLabel(m)} away`}
                  className="ml-auto grid size-6 place-items-center rounded text-ink-3 opacity-0 group-hover:opacity-100 hover:bg-bench hover:text-danger focus-visible:opacity-100"
                >
                  <X className="size-3.5" aria-hidden />
                </button>
              </p>
              {row.isCompanyAdmin ? (
                <p className="text-meta text-ink-3 italic">Administrator</p>
              ) : (
                <Select
                  aria-label={`${row.fullName}'s role in ${moduleLabel(m)}`}
                  className="mt-1 w-full"
                  value={current ?? ""}
                  onChange={(e) => act(() => setPersonAppRole(row.id, m.key, e.target.value || null))}
                  disabled={busy || choices.length === 0}
                >
                  <option value="">No role yet</option>
                  {[...choices, ...data.roles.filter((r) => r.id === current && !choices.includes(r))].map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </Select>
              )}
            </div>
          </div>
        );
      })}
      {notYet.length > 0 && (
        <div className="flex items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-lg border border-dashed border-rule-strong text-ink-3" aria-hidden>
            <Plus className="size-5" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-ink">Give an app</p>
            <Select aria-label={`Give ${row.fullName} an app`} className="mt-1 w-full" value="" onChange={(e) => e.target.value && act(() => setPersonModule(row.id, e.target.value, true))} disabled={busy}>
              <option value="">Choose an app</option>
              {notYet.map((m) => (
                <option key={m.key} value={m.key}>
                  {moduleLabel(m)}
                </option>
              ))}
            </Select>
          </div>
        </div>
      )}
      {opened.length === 0 && notYet.length === 0 && <p className="text-sm text-ink-3">Your company has no apps yet.</p>}
    </div>
  );
}

/** Who can see this employee's records for monitoring (2026-11-18): their managers from the org chart, kept when they move,
 * and anyone an administrator added. Seeing never adds actions: what each may do stays with their own role. */
function Watchers({ person, colleagues }: { person: PersonPage; colleagues: { id: string; name: string }[] }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const watchers: Watcher[] = person.watchers ?? [];
  const taken = new Set([person.id, ...watchers.map((w) => w.id)]);
  const choices = colleagues.filter((c) => !taken.has(c.id)).map((c) => ({ value: c.id, label: c.name }));

  function act(work: () => Promise<{ ok: boolean; error?: string }>, done: string) {
    start(async () => {
      const r = await work();
      if (!r.ok) toast.error(r.error ?? "That didn't work.");
      else {
        toast.success(done);
        router.refresh();
      }
    });
  }

  const source = (w: Watcher) =>
    w.source === "added" ? `Added by ${w.addedBy ?? "an administrator"}` : w.onChart ? "From the org chart" : "From the org chart, before a move";
  return (
    <div className="space-y-4">
      {watchers.length === 0 ? (
        <Empty icon="people" title="Nobody sees them yet" compact>
          Their managers on the org chart are added here. You can also add someone below.
        </Empty>
      ) : (
        <ul className="divide-y divide-rule">
          {watchers.map((w) => (
            <li key={w.id} className="group flex items-center gap-3 py-2">
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 text-sm font-semibold text-ink">
                  <span className="truncate">{w.fullName}</span>
                  {w.status !== "active" && <Pill tone="bad">Switched off</Pill>}
                </p>
                <p className="truncate text-meta text-ink-3">
                  {source(w)}
                  {w.since ? (
                    <>
                      {" · since "}
                      <time dateTime={w.since} title={when(w.since)}>
                        {day(w.since)}
                      </time>
                    </>
                  ) : null}
                </p>
              </div>
              {w.onChart ? (
                <span className="text-meta text-ink-3" title="Change their place on the org chart, or who they report to, to remove this.">
                  On the chart
                </span>
              ) : (
                <ConfirmButton
                  label={<X className="size-3.5" aria-hidden />}
                  triggerVariant="quiet"
                  triggerSize="sm"
                  triggerTitle={`Remove ${w.fullName}`}
                  title={`Remove ${w.fullName}`}
                  body={`${w.fullName} will no longer see ${person.fullName}'s records. Their own role doesn't change.`}
                  confirmLabel="Remove"
                  disabled={busy}
                  onConfirm={async () => act(() => removeWatcher(person.id, w.id), `${w.fullName} removed.`)}
                />
              )}
            </li>
          ))}
        </ul>
      )}
      <div className="max-w-sm">
        <p className="mb-1 text-sm font-semibold text-ink">Add someone</p>
        <Combobox
          aria-label={`Add someone who can see ${person.fullName}`}
          placeholder="Choose an employee"
          className="w-full"
          options={choices}
          value={undefined}
          disabled={busy || choices.length === 0}
          onChange={(v) => v && act(() => addWatcher(person.id, v as string), "Added.")}
        />
        <p className="mt-1 text-meta text-ink-3">They see this employee's records within their own role. What they may do doesn't change.</p>
      </div>
    </div>
  );
}
