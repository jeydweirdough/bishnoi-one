"use client";

import { Modal } from "antd";
import { Copy, KeyRound, Mail, Pencil, Plus, Power, ShieldCheck, ShieldOff, Trash2, UserPlus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormGrid, Input } from "@/src/platform/ui/field";
import { Select } from "@/src/platform/ui/pickers";
import { RowMenu } from "@/src/platform/ui/row-menu";
import { addPerson, changePerson, deletePerson, invitePerson, resetTwoStep, setPersonPassword } from "./actions";
import { setAdministrator } from "@/src/one/company/actions";
import { moduleLabel } from "./labels";
import type { AccessData, AccessPerson } from "./types";

// Adding and keeping a company's people, on the Platform, once for every module (R2, decided
// 2026-10-26): what each module's own Users page used to do, here. A password is made up and
// shown once, to hand over; they change it themselves after.

/** The new password, shown once with a copy button. */
function showPassword(name: string, password: string) {
  Modal.info({
    title: `${name}'s password`,
    icon: <KeyRound className="mr-3 size-5 text-sage-deep" aria-hidden />,
    okText: "Done",
    content: (
      <div className="mt-2 space-y-2">
        <p className="text-sm text-ink-2">Give it to them yourself. It isn&apos;t shown again, and they choose their own at their first sign-in. An invitation is safer: they set it themselves.</p>
        <p className="flex items-center gap-2 rounded-lg bg-bench px-3 py-2 font-mono text-sm">
          <span className="min-w-0 flex-1 truncate">{password}</span>
          <button
            suppressHydrationWarning
            type="button"
            aria-label="Copy password"
            className="grid size-7 place-items-center rounded-md text-ink-3 hover:bg-white hover:text-ink"
            onClick={() => navigator.clipboard.writeText(password).then(() => toast.success("Password copied"), () => toast.error("Couldn't copy: select it instead."))}
          >
            <Copy className="size-4" aria-hidden />
          </button>
        </p>
      </div>
    ),
  });
}

/** An invitation: emailed when the company sends email; the link shown to pass on either way. */
async function sendInvitation(person: { id: string; fullName: string }) {
  const r = await invitePerson(person.id);
  if (!r.ok) return toast.error(r.error);
  const { link, emailed } = r.data;
  Modal.info({
    title: emailed ? `Invitation sent to ${person.fullName}` : `${person.fullName}'s invitation link`,
    icon: <Mail className="mr-3 size-5 text-sage-deep" aria-hidden />,
    okText: "Done",
    content: (
      <div className="mt-2 space-y-2">
        <p className="text-sm text-ink-2">
          {emailed
            ? "They choose their own password with the link in the email (it works for a week, once). You can also pass this link on yourself:"
            : "Your company hasn't set up email sending (Company, Integrations), so nothing was emailed. Pass this link on yourself; it works for a week, once:"}
        </p>
        <p className="flex items-center gap-2 rounded-lg bg-bench px-3 py-2 font-mono text-meta">
          <span className="min-w-0 flex-1 truncate">{link}</span>
          <button
            suppressHydrationWarning
            type="button"
            aria-label="Copy link"
            className="grid size-7 place-items-center rounded-md text-ink-3 hover:bg-white hover:text-ink"
            onClick={() => navigator.clipboard.writeText(link).then(() => toast.success("Link copied"), () => toast.error("Couldn't copy: select it instead."))}
          >
            <Copy className="size-4" aria-hidden />
          </button>
        </p>
      </div>
    ),
  });
}

/** A new password for someone: typed by the administrator, or made up. Either way they choose their own at their next sign-in. */
function PasswordDialog({ person, open, onClose }: { person: { id: string; fullName: string }; open: boolean; onClose: () => void }) {
  const [typed, setTyped] = useState("");
  const [error, setError] = useState<string>();
  const [busy, start] = useTransition();
  function save(made: boolean) {
    start(async () => {
      const r = await setPersonPassword(person.id, made ? undefined : typed);
      if (!r.ok) return setError(r.error);
      setTyped("");
      setError(undefined);
      onClose();
      if (r.data.password) showPassword(person.fullName, r.data.password);
      else toast.success(`${person.fullName}'s password is set`, { description: "Their other sign-ins ended; they choose their own at the next sign-in." });
    });
  }
  return (
    <Modal
      open={open}
      title={`New password for ${person.fullName}`}
      onCancel={() => !busy && onClose()}
      destroyOnHidden
      footer={
        <div className="flex flex-wrap justify-end gap-2">
          <Button onClick={() => save(true)} disabled={busy}>
            Make one up
          </Button>
          <Button variant="primary" onClick={() => save(false)} loading={busy} disabled={typed.length === 0}>
            Set this password
          </Button>
        </div>
      }
    >
      <div className="space-y-3 pt-2">
        <p className="text-sm text-ink-2">Type one to give them, or let Bishnoi One make one up. They choose their own at their next sign-in, and their other sign-ins end now.</p>
        <Field label="New password" error={error} hint="At least 8 characters.">
          {(p) => <Input {...p} type="text" autoComplete="off" value={typed} onChange={(e) => (setTyped(e.target.value), setError(undefined))} maxLength={200} />}
        </Field>
      </div>
    </Modal>
  );
}

