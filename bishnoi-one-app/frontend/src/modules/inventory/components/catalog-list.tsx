"use client";

import { Ellipsis, Pencil, Plus, Power, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Dropdown, Modal, type MenuProps } from "antd";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/inventory/platform/ui/button";
import { ConfirmButton } from "@/src/modules/inventory/platform/ui/confirm";
import { Field, FormError, Input, Select } from "@/src/modules/inventory/platform/ui/field";
import { deleteCatalogItem, saveCatalogItem } from "@/src/modules/inventory/actions/inventory";
import { Table, Td } from "@/src/modules/inventory/components/ui";

export type CatalogItem = { key: string; name: string; code?: string; parentId?: string | null; path?: string; isActive: boolean; count: number; childCount?: number };
export type CatalogKind = "categories" | "brands" | "units";

const WORDS: Record<CatalogKind, { one: string; title: string }> = {
  categories: { one: "category", title: "Category" },
  brands: { one: "brand", title: "Brand" },
  units: { one: "unit", title: "Unit" },
};

type Draft = { name: string; code: string; parentId: string; isActive: boolean };

/** What still uses it ("70 products and 2 categories"), or null when nothing does. */
function inUse(kind: CatalogKind, item: CatalogItem): string | null {
  const parts = [
    item.count > 0 ? `${item.count.toLocaleString()} product${item.count === 1 ? "" : "s"}` : null,
    kind === "categories" && item.childCount ? `${item.childCount} categor${item.childCount === 1 ? "y" : "ies"} inside it` : null,
  ].filter(Boolean);
  return parts.length ? parts.join(" and ") : null;
}

/** Every category inside this one, at any depth: it can't move into those. */
function inside(items: CatalogItem[], key: string): Set<string> {
  const out = new Set<string>();
  let grew = true;
  while (grew) {
    grew = false;
    for (const c of items) if (c.parentId && (c.parentId === key || out.has(c.parentId)) && !out.has(c.key)) (out.add(c.key), (grew = true));
  }
  return out;
}

/**
 * Deleting something still in use: what uses it moves to another first, then
 * it's deleted, in one step. Nothing is left pointing at what's gone.
 */
