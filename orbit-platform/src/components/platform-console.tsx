"use client";

import { ArrowRight, ChevronRight, Eye, Plus, Power, X } from "lucide-react";
import { useEffect, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { addCompany, companyPeople, setCompanyOn } from "../actions";
import { openCompany, viewAs } from "@/src/platform/actions/session";
import type { CompanyPerson, PlatformCompany } from "@/src/platform/lib/types";

// The platform: every company on Orbit, and putting a new one on it.
//
// This is the one screen that belongs to no company. A Developer Admin signs in
// here — not into anybody's company — takes a new customer on, and opens one
// when there is something to put right. Opening a company ends this session and
// starts one inside it, because the wall (api app/tenancy.py) is what keeps one
// company's records out of another's, and it has no "both at once".

const CURRENCIES = ["PHP", "USD", "EUR", "GBP", "SGD", "AUD", "JPY"];
const ZONES = ["Asia/Manila", "Asia/Singapore", "Asia/Tokyo", "Australia/Sydney", "Europe/London", "America/New_York"];

type Draft = {
  name: string;
  slug: string;
  adminName: string;
  adminEmail: string;
  adminPassword: string;
  currency: string;
  timezone: string;
};

const EMPTY: Draft = {
  name: "",
  slug: "",
  adminName: "",
  adminEmail: "",
  adminPassword: "",
  currency: "PHP",
  timezone: "Asia/Manila",
};

/** What the address will be, shown as it is typed so nobody is surprised by it. */
const asSlug = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);

