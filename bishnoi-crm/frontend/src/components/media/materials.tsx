"use client";

import { DatePicker, Input, Modal, Select, Tag, Upload } from "antd";
import dayjs from "dayjs";
import { ExternalLink, FileText, Link2, Plus, Upload as UploadIcon } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { FormError } from "@/src/platform/ui/field";
import { deleteMaterial, openMaterial, saveMaterial, switchMaterial, type Material } from "../../actions/media";

type Option = { value: string; label: string };

/** Opens a material: counted (for the customer, when opened from their page), then shown in a new tab. */
export function OpenButton({ item, companyId }: { item: Material; companyId: string | null }) {
  const [pending, start] = useTransition();
  return (
    <Button
      size="sm"
      variant="primary"
      icon={item.kind === "link" ? <ExternalLink className="size-3.5" aria-hidden /> : <FileText className="size-3.5" aria-hidden />}
      loading={pending}
      onClick={() => {
        // Opened now, while the click still counts as the person's own: browsers block tabs opened later.
        const tab = window.open("about:blank", "_blank");
        start(async () => {
          const r = await openMaterial(item.id, companyId);
          if (!r.ok) {
            tab?.close();
            return void toast.error(r.error);
          }
          const where = r.data.url ?? `/media/${item.id}/file`;
          if (tab) tab.location.href = where;
          else window.location.href = where;
        });
      }}
    >
      Open
    </Button>
  );
}