function MoveThenDelete({ kind, item, items, onClose, onDone }: { kind: CatalogKind; item: CatalogItem; items: CatalogItem[]; onClose: () => void; onDone: () => void }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [target, setTarget] = useState("");
  const [error, setError] = useState<string | null>(null);
  const w = WORDS[kind];
  const using = inUse(kind, item);
  const blocked = kind === "categories" ? inside(items, item.key) : new Set<string>();
  const choices = items.filter((i) => i.key !== item.key && !blocked.has(i.key));
  const label = (i: CatalogItem) => (kind === "categories" ? (i.path ?? i.name) : kind === "units" ? `${i.name} (${i.code})` : i.name) + (i.isActive ? "" : " · inactive");

  function go() {
    if (!target) return setError(`Pick the ${w.one} to move them to.`);
    start(async () => {
      const r = await deleteCatalogItem(kind, item.key, target);
      if (!r.ok) return setError(r.fields?.moveTo ?? r.error);
      const to = items.find((i) => i.key === target);
      toast.success(`${item.name} deleted`, { description: `${using} moved to ${to?.name ?? "the other " + w.one}.` });
      onDone();
      router.refresh();
    });
  }

  return (
    <Modal
      open
      title={`Delete ${item.name}`}
      onCancel={() => !pending && onClose()}
      width={480}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="quiet" onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button variant="danger" loading={pending} onClick={go} disabled={choices.length === 0}>
            Move and delete
          </Button>
        </div>
      }
    >
      <div className="space-y-4 pt-2">
        <p className="text-sm text-ink-2">
          {using} still use{using?.startsWith("1 ") && !using.includes(" and ") ? "s" : ""} this {w.one}. They move to the {w.one} you pick, then {item.name} is deleted.
          {kind === "units" && " Their quantities stay the same numbers, counted in the new unit."}
        </p>
        {choices.length === 0 ? (
          <p className="text-sm text-danger">There&apos;s no other {w.one} to move them to. Add one first, or switch this one off instead.</p>
        ) : (
          <Field label={`Move them to`} error={error ?? undefined}>
            {(p) => (
              <Select {...p} value={target} onChange={(e) => (setTarget(e.target.value), setError(null))}>
                <option value="">Pick a {w.one}</option>
                {choices.map((c) => (
                  <option key={c.key} value={c.key}>
                    {label(c)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}
      </div>
    </Modal>
  );
}

/**
 * The row's own actions, at its end (Jakob's law: where every list app keeps
 * them): edit, switch off or on, delete. Delete stays in the menu when the item
 * is in use, switched off, with the reason, so nobody is left wondering.
 */
function RowActions({ kind, item, items: all, canEdit, canDelete, onEdit }: { kind: CatalogKind; item: CatalogItem; items: CatalogItem[]; canEdit: boolean; canDelete: boolean; onEdit: () => void }) {
  const router = useRouter();
  const [modal, holder] = Modal.useModal();
  const [moving, setMoving] = useState(false);
  const w = WORDS[kind];
  const using = inUse(kind, item);

  async function toggle() {
    const r = await saveCatalogItem(kind, item.key, { isActive: !item.isActive });
    if (!r.ok) return void toast.error(Object.values(r.fields ?? {})[0] ?? r.error);
    toast.success(item.isActive ? `${item.name} switched off` : `${item.name} switched on`);
    router.refresh();
  }

  function remove() {
    modal.confirm({
      title: `Delete ${item.name}?`,
      content: `The ${w.one} is removed. Nothing uses it.`,
      okText: `Delete ${w.one}`,
      okButtonProps: { danger: true },
      cancelText: "Cancel",
      onOk: async () => {
        const r = await deleteCatalogItem(kind, item.key);
        if (!r.ok) {
          toast.error(r.error);
          return;
        }
        toast.success(`${item.name} deleted`);
        router.refresh();
      },
    });
  }

  const items: MenuProps["items"] = [
    ...(canEdit
      ? [
          { key: "edit", label: `Edit ${w.one}`, icon: <Pencil className="size-4" aria-hidden /> },
          { key: "toggle", label: item.isActive ? "Switch off" : "Switch on", icon: <Power className="size-4" aria-hidden /> },
        ]
      : []),
    ...(canDelete
      ? [
          { type: "divider" as const },
          {
            key: "delete",
            danger: true,
            icon: <Trash2 className="size-4" aria-hidden />,
            label: (
              <span className="block">
                Delete {w.one}
                {using && <span className="block max-w-56 text-[12px] whitespace-normal opacity-70">Moves its {using} first</span>}
              </span>
            ),
          },
        ]
      : []),
  ];
  if (items.length === 0) return null;
  return (
    <>
      {holder}
      <Dropdown
        trigger={["click"]}
        placement="bottomRight"
        menu={{ items, onClick: ({ key }) => (key === "edit" ? onEdit() : key === "toggle" ? void toggle() : key === "delete" ? (using ? setMoving(true) : remove()) : undefined) }}
      >
        <button
          type="button"
          aria-label={`Actions for ${item.name}`}
          title={`Actions for ${item.name}`}
          className="relative z-10 grid size-8 place-items-center rounded-full text-ink-3 hover:bg-bench hover:text-ink focus-visible:ring-2 focus-visible:ring-ink focus-visible:outline-none"
        >
          <Ellipsis className="size-4" aria-hidden />
        </button>
      </Dropdown>
      {moving && <MoveThenDelete kind={kind} item={item} items={all} onClose={() => setMoving(false)} onDone={() => setMoving(false)} />}
    </>
  );
}

/** Adding, renaming, switching off or deleting one item, in a dialog. `item` null: a new one. */
function CatalogDialog({ kind, items, item, canDelete, onClose }: { kind: CatalogKind; items: CatalogItem[]; item: CatalogItem | null; canDelete: boolean; onClose: () => void }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [draft, setDraft] = useState<Draft>({ name: item?.name ?? "", code: item?.code ?? "", parentId: item?.parentId ?? "", isActive: item?.isActive ?? true });
  const [error, setError] = useState<string | null>(null);
  const w = WORDS[kind];

  function save() {
    const input: Record<string, unknown> = { name: draft.name.trim() };
    if (kind === "units" && !item) input.code = draft.code.trim().toLowerCase();
    if (kind === "categories") input.parentId = draft.parentId || null;
    if (item) input.isActive = draft.isActive;
    start(async () => {
      const r = await saveCatalogItem(kind, item?.key ?? null, input);
      if (!r.ok) {
        setError(Object.values(r.fields ?? {})[0] ?? r.error);
        return;
      }
      toast.success(item ? `${draft.name.trim()} saved` : `${draft.name.trim()} added`);
      onClose();
      router.refresh();
    });
  }

  // Delete only what nothing uses: no products, no categories inside.
  const using = item ? inUse(kind, item) : null;
  const deletable = item && canDelete && !using;
  const [moving, setMoving] = useState(false);
  return (
    <Modal
      open
      title={item ? `Edit ${w.one}` : `Add ${w.one}`}
      onCancel={() => !pending && onClose()}
      width={460}
      footer={
        <div className="flex items-center gap-2">
          {item && canDelete && using && (
            <Button variant="quiet" size="sm" className="!text-danger" icon={<Trash2 className="size-4" aria-hidden />} onClick={() => setMoving(true)}>
              Delete
            </Button>
          )}
          {deletable && (
            <ConfirmButton
              label="Delete"
              title={`Delete ${item.name}?`}
              body={`The ${w.one} is removed. Nothing uses it.`}
              confirmLabel={`Delete ${w.one}`}
              triggerVariant="quiet"
              triggerSize="sm"
              triggerClassName="!text-danger"
              icon={<Trash2 className="size-4" aria-hidden />}
              onConfirm={async () => {
                const r = await deleteCatalogItem(kind, item.key);
                if (!r.ok) {
                  toast.error(r.error);
                  return false;
                }
                toast.success(`${item.name} deleted`);
                onClose();
                router.refresh();
              }}
            />
          )}
          <span className="ml-auto" />
          <Button variant="quiet" onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button variant="primary" loading={pending} onClick={save}>
            {item ? "Save" : `Add ${w.one}`}
          </Button>
        </div>
      }
    >
      <div className="space-y-4 pt-2">
        {kind === "units" && (
          <Field label="Code" hint={item ? "The code can't be changed once used." : "Short, as quantities show it: box, vial, tablet."}>
            {(p) => <Input {...p} value={draft.code} placeholder="box" disabled={Boolean(item)} onChange={(e) => setDraft({ ...draft, code: e.target.value })} autoFocus={!item} />}
          </Field>
        )}
        <Field label="Name">
          {(p) => <Input {...p} value={draft.name} placeholder={kind === "units" ? "Box" : kind === "brands" ? "Brand name" : "Category name"} onChange={(e) => setDraft({ ...draft, name: e.target.value })} onPressEnter={save} autoFocus={kind !== "units" || Boolean(item)} />}
        </Field>
        {kind === "categories" && (
          <Field label="Inside" hint="Nest categories to build a hierarchy, for example Medical Supplies › Syringes.">
            {(p) => (
              <Select {...p} value={draft.parentId} onChange={(e) => setDraft({ ...draft, parentId: e.target.value })}>
                <option value="">None (top level)</option>
                {items.filter((c) => c.key !== item?.key).map((c) => <option key={c.key} value={c.key}>{c.path}</option>)}
              </Select>
            )}
          </Field>
        )}
        {item && (
          <Field label="Status" hint={`An inactive ${w.one} can't be picked for new products. Products already using it keep it.`}>
            {(p) => (
              <Select {...p} value={draft.isActive ? "active" : "inactive"} onChange={(e) => setDraft({ ...draft, isActive: e.target.value === "active" })}>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </Select>
            )}
          </Field>
        )}
        <FormError message={error} />
      </div>
      {moving && item && <MoveThenDelete kind={kind} item={item} items={items} onClose={() => setMoving(false)} onDone={onClose} />}
    </Modal>
  );
}

/** The page header's Add button. */
export function CatalogAddButton({ kind, items }: { kind: CatalogKind; items: CatalogItem[] }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setOpen(true)}>
        Add {WORDS[kind].one}
      </Button>
      {open && <CatalogDialog kind={kind} items={items} item={null} canDelete={false} onClose={() => setOpen(false)} />}
    </>
  );
}

/** The list as Products reads: one row each, the name to open it; its products a click away. */
export function CatalogTable({ kind, items, all, canEdit, canDelete }: { kind: CatalogKind; items: CatalogItem[]; all: CatalogItem[]; canEdit: boolean; canDelete: boolean }) {
  const [editing, setEditing] = useState<CatalogItem | null>(null);
  const w = WORDS[kind];
  // Units have no filter on Products, so only categories and brands link to theirs.
  const productsOf = (item: CatalogItem) => (kind === "categories" ? `/inventory/products?category=${item.key}&status=all` : kind === "brands" ? `/inventory/products?brand=${item.key}&status=all` : null);
  return (
    <>
      <Table head={[w.title, " Products", ...(kind === "categories" ? [" Subcategories"] : []), "Status", ...(canEdit || canDelete ? [<span key="a" className="sr-only">Actions</span>] : [])]} min="36rem">
        {items.map((item) => {
          const href = productsOf(item);
          return (
            <tr key={item.key} className="relative hover:bg-bench/40">
              <Td>
                {canEdit ? (
                  <button type="button" onClick={() => setEditing(item)} className="text-left font-semibold text-ink after:absolute after:inset-0 hover:underline" title={`Edit ${w.one} ${item.name}`}>
                    {kind === "categories" ? item.path : item.name}
                  </button>
                ) : (
                  <span className="font-semibold text-ink">{kind === "categories" ? item.path : item.name}</span>
                )}
                {kind === "units" && <span className="block text-meta text-ink-3">{item.code}</span>}
              </Td>
              <Td num>
                {href && item.count > 0 ? (
                  <Link href={href} className="relative z-10 hover:text-ink hover:underline">
                    {item.count.toLocaleString()}
                  </Link>
                ) : (
                  item.count.toLocaleString()
                )}
              </Td>
              {kind === "categories" && <Td num className={item.childCount ? "" : "text-ink-3"}>{item.childCount ? item.childCount.toLocaleString() : "—"}</Td>}
              <Td className={item.isActive ? "text-ink-2" : "text-ink-3"}>{item.isActive ? "Active" : "Inactive"}</Td>
              {(canEdit || canDelete) && (
                <Td className="w-12 !py-1.5 text-right">
                  <RowActions kind={kind} item={item} items={all} canEdit={canEdit} canDelete={canDelete} onEdit={() => setEditing(item)} />
                </Td>
              )}
            </tr>
          );
        })}
      </Table>
      {editing && <CatalogDialog kind={kind} items={all} item={editing} canDelete={canDelete} onClose={() => setEditing(null)} />}
    </>
  );
}
