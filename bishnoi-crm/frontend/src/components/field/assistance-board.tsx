"use client";

import { Dropdown, Modal } from "antd";
import { IdCard, MoreHorizontal, Paperclip, Plus, X } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { attachAssistance, decideAssistance, fileAssistance, removeAssistanceFile, withdrawAssistance } from "../../actions/field";
import { FileDrop } from "@/src/platform/ui/file-drop";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, Textarea } from "@/src/platform/ui/field";
import { Combobox, DateInput } from "@/src/platform/ui/pickers";
import { Empty, Sheet } from "@/src/platform/ui/sheet";
import type { Assistance, AssistanceList, AssistanceProgram } from "./types";

// Government assistance applications (PAP, Rx playbook): filed for a doctor's
// patient, followed up weekly, and approved with a confirmation receipt (the
// approval is the month's point). Pending ones come first, oldest first.

const STATUS = {
  pending: { label: "Pending", pill: "bg-[#eda100]/15 text-[#8a5a00]" },
  approved: { label: "Approved", pill: "bg-[#1a8a52]/12 text-[#1a6b40]" },
  denied: { label: "Denied", pill: "bg-[#e34948]/12 text-[#b42318]" },
} as const;

/** Files go one to a request: a request takes at most 4.5 MB. PDF or a photo. */
const FILE_TYPES = "application/pdf,image/jpeg,image/png";
const MAX_FILE = 4 * 1024 * 1024;
const FILE_NOTE = "PDF, JPG or PNG, up to 4 MB each.";

/** Sends each file in turn; says which, if any, didn't go. */
async function sendFiles(id: string, kind: "id" | "document", files: File[]): Promise<string[]> {
  const failed: string[] = [];
  for (const f of files) {
    const form = new FormData();
    form.append("files", f);
    const r = await attachAssistance(id, kind, form);
    if (!r.ok) failed.push(`${f.name}: ${r.fields?.files ?? r.error}`);
  }
  return failed;
}

/** Days from one day to another ("2026-10-01" → "2026-10-08": 7). */
const daysBetween = (from: string, to: string) => Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86400000);

