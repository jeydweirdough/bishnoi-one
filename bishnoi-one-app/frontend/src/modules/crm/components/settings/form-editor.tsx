"use client";

import {
  AlignLeft,
  ArrowLeft,
  AtSign,
  Building2,
  Calendar,
  CheckSquare,
  ChevronDown,
  ChevronUp,
  Coins,
  EyeOff,
  FlaskConical,
  GripVertical,
  Hash,
  Link2,
  List,
  ListChecks,
  Lock,
  Package,
  Phone,
  Plus,
  Search,
  Settings2,
  Trash2,
  Type,
} from "lucide-react";
import { Modal, Switch } from "antd";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition, type DragEvent, type ReactNode } from "react";
import { toast } from "sonner";
import { Button, IconButton } from "@/src/platform/ui/button";
import { Field, Input, Select, Textarea } from "@/src/platform/ui/field";
import { Sheet } from "@/src/platform/ui/sheet";
import type { CustomEntity, FormFieldDef, FormLayout } from "@/src/platform/lib/types";
import { saveForm, type SectionDraft } from "@/src/modules/crm/actions/settings";
import { useTerms } from "@/src/modules/crm/components/terms/provider";
import type { Terms } from "@/src/modules/crm/components/terms/terms";
import type { TeamName } from "@/src/modules/crm/components/admin/teams-for";

// The form designer (Settings → Forms).
//
// The form is drawn the way it reads, like a printed document: a title between
// two rules, each section a green band, its fields in bordered cells. Fields
// not on the form wait in the list on the left; drag one onto the page (or
// click it) to put it there, drag a cell to move it, and click a cell to change
// its label, whether it's required, its help text and its options. What's on
// the page is what's saved, and what everyone fills in.

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
  { type: "molecule", label: "Product family", icon: <FlaskConical className="size-4" /> },
  { type: "customer", label: "Another customer", icon: <Building2 className="size-4" /> },
];

const BUILT_IN_KINDS: Record<string, string> = { status: "Customer type", owner: "Owner", company: "Customer" };
const kindLabel = (t: string, words?: Terms) =>
  t === "molecule" && words ? words.genericName : KINDS.find((k) => k.type === t)?.label ?? BUILT_IN_KINDS[t] ?? t;
const kindIcon = (t: string) => KINDS.find((k) => k.type === t)?.icon ?? <Lock className="size-4" />;
const WITH_OPTIONS = new Set(["choice", "multi_choice"]);
const MAY_BE_UNIQUE = new Set(["text", "number", "email", "phone"]);

/** The title across the top of the page, as the document would be called. */
const TITLES: Record<CustomEntity, string> = { company: "Customer", contact: "Contact", product: "Product", quote: "Quotation" } as Record<CustomEntity, string>;

/** Realistic sample values, so the page reads like a filled-in record. */
const SAMPLE_VALUES: Record<string, string> = {
  name: "St. Luke's Medical Center - BGC",
  firstName: "Manuel",
  lastName: "Santos",
  jobTitle: "Chief of Medical Staff",
  email: "procurement@stlukes.com.ph",
  phone: "+63 (2) 8789-7700",
  website: "https://www.stlukes.com.ph",
  tin: "000-123-456-000",
  address: "32nd Street, Bonifacio Global City",
  city: "Taguig City",
  country: "Philippines",
  x_tier: "Tier 1 (Core)",
  x_pdea_s2: "PDEA-S2-2026-08841",
  x_s2_expiry: "31 Dec 2027",
  x_credit_status: "Good standing",
  x_account_lifecycle: "Active",
  x_stakeholder: "Pharmacy director",
  x_care_team_status: "Active prescriber",
  code: "MED-500",
  genericName: "Amoxicillin trihydrate",
  strength: "500 mg",
  notes: "Hospital tender pricing with 30-day term delivery.",
  x_payer_program: "PCSO / DOH MAIP",
  x_procurement_mode: "Small value procurement (RA 9184)",
};

type DraftSection = { ref: string; id: string | null; title: string; columns: 1 | 2; fields: FormFieldDef[] };
/** Where a dragged field is about to land: before a field, or at the end of a section. */
type Spot = { section: string; before: string | null };

let made = 0;
const newRef = () => `s${++made}`;

const fromLayout = (layout: FormLayout): DraftSection[] =>
  layout.sections.map((s) => ({ ref: s.id || newRef(), id: s.id || null, title: s.title, columns: s.columns, fields: s.fields }));

