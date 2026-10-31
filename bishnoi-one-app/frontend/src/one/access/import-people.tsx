"use client";

import { Modal } from "antd";
import { Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import { toast } from "sonner";
import { parseCsv } from "@/src/platform/lib/csv";
import { Button } from "@/src/platform/ui/button";
import { Field, Input } from "@/src/platform/ui/field";
import { FileDrop } from "@/src/platform/ui/file-drop";
import { Select } from "@/src/platform/ui/pickers";
import { importPeople, type ImportPeopleResult, type ImportPeopleRow } from "./actions";

// People from a CSV file (2026-10-30): read in the browser (nothing of the file is uploaded or kept),
// each column matched to what it holds, every row checked by the Platform (new, already here, or a
// problem and why), then every new person added at once, with an invitation each if asked. Zoho's users
// export (First Name, Last Name, Username…) and this app's own export are recognised by their headings.

type Target = "fullName" | "firstName" | "lastName" | "email" | "title" | "role" | "apps";
const TARGETS: { key: Target; label: string; guesses: string[] }[] = [
  { key: "fullName", label: "Full name", guesses: ["name", "full name", "display name", "employee name"] },
  { key: "firstName", label: "First name", guesses: ["first name", "given name"] },
  { key: "lastName", label: "Last name", guesses: ["last name", "surname", "family name"] },
  { key: "email", label: "Work email", guesses: ["email", "work email", "email address", "e-mail", "username", "user name"] },
  { key: "title", label: "Title", guesses: ["title", "job title", "designation", "position"] },
  { key: "role", label: "Role", guesses: ["role", "profile"] },
  { key: "apps", label: "Apps (separated by ;)", guesses: ["apps", "modules", "applications"] },
];
const NONE = "-1";

export function ImportPeople() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [head, setHead] = useState<string[] | null>(null);
  const [body, setBody] = useState<string[][]>([]);
  const [map, setMap] = useState<Record<Target, number>>({} as Record<Target, number>);
  const [domain, setDomain] = useState("");
  const [checked, setChecked] = useState<ImportPeopleResult | null>(null);
  const [invite, setInvite] = useState(true);
  const [busy, start] = useTransition();

  function reset() {
    setHead(null);
    setBody([]);
    setChecked(null);
  }

  async function read(file: File | null) {
    reset();
    if (!file) return;
    const [h, ...rest] = parseCsv(await file.text());
    if (!h || rest.length === 0) return void toast.error("That file has no rows under its headings.");
    const names = h.map((x) => x.trim().toLowerCase());
    setHead(h.map((x) => x.trim()));
    setBody(rest);
    setMap(Object.fromEntries(TARGETS.map((t) => [t.key, names.findIndex((n) => t.guesses.includes(n))])) as Record<Target, number>);
  }

  const rows: ImportPeopleRow[] = useMemo(() => {
    const at = (r: string[], t: Target) => (map[t] >= 0 ? (r[map[t]] ?? "").trim() : "");
    const at2 = domain.trim().replace(/^@/, "");
    return body.map((r) => {
      const email = at(r, "email");
      return {
        fullName: at(r, "fullName") || [at(r, "firstName"), at(r, "lastName")].filter(Boolean).join(" "),
        email: email && !email.includes("@") && at2 ? `${email}@${at2}` : email,
        title: at(r, "title") || null,
        role: at(r, "role") || null,
        apps: at(r, "apps").split(/[;|]/).map((a) => a.trim()).filter(Boolean),
      };
    });
  }, [body, map, domain]);

  function check() {
    start(async () => {
      const r = await importPeople(rows, false, false);
      if (!r.ok) return void toast.error(r.error);
      setChecked(r.data);
    });
  }

  function add() {
    if (!checked) return;
    // Only the rows that are new: those with problems or already here stay out.
    const fresh = checked.rows.filter((x) => x.outcome === "new").map((x) => rows[x.n - 1]);
    start(async () => {
      const r = await importPeople(fresh, true, invite);
      if (!r.ok) return void toast.error(r.error);
      const { added = 0, invited = 0, emailed = 0 } = r.data;
      toast.success(`${added} ${added === 1 ? "person" : "people"} added`, {
        description: invite ? (emailed ? `${emailed} invitation${emailed === 1 ? "" : "s"} emailed.` : `${invited} invitation links made: email sending isn't set up, so send each from their ⋯ menu.`) : "Send each an invitation from their ⋯ menu.",
        duration: 10_000,
      });
      setOpen(false);
      reset();
      router.refresh();
    });
  }

  const tone = { new: "text-ink", already: "text-ink-3", problem: "text-promo-ink" } as const;
  const word = { new: "New", already: "Already here", problem: "Problem" } as const;

  return (
    <>
      <Button icon={<Upload className="size-4" aria-hidden />} onClick={() => setOpen(true)}>
        Import
      </Button>
      <Modal
        open={open}
        title="Import people from a file"
        width={760}
        onCancel={() => !busy && (setOpen(false), reset())}
        footer={
          <div className="flex flex-wrap items-center justify-end gap-2">
            {checked && checked.counts.new > 0 && (
              <label className="mr-auto inline-flex items-center gap-2 text-sm text-ink-2">
                <input type="checkbox" checked={invite} onChange={(e) => setInvite(e.target.checked)} />
                Send each an invitation to choose their password
              </label>
            )}
            <Button onClick={() => (setOpen(false), reset())} disabled={busy}>
              Cancel
            </Button>
            {checked ? (
              <Button variant="primary" onClick={add} loading={busy} disabled={checked.counts.new === 0}>
                Add {checked.counts.new} {checked.counts.new === 1 ? "person" : "people"}
              </Button>
            ) : (
              <Button variant="primary" onClick={check} loading={busy} disabled={!head || rows.length === 0}>
                Check {rows.length || ""} rows
              </Button>
            )}
          </div>
        }
        destroyOnHidden
      >
        <div className="space-y-4 pt-2">
          <FileDrop accept=".csv,text/csv" maxBytes={2_000_000} note="CSV: a row per person. Zoho's users export works as it is." onFile={(f) => void read(f)} />
          {head && !checked && (
            <>
              <p className="text-sm text-ink-2">Match each column to what it holds. {rows.length} rows.</p>
              <div className="grid gap-3 sm:grid-cols-2">
                {TARGETS.map((t) => (
                  <Field key={t.key} label={t.label} size="full" optional={t.key !== "email"}>
                    {(p) => (
                      <Select {...p} value={String(map[t.key] ?? -1)} onChange={(e) => setMap({ ...map, [t.key]: Number(e.target.value) })}>
                        <option value={NONE}>Not in the file</option>
                        {head.map((h, i) => (
                          <option key={i} value={i}>
                            {h || `Column ${i + 1}`}
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>
                ))}
                <Field label="Email domain, for usernames without one" size="full" optional hint="e.g. getmeds.ph: a username “ana” becomes ana@getmeds.ph.">
                  {(p) => <Input {...p} value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="getmeds.ph" />}
                </Field>
              </div>
            </>
          )}
          {checked && (
            <>
              <p className="text-sm text-ink-2">
                {checked.counts.new} new · {checked.counts.already} already here · {checked.counts.problem} with problems (left out).{" "}
                <button type="button" className="text-hema hover:underline" onClick={() => setChecked(null)}>
                  Change the matching
                </button>
              </p>
              <div className="max-h-80 overflow-auto rounded-lg border border-rule">
                <table className="w-full text-left text-meta">
                  <thead className="sticky top-0 bg-bench text-ink-3">
                    <tr>
                      <th className="px-3 py-2">Row</th>
                      <th className="px-3 py-2">Person</th>
                      <th className="px-3 py-2">Role · apps</th>
                      <th className="px-3 py-2">Check</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-rule">
                    {checked.rows.map((r) => (
                      <tr key={r.n}>
                        <td className="px-3 py-2 text-ink-3">{r.n + 1}</td>
                        <td className="px-3 py-2">
                          <span className="font-medium text-ink">{r.fullName || "—"}</span>
                          <span className="block text-ink-3">{r.email || "—"}</span>
                        </td>
                        <td className="px-3 py-2 text-ink-2">{[r.role, r.apps.join(", ")].filter(Boolean).join(" · ") || "—"}</td>
                        <td className={`px-3 py-2 ${tone[r.outcome]}`}>
                          {word[r.outcome]}
                          {r.reasons.length > 0 && <span className="block">{r.reasons.join(" ")}</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </Modal>
    </>
  );
}
