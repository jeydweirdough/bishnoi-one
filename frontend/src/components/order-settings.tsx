"use client";

import { ArrowDown, ArrowUp, Plus, X } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { saveOrderFields, saveOrderList, saveOrderRules } from "../actions/orders";
import { makeFormat, plural, type Format } from "@/src/platform/lib/format";
import type { OrderField, OrderFieldType, OrderListItem, OrderListKind, OrderSettings, Org } from "@/src/platform/lib/types";
import { IconButton, ListEditor, listDetail, listRows, moved, type ListRow } from "@/src/platform/ui/list-editor";
import { PickList, SaveBar, type PickItem } from "@/src/platform/ui/pick-list";

// Settings -> Orders: pick one list (or the extra fields, or the rules), then
// edit only that. Each keeps its unsaved changes while another is open.

type View = OrderListKind | "fields" | "rules";
type FieldRow = {
  id: string;
  key?: string;
  label: string;
  type: OrderFieldType;
  required: boolean;
  options: string;
  help: string;
  section: string;
  isActive: boolean;
};
type RulesDraft = { large: string; days: string; prefix: string };

const FIELD_TYPES: { value: OrderFieldType; label: string }[] = [
  { value: "text", label: "Short text" },
  { value: "textarea", label: "Long text" },
  { value: "number", label: "Number" },
  { value: "date", label: "Date" },
  { value: "choice", label: "Choice" },
];

let counter = 0;
const newId = () => `new-${++counter}`;

const fieldRows = (fields: OrderField[]): FieldRow[] =>
  fields.map((f) => ({
    id: f.key,
    key: f.key,
    label: f.label,
    type: f.type,
    required: f.required,
    options: f.options.join(", "),
    help: f.help,
    section: f.section ?? "",
    isActive: f.isActive,
  }));
const rulesDraft = (fmt: Format, r: OrderSettings["rules"]): RulesDraft => ({
  large: fmt.pesosText(r.largeOrderCentavos),
  days: String(r.recycleDays),
  prefix: r.orderPrefix,
});
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

export function OrderSettingsEditor({ data, org }: { data: OrderSettings; org: Org }) {
  const fmt = makeFormat(org);
  const [view, setView] = useState<View>(data.kinds[0]?.kind ?? "fields");
  const [lists, setLists] = useState<Partial<Record<OrderListKind, ListRow[]>>>({});
  const [fields, setFields] = useState<FieldRow[] | undefined>();
  const [rules, setRules] = useState<RulesDraft | undefined>();

  const listDirty = (kind: OrderListKind) => lists[kind] !== undefined && !same(lists[kind], listRows(data.lists[kind]));
  const fieldsDirty = fields !== undefined && !same(fields, fieldRows(data.fields));
  const rulesDirty = rules !== undefined && !same(rules, rulesDraft(fmt, data.rules));
  const setList = (kind: OrderListKind) => (rows: ListRow[] | undefined) => setLists((all) => ({ ...all, [kind]: rows }));

  const items: PickItem[] = [
    ...data.kinds.map((k) => ({
      key: k.kind,
      label: k.label,
      detail: listDetail(data.lists[k.kind]),
      group: "Pick-lists",
      unsaved: listDirty(k.kind),
    })),
    {
      key: "fields",
      label: "Extra fields",
      detail: data.fields.length ? plural(data.fields.length, "field") : "None yet",
      group: "The order form",
      unsaved: fieldsDirty,
    },
    {
      key: "rules",
      label: "Rules",
      detail: `${data.rules.orderPrefix} numbers · second look from ${fmt.pesoCompact(data.rules.largeOrderCentavos)}`,
      group: "The order form",
      unsaved: rulesDirty,
    },
  ];
  const kind = data.kinds.find((k) => k.kind === view);

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[17rem_minmax(0,1fr)] lg:items-start">
      <PickList title="Order settings" icon="orders" items={items} selected={view} onSelect={(key) => setView(key as View)} />
      {kind && (
        <ListEditor
          key={kind.kind}
          icon="orders"
          label={kind.label}
          hint={kind.hint}
          note="Switched-off choices stay on the orders that used them, but can't be picked for new ones."
          savedNote="The Orders app offers them on its next order."
          rows={lists[kind.kind] ?? listRows(data.lists[kind.kind])}
          dirty={listDirty(kind.kind)}
          setRows={setList(kind.kind)}
          onSave={(items) => saveOrderList(kind.kind, items.map(({ code, name, isActive }) => ({ code, name, isActive })))}
        />
      )}
      {view === "fields" && (
        <FieldsEditor
          rows={fields ?? fieldRows(data.fields)}
          sections={data.lists.field_section.filter((s) => s.isActive)}
          dirty={fieldsDirty}
          setRows={setFields}
        />
      )}
      {view === "rules" && <RulesEditor fmt={fmt} draft={rules ?? rulesDraft(fmt, data.rules)} dirty={rulesDirty} setDraft={setRules} />}
    </div>
  );
}

