"use client";

import {
  ArrowDown,
  ArrowUp,
  AtSign,
  Calendar,
  CheckSquare,
  ChevronDown,
  Coins,
  EyeOff,
  Hash,
  Link2,
  List,
  ListChecks,
  Lock,
  Phone,
  Plus,
  Trash2,
  Type,
  AlignLeft,
  GripVertical,
  Package,
  FlaskConical,
  Building2,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition, type ReactNode } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, Input } from "@/src/platform/ui/field";
import { Sheet } from "@/src/platform/ui/sheet";
import type { CustomEntity, FormFieldDef, FormLayout } from "@/src/platform/lib/types";
import { saveForm, type SectionDraft } from "../../actions/settings";
import { ChipsInput } from "../admin/chips-input";
import { Select as AntSelect } from "antd";
import { TeamsFor, type TeamName } from "../admin/teams-for";

// The form editor (Settings → Forms), laid out like Zoho's: the kinds of field
// on the left, the form itself in the middle, the picked field's properties on
// the right. Nothing is saved until Save; Discard puts it back as it was.

type Kind = { type: string; label: string; icon: ReactNode };
const KINDS: Kind[] = [
  { type: "text", label: "Single line", icon: <Type className="size-4" /> },
  { type: "long_text", label: "Multi-line", icon: <AlignLeft className="size-4" /> },
  { type: "number", label: "Number", icon: <Hash className="size-4" /> },
  { type: "money", label: "Currency", icon: <Coins className="size-4" /> },
  { type: "date", label: "Date", icon: <Calendar className="size-4" /> },
  { type: "choice", label: "Pick list", icon: <List className="size-4" /> },
  { type: "multi_choice", label: "Multi-select", icon: <ListChecks className="size-4" /> },
  { type: "yes_no", label: "Checkbox", icon: <CheckSquare className="size-4" /> },
  { type: "email", label: "Email", icon: <AtSign className="size-4" /> },
  { type: "phone", label: "Phone", icon: <Phone className="size-4" /> },
  { type: "url", label: "URL", icon: <Link2 className="size-4" /> },
  { type: "products", label: "Our products", icon: <Package className="size-4" /> },
  { type: "molecule", label: "Molecule", icon: <FlaskConical className="size-4" /> },
  { type: "customer", label: "Another customer", icon: <Building2 className="size-4" /> },
];
const BUILT_IN_KINDS: Record<string, string> = { status: "Customer type", owner: "Owner", company: "Customer" };
const kindLabel = (t: string) => KINDS.find((k) => k.type === t)?.label ?? BUILT_IN_KINDS[t] ?? t;
const kindIcon = (t: string) => KINDS.find((k) => k.type === t)?.icon ?? <Lock className="size-4" />;

/** What's fixed on a form and not the editor's to move. */
const FIXED: Partial<Record<CustomEntity, { where: "top" | "bottom"; text: string }>> = {
  product: { where: "bottom", text: "Prices: one per price type, set under the form. Built in." },
  quote: { where: "top", text: "Price type, products and bundles, promos, discounts, who pays and the guarantee letter. Built in." },
};

type F = FormFieldDef & { uid: string };
type S = { uid: string; id: string | null; title: string; columns: 1 | 2; fields: F[] };

let counter = 0;
const uid = () => `u${++counter}`;
const fromLayout = (layout: FormLayout): S[] =>
  layout.sections.map((s) => ({ uid: uid(), id: s.id, title: s.title, columns: s.columns, fields: s.fields.map((f) => ({ ...f, uid: uid() })) }));

