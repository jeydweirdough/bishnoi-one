"use client";

import { DatePicker, Input, Modal, Select, Tag } from "antd";
import dayjs from "dayjs";
import { Plus } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { FormError } from "@/src/platform/ui/field";
import { Sheet } from "@/src/platform/ui/sheet";
import { saveTemplate, type EmailTemplate } from "../../actions/mailbox";

type Option = { value: string; label: string };

function Editor({ t, teams, onDone }: { t: EmailTemplate | null; teams: Option[]; onDone: () => void }) {
  const [v, setV] = useState({
    name: t?.name ?? "",
    subject: t?.subject ?? "",
    body: t?.body ?? "",
    onlyTeams: t?.onlyTeams ?? [],
    approvedOn: t?.approvedOn ?? dayjs().format("YYYY-MM-DD"),
    expiresOn: t?.expiresOn ?? null,
    isActive: t?.isActive ?? true,
  });
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  function save() {
    if (!v.name.trim() || !v.subject.trim() || !v.body.trim()) return setError("Give it a name, a subject and its wording.");
    start(async () => {
      const r = await saveTemplate(t?.id ?? null, { ...v, name: v.name.trim(), subject: v.subject.trim(), body: v.body.trim() });
      if (!r.ok) return setError(r.fields ? Object.values(r.fields)[0] : r.error);
      toast.success("Saved", { description: r.data.name });
      onDone();
    });
  }
  return (
    <Modal open title={t ? "Change approved email" : "New approved email"} onCancel={onDone} onOk={save} okText="Save" confirmLoading={pending} width={640}>
      <div className="space-y-4 pt-1">
        <label className="block">
          <span className="mb-1.5 block text-sm text-ink">Name (what reps pick)</span>
          <Input value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} maxLength={120} placeholder="e.g. Introducing Onco One" />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm text-ink">Subject</span>
          <Input value={v.subject} onChange={(e) => setV({ ...v, subject: e.target.value })} maxLength={200} />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm text-ink">Wording, as approved</span>
          <Input.TextArea rows={8} value={v.body} onChange={(e) => setV({ ...v, body: e.target.value })} maxLength={20000} />
          <span className="mt-1 block text-meta text-ink-3">{"{customer}, {contact} and {me} are filled in when it's sent. Reps can add a personal note on top, never change this."}</span>
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm text-ink">Divisions</span>
          <Select mode="multiple" className="w-full" value={v.onlyTeams} onChange={(onlyTeams) => setV({ ...v, onlyTeams })} options={teams} placeholder="Everyone" showSearch={{ optionFilterProp: "label" }} />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">Approved on</span>
            <DatePicker className="w-full" value={dayjs(v.approvedOn)} onChange={(d) => d && setV({ ...v, approvedOn: d.format("YYYY-MM-DD") })} allowClear={false} format="D MMM YYYY" />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">
              Expires on <span className="text-ink-3">(optional)</span>
            </span>
            <DatePicker className="w-full" value={v.expiresOn ? dayjs(v.expiresOn) : null} onChange={(d) => setV({ ...v, expiresOn: d ? d.format("YYYY-MM-DD") : null })} format="D MMM YYYY" />
          </label>
        </div>
        <FormError message={error} />
      </div>
    </Modal>
  );
}

/** Settings → Approved emails: what reps may send from a customer's page, worded as approved. */
export function EmailTemplates({ items, teams }: { items: EmailTemplate[]; teams: Option[] }) {
  const [editing, setEditing] = useState<EmailTemplate | "new" | null>(null);
  const [, start] = useTransition();
  return (
    <div className="max-w-3xl space-y-4">
      <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setEditing("new")}>
        New approved email
      </Button>
      <Sheet>
        {items.length === 0 ? (
          <p className="px-5 py-8 text-center text-sm text-ink-3">None yet. Write the emails reps may send, as approved.</p>
        ) : (
          <ul className="divide-y divide-rule">
            {items.map((t) => (
              <li key={t.id} className={`flex flex-wrap items-center gap-3 px-5 py-3 ${t.isCurrent ? "" : "opacity-60"}`}>
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-ink">{t.name}</p>
                  <p className="truncate text-meta text-ink-3">{t.subject}</p>
                </div>
                {!t.isCurrent && <Tag color="error">{t.isActive ? "Not current" : "Switched off"}</Tag>}
                <Button size="sm" onClick={() => setEditing(t)}>
                  Change
                </Button>
                <Button
                  size="sm"
                  variant="quiet"
                  onClick={() => start(async () => void (await saveTemplate(t.id, { name: t.name, subject: t.subject, body: t.body, onlyTeams: t.onlyTeams, approvedOn: t.approvedOn, expiresOn: t.expiresOn, isActive: !t.isActive })))}
                >
                  {t.isActive ? "Switch off" : "Switch on"}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
      {editing && <Editor t={editing === "new" ? null : editing} teams={teams} onDone={() => setEditing(null)} />}
    </div>
  );
}