/** What would be saved, to tell whether anything changed. */
const fingerprint = (sections: DraftSection[]) =>
  JSON.stringify(sections.map((s) => [s.id, s.title, s.columns, s.fields.map((f) => [f.key, f.label, f.required, f.hidden, f.inList, f.unique, f.helpText, f.placeholder, f.options])]));

export function FormEditor({
  entity,
  layout,
}: {
  entity: CustomEntity;
  layout: FormLayout;
  teams?: TeamName[];
  kinds?: TeamName[];
}) {
  const terms = useTerms();
  const router = useRouter();
  const [sections, setSections] = useState<DraftSection[]>(() => fromLayout(layout));
  const [saved, setSaved] = useState(() => fingerprint(fromLayout(layout)));
  const [selected, setSelected] = useState<string | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);
  const [spot, setSpot] = useState<Spot | null>(null);
  const [search, setSearch] = useState("");
  const [sample, setSample] = useState(true);
  const [adding, setAdding] = useState(false);
  const [pending, startTransition] = useTransition();

  const dirty = fingerprint(sections) !== saved;
  const all = sections.flatMap((s) => s.fields);
  const onForm = all.filter((f) => !f.hidden).length;
  const waiting = all.filter((f) => f.hidden);
  const shown = waiting.filter((f) => !search.trim() || f.label.toLowerCase().includes(search.trim().toLowerCase()));
  const chosen = selected ? all.find((f) => f.key === selected) ?? null : null;

  // --- changes to the page ---

  /** Takes a field out of wherever it is and puts it at a spot, on the form. */
  function place(key: string, to: Spot) {
    setSections((list) => {
      const field = list.flatMap((s) => s.fields).find((f) => f.key === key);
      if (!field || key === to.before) return list;
      const without = list.map((s) => ({ ...s, fields: s.fields.filter((f) => f.key !== key) }));
      return without.map((s) => {
        if (s.ref !== to.section) return s;
        const at = to.before ? s.fields.findIndex((f) => f.key === to.before) : -1;
        const fields = [...s.fields];
        fields.splice(at < 0 ? fields.length : at, 0, { ...field, hidden: false });
        return { ...s, fields };
      });
    });
  }

  /** Off the page: built-in and used fields are kept, hidden; a field added since saving goes. */
  function takeOff(field: FormFieldDef) {
    if (field.locked) return;
    if (selected === field.key) setSelected(null);
    if (!field.id) {
      setSections((list) => list.map((s) => ({ ...s, fields: s.fields.filter((f) => f.key !== field.key) })));
      return;
    }
    change(field.key, { hidden: true });
  }

  /** Deleted for good: only an added field no record has a value in. */
  function remove(field: FormFieldDef) {
    setSections((list) => list.map((s) => ({ ...s, fields: s.fields.filter((f) => f.key !== field.key) })));
  }

  function change(key: string, patch: Partial<FormFieldDef>) {
    setSections((list) => list.map((s) => ({ ...s, fields: s.fields.map((f) => (f.key === key ? { ...f, ...patch } : f)) })));
  }

  function changeSection(ref: string, patch: Partial<DraftSection>) {
    setSections((list) => list.map((s) => (s.ref === ref ? { ...s, ...patch } : s)));
  }

  function moveSection(ref: string, by: -1 | 1) {
    setSections((list) => {
      const i = list.findIndex((s) => s.ref === ref);
      const j = i + by;
      if (i < 0 || j < 0 || j >= list.length) return list;
      const next = [...list];
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });
  }

  /** A section goes once nothing shows in it; its hidden fields move to the one beside it. */
  function dropSection(ref: string) {
    setSections((list) => {
      const i = list.findIndex((s) => s.ref === ref);
      if (i < 0 || list.length === 1) return list;
      const keep = list[i].fields;
      const next = list.filter((s) => s.ref !== ref);
      const into = Math.max(0, i - 1);
      next[into] = { ...next[into], fields: [...next[into].fields, ...keep] };
      return next;
    });
  }

  function addSection() {
    setSections((list) => [...list, { ref: newRef(), id: null, title: "New section", columns: 2, fields: [] }]);
  }

  /** A click on a waiting field: onto the end of the section being worked in, or the last one. */
  function addToPage(key: string) {
    const target = (chosen && sections.find((s) => s.fields.some((f) => f.key === chosen.key))) || sections[sections.length - 1];
    if (target) place(key, { section: target.ref, before: null });
  }

  function addField(field: FormFieldDef) {
    const target = sections[sections.length - 1];
    if (!target) return;
    setSections((list) => list.map((s) => (s.ref === target.ref ? { ...s, fields: [...s.fields, field] } : s)));
    setSelected(field.key);
  }

  // --- dragging ---

  const startDrag = (key: string) => (e: DragEvent) => {
    e.dataTransfer.setData("text/plain", key);
    e.dataTransfer.effectAllowed = "move";
    setDragging(key);
  };
  const over = (to: Spot) => (e: DragEvent) => {
    if (!dragging) return;
    e.preventDefault();
    e.stopPropagation();
    if (spot?.section !== to.section || spot.before !== to.before) setSpot(to);
  };
  const drop = (to: Spot) => (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const key = e.dataTransfer.getData("text/plain") || dragging;
    if (key) place(key, to);
    endDrag();
  };
  const endDrag = () => {
    setDragging(null);
    setSpot(null);
  };

  // --- saving ---

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
        optionNames: Object.fromEntries(
          Object.entries(f.optionNames ?? {})
            .filter(([o, n]) => f.options.includes(o) && typeof n === "string" && Boolean(n.trim()))
            .map(([o, n]) => [o, String(n).trim()]),
        ),
        unique: f.unique ?? false,
        onlyTeams: f.onlyTeams ?? [],
        exceptTeams: f.exceptTeams ?? [],
        onlyTypes: f.onlyTypes ?? [],
        exceptTypes: f.exceptTypes ?? [],
      })),
    }));
    startTransition(async () => {
      const result = await saveForm(entity, body);
      if (!result.ok) return void toast.error(result.error);
      const next = fromLayout(result.data);
      setSections(next);
      setSaved(fingerprint(next));
      setSelected(null);
      toast.success("Form saved", { description: "Everyone gets this form from now on." });
      router.refresh();
    });
  }

  function discard() {
    const back = fromLayout(layout);
    setSections(back);
    setSaved(fingerprint(back));
    setSelected(null);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-meta text-ink-3">
          {onForm} {onForm === 1 ? "field" : "fields"} on the form in {sections.length} {sections.length === 1 ? "section" : "sections"}. Drag fields onto the page, or click one to change it.
        </p>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-ink-2">
            <Switch size="small" checked={sample} onChange={setSample} />
            Sample values
          </label>
          {dirty && (
            <Button variant="quiet" onClick={discard}>
              Discard changes
            </Button>
          )}
          <Button variant="primary" loading={pending} disabled={!dirty} onClick={save}>
            Save form
          </Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[17rem_minmax(0,1fr)] lg:items-start">
        {/* The field's settings while one is picked; otherwise the fields not on the form. */}
        <Sheet className="p-4 lg:sticky lg:top-4">
          {chosen ? (
            <FieldSettings
              field={chosen}
              terms={terms}
              onChange={(patch) => change(chosen.key, patch)}
              onTakeOff={() => takeOff(chosen)}
              onClose={() => setSelected(null)}
            />
          ) : (
            <>
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-ink">Not on the form</h3>
                <span className="rounded-md bg-bench px-2 py-0.5 text-meta text-ink-2 tabular-nums">{waiting.length}</span>
              </div>
              {waiting.length > 6 && (
                <div className="mt-3">
                  <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search fields" prefix={<Search className="size-3.5 text-ink-3" />} />
                </div>
              )}
              <ul className="mt-3 max-h-[28rem] space-y-1 overflow-y-auto">
                {shown.map((f) => (
                  <li key={f.key} className="group flex items-center gap-1">
                    <button suppressHydrationWarning
                      type="button"
                      draggable
                      onDragStart={startDrag(f.key)}
                      onDragEnd={endDrag}
                      onClick={() => addToPage(f.key)}
                      title="Drag onto the page, or click to add it"
                      className="flex min-w-0 flex-1 cursor-grab items-center gap-2.5 rounded-lg border border-rule bg-sheet px-2.5 py-2 text-left text-sm hover:border-sage-deep hover:bg-mint active:cursor-grabbing"
                    >
                      <span className="grid size-6 shrink-0 place-items-center rounded-md bg-bench text-ink-3">{kindIcon(f.type)}</span>
                      <span className="min-w-0 flex-1 truncate text-ink">{f.label}</span>
                      <Plus className="size-3.5 shrink-0 text-ink-3" aria-hidden />
                    </button>
                    {!f.standard && !f.used && f.id && (
                      <IconButton label={`Delete ${f.label}`} size="sm" tone="danger" onClick={() => remove(f)}>
                        <Trash2 className="size-3.5" />
                      </IconButton>
                    )}
                  </li>
                ))}
                {waiting.length === 0 && <li className="py-4 text-center text-meta text-ink-3">Every field is on the form.</li>}
                {waiting.length > 0 && shown.length === 0 && <li className="py-4 text-center text-meta text-ink-3">No field matches.</li>}
              </ul>
              <div className="mt-4 border-t border-rule pt-4">
                <Button className="w-full" icon={<Plus className="size-4" />} onClick={() => setAdding(true)}>
                  New field
                </Button>
              </div>
            </>
          )}
        </Sheet>

        {/* The page. */}
        <Sheet className="overflow-x-auto px-5 py-8 sm:px-10">
          <div className="mx-auto max-w-4xl">
            <div className="mb-8 flex items-center gap-5">
              <span className="h-px flex-1 bg-rule" aria-hidden />
              <h3 className="text-2xl font-normal tracking-[0.12em] text-ink uppercase">{TITLES[entity] ?? entity}</h3>
              <span className="h-px flex-1 bg-rule" aria-hidden />
            </div>

            <div className="space-y-6">
              {sections.map((s, i) => {
                const visible = s.fields.filter((f) => !f.hidden);
                const hiddenHere = s.fields.length - visible.length;
                return (
                  <section key={s.ref} aria-label={s.title}>
                    <div className="group/band flex items-center gap-2 bg-sage-deep px-3 py-2 text-white">
                      <input suppressHydrationWarning
                        value={s.title}
                        onChange={(e) => changeSection(s.ref, { title: e.target.value })}
                        aria-label="Section title"
                        className="min-w-0 flex-1 rounded bg-transparent px-1 py-0.5 text-[0.9375rem] font-medium text-white placeholder:text-white/60 hover:bg-white/10 focus:bg-white/15 focus:outline-none"
                        placeholder="Section title"
                      />
                      <div className="flex items-center gap-0.5 rounded-md bg-white/10 p-0.5 text-meta" role="group" aria-label="Columns">
                        {([1, 2] as const).map((n) => (
                          <button suppressHydrationWarning
                            key={n}
                            type="button"
                            aria-pressed={s.columns === n}
                            onClick={() => changeSection(s.ref, { columns: n })}
                            className={`rounded px-2 py-0.5 ${s.columns === n ? "bg-white text-sage-deep" : "text-white/85 hover:bg-white/15"}`}
                          >
                            {n} {n === 1 ? "column" : "columns"}
                          </button>
                        ))}
                      </div>
                      <BandButton label="Move section up" disabled={i === 0} onClick={() => moveSection(s.ref, -1)}>
                        <ChevronUp className="size-4" />
                      </BandButton>
                      <BandButton label="Move section down" disabled={i === sections.length - 1} onClick={() => moveSection(s.ref, 1)}>
                        <ChevronDown className="size-4" />
                      </BandButton>
                      <BandButton
                        label={visible.length > 0 ? "Move or take off its fields first" : "Delete section"}
                        disabled={visible.length > 0 || sections.length === 1}
                        onClick={() => dropSection(s.ref)}
                      >
                        <Trash2 className="size-4" />
                      </BandButton>
                    </div>

                    <div
                      className={`grid border-l border-rule ${s.columns === 2 ? "sm:grid-cols-2" : ""}`}
                      onDragOver={over({ section: s.ref, before: null })}
                      onDrop={drop({ section: s.ref, before: null })}
                    >
                      {visible.map((f) => (
                        <Cell
                          key={f.key}
                          field={f}
                          wide={s.columns === 2 && f.type === "long_text"}
                          sample={sample}
                          terms={terms}
                          picked={selected === f.key}
                          lifted={dragging === f.key}
                          landing={spot?.section === s.ref && spot.before === f.key && dragging !== f.key}
                          onPick={() => setSelected(selected === f.key ? null : f.key)}
                          onTakeOff={() => takeOff(f)}
                          onDragStart={startDrag(f.key)}
                          onDragEnd={endDrag}
                          onDragOver={over({ section: s.ref, before: f.key })}
                          onDrop={drop({ section: s.ref, before: f.key })}
                        />
                      ))}
                      <div
                        className={`flex min-h-14 items-center justify-center border-r border-b border-dashed px-3 py-3 text-meta ${s.columns === 2 ? "sm:col-span-2" : ""} ${
                          spot?.section === s.ref && spot.before === null ? "border-sage-deep bg-mint text-sage-deep" : "border-rule text-ink-3"
                        }`}
                      >
                        {dragging
                          ? "Drop here"
                          : visible.length === 0
                            ? "Drag fields here from the list"
                            : hiddenHere > 0
                              ? `${hiddenHere} hidden ${hiddenHere === 1 ? "field" : "fields"} from this section in Not on the form`
                              : "Drag more fields here"}
                      </div>
                    </div>
                  </section>
                );
              })}
            </div>

            <button suppressHydrationWarning
              type="button"
              onClick={addSection}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-rule-strong py-3 text-sm text-ink-2 hover:border-sage-deep hover:bg-mint hover:text-ink"
            >
              <Plus className="size-4" aria-hidden />
              Add section
            </button>

            {entity === "quote" && <QuoteLines />}
          </div>
        </Sheet>
      </div>

      <NewField open={adding} onClose={() => setAdding(false)} onAdd={addField} taken={new Set(all.map((f) => f.label.trim().toLowerCase()))} terms={terms} />
    </div>
  );
}