export function FormEditor({
  entity,
  layout,
  teams = [],
  kinds = [],
}: {
  entity: CustomEntity;
  layout: FormLayout;
  teams?: TeamName[];
  /** The customer types, for "Which customer types" (customers' form only). */
  kinds?: TeamName[];
}) {
  const router = useRouter();
  const [saved, setSaved] = useState(() => fromLayout(layout));
  const [sections, setSections] = useState<S[]>(saved);
  const [picked, setPicked] = useState<string | null>(null);
  const [dragging, setDragging] = useState<{ field?: string; kind?: string } | null>(null);
  const [pending, start] = useTransition();
  const dirty = useMemo(() => JSON.stringify(sections) !== JSON.stringify(saved), [sections, saved]);
  const field = sections.flatMap((s) => s.fields).find((f) => f.uid === picked) ?? null;
  const fixed = FIXED[entity];

  const update = (fn: (all: S[]) => S[]) => setSections((all) => fn(structuredClone(all)));

  function newField(type: string): F {
    const label = `New ${kindLabel(type).toLowerCase()}`;
    const taken = new Set(sections.flatMap((s) => s.fields.map((f) => f.label.toLowerCase())));
    let name = label;
    for (let n = 2; taken.has(name.toLowerCase()); n++) name = `${label} ${n}`;
    return {
      uid: uid(), id: "", key: "", label: name, type: type as F["type"], standard: false, locked: false, required: false, hidden: false,
      inList: false, options: type === "choice" || type === "multi_choice" ? ["Option 1", "Option 2"] : [], helpText: null, placeholder: null, used: 0,
    };
  }

  /** Puts a field (moved, or new) into a section, before `before` (or at the end). */
  function place(sectionUid: string, before: string | null) {
    if (!dragging) return;
    update((all) => {
      let moving: F | undefined;
      if (dragging.field) {
        for (const s of all) {
          const i = s.fields.findIndex((f) => f.uid === dragging.field);
          if (i >= 0) moving = s.fields.splice(i, 1)[0];
        }
      } else if (dragging.kind) {
        moving = newField(dragging.kind);
        setPicked(moving.uid);
      }
      if (!moving) return all;
      const target = all.find((s) => s.uid === sectionUid)!;
      const at = before ? target.fields.findIndex((f) => f.uid === before) : -1;
      target.fields.splice(at < 0 ? target.fields.length : at, 0, moving);
      return all;
    });
    setDragging(null);
  }

  function add(type: string) {
    const f = newField(type);
    update((all) => {
      const into = all.find((s) => s.fields.some((x) => x.uid === picked)) ?? all[all.length - 1];
      into.fields.push(f);
      return all;
    });
    setPicked(f.uid);
  }

  function change(patch: Partial<F>) {
    update((all) => {
      for (const s of all) for (const f of s.fields) if (f.uid === picked) Object.assign(f, patch);
      return all;
    });
  }

  function remove() {
    update((all) => {
      for (const s of all) s.fields = s.fields.filter((f) => f.uid !== picked);
      return all;
    });
    setPicked(null);
  }

  function save() {
    const body: SectionDraft[] = sections.map((s) => ({
      id: s.id,
      title: s.title.trim() || "Untitled section",
      columns: s.columns,
      fields: s.fields.map((f) => ({
        id: f.id || null,
        label: f.label.trim(),
        type: f.type,
        required: f.required,
        hidden: f.hidden,
        inList: f.inList,
        options: f.options,
        helpText: f.helpText?.trim() || null,
        placeholder: f.placeholder?.trim() || null,
        optionNames: Object.fromEntries(Object.entries(f.optionNames ?? {}).filter(([o, n]) => f.options.includes(o) && n.trim())),
        unique: f.unique ?? false,
        onlyTeams: f.onlyTeams ?? [],
        exceptTeams: f.exceptTeams ?? [],
        onlyTypes: f.onlyTypes ?? [],
        exceptTypes: f.exceptTypes ?? [],
      })),
    }));
    start(async () => {
      const r = await saveForm(entity, body);
      if (!r.ok) return void toast.error(r.error);
      const fresh = fromLayout(r.data);
      setSaved(fresh);
      setSections(fresh);
      setPicked(null);
      toast.success("Form saved", { description: "Everyone sees it on their next page." });
      router.refresh();
    });
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[13rem_minmax(0,1fr)_18rem] lg:items-start">
      {/* The kinds of field: click to add to the picked field's section, or drag onto the form. */}
      <Sheet className="px-3 py-3 lg:sticky lg:top-4">
        <p className="px-2 pb-2 text-caps font-semibold text-ink-3 uppercase">New field</p>
        <ul className="grid grid-cols-2 gap-1 lg:grid-cols-1">
          {KINDS.map((k) => (
            <li key={k.type}>
              <button
                type="button"
                draggable
                onDragStart={() => setDragging({ kind: k.type })}
                onDragEnd={() => setDragging(null)}
                onClick={() => add(k.type)}
                className="flex w-full cursor-grab items-center gap-2 rounded-[6px] border border-transparent px-2 py-1.5 text-left text-sm text-ink-2 hover:border-rule-strong hover:bg-bench hover:text-ink"
              >
                <span className="text-ink-3">{k.icon}</span>
                {k.label}
              </button>
            </li>
          ))}
        </ul>
      </Sheet>

      {/* The form. */}
      <div className="min-w-0 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-meta text-ink-3">Drag fields to move them. Click one to change it.</p>
          <span className="flex gap-2">
            {dirty && (
              <Button variant="quiet" onClick={() => (setSections(saved), setPicked(null))}>
                Discard changes
              </Button>
            )}
            <Button variant="primary" loading={pending} disabled={!dirty} onClick={save}>
              Save form
            </Button>
          </span>
        </div>

        {fixed?.where === "top" && <FixedBlock text={fixed.text} />}

        {sections.map((s, i) => (
          <Sheet key={s.uid} className="px-4 pt-3 pb-4">
            <div className="flex flex-wrap items-center gap-2 border-b border-rule pb-2">
              <input
                aria-label="Section name"
                value={s.title}
                onChange={(e) => update((all) => ((all[i].title = e.target.value), all))}
                className="min-w-0 flex-1 border-0 border-b border-transparent bg-transparent px-0 text-sm font-semibold text-ink hover:border-rule focus:border-hema focus:outline-none"
              />
              <span className="inline-flex rounded-[6px] border border-rule-strong p-0.5 text-meta">
                {([1, 2] as const).map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => update((all) => ((all[i].columns = c), all))}
                    className={`rounded-[4px] px-2 py-0.5 ${s.columns === c ? "bg-hema-tint font-semibold text-ink" : "text-ink-2"}`}
                  >
                    {c} column{c === 2 ? "s" : ""}
                  </button>
                ))}
              </span>
              <IconButton label="Move section up" disabled={i === 0} onClick={() => update((all) => (all.splice(i - 1, 0, all.splice(i, 1)[0]), all))}>
                <ArrowUp className="size-3.5" />
              </IconButton>
              <IconButton
                label="Move section down"
                disabled={i === sections.length - 1}
                onClick={() => update((all) => (all.splice(i + 1, 0, all.splice(i, 1)[0]), all))}
              >
                <ArrowDown className="size-3.5" />
              </IconButton>
              <IconButton
                label={s.fields.length ? "Move its fields out to remove this section" : "Remove section"}
                disabled={s.fields.length > 0 || sections.length === 1}
                onClick={() => update((all) => (all.splice(i, 1), all))}
              >
                <Trash2 className="size-3.5" />
              </IconButton>
            </div>
            <ul
              className={`mt-3 grid min-h-14 gap-2 ${s.columns === 2 ? "sm:grid-cols-2" : ""} rounded-[6px] ${dragging ? "outline-1 outline-offset-4 outline-rule-strong outline-dashed" : ""}`}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                place(s.uid, null);
              }}
            >
              {s.fields.length === 0 && <li className="col-span-full py-3 text-center text-meta text-ink-3">Drop fields here</li>}
              {s.fields.map((f) => (
                <li
                  key={f.uid}
                  draggable
                  onDragStart={(e) => {
                    e.stopPropagation();
                    setDragging({ field: f.uid });
                  }}
                  onDragEnd={() => setDragging(null)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    place(s.uid, f.uid);
                  }}
                  onClick={() => setPicked(f.uid)}
                  className={`group flex cursor-pointer items-center gap-2 rounded-[6px] border px-2.5 py-2 text-sm ${
                    picked === f.uid ? "border-hema bg-hema-tint" : "border-rule-strong bg-sheet hover:border-hema"
                  } ${f.hidden ? "opacity-50" : ""} ${(f.type === "long_text" || f.type === "multi_choice") && s.columns === 2 ? "sm:col-span-2" : ""}`}
                >
                  <GripVertical className="size-4 shrink-0 cursor-grab text-ink-3" aria-hidden />
                  <span className="shrink-0 text-ink-3">{kindIcon(f.type)}</span>
                  <span className="min-w-0 flex-1 truncate">
                    {f.label}
                    {f.required && <span className="text-danger"> *</span>}
                  </span>
                  {f.hidden && <EyeOff className="size-3.5 shrink-0 text-ink-3" aria-label="Hidden" />}
                  {f.standard && <Lock className="size-3.5 shrink-0 text-ink-3" aria-label="Built in" />}
                  <span className="hidden shrink-0 text-meta text-ink-3 xl:inline">{kindLabel(f.type)}</span>
                </li>
              ))}
            </ul>
          </Sheet>
        ))}

        <Button
          variant="quiet"
          icon={<Plus className="size-4" aria-hidden />}
          onClick={() => update((all) => [...all, { uid: uid(), id: null, title: "New section", columns: 2, fields: [] }])}
        >
          Add section
        </Button>

        {fixed?.where === "bottom" && <FixedBlock text={fixed.text} />}
      </div>

      {/* The picked field's properties. */}
      <Sheet className="px-4 py-4 lg:sticky lg:top-4">
        {field ? (
          <Properties key={field.uid} field={field} onChange={change} onRemove={remove} teams={teams} kinds={kinds} entity={entity} />
        ) : (
          <div className="py-6 text-center text-meta text-ink-3">
            <ChevronDown className="mx-auto mb-2 size-5 rotate-90 lg:rotate-0" aria-hidden />
            Click a field on the form to change its name, whether it&apos;s required, its options and more.
          </div>
        )}
      </Sheet>
    </div>
  );
}

