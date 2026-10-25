"use client";

import { Dropdown, Modal } from "antd";
import { Bookmark, MoreHorizontal, Users } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { changeView, deleteView, saveView, type SavedView, type ViewList, type Views } from "@/src/modules/crm/actions/views";
import { IconButton } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Input } from "@/src/platform/ui/field";

// Saved views (benchmark E2, after Twenty): a list's filters kept by name, one
// click away. "All" is the list as it opens; each view is the list as someone
// left it. Save view keeps the filters showing now; a view's own menu (its
// owner's) brings it up to date, renames it, shares it or deletes it.

/** The list's address after "?", the way a view keeps it: no page, no empty values, in a steady order. */
function keyOf(params: URLSearchParams | string): string {
  const p = new URLSearchParams(params);
  const pairs = [...p.entries()].filter(([k, v]) => k !== "page" && v).sort(([a, x], [b, y]) => (a === b ? x.localeCompare(y) : a.localeCompare(b)));
  return new URLSearchParams(pairs).toString();
}

function Tab({ href, current, children }: { href: string; current: boolean; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      scroll={false}
      aria-current={current ? "page" : undefined}
      className={`inline-flex h-8 shrink-0 items-center gap-1.5 rounded-full border px-3 text-meta transition-colors ${
        current ? "border-ink bg-ink font-semibold text-white" : "border-rule-strong bg-sheet text-ink-2 hover:border-ink hover:text-ink"
      }`}
    >
      {children}
    </Link>
  );
}

export function ViewsBar({ list, views }: { list: ViewList; views: Views }) {
  const pathname = usePathname();
  const params = useSearchParams();
  const now = keyOf(params);
  const [name, setName] = useState("");
  const [shared, setShared] = useState(false);
  const [renaming, setRenaming] = useState<SavedView | null>(null);
  const [newName, setNewName] = useState("");
  const [, start] = useTransition();
  const current = views.items.find((v) => v.query === now);
  const hrefOf = (q: string) => (q ? `${pathname}?${q}` : pathname);

  const create = async () => {
    if (!name.trim()) {
      toast.error("Give the view a name.");
      return false;
    }
    const r = await saveView({ list, name: name.trim(), query: now, shared });
    if (!r.ok) {
      toast.error(r.error);
      return false;
    }
    toast.success(`Saved: ${r.data.name}`);
    setName("");
    setShared(false);
  };
  const change = (v: SavedView, input: { name?: string; query?: string; shared?: boolean }, done: string) =>
    start(async () => {
      const r = await changeView(v.id, input);
      if (r.ok) toast.success(done);
      else toast.error(r.error);
    });

  return (
    <nav aria-label="Views" className="mb-3 flex items-center gap-1.5 overflow-x-auto pb-1 [scrollbar-width:thin]">
      <Tab href={pathname} current={now === ""}>
        All
      </Tab>
      {views.items.map((v) => (
        <span key={v.id} className="inline-flex shrink-0 items-center">
          <Tab href={hrefOf(v.query)} current={current?.id === v.id}>
            {v.shared ? <Users className="size-3.5" aria-label="Shared" /> : <Bookmark className="size-3.5" aria-hidden />}
            {v.name}
          </Tab>
          {current?.id === v.id && v.canEdit && (
            <Dropdown
              trigger={["click"]}
              menu={{
                items: [
                  { key: "rename", label: "Rename" },
                  ...(views.canShare ? [{ key: "share", label: v.shared ? "Keep to myself" : "Share with everyone" }] : []),
                  { type: "divider" as const },
                  { key: "delete", label: "Delete", danger: true },
                ],
                onClick: ({ key }) => {
                  if (key === "rename") {
                    setNewName(v.name);
                    setRenaming(v);
                  } else if (key === "share") change(v, { shared: !v.shared }, v.shared ? `${v.name}: yours only now` : `${v.name}: shared with everyone`);
                  else if (key === "delete")
                    start(async () => {
                      const r = await deleteView(v.id);
                      if (r.ok) toast.success(`Deleted: ${v.name}`);
                      else toast.error(r.error);
                    });
                },
              }}
            >
              <IconButton size="sm" label={`Options: ${v.name}`} className="ml-0.5">
                <MoreHorizontal className="size-4" aria-hidden />
              </IconButton>
            </Dropdown>
          )}
        </span>
      ))}
      {/* Filters showing that no view keeps yet: offer to keep them. */}
      {now !== "" && !current && (
        <ConfirmButton
          label="Save view"
          icon={<Bookmark className="size-3.5" aria-hidden />}
          triggerVariant="quiet"
          triggerSize="sm"
          title="Save these filters as a view"
          body={
            <div className="space-y-3">
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-ink">Name</span>
                <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={60} placeholder="e.g. Overdue drugstores" autoFocus />
              </label>
              {views.canShare && (
                <label className="flex items-center gap-2 text-sm text-ink">
                  <input suppressHydrationWarning type="checkbox" checked={shared} onChange={(e) => setShared(e.target.checked)} className="size-4 accent-[var(--color-ink)]" />
                  Share with everyone who sees this list
                </label>
              )}
              <p className="text-meta text-ink-3">It keeps the search, filters and sort showing now.</p>
            </div>
          }
          confirmLabel="Save view"
          danger={false}
          onConfirm={create}
        />
      )}
      <Modal
        open={renaming !== null}
        title="Rename view"
        okText="Rename"
        onCancel={() => setRenaming(null)}
        onOk={() => {
          if (renaming && newName.trim()) change(renaming, { name: newName.trim() }, `Renamed: ${newName.trim()}`);
          setRenaming(null);
        }}
      >
        <Input value={newName} onChange={(e) => setNewName(e.target.value)} maxLength={60} autoFocus />
      </Modal>
    </nav>
  );
}