function BandButton({ label, disabled, onClick, children }: { label: string; disabled?: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button suppressHydrationWarning
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="grid size-7 place-items-center rounded-md text-white/85 hover:bg-white/15 hover:text-white disabled:opacity-35 disabled:hover:bg-transparent"
    >
      {children}
    </button>
  );
}

/** One field on the page: its label over its value, in a bordered cell, as the document reads. */
function Cell({
  field,
  wide,
  sample,
  terms,
  picked,
  lifted,
  landing,
  onPick,
  onTakeOff,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
}: {
  field: FormFieldDef;
  wide: boolean;
  sample: boolean;
  terms: Terms | undefined;
  picked: boolean;
  lifted: boolean;
  landing: boolean;
  onPick: () => void;
  onTakeOff: () => void;
  onDragStart: (e: DragEvent) => void;
  onDragEnd: () => void;
  onDragOver: (e: DragEvent) => void;
  onDrop: (e: DragEvent) => void;
}) {
  const value = sample ? sampleOf(field) : "";
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragOver={onDragOver}
      onDrop={onDrop}
      className={`group/cell relative min-w-0 border-r border-b border-rule px-4 py-3 transition-colors ${wide ? "sm:col-span-2" : ""} ${
        picked ? "bg-mint ring-2 ring-sage-deep ring-inset" : "hover:bg-bench/60"
      } ${lifted ? "opacity-40" : ""} ${landing ? "shadow-[inset_0_3px_0_var(--color-sage-deep,#4f7f44)]" : ""}`}
    >
      <button suppressHydrationWarning type="button" onClick={onPick} className="block w-full cursor-pointer text-left" aria-label={`${field.label}: change its settings`}>
        <span className="flex items-center gap-1.5 text-meta text-ink-3">
          <GripVertical className="-ml-2.5 size-3.5 shrink-0 cursor-grab opacity-0 group-hover/cell:opacity-100" aria-hidden />
          <span className="truncate">{field.label}</span>
          {field.required && <span className="text-danger">*</span>}
          {field.locked && <Lock className="size-3 shrink-0" aria-label="Always on the form" />}
        </span>
        <span className={`mt-1 block truncate text-sm ${value ? "text-ink" : "text-ink-3"}`}>
          {value || field.placeholder || kindLabel(field.type, terms)}
        </span>
        {field.helpText && <span className="mt-0.5 block truncate text-meta text-ink-3">{field.helpText}</span>}
      </button>
      <span className="absolute top-1.5 right-1.5 flex gap-0.5 opacity-0 group-hover/cell:opacity-100 focus-within:opacity-100">
        <IconButton label={`${field.label} settings`} size="sm" onClick={onPick}>
          <Settings2 className="size-3.5" />
        </IconButton>
        {!field.locked && (
          <IconButton label={`Take ${field.label} off the form`} size="sm" onClick={onTakeOff}>
            <EyeOff className="size-3.5" />
          </IconButton>
        )}
      </span>
    </div>
  );
}

