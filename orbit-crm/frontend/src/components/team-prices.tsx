"use client";

import { X } from "lucide-react";
import { useState, useTransition, type ReactNode } from "react";
import { toast } from "sonner";
import { IconButton } from "@/src/platform/ui/list-editor";
import { PickList, SaveBar } from "@/src/platform/ui/pick-list";
import { CellInput, FormError } from "@/src/platform/ui/field";
import { Empty, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { loadTeamPrices, saveTeamPrices } from "../actions/team-prices";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import type { Org, TeamPriceInput, TeamPriceType, TeamPrices, TeamPricedProduct } from "@/src/platform/lib/types";

// Prices: what one team charges. The company's price list is the default and
// stays as it is; a lead's number sits over it only where they type one, so a
// team that sets nothing prices exactly as it always did. The owners decided
// there is no floor and no approval, which is why nothing here argues with a
// number or asks twice.

/** A team's unsaved sheet: which price types it quotes with, and what it charges, as typed. */
type Draft = { chosen: string[]; amounts: Record<string, string> };

const cellKey = (productId: string, code: string) => `${productId}|${code}`;
const same = (a: string[], b: string[]) => a.length === b.length && [...a].sort().join() === [...b].sort().join();

function toDraft(fmt: Format, sheet: TeamPrices): Draft {
  return {
    chosen: sheet.priceTypes.filter((t) => t.chosen).map((t) => t.code),
    amounts: Object.fromEntries(
      sheet.products.flatMap((p) => Object.entries(p.prices).map(([code, cell]) => [cellKey(p.id, code), fmt.pesosText(cell.team)])),
    ),
  };
}

/** What a team actually quotes with: the ones it ticked, or every one when it ticked none. */
function quoting(sheet: TeamPrices, chosen: string[]): TeamPriceType[] {
  return chosen.length ? sheet.priceTypes.filter((t) => chosen.includes(t.code)) : sheet.priceTypes;
}

/** What a price type is, in one line: where its amount comes from, and when it may be quoted. */
function describe(t: TeamPriceType): string {
  return [
    t.entry === "list" ? "From the price list" : "Typed on the quote, so there's nothing to set here",
    t.rule === "with_rx" && "only when the quote has a prescription",
  ]
    .filter(Boolean)
    .join(" · ");
}

/** A team this person may set prices for. */
export type PricedTeam = { id: string; name: string };

export function TeamPricesEditor({
  teams,
  initial,
  org,
}: {
  teams: PricedTeam[];
  initial: TeamPrices;
  org: Org;
}) {
  const fmt = makeFormat(org);
  const [team, setTeam] = useState(initial.team);
  // Each team's sheet is fetched the first time it's picked and kept, so
  // switching back and forth doesn't cost a wait or lose what was typed.
  const [sheets, setSheets] = useState<Record<string, TeamPrices>>(() => ({ [team]: initial }));
  const [drafts, setDrafts] = useState<Record<string, Draft | undefined>>({});
  const [loading, startLoad] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const sheet = sheets[team];
  const saved = sheet ? toDraft(fmt, sheet) : null;
  const draft = drafts[team] ?? saved;
  const dirtyIn = (code: string) => {
    const there = sheets[code];
    const typed = drafts[code];
    if (!there || !typed) return false;
    const base = toDraft(fmt, there);
    return !same(typed.chosen, base.chosen) || Object.keys(typed.amounts).some((k) => typed.amounts[k] !== base.amounts[k]);
  };
  const picked = teams.find((t) => t.id === team);
  const teamName = picked?.name ?? team;
  const forget = () => setDrafts((all) => ({ ...all, [team]: undefined }));

  function pick(key: string) {
    setTeam(key);
    setError(null);
    if (sheets[key]) return;
    const wanted = teams.find((t) => t.id === key);
    if (!wanted) return;
    startLoad(async () => {
      const result = await loadTeamPrices(wanted.id);
      if (!result.ok) return setError(result.error);
      setSheets((all) => ({ ...all, [key]: result.data }));
    });
  }

  const picker = teams.length > 1 && (
    <PickList
      title="Your teams"
      icon="teams"
      items={teams.map((t) => ({ key: t.id, label: t.name, unsaved: dirtyIn(t.id) }))}
      selected={team}
      onSelect={pick}
    />
  );

  // With no price types set up there is nothing for a lead to price. Say so
  // rather than showing an empty table.
  if (sheet && sheet.priceTypes.length === 0) {
    return (
      <Sheet>
        <Empty icon="pricing" title="There's no price list yet">
          An administrator sets up price types in Administration → Settings → Pricing &amp; retention. Until then there is nothing for{" "}
          {teams.length > 1 ? "your teams" : teamName} to charge over.
        </Empty>
      </Sheet>
    );
  }

  return (
    <div className={`grid grid-cols-[minmax(0,1fr)] gap-5 ${picker ? "lg:grid-cols-[17rem_minmax(0,1fr)] lg:items-start" : ""}`}>
      {picker}
      <div className="min-w-0" aria-busy={loading || undefined}>
        {!sheet || !draft || !saved ? (
          <Sheet>
            <Empty icon="pricing" title="Fetching this team's prices…" />
          </Sheet>
        ) : (
          <TeamSheet
            key={team}
            fmt={fmt}
            team={team}
            teamName={teamName}
            sheet={sheet}
            saved={saved}
            draft={draft}
            dirty={dirtyIn(team)}
            setDraft={(next) => setDrafts((all) => ({ ...all, [team]: next }))}
            forget={forget}
            onSaved={(fresh) => {
              setSheets((all) => ({ ...all, [team]: fresh }));
              forget();
            }}
          />
        )}
        <FormError message={error} />
      </div>
    </div>
  );
}

function TeamSheet({
  fmt,
  team,
  teamName,
  sheet,
  saved,
  draft,
  dirty,
  setDraft,
  forget,
  onSaved,
}: {
  fmt: Format;
  team: string;
  teamName: string;
  sheet: TeamPrices;
  saved: Draft;
  draft: Draft;
  dirty: boolean;
  setDraft: (draft: Draft) => void;
  forget: () => void;
  onSaved: (fresh: TeamPrices) => void;
}) {
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, start] = useTransition();

  const columns = quoting(sheet, draft.chosen).filter((t) => t.entry === "list");
  const tick = (code: string, on: boolean) =>
    setDraft({ ...draft, chosen: on ? [...draft.chosen, code] : draft.chosen.filter((c) => c !== code) });
  const write = (key: string, text: string) => setDraft({ ...draft, amounts: { ...draft.amounts, [key]: text } });

  function save() {
    const found: Record<string, string> = {};
    const items: TeamPriceInput[] = [];
    for (const [key, text] of Object.entries(draft.amounts)) {
      if (text === saved.amounts[key]) continue;
      const [productId, priceTypeCode] = key.split("|");
      const amountCentavos = text.trim() ? fmt.toCentavos(text) : null;
      if (text.trim() && amountCentavos === null) found[key] = `An amount in ${fmt.currency}, like 1250.`;
      else items.push({ productId, priceTypeCode, amountCentavos });
    }
    setProblems(found);
    if (Object.keys(found).length) return setError("Some amounts need a look.");
    const codes = same(draft.chosen, saved.chosen) ? undefined : draft.chosen;
    start(async () => {
      const result = await saveTeamPrices(team, { codes, items });
      if (!result.ok) return setError(result.error);
      setError(null);
      onSaved(result.data);
      toast.success("Special prices saved", { description: `Reps in ${teamName} see them on their next quote.` });
    });
  }

  return (
    <div className="space-y-5">
      <Sheet className="max-w-[54rem] px-5 pt-4 pb-5">
        <SectionTitle icon="pricing">Prices {teamName} quotes with</SectionTitle>
        <p className="text-meta text-ink-3">
          Which prices your reps may pick on a quote. Tick none and the team quotes with all of them.
        </p>
        <ul className="mt-3 divide-y divide-rule border-y border-rule">
          {sheet.priceTypes.map((t) => {
            const on = draft.chosen.includes(t.code);
            return (
              <li key={t.code} className="py-2.5">
                <label className="flex cursor-pointer items-start gap-3">
                  <input type="checkbox" checked={on} onChange={(e) => tick(t.code, e.target.checked)} className="mt-0.5 size-4 shrink-0 accent-hema" />
                  <span className="min-w-0">
                    <span className={on ? "font-semibold" : ""}>{t.name}</span>
                    <span className="block text-meta text-ink-3">{describe(t)}</span>
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
        {draft.chosen.length === 0 && (
          <p className="mt-2.5 text-meta text-ink-2">Nothing ticked, so {teamName} quotes with all of them.</p>
        )}
      </Sheet>

      <Sheet className="max-w-[54rem] px-5 pt-4 pb-4">
        <SectionTitle icon="products">{teamName}&apos;s special prices</SectionTitle>
        <p className="text-meta text-ink-3">
          Leave a price empty and it follows the standard price. Your team quotes at these; a salesperson asking for a lower one sends it to you for approval.
        </p>
        {columns.length === 0 ? (
          <Empty icon="products" title="Nothing to set here">
            Every price {teamName} quotes with is typed on the quote itself, so there is no list to price from.
          </Empty>
        ) : sheet.products.length === 0 ? (
          <Empty icon="products" title="No products yet">Products and their standard prices are kept in Products.</Empty>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm sm:min-w-[42rem]">
              <thead>
                <tr className="border-b border-rule text-caps text-ink-3 uppercase">
                  <th scope="col" className="w-full py-2 pr-3 font-semibold">Product</th>
                  {/* A phone has no room for three money columns, so the company's
                      price and the difference move under the product's name. */}
                  <th scope="col" className="hidden px-3 py-2 text-right font-semibold sm:table-cell">Standard</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold normal-case tracking-normal">{teamName}</th>
                  <th scope="col" className="hidden py-2 pl-3 font-semibold sm:table-cell">Difference</th>
                </tr>
              </thead>
              {columns.map((t) => (
                <tbody key={t.code}>
                  <tr>
                    <th colSpan={4} scope="colgroup" className="pt-4 pb-1 text-left text-meta font-semibold text-ink-2">
                      {t.name}
                      {t.rule === "with_rx" && <span className="font-normal text-ink-3"> · only with a prescription</span>}
                    </th>
                  </tr>
                  {sheet.products.map((p) => (
                    <PriceRow
                      key={p.id}
                      fmt={fmt}
                      product={p}
                      type={t}
                      text={draft.amounts[cellKey(p.id, t.code)] ?? ""}
                      problem={problems[cellKey(p.id, t.code)]}
                      onType={(text) => write(cellKey(p.id, t.code), text)}
                    />
                  ))}
                </tbody>
              ))}
            </table>
          </div>
        )}
      </Sheet>

      {dirty && (
        <SaveBar
          what={`Unsaved changes to the prices for ${teamName}`}
          saving={saving}
          onSave={save}
          onDiscard={() => {
            forget();
            setProblems({});
            setError(null);
          }}
          error={<FormError message={error} />}
        />
      )}
    </div>
  );
}

function PriceRow({
  fmt,
  product,
  type,
  text,
  problem,
  onType,
}: {
  fmt: Format;
  product: TeamPricedProduct;
  type: TeamPriceType;
  text: string;
  problem?: string;
  onType: (text: string) => void;
}) {
  const cell = product.prices[type.code];
  const company = cell?.company ?? null;
  const companyText = company === null ? "—" : fmt.peso(company);
  const label = `${product.name}, ${type.name}`;
  return (
    <tr className="border-t border-rule align-top">
      <th scope="row" className="py-2.5 pr-3 text-left font-medium">
        {product.name}
        <span className="block text-meta font-normal text-ink-3">
          {product.code} · {product.unit}
        </span>
        <span className="mt-0.5 block text-meta font-normal sm:hidden">
          {text.trim() ? (
            <>
              <span className="text-ink-3">Standard {companyText}</span> · {difference(fmt, company, text)}
            </>
          ) : (
            <span className="text-ink-3">Follows standard · {companyText}</span>
          )}
        </span>
      </th>
      <td className="hidden px-3 py-2.5 text-right whitespace-nowrap tabular-nums sm:table-cell">
        {company === null ? <span className="text-ink-3">—</span> : companyText}
      </td>
      <td className="px-3 py-2.5">
        <span className="flex items-center justify-end gap-1">
          <span className="text-meta text-ink-3">{fmt.symbol}</span>
          <CellInput
            aria-label={`${label}: what your team charges. Leave empty to follow the standard price.`}
            aria-invalid={problem ? true : undefined}
            inputMode="decimal"
            value={text}
            onChange={(e) => onType(e.target.value)}
            className="w-28 sm:w-32"
          />
          {/* Emptying the box is what hands the price back, so there's a button that does it. */}
          <span className="w-8 shrink-0">
            {text !== "" && (
              <IconButton label={`Clear ${label} and follow the standard price`} onClick={() => onType("")}>
                <X className="size-4" aria-hidden />
              </IconButton>
            )}
          </span>
        </span>
        {problem && <span className="mt-1 block text-right text-meta text-danger">{problem}</span>}
      </td>
      <td className="hidden py-2.5 pl-3 whitespace-nowrap sm:table-cell">{difference(fmt, company, text)}</td>
    </tr>
  );
}

/** How the team's price reads against the company's, in words rather than a sign. */
function difference(fmt: Format, company: number | null, text: string): ReactNode {
  if (!text.trim()) return <span className="text-ink-3">Follows standard</span>;
  const team = fmt.toCentavos(text);
  if (team === null) return <span className="text-danger">Check this amount</span>;
  if (company === null) return <span className="text-ink-2">No standard price here</span>;
  if (team === company) return <span className="text-ink-3">Same as standard</span>;
  return (
    <span className="text-ink-2 tabular-nums">
      {fmt.peso(Math.abs(team - company))} {team < company ? "less" : "more"}
    </span>
  );
}