/** Add person: who they are, their role, and the modules they may open. */
export function AddPerson({ data }: { data: AccessData }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, start] = useTransition();
  const [form, setForm] = useState({ fullName: "", email: "", title: "", roleId: "", apps: [] as string[] });
  const [errors, setErrors] = useState<Record<string, string>>({});

  function save() {
    start(async () => {
      const r = await addPerson({ fullName: form.fullName.trim(), email: form.email.trim(), title: form.title.trim() || null, roleId: form.roleId || null, apps: form.apps });
      if (!r.ok) {
        setErrors("fields" in r && r.fields ? r.fields : {});
        return void toast.error(r.error);
      }
      setOpen(false);
      setForm({ fullName: "", email: "", title: "", roleId: "", apps: [] });
      router.refresh();
      const { person, hasPassword } = r.data;
      toast.success(`${person.fullName} added`, {
        description: hasPassword ? "They sign in with the password they already have at another company." : "Send them an invitation: they choose their own password.",
        action: hasPassword ? undefined : { label: "Send invitation", onClick: () => void sendInvitation(person) },
        duration: 10_000,
      });
    });
  }

  return (
    <>
      <Button variant="primary" icon={<UserPlus className="size-4" aria-hidden />} onClick={() => setOpen(true)}>
        Add person
      </Button>
      <Modal open={open} title="Add person" onCancel={() => !busy && setOpen(false)} onOk={save} okText="Add person" confirmLoading={busy} width={600} destroyOnHidden>
        <FormGrid className="pt-2">
          <Field label="Full name" size="md" error={errors.fullName}>
            {(p) => <Input {...p} value={form.fullName} onChange={(e) => setForm({ ...form, fullName: e.target.value })} autoFocus maxLength={120} />}
          </Field>
          <Field label="Work email" size="md" error={errors.email} hint="They sign in with this.">
            {(p) => <Input {...p} type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} maxLength={254} />}
          </Field>
          <Field label="Title" size="md" optional>
            {(p) => <Input {...p} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} maxLength={120} placeholder="e.g. Pharmacist" />}
          </Field>
          <Field label="Role" size="md" optional error={errors.roleId}>
            {(p) => (
              <Select {...p} value={form.roleId} onChange={(e) => setForm({ ...form, roleId: e.target.value })}>
                <option value="">No role yet</option>
                {data.roles.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <fieldset className="sm:col-span-6">
            <legend className="mb-1.5 text-sm font-medium text-ink">Modules they may open</legend>
            <div className="flex flex-wrap gap-1.5">
              {data.modules.map((m) => {
                const on = form.apps.includes(m.key);
                return (
                  <button
                    suppressHydrationWarning
                    key={m.key}
                    type="button"
                    aria-pressed={on}
                    onClick={() => setForm({ ...form, apps: on ? form.apps.filter((k) => k !== m.key) : [...form.apps, m.key] })}
                    className={`inline-flex items-center gap-1 rounded-md border px-3 py-1 text-meta transition-colors ${on ? "border-sage-deep bg-mint-2 font-semibold text-ink" : "border-rule-strong bg-sheet text-ink-3 hover:border-sage-deep"}`}
                  >
                    {!on && <Plus className="size-3" aria-hidden />}
                    {moduleLabel(m)}
                  </button>
                );
              })}
            </div>
          </fieldset>
        </FormGrid>
      </Modal>
    </>
  );
}

/** A person's ⋯: change their details, set a new password, switch them off or on, delete them to the recycle bin. */
export function PersonMenu({ person, isMe }: { person: AccessPerson; isMe: boolean }) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [settingPassword, setSettingPassword] = useState(false);
  const [form, setForm] = useState({ fullName: person.fullName, title: person.title ?? "", email: person.email });
  const [fields, setFields] = useState<Record<string, string>>({});
  const [busy, start] = useTransition();
  const off = person.status !== "active";

  function save() {
    start(async () => {
      const email = form.email.trim().toLowerCase();
      const emailChanged = email !== person.email.toLowerCase();
      const r = await changePerson(person.id, { fullName: form.fullName.trim(), title: form.title.trim() || null, ...(emailChanged && { email }) });
      if (!r.ok) {
        setFields(r.fields ?? {});
        if (!r.fields) toast.error(r.error);
        return;
      }
      setFields({});
      setEditing(false);
      toast.success("Saved", emailChanged ? { description: `${person.fullName} now signs in as ${email}, with the same password.` } : undefined);
      router.refresh();
    });
  }

  return (
    <>
      <PasswordDialog person={person} open={settingPassword} onClose={() => setSettingPassword(false)} />
      <RowMenu
        always
        label={`Actions for ${person.fullName}`}
        items={[
          { label: "Change details", icon: <Pencil />, onSelect: () => setEditing(true) },
          ...(off ? [] : [{ label: "Send invitation", icon: <Mail />, onSelect: () => void sendInvitation(person) }]),
          { label: "Set a new password", icon: <KeyRound />, onSelect: () => setSettingPassword(true) },
          ...(isMe
            ? []
            : [
                person.isCompanyAdmin
                  ? {
                      label: "Remove as administrator",
                      icon: <ShieldOff />,
                      run: () => setAdministrator(person.id, false),
                      confirm: `Remove ${person.fullName} as administrator? They keep their role and apps, but can't open the Admin Console. Their sign-ins end.`,
                      done: `${person.fullName} is no longer an administrator`,
                    }
                  : off
                    ? "divider" as const
                    : {
                        label: "Make administrator",
                        icon: <ShieldCheck />,
                        run: () => setAdministrator(person.id, true),
                        confirm: `Make ${person.fullName} an administrator? They can change everything in the Admin Console: people, roles, apps and the company.`,
                        done: `${person.fullName} is now an administrator`,
                      },
                {
                  label: "Reset two-step sign-in",
                  icon: <ShieldOff />,
                  run: () => resetTwoStep(person.id),
                  confirm: `Reset ${person.fullName}'s two-step sign-in? Use this when they lost their phone. Their sign-ins end; they set it up again next time.`,
                  done: `${person.fullName} sets up two-step sign-in again at their next sign-in`,
                },
                "divider" as const,
                off
                  ? { label: "Switch on", icon: <Power />, run: () => changePerson(person.id, { status: "active" }), done: `${person.fullName} can sign in again` }
                  : {
                      label: "Switch off",
                      icon: <Power />,
                      run: () => changePerson(person.id, { status: "suspended" }),
                      danger: true,
                      confirm: `Switch ${person.fullName} off? They can't sign in to any module until switched on again.`,
                      done: `${person.fullName} is switched off`,
                    },
                {
                  label: "Delete",
                  icon: <Trash2 />,
                  run: () => deletePerson(person.id),
                  danger: true,
                  confirm: `Delete ${person.fullName}? They go to the recycle bin: switched off and signed out everywhere. What they did stays, and you can restore them from the recycle bin.`,
                  done: `${person.fullName} is in the recycle bin`,
                },
              ]),
        ]}
      />
      <Modal open={editing} title={`Change ${person.fullName}`} onCancel={() => !busy && setEditing(false)} onOk={save} okText="Save" confirmLoading={busy} width={480} destroyOnHidden>
        <FormGrid className="pt-2">
          <Field label="Full name" size="full" error={fields.fullName}>
            {(p) => <Input {...p} value={form.fullName} onChange={(e) => setForm({ ...form, fullName: e.target.value })} maxLength={120} />}
          </Field>
          <Field label="Work email" size="full" error={fields.email} hint="They sign in with this. At your company's email domain; their password stays.">
            {(p) => <Input {...p} type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} maxLength={254} />}
          </Field>
          <Field label="Title" size="full" optional>
            {(p) => <Input {...p} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} maxLength={120} />}
          </Field>
        </FormGrid>
      </Modal>
    </>
  );
}