export function AssistanceBoard({ data, doctors, today, dateLabel }: { data: AssistanceList; doctors: { id: string; name: string }[]; today: string; dateLabel: Record<string, string> }) {
  const [filing, setFiling] = useState(false);
  const [approving, setApproving] = useState<Assistance | null>(null);
  const [attaching, setAttaching] = useState<Assistance | null>(null);
  const [, start] = useTransition();
  const program = (key: string) => data.programs.find((p) => p.key === key)?.name ?? key;
  const act = (work: () => Promise<{ ok: boolean; error?: string }>, done: string) =>
    start(async () => {
      const r = await work();
      if (r.ok) toast.success(done);
      else toast.error((r as { error: string }).error);
    });

  return (
    <>
      {data.can.file && (
        <div className="mb-4 flex justify-end">
          <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setFiling(true)}>
            New application
          </Button>
        </div>
      )}
      <Sheet className="px-5 pt-1 pb-2">
        {data.items.length === 0 ? (
          <Empty
            icon="approvals"
            title="No applications"
            actions={data.can.file && <Button onClick={() => setFiling(true)}>New application</Button>}
          >
            During a visit, ask the doctor whether a patient qualifies (PhilHealth Category 4, or a Barangay Certificate of Indigency). Record it here within 24 hours of submission.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {data.items.map((a) => {
              const waited = daysBetween(a.submittedOn, today);
              const s = STATUS[a.status];
              return (
                <li key={a.id} className="flex flex-wrap items-start gap-x-4 gap-y-1 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-2 text-sm">
                      <span className="font-semibold text-ink">{a.patientName}</span>
                      <span className={`rounded-full px-2 py-0.5 text-meta font-semibold ${s.pill}`}>{s.label}</span>
                    </p>
                    <p className="text-meta text-ink-2">
                      {program(a.program)} · {a.products.map((p) => p.name).join(", ")} ·{" "}
                      <a href={`/companies/${a.doctor.id}`} className="hover:underline">
                        {a.doctor.name}
                      </a>
                    </p>
                    <p className="text-meta text-ink-3">
                      Submitted {dateLabel[a.submittedOn] ?? a.submittedOn}
                      {a.status === "pending" && (
                        <span className={waited >= 7 ? "font-semibold text-[#8a5a00]" : ""}>
                          {" "}
                          · {waited === 0 ? "today" : `${waited} ${waited === 1 ? "day" : "days"} waiting`}
                          {waited >= 7 && ": follow up this week"}
                        </span>
                      )}
                      {a.status !== "pending" && a.decidedOn && ` · ${STATUS[a.status].label.toLowerCase()} ${dateLabel[a.decidedOn] ?? a.decidedOn}`}
                      {a.receiptNo && ` · receipt ${a.receiptNo}`}
                      {` · ${a.owner.name}`}
                    </p>
                    {a.notes && <p className="mt-0.5 text-meta text-ink-2">{a.notes}</p>}
                    {a.attachments.length > 0 && (
                      <ul className="mt-1.5 flex flex-wrap gap-1.5" aria-label="Attachments">
                        {a.attachments.map((f) => (
                          <li key={f.n} className="inline-flex items-center gap-1 rounded-md border border-rule bg-bench/60 py-0.5 pr-1 pl-2 text-meta">
                            {f.kind === "id" ? <IdCard className="size-3.5 text-ink-3" aria-label="ID" /> : <Paperclip className="size-3.5 text-ink-3" aria-label="Document" />}
                            <a href={`/field/assistance/${a.id}/files/${f.n}`} target="_blank" rel="noopener" className="max-w-48 truncate text-ink hover:underline">
                              {f.name}
                            </a>
                            {data.can.edit && (
                              <button type="button" onClick={() => act(() => removeAssistanceFile(a.id, f.n), "File removed")} className="grid size-5 place-items-center rounded text-ink-3 hover:text-danger" aria-label={`Remove ${f.name}`}>
                                <X className="size-3" aria-hidden />
                              </button>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  {data.can.edit && (
                    <Dropdown
                      trigger={["click"]}
                      menu={{
                        items:
                          a.status === "pending"
                            ? [
                                { key: "attach", label: "Add attachments…" },
                                { key: "approve", label: "Mark approved…" },
                                { key: "deny", label: "Mark denied" },
                                { type: "divider" as const },
                                { key: "withdraw", label: "Withdraw application", danger: true },
                              ]
                            : [{ key: "attach", label: "Add attachments…" }, { key: "again", label: a.status === "denied" ? "Resubmit" : "Reopen" }],
                        onClick: ({ key }) => {
                          if (key === "attach") setAttaching(a);
                          else if (key === "approve") setApproving(a);
                          else if (key === "deny") act(() => decideAssistance(a.id, { status: "denied" }), "Marked denied");
                          else if (key === "again") act(() => decideAssistance(a.id, { status: "pending", submittedOn: today }), a.status === "denied" ? "Resubmitted" : "Reopened");
                          else if (key === "withdraw") act(() => withdrawAssistance(a.id), "Application withdrawn");
                        },
                      }}
                    >
                      <button type="button" className="grid size-8 place-items-center rounded-lg text-ink-3 hover:bg-bench hover:text-ink" aria-label={`Actions for ${a.patientName}'s application`}>
                        <MoreHorizontal className="size-4" aria-hidden />
                      </button>
                    </Dropdown>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Sheet>
      {filing && <FileForm data={data} doctors={doctors} today={today} onClose={() => setFiling(false)} />}
      {approving && <ApproveForm a={approving} today={today} onClose={() => setApproving(null)} />}
      {attaching && <AttachForm a={attaching} onClose={() => setAttaching(null)} />}
    </>
  );
}

function FileForm({ data, doctors, today, onClose }: { data: AssistanceList; doctors: { id: string; name: string }[]; today: string; onClose: () => void }) {
  const [program, setProgram] = useState<AssistanceProgram | "">("");
  const [patient, setPatient] = useState("");
  const [doctor, setDoctor] = useState("");
  const [products, setProducts] = useState<string[]>([]);
  const [submittedOn, setSubmittedOn] = useState(today);
  const [notes, setNotes] = useState("");
  const [ids, setIds] = useState<File[]>([]);
  const [docs, setDocs] = useState<File[]>([]);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, start] = useTransition();
  const chosen = data.programs.find((p) => p.key === program);

  function save() {
    const missing: Record<string, string> = {};
    if (!program) missing.program = "Pick the program.";
    if (patient.trim().length < 2) missing.patientName = "Enter the patient's full name.";
    if (!doctor) missing.companyId = "Pick the prescribing doctor.";
    if (!products.length) missing.productIds = "Pick the GetMeds products it's for.";
    setFields(missing);
    setError(null);
    if (Object.keys(missing).length) return;
    start(async () => {
      const r = await fileAssistance({ program: program as AssistanceProgram, patientName: patient, companyId: doctor, productIds: products, submittedOn, notes: notes.trim() || null });
      if (!r.ok) {
        setFields(r.fields ?? {});
        setError(r.fields && Object.keys(r.fields).length ? null : r.error);
        return;
      }
      // Then its files, one at a time; the application is kept whatever becomes of them.
      const failed = [...(await sendFiles(r.data.id, "id", ids)), ...(await sendFiles(r.data.id, "document", docs))];
      if (failed.length) toast.warning("Application saved; some files failed to upload", { description: `${failed.join(" ")} Add them from the application's menu.` });
      else toast.success("Application submitted", { description: "Follow up weekly until a decision is made." });
      onClose();
    });
  }

  return (
    <Modal open title="New application" onCancel={() => !saving && onClose()} onOk={save} okText="Submit" cancelText="Cancel" confirmLoading={saving} width={560} destroyOnHidden>
      <div className="mt-3 grid gap-4 sm:grid-cols-2">
        <Field label="Program" error={fields.program} hint={chosen ? `${chosen.gives}; ${chosen.days}.` : undefined} className="sm:col-span-2">
          {(p) => <Combobox {...p} value={program || undefined} onChange={(v) => setProgram(v as AssistanceProgram)} options={data.programs.map((x) => ({ value: x.key, label: x.name }))} placeholder="Select a program" />}
        </Field>
        <Field label="Patient name" error={fields.patientName} hint="As on the form. The diagnosis stays on the paper form." className="sm:col-span-2">
          {(p) => <Input {...p} value={patient} onChange={(e) => setPatient(e.target.value)} maxLength={120} autoFocus />}
        </Field>
        <Field label="Prescribing doctor" error={fields.companyId} className="sm:col-span-2">
          {(p) => <Combobox {...p} value={doctor || undefined} onChange={(v) => setDoctor(String(v))} options={doctors.map((d) => ({ value: d.id, label: d.name }))} placeholder="Select a doctor" />}
        </Field>
        <Field label="GetMeds products" error={fields.productIds ?? fields["productIds.0"]} hint="Every product on the application." className="sm:col-span-2">
          {(p) => (
            <Combobox<string[]>
              {...p}
              mode="multiple"
              value={products}
              onChange={(v) => setProducts(v)}
              options={data.products.map((x) => ({ value: x.id, label: x.strength ? `${x.name} ${x.strength}` : x.name }))}
              placeholder="Select products"
              maxCount={10}
            />
          )}
        </Field>
        <Field label="Date submitted" error={fields.submittedOn}>
          {(p) => <DateInput {...p} type="date" value={submittedOn} max={today} onChange={(e) => setSubmittedOn(e.target.value || today)} />}
        </Field>
        <div className="sm:col-span-2">
          <p className="mb-1.5 text-sm font-medium text-ink">
            Patient IDs <span className="font-normal text-ink-3">(optional)</span>
          </p>
          <FileDrop multiple accept={FILE_TYPES} maxBytes={MAX_FILE} note={`PhilHealth, Senior Citizen, PWD, a government ID. ${FILE_NOTE}`} onFiles={setIds} busy={saving} />
        </div>
        <div className="sm:col-span-2">
          <p className="mb-1.5 text-sm font-medium text-ink">
            Other attachments <span className="font-normal text-ink-3">(optional)</span>
          </p>
          <FileDrop multiple accept={FILE_TYPES} maxBytes={MAX_FILE} note={`The application form, the prescription, the indigency certificate. ${FILE_NOTE}`} onFiles={setDocs} busy={saving} />
        </div>
        <Field label="Notes" optional error={fields.notes} className="sm:col-span-2">
          {(p) => <Textarea {...p} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} placeholder="Submission location and follow-up contact" />}
        </Field>
      </div>
      <FormError message={error} />
    </Modal>
  );
}

function ApproveForm({ a, today, onClose }: { a: Assistance; today: string; onClose: () => void }) {
  const [receipt, setReceipt] = useState("");
  const [on, setOn] = useState(today);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [saving, start] = useTransition();
  function save() {
    if (!receipt.trim()) return setFields({ receiptNo: "Enter the confirmation receipt number: the approval counts with it." });
    start(async () => {
      const r = await decideAssistance(a.id, { status: "approved", receiptNo: receipt.trim(), decidedOn: on });
      if (!r.ok) return setFields(r.fields ?? { receiptNo: r.error });
      toast.success("Approved", { description: `${a.patientName}: counted toward this month.` });
      onClose();
    });
  }
  return (
    <Modal open title={`Approve application: ${a.patientName}`} onCancel={() => !saving && onClose()} onOk={save} okText="Mark approved" cancelText="Cancel" confirmLoading={saving} width={440} destroyOnHidden>
      <div className="mt-3 space-y-4">
        <Field label="Confirmation receipt number" error={fields.receiptNo}>
          {(p) => <Input {...p} value={receipt} onChange={(e) => setReceipt(e.target.value)} maxLength={60} autoFocus />}
        </Field>
        <Field label="Approved on" error={fields.decidedOn}>
          {(p) => <DateInput {...p} type="date" value={on} max={today} onChange={(e) => setOn(e.target.value || today)} />}
        </Field>
      </div>
    </Modal>
  );
}

/** More files on an application already filed: IDs, or other documents. */
function AttachForm({ a, onClose }: { a: Assistance; onClose: () => void }) {
  const [ids, setIds] = useState<File[]>([]);
  const [docs, setDocs] = useState<File[]>([]);
  const [saving, start] = useTransition();
  function save() {
    if (!ids.length && !docs.length) return void toast.error("Select a file first.");
    start(async () => {
      const failed = [...(await sendFiles(a.id, "id", ids)), ...(await sendFiles(a.id, "document", docs))];
      if (failed.length) toast.error("Some files failed to upload", { description: failed.join(" ") });
      else toast.success("Files added");
      onClose();
    });
  }
  return (
    <Modal open title={`Attachments for ${a.patientName}`} onCancel={() => !saving && onClose()} onOk={save} okText="Add files" cancelText="Cancel" confirmLoading={saving} width={520} destroyOnHidden>
      <div className="mt-3 space-y-4">
        <div>
          <p className="mb-1.5 text-sm font-medium text-ink">Patient IDs</p>
          <FileDrop multiple accept={FILE_TYPES} maxBytes={MAX_FILE} note={FILE_NOTE} onFiles={setIds} busy={saving} />
        </div>
        <div>
          <p className="mb-1.5 text-sm font-medium text-ink">Other attachments</p>
          <FileDrop multiple accept={FILE_TYPES} maxBytes={MAX_FILE} note={FILE_NOTE} onFiles={setDocs} busy={saving} />
        </div>
      </div>
    </Modal>
  );
}
