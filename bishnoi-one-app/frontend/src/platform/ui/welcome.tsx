import { Sparkles, Target } from "lucide-react";

// The welcome on every module's home (decided 2026-10-26): a short line to start the day on, a new
// one each visit, and what this module, and the person's team and division, put first today, as
// three short points. Drawn on the server; nothing to load.

export type WelcomeModule = "crm" | "inventory" | "finance" | "pharmacy" | "admin";

const LINES = [
  "Small steps every day add up to big results.",
  "Progress, not perfection.",
  "Every call you make today is a door you open.",
  "Do the important thing first.",
  "Consistency beats intensity.",
  "Your best work today sets up tomorrow.",
  "One more follow-up can be the one that closes it.",
  "Good records today save hours tomorrow.",
  "Focus on what moves the number.",
  "Start strong, finish stronger.",
  "Make today count.",
  "The customer remembers how you made them feel.",
  "Done is better than perfect. Then make it better.",
  "Clear the small things, then go big.",
  "Great teams win together.",
  "Keep it simple. Keep it moving.",
  "Every detail matters to a patient.",
  "Plan the work, then work the plan.",
];

/** What a module puts first, for everyone in it. */
const MODULE_FOCUS: Record<WelcomeModule, string[]> = {
  crm: ["Follow up within 24 hours", "Move every open deal a step", "Keep customer profiles complete"],
  inventory: ["First to expire, first out", "Reorder before stock runs low", "Receive and put away the same day"],
  finance: ["Collect what's due", "File BIR forms on time", "Close the books every month"],
  pharmacy: ["Verify prescriptions promptly", "First to expire, first out", "Record every sale"],
  admin: ["Renew before anything lapses", "Resolve office requests quickly", "Keep fleet and travel on schedule"],
};

/** What a team or division puts first, matched on its name (CRM divisions by the 2026 org chart). */
const TEAM_FOCUS: { match: RegExp; focus: string[] }[] = [
  { match: /\b(hos|hospital|onco|pap)\b/i, focus: ["Cover cancer centers and oncologists", "Patient assistance (PAP) cases", "Formulary listings"] },
  { match: /\b(stc|uro|b&b|rx|prescription)\b/i, focus: ["Visit your top prescribers", "Detail the focus products", "Log every visit the same day"] },
  { match: /\bnbd\b/i, focus: ["Open new distributors and drugstores", "First orders from new accounts", "Quotes out within a day"] },
  { match: /\bcrr\b/i, focus: ["Reorders from existing accounts", "Credit standing in good order", "Win back quiet customers"] },
  { match: /\b(telesales|b2c|online)\b/i, focus: ["Answer enquiries the same day", "Turn quotes into orders", "Call back every missed lead"] },
  { match: /\b(government|bidding|bid|clidp)\b/i, focus: ["Bid deadlines on PhilGEPS", "CLIDP validity", "Documents ready before the opening"] },
  { match: /\b(modern trade|chain)\b/i, focus: ["Shelf availability in every branch", "Reorders on schedule", "Promos running on time"] },
];

/** A team lead's first point: the team. */
const LEAD_FOCUS = "Coach whoever is furthest behind";

export function Welcome({
  module,
  name,
  greeting,
  team,
  lead = false,
}: {
  module: WelcomeModule;
  /** Their first name. */
  name: string;
  /** "Good morning", from the company's clock (fmt.greeting()); left out where the page title already greets. */
  greeting?: string;
  /** Their main team or division's name, when the module has one. */
  team?: string | null;
  /** They lead a team. */
  lead?: boolean;
}) {
  const line = LINES[Math.floor(Math.random() * LINES.length)];
  const fromTeam = team ? TEAM_FOCUS.find((t) => t.match.test(team))?.focus : undefined;
  const focus = [...(lead ? [LEAD_FOCUS] : []), ...(fromTeam ?? MODULE_FOCUS[module])].slice(0, 3);
  return (
    <section aria-label="Welcome" className="mb-5 flex flex-wrap items-center gap-x-6 gap-y-3 rounded-2xl bg-gradient-to-r from-mint to-mint-2/60 px-5 py-4">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-white text-sage-deep shadow-[0_1px_2px_rgba(20,20,20,0.06)]">
          <Sparkles className="size-5" aria-hidden />
        </span>
        <div className="min-w-0">
          {greeting ? (
            <>
              <p className="text-sm font-semibold text-ink">
                {greeting}, {name}.
              </p>
              <p className="text-sm text-ink-2">{line}</p>
            </>
          ) : (
            <p className="text-sm font-semibold text-ink">{line}</p>
          )}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 text-meta font-semibold text-sage-deep">
          <Target className="size-3.5" aria-hidden />
          {team ? `${team} focus` : "Today's focus"}
        </span>
        {focus.map((f) => (
          <span key={f} className="rounded-full bg-white px-3 py-1 text-meta font-medium text-ink shadow-[0_1px_2px_rgba(20,20,20,0.05)]">
            {f}
          </span>
        ))}
      </div>
    </section>
  );
}