function FixedBlock({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-2 rounded-[6px] border border-dashed border-rule-strong bg-bench/60 px-4 py-3 text-meta text-ink-3">
      <Lock className="size-3.5 shrink-0" aria-hidden />
      {text}
    </div>
  );
}

function IconButton({ label, disabled, onClick, children }: { label: string; disabled?: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" title={label} aria-label={label} disabled={disabled} onClick={onClick} className="rounded-[6px] p-1 text-ink-3 hover:bg-bench hover:text-ink disabled:opacity-30">
      {children}
    </button>
  );
}

/** Who a field is on the form for: everyone, only some teams (the Rx team's own fields), or everyone but some. */
function WhoFor({ field: f, teams, onChange }: { field: F; teams: TeamName[]; onChange: (patch: Partial<F>) => void }) {
  return (
    <div className="space-y-2">
      <p className="text-sm text-ink">Who it&apos;s for</p>
      <TeamsFor teams={teams} only={f.onlyTeams} except={f.exceptTeams} onChange={(onlyTeams, exceptTeams) => onChange({ onlyTeams, exceptTeams })} what="this field" />
    </div>
  );
}

/** Full names for short options ("MED ONCO": "Medical oncology"): the short one is shown, either can be searched. */
function OptionNames({ field: f, onChange }: { field: F; onChange: (patch: Partial<F>) => void }) {
  const names = f.optionNames ?? {};
  const filled = Object.values(names).filter((n) => n.trim()).length;
  return (
    <details className="rounded-sheet border border-rule px-3 py-2" open={filled > 0}>
      <summary className="cursor-pointer text-sm text-ink">
        Full names {filled > 0 && <span className="text-ink-3">({filled})</span>}
      </summary>
      <p className="mt-1 text-meta text-ink-3">For options that are short codes. People see the code and can search by either.</p>
      <div className="mt-2 space-y-1.5">
        {f.options.map((o) => (
          <label key={o} className="grid grid-cols-[minmax(0,7rem)_1fr] items-center gap-2 text-sm">
            <span className="truncate text-ink-2">{o}</span>
            <Input value={names[o] ?? ""} onChange={(e) => onChange({ optionNames: { ...names, [o]: e.target.value } })} maxLength={120} placeholder="Full name" />
          </label>
        ))}
      </div>
    </details>
  );
}