/** Adding or changing one, for an administrator: what it is, a file or a link, its products, divisions and dates. */
function MaterialForm({
  item,
  products,
  teams,
  onDone,
}: {
  item: Material | null;
  products: Option[];
  teams: Option[];
  onDone: () => void;
}) {
  const [title, setTitle] = useState(item?.title ?? "");
  const [description, setDescription] = useState(item?.description ?? "");
  const [kind, setKind] = useState<"file" | "link">(item?.kind ?? "file");
  const [url, setUrl] = useState(item?.url ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [picked, setPicked] = useState(item?.products.map((p) => p.code) ?? []);
  const [onlyTeams, setOnlyTeams] = useState(item?.onlyTeams ?? []);
  const [approvedOn, setApprovedOn] = useState(item?.approvedOn ?? dayjs().format("YYYY-MM-DD"));
  const [expiresOn, setExpiresOn] = useState<string | null>(item?.expiresOn ?? null);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function save() {
    if (!title.trim()) return setError("Give it a title.");
    if (kind === "link" && !url.trim()) return setError("Paste the link to it.");
    if (kind === "file" && !file && item?.kind !== "file") return setError("Choose the file.");
    const form = file ? new FormData() : null;
    if (form && file) form.set("file", file);
    start(async () => {
      const r = await saveMaterial(
        item?.id ?? null,
        { title: title.trim(), description: description.trim() || null, url: kind === "link" ? url.trim() : null, products: picked, onlyTeams, approvedOn, expiresOn },
        form,
      );
      if (!r.ok) return setError(r.fields ? Object.values(r.fields)[0] : r.error);
      toast.success(item ? "Saved" : "Material added", { description: r.data.title });
      onDone();
    });
  }

  return (
    <Modal open title={item ? "Change material" : "Add material"} onCancel={onDone} onOk={save} okText={item ? "Save" : "Add"} confirmLoading={pending} width={560}>
      <div className="space-y-4 pt-1">
        <label className="block">
          <span className="mb-1.5 block text-sm text-ink">Title</span>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={160} placeholder="e.g. Onco One: dosing and evidence" />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm text-ink">
            What it&apos;s for <span className="text-ink-3">(optional)</span>
          </span>
          <Input.TextArea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={500} />
        </label>
        <div>
          <span className="mb-1.5 block text-sm text-ink">The material</span>
          <Select
            className="mb-2 w-full"
            value={kind}
            onChange={setKind}
            options={[
              { value: "file", label: "A file kept here (PDF, PowerPoint or picture, up to 4 MB)" },
              { value: "link", label: "A link to it on the shared drive (bigger decks, videos)" },
            ]}
          />
          {kind === "file" ? (
            <Upload beforeUpload={(f) => (setFile(f), false)} maxCount={1} onRemove={() => setFile(null)} accept=".pdf,.pptx,.png,.jpg,.jpeg">
              <Button icon={<UploadIcon className="size-4" aria-hidden />}>{item?.kind === "file" ? `Replace ${item.fileName ?? "the file"}` : "Choose the file"}</Button>
            </Upload>
          ) : (
            <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" prefix={<Link2 className="size-4 text-ink-3" aria-hidden />} />
          )}
        </div>
        <label className="block">
          <span className="mb-1.5 block text-sm text-ink">Products</span>
          <Select mode="multiple" className="w-full" value={picked} onChange={setPicked} options={products} showSearch={{ optionFilterProp: "label" }} placeholder="The products it's about" />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm text-ink">Divisions</span>
          <Select mode="multiple" className="w-full" value={onlyTeams} onChange={setOnlyTeams} options={teams} showSearch={{ optionFilterProp: "label" }} placeholder="Everyone" />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">Approved on</span>
            <DatePicker className="w-full" value={dayjs(approvedOn)} onChange={(d) => d && setApprovedOn(d.format("YYYY-MM-DD"))} allowClear={false} format="D MMM YYYY" />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">
              Expires on <span className="text-ink-3">(optional)</span>
            </span>
            <DatePicker className="w-full" value={expiresOn ? dayjs(expiresOn) : null} onChange={(d) => setExpiresOn(d ? d.format("YYYY-MM-DD") : null)} format="D MMM YYYY" />
          </label>
        </div>
        <FormError message={error} />
      </div>
    </Modal>
  );
}

/** The materials, as cards: open for everyone; add, change, switch off and delete for an administrator. */
export function Materials({
  items,
  canManage,
  companyId,
  products,
  teams,
}: {
  items: Material[];
  canManage: boolean;
  companyId: string | null;
  products: Option[];
  teams: Option[];
}) {
  const [editing, setEditing] = useState<Material | "new" | null>(null);
  const [, start] = useTransition();
  const teamName = (id: string) => teams.find((t) => t.value === id)?.label ?? "A removed team";
  return (
    <>
      {canManage && (
        <div className="mb-4">
          <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setEditing("new")}>
            Add material
          </Button>
        </div>
      )}
      {items.length === 0 ? (
        <p className="rounded-sheet border border-rule bg-sheet px-5 py-8 text-center text-sm text-ink-3">
          {canManage ? "No materials yet. Add the approved decks and PDFs reps show customers." : "No approved materials for your division yet."}
        </p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((m) => (
            <li key={m.id} className={`flex flex-col rounded-sheet border border-rule bg-sheet p-4 shadow-sheet ${m.isCurrent ? "" : "opacity-70"}`}>
              <div className="flex items-start gap-3">
                <span className="grid size-9 shrink-0 place-items-center rounded-[6px] bg-bench text-ink-2">
                  {m.kind === "link" ? <Link2 className="size-4" aria-hidden /> : <FileText className="size-4" aria-hidden />}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-ink">{m.title}</p>
                  {m.description && <p className="mt-0.5 text-meta text-ink-2">{m.description}</p>}
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-1">
                {m.products.map((p) => (
                  <Tag key={p.code}>{p.name}</Tag>
                ))}
                {m.onlyTeams.map((t) => (
                  <Tag key={t} color="processing">
                    {teamName(t)}
                  </Tag>
                ))}
                {!m.isCurrent && <Tag color="error">{m.isActive ? "Not current" : "Switched off"}</Tag>}
              </div>
              <p className="mt-2 text-meta text-ink-3">
                Approved {dayjs(m.approvedOn).format("D MMM YYYY")}
                {m.expiresOn && ` · until ${dayjs(m.expiresOn).format("D MMM YYYY")}`}
                {canManage && m.opened30d !== undefined && ` · opened ${m.opened30d} ${m.opened30d === 1 ? "time" : "times"} in 30 days`}
              </p>
              <div className="mt-auto flex flex-wrap items-center gap-2 pt-3">
                <OpenButton item={m} companyId={companyId} />
                {canManage && (
                  <>
                    <Button size="sm" onClick={() => setEditing(m)}>
                      Change
                    </Button>
                    <Button size="sm" variant="quiet" onClick={() => start(async () => void (await switchMaterial(m.id, !m.isActive)))}>
                      {m.isActive ? "Switch off" : "Switch on"}
                    </Button>
                    <ConfirmButton
                      label="Delete"
                      triggerSize="sm"
                      title={`Delete ${m.title}?`}
                      body="Reps won't see it any more, and its openings are forgotten. Switch it off instead to keep them."
                      confirmLabel="Delete material"
                      onConfirm={async () => {
                        const r = await deleteMaterial(m.id);
                        if (!r.ok) {
                          toast.error(r.error);
                          return false;
                        }
                      }}
                    />
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {editing && <MaterialForm item={editing === "new" ? null : editing} products={products} teams={teams} onDone={() => setEditing(null)} />}
    </>
  );
}