/** One company's people, and the one click that looks through any of them. */
function People({ orgId, busy, onView }: { orgId: string; busy: boolean; onView: (userId: string) => void }) {
  // null until it is read: one piece of state, so nothing is set while rendering.
  const [people, setPeople] = useState<CompanyPerson[] | null>(null);

  useEffect(() => {
    let live = true;
    companyPeople(orgId).then((result) => {
      if (live) setPeople(result.ok ? result.data : []);
    });
    return () => {
      live = false;
    };
  }, [orgId]);

  if (people === null) return <p className="px-3 py-3 pl-14 text-meta text-ink-3">Reading who is in it…</p>;
  if (people.length === 0) return <p className="px-3 py-3 pl-14 text-meta text-ink-3">Nobody in it yet.</p>;

  return (
    <ul className="divide-y divide-rule border-t border-rule" role="list">
      {people.map((p) => (
        <li key={p.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2 pr-3 pl-14">
          <span className="min-w-0 flex-1">
            <span className="flex flex-wrap items-center gap-2">
              <b className="font-medium text-ink">{p.fullName}</b>
              {p.isOwner && <span className="rounded-[3px] bg-hema-tint px-1.5 text-meta font-semibold text-hema">Owner</span>}
              {p.isAdmin && !p.isOwner && (
                <span className="rounded-[3px] bg-bench px-1.5 text-meta font-semibold text-ink-2">Admin</span>
              )}
            </span>
            <span className="block truncate text-meta text-ink-3">
              {p.email} · {p.moduleCount === 1 ? "1 module" : `${p.moduleCount} modules`}
            </span>
          </span>
          <Button size="sm" variant="quiet" disabled={busy} icon={<Eye className="size-4" aria-hidden />} onClick={() => onView(p.id)}>
            See as them
          </Button>
        </li>
      ))}
    </ul>
  );
}

export function PlatformConsole({ companies }: { companies: PlatformCompany[] }) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [busy, start] = useTransition();
  const [going, setGoing] = useState<string | null>(null);
  const [showing, setShowing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const change = (patch: Partial<Draft>) => setDraft({ ...draft, ...patch });
  const slug = draft.slug.trim() || asSlug(draft.name);

  function add() {
    if (draft.name.trim().length < 2) return setError("Give the company a name.");
    if (!slug) return setError("That name has no letters or numbers in it.");
    if (draft.adminName.trim().length < 2) return setError("Name the person who will run it.");
    if (!/^[^@\s]+@[^@\s]+\.[^@\s.]+$/.test(draft.adminEmail.trim())) return setError("Give them a work email.");
    if (draft.adminPassword.length < 12) return setError("Their first password needs at least 12 characters.");
    setError(null);
    start(async () => {
      const result = await addCompany({
        name: draft.name.trim(),
        slug,
        currency: draft.currency,
        timezone: draft.timezone,
        adminEmail: draft.adminEmail.trim().toLowerCase(),
        adminName: draft.adminName.trim(),
        adminPassword: draft.adminPassword,
      });
      if (!result.ok) return setError(result.error);
      setAdding(false);
      setDraft(EMPTY);
      toast.success(`${result.data.company.name} is on Orbit`, {
        description: `${draft.adminName.trim()} can sign in and set it up.`,
      });
    });
  }

  function open(id: string) {
    setGoing(id);
    setError(null);
    start(async () => {
      const result = await openCompany(id);
      if (result?.error) {
        setError(result.error);
        setGoing(null);
      }
    });
  }

  function look(orgId: string, userId: string) {
    setError(null);
    start(async () => {
      const result = await viewAs(orgId, userId);
      if (result?.error) setError(result.error);
    });
  }

  /** Switching one back on: nothing is lost by doing it, so it just happens. */
  function toggle(c: PlatformCompany) {
    start(async () => {
      const result = await setCompanyOn(c.id, true);
      if (!result.ok) return setError(result.error);
      toast.success(`${c.name} switched back on`);
    });
  }

  return (
    <div className="max-w-[46rem] space-y-4">
      <FormError message={error} />

      <Sheet className="px-2 py-2">
        <ul className="divide-y divide-rule" role="list">
          {companies.map((c) => {
            const off = c.status !== "active";
            return (
              <li key={c.id}>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-3 py-3">
                <button
                  type="button"
                  aria-expanded={showing === c.id}
                  aria-label={`Who is in ${c.name}`}
                  onClick={() => setShowing(showing === c.id ? null : c.id)}
                  className="flex size-9 shrink-0 items-center justify-center rounded-[3px] bg-bench text-ink-3 hover:text-ink"
                >
                  <ChevronRight className={`size-4 transition-transform ${showing === c.id ? "rotate-90" : ""}`} aria-hidden />
                </button>
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-2">
                    <b className="font-semibold text-ink">{c.name}</b>
                    {off && (
                      <span className="rounded-[3px] bg-danger-tint px-1.5 py-0.5 text-meta font-semibold text-danger">
                        Switched off
                      </span>
                    )}
                    {!c.isReady && (
                      <span className="rounded-[3px] bg-bench px-1.5 py-0.5 text-meta font-semibold text-ink-3">Nobody in it</span>
                    )}
                  </span>
                  <span className="block truncate text-meta text-ink-3">
                    {c.slug} · {c.currency} · {c.timezone} · {c.peopleCount === 1 ? "1 person" : `${c.peopleCount} people`}
                  </span>
                </span>
                <span className="flex items-center gap-1">
                  {off ? (
                    <Button
                      size="sm"
                      variant="quiet"
                      disabled={busy}
                      icon={<Power className="size-4" aria-hidden />}
                      onClick={() => toggle(c)}
                    >
                      Switch on
                    </Button>
                  ) : (
                    /* Asked first: switching a company off locks every one of
                       its people out at once, and it sits a thumb's width from
                       Open. */
                    <ConfirmButton
                      label="Switch off"
                      triggerVariant="quiet"
                      triggerSize="sm"
                      triggerClassName="!text-ink-3 hover:!text-danger"
                      icon={<Power className="size-4" aria-hidden />}
                      disabled={busy}
                      title={`Switch ${c.name} off?`}
                      body={
                        <>
                          Nobody at {c.name} will be able to sign in — all{" "}
                          {c.peopleCount === 1 ? "1 person" : `${c.peopleCount} people`} of them. Nothing of theirs is
                          deleted, and you can switch it back on from here.
                        </>
                      }
                      confirmLabel="Switch it off"
                      onConfirm={async () => {
                        const result = await setCompanyOn(c.id, false);
                        if (!result.ok) {
                          setError(result.error);
                          return false;
                        }
                        toast.success(`${c.name} switched off`);
                      }}
                    />
                  )}
                  <Button
                    size="sm"
                    variant="quiet"
                    loading={busy && going === c.id}
                    disabled={busy || off}
                    icon={<ArrowRight className="size-4" aria-hidden />}
                    onClick={() => open(c.id)}
                  >
                    Open
                  </Button>
                </span>
                </div>
                {showing === c.id && <People orgId={c.id} busy={busy} onView={(userId) => look(c.id, userId)} />}
              </li>
            );
          })}
        </ul>
      </Sheet>

      {!adding ? (
        <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setAdding(true)}>
          Add a company
        </Button>
      ) : (
        <Sheet className="px-5 pt-4 pb-5 sm:px-7">
          <SectionTitle icon="companies">A company joins Orbit</SectionTitle>
          <p className="mb-5 text-meta text-ink-3">
            It opens to a working system — divisions, teams, roles, price types, order settings — and the person you name here
            changes every bit of it in Settings. Nothing below is yours to keep deciding.
          </p>

          <div className="space-y-5">
            <Field label="Company name" hint={slug ? `Its address will be ${slug}` : "Its legal name, for letters and reports"}>
              {(p) => (
                <Input
                  {...p}
                  value={draft.name}
                  maxLength={120}
                  autoComplete="off"
                  placeholder="e.g. Northwind Pharma"
                  onChange={(e) => change({ name: e.target.value })}
                />
              )}
            </Field>

            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Money" hint="What its prices are in">
                {(p) => (
                  <Select {...p} value={draft.currency} onChange={(e) => change({ currency: e.target.value })}>
                    {CURRENCIES.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="Time" hint="What its days and deadlines are in">
                {(p) => (
                  <Select {...p} value={draft.timezone} onChange={(e) => change({ timezone: e.target.value })}>
                    {ZONES.map((z) => (
                      <option key={z} value={z}>
                        {z}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            </div>

            <div className="border-t border-rule pt-5">
              <p className="mb-4 text-meta font-semibold text-ink-2">
                Who will run it
                <span className="block font-normal text-ink-3">
                  They get the Admin role, and set up everything else themselves. Somebody already on Orbit keeps the password
                  they have.
                </span>
              </p>
              <div className="space-y-5">
                <Field label="Their name">
                  {(p) => (
                    <Input
                      {...p}
                      value={draft.adminName}
                      maxLength={120}
                      autoComplete="off"
                      className="max-w-xs"
                      onChange={(e) => change({ adminName: e.target.value })}
                    />
                  )}
                </Field>
                <Field label="Their work email">
                  {(p) => (
                    <Input
                      {...p}
                      type="email"
                      value={draft.adminEmail}
                      maxLength={254}
                      autoComplete="off"
                      inputMode="email"
                      onChange={(e) => change({ adminEmail: e.target.value })}
                    />
                  )}
                </Field>
                <Field label="Their first password" hint="At least 12 characters. They change it once they are in.">
                  {(p) => (
                    <Input
                      {...p}
                      type="text"
                      value={draft.adminPassword}
                      autoComplete="off"
                      spellCheck={false}
                      onChange={(e) => change({ adminPassword: e.target.value })}
                    />
                  )}
                </Field>
              </div>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-2 border-t border-rule pt-4">
            <Button variant="primary" loading={busy} onClick={add}>
              Add {draft.name.trim() || "the company"}
            </Button>
            <Button
              variant="quiet"
              disabled={busy}
              icon={<X className="size-4" aria-hidden />}
              onClick={() => {
                setAdding(false);
                setDraft(EMPTY);
                setError(null);
              }}
            >
              Cancel
            </Button>
          </div>
        </Sheet>
      )}
    </div>
  );
}
