"use client";

import { Pencil, Plus } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/modules/finance/platform/ui/field";
import type { Account } from "@/src/modules/finance/ledger/types";
import { saveCategory } from "@/src/modules/finance/funds/actions";
import type { ExpenseCategory } from "@/src/modules/finance/funds/types";

/** Expense categories and their sub-categories. A category (Food) posts to its
 *  expense account; its sub-categories (Dining, Breakfast) add detail to a
 *  receipt and follow the category's account and reimbursable rule. */
export function CategoriesEditor({ categories, accounts, canEdit }: { categories: ExpenseCategory[]; accounts: Account[]; canEdit: boolean }) {
  const [editing, setEditing] = useState<{ category: ExpenseCategory | null; parentId: string | null } | null>(null);
  const tops = categories.filter((c) => c.parentId === null);
  const form = (key: string) =>
    editing && (
      <CategoryForm
        key={key}
        category={editing.category}
        parentId={editing.parentId}
        tops={tops}
        accounts={accounts.filter((a) => a.type === "expense" && a.isActive)}
        onDone={() => setEditing(null)}
      />
    );
  return (
    <div className="space-y-4">
      {canEdit && !editing && (
        <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setEditing({ category: null, parentId: null })}>
          Add a category
        </Button>
      )}
      {editing && !editing.category && !editing.parentId && form("new")}
      <ul className="divide-y divide-rule border-y border-rule">
        {tops.map((top) => {
          const subs = categories.filter((c) => c.parentId === top.id);
          return (
            <li key={top.id} className={`py-3 ${top.isActive ? "" : "text-ink-3"}`}>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <p className="flex items-center gap-1 text-sm font-semibold">
                  {top.name}
                  {canEdit && (
                    <Button size="sm" variant="quiet" className="!px-1.5" aria-label={`Edit ${top.name}`} onClick={() => setEditing({ category: top, parentId: null })}>
                      <Pencil className="size-3.5" aria-hidden />
                    </Button>
                  )}
                </p>
                <span className="text-meta text-ink-2">{top.account ? `${top.account.code} · ${top.account.name}` : <span className="text-danger">No account</span>}</span>
                <span className={`rounded-full px-2 py-0.5 text-meta ${top.reimbursable ? "bg-hema-tint text-hema" : "bg-bench text-ink-2"}`}>
                  {top.reimbursable ? "Reimbursable" : "Non-reimbursable"}
                </span>
                {!top.isActive && <span className="text-meta">inactive</span>}
              </div>
              {top.description && <p className="text-meta text-ink-3">{top.description}</p>}
              {editing?.category?.id === top.id && <div className="mt-3">{form(top.id)}</div>}
              <ul className="mt-2 ml-4 space-y-1 border-l border-rule pl-3">
                {subs.map((sub) => (
                  <li key={sub.id} className={`text-sm ${sub.isActive ? "text-ink-2" : "text-ink-3"}`}>
                    <span className="flex items-center gap-1">
                      {sub.name}
                      {!sub.isActive && <span className="text-meta">(inactive)</span>}
                      {canEdit && (
                        <Button size="sm" variant="quiet" className="!px-1.5" aria-label={`Edit ${sub.name}`} onClick={() => setEditing({ category: sub, parentId: top.id })}>
                          <Pencil className="size-3.5" aria-hidden />
                        </Button>
                      )}
                    </span>
                    {editing?.category?.id === sub.id && <div className="my-2">{form(sub.id)}</div>}
                  </li>
                ))}
                {canEdit && (
                  <li>
                    {editing && !editing.category && editing.parentId === top.id ? (
                      form(`new-${top.id}`)
                    ) : (
                      <Button size="sm" variant="quiet" className="-ml-3" icon={<Plus className="size-3.5" aria-hidden />} onClick={() => setEditing({ category: null, parentId: top.id })}>
                        Add a sub-category
                      </Button>
                    )}
                  </li>
                )}
              </ul>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function CategoryForm({
  category,
  parentId,
  tops,
  accounts,
  onDone,
}: {
  category: ExpenseCategory | null;
  parentId: string | null;
  tops: ExpenseCategory[];
  accounts: Account[];
  onDone: () => void;
}) {
  const sub = parentId !== null;
  const [name, setName] = useState(category?.name ?? "");
  const [parent, setParent] = useState(parentId ?? "");
  const [accountId, setAccountId] = useState(category?.account?.id ?? "");
  const [description, setDescription] = useState(category?.description ?? "");
  const [reimbursable, setReimbursable] = useState(category?.reimbursable ?? true);
  const [isActive, setActive] = useState(category?.isActive ?? true);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setFields({ name: "Enter a name." });
    start(async () => {
      const result = await saveCategory(category?.id ?? null, {
        name: name.trim(),
        parentId: sub ? parent : null,
        accountId: sub ? null : accountId || null,
        description: description.trim() || null,
        reimbursable,
        isActive,
      });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(category ? "Saved" : sub ? "Sub-category added" : "Category added", { description: result.data.label });
      onDone();
    });
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-4 rounded-[3px] border border-rule bg-sheet p-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={sub ? "Sub-category name" : "Category name"} error={fields.name}>
          {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} placeholder={sub ? "Dining" : "Food"} autoFocus />}
        </Field>
        {sub ? (
          <Field label="Parent category" error={fields.parentId}>
            {(p) => (
              <Select {...p} value={parent} onChange={(e) => setParent(e.target.value)}>
                {tops.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        ) : (
          <Field label="Expense account" error={fields.accountId} hint="Expenses in this category and its sub-categories post to this account.">
            {(p) => (
              <Select {...p} value={accountId} onChange={(e) => setAccountId(e.target.value)}>
                <option value="">Select an account…</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} · {a.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}
      </div>
      <Field label="Description" optional error={fields.description}>
        {(p) => <Input {...p} value={description} onChange={(e) => setDescription(e.target.value)} />}
      </Field>
      {!sub && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={reimbursable} onChange={(e) => setReimbursable(e.target.checked)} className="size-4 accent-hema" />
          Reimbursable (charged to the company)
        </label>
      )}
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={isActive} onChange={(e) => setActive(e.target.checked)} className="size-4 accent-hema" />
        Active (available in new liquidations)
      </label>
      <FormError message={error} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          {category ? "Save" : "Add"}
        </Button>
        <Button variant="quiet" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