function FieldsEditor({
  rows,
  sections,
  dirty,
  setRows,
}: {
  rows: FieldRow[];
  sections: OrderListItem[];
  dirty: boolean;
  setRows: (rows: FieldRow[] | undefined) => void;
}) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, start] = useTransition();

  const change = (i: number, patch: Partial<FieldRow>) => setRows(rows.map((r, n) => (n === i ? { ...r, ...patch } : r)));
  const optionsOf = (r: FieldRow) =>
    r.options
      .split(",")
      .map((o) => o.trim())
      .filter(Boolean);

  function save() {
    const found: Record<string, string> = {};
    rows.forEach((r, i) => {
      if (r.label.trim().length < 2) found[`fields.${i}.label`] = "Name it (2 letters or more).";
      if (r.type === "choice" && new Set(optionsOf(r)).size < 2) found[`fields.${i}.options`] = "A choice needs at least two options.";
    });
    setErrors(found);
    if (Object.keys(found).length) return;
    start(async () => {
      const result = await saveOrderFields(
        rows.map((r) => ({
          key: r.key,
          label: r.label.trim(),
          type: r.type,
          required: r.required,
          options: r.type === "choice" ? optionsOf(r) : [],
          help: r.help.trim(),
          section: r.section || null,
          isActive: r.isActive,
        })),
      );
      if (!result.ok) {
        setErrors(result.fields ?? {});
        return setError(result.error);
      }
      setError(null);
      setRows(undefined);
      toast.success("Extra fields saved", {
        description: "The Orders app asks for them on its next order.",
      });
    });
  }

  return (
    <Sheet className="px-5 pt-4 pb-5">
      <SectionTitle icon="orders">Extra fields</SectionTitle>
      <p className="text-meta text-ink-3">
        Questions the order form asks on top of the ones every order has (customer, items, payment, delivery). Switched-off fields stay on
        the orders that have them.
      </p>
      {rows.length === 0 && <p className="mt-4 text-sm text-ink-2">No extra fields. Every order asks only the usual questions.</p>}
      <ol className="mt-3 space-y-3">
        {rows.map((row, i) => (
          <li key={row.id} className="rounded-[3px] border border-rule px-4 pt-3 pb-4">
            <div className="flex items-start gap-3">
              <div className="grid min-w-0 flex-1 gap-3 sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
                <Field label="Question" error={errors[`fields.${i}.label`]}>
                  {(p) => <Input {...p} value={row.label} maxLength={80} onChange={(e) => change(i, { label: e.target.value })} />}
                </Field>
                <Field label="Answer">
                  {(p) => (
                    <Select {...p} value={row.type} onChange={(e) => change(i, { type: e.target.value as OrderFieldType })}>
                      {FIELD_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>
                          {t.label}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
                {row.type === "choice" && (
                  <Field
                    label="Options"
                    hint="Separated by commas: Yes, No"
                    error={errors[`fields.${i}.options`]}
                    className="sm:col-span-2"
                  >
                    {(p) => <Input {...p} value={row.options} onChange={(e) => change(i, { options: e.target.value })} />}
                  </Field>
                )}
                <Field label="Help text" optional>
                  {(p) => <Input {...p} value={row.help} maxLength={200} onChange={(e) => change(i, { help: e.target.value })} />}
                </Field>
                <Field label="Where on the form" hint={sections.length ? undefined : "Add some sections first, under Form sections."}>
                  {(p) => (
                    <Select {...p} value={row.section} onChange={(e) => change(i, { section: e.target.value })}>
                      <option value="">{sections.length ? `Last — ${sections[sections.length - 1].name}` : "Anywhere"}</option>
                      {sections.map((s) => (
                        <option key={s.code} value={s.code}>
                          {s.name}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
              </div>
              <div className="flex shrink-0 flex-col items-center pt-5">
                <IconButton label={`Move ${row.label || "this field"} up`} disabled={i === 0} onClick={() => setRows(moved(rows, i, -1))}>
                  <ArrowUp className="size-4" aria-hidden />
                </IconButton>
                <IconButton
                  label={`Move ${row.label || "this field"} down`}
                  disabled={i === rows.length - 1}
                  onClick={() => setRows(moved(rows, i, 1))}
                >
                  <ArrowDown className="size-4" aria-hidden />
                </IconButton>
                <IconButton label={`Remove ${row.label || "this field"}`} onClick={() => setRows(rows.filter((_, n) => n !== i))}>
                  <X className="size-4" aria-hidden />
                </IconButton>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-meta text-ink-2">
              <label className="flex h-8 cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={row.required}
                  onChange={(e) => change(i, { required: e.target.checked })}
                  className="size-4 accent-hema"
                />
                Must be answered
              </label>
              <label className="flex h-8 cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={row.isActive}
                  onChange={(e) => change(i, { isActive: e.target.checked })}
                  className="size-4 accent-hema"
                />
                On
              </label>
            </div>
          </li>
        ))}
      </ol>
      <Button
        size="sm"
        className="mt-4"
        icon={<Plus className="size-4" aria-hidden />}
        onClick={() =>
          setRows([
            ...rows,
            {
              id: newId(),
              label: "",
              type: "text",
              required: false,
              options: "",
              section: "",
              help: "",
              isActive: true,
            },
          ])
        }
        disabled={rows.length >= 30}
      >
        Add a field
      </Button>
      {dirty && (
        <SaveBar
          what="Unsaved changes to the extra fields"
          saving={saving}
          onSave={save}
          onDiscard={() => {
            setRows(undefined);
            setErrors({});
            setError(null);
          }}
          error={<FormError message={error} />}
        />
      )}
    </Sheet>
  );
}

function RulesEditor({ fmt, draft, dirty, setDraft }: { fmt: Format; draft: RulesDraft; dirty: boolean; setDraft: (d: RulesDraft | undefined) => void }) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, start] = useTransition();
  const prefix = draft.prefix.toUpperCase();
  const today = new Date();
  const stamp = `${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, "0")}${String(today.getDate()).padStart(2, "0")}`;

  function save() {
    const large = fmt.toCentavos(draft.large);
    const days = Number(draft.days);
    const found: Record<string, string> = {};
    if (large === null) found.largeOrderCentavos = `An amount in ${fmt.currency}, like 100000.`;
    if (!Number.isInteger(days) || days < 1 || days > 365) found.recycleDays = "Whole days, 1 to 365.";
    if (!/^[A-Z0-9]{1,8}$/.test(prefix)) found.orderPrefix = "Up to 8 letters or digits.";
    setErrors(found);
    if (Object.keys(found).length || large === null) return;
    start(async () => {
      const result = await saveOrderRules({
        largeOrderCentavos: large,
        recycleDays: days,
        orderPrefix: prefix,
      });
      if (!result.ok) {
        setErrors(result.fields ?? {});
        return setError(result.error);
      }
      setError(null);
      setDraft(undefined);
      toast.success("Order rules saved");
    });
  }

  const large = fmt.toCentavos(draft.large);
  return (
    <Sheet className="max-w-[40rem] px-5 pt-4 pb-5">
      <SectionTitle icon="orders">Rules</SectionTitle>
      <div className="mt-2 space-y-5">
        <Field
          label="Large orders, from"
          error={errors.largeOrderCentavos}
          hint={`Open orders from ${large !== null ? fmt.peso(large) : "this amount"} up get a second look before Finance verifies payment.`}
        >
          {(p) => (
            <div className="flex items-center gap-2">
              <span className="text-ink-3">{fmt.symbol}</span>
              <Input
                {...p}
                inputMode="decimal"
                value={draft.large}
                onChange={(e) => setDraft({ ...draft, large: e.target.value })}
                className="max-w-48"
              />
            </div>
          )}
        </Field>
        <Field
          label="Recycle bin keeps deleted orders for"
          error={errors.recycleDays}
          hint="Until then an admin can restore them; after that they're gone for good."
        >
          {(p) => (
            <div className="flex items-center gap-2">
              <Input
                {...p}
                inputMode="numeric"
                value={draft.days}
                onChange={(e) => setDraft({ ...draft, days: e.target.value })}
                className="max-w-20"
              />
              <span className="text-ink-3">days</span>
            </div>
          )}
        </Field>
        <Field
          label="Order numbers start with"
          error={errors.orderPrefix}
          hint={
            <>
              The next order today would be{" "}
              <span className="font-semibold text-ink-2">
                {prefix || "?"}-{stamp}-0001
              </span>
              . Old orders keep their numbers.
            </>
          }
        >
          {(p) => (
            <Input
              {...p}
              value={draft.prefix}
              maxLength={8}
              autoCapitalize="characters"
              onChange={(e) =>
                setDraft({
                  ...draft,
                  prefix: e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""),
                })
              }
              className="max-w-28 uppercase"
            />
          )}
        </Field>
      </div>
      {dirty && (
        <SaveBar
          what="Unsaved changes to the order rules"
          saving={saving}
          onSave={save}
          onDiscard={() => {
            setDraft(undefined);
            setErrors({});
            setError(null);
          }}
          error={<FormError message={error} />}
        />
      )}
    </Sheet>
  );
}
