"use client";

import {
  AlignLeft,
  ArrowLeft,
  AtSign,
  Building2,
  Calendar,
  Check,
  CheckSquare,
  Code2,
  Coins,
  Copy,
  Eye,
  EyeOff,
  FlaskConical,
  Hash,
  Info,
  Link2,
  List,
  ListChecks,
  Lock,
  Maximize2,
  Package,
  Phone,
  Plus,
  RotateCcw,
  Search,
  Sparkles,
  Type,
  Wand2,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, useTransition, type ReactNode } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, Input, Select, Textarea } from "@/src/platform/ui/field";
import { Sheet } from "@/src/platform/ui/sheet";
import type { CustomEntity, FormFieldDef, FormLayout, FormSectionDef } from "@/src/platform/lib/types";
import { saveForm, type SectionDraft } from "../../actions/settings";
import { useTerms } from "@/src/components/terms/provider";
import type { Terms } from "@/src/components/terms/terms";
import type { TeamName } from "../admin/teams-for";

// XML Form Editor (Settings → Forms)
// Focused XML-based builder with on-demand interactive preview.

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

function escapeXml(unsafe: string): string {
  return (unsafe || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/** Generates canonical XML field name tag based on entity and key */
function defaultTagForField(f: FormFieldDef, entity: CustomEntity): string {
  if (entity === "company" && f.key === "name") return "customer_name";
  if (entity === "company" && f.key === "status") return "customer_type";
  if (entity === "contact" && f.key === "firstName") return "first_name";
  if (entity === "contact" && f.key === "lastName") return "last_name";
  if (entity === "contact" && f.key === "companyId") return "customer";
  if (entity === "product" && f.key === "name") return "product_name";
  if (entity === "product" && f.key === "code") return "product_code";
  if (f.key.startsWith("x_")) return f.key;
  return f.key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
}

/** Resolves an XML attribute/tag back to an existing FormFieldDef key */
function resolveFieldKey(rawTag: string, entity: CustomEntity, fieldMap: Map<string, FormFieldDef>): string | null {
  const clean = rawTag.trim().toLowerCase().replace(/^%+|%+$/g, "");
  if (fieldMap.has(clean)) return clean;

  const camel = clean.replace(/_([a-z0-9])/g, (_, ch) => ch.toUpperCase());
  if (fieldMap.has(camel)) return camel;

  if (entity === "company") {
    if (clean === "customer_name" || clean === "customername" || clean === "customer" || clean === "name") return "name";
    if (clean === "customer_type" || clean === "customertype" || clean === "type" || clean === "status") return "status";
    if (clean === "tier") return "x_tier";
    if (clean === "pvi" || clean === "pvi_zone") return "x_pvi_zone";
    if (clean === "s2" || clean === "pdea_s2" || clean === "s2_license") return "x_pdea_s2";
    if (clean === "s2_expiry" || clean === "s2_expiration") return "x_s2_expiry";
    if (clean === "credit_status") return "x_credit_status";
    if (clean === "lifecycle" || clean === "account_lifecycle") return "x_account_lifecycle";
  }
  if (entity === "contact") {
    if (clean === "first_name" || clean === "firstname") return "firstName";
    if (clean === "last_name" || clean === "lastname") return "lastName";
    if (clean === "customer" || clean === "company" || clean === "hospital") return "companyId";
    if (clean === "stakeholder") return "x_stakeholder";
    if (clean === "care_team") return "x_care_team_status";
  }
  if (entity === "product") {
    if (clean === "product_name" || clean === "productname") return "name";
    if (clean === "product_code" || clean === "productcode") return "code";
    if (clean === "generic_name" || clean === "genericname") return "genericName";
  }
  if (entity === "quote") {
    if (clean === "quote_notes") return "notes";
    if (clean === "payer" || clean === "payer_program") return "x_payer_program";
    if (clean === "procurement" || clean === "procurement_mode") return "x_procurement_mode";
  }

  if (!clean.startsWith("x_") && fieldMap.has(`x_${clean}`)) return `x_${clean}`;

  for (const k of fieldMap.keys()) {
    if (k.toLowerCase() === clean || k.toLowerCase().replace(/_/g, "") === clean.replace(/_/g, "")) {
      return k;
    }
  }
  return null;
}

/** Generates clean, beautiful XML markup from a layout */
export function layoutToXml(layout: FormLayout, entity: CustomEntity): string {
  const lines: string[] = [];
  lines.push(`<form entity="${entity}">`);
  for (const s of layout.sections) {
    lines.push(`  <section title="${escapeXml(s.title)}" columns="${s.columns}">`);
    for (const f of s.fields) {
      const tag = defaultTagForField(f, entity);
      const attrs: string[] = [`name="${tag}"`];
      if (f.label && f.label.toLowerCase() !== tag.replace(/_/g, " ").toLowerCase()) {
        attrs.push(`label="${escapeXml(f.label)}"`);
      }
      if (f.required && !f.standard) {
        attrs.push(`required="true"`);
      }
      if (f.hidden) {
        attrs.push(`hidden="true"`);
      }
      lines.push(`    <field ${attrs.join(" ")} />`);
    }
    lines.push(`  </section>`);
    lines.push("");
  }
  lines.push(`</form>`);
  return lines.join("\n").trim();
}

type ParsedSection = {
  id: string | null;
  title: string;
  columns: 1 | 2;
  fields: FormFieldDef[];
};

/** Parses XML format into sections and field definitions */
export function parseXmlToSections(
  xmlCode: string,
  entity: CustomEntity,
  knownFields: Map<string, FormFieldDef>,
  originalSections: FormSectionDef[]
): { sections: ParsedSection[]; warnings: string[]; totalFields: number } {
  const warnings: string[] = [];
  const sections: ParsedSection[] = [];
  const seenFieldKeys = new Set<string>();

  // Remove XML comments
  const cleanCode = xmlCode.replace(/<!--[\s\S]*?-->/g, "");

  const sectionRegex = /<section\s+([^>]*?)>([\s\S]*?)<\/section>/gi;
  const attrRegex = /([a-zA-Z0-9_-]+)=["']([^"']*)["']/g;
  const fieldTagRegex = /<field\s+([^>]*?)(?:\/>|>([\s\S]*?)<\/field>)/gi;
  const percentTagRegex = /%([a-zA-Z0-9_]+)(?::\s*([a-zA-Z0-9_]+))?%/g;

  let sm: RegExpExecArray | null;
  while ((sm = sectionRegex.exec(cleanCode)) !== null) {
    const attrStr = sm[1];
    const body = sm[2];

    const attrs: Record<string, string> = {};
    let am: RegExpExecArray | null;
    while ((am = attrRegex.exec(attrStr)) !== null) {
      attrs[am[1].toLowerCase()] = am[2];
    }

    const title = attrs.title || attrs.name || "Untitled section";
    const columns = (attrs.columns === "1" ? 1 : 2) as 1 | 2;

    const orig = originalSections.find((os) => os.title.toLowerCase() === title.toLowerCase());
    const id = orig ? orig.id : null;

    const sectionFields: FormFieldDef[] = [];

    // Parse <field ... /> tags
    let fm: RegExpExecArray | null;
    while ((fm = fieldTagRegex.exec(body)) !== null) {
      const fAttrStr = fm[1];
      const inner = (fm[2] || "").trim();

      const fAttrs: Record<string, string> = {};
      let fam: RegExpExecArray | null;
      while ((fam = attrRegex.exec(fAttrStr)) !== null) {
        fAttrs[fam[1].toLowerCase()] = fam[2];
      }

      const rawTag = fAttrs.name || fAttrs.key || fAttrs.tag || inner.replace(/%/g, "").trim();
      if (!rawTag) continue;

      const isRequired = fAttrs.required === "true" || fAttrs.required === "1";
      const isHidden = fAttrs.hidden === "true" || fAttrs.hidden === "1";
      const customLabel = fAttrs.label?.trim();

      const resolvedKey = resolveFieldKey(rawTag, entity, knownFields);
      if (resolvedKey && knownFields.has(resolvedKey)) {
        const base = knownFields.get(resolvedKey)!;
        if (seenFieldKeys.has(base.key)) {
          warnings.push(`Field "${rawTag}" appears more than once on the form.`);
        }
        seenFieldKeys.add(base.key);

        sectionFields.push({
          ...base,
          label: customLabel || base.label,
          required: isRequired || (base.standard ? base.required : false),
          hidden: isHidden,
        });
      } else {
        // Custom field defined in XML
        const customKey = rawTag.startsWith("x_") ? rawTag : `x_${rawTag.toLowerCase()}`;
        if (seenFieldKeys.has(customKey)) {
          warnings.push(`Field "${rawTag}" appears more than once.`);
        }
        seenFieldKeys.add(customKey);

        sectionFields.push({
          id: "",
          key: customKey,
          label: customLabel || rawTag.replace(/^x_/, "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
          type: "text",
          standard: false,
          locked: false,
          required: isRequired,
          hidden: isHidden,
          inList: false,
          options: [],
          helpText: null,
          placeholder: null,
          used: 0,
        });
      }
    }

    // Also support any loose %tag% in body not wrapped in <field>
    const bodyWithoutFields = body.replace(fieldTagRegex, "");
    let pm: RegExpExecArray | null;
    while ((pm = percentTagRegex.exec(bodyWithoutFields)) !== null) {
      const rawTag = pm[1];
      const modifier = pm[2]?.toLowerCase();
      const resolvedKey = resolveFieldKey(rawTag, entity, knownFields);

      if (resolvedKey && knownFields.has(resolvedKey)) {
        const base = knownFields.get(resolvedKey)!;
        if (seenFieldKeys.has(base.key)) {
          warnings.push(`Field "%${rawTag}%" appears more than once.`);
        }
        seenFieldKeys.add(base.key);
        sectionFields.push({
          ...base,
          required: modifier === "required" ? true : modifier === "optional" ? false : base.required,
          hidden: modifier === "hidden",
        });
      }
    }

    sections.push({ id, title, columns, fields: sectionFields });
  }

  // Fallback: If no <section> tags found, wrap whole code in default section
  if (sections.length === 0 && cleanCode.trim().length > 0) {
    const sectionFields: FormFieldDef[] = [];
    let fm: RegExpExecArray | null;
    while ((fm = fieldTagRegex.exec(cleanCode)) !== null) {
      const fAttrs: Record<string, string> = {};
      let fam: RegExpExecArray | null;
      while ((fam = attrRegex.exec(fm[1])) !== null) {
        fAttrs[fam[1].toLowerCase()] = fam[2];
      }
      const rawTag = fAttrs.name || fAttrs.key || "";
      const resolvedKey = resolveFieldKey(rawTag, entity, knownFields);
      if (resolvedKey && knownFields.has(resolvedKey)) {
        const base = knownFields.get(resolvedKey)!;
        seenFieldKeys.add(base.key);
        sectionFields.push({
          ...base,
          required: fAttrs.required === "true" || base.required,
          hidden: fAttrs.hidden === "true",
        });
      }
    }
    sections.push({ id: null, title: "General", columns: 2, fields: sectionFields });
  }

  // Ensure standard built-in fields are not dropped from backend validation
  for (const f of knownFields.values()) {
    if (f.standard && !seenFieldKeys.has(f.key)) {
      warnings.push(`Built-in field "${f.label}" was omitted from XML; keeping it hidden.`);
      if (sections.length > 0) {
        sections[sections.length - 1].fields.push({ ...f, hidden: true });
      }
    }
  }

  const totalFields = sections.reduce((sum, s) => sum + s.fields.length, 0);
  return { sections, warnings, totalFields };
}

/** Formats XML code with clean 2-space indentation */
function formatXml(xml: string): string {
  let formatted = "";
  let pad = 0;
  // Normalize self-closing and separate tags
  const tokens = xml
    .replace(/>\s*</g, "><")
    .replace(/></g, ">\n<")
    .split("\n");

  for (const rawToken of tokens) {
    const token = rawToken.trim();
    if (!token) continue;

    if (token.startsWith("</")) {
      pad = Math.max(0, pad - 1);
    }

    formatted += "  ".repeat(pad) + token + "\n";

    if (token.startsWith("<") && !token.startsWith("</") && !token.endsWith("/>") && !token.startsWith("<?") && !token.startsWith("<!--")) {
      // Check if it's not a single-line tag like <tag>content</tag>
      if (!/<\w+[^>]*>.*?<\/\w+>/.test(token)) {
        pad += 1;
      }
    }
  }
  return formatted.trim();
}

/** Realistic sample values for previewing */
const SAMPLE_VALUES: Record<string, string> = {
  name: "St. Luke's Medical Center - BGC",
  customer_name: "St. Luke's Medical Center - BGC",
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
  x_pvi_zone: "Red (Peak / Tender <72h)",
  x_pdea_s2: "PDEA-S2-2026-08841",
  x_s2_expiry: "2027-12-31",
  x_credit_status: "Good Standing",
  x_account_lifecycle: "Active",
  x_stakeholder: "Pharmacy Director",
  x_care_team_status: "Active Prescriber",
  code: "MED-500",
  genericName: "Amoxicillin Trihydrate",
  strength: "500 mg",
  notes: "Hospital tender pricing with 30-day term delivery.",
  x_payer_program: "PCSO / DOH MAIP",
  x_procurement_mode: "Small Value Procurement (RA 9184)",
  x_gl_number: "GL-2026-90412",
  x_gl_expiry: "2026-11-30",
  x_csp_number: "CSP-2026-5510",
};

export function FormEditor({
  entity,
  layout,
  teams = [],
  kinds = [],
}: {
  entity: CustomEntity;
  layout: FormLayout;
  teams?: TeamName[];
  kinds?: TeamName[];
}) {
  const terms = useTerms();
  const router = useRouter();

  // Map of all known fields in this layout
  const fieldMap = useMemo(() => {
    const map = new Map<string, FormFieldDef>();
    for (const s of layout.sections) {
      for (const f of s.fields) {
        map.set(f.key, f);
      }
    }
    return map;
  }, [layout]);

  // Initial XML generated from current layout
  const initialXml = useMemo(() => layoutToXml(layout, entity), [layout, entity]);
  const [code, setCode] = useState(initialXml);
  const [savedCode, setSavedCode] = useState(initialXml);

  // Active View Mode: "editor" (Focus on forming the XML) or "preview" (Full interactive preview)
  const [activeView, setActiveView] = useState<"editor" | "preview">("editor");

  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState<"all" | "standard" | "custom">("all");
  const [previewSample, setPreviewSample] = useState(true);
  const [copied, setCopied] = useState(false);
  const [pending, startTransition] = useTransition();

  // Add custom field modal state
  const [newFieldOpen, setNewFieldOpen] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [newType, setNewType] = useState("text");
  const [newRequired, setNewRequired] = useState(false);
  const [newOptions, setNewOptions] = useState("Option 1\nOption 2");

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Parse XML in real time
  const parsed = useMemo(
    () => parseXmlToSections(code, entity, fieldMap, layout.sections),
    [code, entity, fieldMap, layout.sections]
  );

  const isDirty = code.trim() !== savedCode.trim();

  /** Inserts text at current cursor position */
  const insertText = useCallback((text: string) => {
    const textarea = textareaRef.current;
    if (!textarea) {
      setCode((c) => `${c}\n${text}`);
      return;
    }
    const start = textarea.selectionStart ?? textarea.value.length;
    const end = textarea.selectionEnd ?? start;
    const nextCode = textarea.value.slice(0, start) + text + textarea.value.slice(end);
    setCode(nextCode);
    setTimeout(() => {
      textarea.focus();
      const pos = start + text.length;
      textarea.setSelectionRange(pos, pos);
    }, 10);
  }, []);

  /** Inserts a field XML element */
  const insertFieldXml = (tag: string, label?: string) => {
    const snippet = label
      ? `  <field name="${tag}" label="${escapeXml(label)}" />\n`
      : `  <field name="${tag}" />\n`;
    insertText(snippet);
    toast.success(`Inserted <field name="${tag}" />`);
  };

  /** Formats the XML in the editor */
  const handleFormat = () => {
    try {
      const formatted = formatXml(code);
      setCode(formatted);
      toast.success("XML formatted");
    } catch {
      toast.error("Could not format XML");
    }
  };

  /** Handles Tab key in editor */
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Tab") {
      e.preventDefault();
      insertText("  ");
    }
  };

  /** Copies code */
  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    toast.success("XML code copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

  /** Inserts a new section snippet */
  const handleInsertSection = () => {
    const snippet = `\n  <section title="New Section" columns="2">\n    \n  </section>\n`;
    insertText(snippet);
  };

  /** Saves the coded form layout */
  const handleSave = () => {
    const body: SectionDraft[] = parsed.sections.map((s) => ({
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
            .map(([o, n]) => [o, String(n).trim()])
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
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      setSavedCode(code);
      toast.success("Form saved successfully", {
        description: "Your XML layout is now active for all users.",
      });
      router.refresh();
    });
  };

  /** Adds custom field */
  const handleCreateCustomField = () => {
    const cleanLabel = newLabel.trim();
    if (!cleanLabel) {
      toast.error("Please enter a field label");
      return;
    }
    const cleanKey = `x_${cleanLabel.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "")}`;
    const opts =
      newType === "choice" || newType === "multi_choice"
        ? newOptions
            .split("\n")
            .map((o) => o.trim())
            .filter(Boolean)
        : [];

    const newFieldDef: FormFieldDef = {
      id: "",
      key: cleanKey,
      label: cleanLabel,
      type: newType as FormFieldDef["type"],
      standard: false,
      locked: false,
      required: newRequired,
      hidden: false,
      inList: false,
      options: opts,
      helpText: null,
      placeholder: null,
      used: 0,
    };

    fieldMap.set(cleanKey, newFieldDef);
    insertText(`  <field name="${cleanKey}" label="${escapeXml(cleanLabel)}"${newRequired ? ' required="true"' : ""} />\n`);
    setNewFieldOpen(false);
    setNewLabel("");
    toast.success(`Created field <field name="${cleanKey}" />`);
  };

  // Filtered field list for the palette
  const allFieldList = useMemo(() => Array.from(fieldMap.values()), [fieldMap]);
  const filteredFields = useMemo(() => {
    const q = search.trim().toLowerCase();
    return allFieldList.filter((f) => {
      if (activeTab === "standard" && !f.standard) return false;
      if (activeTab === "custom" && f.standard) return false;
      if (!q) return true;
      const tag = defaultTagForField(f, entity).toLowerCase();
      return f.label.toLowerCase().includes(q) || f.key.toLowerCase().includes(q) || tag.includes(q);
    });
  }, [allFieldList, search, activeTab, entity]);

  return (
    <div className="space-y-4">
      {/* Top Header & View Switcher */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rule pb-3.5">
        <div className="flex items-center gap-3">
          <span className="flex size-8 items-center justify-center rounded-xl bg-hema-tint text-hema shadow-xs">
            <Code2 className="size-4.5" />
          </span>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-ink">XML Form Studio</h2>
              <span className="rounded-md bg-bench px-2 py-0.5 text-[11px] font-medium text-ink-2 capitalize">
                {entity}
              </span>
            </div>
            <p className="text-meta text-ink-3">
              Define form layout with clean XML tags. Focus on building your structure, then click preview.
            </p>
          </div>
        </div>

        {/* View Mode Switcher and Actions */}
        <div className="flex items-center gap-2">
          {/* Segmented Mode Control */}
          <div className="flex rounded-xl bg-bench p-1 text-xs">
            <button
              type="button"
              onClick={() => setActiveView("editor")}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-medium transition-all ${
                activeView === "editor"
                  ? "bg-sheet text-ink shadow-sm"
                  : "text-ink-3 hover:text-ink"
              }`}
            >
              <Code2 className="size-3.5" />
              <span>XML Editor</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveView("preview")}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-medium transition-all ${
                activeView === "preview"
                  ? "bg-hema-tint text-hema font-semibold shadow-sm"
                  : "text-ink-3 hover:text-ink"
              }`}
            >
              <Eye className="size-3.5" />
              <span>Preview Form</span>
              <span className="ml-1 rounded-md bg-emerald-500/10 px-1.5 py-0.2 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                {parsed.totalFields}
              </span>
            </button>
          </div>

          {isDirty && (
            <Button variant="quiet" onClick={() => setCode(savedCode)}>
              Discard
            </Button>
          )}

          <Button variant="primary" loading={pending} disabled={!isDirty} onClick={handleSave}>
            Save form
          </Button>
        </div>
      </div>

      {/* VIEW 1: FOCUSED XML FORM BUILDER */}
      {activeView === "editor" && (
        <div className="grid gap-4 lg:grid-cols-[19rem_minmax(0,1fr)]">
          {/* Left Column: Available Fields Palette */}
          <Sheet className="flex flex-col p-3.5 self-start">
            <div className="flex items-center justify-between pb-2 border-b border-rule">
              <span className="text-xs font-semibold uppercase tracking-wider text-ink-3">Available Fields</span>
              <span className="rounded-md bg-bench px-2 py-0.5 text-[11px] font-medium text-ink-2">
                {allFieldList.length}
              </span>
            </div>

            <div className="mt-2.5">
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search fields or tags..."
                prefix={<Search className="size-3.5 text-ink-3" />}
              />
            </div>

            {/* Filter Pills */}
            <div className="mt-2 flex gap-1 rounded-lg bg-bench p-1 text-[11px]">
              {(["all", "standard", "custom"] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setActiveTab(tab)}
                  className={`flex-1 rounded-md py-1 font-medium capitalize transition-colors ${
                    activeTab === tab ? "bg-sheet text-ink shadow-sm" : "text-ink-3 hover:text-ink"
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Field Cards Palette */}
            <div className="mt-2.5 max-h-[38rem] flex-1 space-y-1 overflow-y-auto pr-1">
              {filteredFields.map((f) => {
                const tag = defaultTagForField(f, entity);
                return (
                  <button
                    key={f.key}
                    type="button"
                    onClick={() => insertFieldXml(tag, f.label)}
                    title={`Click to insert <field name="${tag}" /> at cursor`}
                    className="group flex w-full items-center justify-between gap-2 rounded-xl border border-transparent bg-sheet px-2.5 py-2 text-left text-xs transition-all hover:border-hema/40 hover:bg-bench hover:shadow-xs"
                  >
                    <div className="flex min-w-0 items-center gap-2.5">
                      <span className="flex size-6 shrink-0 items-center justify-center rounded-lg bg-bench text-ink-3 transition-colors group-hover:bg-hema-tint group-hover:text-hema">
                        {kindIcon(f.type)}
                      </span>
                      <span className="truncate font-medium text-ink transition-colors group-hover:text-hema">
                        {f.label}
                      </span>
                    </div>
                    <span className="shrink-0 rounded-md bg-bench px-1.5 py-0.5 font-mono text-[10px] text-ink-3 transition-colors group-hover:bg-hema-tint group-hover:text-hema">
                      +{tag}
                    </span>
                  </button>
                );
              })}
              {filteredFields.length === 0 && (
                <p className="py-6 text-center text-meta text-ink-3">No matching field found.</p>
              )}
            </div>

            {/* Add Custom Field Button */}
            <div className="mt-3 pt-3 border-t border-rule">
              <Button
                variant="quiet"
                size="sm"
                className="w-full justify-center !text-hema hover:!bg-hema-tint"
                icon={<Plus className="size-3.5" />}
                onClick={() => setNewFieldOpen(true)}
              >
                Add custom field
              </Button>
            </div>
          </Sheet>

          {/* Right Column: Full-Width XML Code Editor */}
          <Sheet className="flex flex-col p-4">
            {/* Editor Toolbar */}
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-rule pb-2.5">
              <div className="flex items-center gap-2">
                <span className="size-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="font-mono text-xs font-semibold text-hema">&lt;form entity=&quot;{entity}&quot;&gt;</span>
                <span className="text-meta text-ink-3">
                  · {parsed.sections.length} sections, {parsed.totalFields} fields defined
                </span>
              </div>

              <div className="flex items-center gap-1.5">
                <Button size="sm" variant="quiet" icon={<Plus className="size-3.5" />} onClick={handleInsertSection}>
                  Section
                </Button>
                <Button size="sm" variant="quiet" icon={<Wand2 className="size-3.5" />} onClick={handleFormat}>
                  Format
                </Button>
                <Button
                  size="sm"
                  variant="quiet"
                  icon={copied ? <Check className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
                  onClick={handleCopy}
                >
                  {copied ? "Copied" : "Copy"}
                </Button>
                <Button size="sm" variant="quiet" icon={<RotateCcw className="size-3.5" />} onClick={() => setCode(savedCode)}>
                  Reset
                </Button>
                <Button
                  size="sm"
                  variant="primary"
                  className="!bg-hema !text-white"
                  icon={<Eye className="size-3.5" />}
                  onClick={() => setActiveView("preview")}
                >
                  Preview Form
                </Button>
              </div>
            </div>

            {/* Editor Input Area */}
            <div className="mt-3 flex-1 flex flex-col">
              <textarea
                ref={textareaRef}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                onKeyDown={handleKeyDown}
                spellCheck={false}
                aria-label="XML Form Structure Editor"
                className="min-h-[40rem] flex-1 resize-y rounded-xl border border-slate-700 bg-[#0b1329] p-4 font-mono text-[13px] leading-relaxed text-[#e2e8f0] shadow-inner focus:border-hema focus:outline-none focus:ring-1 focus:ring-hema"
              />
            </div>

            {/* Calm, Stress-Free Editor Footer */}
            <div className="mt-2.5 flex items-center justify-between text-xs text-ink-3 px-1">
              <div className="flex items-center gap-2">
                <span className={`size-2 rounded-full ${parsed.sections.length > 0 ? "bg-emerald-500" : "bg-amber-500"}`} />
                <span className="font-mono text-[11px] text-ink-2">
                  {parsed.sections.length} sections · {parsed.totalFields} fields
                </span>
              </div>
              <span className="text-meta text-ink-3">
                Click any field on the left to insert into your form structure.
              </span>
            </div>
          </Sheet>
        </div>
      )}

      {/* VIEW 2: ON-DEMAND FULL INTERACTIVE PREVIEW */}
      {activeView === "preview" && (
        <Sheet className="flex flex-col p-5">
          {/* Preview Navigation Header */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rule pb-3.5">
            <div className="flex items-center gap-3">
              <Button
                variant="quiet"
                size="sm"
                icon={<ArrowLeft className="size-4" />}
                onClick={() => setActiveView("editor")}
              >
                Back to XML Editor
              </Button>
              <div className="h-4 w-px bg-rule" />
              <div className="flex items-center gap-2">
                <span className="flex size-6 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600">
                  <Eye className="size-3.5" />
                </span>
                <span className="text-xs font-semibold uppercase tracking-wider text-ink-3">Interactive Form Preview</span>
                <span className="rounded-md bg-emerald-500/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-600">
                  {parsed.sections.length} sections · {parsed.totalFields} fields
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPreviewSample((s) => !s)}
                className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                  previewSample ? "bg-hema-tint text-hema font-semibold" : "bg-bench text-ink-3 hover:text-ink"
                }`}
              >
                {previewSample ? "Sample Data: ON" : "Blank Form Mode"}
              </button>

              <Button variant="primary" loading={pending} disabled={!isDirty} onClick={handleSave}>
                Save form
              </Button>
            </div>
          </div>

          {/* Form Preview Canvas */}
          <div className="mt-5 max-w-4xl mx-auto w-full space-y-6 pb-8">
            {parsed.sections.map((section, sIdx) => (
              <div key={sIdx} className="rounded-xl border border-rule bg-sheet p-5 shadow-sm">
                <div className="mb-4 flex items-center justify-between border-b border-rule pb-2.5">
                  <h3 className="text-sm font-semibold text-ink">{section.title}</h3>
                  <span className="rounded-md bg-bench px-2 py-0.5 text-[11px] font-medium text-ink-3">
                    {section.columns} column{section.columns === 2 ? "s" : ""}
                  </span>
                </div>

                <div className={`grid gap-4 ${section.columns === 2 ? "sm:grid-cols-2" : "grid-cols-1"}`}>
                  {section.fields.map((f, fIdx) => (
                    <PreviewField key={`${f.key}-${fIdx}`} field={f} sample={previewSample} terms={terms} />
                  ))}
                  {section.fields.length === 0 && (
                    <p className="col-span-full py-6 text-center text-meta text-ink-3 italic">
                      No fields placed in this section. Add &lt;field name=&quot;...&quot; /&gt; tags in XML.
                    </p>
                  )}
                </div>
              </div>
            ))}

            {parsed.sections.length === 0 && (
              <div className="py-16 text-center text-meta text-ink-3 space-y-3">
                <p>No valid sections parsed from XML.</p>
                <Button variant="quiet" size="sm" onClick={() => setActiveView("editor")}>
                  Return to XML Editor
                </Button>
              </div>
            )}
          </div>
        </Sheet>
      )}

      {/* Modal: Add Custom Field */}
      {newFieldOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-xs">
          <Sheet className="w-full max-w-md p-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-rule pb-3">
              <h3 className="text-base font-semibold text-ink">Add Custom Field</h3>
              <button
                type="button"
                onClick={() => setNewFieldOpen(false)}
                className="rounded-md p-1 text-ink-3 hover:bg-bench hover:text-ink"
              >
                <X className="size-4" />
              </button>
            </div>

            <div className="mt-4 space-y-3.5 text-sm">
              <Field label="Field label">
                {(p) => (
                  <Input
                    {...p}
                    value={newLabel}
                    onChange={(e) => setNewLabel(e.target.value)}
                    placeholder="e.g. Hospital Accreditation"
                    autoFocus
                  />
                )}
              </Field>

              <Field label="Field type">
                {(p) => (
                  <Select
                    {...p}
                    value={newType}
                    onChange={(e) => setNewType(e.target.value)}
                  >
                    {KINDS.map((k) => (
                      <option key={k.type} value={k.type}>
                        {kindLabel(k.type, terms)}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>

              {(newType === "choice" || newType === "multi_choice") && (
                <Field label="Options (one per line)">
                  {(p) => (
                    <Textarea
                      {...p}
                      rows={3}
                      value={newOptions}
                      onChange={(e) => setNewOptions(e.target.value)}
                      placeholder="Option 1&#10;Option 2"
                    />
                  )}
                </Field>
              )}

              <label className="flex items-center gap-2 cursor-pointer pt-1">
                <input
                  type="checkbox"
                  checked={newRequired}
                  onChange={(e) => setNewRequired(e.target.checked)}
                  className="rounded border-rule text-hema focus:ring-hema"
                />
                <span className="text-ink">Required field</span>
              </label>

              <div className="mt-5 flex justify-end gap-2 pt-2 border-t border-rule">
                <Button variant="quiet" onClick={() => setNewFieldOpen(false)}>
                  Cancel
                </Button>
                <Button variant="primary" onClick={handleCreateCustomField}>
                  Add &amp; Insert XML Field
                </Button>
              </div>
            </div>
          </Sheet>
        </div>
      )}
    </div>
  );
}

/** Individual Field rendering in the Interactive Preview */
function PreviewField({ field, sample, terms }: { field: FormFieldDef; sample: boolean; terms: Terms | undefined }) {
  const isHidden = field.hidden;
  const sampleValue = sample ? SAMPLE_VALUES[field.key] ?? (field.options.length ? field.options[0] : "Sample value") : "";

  if (isHidden) {
    return (
      <div className="rounded-xl border border-dashed border-rule bg-bench/50 p-2.5 text-xs text-ink-3 flex items-center justify-between opacity-60">
        <span className="flex items-center gap-1.5">
          <EyeOff className="size-3.5" />
          <span className="line-through">{field.label}</span>
        </span>
        <span className="text-[10px] font-mono">&lt;field hidden=&quot;true&quot; /&gt;</span>
      </div>
    );
  }

  return (
    <div className={`min-w-0 ${field.type === "long_text" ? "sm:col-span-2" : ""}`}>
      <label className="mb-1 block text-xs font-medium text-ink">
        {field.label}
        {field.required && <span className="text-danger font-semibold"> *</span>}
        {!field.required && <span className="text-ink-3 font-normal"> (optional)</span>}
      </label>

      {field.type === "long_text" ? (
        <textarea
          rows={2}
          readOnly
          value={sampleValue}
          placeholder={field.placeholder || `Enter ${field.label.toLowerCase()}...`}
          className="w-full rounded-lg border border-rule bg-sheet px-3 py-1.5 text-xs text-ink placeholder:text-ink-3/70 focus:outline-none"
        />
      ) : field.type === "choice" || field.type === "status" ? (
        <select
          disabled
          value={sampleValue}
          className="w-full rounded-lg border border-rule bg-sheet px-3 py-1.5 text-xs text-ink focus:outline-none disabled:bg-sheet disabled:opacity-100"
        >
          {field.options.map((o) => (
            <option key={o} value={o}>
              {field.optionNames?.[o] || o}
            </option>
          ))}
          {!field.options.length && <option>Select {field.label.toLowerCase()}...</option>}
        </select>
      ) : field.type === "date" ? (
        <input
          type="date"
          readOnly
          value={sample ? (SAMPLE_VALUES[field.key] || "2026-10-14") : ""}
          className="w-full rounded-lg border border-rule bg-sheet px-3 py-1.5 text-xs text-ink focus:outline-none"
        />
      ) : field.type === "money" ? (
        <div className="relative">
          <span className="absolute left-3 top-1.5 text-xs text-ink-3">₱</span>
          <input
            type="text"
            readOnly
            value={sample ? "1,250,000.00" : ""}
            placeholder="0.00"
            className="w-full rounded-lg border border-rule bg-sheet pl-7 pr-3 py-1.5 text-xs text-ink text-right tabular-nums focus:outline-none"
          />
        </div>
      ) : field.type === "yes_no" ? (
        <label className="mt-1 flex items-center gap-2 text-xs text-ink cursor-pointer">
          <input type="checkbox" checked={sample} readOnly className="rounded border-rule text-hema" />
          <span>{field.label}</span>
        </label>
      ) : field.type === "multi_choice" || field.type === "products" ? (
        <div className="flex flex-wrap gap-1 rounded-lg border border-rule bg-sheet p-1.5 min-h-8 items-center">
          {sample ? (
            (field.options.slice(0, 2).length ? field.options.slice(0, 2) : ["Option A", "Option B"]).map((opt) => (
              <span key={opt} className="rounded-md bg-hema-tint px-2 py-0.5 text-[10px] font-medium text-hema">
                {opt}
              </span>
            ))
          ) : (
            <span className="text-xs text-ink-3 px-1.5">Pick options...</span>
          )}
        </div>
      ) : (
        <input
          type="text"
          readOnly
          value={sampleValue}
          placeholder={field.placeholder || `Enter ${field.label.toLowerCase()}...`}
          className="w-full rounded-lg border border-rule bg-sheet px-3 py-1.5 text-xs text-ink placeholder:text-ink-3/70 focus:outline-none"
        />
      )}

      {field.helpText && <p className="mt-1 text-[11px] text-ink-3">{field.helpText}</p>}
    </div>
  );
}