function sampleOf(field: FormFieldDef): string {
  if (SAMPLE_VALUES[field.key]) return SAMPLE_VALUES[field.key];
  if (field.type === "yes_no") return "Yes";
  if (field.type === "money") return "₱1,250,000.00";
  if (field.type === "number") return "12";
  if (field.type === "date") return "15 Oct 2026";
  if (field.type === "email") return "name@example.com";
  if (field.type === "url") return "https://example.com";
  if (field.options.length) {
    const first = field.options.slice(0, field.type === "multi_choice" ? 2 : 1);
    return first.map((o) => field.optionNames?.[o] || o).join(", ");
  }
  return "";
}

/** The picked field's settings, in the list's place, with the way back above them. */
function FieldSettings({
  field,
  terms,
  onChange,
  onTakeOff,
  onClose,
}: {
  field: FormFieldDef;
  terms: Terms | undefined;
  onChange: (patch: Partial<FormFieldDef>) => void;
  onTakeOff: () => void;
  onClose: () => void;
}) {
  const options = WITH_OPTIONS.has(field.type) && !field.sharedList;
  return (
    <div>
      <button suppressHydrationWarning type="button" onClick={onClose} className="mb-3 inline-flex items-center gap-1.5 text-meta text-ink-2 hover:text-ink">
        <ArrowLeft className="size-3.5" aria-hidden />
        Fields not on the form
      </button>
      <div className="flex items-center gap-2.5">
        <span className="grid size-8 place-items-center rounded-lg bg-bench text-ink-2">{kindIcon(field.type)}</span>
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-ink">{field.label || "Untitled field"}</h3>
          <p className="text-meta text-ink-3">
            {kindLabel(field.type, terms)}
            {field.standard ? " · Built in" : ""}
          </p>
        </div>
      </div>
      <div className="mt-4 space-y-3.5">
        <Field label="Label">{(p) => <Input {...p} value={field.label} onChange={(e) => onChange({ label: e.target.value })} />}</Field>
        <Field label="Help text" optional>
          {(p) => <Input {...p} value={field.helpText ?? ""} onChange={(e) => onChange({ helpText: e.target.value })} placeholder="Shown under the field" />}
        </Field>
        <Field label="Placeholder" optional>
          {(p) => <Input {...p} value={field.placeholder ?? ""} onChange={(e) => onChange({ placeholder: e.target.value })} placeholder="Shown inside the empty field" />}
        </Field>
        {options && (
          <Field label="Options" hint="One per line.">
            {(p) => (
              <Textarea
                {...p}
                rows={4}
                value={field.options.join("\n")}
                onChange={(e) => onChange({ options: e.target.value.split("\n").map((o) => o.trimStart()) })}
              />
            )}
          </Field>
        )}
        {field.sharedList && <p className="text-meta text-ink-3">Its options are kept in Settings → Deal stages.</p>}
        <Toggle label="Required" hint={field.locked ? "Always required." : undefined} checked={field.locked || field.required} disabled={field.locked} onChange={(v) => onChange({ required: v })} />
        <Toggle label="Show in lists" checked={field.inList} onChange={(v) => onChange({ inList: v })} />
        {MAY_BE_UNIQUE.has(field.type) && !field.standard && (
          <Toggle label="No two records the same" checked={field.unique ?? false} onChange={(v) => onChange({ unique: v })} />
        )}
      </div>
      {!field.locked && (
        <div className="mt-5 border-t border-rule pt-4">
          <Button className="w-full" icon={<EyeOff className="size-4" />} onClick={onTakeOff}>
            Take off the form
          </Button>
          <p className="mt-2 text-meta text-ink-3">{field.id ? "Kept in Not on the form, with its values, until you put it back." : "Not saved yet, so it goes."}</p>
        </div>
      )}
    </div>
  );
}