function Properties({
  field,
  onChange,
  onRemove,
  teams,
  kinds,
  entity,
}: {
  field: F;
  onChange: (patch: Partial<F>) => void;
  onRemove: () => void;
  teams: TeamName[];
  kinds: TeamName[];
  entity: CustomEntity;
}) {
  const f = field;
  const withOptions = f.type === "choice" || f.type === "multi_choice";
  const box = (label: string, value: boolean, set: (v: boolean) => void, disabled = false, note?: string) => (
    <label className={`flex items-start gap-2 text-sm ${disabled ? "text-ink-3" : ""}`}>
      <input type="checkbox" checked={value} disabled={disabled} onChange={(e) => set(e.target.checked)} className="mt-0.5 size-4 accent-hema" />
      <span>
        {label}
        {note && <span className="block text-meta text-ink-3">{note}</span>}
      </span>
    </label>
  );
  return (
    <div className="space-y-4">
      <div>
        <p className="text-caps font-semibold text-ink-3 uppercase">{f.standard ? "Built-in field" : "Added field"}</p>
        <p className="mt-0.5 flex items-center gap-1.5 text-meta text-ink-2">
          {kindIcon(f.type)} {kindLabel(f.type)}
        </p>
      </div>
      <Field label="Name">{(p) => <Input {...p} value={f.label} onChange={(e) => onChange({ label: e.target.value })} maxLength={80} />}</Field>
      {withOptions && f.sharedList ? (
        <p className="text-meta text-ink-2">
          Its choices are the lead sources deals use. Change them in{" "}
          <a href="/admin/settings/deal-stages" className="text-ink hover:underline">
            Settings → Deal stages
          </a>
          .
        </p>
      ) : withOptions && (
        <ChipsInput
          label={f.type === "choice" ? "Pick list options" : "Options"}
          value={f.options}
          onChange={(options) => onChange({ options })}
          placeholder="Type an option"
          max={100}
          optional={false}
        />
      )}
      {f.type === "choice" && !f.sharedList && f.options.length > 0 && <OptionNames field={f} onChange={onChange} />}
      {f.type === "customer" && entity === "company" && (
        <div className="space-y-1">
          <p className="text-sm text-ink">Which customer types it can be</p>
          <AntSelect
            mode="multiple"
            className="w-full"
            value={f.options}
            onChange={(options) => onChange({ options })}
            placeholder="Any customer"
            options={kinds.map((k) => ({ value: k.id, label: k.name }))}
            showSearch={{ optionFilterProp: "label" }}
          />
          <p className="text-meta text-ink-3">E.g. a doctor&apos;s hospital: Hospital, Cancer center. Its page lists who points at it.</p>
        </div>
      )}
      {f.type === "products" && (
        <div className="space-y-1">
          <p className="text-sm text-ink">Products not offered</p>
          <AntSelect
            mode="multiple"
            className="w-full"
            value={f.options}
            onChange={(options) => onChange({ options })}
            placeholder="Every active product is offered"
            options={(f.picks ?? []).map((p) => ({ value: p.value, label: p.hint ? `${p.label} (${p.hint})` : p.label }))}
            showSearch={{ optionFilterProp: "label" }}
          />
          <p className="text-meta text-ink-3">Left off this field&apos;s list, e.g. products not promoted. New products are offered until left out here.</p>
        </div>
      )}
      <div className="space-y-2">
        {box("Required", f.required, (required) => onChange({ required }), f.locked, f.locked ? "Always required: the record can't do without it." : undefined)}
        {box("Hidden", f.hidden, (hidden) => onChange({ hidden }), f.locked, f.locked ? "Always shown." : "Off the form; values already kept stay.")}
        {!["status", "owner", "company"].includes(f.type) && box("Show in the list", f.inList, (inList) => onChange({ inList }))}
        {!f.standard &&
          ["text", "number", "email", "phone"].includes(f.type) &&
          box("No two can be the same", f.unique ?? false, (unique) => onChange({ unique }), false, "Like a customer code: each record has its own.")}
      </div>
      {entity === "company" && !f.locked && teams.length > 0 && <WhoFor field={f} teams={teams} onChange={onChange} />}
      {entity === "company" && !f.locked && kinds.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm text-ink">Which customer types</p>
          <TeamsFor
            teams={kinds}
            only={f.onlyTypes}
            except={f.exceptTypes}
            onChange={(onlyTypes, exceptTypes) => onChange({ onlyTypes, exceptTypes })}
            notes={{
              everyone: "Asked of every kind of customer.",
              only: "Asked only of these kinds of customer (a doctor's profile, say).",
              except: "Not asked of these kinds of customer.",
              placeholder: "Pick customer types",
            }}
          />
        </div>
      )}
      {!["status", "owner", "company", "yes_no"].includes(f.type) && (
        <>
          <Field label="Help text" optional>
            {(p) => <Input {...p} value={f.helpText ?? ""} onChange={(e) => onChange({ helpText: e.target.value })} maxLength={200} placeholder="Shown under the field" />}
          </Field>
          {!withOptions && (
            <Field label="Placeholder" optional>
              {(p) => <Input {...p} value={f.placeholder ?? ""} onChange={(e) => onChange({ placeholder: e.target.value })} maxLength={80} placeholder="Shown inside, while empty" />}
            </Field>
          )}
        </>
      )}
      {!f.standard && (
        <div className="border-t border-rule pt-3">
          {f.used ? (
            <p className="text-meta text-ink-3">
              {f.used} {f.used === 1 ? "record has" : "records have"} a value in it, so it can be hidden but not deleted.
            </p>
          ) : (
            <Button variant="quiet" icon={<Trash2 className="size-4" aria-hidden />} onClick={onRemove} className="!text-danger">
              Delete field
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
