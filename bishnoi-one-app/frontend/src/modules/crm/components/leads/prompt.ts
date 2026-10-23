import type { Lead } from "@/src/modules/crm/actions/leads";

// Find leads with AI: the prompt a person takes to their own chatbot, and the
// reader for what they paste back. The answer is treated as data: only the
// known fields are read, whatever else the chatbot wrote.

export type Ask = { where: string; types: { code: string; name: string }[]; focus: string; count: number; company: string; team: string | null };

export function leadPrompt(a: Ask): string {
  const kinds = a.types.map((t) => `"${t.code}" (${t.name})`).join(", ");
  return `You are helping the sales team of ${a.company}, a pharmaceutical company in the Philippines${a.team ? ` (division: ${a.team})` : ""}, find new business customers.

Search the web and find up to ${a.count} real, currently operating businesses in ${a.where || "the Philippines"} that could buy from us.
Kinds of business we want: ${kinds}.${a.focus ? `\nProduct focus: ${a.focus}. Prefer businesses likely to stock or prescribe these.` : ""}

Rules:
- Use web search. Only list businesses you found on a real web page, and give that page as "source". If you cannot search the web, say so and stop.
- Never invent a phone number, email or address. Leave a field empty ("") when the page doesn't show it.
- Business contact details only (the business's own phone, email, website). No personal information about individuals.
- "type" must be exactly one of these codes: ${a.types.map((t) => `"${t.code}"`).join(", ")}.
- "why" is one short sentence on why it's a good fit.

Answer with ONLY one JSON code block, in exactly this format, and nothing after it:

\`\`\`json
[
  {
    "name": "",
    "type": "",
    "address": "",
    "city": "",
    "region": "",
    "phone": "",
    "email": "",
    "website": "",
    "source": "",
    "why": ""
  }
]
\`\`\``;
}

/** Where each chatbot opens with the prompt already in its box (unofficial links: the prompt is always copied too). */
export const CHATBOTS = [
  { key: "chatgpt", label: "ChatGPT", url: (p: string) => `https://chatgpt.com/?q=${encodeURIComponent(p)}`, prefills: true },
  { key: "claude", label: "Claude", url: (p: string) => `https://claude.ai/new?q=${encodeURIComponent(p)}`, prefills: true },
  { key: "deepseek", label: "DeepSeek", url: () => "https://chat.deepseek.com/", prefills: false },
] as const;

const FIELDS: (keyof Lead)[] = ["name", "type", "address", "city", "region", "phone", "email", "website", "source", "why"];
const ALIASES: Record<string, keyof Lead> = {
  business: "name", company: "name", "business name": "name", kind: "type", category: "type", location: "address",
  town: "city", province: "region", telephone: "phone", contact: "phone", "phone number": "phone", "e-mail": "email",
  url: "website", site: "website", link: "source", "source url": "source", reason: "why", "why fit": "why", notes: "why",
};

function keyOf(raw: string): keyof Lead | null {
  const k = raw.trim().toLowerCase().replace(/[_*`]/g, " ").replace(/\s+/g, " ").trim();
  if ((FIELDS as string[]).includes(k)) return k as keyof Lead;
  return ALIASES[k] ?? null;
}

function tidy(rows: Record<string, unknown>[]): Lead[] {
  const out: Lead[] = [];
  for (const row of rows) {
    if (!row || typeof row !== "object") continue;
    const lead: Lead = { name: "" };
    for (const [k, v] of Object.entries(row)) {
      const key = keyOf(k);
      if (key && v !== null && v !== undefined) lead[key] = String(v).trim().slice(0, key === "why" ? 1000 : key === "source" ? 500 : 300);
    }
    if (lead.name) out.push(lead);
  }
  return out;
}

/** The JSON array in a pasted answer: in a code fence, or the first [...] in the text. */
function fromJson(text: string): Lead[] | null {
  const fenced = [...text.matchAll(/```(?:json)?\s*([\s\S]*?)```/gi)].map((m) => m[1]);
  const candidates = [...fenced, text];
  for (const c of candidates) {
    const start = c.indexOf("[");
    const end = c.lastIndexOf("]");
    if (start < 0 || end <= start) continue;
    try {
      const parsed = JSON.parse(c.slice(start, end + 1));
      if (Array.isArray(parsed)) return tidy(parsed);
    } catch {
      // not JSON: try the next one
    }
  }
  return null;
}

function splitLine(line: string, sep: string): string[] {
  if (sep === "|") return line.replace(/^\s*\|/, "").replace(/\|\s*$/, "").split("|").map((s) => s.trim());
  const cells: string[] = [];
  let cur = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (quoted && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else quoted = !quoted;
    } else if (ch === sep && !quoted) {
      cells.push(cur.trim());
      cur = "";
    } else cur += ch;
  }
  cells.push(cur.trim());
  return cells;
}

/** A pasted table: Markdown (|), tab-separated (from a spreadsheet) or CSV, with a header row. */
function fromTable(text: string): Lead[] {
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !/^\|?\s*:?-{2,}/.test(l));
  if (lines.length < 2) return [];
  const sep = lines[0].includes("|") ? "|" : lines[0].includes("\t") ? "\t" : ",";
  const header = splitLine(lines[0], sep).map(keyOf);
  if (!header.includes("name")) return [];
  return tidy(
    lines.slice(1).map((line) => {
      const cells = splitLine(line, sep);
      return Object.fromEntries(header.map((h, i) => [h ?? `x${i}`, cells[i] ?? ""]));
    }),
  );
}

/** Every lead in what was pasted, whichever of the formats the chatbot used. */
export function readPasted(text: string): Lead[] {
  return fromJson(text) ?? fromTable(text);
}
