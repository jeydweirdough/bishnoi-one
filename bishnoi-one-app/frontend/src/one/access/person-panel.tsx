"use client";

import { AtSign, KeyRound, Pencil, Plus, ShieldOff, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { ago, when } from "@/src/modules/console/lib/words";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Pill } from "@/src/platform/ui/figures";
import { Icon, moduleIcon } from "@/src/platform/ui/icons";
import { Select } from "@/src/platform/ui/pickers";
import { RowMenu } from "@/src/platform/ui/row-menu";
import { Empty, Particulars, Sheet } from "@/src/platform/ui/sheet";
import { setPersonAppRole, setPersonModule } from "./actions";
import { moduleLabel } from "./labels";
import { usePersonActions } from "./person-dialogs";
import type { AccessData, AccessPerson, PersonPage } from "./types";

// A person in a panel beside People (2026-10-31, after Zoho Directory's): who they are and every action on them
// at the top, then Info, Applications (each app with their role in it), Security and Account activity.

export type PanelActivity = { id: string; at: string; text: string };

const TABS = [
  ["info", "Info"],
  ["apps", "Applications"],
  ["security", "Security"],
  ["activity", "Account activity"],
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

export function PersonPanel({ person, row, data, activity }: { person: PersonPage; row: AccessPerson; data: AccessData; activity: PanelActivity[] }) {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("info");
  const isMe = row.id === data.meId;
  const a = usePersonActions(row, isMe, data.modules.map((m) => m.key), data.company.emailDomain);
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
        <Button size="sm" icon={<AtSign className="size-4" aria-hidden />} onClick={a.openEdit}>
          Manage email address
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
            onClick={() => setTab(key)}
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
          (activity.length === 0 ? (
            <Empty icon="auditLog" title="Nothing yet">
              Their sign-ins, and changes by them or to them, show here.
            </Empty>
          ) : (
            <>
              <ul className="divide-y divide-rule">
                {activity.map((e) => (
                  <li key={e.id} className="flex items-baseline gap-3 py-2 text-sm">
                    <time dateTime={e.at} title={when(e.at)} className="w-24 shrink-0 text-meta text-ink-3">
                      {ago(e.at)}
                    </time>
                    <span className="min-w-0 flex-1 text-ink-2">{e.text}</span>
                  </li>
                ))}
              </ul>
              <Link href={`/platform/company/activity?q=${encodeURIComponent(person.email)}`} className="mt-3 inline-block text-meta text-ink-2 hover:text-hema hover:underline">
                Everything in the Activity log
              </Link>
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
