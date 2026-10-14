"use client";

import { Dropdown, Modal, Tag } from "antd";
import { Combobox } from "@/src/platform/ui/pickers";
import { DateInput } from "@/src/platform/ui/pickers";
import { FileDrop } from "@/src/platform/ui/file-drop";
import dayjs from "dayjs";
import { ExternalLink, FileText, Link2, MoreHorizontal, Plus } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Empty, Sheet } from "@/src/platform/ui/sheet";
import { Button, IconButton } from "@/src/platform/ui/button";
import { FormError, Input, Textarea } from "@/src/platform/ui/field";
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

/** The divisions list's "everyone" choice: no division picked. */
const EVERYONE = "__everyone__";

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
          <Textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={500} />
        </label>
        <div>
          <span className="mb-1.5 block text-sm text-ink">The material</span>
          <Combobox
            className="w-full"
            value={kind}
            onChange={setKind}
            options={[
              { value: "file", label: "A file kept here (PDF, PowerPoint or picture, up to 4 MB)" },
              { value: "link", label: "A link to it on the shared drive (bigger decks, videos)" },
            ]}
          />
          <div className="mt-3">
          {kind === "file" ? (
            <FileDrop
              accept=".pdf,.pptx,.png,.jpg,.jpeg"
              note="PDF, PowerPoint or a picture, up to 4 MB"
              maxBytes={4 * 1024 * 1024}
              current={item?.kind === "file" ? { name: item.fileName ?? "The file" } : null}
              onFile={setFile}
            />
          ) : (
            <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" prefix={<Link2 className="size-4 text-ink-3" aria-hidden />} />
          )}
          </div>
        </div>
        <label className="block">
          <span className="mb-1.5 block text-sm text-ink">Products</span>
          <Combobox mode="multiple" className="w-full" value={picked} onChange={setPicked} options={products} showSearch={{ optionFilterProp: "label" }} placeholder="The products it's about" />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm text-ink">Who can show it</span>
          {/* "Everyone" is a choice of its own: picking a division narrows it, picking Everyone opens it to all again. */}
          <Combobox
            mode="multiple"
            className="w-full"
            value={onlyTeams.length ? onlyTeams : [EVERYONE]}
            onChange={(picked: string[]) => {
              const added = picked.find((v) => !onlyTeams.includes(v) && v !== EVERYONE);
              setOnlyTeams(picked.at(-1) === EVERYONE && !added ? [] : picked.filter((v) => v !== EVERYONE));
            }}
            options={[{ value: EVERYONE, label: "Everyone, every division" }, ...teams]}
            showSearch={{ optionFilterProp: "label" }}
          />
          <span className="mt-1 block text-meta text-ink-3">{onlyTeams.length ? "Only these divisions see it in Media." : "Every division sees it. Pick divisions to show it to them only."}</span>
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">Approved on</span>
            <DateInput type="date" value={approvedOn} onChange={(e) => e.target.value && setApprovedOn(e.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm text-ink">
              Expires on <span className="text-ink-3">(optional)</span>
            </span>
            <DateInput type="date" value={expiresOn ?? ""} min={approvedOn} onChange={(e) => setExpiresOn(e.target.value || null)} />
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
  const [deleting, setDeleting] = useState<Material | null>(null);
  const [removing, remove] = useTransition();
  const teamName = (id: string) => teams.find((t) => t.value === id)?.label ?? "A removed team";
  return (
    <>
      {canManage && items.length > 0 && (
        <div className="mb-4">
          <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setEditing("new")}>
            Add material
          </Button>
        </div>
      )}
      {items.length === 0 ? (
        <Sheet>
          {canManage ? (
            <Empty
              icon="letters"
              title="No materials yet"
              actions={
                <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setEditing("new")}>
                  Add the first material
                </Button>
              }
            >
              Add the approved decks, PDFs and links reps show customers, with the products and divisions they&apos;re for.
            </Empty>
          ) : (
            <Empty icon="letters" title="Nothing approved for your division yet">
              Approved presentations, PDFs and videos show up here once an administrator adds them. Ask them for what you need to show customers.
            </Empty>
          )}
        </Sheet>
      ) : (
        <>
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((m) => (
            <li key={m.id} className={`flex flex-col rounded-sheet border border-rule bg-sheet p-5 shadow-sheet ${m.isCurrent ? "" : "opacity-75"}`}>
              {/* What it is, with the ways to manage it beside its name. */}
              <div className="flex items-start gap-3">
                <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-bench text-ink-2">
                  {m.kind === "link" ? <Link2 className="size-4" aria-hidden /> : <FileText className="size-4" aria-hidden />}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold text-ink">{m.title}</p>
                  {m.description && <p className="mt-0.5 line-clamp-2 text-meta text-ink-3">{m.description}</p>}
                </div>
                {canManage && (
                  <Dropdown
                    trigger={["click"]}
                    placement="bottomRight"
                    menu={{
                      items: [
                        { key: "change", label: "Change" },
                        { key: "switch", label: m.isActive ? "Switch off" : "Switch on" },
                        { type: "divider" },
                        { key: "delete", label: "Delete", danger: true },
                      ],
                      onClick: ({ key }) => {
                        if (key === "change") setEditing(m);
                        if (key === "switch") start(async () => void (await switchMaterial(m.id, !m.isActive)));
                        if (key === "delete") setDeleting(m);
                      },
                    }}
                  >
                    <IconButton className="-mt-1 -mr-1" label={`Manage ${m.title}`}>
                      <MoreHorizontal className="size-4" aria-hidden />
                    </IconButton>
                  </Dropdown>
                )}
              </div>

              {/* Where it stands, then what it's about. */}
              {(!m.isCurrent || m.onlyTeams.length > 0) && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {!m.isCurrent && <Tag color="error">{m.isActive ? "Not current" : "Switched off"}</Tag>}
                  {m.onlyTeams.map((t) => (
                    <Tag key={t}>{teamName(t)}</Tag>
                  ))}
                </div>
              )}
              {m.products.length > 0 && (
                <p className="mt-3 text-meta text-ink-2">
                  <span className="text-ink-3">For </span>
                  {m.products.map((p) => p.name).join(", ")}
                </p>
              )}

              {/* The one thing to do with it, and its dates. */}
              <div className="mt-auto pt-4">
                <div className="flex items-center justify-between gap-3 border-t border-rule pt-3">
                  <OpenButton item={m} companyId={companyId} />
                  <p className="text-right text-meta text-ink-3">
                    {m.expiresOn ? `Until ${dayjs(m.expiresOn).format("D MMM YYYY")}` : `Approved ${dayjs(m.approvedOn).format("D MMM YYYY")}`}
                    {canManage && m.opened30d !== undefined && (
                      <span className="block">
                        Opened {m.opened30d} {m.opened30d === 1 ? "time" : "times"} in 30 days
                      </span>
                    )}
                  </p>
                </div>
              </div>
            </li>
          ))}
        </ul>
        <Modal
          open={deleting !== null}
          title={deleting ? `Delete ${deleting.title}?` : ""}
          onCancel={() => setDeleting(null)}
          okText="Delete material"
          okButtonProps={{ danger: true }}
          confirmLoading={removing}
          onOk={() =>
            deleting &&
            remove(async () => {
              const r = await deleteMaterial(deleting.id);
              if (!r.ok) return void toast.error(r.error);
              setDeleting(null);
            })
          }
          width={440}
        >
          <p className="text-sm text-ink-2">Reps won&apos;t see it any more, and its openings are forgotten. Switch it off instead to keep them.</p>
        </Modal>
        </>
      )}
      {editing && <MaterialForm item={editing === "new" ? null : editing} products={products} teams={teams} onDone={() => setEditing(null)} />}
    </>
  );
}