function Toggle({ label, hint, checked, disabled, onChange }: { label: string; hint?: string; checked: boolean; disabled?: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center justify-between gap-3 text-sm text-ink">
      <span>
        {label}
        {hint && <span className="block text-meta text-ink-3">{hint}</span>}
      </span>
      <Switch size="small" checked={checked} disabled={disabled} onChange={onChange} />
    </label>
  );
}

/** A new field: its name and kind, then it's on the page to place and set up. */
function NewField({
  open,
  onClose,
  onAdd,
  taken,
  terms,
}: {
  open: boolean;
  onClose: () => void;
  onAdd: (field: FormFieldDef) => void;
  taken: Set<string>;
  terms: Terms | undefined;
}) {
  const [label, setLabel] = useState("");
  const [type, setType] = useState("text");
  const [options, setOptions] = useState("");
  const clean = label.trim();
  const list = options.split("\n").map((o) => o.trim()).filter(Boolean);
  const problem = !clean
    ? null
    : taken.has(clean.toLowerCase())
      ? "A field already has that name."
      : WITH_OPTIONS.has(type) && list.length < 2
        ? "Give it at least two options."
        : null;

  function add() {
    if (!clean || problem) return;
    const key = `x_new_${clean.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "")}_${Date.now().toString(36)}`;
    onAdd({
      id: "",
      key,
      label: clean,
      type: type as FormFieldDef["type"],
      standard: false,
      locked: false,
      required: false,
      hidden: false,
      inList: false,
      options: WITH_OPTIONS.has(type) ? list : [],
      helpText: null,
      placeholder: null,
      used: 0,
    });
    setLabel("");
    setOptions("");
    setType("text");
    onClose();
  }

  const kinds = useMemo(() => KINDS.map((k) => ({ value: k.type, label: kindLabel(k.type, terms) })), [terms]);
  return (
    <Modal open={open} title="New field" onCancel={onClose} footer={null} width={440} destroyOnHidden>
      <div className="space-y-3.5 pt-2">
        <Field label="Name" error={problem ?? undefined}>
          {(p) => <Input {...p} value={label} onChange={(e) => setLabel(e.target.value)} placeholder="For example, Hospital accreditation" autoFocus onPressEnter={add} />}
        </Field>
        <Field label="Kind">
          {(p) => (
            <Select {...p} value={type} onChange={(e) => setType(e.target.value)}>
              {kinds.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        {WITH_OPTIONS.has(type) && (
          <Field label="Options" hint="One per line.">
            {(p) => <Textarea {...p} rows={4} value={options} onChange={(e) => setOptions(e.target.value)} />}
          </Field>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="quiet" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={!clean || Boolean(problem)} onClick={add}>
            Add to the form
          </Button>
        </div>
      </div>
    </Modal>
  );
}

/** A quotation's lines and totals: always on it, so shown on the page but not changed here. */
function QuoteLines() {
  return (
    <div className="mt-8" aria-label="Always on the quotation">
      <p className="mb-2 text-meta text-ink-3">Always on the quotation: the products and the totals.</p>
      <div className="grid grid-cols-[2.5rem_minmax(0,1fr)_5rem_6rem_6.5rem] bg-sage-deep px-1 py-2 text-sm text-white">
        <span className="px-2">#</span>
        <span className="px-2">Item and description</span>
        <span className="px-2 text-right">Qty</span>
        <span className="px-2 text-right">Rate</span>
        <span className="px-2 text-right">Amount</span>
      </div>
      {[
        ["1", "Amoxicillin 500 mg capsule", "Box of 100", "10", "450.00", "4,500.00"],
        ["2", "Paracetamol 500 mg tablet", "Box of 100", "5", "180.00", "900.00"],
      ].map(([n, name, unit, qty, rate, amount]) => (
        <div key={n} className="grid grid-cols-[2.5rem_minmax(0,1fr)_5rem_6rem_6.5rem] border-x border-b border-rule px-1 py-3 text-sm text-ink-2">
          <span className="px-2">{n}</span>
          <span className="px-2">
            <span className="block text-ink">{name}</span>
            <span className="block text-meta text-ink-3">{unit}</span>
          </span>
          <span className="px-2 text-right tabular-nums">{qty}</span>
          <span className="px-2 text-right tabular-nums">{rate}</span>
          <span className="px-2 text-right tabular-nums">{amount}</span>
        </div>
      ))}
      <div className="ml-auto w-full max-w-xs bg-bench text-sm">
        <div className="flex justify-between px-4 py-2 text-ink-2">
          <span>Sub total</span>
          <span className="tabular-nums">5,400.00</span>
        </div>
        <div className="flex justify-between px-4 py-2 font-semibold text-ink">
          <span>Total</span>
          <span className="tabular-nums">₱5,400.00</span>
        </div>
        <div className="flex justify-between bg-mint-2 px-4 py-2.5 font-semibold text-ink">
          <span>Balance due</span>
          <span className="tabular-nums">₱5,400.00</span>
        </div>
      </div>
    </div>
  );
}
